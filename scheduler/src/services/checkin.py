# -*- coding: utf-8 -*-
"""Check-in de autoatendimento com pagamento, no iPad da recepção (PRD 026).

A paciente se identifica pelo celular (código no WhatsApp), confirma o
agendamento mais próximo e paga sozinha. Este módulo é tudo o que acontece
depois do token: quais agendamentos o número tem, o check-in, a cobrança e o
que o provedor avisa depois.

Regras que valem em todo lugar daqui:

- O agendamento tem de ser DESTE número (mesmas variantes de telefone do
  "Meus agendamentos"). Id de agendamento de outra pessoa responde como
  inexistente, nunca como "não é seu".
- O valor cobrado é o GRAVADO (`final_price_cents`), o mesmo que o bot e o
  site combinaram. Sem valor, não há cobrança no iPad: a recepção resolve.
- Um pagamento vivo por agendamento (índice único parcial). Trocar de método
  cancela o anterior no provedor ANTES de criar o novo.
"""
import logging
import uuid
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

import psycopg2

from src.providers.payment_provider import (
    AGUARDANDO_DINHEIRO, CANCELADO, DINHEIRO, ESTORNADO, LINK, METODOS, PAGO, PENDENTE, PIX,
    ErroDoProvedor, Pagador, PaymentProvider, cobranca_de_teste,
)
from src.services import mes_vigente
from src.services.appointment_service import AppointmentService
from src.utils.cadastro import cpf_valido, normaliza_cpf
from src.utils.phone import normalize_phone, variantes_do_numero

logger = logging.getLogger(__name__)

VIVOS = (PENDENTE, AGUARDANDO_DINHEIRO, PAGO)
MAX_AGENDAMENTOS = 5


class CheckinInvalido(Exception):
    """Pedido que a paciente pode corrigir na tela (mensagem para ela)."""


class NaoEncontrado(Exception):
    pass


class PrecisaDeCpf(Exception):
    """Link de cobrança sem CPF conhecido: o painel pede e manda de novo."""


def _final(phone: str) -> str:
    return f"***{str(phone)[-4:]}" if phone else "-"


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if hasattr(valor, "isoformat") else (str(valor) if valor else None)


def pagamento_para_tela(row: Optional[Dict]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "method": row["method"],
        "status": row["status"],
        "amountCents": row["amount_cents"],
        "invoiceUrl": row.get("invoice_url"),
        "pixPayload": row.get("pix_payload"),
        "paidAt": _iso(row.get("paid_at")),
        "simulated": cobranca_de_teste(row.get("provider")),
        "canSimulate": _da_para_simular(row),
    }


def _da_para_simular(row: Dict) -> bool:
    """O botão "Simular pagamento (teste)". O simulado simula qualquer método.
    No sandbox do Asaas só o Pix: o "confirmar" do sandbox recusa cartão (pede o
    titular), e cartão se testa pagando a fatura com o cartão de teste."""
    if row.get("provider") == "simulado":
        return True
    return cobranca_de_teste(row.get("provider")) and row.get("method") == PIX


def _mesmo_nome(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a and b) and " ".join(a.lower().split()) == " ".join(b.lower().split())


def _pagamentos_vivos(db, ids: List[str]) -> Dict[str, Dict]:
    if not ids:
        return {}
    rows = db.execute_query(
        "SELECT * FROM scheduler.appointment_payments "
        "WHERE appointment_id = ANY(%s::uuid[]) AND status = ANY(%s)",
        (ids, list(VIVOS)),
    )
    return {str(r["appointment_id"]): r for r in rows}


def agendamentos_do_numero(db, clinic_id: str, phone: str) -> List[Dict[str, Any]]:
    """Os próximos agendamentos confirmados do número, do mais próximo ao mais
    distante, com o que a tela precisa para a paciente reconhecer o seu: data,
    horário, nome de quem agendou, áreas e valor."""
    linhas = AppointmentService.completo(db).get_active_appointments_by_phone(clinic_id, phone)[:MAX_AGENDAMENTOS]
    vivos = _pagamentos_vivos(db, [str(r["id"]) for r in linhas])
    return [
        {
            "id": str(r["id"]),
            "date": _iso(r.get("appointment_date")),
            "startTime": str(r.get("start_time") or "")[:5],
            "fullName": r.get("full_name"),
            "serviceName": r.get("service_name"),
            "areas": [a for a in (r.get("areas_display") or "").split(", ") if a],
            "originalPriceCents": r.get("original_price_cents"),
            "finalPriceCents": r.get("final_price_cents"),
            "discountPct": float(r.get("discount_pct") or 0),
            "checkedInAt": _iso(r.get("checked_in_at")),
            "payment": pagamento_para_tela(vivos.get(str(r["id"]))),
        }
        for r in linhas
    ]


