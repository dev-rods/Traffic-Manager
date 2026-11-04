# -*- coding: utf-8 -*-
"""PUT /clinics/{clinicId}/professionals/{professionalId} (PRD 036).

Até aqui profissionais só tinham Create e List. O termo de consentimento
precisa do registro no conselho da responsável técnica, e ele é editado no
painel. Admin, como o create.
"""
import logging
from datetime import date, datetime, time

from src.services.db.postgres import PostgresService
from src.utils.http import extract_path_param, http_response, parse_body, require_api_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = ("name", "role", "registro_conselho", "active")
TAMANHO_REGISTRO = 60


def _serialize_row(row):
    return {k: v.isoformat() if isinstance(v, (datetime, date, time)) else v for k, v in row.items()}


def _erro(status, mensagem):
    return http_response(status, {"status": "ERROR", "message": mensagem})


def handler(event, context):
    try:
        _, erro = require_api_key(event)
        if erro:
            return erro
        clinic_id = extract_path_param(event, "clinicId")
        professional_id = extract_path_param(event, "professionalId")
        if not clinic_id or not professional_id:
            return _erro(400, "clinicId e professionalId são obrigatórios")
        body = parse_body(event)
        if not body:
            return _erro(400, "Corpo da requisição vazio ou inválido")

        set_clauses, params = [], []
        for campo in ALLOWED_FIELDS:
            if campo not in body:
                continue
            valor = body[campo]
            if campo == "name":
                valor = " ".join(str(valor or "").split())
                if not valor:
                    return _erro(400, "name não pode ser vazio")
            elif campo == "role":
                valor = (str(valor).strip() or None) if valor is not None else None
            elif campo == "registro_conselho":
                valor = (str(valor).strip()[:TAMANHO_REGISTRO] or None) if valor is not None else None
            elif campo == "active":
                if not isinstance(valor, bool):
                    return _erro(400, "active deve ser true ou false")
            set_clauses.append(f"{campo} = %s")
            params.append(valor)
        if not set_clauses:
            return _erro(400, "Nenhum campo válido fornecido para atualização")
        set_clauses.append("updated_at = NOW()")
        params.extend([professional_id, clinic_id])

        row = PostgresService().execute_write_returning(
            f"UPDATE scheduler.professionals SET {', '.join(set_clauses)} "
            "WHERE id = %s::uuid AND clinic_id = %s RETURNING *",
            tuple(params),
        )
        if not row:
            return _erro(404, "Profissional não encontrado")
        logger.info(f"[UpdateProfessional] {clinic_id} {professional_id}: {sorted(c.split(' ')[0] for c in set_clauses[:-1])}")
        return http_response(200, {"status": "SUCCESS", "professional": _serialize_row(row)})
    except Exception as e:
        logger.error(f"[UpdateProfessional] erro: {e}", exc_info=True)
        return _erro(500, "Erro interno no servidor")
