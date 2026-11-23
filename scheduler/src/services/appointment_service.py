import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from src.services.db.postgres import PostgresService
from src.services.relogio import HOJE_SQL
from src.services.desconto_personalizado import aplica as aplica_desconto
from src.services.desconto_personalizado import DescontoInvalido, RAZAO as RAZAO_PERSONALIZADO
from src.services.desconto_personalizado import pct_equivalente
from src.services.primeira_visita import e_primeira_visita, passa_a_marca_adiante
from src.services.reagendamento import vincula_antecessor
from src.services.desfecho import DESFECHOS, DesfechoInvalido, desfecho_do_agendamento
from src.services.politica_de_desconto import decide, preco_de_tabela
from src.services.duration_rules import (
    calcula_duracao, duracao_da_sessao, duracao_do_carrinho, get_duration_rules)
from src.services.duracao_manual import efetiva as duracao_efetiva
from src.services.duracao_manual import valida as valida_duracao_manual

logger = logging.getLogger(__name__)


class _SemMudanca:
    """Marca "o pedido nao falou sobre isso".

    `None` ja significa outra coisa - limpar a duracao manual - entao nao serve
    como padrao. Sem separar os dois, trocar a area sempre pareceria um pedido
    de limpar o override.
    """

    def __repr__(self):
        return "SEM_MUDANCA"


SEM_MUDANCA = _SemMudanca()


class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


class MudancaDeData(ValueError):
    """`reschedule_appointment` e para a MESMA data (PRD 054). Outra data e
    remarcacao: `remarca`, que encerra o antigo e cria o novo."""


class OptimisticLockError(Exception):
    pass


class SessaoNoMesmoMes(Exception):
    """A paciente ja tem sessao confirmada futura no mes-calendario da data
    pedida (PRD 056). `existente` e a mais proxima: id, appointment_date,
    start_time, areas_display, patient_name. Quem chama monta o aviso
    ("sua sessao de X sera cancelada e remarcada") e repete o pedido com
    `substituir_mesmo_mes=True`; so o painel, por ADMIN e com motivo, pode
    `permitir_duas=True`."""

    def __init__(self, existente):
        super().__init__("Ja existe sessao confirmada neste mes")
        self.existente = existente


class OutraSessaoFutura(Exception):
    """A paciente ja tem sessao confirmada futura em OUTRO mes (PRD 060).
    Nao e bloqueio: e a pergunta "remarcar essa sessao ou marcar mais uma?".
    `existente` tem a mesma carga de `SessaoNoMesmoMes` (a mais proxima).
    Quem chama repete o pedido com `remarcar_a_existente=True` (vira a troca
    da 056: a existente sai pelo desfecho da antecedencia e a nova nasce
    vinculada) ou `mais_uma=True` (cria a segunda, como antes do 060).

    Em 23/11/2026 duas pacientes da Essencia que queriam remarcar criaram a
    sessao nova em dezembro pelo site: novembro ficou de pe, o lembrete saiu
    e a recepcao cancelou a mao. Mes diferente passava em silencio."""

    def __init__(self, existente):
        super().__init__("Ja existe sessao confirmada em outro mes")
        self.existente = existente