def _do_numero(db, clinic_id: str, phone: str, appointment_id: str) -> Dict:
    """O agendamento confirmado deste número, com o cadastro do paciente."""
    try:
        uuid.UUID(str(appointment_id))
    except ValueError:
        raise NaoEncontrado()
    rows = db.execute_query(
        """
        SELECT a.*, p.id AS patient_uuid, p.name AS patient_name, p.cpf AS patient_cpf
        FROM scheduler.appointments a
        JOIN scheduler.patients p ON p.id = a.patient_id
        WHERE a.id = %s::uuid AND a.clinic_id = %s AND a.status = 'CONFIRMED'
          AND p.phone = ANY(%s) AND p.deleted_at IS NULL
        """,
        (appointment_id, clinic_id, sorted(variantes_do_numero(phone))),
    )
    if not rows:
        raise NaoEncontrado()
    return rows[0]


def _cpf_conhecido(appt: Dict) -> Optional[str]:
    """O CPF do cadastro serve se quem agendou É o titular do cadastro. Num
    telefone compartilhado, o cadastro é de uma pessoa e o agendamento pode ser
    de outra; cobrar no CPF errado seria pior do que perguntar."""
    cpf = normaliza_cpf(appt.get("patient_cpf"))
    if not cpf or not cpf_valido(cpf):
        return None
    nome = appt.get("full_name")
    if nome and not _mesmo_nome(nome, appt.get("patient_name")):
        return None
    return cpf


def confirma(db, clinic_id: str, phone: str, appointment_id: str) -> Dict[str, Any]:
    appt = _do_numero(db, clinic_id, phone, appointment_id)
    if not appt.get("checked_in_at"):
        db.execute_write(
            "UPDATE scheduler.appointments SET checked_in_at = NOW(), updated_at = NOW() "
            "WHERE id = %s::uuid AND checked_in_at IS NULL",
            (appointment_id,),
        )
        logger.info(f"[Checkin] check-in {clinic_id} {appointment_id} tel={_final(phone)}")
    return {"checkedIn": True, "payerCpfKnown": _cpf_conhecido(appt) is not None}


def _vivo(db, appointment_id: str) -> Optional[Dict]:
    return _pagamentos_vivos(db, [appointment_id]).get(appointment_id)


def _marca(db, payment_id: str, status: str) -> None:
    db.execute_write(
        "UPDATE scheduler.appointment_payments SET status = %s, updated_at = NOW(), "
        "paid_at = CASE WHEN %s = 'PAID' THEN COALESCE(paid_at, NOW()) ELSE paid_at END "
        "WHERE id = %s::uuid",
        (status, status, payment_id),
    )


def _descarta(db, provider: PaymentProvider, row: Dict) -> Optional[Dict]:
    """Tira de cena um pagamento vivo que não foi pago. Se o provedor disser
    que ele FOI pago (a paciente pagou o Pix enquanto trocava de método), ele
    fica, e é devolvido para a tela mostrar como pago."""
    if row["provider"] == provider.nome and row.get("provider_payment_id"):
        if provider.consulta_status(row["provider_payment_id"]) == PAGO:
            _marca(db, str(row["id"]), PAGO)
            return dict(row, status=PAGO)
        provider.cancela(row["provider_payment_id"])
    _marca(db, str(row["id"]), CANCELADO)
    return None


