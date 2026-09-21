# -*- coding: utf-8 -*-
"""PATCH /clinics/{clinicId}/users/{userId} - a janela e o acesso de alguem.

Rota de ADMIN. Tres travas que nao sao detalhe:

1. **Nao se muda papel por aqui.** Promover alguem a administrador e coisa que
   merece um caminho deliberado, e nao um campo numa tela de configuracao.
2. **Nao se mexe em quem e de outra clinica**, mesmo sabendo o id.
3. **Desativar ou encurtar a janela derruba a sessao viva.** Sem isso, tirar o
   acesso de alguem so valeria daqui a 12 horas - que e tempo demais quando o
   motivo de tirar foi uma demissao.
"""
import logging

from src.utils.http import (
    http_response,
    require_api_key,
    extract_path_param,
    parse_body,
)
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_DIAS = 365


def handler(event, context):
    try:
        _, erro = require_api_key(event)
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        user_id = extract_path_param(event, "userId")
        if not clinic_id or not user_id:
            return http_response(400, {
                "status": "ERROR", "message": "clinicId e userId sao obrigatorios"})

        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR", "message": "Body vazio ou invalido"})

        db = PostgresService()

        alvo = db.execute_query(
            "SELECT id, role, active, agenda_days_ahead, agenda_visible_until "
            "FROM scheduler.clinic_users WHERE id = %s::uuid AND clinic_id = %s",
            (user_id, clinic_id))
        if not alvo:
            return http_response(404, {
                "status": "ERROR", "message": "Usuario nao encontrado nesta clinica"})
        antes = alvo[0]

        if "role" in body and body["role"] != antes["role"]:
            return http_response(400, {
                "status": "ERROR",
                "message": "Trocar o papel nao e permitido por esta tela"})

        sets, params = [], []

        if "agenda_days_ahead" in body:
            dias = body["agenda_days_ahead"]
            if dias is not None:
                try:
                    dias = int(dias)
                except (TypeError, ValueError):
                    return http_response(400, {
                        "status": "ERROR",
                        "message": "agenda_days_ahead deve ser um numero inteiro"})
                if dias < 0 or dias > MAX_DIAS:
                    return http_response(400, {
                        "status": "ERROR",
                        "message": "agenda_days_ahead deve ser de 0 a %d" % MAX_DIAS})
            sets.append("agenda_days_ahead = %s")
            params.append(dias)

        if "agenda_visible_until" in body:
            ate = body["agenda_visible_until"] or None
            sets.append("agenda_visible_until = %s")
            params.append(ate)

        for campo in ("can_see_prices", "can_see_patient_list"):
            if campo in body:
                sets.append("%s = %%s" % campo)
                params.append(bool(body[campo]))

        if "active" in body:
            sets.append("active = %s")
            params.append(bool(body["active"]))

        if "name" in body:
            sets.append("name = %s")
            params.append((body["name"] or "").strip() or None)

        if not sets:
            return http_response(400, {
                "status": "ERROR", "message": "Nenhum campo para atualizar"})

        sets.append("updated_at = NOW()")
        params.extend([user_id, clinic_id])

        db.execute_write(
            "UPDATE scheduler.clinic_users SET %s "
            "WHERE id = %%s::uuid AND clinic_id = %%s" % ", ".join(sets),
            tuple(params))

        # Mudanca de acesso precisa valer AGORA. Desativar alguem, ou apertar a
        # janela dele, so faria efeito no proximo login sem esta linha - e o
        # motivo de apertar costuma ser urgente.
        mexeu_no_acesso = any(c in body for c in
                              ("active", "agenda_days_ahead", "agenda_visible_until",
                               "can_see_prices", "can_see_patient_list"))
        if mexeu_no_acesso:
            db.execute_write(
                "UPDATE scheduler.user_sessions SET revoked_at = NOW() "
                "WHERE user_id = %s::uuid AND revoked_at IS NULL", (user_id,))

        depois = db.execute_query(
            "SELECT id, email, name, role, active, agenda_days_ahead, "
            "       agenda_visible_until, can_see_prices, can_see_patient_list "
            "FROM scheduler.clinic_users WHERE id = %s::uuid", (user_id,))[0]

        logger.info(f"Usuario atualizado: {user_id} ({clinic_id})")

        return http_response(200, {
            "status": "SUCCESS",
            "message": ("Acesso atualizado. A pessoa precisara entrar de novo."
                        if mexeu_no_acesso else "Usuario atualizado."),
            "user": {
                "id": str(depois["id"]),
                "email": depois["email"],
                "name": depois["name"],
                "role": depois["role"],
                "active": depois["active"],
                "agenda_days_ahead": depois["agenda_days_ahead"],
                "agenda_visible_until": (depois["agenda_visible_until"].isoformat()
                                         if depois["agenda_visible_until"] else None),
                "can_see_prices": depois["can_see_prices"],
                "can_see_patient_list": depois["can_see_patient_list"],
            },
        })

    except Exception as e:
        logger.error(f"Erro ao atualizar usuario: {e}")
        return http_response(500, {
            "status": "ERROR", "message": "Erro interno no servidor"})