class AppointmentService:

    def __init__(self, db: PostgresService, reminder_service=None, lead_service=None):
        self.db = db
        self.reminder_service = reminder_service
        self.lead_service = lead_service

    @classmethod
    def completo(cls, db: PostgresService) -> "AppointmentService":
        """O serviço com tudo que ele precisa para não perder conversão.

        Existe porque `lead_service=None` é um default silencioso: sem ele, o
        bloco que marca o lead como agendado e registra a conversão do gclid
        simplesmente não roda, e ninguém percebe - o agendamento é criado
        normalmente, só não chega ao Google Ads.

        Foi o que aconteceu em produção até 27/09/2026: o webhook do bot
        passava `lead_service`, mas o painel, a edição e o agente montavam o
        serviço sem ele. **57% dos agendamentos vindos de anúncio ficaram
        invisíveis** para o Google - 16 de 28 em 30 dias, R$ 3.984,50 de
        receita não reportada.

        Quem cria agendamento usa esta fábrica. O construtor continua aberto
        para os testes, que precisam injetar dublê.
        """
        from src.services.lead_service import LeadService

        return cls(db, lead_service=LeadService(db))

    def _fuso_da_clinica(self, clinic_id):
        """So o `timezone`, para o lembrete sair na hora certa. Falha vira
        vazio, que o lembrete trata como America/Sao_Paulo."""
        try:
            linhas = self.db.execute_query(
                "SELECT timezone FROM scheduler.clinics WHERE clinic_id = %s",
                (clinic_id,),
            )
            return linhas[0] if linhas else {}
        except Exception as e:
            logger.warning(f"[AppointmentService] Nao li o fuso de {clinic_id}: {e}")
            return {}

    # -- Conflito de horário (PRD 049) --------------------------------------
    #
    # Uma regra, um lugar. Há conflito quando uma sessão CONFIRMED do mesmo
    # dia e clínica é invadida pela janela nova em MAIS de
    # `tolerancia_minutos`, medida por vizinha (LEAST dos fins - GREATEST dos
    # inícios). Com 0, qualquer sobreposição conta e encostar não conta: é a
    # regra que sempre valeu. Só a edição manual pelo painel passa 15
    # (`functions/appointment/update.py`); bot, site e criação ficam em 0.
    def _conflitos(self, clinic_id: str, data, inicio: str, fim: str,
                   excluir_id: Optional[str] = None, tolerancia_minutos: int = 0):
        sql = (
            "SELECT id FROM scheduler.appointments "
            "WHERE clinic_id = %s AND appointment_date = %s AND status = 'CONFIRMED' "
        )
        params: list = [clinic_id, data]
        if excluir_id:
            sql += "AND id != %s::uuid "
            params.append(excluir_id)
        sql += (
            "AND start_time < %s::time AND end_time > %s::time "
            "AND (LEAST(end_time, %s::time) - GREATEST(start_time, %s::time)) > (%s * interval '1 minute')"
        )
        params += [fim, inicio, fim, inicio, int(tolerancia_minutos or 0)]
        return self.db.execute_query(sql, tuple(params))

    @staticmethod
    def _mensagem_de_conflito(padrao: str, tolerancia_minutos: int, data, inicio: str, fim: str) -> str:
        if tolerancia_minutos:
            return (f"Conflito de horário: a sessão invadiria a vizinha em mais de "
                    f"{int(tolerancia_minutos)} minutos ({data} {inicio}-{fim})")
        return padrao

    def sessao_no_mesmo_mes(self, clinic_id: str, phone: str, data,
                            excluir_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """A sessao CONFIRMED futura deste numero (variantes, mesma clinica) no
        mesmo ano-mes de `data`, a mais proxima; None se nao houver (PRD 056).

        Mes-calendario de proposito, decisao do Andre: duas sessoes no mesmo
        mes sao engano ou remarcacao mal feita; no mes seguinte e antecipar a
        reserva. `excluir_id` e o proprio agendamento quando se esta movendo.
        So uma lista de verdade conta: um duble que devolva outra coisa nao
        pode virar conflito.
        """
        return self._sessao_confirmada_futura(clinic_id, phone, data, mesmo_mes=True, excluir_id=excluir_id)

    def sessao_futura_em_outro_mes(self, clinic_id: str, phone: str, data) -> Optional[Dict[str, Any]]:
        """A sessao CONFIRMED futura deste numero em OUTRO ano-mes que o de
        `data`, a mais proxima; None se nao houver (PRD 060). Nao bloqueia
        nada: e o que faz criar perguntar "remarcar ou mais uma?"."""
        return self._sessao_confirmada_futura(clinic_id, phone, data, mesmo_mes=False)

    def _sessao_confirmada_futura(self, clinic_id: str, phone: str, data, mesmo_mes: bool,
                                  excluir_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        from src.utils.phone import variantes_do_numero
        variantes = sorted(variantes_do_numero(phone or ""))
        if not variantes or not data:
            return None
        operador = "=" if mesmo_mes else "<>"
        sql = f"""
            SELECT a.id, a.appointment_date, a.start_time, p.name AS patient_name,
                   (SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at)
                      FROM scheduler.appointment_service_areas asa
                     WHERE asa.appointment_id = a.id) AS areas_display
              FROM scheduler.appointments a
              JOIN scheduler.patients p ON p.id = a.patient_id
             WHERE a.clinic_id = %s AND p.clinic_id = %s AND p.phone = ANY(%s)
               AND p.deleted_at IS NULL AND a.status = 'CONFIRMED'
               AND a.appointment_date >= {HOJE_SQL}
               AND date_trunc('month', a.appointment_date) {operador} date_trunc('month', %s::date)
        """
        params: list = [clinic_id, clinic_id, variantes, str(data)]
        if excluir_id:
            sql += " AND a.id <> %s::uuid"
            params.append(str(excluir_id))
        sql += " ORDER BY a.appointment_date, a.start_time LIMIT 1"
        linhas = self.db.execute_query(sql, tuple(params))
        if not isinstance(linhas, list) or not linhas:
            return None
        return linhas[0]

    def _leva_para_o_novo(self, antigo_id: str, antigo: Dict[str, Any], novo_id: str) -> None:
        """O que e por agendamento acompanha a paciente quando um registro
        substitui outro (PRD 054/056): vinculo nos dois sentidos, pagamento
        vivo (um pago no antigo apareceria como estorno pendente) e o link dos
        documentos ja enviado."""
        self.db.execute_write(
            "UPDATE scheduler.appointments SET rescheduled_from_id = %s::uuid, updated_at = NOW() "
            "WHERE id = %s::uuid",
            (antigo_id, novo_id),
        )
        self.db.execute_write(
            "UPDATE scheduler.appointments SET rescheduled_to_id = %s::uuid, updated_at = NOW() "
            "WHERE id = %s::uuid AND rescheduled_to_id IS NULL",
            (novo_id, antigo_id),
        )
        self.db.execute_write(
            "UPDATE scheduler.appointment_payments SET appointment_id = %s::uuid "
            "WHERE appointment_id = %s::uuid AND status IN ('PENDING', 'AWAITING_CASH', 'PAID')",
            (novo_id, antigo_id),
        )
        if antigo.get("consent_link_sent_at"):
            self.db.execute_write(
                "UPDATE scheduler.appointments SET consent_link_sent_at = %s WHERE id = %s::uuid",
                (antigo["consent_link_sent_at"], novo_id),
            )

    def create_appointment(
        self,
        clinic_id: str,
        phone: str,
        service_id: str,
        date: str,
        time: str,
        professional_id: Optional[str] = None,
        service_ids: Optional[List[str]] = None,
        total_duration_minutes: Optional[int] = None,
        manual_duration_minutes: Optional[int] = None,
        service_area_pairs: Optional[List[Dict[str, str]]] = None,
        discount_pct: int = 0,
        discount_reason: Optional[str] = None,
        original_price_cents: Optional[int] = None,
        final_price_cents: Optional[int] = None,
        full_name: Optional[str] = None,
        notes: Optional[str] = None,
        is_first_visit: Optional[bool] = None,
        cpf: Optional[str] = None,
        birth_date: Optional[str] = None,
        email: Optional[str] = None,
        discount_cents: Optional[int] = None,
        substituir_mesmo_mes: bool = False,
        permitir_duas: bool = False,
        autor: Optional[str] = None,
        motivo_das_duas: Optional[str] = None,
        remarcar_a_existente: bool = False,
        mais_uma: bool = False,
    ) -> Dict[str, Any]:
        """`is_first_visit=None` deixa o sistema decidir; um booleano manda.

        Uma sessao por mes (PRD 056): se a paciente ja tem sessao confirmada
        futura no mes de `date`, levanta `SessaoNoMesmoMes` com a existente.
        `substituir_mesmo_mes=True` e a confirmacao do aviso: a existente e
        cancelada com o desfecho da antecedencia (falta nas ultimas 24 h) e o
        novo nasce vinculado a ela, levando pagamento vivo, link dos documentos
        e conversao. `permitir_duas=True` mantem as duas: so o painel passa,
        por ADMIN e com `motivo_das_duas`, gravado no novo com `autor`.

        Sessao futura em OUTRO mes (PRD 060): nao bloqueia, pergunta. Sem
        `remarcar_a_existente` nem `mais_uma`, levanta `OutraSessaoFutura`
        com a existente. `remarcar_a_existente=True` e a mesma troca do
        `substituir_mesmo_mes`, so que da sessao de outro mes; `mais_uma=True`
        cria a segunda e nao grava nada: antecipar a reserva e legitimo.

        `discount_cents` (PRD 050) e o desconto em reais, so pelo painel. Quando
        vem, e a fonte do preco: vence o percentual e o combinado da paciente,
        e `discount_pct` recebe o equivalente so para leitura.

        O bot passa None: ele conversa com quem chega da landing page e nao tem
        ninguem para conferir. O painel manda o valor da caixinha, porque quem
        esta na recepcao sabe de historico que o banco nao tem - pessoa que ja
        veio antes do sistema existir, ou que remarcou por fora.
        """
        # 1. Get or create patient
        patient = self._get_or_create_patient(clinic_id, phone, full_name, cpf, birth_date, email)
        patient_id = str(patient["id"])

        # 1b. Uma sessao por mes (PRD 056). Antes de qualquer escrita de
        # agendamento; a existente so e cancelada depois de o horario novo
        # caber (passo 4), para um conflito nao deixar a paciente sem sessao.
        existente = self.sessao_no_mesmo_mes(clinic_id, phone, date)
        if existente and not (substituir_mesmo_mes or permitir_duas):
            raise SessaoNoMesmoMes(existente)

        # 1c. Sessao futura em OUTRO mes (PRD 060): pergunta, nao bloqueio.
        # So quando o mes esta livre; com `permitir_duas` o ADMIN ja decidiu.
        outra = None
        if not existente and not permitir_duas:
            outra = self.sessao_futura_em_outro_mes(clinic_id, phone, date)
            if outra and not (remarcar_a_existente or mais_uma):
                raise OutraSessaoFutura(outra)

        # 2. Resolve service list and duration
        all_service_ids = service_ids if service_ids else [service_id]
        primary_service_id = all_service_ids[0]

        # Fetch base service info
        placeholders = ", ".join(["%s"] * len(all_service_ids))
        services = self.db.execute_query(
            f"SELECT id, duration_minutes, name, price_cents FROM scheduler.services WHERE id::text IN ({placeholders}) AND active = TRUE",
            tuple(all_service_ids),
        )
        if not services:
            raise NotFoundError(f"Serviço(s) não encontrado(s)")

        # Build a lookup by id for ordering and data
        svc_lookup = {str(s["id"]): s for s in services}

        # A duração é sempre derivada, nunca informada. O parâmetro
        # total_duration_minutes continua na assinatura para não quebrar quem
        # chama, mas não decide nada: o agente já pediu horário para uma sessão
        # de 4 minutos com ele. Ver duration_rules.py.
        # A mesma conta que o site público usa para pedir horário - ver
        # duracao_do_carrinho.
        duration_minutes = duracao_do_carrinho(
            self.db, clinic_id, all_service_ids, service_area_pairs, servicos=services)

        if total_duration_minutes and int(total_duration_minutes) != duration_minutes:
            logger.info(
                f"[Duracao] {clinic_id}: ignorando total_duration_minutes="
                f"{total_duration_minutes} do chamador; calculado={duration_minutes}"
            )

        # A duracao que uma PESSOA fixou vale sobre o calculo - e so ela.
        # `total_duration_minutes` acima continua valendo zero: quem passa aquele
        # campo e o bot (ai_tools), e foi ele que pediu
        # horario para uma sessao de 4 minutos. Sao dois campos com significados
        # diferentes de proposito. Ver duracao_manual.
        manual = valida_duracao_manual(manual_duration_minutes)
        if manual:
            logger.info(
                f"[Duracao] {clinic_id}: duracao manual de {manual}min "
                f"(calculado={duration_minutes})"
            )
        duration_minutes = duracao_efetiva(duration_minutes, manual)

        # 2a-bis. Ninguem opinou: vale a politica da clinica (PRD 053).
        #
        # `discount_pct` zerado E sem razao significa "ninguem decidiu", e a
        # resposta e a MESMA do bot e do site: `decide` (combinado da paciente
        # vence; senao o maior entre primeira sessao e faixa de areas). Ate
        # 20/11/2026 so o combinado era aplicado aqui, e um agendamento feito
        # pela recepcao nunca ganhava primeira sessao nem faixa.
        #
        # O painel opina quando escolhe parceria, personalizado ou "Sem
        # desconto" - este ultimo chega como pct 0 com razao "none", e e o que
        # o deixa fora deste if. Bot e site passam pct 0 sem razao quando a
        # politica deles nao deu nada: `decide` roda de novo com os mesmos
        # dados e o mesmo resultado, uma consulta a mais.
        #
        # Fica antes do bloco de precos de proposito: o final_price_cents e
        # calculado logo abaixo a partir do discount_pct, e mudar o desconto
        # depois deixaria o valor gravado divergente do desconto gravado.
        if discount_cents is None and not discount_pct and not discount_reason:
            decisao = decide(self.db, clinic_id, phone, len(service_area_pairs or []))
            if decisao.pct:
                discount_pct, discount_reason = decisao.pct, decisao.razao

        # 2b. Auto-calculate prices when not provided by caller
        if original_price_cents is None:
            # A mesma conta que a cotação do site mostra antes de confirmar.
            original_price_cents = preco_de_tabela(
                self.db, all_service_ids, service_area_pairs, servicos=services)

            if original_price_cents is not None:
                final_price_cents = aplica_desconto(original_price_cents, discount_pct)

        # 2c. Desconto em reais (PRD 050): subtracao exata sobre o preco de
        # tabela. Sem preco de tabela nao ha do que tirar.
        if discount_cents is not None:
            if original_price_cents is None:
                raise DescontoInvalido("desconto em reais exige preco de tabela")
            final_price_cents = aplica_desconto(original_price_cents, None, cents=discount_cents)
            discount_pct = pct_equivalente(original_price_cents, discount_cents)
            discount_reason = discount_reason or RAZAO_PERSONALIZADO

        # 3. Calculate end_time
        start_parts = time.split(":")
        start_hour, start_min = int(start_parts[0]), int(start_parts[1])
        total_minutes = start_hour * 60 + start_min + duration_minutes
        end_hour, end_min = total_minutes // 60, total_minutes % 60
        end_time = f"{end_hour:02d}:{end_min:02d}"

        # 4. Check for conflicts (criação nunca tolera sobreposição, PRD 049)
        conflicts = self._conflitos(clinic_id, date, time, end_time)

        if conflicts:
            raise ConflictError(f"Conflito de horário: já existe agendamento para {date} {time}-{end_time}")

        # 4b. A troca confirmada (PRD 056): a sessao do mes sai com o desfecho
        # da antecedencia e, depois do INSERT, o novo recebe o que era dela.
        substituida = None
        if existente and substituir_mesmo_mes and not permitir_duas:
            substituida = self.cancel_appointment(str(existente["id"]), autor=autor)
            logger.info(
                f"[MesmoMes] {clinic_id}: sessao {existente['id']} de {existente['appointment_date']} "
                f"substituida por {date} {time} (desfecho={substituida['outcome']}, autor={autor!r})"
            )
        elif outra and remarcar_a_existente:
            # A troca da 056, so que da sessao de outro mes (PRD 060).
            substituida = self.cancel_appointment(str(outra["id"]), autor=autor)
            logger.info(
                f"[OutroMes] {clinic_id}: sessao {outra['id']} de {outra['appointment_date']} "
                f"remarcada para {date} {time} (desfecho={substituida['outcome']}, autor={autor!r})"
            )
        elif outra and mais_uma:
            logger.info(f"[OutroMes] {clinic_id}: mais uma sessao alem da de {outra['appointment_date']} (autor={autor!r})")

        # 5. Resolve professional
        prof_id_param = None
        if professional_id:
            prof_id_param = professional_id
        else:
            professionals = self.db.execute_query(
                "SELECT id FROM scheduler.professionals WHERE clinic_id = %s AND active = TRUE LIMIT 1",
                (clinic_id,),
            )
            if professionals:
                prof_id_param = str(professionals[0]["id"])

        # 6. Insert appointment
        result = self.db.execute_write_returning(
            """
            INSERT INTO scheduler.appointments (
                clinic_id, patient_id, professional_id, service_id,
                appointment_date, start_time, end_time,
                total_duration_minutes, manual_duration_minutes,
                discount_pct, discount_cents, discount_reason, original_price_cents, final_price_cents,
                full_name, notes,
                status, created_at, updated_at, version
            ) VALUES (
                %s, %s::uuid, %s::uuid, %s::uuid,
                %s, %s::time, %s::time,
                %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                'CONFIRMED', NOW(), NOW(), 1
            )
            RETURNING *
            """,
            (clinic_id, patient_id, prof_id_param, primary_service_id,
             date, time, end_time,
             duration_minutes, manual,
             discount_pct, discount_cents, discount_reason, original_price_cents, final_price_cents,
             full_name, (notes or None)),
        )

        if not result:
            raise Exception("Erro ao criar agendamento")

        appointment_id = str(result["id"])

        # Estreia. Quando o chamador nao opina (`None`), o sistema conta os
        # agendamentos confirmados: e o caso do bot, que atende quem chega da
        # landing page sem ninguem por perto para conferir.
        #
        # O painel opina sempre, e por decisao do Andre em 09/09/2026 opina
        # False por padrao. A contagem automatica so enxerga o que esta neste
        # banco, e a clinica atende desde antes dele existir - marcar "primeira
        # vez" em cliente antiga na frente dela e o erro que custa caro.
        #
        # Depois do INSERT e por isso `ignorar_id`: neste ponto o proprio
        # agendamento ja esta no banco e contaria a si mesmo.
        estreia = (
            e_primeira_visita(self.db, clinic_id, phone, ignorar_id=appointment_id)
            if is_first_visit is None
            else is_first_visit
        )
        if estreia:
            self.db.execute_write(
                "UPDATE scheduler.appointments SET is_first_visit = TRUE "
                "WHERE id = %s::uuid", (appointment_id,))
            result["is_first_visit"] = True

        # 7. Insert into junction tables
        if service_area_pairs:
            # Services WITH areas -> appointment_service_areas (1 row per pair)
            # Fetch info for each pair
            values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
            params = ()
            for pair in service_area_pairs:
                params += (pair["service_id"], pair["area_id"])
            pair_rows = self.db.execute_query(
                f"""SELECT pairs.service_id, pairs.area_id,
                       s.name as service_name, a.name as area_name,
                       COALESCE(sa.duration_minutes, s.duration_minutes) as duration_minutes,
                       COALESCE(sa.price_cents, s.price_cents) as price_cents
                FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                JOIN scheduler.services s ON s.id = pairs.service_id
                JOIN scheduler.areas a ON a.id = pairs.area_id
                LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
                params,
            )
            for row in pair_rows:
                self.db.execute_write(
                    """
                    INSERT INTO scheduler.appointment_service_areas
                        (appointment_id, service_id, area_id, area_name, service_name, duration_minutes, price_cents)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s)
                    """,
                    (appointment_id, str(row["service_id"]), str(row["area_id"]),
                     row["area_name"], row["service_name"],
                     row["duration_minutes"], row.get("price_cents")),
                )
        else:
            # Services WITHOUT areas -> appointment_services (as before)
            for sid in all_service_ids:
                svc = svc_lookup.get(sid)
                if svc:
                    self.db.execute_write(
                        """
                        INSERT INTO scheduler.appointment_services
                            (appointment_id, service_id, service_name, duration_minutes, price_cents)
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                        """,
                        (appointment_id, sid, svc["name"], svc["duration_minutes"], svc.get("price_cents")),
                    )

        logger.info(
            f"[AppointmentService] Agendamento criado: id={result['id']} "
            f"clinic={clinic_id} date={date} time={time} services={len(all_service_ids)} "
            f"service_area_pairs={len(service_area_pairs) if service_area_pairs else 0}"
        )

        # 8. O lembrete de sessao e por DIA da agenda (PRD 027), enfileirado
        # pelo botao do painel ou pelo lote automatico - nao na criacao.

        # 8b. Reagendamento (PRD 035). Se esta pessoa teve um cancelamento ha
        # pouco nesta clinica, o antigo passa a apontar para este: e remarcacao,
        # nao cancelamento. Aqui, e nao no chamador, porque painel, site e bot
        # chegam todos por esta funcao. A conversao do Google Ads acompanha a
        # pessoa: muda de registro em vez de nascer outra (o uploader sobe o
        # evento de agendamento sem filtro de status e retrataria a compra do
        # antigo). `is True` de proposito: o retorno e bool, e um duble
        # qualquer nao pode passar por "movida".
        antecessor = vincula_antecessor(self.db, result)
        if antecessor == appointment_id:
            antecessor = None
        if substituida is not None:
            # O vinculo pela janela pode ter pego outro cancelamento recente;
            # o que vale e a sessao que esta criacao substituiu.
            antecessor = str(substituida["id"])
            self._leva_para_o_novo(antecessor, substituida, appointment_id)
        if existente and permitir_duas:
            self.db.execute_write(
                "UPDATE scheduler.appointments SET second_in_month_by = %s, second_in_month_reason = %s "
                "WHERE id = %s::uuid",
                ((autor or "painel")[:100], (motivo_das_duas or "").strip()[:200] or None, appointment_id),
            )
            logger.info(f"[MesmoMes] {clinic_id}: segunda sessao no mes autorizada por {autor!r}: {motivo_das_duas!r}")
        conversao_movida = False
        if antecessor and self.lead_service:
            try:
                conversao_movida = self.lead_service.move_conversion(
                    antecessor, appointment_id, f"{date} {time}-03:00") is True
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao mover conversao: {e}")
        result["rescheduled_from_id"] = antecessor

        # 9. Mark lead as booked (if lead exists for this phone+clinic)
        if self.lead_service:
            try:
                self.lead_service.mark_as_booked(
                    clinic_id=clinic_id,
                    phone=phone,
                    appointment_id=appointment_id,
                    appointment_value=final_price_cents / 100.0 if final_price_cents else None,
                    name=full_name,
                )
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao atualizar lead: {e}")

            # Record this appointment as a conversion tied to the lead's gclid
            # (recurring return: every appointment counts). No-op if no gclid lead.
            # conversion_date carries the appointment start time in clinic tz (BRT, -03:00)
            # so Google gets the real moment, not midnight.
            # Remarcacao com registro novo ja trouxe a conversao do antigo.
            if conversao_movida:
                return result
            try:
                self.lead_service.record_conversion(
                    clinic_id=clinic_id,
                    phone=phone,
                    name=full_name,
                    appointment_id=appointment_id,
                    value_cents=final_price_cents,
                    conversion_date=f"{date} {time}-03:00",
                )
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao registrar conversao do lead: {e}")

        return result

    def reschedule_appointment(
        self, appointment_id: str, new_date: str, new_time: str, tolerancia_minutos: int = 0) -> Dict[str, Any]:
        # 1. Fetch with optimistic lock
        appointments = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid AND status = 'CONFIRMED'",
            (appointment_id,),
        )

        if not appointments:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou não confirmado")

        appointment = appointments[0]
        current_version = appointment.get("version", 1)
        clinic_id = appointment["clinic_id"]

        # Mesma data, outro horario: edicao. Outra data e remarcacao (PRD 054):
        # o dia antigo guarda a sessao que nao aconteceu, com o desfecho da
        # antecedencia. Ate 20/11/2026 este metodo movia o registro inteiro e a
        # historia do dia antigo sumia.
        if str(new_date) != str(appointment["appointment_date"]):
            raise MudancaDeData("Mudar a data e remarcar: use remarca()")

        # 2. Get duration: prefer total_duration_minutes, then appointment_service_areas, then appointment_services, then service default
        duration_minutes = appointment.get("total_duration_minutes")
        if not duration_minutes:
            # Try appointment_service_areas first (services with areas)
            asa_junction = self.db.execute_query(
                "SELECT SUM(duration_minutes) as total FROM scheduler.appointment_service_areas WHERE appointment_id = %s::uuid",
                (appointment_id,),
            )
            if asa_junction and asa_junction[0].get("total"):
                duration_minutes = int(asa_junction[0]["total"])
            else:
                # Try appointment_services (services without areas)
                junction = self.db.execute_query(
                    "SELECT SUM(duration_minutes) as total FROM scheduler.appointment_services WHERE appointment_id = %s::uuid",
                    (appointment_id,),
                )
                if junction and junction[0].get("total"):
                    duration_minutes = int(junction[0]["total"])
                else:
                    services = self.db.execute_query(
                        "SELECT duration_minutes FROM scheduler.services WHERE id = %s::uuid",
                        (str(appointment["service_id"]),),
                    )
                    duration_minutes = services[0]["duration_minutes"] if services else 60

        # 3. Calculate new end_time
        #
        # A normalização existe para agendamento criado sob a regra antiga
        # (faixas por quantidade de áreas): ele é normalizado aqui em vez de
        # arrastar a duração velha para a agenda nova. Isso continua valendo.
        #
        # Mas duração que uma PESSOA fixou não é regra velha. Até 16/09/2026
        # esta linha rodava sobre ela também, e um override de 75min virava 50
        # no teto assim que alguém remarcasse - sem ninguém pedir e sem nada
        # avisar. Ver duracao_manual.
        manual = appointment.get("manual_duration_minutes")
        if manual:
            duration_minutes = duracao_efetiva(duration_minutes, manual)
        else:
            duration_minutes = duracao_da_sessao(
                duration_minutes, get_duration_rules(self.db, clinic_id))
        start_parts = new_time.split(":")
        start_hour, start_min = int(start_parts[0]), int(start_parts[1])
        total_minutes = start_hour * 60 + start_min + duration_minutes
        end_hour, end_min = total_minutes // 60, total_minutes % 60
        new_end_time = f"{end_hour:02d}:{end_min:02d}"

        # 4. Check conflicts in new slot
        conflicts = self._conflitos(clinic_id, new_date, new_time, new_end_time,
                                    excluir_id=appointment_id, tolerancia_minutos=tolerancia_minutos)

        if conflicts:
            raise ConflictError(self._mensagem_de_conflito(
                f"Conflito de horário no novo slot: {new_date} {new_time}-{new_end_time}",
                tolerancia_minutos, new_date, new_time, new_end_time))

        # 5. Update with optimistic lock
        updated_rows = self.db.execute_write(
            """
            UPDATE scheduler.appointments
            SET appointment_date = %s, start_time = %s::time, end_time = %s::time,
                total_duration_minutes = %s,
                -- Quem confirmou confirmou um HORARIO, nao um agendamento
                -- (PRD 043, decisao do Andre em 08/11/2026). Sem isto a agenda
                -- seguia exibindo "Confirmada" num horario que a paciente nunca
                -- viu - e como ninguem a avisa da remarcacao, a recepcao
                -- acreditava numa confirmacao que nao existia.
                confirmado_em = NULL, confirmado_por = NULL,
                version = version + 1, updated_at = NOW()
            WHERE id = %s::uuid AND version = %s
            """,
            # A duracao vai junto do end_time, SEMPRE - com e sem override.
            # Ate 16/09/2026 o reschedule mudava o end_time e deixava a coluna
            # com o valor velho: a agenda mostrava uma coisa e o banco guardava
            # outra, e isso ja acontecia sem override nenhum.
            (new_date, new_time, new_end_time, duration_minutes,
             appointment_id, current_version),
        )

        if updated_rows == 0:
            raise OptimisticLockError("Agendamento foi modificado por outro processo")

        # 6. Remarcou: o lembrete pendente do dia antigo cai. O do dia novo vem
        # pelo lote daquele dia (PRD 027), nao daqui.
        # A estreia passa para a proxima sessao confirmada, se houver.
        passa_a_marca_adiante(self.db, appointment_id)

        if self.reminder_service:
            try:
                self.reminder_service.cancel_reminder(appointment_id)
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao cancelar lembrete antigo: {e}")

        result = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid",
            (appointment_id,),
        )
        updated_appointment = result[0] if result else appointment

        # Keep any pending conversion aligned with the moved appointment
        if self.lead_service:
            try:
                self.lead_service.update_conversion_date(
                    appointment_id=appointment_id,
                    conversion_date=f"{new_date} {new_time}-03:00",
                )
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao atualizar conversao (reschedule): {e}")

        logger.info(
            f"[AppointmentService] Agendamento remarcado: id={appointment_id} "
            f"newDate={new_date} newTime={new_time}"
        )

        return updated_appointment

    def update_appointment_services(
        self,
        appointment_id: str,
        service_id: str,
        service_area_pairs: Optional[List[Dict[str, str]]] = None,
        manual_duration_minutes=SEM_MUDANCA,
        verificar_conflito: bool = True, tolerancia_minutos: int = 0) -> Dict[str, Any]:
        """Troca o servico e as areas, recalculando duracao e fim da sessao.

        `manual_duration_minutes` existe porque trocar a area e fixar a duracao
        costumam ser o MESMO pedido. Em 20/09/2026 o Andre trocou a area da
        Larissa de "Virilha Completa" para "Virilha Completa + anus" e fixou 10
        minutos; recebeu conflito de horario. A troca de area recalculava 15
        minutos, conferia o conflito com ESSE numero e recusava - antes de a
        duracao que ele digitou sequer ser lida.

        Trocar a area continua DESCARTANDO um override anterior, como o Andre
        decidiu em 17/09: aquele valor foi escolhido para outras areas. Mas um
        valor mandado no MESMO pedido nao e override anterior - e a decisao de
        agora, e ela vence.

        `verificar_conflito=False` para quando um reschedule vem logo em
        seguida: aqui a data ainda e a antiga, e conferir contra ela acusaria
        conflito num dia que a paciente nem vai ocupar.
        """
        # 1. Fetch appointment with optimistic lock
        appointments = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid AND status = 'CONFIRMED'",
            (appointment_id,),
        )
        if not appointments:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou não confirmado")

        appointment = appointments[0]
        current_version = appointment.get("version", 1)
        clinic_id = appointment["clinic_id"]
        appt_date = str(appointment["appointment_date"])
        start_time = str(appointment["start_time"])[:5]

        # 2. Validate service exists
        services = self.db.execute_query(
            "SELECT id, duration_minutes, name, price_cents FROM scheduler.services WHERE id::text = %s AND active = TRUE",
            (service_id,),
        )
        if not services:
            raise NotFoundError("Serviço não encontrado")

        svc = services[0]

        # Trocar as areas DESCARTA a duracao manual, por decisao do Andre em
        # 16/09/2026: o override foi decidido para OUTRO conjunto de areas.
        # Mudou a area, mudou a premissa - manter seria carregar 50 minutos
        # escolhidos para quatro areas numa sessao que agora tem uma.
        #
        # Quem chamou precisa SABER que descartou, senao o valor some da tela e
        # a atendente nao entende por que. Ver o handler de update.
        # So e descarte quando o pedido NAO trouxe duracao nova: se trouxe, o
        # valor nao foi perdido, foi substituido - e avisar "descartada" na tela
        # seria mentira.
        duracao_manual_descartada = (
            bool(appointment.get("manual_duration_minutes"))
            and manual_duration_minutes is SEM_MUDANCA
        )
        if duracao_manual_descartada:
            logger.info(
                f"[Duracao] {appointment_id}: duracao manual de "
                f"{appointment['manual_duration_minutes']}min descartada - as areas mudaram"
            )

        # 3. Calculate new duration and price
        discount_pct = appointment.get("discount_pct") or 0
        # PRD 050: desconto em reais e a fonte; o percentual e copia e e
        # reescrito abaixo. Subtotal novo menor que o desconto fixado recusa a
        # troca (DescontoInvalido -> 400): zerar em silencio seria parceria.
        discount_cents = appointment.get("discount_cents")
        if service_area_pairs:
            values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
            params: tuple = ()
            for pair in service_area_pairs:
                params += (pair["serviceId"], pair["areaId"])
            # O preço continua sendo a soma por área; só a duração passou a vir
            # da quantidade de áreas. Ver duration_rules.py.
            rows = self.db.execute_query(
                f"""SELECT SUM(COALESCE(sa.price_cents, s.price_cents)) as total_price
                FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                JOIN scheduler.services s ON s.id = pairs.service_id AND s.active = TRUE
                LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
                params,
            )
            duration_minutes = calcula_duracao(
                self.db, appointment["clinic_id"], service_area_pairs)
            original_price_cents = int(rows[0]["total_price"]) if rows and rows[0]["total_price"] else svc.get("price_cents")
        else:
            duration_minutes = duracao_da_sessao(
                svc.get("duration_minutes"), get_duration_rules(self.db, appointment["clinic_id"]))
            original_price_cents = svc.get("price_cents")

        # A duracao mandada no mesmo pedido vence a recalculada. Sem isto, o
        # conflito abaixo seria conferido contra um numero que o pedido ja
        # substituiu.
        manual_do_pedido = None
        if manual_duration_minutes is not SEM_MUDANCA:
            manual_do_pedido = valida_duracao_manual(manual_duration_minutes)
            duration_minutes = duracao_efetiva(duration_minutes, manual_do_pedido)

        if original_price_cents:
            final_price_cents = aplica_desconto(original_price_cents, discount_pct, cents=discount_cents)
            if discount_cents is not None:
                discount_pct = pct_equivalente(original_price_cents, discount_cents)
        else:
            final_price_cents = original_price_cents

        # 4. Calculate new end_time
        start_parts = start_time.split(":")
        start_hour, start_min = int(start_parts[0]), int(start_parts[1])
        total_minutes = start_hour * 60 + start_min + duration_minutes
        end_hour, end_min = total_minutes // 60, total_minutes % 60
        new_end_time = f"{end_hour:02d}:{end_min:02d}"

        # 5. Check conflicts with new duration
        conflicts = self._conflitos(clinic_id, appt_date, start_time, new_end_time,
                                    excluir_id=appointment_id, tolerancia_minutos=tolerancia_minutos)
        if conflicts and verificar_conflito:
            raise ConflictError(self._mensagem_de_conflito(
                f"Conflito de horário com nova duração: {appt_date} {start_time}-{new_end_time}",
                tolerancia_minutos, appt_date, start_time, new_end_time))

        # 6. Update appointment record
        updated_rows = self.db.execute_write(
            """
            UPDATE scheduler.appointments
            SET service_id = %s::uuid, end_time = %s::time, total_duration_minutes = %s,
                manual_duration_minutes = %s,
                original_price_cents = %s, final_price_cents = %s, discount_pct = %s,
                version = version + 1, updated_at = NOW()
            WHERE id = %s::uuid AND version = %s
            """,
            (service_id, new_end_time, duration_minutes, manual_do_pedido,
             original_price_cents, final_price_cents, discount_pct,
             appointment_id, current_version),
        )
        if updated_rows == 0:
            raise OptimisticLockError("Agendamento foi modificado por outro processo")

        # 7. Replace junction table records
        self.db.execute_write(
            "DELETE FROM scheduler.appointment_service_areas WHERE appointment_id = %s::uuid",
            (appointment_id,),
        )
        self.db.execute_write(
            "DELETE FROM scheduler.appointment_services WHERE appointment_id = %s::uuid",
            (appointment_id,),
        )

        if service_area_pairs:
            values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
            params = ()
            for pair in service_area_pairs:
                params += (pair["serviceId"], pair["areaId"])
            pair_rows = self.db.execute_query(
                f"""SELECT pairs.service_id, pairs.area_id,
                       s.name as service_name, a.name as area_name,
                       COALESCE(sa.duration_minutes, s.duration_minutes) as duration_minutes,
                       COALESCE(sa.price_cents, s.price_cents) as price_cents
                FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                JOIN scheduler.services s ON s.id = pairs.service_id
                JOIN scheduler.areas a ON a.id = pairs.area_id
                LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
                params,
            )
            for row in pair_rows:
                self.db.execute_write(
                    """
                    INSERT INTO scheduler.appointment_service_areas
                        (appointment_id, service_id, area_id, area_name, service_name, duration_minutes, price_cents)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s)
                    """,
                    (appointment_id, str(row["service_id"]), str(row["area_id"]),
                     row["area_name"], row["service_name"],
                     row["duration_minutes"], row.get("price_cents")),
                )
        else:
            self.db.execute_write(
                """
                INSERT INTO scheduler.appointment_services
                    (appointment_id, service_id, service_name, duration_minutes, price_cents)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                """,
                (appointment_id, service_id, svc["name"], svc["duration_minutes"], svc.get("price_cents")),
            )

        # 8. Re-fetch and sync
        result = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid",
            (appointment_id,),
        )
        updated_appointment = result[0] if result else appointment

        logger.info(
            f"[AppointmentService] Serviço/áreas atualizados: id={appointment_id} "
            f"service={service_id} areas={len(service_area_pairs) if service_area_pairs else 0}"
        )

        # A bandeira viaja junto do agendamento porque quem responde a atendente
        # e o handler, e ele nao tem como saber o que havia antes do UPDATE.
        updated_appointment = dict(updated_appointment)
        updated_appointment["manual_duration_descartada"] = duracao_manual_descartada

        return updated_appointment

    def aplica_politica(self, appointment_id: str) -> Dict[str, Any]:
        """Re-decide o desconto pela politica da clinica sobre o preco de
        tabela ATUAL (PRD 053, decisao 5).

        Chamado pela edicao, depois da troca de areas: a faixa por quantidade
        de areas depende das areas, e congelar o percentual gravado deixaria
        15% de "2-4 areas" numa sessao de seis. Zera `discount_cents`: a
        politica e percentual.

        A razao gravada e a de `decide`, inclusive None quando a politica nao
        da nada - "none" fica reservado a escolha explicita do painel.
        """
        linhas = self.db.execute_query(
            """
            SELECT a.clinic_id, a.original_price_cents, a.version, p.phone,
                   (SELECT COUNT(*) FROM scheduler.appointment_service_areas x
                     WHERE x.appointment_id = a.id) AS qtd_areas
            FROM scheduler.appointments a
            LEFT JOIN scheduler.patients p ON p.id = a.patient_id
            WHERE a.id = %s::uuid AND a.status = 'CONFIRMED'
            """,
            (appointment_id,),
        )
        if not linhas:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou não confirmado")
        atual = linhas[0]
        original = atual.get("original_price_cents")
        decisao = decide(self.db, atual["clinic_id"], atual.get("phone"), int(atual.get("qtd_areas") or 0))
        final = aplica_desconto(original, decisao.pct) if original is not None else None

        logger.info(
            f"[Desconto] {appointment_id}: politica re-decidida -> "
            f"{decisao.razao} {decisao.pct}% (original={original}, final={final})"
        )
        resultado = self.db.execute_write_returning(
            """
            UPDATE scheduler.appointments
            SET discount_pct = %s, discount_cents = NULL, discount_reason = %s,
                final_price_cents = %s, version = version + 1, updated_at = NOW()
            WHERE id = %s::uuid AND version = %s
            RETURNING *
            """,
            (decisao.pct, decisao.razao, final, appointment_id, atual.get("version", 1)),
        )
        if not resultado:
            raise ConflictError("Agendamento foi modificado por outro processo")
        return resultado

    def set_manual_duration(
        self,
        appointment_id: str,
        minutos: Optional[int],
        verificar_conflito: bool = True, tolerancia_minutos: int = 0) -> Dict[str, Any]:
        """Fixa (ou solta) a duração de UM agendamento.

        `minutos=None` solta: a duração volta a ser CALCULADA a partir das áreas
        gravadas, não ao último valor que estava na coluna. Voltar ao cálculo tem
        de voltar ao cálculo, senão "soltar" só congela o override com outro nome.

        `verificar_conflito=False` existe para o caso de o mesmo request também
        remarcar. A checagem aqui roda contra a data ATUAL, que o reschedule vai
        trocar em seguida - conferir duas vezes acusaria conflito numa data que a
        paciente nem vai ocupar. Quem confere, nesse caso, é o reschedule, já com
        a data final. Ver o handler de update.
        """
        manual = valida_duracao_manual(minutos)

        appointments = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid AND status = 'CONFIRMED'",
            (appointment_id,),
        )
        if not appointments:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou não confirmado")

        appointment = appointments[0]
        current_version = appointment.get("version", 1)
        clinic_id = appointment["clinic_id"]
        appt_date = str(appointment["appointment_date"])
        start_time = str(appointment["start_time"])[:5]

        if manual:
            duration_minutes = manual
        else:
            # Recalcula das áreas gravadas, passando pela regra da clínica -
            # exatamente o que a criação faria hoje para este agendamento.
            areas = self.db.execute_query(
                """SELECT service_id, area_id FROM scheduler.appointment_service_areas
                   WHERE appointment_id = %s::uuid""",
                (appointment_id,),
            ) or []
            pares = [{"service_id": str(a["service_id"]), "area_id": str(a["area_id"])}
                     for a in areas]
            if pares:
                duration_minutes = calcula_duracao(self.db, clinic_id, pares)
            else:
                # Serviço sem área detalhada: a duração do próprio serviço,
                # pelos mesmos piso, teto e passo.
                svc = self.db.execute_query(
                    "SELECT duration_minutes FROM scheduler.services WHERE id = %s::uuid",
                    (str(appointment["service_id"]),),
                )
                duration_minutes = duracao_da_sessao(
                    svc[0]["duration_minutes"] if svc else 0,
                    get_duration_rules(self.db, clinic_id),
                )

        start_hour, start_min = (int(p) for p in start_time.split(":")[:2])
        total_minutes = start_hour * 60 + start_min + duration_minutes
        new_end_time = f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"

        if verificar_conflito:
            conflicts = self._conflitos(clinic_id, appt_date, start_time, new_end_time,
                                        excluir_id=appointment_id, tolerancia_minutos=tolerancia_minutos)
            if conflicts:
                raise ConflictError(self._mensagem_de_conflito(
                    f"Conflito de horário com a duração de {duration_minutes} minutos: "
                    f"{appt_date} {start_time}-{new_end_time}",
                    tolerancia_minutos, appt_date, start_time, new_end_time))

        updated_rows = self.db.execute_write(
            """
            UPDATE scheduler.appointments
            SET manual_duration_minutes = %s, total_duration_minutes = %s,
                end_time = %s::time,
                version = version + 1, updated_at = NOW()
            WHERE id = %s::uuid AND version = %s
            """,
            (manual, duration_minutes, new_end_time, appointment_id, current_version),
        )
        if updated_rows == 0:
            raise OptimisticLockError("Agendamento foi modificado por outro processo")

        logger.info(
            f"[Duracao] {appointment_id}: "
            + (f"duracao manual de {manual}min" if manual
               else f"override solto, voltou ao calculado ({duration_minutes}min)")
            + f" | {start_time}-{new_end_time}"
        )

        result = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid",
            (appointment_id,),
        )
        return result[0] if result else appointment

    def cancel_appointment(self, appointment_id: str, desfecho: Optional[str] = None,
                           motivo: Optional[str] = None, autor: Optional[str] = None) -> Dict[str, Any]:
        """Encerra o agendamento com o desfecho da antecedencia (PRD 054):
        CANCELLED com 24 h ou mais antes da abertura da agenda do dia, NO_SHOW
        com menos. `desfecho` explicito e a sobreposicao do painel (decisao 2)
        e exige `motivo` quando diverge do automatico; bot e site nao mandam.
        A linha devolvida traz `outcome`."""
        atuais = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid AND status = 'CONFIRMED'",
            (appointment_id,),
        )
        if not atuais:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou já cancelado")
        atual = atuais[0]

        automatico = desfecho_do_agendamento(self.db, atual)
        if desfecho is not None and desfecho not in DESFECHOS:
            raise DesfechoInvalido(f"Desfecho desconhecido: {desfecho!r}")
        sobreposto = desfecho is not None and desfecho != automatico
        if sobreposto and not (motivo or "").strip():
            raise DesfechoInvalido("Para registrar um desfecho diferente do automatico, informe o motivo")
        final = desfecho or automatico

        result = self.db.execute_write_returning(
            """
            UPDATE scheduler.appointments
            SET status = %s, outcome_overridden_by = %s, outcome_reason = %s,
                updated_at = NOW(), version = version + 1
            WHERE id = %s::uuid AND status = 'CONFIRMED'
            RETURNING *
            """,
            (final, (autor or "painel")[:100] if sobreposto else None,
             (motivo or "").strip()[:200] or None if sobreposto else None,
             appointment_id),
        )
        if not result:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou já cancelado")
        result["outcome"] = final
        if sobreposto:
            logger.info(f"[Desfecho] {appointment_id}: {automatico} -> {final} por {autor!r}: {motivo!r}")

        # A estreia passa para a proxima sessao confirmada, se houver.
        passa_a_marca_adiante(self.db, appointment_id)

        if self.reminder_service:
            try:
                self.reminder_service.cancel_reminder(appointment_id)
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao cancelar lembrete: {e}")

        logger.info(f"[AppointmentService] Agendamento encerrado: id={appointment_id} desfecho={final}")
        return result

    def remarca(self, appointment_id: str, nova_data: str, nova_hora: str,
                tolerancia_minutos: int = 0, desfecho: Optional[str] = None,
                motivo: Optional[str] = None, autor: Optional[str] = None,
                substituir_mesmo_mes: bool = False, permitir_duas: bool = False,
                motivo_das_duas: Optional[str] = None) -> Dict[str, Any]:
        """Outra data (PRD 054): o antigo recebe o desfecho da antecedencia (ou
        a sobreposicao do painel) e aponta para o novo; o novo nasce igual ao
        antigo - areas, desconto gravado, duracao fixada, observacao, estreia -
        e leva pagamento vivo, link dos documentos e conversao. Mesma data
        delega a `reschedule_appointment`. Devolve {"antigo", "novo"}.

        Confere o conflito do horario novo ANTES de encerrar o antigo: um
        conflito nao pode deixar a paciente sem sessao nenhuma.

        Uma sessao por mes (PRD 056): se no mes de `nova_data` ja ha OUTRA
        sessao confirmada desta paciente, levanta `SessaoNoMesmoMes`;
        `substituir_mesmo_mes` cancela essa outra (desfecho da antecedencia)
        antes de criar o novo; `permitir_duas` so pelo painel, ADMIN, motivo.
        """
        atuais = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid AND status = 'CONFIRMED'",
            (appointment_id,),
        )
        if not atuais:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou não confirmado")
        antigo = atuais[0]
        if str(nova_data) == str(antigo["appointment_date"]):
            return {"antigo": None,
                    "novo": self.reschedule_appointment(appointment_id, nova_data, nova_hora,
                                                        tolerancia_minutos=tolerancia_minutos)}

        clinic_id = antigo["clinic_id"]
        pares = [
            {"service_id": str(p["service_id"]), "area_id": str(p["area_id"])}
            for p in self.db.execute_query(
                "SELECT service_id, area_id FROM scheduler.appointment_service_areas "
                "WHERE appointment_id = %s::uuid ORDER BY created_at",
                (appointment_id,),
            )
        ]
        pacientes = self.db.execute_query(
            "SELECT phone FROM scheduler.patients WHERE id = %s::uuid", (str(antigo["patient_id"]),))
        if not pacientes:
            raise NotFoundError(f"Paciente do agendamento {appointment_id} não encontrado")
        phone = pacientes[0]["phone"]

        # 0. Outra sessao dela no mes de destino (PRD 056). Antes de qualquer
        # escrita; a terceira so e cancelada depois de o horario caber.
        terceira = None if permitir_duas else self.sessao_no_mesmo_mes(
            clinic_id, phone, nova_data, excluir_id=appointment_id)
        if terceira and not substituir_mesmo_mes:
            raise SessaoNoMesmoMes(terceira)

        # 1. O horario novo cabe? Com a duracao que o antigo ocupa.
        duracao = int(antigo.get("total_duration_minutes") or 0) or duracao_do_carrinho(
            self.db, clinic_id, [str(antigo["service_id"])], pares)
        h, m = (int(x) for x in str(nova_hora).split(":")[:2])
        fim = f"{(h * 60 + m + duracao) // 60:02d}:{(h * 60 + m + duracao) % 60:02d}"
        conflitos = self._conflitos(clinic_id, nova_data, nova_hora, fim,
                                    excluir_id=appointment_id, tolerancia_minutos=tolerancia_minutos)
        if conflitos:
            raise ConflictError(self._mensagem_de_conflito(
                f"Conflito de horário no novo slot: {nova_data} {nova_hora}-{fim}",
                tolerancia_minutos, nova_data, nova_hora, fim))

        # 1b. A terceira sai primeiro, com o desfecho da antecedencia (PRD 056).
        if terceira:
            saiu = self.cancel_appointment(str(terceira["id"]), autor=autor)
            logger.info(f"[MesmoMes] remarcacao de {appointment_id} para {nova_data}: "
                        f"sessao {terceira['id']} do mesmo mes cancelada (desfecho={saiu['outcome']})")

        # 2. Encerra o antigo com o desfecho. Cancela o lembrete e passa a estreia.
        encerrado = self.cancel_appointment(appointment_id, desfecho=desfecho, motivo=motivo, autor=autor)

        # 3. O novo, igual ao antigo. `vincula_antecessor` dentro do create acha
        #    o antigo (recem-encerrado, dentro da janela), grava rescheduled_to_id
        #    e move a conversao em vez de registrar outra.
        novo = self.create_appointment(
            clinic_id=clinic_id, phone=phone, service_id=str(antigo["service_id"]),
            date=str(nova_data), time=str(nova_hora)[:5],
            professional_id=str(antigo["professional_id"]) if antigo.get("professional_id") else None,
            service_area_pairs=pares or None,
            full_name=antigo.get("full_name"), notes=antigo.get("notes"),
            discount_pct=antigo.get("discount_pct") or 0,
            discount_reason=antigo.get("discount_reason"),
            discount_cents=antigo.get("discount_cents"),
            manual_duration_minutes=antigo.get("manual_duration_minutes"),
            is_first_visit=bool(antigo.get("is_first_visit")),
            # O mes ja foi conferido acima (e o antigo acabou de ser encerrado).
            permitir_duas=True, autor=autor,
            motivo_das_duas=motivo_das_duas if permitir_duas else None,
        )
        novo_id = str(novo["id"])

        # 4. Vinculo nos dois sentidos, mesmo que a janela do vincula_antecessor
        #    nao tenha pego (relogio, concorrencia); pagamento vivo e link dos
        #    documentos acompanham.
        self._leva_para_o_novo(appointment_id, antigo, novo_id)

        logger.info(
            f"[Remarcacao] {appointment_id} -> {novo_id}: {antigo['appointment_date']} "
            f"{str(antigo['start_time'])[:5]} => {nova_data} {nova_hora} (desfecho={encerrado['outcome']})"
        )
        novo["rescheduled_from_id"] = appointment_id
        encerrado["rescheduled_to_id"] = novo_id
        return {"antigo": encerrado, "novo": novo}

    def marca_no_show(self, appointment_id: str) -> Dict[str, Any]:
        """A pessoa nao compareceu. Marca a falta, sem liberar o horario.

        Falta e diferente de cancelamento: quem cancela com antecedencia libera
        a agenda, quem nao aparece queima o horario. Ate 04/10/2026 os dois
        viravam CANCELLED, e a diferenca se perdia.

        Existe para a conversao offline ser honesta: ela e uma COMPRA, e compra
        exige comparecimento. Sem este status, `CONFIRMED` com data passada
        significava so "ninguem cancelou", e um no-show subia ao Google como
        venda. Ver infra/src/functions/conversions/uploader.py.

        ## Nao ha guard de data, por decisao do Andre em 04/10/2026

        A primeira versao exigia `appointment_date < hoje`, pensando na
        correcao da conversao. Estava errado: avisar no DIA e falta, nao
        cancelamento - o horario ja nao da para preencher. Com o guard, a
        recepcionista que precisasse liberar o horario de hoje as 10h30 teria
        de CANCELAR, perdendo exatamente a informacao que este status existe
        para capturar.

        Quem decide se foi falta ou cancelamento e quem esta no balcao, com
        contexto que o codigo nao tem: a razao da cliente, a chance de
        reocupar. Encodar uma politica ("menos de 24h e falta") seria inventar
        regra que ninguem pediu.

        ## Revisto em 20/11/2026 (PRD 054)

        A regra foi pedida: CANCELAR com menos de 24 h antes da abertura da
        agenda do dia vira NO_SHOW, em `cancel_appointment` (ver desfecho.py).
        Este metodo segue sendo o "nao veio" descoberto depois, marcado a mao
        pela recepcao, e por isso continua sem guard de data.

        O que a distingue de CANCELLED, entao, nao e o momento: e a contagem.
        As duas liberam o horario (as queries de conflito e de horarios livres
        usam `= 'CONFIRMED'`), mas NO_SHOW registra que o horario foi perdido.

        ## O filtro de status esta no WHERE, de proposito

        Consultar primeiro e escrever depois deixa janela entre as duas: a
        recepcao marca falta no mesmo instante em que a paciente cancela pelo
        bot, e o segundo UPDATE sobrescreve o primeiro sem ninguem notar. No
        WHERE, o banco decide, e quem perdeu recebe NotFoundError.

        ## O que esta funcao NAO faz, e por que

        Nao chama `passa_a_marca_adiante`, ao contrario de `cancel_appointment`.
        Aquela funcao move `is_first_visit` para a proxima sessao confirmada e
        **nao tem inverso**. Como marcar falta e reversivel (ver
        `desmarca_no_show`), espelha-la tornaria o desmarcar lossy - a marca de
        estreia nao voltaria.

        O preco disso esta registrado: quem falta na estreia mantem a marca na
        linha da falta, e a sessao em que de fato pisa na clinica aparece como
        veterana. E o mesmo defeito que a decisao de 09/09/2026 resolveu para
        cancelamento, e fica como pendencia propria - inventar um inverso aqui
        trocaria um defeito de exibicao estreito por risco de corromper a marca.

        Nao toca lembrete: so se marca falta de sessao que ja passou, e o
        lembrete dela ja disparou.
        """
        result = self.db.execute_write_returning(
            """
            UPDATE scheduler.appointments
            SET status = 'NO_SHOW', updated_at = NOW(), version = version + 1
            WHERE id = %s::uuid AND status = 'CONFIRMED'
            RETURNING *
            """,
            (appointment_id,),
        )

        if not result:
            raise NotFoundError(
                f"Agendamento {appointment_id} nao pode receber falta: ou nao "
                f"existe, ou nao esta CONFIRMED"
            )

        logger.info(f"[AppointmentService] Falta marcada: id={appointment_id}")
        return result

    def desmarca_no_show(self, appointment_id: str) -> Dict[str, Any]:
        """Desfaz a falta. Marcar errado tem de ter volta.

        E o que permite `marca_no_show` ser acao direta no painel, sem modal de
        confirmacao: cerimonia se paga quando a acao e irreversivel, e esta nao
        e.

        `status = 'NO_SHOW'` no WHERE impede ressuscitar cancelado: sem ele,
        desmarcar falta viraria um jeito obliquo de descancelar - e cancelamento
        ja liberou o horario, que pode ter sido ocupado por outra pessoa.
        """
        result = self.db.execute_write_returning(
            """
            UPDATE scheduler.appointments
            SET status = 'CONFIRMED', updated_at = NOW(), version = version + 1
            WHERE id = %s::uuid AND status = 'NO_SHOW'
            RETURNING *
            """,
            (appointment_id,),
        )

        if not result:
            raise NotFoundError(
                f"Agendamento {appointment_id} nao esta marcado como falta"
            )

        logger.info(f"[AppointmentService] Falta desmarcada: id={appointment_id}")
        return result

    def get_active_appointment_by_phone(
        self, clinic_id: str, phone: str
    ) -> Optional[Dict[str, Any]]:
        from src.utils.phone import formas_do_numero
        patients = self.db.execute_query(
            "SELECT id FROM scheduler.patients WHERE clinic_id = %s AND phone = ANY(%s) AND deleted_at IS NULL",
            (clinic_id, formas_do_numero(phone)),
        )

        if not patients:
            return None

        patient_id = str(patients[0]["id"])

        appointments = self.db.execute_query(
            f"""
            SELECT a.*, s.name as service_name,
                   areas_q.areas_display
            FROM scheduler.appointments a
            LEFT JOIN scheduler.services s ON a.service_id = s.id
            LEFT JOIN LATERAL (
                SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at) as areas_display
                FROM scheduler.appointment_service_areas asa
                WHERE asa.appointment_id = a.id
            ) areas_q ON TRUE
            WHERE a.patient_id = %s::uuid AND a.status = 'CONFIRMED'
            AND a.appointment_date >= {HOJE_SQL}
            ORDER BY a.appointment_date ASC, a.start_time ASC
            LIMIT 1
            """,
            (patient_id,),
        )

        return appointments[0] if appointments else None

    def get_active_appointments_by_phone(
        self, clinic_id: str, phone: str
    ) -> List[Dict[str, Any]]:
        """Os agendamentos futuros confirmados de um número, de todos os
        pacientes que ele tenha nesta clínica.

        O telefone chega como a pessoa digitou ou como o WhatsApp entregou, e
        a comparação é feita pelas variantes normalizadas. Até 18/10/2026 a
        comparação era exata com o que chegava: o site mandava
        `(11) 99999-0000`, o paciente estava gravado `5511999990000`, e
        "Meus agendamentos" respondia vazio para quem tinha acabado de
        agendar. As variantes cobrem também o número sem o nono dígito que o
        bot grava fora dos DDDs 11-28 (`phone.variantes_do_numero`).
        """
        from src.utils.phone import variantes_do_numero
        variantes = sorted(variantes_do_numero(phone or ""))
        if not variantes:
            return []

        return self.db.execute_query(
            f"""
            SELECT a.*, s.name as service_name,
                   areas_q.areas_display,
                   -- O carrinho do agendamento, para o site remarcar com a
                   -- mesma duracao e as mesmas areas (PRD 035).
                   COALESCE(svc.ids, ARRAY[a.service_id::text]) AS service_ids,
                   COALESCE(pares.lista, '[]'::json)            AS service_area_pairs
            FROM scheduler.appointments a
            JOIN scheduler.patients p ON p.id = a.patient_id
            LEFT JOIN scheduler.services s ON a.service_id = s.id
            LEFT JOIN LATERAL (
                SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at) as areas_display
                FROM scheduler.appointment_service_areas asa
                WHERE asa.appointment_id = a.id
            ) areas_q ON TRUE
            LEFT JOIN LATERAL (
                SELECT array_agg(aps.service_id::text ORDER BY aps.created_at) AS ids
                FROM scheduler.appointment_services aps
                WHERE aps.appointment_id = a.id
            ) svc ON TRUE
            LEFT JOIN LATERAL (
                SELECT json_agg(json_build_object('serviceId', asa.service_id,
                                                  'areaId', asa.area_id)
                                ORDER BY asa.created_at) AS lista
                FROM scheduler.appointment_service_areas asa
                WHERE asa.appointment_id = a.id
            ) pares ON TRUE
            WHERE p.clinic_id = %s AND p.phone = ANY(%s) AND p.deleted_at IS NULL
            AND a.clinic_id = %s AND a.status = 'CONFIRMED'
            AND a.appointment_date >= {HOJE_SQL}
            ORDER BY a.appointment_date ASC, a.start_time ASC
            """,
            (clinic_id, variantes, clinic_id),
        )

    def _get_or_create_patient(self, clinic_id: str, phone: str,
                               full_name: Optional[str] = None, cpf: Optional[str] = None,
                               birth_date: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        """O paciente do agendamento, criado se ainda não existir.

        Nome, CPF, nascimento e e-mail entram juntos (os três últimos vêm do
        site, PRD 032; bot e painel passam None). Antes o INSERT levava só
        clínica e telefone, e todo paciente novo nascia anônimo: a agenda
        mostrava a linha sem nome, e o painel de pacientes também.

        O que já está cadastrado NÃO é sobrescrito: só o que está vazio é
        preenchido (COALESCE). Quem está no sistema pode ter sido corrigido à
        mão, e o que vem no agendamento é o que a pessoa digitou naquele dia -
        não é mais confiável que a clínica.
        """
        from src.utils.phone import formas_do_numero, normalize_phone
        phone = normalize_phone(phone)
        nome = (full_name or "").strip() or None

        # Lookup includes soft-deleted records so we can restore in place
        # and avoid violating the UNIQUE(clinic_id, phone) constraint.
        # Casa pelas variantes (com e sem o nono dígito), a mesma régua da
        # cotação do site e da identificação do bot: casando exato, a Paula
        # (gravada `553591328559`) ganhou um segundo cadastro quando digitou
        # o número com o 9 no site, em 21/10/2026. Havendo mais de um, o
        # exato vence; entre iguais, o ativo vence o apagado.
        patients = self.db.execute_query(
            "SELECT * FROM scheduler.patients WHERE clinic_id = %s AND phone = ANY(%s) "
            "ORDER BY (phone = %s) DESC, (deleted_at IS NULL) DESC, created_at",
            (clinic_id, formas_do_numero(phone), phone),
        )

        if patients:
            existing = patients[0]
            if existing.get("deleted_at") is None:
                # Preenche só o que está vazio, e só se veio algo para preencher.
                # Cadastro sem nome é o rastro do defeito antigo; CPF, nascimento
                # e e-mail vazios são o paciente que nasceu pelo site antes do
                # PRD 032. Nada existente é tocado.
                if _completa_algo(existing, nome, cpf, birth_date, email):
                    atualizado = self.db.execute_write_returning(
                        """
                        UPDATE scheduler.patients
                           SET name = COALESCE(NULLIF(name, ''), %s),
                               cpf = COALESCE(NULLIF(cpf, ''), %s),
                               birth_date = COALESCE(birth_date, %s::date),
                               email = COALESCE(NULLIF(email, ''), %s),
                               updated_at = NOW()
                         WHERE id = %s::uuid
                        RETURNING *
                        """,
                        (nome, cpf, birth_date, email, str(existing["id"])),
                    )
                    return atualizado or existing
                return existing

            # Soft-deleted patient came back — restore in place, completing
            # what is empty with what came along.
            restored = self.db.execute_write_returning(
                """
                UPDATE scheduler.patients
                   SET deleted_at = NULL,
                       name = COALESCE(NULLIF(name, ''), %s),
                       cpf = COALESCE(NULLIF(cpf, ''), %s),
                       birth_date = COALESCE(birth_date, %s::date),
                       email = COALESCE(NULLIF(email, ''), %s),
                       updated_at = NOW()
                 WHERE id = %s::uuid
                RETURNING *
                """,
                (nome, cpf, birth_date, email, str(existing["id"])),
            )
            logger.info(
                f"[AppointmentService] Patient restored from soft-delete: id={existing['id']} phone={phone}"
            )
            return restored

        result = self.db.execute_write_returning(
            """
            INSERT INTO scheduler.patients (clinic_id, phone, name, cpf, birth_date, email, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s::date, %s, NOW(), NOW())
            RETURNING *
            """,
            (clinic_id, phone, nome, cpf, birth_date, email),
        )

        return result


def _completa_algo(existente: Dict[str, Any], nome, cpf, birth_date, email) -> bool:
    """Veio algum dado para um campo que está vazio no cadastro?"""
    def vazio(campo):
        v = existente.get(campo)
        return v is None or (isinstance(v, str) and not v.strip())
    return any(novo and vazio(campo) for campo, novo in (
        ("name", nome), ("cpf", cpf), ("birth_date", birth_date), ("email", email)))
