import logging

from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    DELETE /clinics/{clinicId}/patients/{patientId}
    Soft-delete: seta deleted_at = NOW() se ainda nao deletado.
    Idempotente: paciente ja deletado retorna 200 sem rescrever o timestamp.
    """
    try:
        logger.info("Delete patient request received")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        patient_id = extract_path_param(event, "patientId")
        if not clinic_id or not patient_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId e patientId sao obrigatorios"
            })

        db = PostgresService()

        existing = db.execute_query(
            "SELECT id, deleted_at FROM scheduler.patients WHERE id = %s::uuid AND clinic_id = %s",
            (patient_id, clinic_id),
        )
        if not existing:
            return http_response(404, {
                "status": "ERROR",
                "message": "Paciente nao encontrado"
            })

        if existing[0].get("deleted_at"):
            logger.info(f"Patient {patient_id} already soft-deleted, returning 200")
            return http_response(200, {
                "status": "SUCCESS",
                "message": "Paciente ja estava excluido"
            })

        db.execute_write_returning(
            "UPDATE scheduler.patients SET deleted_at = NOW(), updated_at = NOW() "
            "WHERE id = %s::uuid AND clinic_id = %s RETURNING id",
            (patient_id, clinic_id),
        )

        logger.info(f"Patient soft-deleted: {patient_id}")
        return http_response(200, {
            "status": "SUCCESS",
            "message": "Paciente excluido"
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error deleting patient: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno do servidor",
            "error": error_msg,
        })
