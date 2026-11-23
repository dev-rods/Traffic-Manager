import logging
import os
import re
from datetime import datetime, date, time

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.phone import is_valid_phone, normalize_phone
from src.services.db.postgres import PostgresService
from src.services.appointment_service import (
    AppointmentService, ConflictError, NotFoundError, OutraSessaoFutura, SessaoNoMesmoMes)
from src.utils.booking_verification import verify_token
from src.services.template_service import TemplateService
from src.services.orientacoes_pos_sessao import texto as orientacoes_da_clinica
from src.services.politica_de_desconto import texto_do_preco
from src.services import carrinho, janela_do_site, relogio
from src.utils.cadastro import cpf_valido, normaliza_cpf, normaliza_data_nascimento, normaliza_email
from src.services.availability_engine import AvailabilityEngine
from src.services.envio_do_sistema import SITE_AGENDAMENTO, envia_texto

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _format_date_br(iso_date: str) -> str:
    try:
        y, m, d = iso_date.split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return iso_date


_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

# Cadastro do paciente pelo site (PRD 032). O site distingue pelo `code`; o
# 409 sem code continua sendo horário ocupado.
CADASTRO_INCOMPLETO = "CADASTRO_INCOMPLETO"
CPF_EM_USO = "CPF_EM_USO"
MENSAGEM_CADASTRO = "Para a primeira sessão precisamos de CPF, data de nascimento e e-mail."


def _cadastro_invalido(campo, mensagem):
    return http_response(400, {"status": "ERROR", "code": CADASTRO_INCOMPLETO,
                               "faltam": [campo], "message": mensagem})


# Uma sessao por mes (PRD 056). O site mostra a existente e pede confirmacao;
# o pedido volta com `substituir: true`.
SAME_MONTH_APPOINTMENT = "SAME_MONTH_APPOINTMENT"
# Sessao futura em OUTRO mes (PRD 060): o site pergunta "remarcar essa sessao
# ou marcar mais uma?" e repete com `remarcarExistente` ou `maisUma`. A
# mensagem serve ao front antigo em cache, que nao conhece o code.
OTHER_MONTH_APPOINTMENT = "OTHER_MONTH_APPOINTMENT"
MENSAGEM_TOKEN = "Verificação por WhatsApp expirada. Confirme o código novamente."


def _mensagem_outro_mes(existente):
    data = str(existente.get("appointment_date") or "")
    dia = f"{data[8:10]}/{data[5:7]}" if len(data) >= 10 else data
    return (f"Você já tem uma sessão em {dia}. Para remarcar, abra Meus agendamentos; "
            "para marcar mais uma, recarregue a página e confirme.")


def _existente(e):
    """A sessao que o aviso mostra. Pode revelar data e hora: o numero foi
    verificado pelo codigo antes de chegar aqui."""
    return {
        "id": str(e["id"]),
        "date": str(e["appointment_date"]),
        "time": str(e["start_time"])[:5],
        "areas": e.get("areas_display"),
    }


def _final_do_telefone(phone):
    return f"***{str(phone)[-4:]}" if phone else "-"


