import json
import logging
from datetime import datetime, date, time

from src.utils.acesso import require_acesso
from src.services.visao_do_staff import para_o_staff, sem_segredos
from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

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


def handler(event, context):
    """
    Handler para obter uma clinica por ID via API.

    GET /clinics/{clinicId}
    """
    try:
        logger.info(f"Requisicao recebida para obter clinica: {json.dumps(event)}")

        # 1. Validar API key
        identidade, error_response = require_acesso(event, "clinica.basica")
        if error_response:
            return error_response

        # 2. Extrair clinicId do path
        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId não fornecido no path"
            })

        logger.info(f"Buscando clinica: {clinic_id}")

        # 3. Buscar clinica no banco
        db = PostgresService()

        query = """
            SELECT * FROM scheduler.clinics
            WHERE clinic_id = %s
        """

        rows = db.execute_query(query, (clinic_id,))

        # 4. Verificar se encontrou
        if not rows:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Clinica não encontrada: {clinic_id}"
            })

        clinic = _serialize_row(rows[0])

        # O funcionário precisa do nome e do horário da clínica para a agenda
        # funcionar, e de mais nada. As credenciais do WhatsApp saem daqui:
        # com elas, um token de funcionário viraria acesso a mandar mensagem
        # em nome da clínica, que é justamente o que ele não pode.
        if not identidade.e_admin:
            clinic = sem_segredos(clinic)

        logger.info(f"Clinica encontrada: {clinic_id}")

        # 5. Retornar resposta
        return http_response(200, para_o_staff(identidade, {
            "status": "SUCCESS",
            "clinic": clinic
        }))

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao obter clinica: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
