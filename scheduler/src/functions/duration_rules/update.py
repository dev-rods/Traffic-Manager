import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = {
    "base_duration_minutes",
    "tier_2_min_areas",
    "tier_2_max_areas",
    "tier_2_duration_minutes",
    "tier_3_min_areas",
    "tier_3_max_areas",
    "tier_3_duration_minutes",
    "tier_4_min_areas",
    "tier_4_duration_minutes",
    "is_active",
}

# Campos de duração precisam ser positivos: minuto zero ou negativo geraria
# agendamento com fim antes do início, e a agenda aceitaria sobreposição infinita.
CAMPOS_DE_MINUTOS = {
    "base_duration_minutes",
    "tier_2_duration_minutes",
    "tier_3_duration_minutes",
    "tier_4_duration_minutes",
}
CAMPOS_DE_AREAS = {
    "tier_2_min_areas",
    "tier_2_max_areas",
    "tier_3_min_areas",
    "tier_3_max_areas",
    "tier_4_min_areas",
}


def _valida(campos):
    """Devolve a primeira mensagem de erro encontrada, ou None."""
    for campo, valor in campos.items():
        if campo in CAMPOS_DE_MINUTOS or campo in CAMPOS_DE_AREAS:
            if not isinstance(valor, int) or isinstance(valor, bool):
                return f"{campo} deve ser um número inteiro"
            if valor < 1:
                return f"{campo} deve ser maior que zero"

    # As faixas precisam subir: 2 antes de 3, 3 antes de 4. Fora de ordem, a
    # busca da faixa devolveria sempre a mais alta e todo mundo teria 45 minutos.
    fronteiras = [
        ("tier_2_min_areas", "tier_2_max_areas"),
        ("tier_3_min_areas", "tier_3_max_areas"),
    ]
    for min_campo, max_campo in fronteiras:
        minimo, maximo = campos.get(min_campo), campos.get(max_campo)
        if minimo is not None and maximo is not None and maximo < minimo:
            return f"{max_campo} nao pode ser menor que {min_campo}"

    ordem = ["tier_2_min_areas", "tier_3_min_areas", "tier_4_min_areas"]
    valores = [campos.get(c) for c in ordem]
    informados = [(c, v) for c, v in zip(ordem, valores) if v is not None]
    for (campo_a, valor_a), (campo_b, valor_b) in zip(informados, informados[1:]):
        if valor_b <= valor_a:
            return f"{campo_b} deve ser maior que {campo_a}"

    return None


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
    Handler para atualizacao de duration rules via API.

    PUT /clinics/{clinicId}/duration-rules
    Body esperado (todos os campos sao opcionais):
    {
        "first_session_discount_pct": 25,
        "tier_2_discount_pct": 12,
        "is_active": false
    }
    """
    try:
        logger.info(f"Requisicao recebida para atualizacao de duration rules: {json.dumps(event)}")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisição vazio ou inválido"
            })

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId não fornecido no path"
            })

        logger.info(f"Atualizando duration rules para clinica: {clinic_id}")

        set_clauses = []
        params = []

        informados = {c: body[c] for c in ALLOWED_FIELDS if c in body}
        erro = _valida(informados)
        if erro:
            return http_response(400, {"status": "ERROR", "message": erro})

        for field in ALLOWED_FIELDS:
            if field in body:
                set_clauses.append(f"{field} = %s")
                params.append(body[field])

        if not set_clauses:
            return http_response(400, {
                "status": "ERROR",
                "message": "Nenhum campo válido fornecido para atualização"
            })

        set_clauses.append("updated_at = NOW()")
        params.append(clinic_id)

        query = f"""
            UPDATE scheduler.duration_rules
            SET {', '.join(set_clauses)}
            WHERE clinic_id = %s
            RETURNING *
        """

        db = PostgresService()

        result = db.execute_write_returning(query, tuple(params))

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Duration rules não encontradas para clinica: {clinic_id}"
            })

        logger.info(f"Duration rules atualizadas para clinica: {clinic_id}")

        return http_response(200, {
            "status": "SUCCESS",
            "message": "Duration rules atualizadas com sucesso",
            "duration_rules": _serialize_row(result)
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao atualizar duration rules: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