def cobra(db, provider: PaymentProvider, clinic_id: str, phone: str, appointment_id: str,
          metodo: str, cpf: Optional[str] = None) -> Dict[str, Any]:
    if metodo not in METODOS:
        raise CheckinInvalido("Escolha uma forma de pagamento.")
    appt = _do_numero(db, clinic_id, phone, appointment_id)
    valor = appt.get("final_price_cents")
    if not valor or int(valor) <= 0:
        raise CheckinInvalido("O valor desta sessão é combinado na recepção.")

    vivo = _vivo(db, appointment_id)
    if vivo:
        if vivo["status"] == PAGO:
            return pagamento_para_tela(vivo)
        if vivo["method"] == metodo and vivo["provider"] == provider.nome:
            return pagamento_para_tela(vivo)
        pago = _descarta(db, provider, vivo)
        if pago:
            return pagamento_para_tela(pago)

    cpf_pagador = _cpf_conhecido(appt)
    if cpf:
        digitos = normaliza_cpf(cpf)
        if not digitos or not cpf_valido(digitos):
            raise CheckinInvalido("Confira o CPF: os números não batem.")
        cpf_pagador = digitos
    if not cpf_pagador:
        raise CheckinInvalido("Informe o CPF de quem vai pagar.")

    nome = appt.get("full_name") or appt.get("patient_name") or "Paciente"
    tz = _fuso(db, clinic_id)
    hoje = mes_vigente.agora_na_clinica(tz).date()
    payment_id = str(uuid.uuid4())
    data_sessao = appt.get("appointment_date")
    descricao = f"Sessão de {data_sessao.strftime('%d/%m/%Y') if hasattr(data_sessao, 'strftime') else data_sessao}"

    cobranca = provider.cria_cobranca(
        Pagador(nome=nome, cpf=cpf_pagador, telefone=normalize_phone(phone)),
        metodo, int(valor), hoje, descricao, payment_id,
    )
    status = AGUARDANDO_DINHEIRO if metodo == DINHEIRO and cobranca.status != PAGO else cobranca.status
    try:
        row = db.execute_write_returning(
            """
            INSERT INTO scheduler.appointment_payments
                (id, clinic_id, appointment_id, method, amount_cents, status, provider,
                 provider_payment_id, invoice_url, pix_payload, payer_name, payer_cpf)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (payment_id, clinic_id, appointment_id, metodo, int(valor), status, provider.nome,
             cobranca.id, cobranca.invoice_url, cobranca.pix_payload, nome, cpf_pagador),
        )
    except psycopg2.IntegrityError:
        # Dois toques ao mesmo tempo: o outro já gravou. A cobrança desta
        # tentativa não pode ficar viva no provedor.
        logger.warning(f"[Checkin] cobrança concorrente em {appointment_id}, descartando {cobranca.id}")
        _cancela_orfa(provider, cobranca.id, payment_id, appointment_id)
        return pagamento_para_tela(_vivo(db, appointment_id))
    except Exception:
        logger.exception(f"[Checkin] cobrança {cobranca.id} criada mas não gravada em {appointment_id}")
        _cancela_orfa(provider, cobranca.id, payment_id, appointment_id)
        raise

    _guarda_cpf_no_cadastro(db, appt, cpf_pagador)
    logger.info(
        f"[Checkin] cobrança {payment_id} {metodo} {valor} {provider.nome}:{cobranca.id} "
        f"{clinic_id} tel={_final(phone)}"
    )
    return pagamento_para_tela(row)


def _cancela_orfa(provider: PaymentProvider, cobranca_id: str, payment_id: str, appointment_id: str) -> None:
    try:
        provider.cancela(cobranca_id)
    except Exception as e:
        logger.error(
            f"[Checkin] cobrança órfã VIVA no provedor {provider.nome}:{cobranca_id} "
            f"(ref {payment_id}, agendamento {appointment_id}): {e}"
        )


def _guarda_cpf_no_cadastro(db, appt: Dict, cpf: str) -> None:
    """Cadastro sem CPF ganha o CPF de quem pagou, se quem pagou é o titular.
    Cadastro COM CPF não é sobrescrito: pode ter sido corrigido à mão."""
    if normaliza_cpf(appt.get("patient_cpf")):
        return
    nome = appt.get("full_name")
    if nome and not _mesmo_nome(nome, appt.get("patient_name")):
        return
    db.execute_write(
        "UPDATE scheduler.patients SET cpf = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND (cpf IS NULL OR cpf = '')",
        (cpf, str(appt["patient_uuid"])),
    )


def _fuso(db, clinic_id: str) -> Optional[str]:
    rows = db.execute_query("SELECT timezone FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,))
    return rows[0].get("timezone") if rows else None


def _pagamento_do_numero(db, clinic_id: str, phone: str, payment_id: str) -> Dict:
    try:
        uuid.UUID(str(payment_id))
    except ValueError:
        raise NaoEncontrado()
    rows = db.execute_query(
        """
        SELECT pay.* FROM scheduler.appointment_payments pay
        JOIN scheduler.appointments a ON a.id = pay.appointment_id
        JOIN scheduler.patients p ON p.id = a.patient_id
        WHERE pay.id = %s::uuid AND pay.clinic_id = %s
          AND p.phone = ANY(%s) AND p.deleted_at IS NULL
        """,
        (payment_id, clinic_id, sorted(variantes_do_numero(phone))),
    )
    if not rows:
        raise NaoEncontrado()
    return rows[0]


def status(db, provider: PaymentProvider, clinic_id: str, phone: str, payment_id: str) -> Dict[str, Any]:
    """O pagamento, como a tela o acompanha. Pendente no Asaas, pergunta ao
    Asaas: o webhook é o caminho normal, isto é a rede para quando ele atrasa."""
    row = _pagamento_do_numero(db, clinic_id, phone, payment_id)
    if row["status"] == PENDENTE and row["provider"] == provider.nome and row.get("provider_payment_id"):
        try:
            atual = provider.consulta_status(row["provider_payment_id"])
        except ErroDoProvedor as e:
            logger.warning(f"[Checkin] consulta de {payment_id} falhou: {e}")
            atual = None
        if atual and atual != row["status"]:
            _marca(db, payment_id, atual)
            row = _pagamento_do_numero(db, clinic_id, phone, payment_id)
    return pagamento_para_tela(row)


def simula_pagamento(db, provider: PaymentProvider, clinic_id: str, phone: str, payment_id: str) -> Dict[str, Any]:
    """Só em teste: provedor simulado, ou Asaas no sandbox (que confirma a
    cobrança de verdade lá e manda o webhook). Em produção não existe."""
    row = _pagamento_do_numero(db, clinic_id, phone, payment_id)
    if row["provider"] != provider.nome or not provider.pode_simular:
        raise NaoEncontrado()
    if not _da_para_simular(row):
        raise CheckinInvalido("No ambiente de teste, pague a fatura com o cartão 4444 4444 4444 4444.")
    if row["status"] in (PENDENTE, AGUARDANDO_DINHEIRO):
        if row.get("provider_payment_id"):
            provider.simula(row["provider_payment_id"])
        _marca(db, payment_id, PAGO)
    return pagamento_para_tela(_pagamento_do_numero(db, clinic_id, phone, payment_id))


def marca_recebido_em_dinheiro(db, provider: PaymentProvider, clinic_id: str, payment_id: str) -> Dict[str, Any]:
    """A recepção recebeu o dinheiro. Só ela chama (Lambda `Caixa`, `agenda.escrever`)."""
    try:
        uuid.UUID(str(payment_id))
    except ValueError:
        raise NaoEncontrado()
    rows = db.execute_query(
        "SELECT * FROM scheduler.appointment_payments WHERE id = %s::uuid AND clinic_id = %s",
        (payment_id, clinic_id),
    )
    if not rows:
        raise NaoEncontrado()
    row = rows[0]
    if row["status"] == PAGO:
        return pagamento_para_tela(row)
    if row["status"] != AGUARDANDO_DINHEIRO:
        raise CheckinInvalido("Este pagamento não está aguardando dinheiro.")
    if row["provider"] == provider.nome and row.get("provider_payment_id"):
        provider.recebe_em_dinheiro(row["provider_payment_id"], row["amount_cents"],
                                    mes_vigente.agora_na_clinica(_fuso(db, clinic_id)).date())
    _marca(db, payment_id, PAGO)
    logger.info(f"[Checkin] dinheiro recebido {payment_id} {clinic_id}")
    rows = db.execute_query("SELECT * FROM scheduler.appointment_payments WHERE id = %s::uuid", (payment_id,))
    return pagamento_para_tela(rows[0])


def estorna(db, provider: PaymentProvider, clinic_id: str, payment_id: str) -> Dict[str, Any]:
    """Devolve um pagamento de sessão cancelada (PRD 028, M7). Só o admin
    chama (Lambda `Caixa`, `require_api_key`): é dinheiro saindo.

    Só vale para sessão CANCELADA: estornar sessão que ainda vai acontecer
    deixaria a paciente atendida sem pagar. Dinheiro não passa pelo provedor
    (o Asaas não tem o que devolver); fica registrado como estornado e a
    devolução é feita em mão, na recepção.
    """
    try:
        uuid.UUID(str(payment_id))
    except ValueError:
        raise NaoEncontrado()
    row = _estornavel(db, clinic_id, payment_id)
    if row["status"] == ESTORNADO:
        return pagamento_para_tela(row)
    if not _troca_status(db, payment_id, PAGO, ESTORNADO):
        row = _estornavel(db, clinic_id, payment_id)
        if row["status"] == ESTORNADO:
            return dict(pagamento_para_tela(row), refundNeedsAuthorization=False)
        raise CheckinInvalido("Só pagamento confirmado pode ser estornado.")
    aguarda_autorizacao = False
    if row["method"] != DINHEIRO and row["provider"] == provider.nome and row.get("provider_payment_id"):
        try:
            aguarda_autorizacao = provider.estorna(row["provider_payment_id"])
        except Exception:
            _troca_status(db, payment_id, ESTORNADO, PAGO)
            raise
    logger.info(f"[Checkin] estorno {payment_id} {row['method']} {row['amount_cents']} {clinic_id}"
                f" aguarda_autorizacao={aguarda_autorizacao}")
    # Estornado aqui = a clínica decidiu devolver e o pedido foi aceito. Se o
    # Asaas ainda pede a autorização do dono da conta, o painel avisa.
    return dict(pagamento_para_tela(dict(row, status=ESTORNADO)),
                refundNeedsAuthorization=aguarda_autorizacao)


def _estornavel(db, clinic_id: str, payment_id: str) -> Dict[str, Any]:
    rows = db.execute_query(
        """
        SELECT pay.*, a.status AS appointment_status
        FROM scheduler.appointment_payments pay
        JOIN scheduler.appointments a ON a.id = pay.appointment_id
        WHERE pay.id = %s::uuid AND pay.clinic_id = %s
        """,
        (payment_id, clinic_id),
    )
    if not rows:
        raise NaoEncontrado()
    row = rows[0]
    if row["status"] not in (PAGO, ESTORNADO):
        raise CheckinInvalido("Só pagamento confirmado pode ser estornado.")
    if row["status"] == PAGO and row.get("appointment_status") != "CANCELLED":
        raise CheckinInvalido("Cancele a sessão antes de estornar o pagamento.")
    return row


def _troca_status(db, payment_id: str, de: str, para: str) -> bool:
    return db.execute_write(
        "UPDATE scheduler.appointment_payments SET status = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = %s",
        (para, payment_id, de),
    ) > 0


# Link de cobrança pelo WhatsApp (PRD 029) ---------------------------------

VENCIMENTO_DO_LINK = timedelta(days=7)


def _whatsapp_padrao(clinic: Dict):
    from src.providers.whatsapp_provider import get_provider
    return get_provider(clinic)


def _mensagem_do_link(appt: Dict, clinica: str, valor_cents: int, link: str) -> str:
    from src.services.preco_minimo import formata_reais
    nome = (appt.get("full_name") or appt.get("patient_name") or "").strip().split(" ")[0]
    data = appt.get("appointment_date")
    data_txt = data.strftime("%d/%m") if hasattr(data, "strftime") else str(data)[8:10] + "/" + str(data)[5:7]
    hora = str(appt.get("start_time") or "")[:5]
    saudacao = f"Olá, {nome}!" if nome else "Olá!"
    return (
        f"{saudacao} Segue o link para pagar a sua sessão de {data_txt} às {hora} na {clinica}:\n\n"
        f"Valor: {formata_reais(valor_cents)}\n{link}\n\n"
        f"No link você escolhe Pix, cartão ou boleto."
    )


def envia_link(db, provider: PaymentProvider, clinic_id: str, appointment_id: str,
               cpf: Optional[str] = None,
               whatsapp_de: Callable[[Dict], Any] = _whatsapp_padrao) -> Dict[str, Any]:
    """Cobrança com forma livre (a paciente escolhe na fatura) mandada pelo
    WhatsApp da clínica, para quem não pagou no check-in (PRD 029).

    Um pagamento vivo por agendamento: link pendente é REENVIADO (sem nova
    cobrança); outra cobrança pendente é descartada antes; pago não envia.
    Falha do WhatsApp não desfaz a cobrança: a resposta traz o link e
    `sent: False`, para a recepção mandar à mão.
    """
    try:
        uuid.UUID(str(appointment_id))
    except ValueError:
        raise NaoEncontrado()
    rows = db.execute_query(
        """
        SELECT a.*, p.id AS patient_uuid, p.name AS patient_name, p.cpf AS patient_cpf,
               p.phone AS patient_phone
        FROM scheduler.appointments a
        JOIN scheduler.patients p ON p.id = a.patient_id
        WHERE a.id = %s::uuid AND a.clinic_id = %s
        """,
        (appointment_id, clinic_id),
    )
    if not rows:
        raise NaoEncontrado()
    appt = rows[0]
    if appt.get("status") != "CONFIRMED":
        raise CheckinInvalido("Só agendamento confirmado pode receber link de pagamento.")
    valor = appt.get("final_price_cents")
    if not valor or int(valor) <= 0:
        raise CheckinInvalido("Este agendamento não tem valor definido.")
    clinicas = db.execute_query("SELECT * FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,))
    if not clinicas:
        raise NaoEncontrado()
    clinica = clinicas[0]

    row = None
    vivo = _vivo(db, appointment_id)
    if vivo:
        if vivo["status"] == PAGO:
            raise CheckinInvalido("Este agendamento já está pago.")
        if vivo["method"] == LINK and vivo["provider"] == provider.nome and vivo.get("invoice_url"):
            row = vivo
        elif _descarta(db, provider, vivo):
            raise CheckinInvalido("Este agendamento acabou de ser pago.")

    if row is None:
        cpf_pagador = _cpf_conhecido(appt)
        if cpf:
            digitos = normaliza_cpf(cpf)
            if not digitos or not cpf_valido(digitos):
                raise CheckinInvalido("Confira o CPF: os números não batem.")
            cpf_pagador = digitos
        if not cpf_pagador:
            raise PrecisaDeCpf()
        row = _cria_link(db, provider, clinic_id, appointment_id, appt, int(valor), cpf_pagador)
        if row is None:
            # Outro pedido criou o pagamento vivo ao mesmo tempo.
            row = _vivo(db, appointment_id)
            if not row or row["method"] != LINK or not row.get("invoice_url"):
                raise CheckinInvalido("O pagamento deste agendamento mudou. Atualize a tela.")

    link = row["invoice_url"]
    nome_clinica = clinica.get("display_name") or clinica.get("name") or "clínica"
    enviado = False
    try:
        resposta = whatsapp_de(clinica).send_text(
            appt["patient_phone"], _mensagem_do_link(appt, nome_clinica, int(row["amount_cents"]), link))
        enviado = bool(resposta.success)
        if not enviado:
            logger.error(f"[Checkin] link {row['id']} não foi pelo WhatsApp: {resposta.error}")
    except Exception as e:
        logger.error(f"[Checkin] link {row['id']} não foi pelo WhatsApp: {e}", exc_info=True)
    logger.info(f"[Checkin] link de cobrança {row['id']} {clinic_id} {appointment_id} "
                f"tel={_final(appt['patient_phone'])} enviado={enviado}")
    return {"payment": pagamento_para_tela(row), "invoiceUrl": link, "sent": enviado}


def _cria_link(db, provider: PaymentProvider, clinic_id: str, appointment_id: str, appt: Dict,
               valor: int, cpf: str) -> Optional[Dict]:
    nome = appt.get("full_name") or appt.get("patient_name") or "Paciente"
    hoje = mes_vigente.agora_na_clinica(_fuso(db, clinic_id)).date()
    payment_id = str(uuid.uuid4())
    data_sessao = appt.get("appointment_date")
    descricao = f"Sessão de {data_sessao.strftime('%d/%m/%Y') if hasattr(data_sessao, 'strftime') else data_sessao}"
    cobranca = provider.cria_cobranca(
        Pagador(nome=nome, cpf=cpf, telefone=normalize_phone(appt["patient_phone"])),
        LINK, valor, hoje + VENCIMENTO_DO_LINK, descricao, payment_id,
    )
    try:
        row = db.execute_write_returning(
            """
            INSERT INTO scheduler.appointment_payments
                (id, clinic_id, appointment_id, method, amount_cents, status, provider,
                 provider_payment_id, invoice_url, pix_payload, payer_name, payer_cpf)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (payment_id, clinic_id, appointment_id, LINK, valor, cobranca.status, provider.nome,
             cobranca.id, cobranca.invoice_url, None, nome, cpf),
        )
    except psycopg2.IntegrityError:
        logger.warning(f"[Checkin] link concorrente em {appointment_id}, descartando {cobranca.id}")
        _cancela_orfa(provider, cobranca.id, payment_id, appointment_id)
        return None
    except Exception:
        logger.exception(f"[Checkin] link {cobranca.id} criado mas não gravado em {appointment_id}")
        _cancela_orfa(provider, cobranca.id, payment_id, appointment_id)
        raise
    _guarda_cpf_no_cadastro(db, appt, cpf)
    return row


