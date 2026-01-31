import json
import logging
from datetime import datetime, date

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def handler(event, context):
    """
    Handler para criacao de item de FAQ via API.

    POST /clinics/{clinicId}/faq
    Body esperado:
    {
        "question_key": "EQUIPMENT",
        "question_label": "Qual equipamento voces usam?",
        "answer": "Trabalhamos com o Soprano Ice Platinum...",
        "display_order": 1   (opcional, default 0)
    }
    """
    try:
        logger.info(f"Requisicao recebida para criacao de FAQ: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Parse body e extrair clinicId do path
        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisicao vazio ou invalido"
            })

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId nao fornecido no path"
            })

        # 3. Validar campos obrigatorios
        question_key = body.get("question_key")
        question_label = body.get("question_label")
        answer = body.get("answer")

        if not question_key or not question_label or not answer:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: question_key, question_label, answer"
            })

        display_order = body.get("display_order", 0)

        logger.info(f"[clinicId: {clinic_id}] Criando FAQ: {question_key}")

        # 4. Inserir no banco de dados
        db = PostgresService()

        query = """
            INSERT INTO scheduler.faq_items (
                id, clinic_id, question_key, question_label, answer, display_order
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, %s
            )
            RETURNING *
        """

        params = (
            clinic_id,
            question_key,
            question_label,
            answer,
            display_order,
        )

        result = db.execute_write_returning(query, params)

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Erro ao criar FAQ"
            })

        faq = _serialize_row(result)

        logger.info(f"[clinicId: {clinic_id}] FAQ criado com sucesso: {question_key}")

        # 5. Retornar resposta
        return http_response(201, {
            "status": "SUCCESS",
            "message": "FAQ criado com sucesso",
            "data": faq
        })

    except Exception as e:
        error_msg = str(e)

        # Handle unique constraint violation (clinic_id, question_key)
        if "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            logger.warning(f"[clinicId: {clinic_id}] FAQ duplicado: {body.get('question_key')}")
            return http_response(409, {
                "status": "ERROR",
                "message": "Ja existe um FAQ com essa question_key para esta clinica"
            })

        logger.error(f"Erro ao criar FAQ: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
