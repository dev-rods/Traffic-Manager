# -*- coding: utf-8 -*-
"""O caixa da clínica: o que estava previsto, o que entrou e o que falta (PRD 026, fase 2).

Duas datas diferentes, de propósito:

- **Previsto** é pela data da SESSÃO: R$ 135 marcados para terça são o que
  terça deveria render.
- **Recebido** é pela data em que o dinheiro ENTROU (`paid_at`, no fuso da
  clínica): um Pix pago na segunda para a sessão de terça é caixa de segunda.
  É o que bate com o extrato do Asaas e com a gaveta no fim do dia.

Por isso "previsto - recebido" de um dia não é "o que falta" daquele dia. O
que falta é a lista de `pendentes`: sessão confirmada até hoje, com valor, sem
pagamento confirmado - com o estado da cobrança, se houver uma.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from src.providers.payment_provider import METODOS
from src.services import mes_vigente

MAX_DIAS = 92


class PeriodoInvalido(Exception):
    pass


def _data(valor: Optional[str], nome: str) -> date:
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise PeriodoInvalido(f"{nome} deve ser YYYY-MM-DD")


def _iso(v) -> Optional[str]:
    return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v is not None else None)


def _fuso(db, clinic_id: str) -> str:
    rows = db.execute_query("SELECT timezone FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,))
    tz = rows[0].get("timezone") if rows else None
    # Mesmo critério de `mes_vigente.agora_na_clinica`: fuso inválido vira SP.
    return mes_vigente.agora_na_clinica(tz).tzinfo.zone


def resumo(db, clinic_id: str, date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
    inicio, fim = _data(date_from, "date_from"), _data(date_to, "date_to")
    if fim < inicio:
        raise PeriodoInvalido("date_to antes de date_from")
    if (fim - inicio).days >= MAX_DIAS:
        raise PeriodoInvalido(f"Período máximo de {MAX_DIAS} dias")

    tz = _fuso(db, clinic_id)
    hoje = mes_vigente.agora_na_clinica(tz).date()

    previsto = db.execute_query(
        """
        SELECT appointment_date AS dia, COUNT(*) AS sessoes,
               COALESCE(SUM(final_price_cents), 0) AS previsto
        FROM scheduler.appointments
        WHERE clinic_id = %s AND status = 'CONFIRMED' AND appointment_date BETWEEN %s AND %s
        GROUP BY appointment_date
        """,
        (clinic_id, inicio, fim),
    )
    recebido = db.execute_query(
        """
        SELECT (paid_at AT TIME ZONE %s)::date AS dia, method, COUNT(*) AS quantidade,
               SUM(amount_cents) AS recebido
        FROM scheduler.appointment_payments
        WHERE clinic_id = %s AND status = 'PAID'
          AND (paid_at AT TIME ZONE %s)::date BETWEEN %s AND %s
        GROUP BY 1, method
        """,
        (tz, clinic_id, tz, inicio, fim),
    )

    dias: Dict[str, Dict[str, Any]] = {}

    def dia(d) -> Dict[str, Any]:
        chave = _iso(d)
        if chave not in dias:
            dias[chave] = {"date": chave, "sessions": 0, "expectedCents": 0, "receivedCents": 0,
                           "byMethod": {m: 0 for m in METODOS}}
        return dias[chave]

    for r in previsto:
        d = dia(r["dia"])
        d["sessions"] = int(r["sessoes"])
        d["expectedCents"] = int(r["previsto"] or 0)
    por_metodo = {m: {"count": 0, "cents": 0} for m in METODOS}
    for r in recebido:
        d = dia(r["dia"])
        valor = int(r["recebido"] or 0)
        d["receivedCents"] += valor
        d["byMethod"][r["method"]] += valor
        por_metodo[r["method"]]["count"] += int(r["quantidade"])
        por_metodo[r["method"]]["cents"] += valor

    pend = pendentes(db, clinic_id, inicio, min(fim, hoje))
    return {
        "dateFrom": inicio.isoformat(),
        "dateTo": fim.isoformat(),
        "timezone": tz,
        "totals": {
            "expectedCents": sum(d["expectedCents"] for d in dias.values()),
            "receivedCents": sum(d["receivedCents"] for d in dias.values()),
            "pendingCents": sum(p["amountCents"] for p in pend),
            "pendingCount": len(pend),
            "byMethod": por_metodo,
        },
        "days": sorted(dias.values(), key=lambda d: d["date"]),
        "pending": pend,
        "payments": pagamentos(db, clinic_id, tz, inicio, fim),
    }


def pendentes(db, clinic_id: str, inicio: date, ate: date) -> List[Dict[str, Any]]:
    """Sessões confirmadas até hoje, com valor, sem pagamento confirmado.
    Sessão futura ainda não é pendência: não venceu."""
    if ate < inicio:
        return []
    rows = db.execute_query(
        """
        SELECT a.id, a.appointment_date, a.start_time, a.final_price_cents, a.checked_in_at,
               COALESCE(a.full_name, p.name) AS nome,
               vivo.id AS payment_id, vivo.method, vivo.status AS payment_status
        FROM scheduler.appointments a
        LEFT JOIN scheduler.patients p ON p.id = a.patient_id
        LEFT JOIN LATERAL (
            SELECT pay.id, pay.method, pay.status
            FROM scheduler.appointment_payments pay
            WHERE pay.appointment_id = a.id AND pay.status IN ('PENDING', 'AWAITING_CASH', 'PAID')
            LIMIT 1
        ) vivo ON TRUE
        WHERE a.clinic_id = %s AND a.status = 'CONFIRMED'
          AND a.appointment_date BETWEEN %s AND %s
          AND COALESCE(a.final_price_cents, 0) > 0
          AND (vivo.status IS NULL OR vivo.status <> 'PAID')
        ORDER BY a.appointment_date, a.start_time
        """,
        (clinic_id, inicio, ate),
    )
    return [
        {
            "appointmentId": str(r["id"]),
            "date": _iso(r["appointment_date"]),
            "startTime": str(r["start_time"])[:5],
            "name": r.get("nome"),
            "amountCents": int(r["final_price_cents"]),
            "checkedIn": r.get("checked_in_at") is not None,
            "paymentId": str(r["payment_id"]) if r.get("payment_id") else None,
            "method": r.get("method"),
            "paymentStatus": r.get("payment_status"),
        }
        for r in rows
    ]


def pagamentos(db, clinic_id: str, tz: str, inicio: date, fim: date) -> List[Dict[str, Any]]:
    rows = db.execute_query(
        """
        SELECT pay.id, pay.method, pay.amount_cents, pay.paid_at, pay.provider,
               a.appointment_date, a.start_time, COALESCE(a.full_name, p.name) AS nome
        FROM scheduler.appointment_payments pay
        JOIN scheduler.appointments a ON a.id = pay.appointment_id
        LEFT JOIN scheduler.patients p ON p.id = a.patient_id
        WHERE pay.clinic_id = %s AND pay.status = 'PAID'
          AND (pay.paid_at AT TIME ZONE %s)::date BETWEEN %s AND %s
        ORDER BY pay.paid_at
        """,
        (clinic_id, tz, inicio, fim),
    )
    return [
        {
            "id": str(r["id"]),
            "method": r["method"],
            "amountCents": int(r["amount_cents"]),
            "paidAt": _iso(r.get("paid_at")),
            "appointmentDate": _iso(r["appointment_date"]),
            "startTime": str(r["start_time"])[:5],
            "name": r.get("nome"),
            "simulated": r.get("provider") == "simulado",
        }
        for r in rows
    ]