EVENTOS_PAGO = {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"}
EVENTOS = {**{e: PAGO for e in EVENTOS_PAGO}, "PAYMENT_DELETED": CANCELADO, "PAYMENT_REFUNDED": ESTORNADO}


def aplica_evento(db, provider: PaymentProvider, evento: Dict[str, Any]) -> str:
    """Um evento do webhook do Asaas. Devolve o que foi feito, para o log.

    Idempotente pelo id do evento, que só é gravado DEPOIS de processado: se
    o processamento falha, o Asaas reenvia e o reenvio não pode ser tomado
    por repetição. Processar duas vezes é inofensivo (as transições são para
    o mesmo estado). Evento de cobrança que não é nossa (a conta do Asaas pode
    ter outras cobranças) é registrado e ignorado.
    """
    event_id = str(evento.get("id") or "")
    tipo = evento.get("event")
    cobranca_id = (evento.get("payment") or {}).get("id")
    if not event_id or not cobranca_id:
        return "ignorado: sem id"

    if db.execute_query(
        "SELECT 1 FROM scheduler.payment_webhook_events WHERE event_id = %s", (event_id,)
    ):
        return "repetido"
    resultado = _processa(db, provider, tipo, cobranca_id, (evento.get("payment") or {}).get("externalReference"))
    db.execute_write(
        "INSERT INTO scheduler.payment_webhook_events (event_id, provider, event, provider_payment_id) "
        "VALUES (%s, 'asaas', %s, %s) ON CONFLICT (event_id) DO NOTHING",
        (event_id, tipo, cobranca_id),
    )
    return resultado


def _processa(db, provider: PaymentProvider, tipo: Optional[str], cobranca_id: str,
              referencia: Optional[str] = None) -> str:
    destino = EVENTOS.get(tipo or "")
    if not destino:
        return f"ignorado: {tipo}"

    rows = db.execute_query(
        "SELECT * FROM scheduler.appointment_payments WHERE provider = 'asaas' AND provider_payment_id = %s",
        (cobranca_id,),
    )
    if not rows:
        if referencia and destino == PAGO:
            logger.error(
                f"[Checkin] {tipo} de cobrança sem registro {cobranca_id} com referência {referencia}: "
                f"possível cobrança órfã do check-in, conferir e estornar"
            )
        return "ignorado: cobrança desconhecida"
    row = rows[0]

    if destino == CANCELADO and row["status"] == PAGO:
        # Pago não volta para cancelado por evento fora de ordem.
        return "ignorado: já pago"
    if destino == PAGO and row["status"] not in VIVOS:
        # Pagou uma cobrança que já tínhamos trocado (Pix pago durante a troca
        # de método). O dinheiro entrou: esta vira a viva e a outra sai.
        outros = db.execute_query(
            "SELECT * FROM scheduler.appointment_payments WHERE appointment_id = %s::uuid "
            "AND status = ANY(%s) AND id <> %s::uuid",
            (str(row["appointment_id"]), [PENDENTE, AGUARDANDO_DINHEIRO, PAGO], str(row["id"])),
        )
        if any(o["status"] == PAGO for o in outros):
            return _pagamento_duplicado(row, cobranca_id)
        for outro in outros:
            try:
                _descarta(db, provider, outro)
            except ErroDoProvedor as e:
                logger.error(f"[Checkin] não descartei {outro['id']} após pagamento tardio: {e}")
                _marca(db, str(outro["id"]), CANCELADO)
    try:
        _marca(db, str(row["id"]), destino)
    except psycopg2.IntegrityError:
        return _pagamento_duplicado(row, cobranca_id)
    logger.info(f"[Checkin] webhook {tipo} -> {destino} pagamento {row['id']}")
    return destino


def _pagamento_duplicado(row: Dict, cobranca_id: str) -> str:
    logger.error(
        f"[Checkin] PAGAMENTO DUPLICADO: cobrança {cobranca_id} (pagamento {row['id']}) paga, mas o "
        f"agendamento {row['appointment_id']} já tem outro pago. Estornar esta cobrança."
    )
    return "conflito: pagamento duplicado"
