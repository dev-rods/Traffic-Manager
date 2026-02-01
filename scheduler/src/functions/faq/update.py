import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = {"question_label", "answer", "display_order", "active"}


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def handler(event, context):
    """
    Handler para atualizacao de item de FAQ via API.

    PUT /faq/{faqId}
    Body esperado (todos os campos sao opcionais):
    {
        "question_label": "Nova pergunta?",
        "answer": "Nova resposta.",
        "display_order": 2,
        "active": true/false
    }
    """
    try:
        logger.info(f"Requisicao recebida para atualizacao de FAQ: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Parse body e extrair faqId do path
        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisicao vazio ou invalido"
            })

        faq_id = extract_path_param(event, "faqId")
        if not faq_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "faqId nao fornecido no path"
            })

        logger.info(f"Atualizando FAQ: {faq_id}")

        # 3. Construir query dinamica apenas com campos fornecidos
        set_clauses = []
        params = []

        for field in ALLOWED_FIELDS:
            if field in body:
                set_clauses.append(f"{field} = %s")
                params.append(body[field])

        if not set_clauses:
            return http_response(400, {
                "status": "ERROR",
                "message": "Nenhum campo valido fornecido para atualizacao"
            })

        # Adicionar faqId no final dos params para o WHERE
        params.append(faq_id)

        query = f"""
            UPDATE scheduler.faq_items
            SET {', '.join(set_clauses)}
            WHERE id = %s::uuid
            RETURNING *
        """

        # 4. Executar atualizacao
        db = PostgresService()

        result = db.execute_write_returning(query, tuple(params))

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"FAQ nao encontrado: {faq_id}"
            })

        faq = _serialize_row(result)

        logger.info(f"FAQ atualizado com sucesso: {faq_id}")

        # 5. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "message": "FAQ atualizado com sucesso",
            "data": faq
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao atualizar FAQ: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
