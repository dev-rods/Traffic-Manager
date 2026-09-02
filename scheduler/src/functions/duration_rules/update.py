import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = {
    "floor_minutes",
    "ceiling_minutes",
    "step_minutes",
    "is_active",
}

# Minuto zero ou negativo geraria agendamento com fim antes do início, e a
# agenda aceitaria sobreposição infinita.
CAMPOS_DE_MINUTOS = {"floor_minutes", "ceiling_minutes", "step_minutes"}


def _valida(campos, atuais=None):
    """Devolve a primeira mensagem de erro encontrada, ou None.

    `atuais` são os valores já gravados: sem eles, alterar só o piso deixaria
    passar um piso acima do teto vigente, e a validação só pareceria funcionar.
    """
    for campo, valor in campos.items():
        if campo in CAMPOS_DE_MINUTOS:
            if not isinstance(valor, int) or isinstance(valor, bool):
                return f"{campo} deve ser um número inteiro"
            if valor < 1:
                return f"{campo} deve ser maior que zero"

    efetivo = dict(atuais or {})
    efetivo.update(campos)

    piso, teto = efetivo.get("floor_minutes"), efetivo.get("ceiling_minutes")
    if piso is not None and teto is not None and int(piso) > int(teto):
        return "floor_minutes nao pode ser maior que ceiling_minutes"

    passo = efetivo.get("step_minutes")
    if passo is not None and teto is not None and int(passo) > int(teto):
        return "step_minutes nao pode ser maior que ceiling_minutes"

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
        "floor_minutes": 15,
        "ceiling_minutes": 50,
        "step_minutes": 5,
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

        db = PostgresService()

        atuais_rows = db.execute_query(
            "SELECT floor_minutes, ceiling_minutes, step_minutes "
            "FROM scheduler.duration_rules WHERE clinic_id = %s",
            (clinic_id,),
        )
        atuais = atuais_rows[0] if atuais_rows else {}

        informados = {c: body[c] for c in ALLOWED_FIELDS if c in body}
        erro = _valida(informados, atuais)
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
