import json
import logging
from datetime import datetime, date, time

from psycopg2.extras import Json

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.vercel_domain_service import VercelDomainService, VercelDomainError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = {
    "name",
    "phone",
    "address",
    "timezone",
    "business_hours",
    "buffer_minutes",
    "welcome_message",
    "pre_session_instructions",
    "zapi_instance_id",
    "zapi_instance_token",
    "owner_email",
    "use_agent",
    "max_future_dates",
    "active",
    "display_name",
    "welcome_intro_message",
    "bot_paused",
    "batch_message_template",
    "logo_url",
    "favicon_url",
    "bot_autoreply_policy",
    "bot_pilot_phones",
    "custom_domain",
}

JSONB_FIELDS = {"business_hours"}


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _sync_vercel_domain(previous_domain, new_domain):
    """Reflete a troca de domínio no projeto Vercel do booking-site.

    Nunca derruba a resposta: o dado já foi persistido no banco quando isto
    roda. Se a Vercel falhar (credencial ausente, domínio já em uso por
    outro projeto, etc.), devolve um aviso pro painel mostrar - a clínica
    não some, só o domínio não entra no ar até o problema ser corrigido.
    """
    service = VercelDomainService()
    if not service.configured:
        if new_domain:
            logger.warning("[UpdateClinic] VERCEL_API_TOKEN ausente — domínio não registrado na Vercel")
            return "Domínio salvo, mas a integração com a Vercel não está configurada."
        return None

    try:
        if previous_domain:
            service.remove_domain(previous_domain)
        if new_domain:
            service.add_domain(new_domain)
        return None
    except VercelDomainError as e:
        logger.error(f"[UpdateClinic] Falha ao sincronizar domínio com a Vercel: {e}")
        return str(e)


def handler(event, context):
    """
    Handler para atualizacao de clinica via API.

    PUT /clinics/{clinicId}
    Body esperado (todos os campos sao opcionais):
    {
        "name": "...",
        "phone": "...",
        "address": "...",
        "timezone": "...",
        "business_hours": {...},
        "buffer_minutes": 15,
        "welcome_message": "...",
        "pre_session_instructions": "...",
        "zapi_instance_id": "...",
        "zapi_instance_token": "...",
        "active": true/false
    }
    """
    try:
        logger.info(f"Requisicao recebida para atualizacao de clinica: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Parse body
        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisição vazio ou inválido"
            })

        # 3. Extrair clinicId do path
        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId não fornecido no path"
            })

        logger.info(f"Atualizando clinica: {clinic_id}")

        db = PostgresService()

        # Precisa do domínio ANTIGO antes de sobrescrever: é o que vai ser
        # removido do projeto Vercel se a clínica trocar ou limpar o domínio.
        previous_domain = None
        if "custom_domain" in body:
            existing = db.execute_query(
                "SELECT custom_domain FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,)
            )
            if existing:
                previous_domain = existing[0].get("custom_domain")

        # 4. Construir query dinamica apenas com campos fornecidos
        set_clauses = []
        params = []

        for field in ALLOWED_FIELDS:
            if field in body:
                value = body[field]
                if field in JSONB_FIELDS:
                    value = Json(value)
                set_clauses.append(f"{field} = %s")
                params.append(value)

        if not set_clauses:
            return http_response(400, {
                "status": "ERROR",
                "message": "Nenhum campo válido fornecido para atualização"
            })

        # Sempre atualizar updated_at
        set_clauses.append("updated_at = NOW()")

        # Adicionar clinic_id no final dos params para o WHERE
        params.append(clinic_id)

        query = f"""
            UPDATE scheduler.clinics
            SET {', '.join(set_clauses)}
            WHERE clinic_id = %s
            RETURNING *
        """

        # 5. Executar atualizacao
        result = db.execute_write_returning(query, tuple(params))

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Clinica não encontrada: {clinic_id}"
            })

        clinic = _serialize_row(result)

        logger.info(f"Clinica atualizada com sucesso: {clinic_id}")

        domain_warning = None
        new_domain = clinic.get("custom_domain")
        if "custom_domain" in body and new_domain != previous_domain:
            domain_warning = _sync_vercel_domain(previous_domain, new_domain)

        # 6. Retornar resposta
        response_body = {
            "status": "SUCCESS",
            "message": "Clinica atualizada com sucesso",
            "clinicId": clinic_id,
            "clinic": clinic
        }
        if domain_warning:
            response_body["domainWarning"] = domain_warning
        return http_response(200, response_body)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao atualizar clinica: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
