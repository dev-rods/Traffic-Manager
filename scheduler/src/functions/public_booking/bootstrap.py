import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param
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
    GET /public/clinics/{clinicId}/bootstrap

    Dados públicos de bootstrap do booking-site: clínica (nome/logo/timezone),
    serviços ativos e profissionais ativos. Sem preço/agenda por profissional
    aqui — isso vem de /available-slots.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        db = PostgresService()

        clinics = db.execute_query(
            """
            SELECT clinic_id, name, display_name, logo_url, favicon_url, timezone
            FROM scheduler.clinics
            WHERE clinic_id = %s AND active = TRUE
            """,
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})

        services = db.execute_query(
            """
            SELECT id, name, duration_minutes, price_cents, description
            FROM scheduler.services
            WHERE clinic_id = %s AND active = TRUE
            ORDER BY name
            """,
            (clinic_id,),
        )

        professionals = db.execute_query(
            """
            SELECT id, name, role, photo_url
            FROM scheduler.professionals
            WHERE clinic_id = %s AND active = TRUE
            ORDER BY name
            """,
            (clinic_id,),
        )

        # Áreas de tratamento por serviço (mesma junção usada pelo bot em
        # ConversationEngine._on_enter_select_areas / GET /services/{serviceId}/areas):
        # cada par (serviço, área) pode sobrescrever duração/preço do serviço base.
        service_areas = db.execute_query(
            """
            SELECT sa.id as service_area_id, sa.service_id, sa.area_id,
                   a.name as area_name, a.display_order,
                   COALESCE(sa.duration_minutes, s.duration_minutes) as duration_minutes,
                   COALESCE(sa.price_cents, s.price_cents) as price_cents
            FROM scheduler.service_areas sa
            JOIN scheduler.areas a ON sa.area_id = a.id AND a.active = TRUE
            JOIN scheduler.services s ON sa.service_id = s.id
            WHERE s.clinic_id = %s AND sa.active = TRUE AND s.active = TRUE
            ORDER BY s.name, a.display_order, a.name
            """,
            (clinic_id,),
        )

        return http_response(200, {
            "status": "SUCCESS",
            "clinic": _serialize_row(clinics[0]),
            "services": [_serialize_row(r) for r in services],
            "professionals": [_serialize_row(r) for r in professionals],
            "serviceAreas": [_serialize_row(r) for r in service_areas],
        })

    except Exception as e:
        logger.error(f"Erro ao buscar bootstrap público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
