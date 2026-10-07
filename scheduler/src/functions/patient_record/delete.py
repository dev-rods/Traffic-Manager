import logging

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.historico_de_sessao import grava_trilha
from src.functions.patient_record._comum import registro_com_aplicacoes

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """DELETE /clinics/{clinicId}/session-records/{recordId}

    Soft delete. O registro some da lista e PERMANECE na trilha - prontuario
    apagado sem rastro nao serve como registro de nada.
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

        # O estado ANTES de sumir: e o que a trilha precisa guardar.
        registro = registro_com_aplicacoes(db, record_id)
        if not registro or registro.get("deleted_at"):
            return http_response(404, {"status": "ERROR",
                                       "message": "Registro nao encontrado"})

        db.execute_write(
            """UPDATE scheduler.patient_session_records
               SET deleted_at = NOW(), version = version + 1, updated_at = NOW()
               WHERE id = %s::uuid AND clinic_id = %s""",
            (record_id, clinic_id),
        )

        body = parse_body(event) or {}
        grava_trilha(db, record_id, clinic_id, "DELETE", registro,
                     body.get("changedBy"))

        logger.info(f"[Prontuario] registro excluido: {record_id}")
        return http_response(200, {"status": "SUCCESS",
                                   "message": "Registro excluido"})

    except Exception as e:
        logger.error(f"[Prontuario] Erro ao excluir registro: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})