def _send_confirmation_whatsapp(db: PostgresService, clinic: dict, phone: str, appointment: dict, qtd_areas: int) -> None:
    """
    A mesma confirmação que o agente de WhatsApp manda ao fechar um
    agendamento: o template "BOOKED" (customizável por clínica), com o valor
    já com desconto, e em seguida as orientações pré-sessão da clínica, numa
    mensagem própria - como o agente faz (`TOOLS_QUE_MARCAM_SESSAO` em
    conversation_agent): a orientação vai crua, do jeito que a clínica escreveu.

    O valor sai do que foi GRAVADO, não da cotação. Cada envio tem seu próprio
    try: falha num não impede o outro, e nenhuma derruba a criação - o
    agendamento já está persistido.
    """
    # Rastreado com origem SITE_AGENDAMENTO: sem o rastro, o eco do z-api
    # virava "atendente" no webhook e pausava o bot por 24h (PRD 034).
    template_service = TemplateService(db)

    try:
        duration_minutes = appointment.get("total_duration_minutes")
        hours, mins = divmod(int(duration_minutes or 0), 60)
        duration_str = f"{hours}h{mins:02d}min" if hours else f"{duration_minutes}min"

        variables = {
            # O nome digitado NESTE agendamento, não o do cadastro: o mesmo
            # telefone pode agendar para mais de uma pessoa.
            "full_name": appointment.get("full_name") or "",
            "date": _format_date_br(str(appointment.get("appointment_date", ""))[:10]),
            "time": str(appointment.get("start_time", ""))[:5],
            "duration": duration_str,
            "price": texto_do_preco(
                appointment.get("original_price_cents"),
                appointment.get("final_price_cents"),
                appointment.get("discount_pct"),
                appointment.get("discount_reason"),
                qtd_areas,
            ),
        }
        content = template_service.get_and_render(clinic["clinic_id"], "BOOKED", variables)
        result = envia_texto(clinic, phone, content, SITE_AGENDAMENTO)
        if not result.success:
            logger.error(f"[PublicBooking] Falha ao enviar confirmação por WhatsApp: {result.error}")
    except Exception as e:
        logger.error(f"[PublicBooking] Erro ao montar/enviar confirmação por WhatsApp: {e}", exc_info=True)

    try:
        orientacoes = orientacoes_da_clinica(template_service, clinic["clinic_id"])
        if orientacoes:
            result = envia_texto(clinic, phone, orientacoes, SITE_AGENDAMENTO)
            if not result.success:
                logger.error(f"[PublicBooking] Falha ao enviar orientações pré-sessão: {result.error}")
    except Exception as e:
        logger.error(f"[PublicBooking] Erro ao enviar orientações pré-sessão: {e}", exc_info=True)


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/appointments

    Body:
    {
        "phone": "string",
        "fullName": "string",
        "serviceIds": ["uuid", ...], // carrinho — 1+ serviços
        "date": "YYYY-MM-DD",
        "time": "HH:MM",
        "professionalId": "uuid",     // opcional
        "serviceAreaPairs": [          // opcional — quando os serviços têm áreas
            {"serviceId": "uuid", "areaId": "uuid"}
        ],
        "token": "string",             // PRD 056: o token de /verify/confirm, sempre
        "substituir": false,           // PRD 056: true = confirmou a troca da sessão do mês
        "cpf": "000.000.000-00",       // PRD 032: obrigatórios quando o celular
        "birthDate": "YYYY-MM-DD",     //   não é de um paciente com cadastro
        "email": "a@b.com"             //   completo; só os que faltam
    }

    Sem os campos que faltam: 400 `code: CADASTRO_INCOMPLETO` com `faltam`.
    CPF que já é de outro paciente da clínica: 409 `code: CPF_EM_USO`.

    Criar exige o código do WhatsApp (PRD 056): `token` de /verify/confirm,
    como cancelar e remarcar; sem ele, 401. Até 21/11/2026 criar não exigia e
    o 409 de agendamento repetido não podia dizer nada da sessão existente.

    Uma sessão por mês: número verificado com sessão confirmada futura no mesmo
    mês da data pedida recebe 409 `code: SAME_MONTH_APPOINTMENT` com `existing`
    (id, date, time, areas). O site avisa que essa sessão será substituída e
    repete o pedido com `substituir: true`: a existente é cancelada com o
    desfecho da antecedência (PRD 054) e a nova nasce vinculada a ela. A
    confirmação chega pelo WhatsApp (template "BOOKED" do bot), como antes.

    Sessão futura em OUTRO mês (PRD 060): 409 `code: OTHER_MONTH_APPOINTMENT`
    com `existing`. O site pergunta "remarcar essa sessão ou marcar mais uma?"
    e repete com `remarcarExistente: true` (a troca acima, da sessão de outro
    mês) ou `maisUma: true` (cria a segunda). Até 23/11/2026 mês diferente
    criava em silêncio.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisição vazio ou inválido"})

        phone = body.get("phone")
        service_ids = body.get("serviceIds")
        appt_date = body.get("date")
        appt_time = body.get("time")
        full_name = (body.get("fullName") or "").strip()

        if not all([phone, service_ids, appt_date, appt_time, full_name]):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: phone, serviceIds, date, time, fullName",
            })
        if not is_valid_phone(str(phone)):
            return http_response(400, {"status": "ERROR", "message": "Telefone inválido"})
        phone = normalize_phone(str(phone))

        # PRD 056: posse do numero antes de criar. Mesma frase do cancelar.
        token = body.get("token")
        if not token or not verify_token(clinic_id, phone, str(token)):
            return http_response(401, {"status": "ERROR", "message": MENSAGEM_TOKEN})

        try:
            data = datetime.strptime(str(appt_date), "%Y-%m-%d").date()
        except ValueError:
            return http_response(400, {"status": "ERROR", "message": "date deve ser YYYY-MM-DD"})
        if not _HORA.match(str(appt_time)):
            return http_response(400, {"status": "ERROR", "message": "time deve ser HH:MM"})

        db = PostgresService()

        clinics = db.execute_query(
            "SELECT clinic_id, timezone, max_future_dates, zapi_instance_id, zapi_instance_token FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})

        pares = carrinho.pares_do_corpo(body.get("serviceAreaPairs"))
        service_ids = carrinho.valida_carrinho(db, clinic_id, service_ids, pares)

        # Cadastro do paciente (PRD 032): o que vier é validado; o que falta no
        # cadastro deste celular é exigido, pela MESMA função que a cotação usa
        # para mostrar os campos. Uma requisição direta não passa pela tela.
        cpf = normaliza_cpf(body.get("cpf"))
        if cpf is False or (cpf and not cpf_valido(cpf)):
            return _cadastro_invalido("cpf", "CPF inválido")
        birth_date = normaliza_data_nascimento(body.get("birthDate"))
        if birth_date is False:
            return _cadastro_invalido("birth_date", "Data de nascimento inválida")
        email = normaliza_email(body.get("email"))
        if email is False:
            return _cadastro_invalido("email", "E-mail inválido")

        paciente = carrinho.paciente_do_telefone(db, clinic_id, phone)
        informados = {"cpf": cpf, "birth_date": birth_date, "email": email}
        faltam = [c for c in carrinho.cadastro_para_o_site(paciente)["faltam"] if not informados.get(c)]
        if faltam:
            return http_response(400, {"status": "ERROR", "code": CADASTRO_INCOMPLETO,
                                       "faltam": faltam, "message": MENSAGEM_CADASTRO})

        if cpf:
            # O mesmo CPF em dois telefones viraria dois pacientes, e o check-in
            # cobraria no cadastro errado.
            proprio = str(paciente["id"]) if paciente else None
            dono = db.execute_query(
                "SELECT id FROM scheduler.patients WHERE clinic_id = %s AND cpf = %s "
                "AND deleted_at IS NULL AND (%s::uuid IS NULL OR id <> %s::uuid) LIMIT 1",
                (clinic_id, cpf, proprio, proprio),
            )
            if dono:
                return http_response(409, {
                    "status": "ERROR", "code": CPF_EM_USO,
                    "message": "Este CPF já está cadastrado com outro celular. Fale com a clínica.",
                })

        # Combos, duração e desconto pelas mesmas funções do agente. Os pares
        # que seguem para a criação são os de DEPOIS do combo: duração, preço e
        # o que fica gravado são os que o WhatsApp gravaria para o mesmo pedido.
        cotacao = carrinho.cota(db, clinic_id, service_ids, pares, phone)

        # A janela do site vale aqui também, não só na tela: o calendário só
        # oferece as próximas datas com horário, mas uma requisição direta não
        # passa pelo calendário. Data e horário têm de estar na grade oferecida
        # (a mesma função de `availability`), o que já exclui o que passou hoje.
        agora = relogio.agora_na_clinica(clinics[0].get("timezone"))
        oferecidos = janela_do_site.dias_oferecidos(
            AvailabilityEngine(db), clinic_id, cotacao.duracao_minutos, agora,
            janela_do_site.quantas(clinics[0]))
        if str(appt_time) not in oferecidos.get(data.isoformat(), {}).get("slots", []):
            return http_response(400, {
                "status": "ERROR",
                "message": "Esta data não está disponível para agendamento online.",
            })

        logger.info(
            f"[PublicBooking][create] {clinic_id} {appt_date} {appt_time} "
            f"dur={cotacao.duracao_minutos} tel={_final_do_telefone(phone)} "
            f"razao={cotacao.desconto.razao} pct={cotacao.desconto.pct}"
        )

        professional_id = carrinho.profissional_da_clinica(db, clinic_id, body.get("professionalId"))
        if body.get("professionalId") and not professional_id:
            logger.warning(f"[PublicBooking][create] {clinic_id} professionalId legado ignorado")

        service = AppointmentService.completo(db)
        substituir = body.get("substituir") is True
        remarcar_existente = body.get("remarcarExistente") is True
        mais_uma = body.get("maisUma") is True

        try:
            result = service.create_appointment(
                clinic_id=clinic_id,
                phone=phone,
                service_id=service_ids[0],
                date=appt_date,
                time=appt_time,
                # Front antigo em cache ainda manda; ausente, o serviço escolhe
                # (o conflito de horário é checado na clínica inteira).
                professional_id=professional_id,
                service_ids=service_ids,
                service_area_pairs=cotacao.pares or None,
                discount_pct=cotacao.desconto.pct,
                discount_reason=cotacao.desconto.razao,
                full_name=full_name,
                cpf=cpf,
                birth_date=birth_date,
                email=email,
                substituir_mesmo_mes=substituir,
                remarcar_a_existente=remarcar_existente,
                mais_uma=mais_uma,
                autor="site",
            )
        except OutraSessaoFutura as e:
            logger.info(
                f"[PublicBooking][create] {clinic_id} tel={_final_do_telefone(phone)} "
                f"já tem sessão em {e.existente['appointment_date']} (outro mês), perguntando remarcar ou mais uma"
            )
            return http_response(409, {
                "status": "ERROR",
                "code": OTHER_MONTH_APPOINTMENT,
                "existing": _existente(e.existente),
                "message": _mensagem_outro_mes(e.existente),
            })
        except SessaoNoMesmoMes as e:
            logger.info(
                f"[PublicBooking][create] {clinic_id} tel={_final_do_telefone(phone)} "
                f"já tem sessão em {e.existente['appointment_date']}, pedindo confirmação da troca"
            )
            return http_response(409, {
                "status": "ERROR",
                "code": SAME_MONTH_APPOINTMENT,
                "existing": _existente(e.existente),
                "message": "Você já tem uma sessão nesta clínica neste mês.",
            })
        except ConflictError:
            # Sem este log o 409 não deixava rastro: era o "agendamento que
            # não chegou no banco" sem nada para investigar.
            logger.warning(
                f"[PublicBooking][create] 409 {clinic_id} {appt_date} {appt_time} "
                f"dur={cotacao.duracao_minutos}"
            )
            raise

        _send_confirmation_whatsapp(db, clinics[0], phone, result, cotacao.qtd_areas)

        return http_response(201, {
            "status": "SUCCESS",
            "message": ("Agendamento remarcado com sucesso" if (substituir or remarcar_existente)
                        else "Agendamento criado com sucesso"),
            "appointment": _serialize_row(result),
        })

    except carrinho.CarrinhoInvalido as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})
    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao criar agendamento público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
