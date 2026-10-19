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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2

from src.providers.payment_provider import (
    AGUARDANDO_DINHEIRO, CANCELADO, DINHEIRO, ESTORNADO, METODOS, PAGO, PENDENTE,
    ErroDoProvedor, Pagador, PaymentProvider,
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
        "simulated": row.get("provider") == "simulado",
    }


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
        try:
            provider.cancela(cobranca.id)
        except ErroDoProvedor as e:
            logger.error(f"[Checkin] não cancelei a cobrança duplicada {cobranca.id}: {e}")
        return pagamento_para_tela(_vivo(db, appointment_id))

    _guarda_cpf_no_cadastro(db, appt, cpf_pagador)
    logger.info(
        f"[Checkin] cobrança {payment_id} {metodo} {valor} {provider.nome}:{cobranca.id} "
        f"{clinic_id} tel={_final(phone)}"
    )
    return pagamento_para_tela(row)


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
    row = _pagamento_do_numero(db, clinic_id, phone, payment_id)
    if row["provider"] != "simulado" or provider.nome != "simulado":
        raise NaoEncontrado()
    if row["status"] in (PENDENTE, AGUARDANDO_DINHEIRO):
        _marca(db, payment_id, PAGO)
    return pagamento_para_tela(_pagamento_do_numero(db, clinic_id, phone, payment_id))


def marca_recebido_em_dinheiro(db, provider: PaymentProvider, clinic_id: str, payment_id: str) -> Dict[str, Any]:
    """A recepção recebeu o dinheiro. Só ela chama (chave do painel)."""
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
                                    datetime.now(timezone.utc).date())
    _marca(db, payment_id, PAGO)
    logger.info(f"[Checkin] dinheiro recebido {payment_id} {clinic_id}")
    rows = db.execute_query("SELECT * FROM scheduler.appointment_payments WHERE id = %s::uuid", (payment_id,))
    return pagamento_para_tela(rows[0])


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
    resultado = _processa(db, provider, tipo, cobranca_id)
    db.execute_write(
        "INSERT INTO scheduler.payment_webhook_events (event_id, provider, event, provider_payment_id) "
        "VALUES (%s, 'asaas', %s, %s) ON CONFLICT (event_id) DO NOTHING",
        (event_id, tipo, cobranca_id),
    )
    return resultado


def _processa(db, provider: PaymentProvider, tipo: Optional[str], cobranca_id: str) -> str:
    destino = EVENTOS.get(tipo or "")
    if not destino:
        return f"ignorado: {tipo}"

    rows = db.execute_query(
        "SELECT * FROM scheduler.appointment_payments WHERE provider = 'asaas' AND provider_payment_id = %s",
        (cobranca_id,),
    )
    if not rows:
        return "ignorado: cobrança desconhecida"
    row = rows[0]

    if destino == CANCELADO and row["status"] == PAGO:
        # Pago não volta para cancelado por evento fora de ordem.
        return "ignorado: já pago"
    if destino == PAGO and row["status"] not in VIVOS:
        # Pagou uma cobrança que já tínhamos trocado (Pix pago durante a troca
        # de método). O dinheiro entrou: esta vira a viva e a outra sai.
        for outro in db.execute_query(
            "SELECT * FROM scheduler.appointment_payments WHERE appointment_id = %s::uuid "
            "AND status = ANY(%s) AND id <> %s::uuid",
            (str(row["appointment_id"]), [PENDENTE, AGUARDANDO_DINHEIRO], str(row["id"])),
        ):
            try:
                _descarta(db, provider, outro)
            except ErroDoProvedor as e:
                logger.error(f"[Checkin] não descartei {outro['id']} após pagamento tardio: {e}")
                _marca(db, str(outro["id"]), CANCELADO)
    _marca(db, str(row["id"]), destino)
    logger.info(f"[Checkin] webhook {tipo} -> {destino} pagamento {row['id']}")
    return destino
