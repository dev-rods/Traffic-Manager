import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_query_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    GET /public/resolve-domain?host=agendar.suaempresa.com

    Traduz um domínio customizado pro clinic_id dono dele. O booking-site
    chama isto uma vez, no boot, quando detecta que está rodando fora do seu
    próprio domínio (*.vercel.app) — é o que permite a clínica acessar o site
    pela marca dela sem o clinic_id aparecer na URL.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        host = extract_query_param(event, "host")
        if not host:
            return http_response(400, {"status": "ERROR", "message": "host não fornecido"})

        # Normaliza: navegadores podem mandar porta (localhost:5174) e o
        # registro salvo nunca tem.
        host = host.split(":")[0].lower()

        clinics = db_lookup(host)
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Nenhuma clínica usa este domínio"})

        return http_response(200, {"status": "SUCCESS", "clinicId": clinics[0]["clinic_id"]})

    except Exception as e:
        logger.error(f"Erro ao resolver domínio público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})


def db_lookup(host: str):
    db = PostgresService()
    return db.execute_query(
        "SELECT clinic_id FROM scheduler.clinics WHERE custom_domain = %s AND active = TRUE",
        (host,),
    )
