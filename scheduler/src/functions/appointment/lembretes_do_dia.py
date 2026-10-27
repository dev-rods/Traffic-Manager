# -*- coding: utf-8 -*-
"""Lembrar a agenda de um dia, pelo botao do painel (PRD 027).

POST /clinics/{clinicId}/agenda/{dia}/lembretes[?simular=true]

`simular` devolve as contagens para a previa. Sem ele, enfileira o lote com
`send_at` = agora (ou o fim do silencio) e acorda o processador para a entrega
sair na hora, como IniciarConversaPeloBot faz com o OutboundProcessor.
"""
import json
import logging
import os
from datetime import datetime, timezone

from src.services.autoatendimento import link_de_autoatendimento
from src.services.db.postgres import PostgresService
from src.services.lembrete_da_agenda import enfileira, send_at_do_lote
from src.services.reminder_service import ReminderService
from src.utils.acesso import hoje_na_clinica, require_acesso
from src.utils.http import extract_path_param, extract_query_param, http_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _hoje(clinic) -> str:
    return hoje_na_clinica(clinic.get("timezone")).isoformat()


def _acorda_processador() -> None:
    import boto3

    nome = os.environ.get("REMINDER_PROCESSOR_FUNCTION_NAME")
    if not nome:
        logger.warning("[LembretesDoDia] REMINDER_PROCESSOR_FUNCTION_NAME ausente; o cron horario entrega")
        return
    boto3.client("lambda").invoke(FunctionName=nome, InvocationType="Event", Payload=json.dumps({}).encode())


def handler(event, context):
    try:
        identidade, erro = require_acesso(event, "agenda.escrever")
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        dia = extract_path_param(event, "dia") or ""
        simular = (extract_query_param(event, "simular") or "").lower() in ("1", "true")
        try:
            datetime.strptime(dia, "%Y-%m-%d")
        except ValueError:
            return http_response(400, {"status": "ERROR", "message": "dia deve ser YYYY-MM-DD"})

        db = PostgresService()
        clinicas = db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE", (clinic_id,))
        if not clinicas:
            return http_response(404, {"status": "ERROR", "message": "Clinica nao encontrada"})
        clinic = clinicas[0]
        if dia < _hoje(clinic):
            return http_response(400, {"status": "ERROR", "message": "Nao se lembra agenda de dia passado"})

        agora = datetime.now(timezone.utc)
        send_at = send_at_do_lote(clinic, agora)
        resultado = enfileira(db, ReminderService(), clinic, dia, send_at, simular=simular)
        resultado["adiados_para"] = resultado["send_at"] if send_at > agora else None
        resultado["tem_link_de_autoatendimento"] = link_de_autoatendimento(clinic) is not None
        if not simular and resultado["enfileirados"] > 0 and resultado["adiados_para"] is None:
            _acorda_processador()

        logger.info(f"[LembretesDoDia] {clinic_id} {dia} simular={simular} por={identidade.user_id or 'admin'}: {resultado}")
        return http_response(200, {"status": "SUCCESS", **resultado})
    except Exception as e:
        logger.error(f"Erro ao lembrar agenda: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
