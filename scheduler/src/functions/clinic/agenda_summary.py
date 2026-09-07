# -*- coding: utf-8 -*-
"""Resumo da agenda dia a dia, para a gerência da clínica.

GET /clinics/{clinicId}/agenda-summary?start=2026-09-01&end=2026-09-30

O dashboard antigo respondia "como foi hoje" e "quantos agendamentos por dia
nesta semana". Quem gerencia uma clínica de estética não pergunta isso: pergunta
quanto entra na quinta, quanto está sendo dado de desconto, quantas desmarcaram,
e se a sala vai ficar vazia à tarde. Todas por DATA, e para datas que ainda vão
acontecer.

`daily_counts` só tinha a contagem. Aqui cada dia traz faturamento, desconto,
cancelamento, ticket médio e minutos ocupados - este último porque numa clínica
de estética a sala é o recurso escasso, e uma agenda com 6 sessões de 15 minutos
não é a mesma coisa que 6 de 50.
"""
import logging
from datetime import date, datetime, timedelta

from src.services.db.postgres import PostgresService
from src.utils.http import (
    extract_path_param,
    extract_query_param,
    http_response,
    require_api_key,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Teto da janela. Sem ele, um `start` de 2020 varreria a tabela inteira a cada
# abertura de tela.
MAX_DIAS = 180
JANELA_PADRAO_DIAS = 30


def _data(texto, padrao):
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date() if texto else padrao
    except (TypeError, ValueError):
        return padrao


def handler(event, context):
    try:
        _, erro = require_api_key(event)
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e obrigatorio"})

        hoje = date.today()
        # O padrão olha para a frente: a pergunta da gerência é sobre o que vem.
        # Passado se pede explicitamente, e a tela deixa.
        inicio = _data(extract_query_param(event, "start"), hoje)
        fim = _data(extract_query_param(event, "end"), inicio + timedelta(days=JANELA_PADRAO_DIAS))

        if fim < inicio:
            inicio, fim = fim, inicio
        if (fim - inicio).days > MAX_DIAS:
            fim = inicio + timedelta(days=MAX_DIAS)

        db = PostgresService()
        linhas = db.execute_query(
            """
            SELECT
                ap.appointment_date AS dia,
                COUNT(*) FILTER (WHERE ap.status = 'CONFIRMED')            AS confirmados,
                COUNT(*) FILTER (WHERE ap.status = 'CANCELLED')            AS cancelados,
                COUNT(DISTINCT ap.patient_id) FILTER (WHERE ap.status = 'CONFIRMED') AS pacientes,
                COALESCE(SUM(ap.original_price_cents) FILTER (WHERE ap.status = 'CONFIRMED'), 0) AS bruto_cents,
                COALESCE(SUM(ap.final_price_cents)    FILTER (WHERE ap.status = 'CONFIRMED'), 0) AS liquido_cents,
                COALESCE(SUM(ap.total_duration_minutes) FILTER (WHERE ap.status = 'CONFIRMED'), 0) AS minutos,
                -- Receita que deixou de entrar por cancelamento. A gerência
                -- precisa ver isso separado do desconto: uma é escolha da
                -- clínica, a outra é perda.
                COALESCE(SUM(ap.final_price_cents) FILTER (WHERE ap.status = 'CANCELLED'), 0) AS perdido_cents
            FROM scheduler.appointments ap
            WHERE ap.clinic_id = %s AND ap.appointment_date BETWEEN %s AND %s
            GROUP BY ap.appointment_date
            ORDER BY ap.appointment_date
            """,
            (clinic_id, inicio.isoformat(), fim.isoformat()),
        )

        dias = []
        for r in linhas:
            bruto = int(r["bruto_cents"] or 0)
            liquido = int(r["liquido_cents"] or 0)
            confirmados = int(r["confirmados"] or 0)
            cancelados = int(r["cancelados"] or 0)
            dias.append({
                "date": r["dia"].isoformat(),
                "confirmed": confirmados,
                "cancelled": cancelados,
                "patients": int(r["pacientes"] or 0),
                "gross_cents": bruto,
                "discount_cents": bruto - liquido,
                "net_cents": liquido,
                "lost_cents": int(r["perdido_cents"] or 0),
                "booked_minutes": int(r["minutos"] or 0),
                # Ticket médio sobre CONFIRMADOS. Dividir pelo total incluindo
                # cancelado daria um número menor que nenhuma sessão custou.
                "avg_ticket_cents": liquido // confirmados if confirmados else 0,
                "cancellation_rate": (
                    round(cancelados / (confirmados + cancelados) * 100)
                    if (confirmados + cancelados) else 0
                ),
            })

        total = {
            "confirmed": sum(d["confirmed"] for d in dias),
            "cancelled": sum(d["cancelled"] for d in dias),
            "gross_cents": sum(d["gross_cents"] for d in dias),
            "discount_cents": sum(d["discount_cents"] for d in dias),
            "net_cents": sum(d["net_cents"] for d in dias),
            "lost_cents": sum(d["lost_cents"] for d in dias),
            "booked_minutes": sum(d["booked_minutes"] for d in dias),
            "days_with_agenda": len(dias),
        }

        return http_response(200, {
            "status": "SUCCESS",
            "clinicId": clinic_id,
            "start": inicio.isoformat(),
            "end": fim.isoformat(),
            "days": dias,
            "total": total,
        })

    except Exception as e:
        logger.error(f"[AgendaSummary] Erro: {e}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
