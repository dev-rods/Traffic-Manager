import logging

from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.functions.patient_record._comum import serializa

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """GET /clinics/{clinicId}/session-records/{recordId}/history

    A trilha do registro, do mais antigo para o mais novo. E o que o selo
    "editado" abre. Sem filtro de deleted_at: a trilha sobrevive ao registro,
    de proposito.
    """
    try:
        _, erro = require_api_key(event)
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        record_id = extract_path_param(event, "recordId")
        if not clinic_id or not record_id:
            return http_response(400, {"status": "ERROR",
                                       "message": "clinicId e recordId sao obrigatorios"})

        db = PostgresService()
        linhas = db.execute_query(
            """SELECT id, action, snapshot, changed_by_name, changed_at
               FROM scheduler.patient_session_record_audit
               WHERE record_id = %s::uuid AND clinic_id = %s
               ORDER BY changed_at""",
            (record_id, clinic_id),
        ) or []

        return http_response(200, {
            "status": "SUCCESS",
            "history": [serializa(l) for l in linhas],
        })

    except Exception as e:
        logger.error(f"[Prontuario] Erro ao ler a trilha: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})
