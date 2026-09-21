# -*- coding: utf-8 -*-
"""GET /clinics/{clinicId}/users - quem entra no painel desta clinica.

Rota de ADMIN: usa `require_api_key`, entao o proprio funcionario nao alcanca.
Ele nao pode ver a lista de contas nem, muito menos, mexer na propria janela.

A senha nao aparece aqui em forma nenhuma, nem o hash: uma tela de gestao nao
precisa dele, e o que nao viaja nao vaza.
"""
import logging

from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    try:
        _, erro = require_api_key(event)
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR", "message": "clinicId e obrigatorio"})

        linhas = PostgresService().execute_query(
            """
            SELECT u.id, u.email, u.name, u.role, u.active,
                   u.agenda_days_ahead, u.agenda_visible_until,
                   u.can_see_prices, u.can_see_patient_list,
                   u.created_at,
                   (SELECT MAX(s.created_at) FROM scheduler.user_sessions s
                     WHERE s.user_id = u.id) AS last_login_at
              FROM scheduler.clinic_users u
             WHERE u.clinic_id = %s
             ORDER BY u.role, u.email
            """,
            (clinic_id,),
        )

        usuarios = [{
            "id": str(u["id"]),
            "email": u["email"],
            "name": u["name"],
            "role": u["role"],
            "active": u["active"],
            "agenda_days_ahead": u["agenda_days_ahead"],
            "agenda_visible_until": (u["agenda_visible_until"].isoformat()
                                     if u["agenda_visible_until"] else None),
            "can_see_prices": u["can_see_prices"],
            "can_see_patient_list": u["can_see_patient_list"],
            "last_login_at": (u["last_login_at"].isoformat()
                              if u["last_login_at"] else None),
        } for u in linhas]

        return http_response(200, {
            "status": "SUCCESS",
            "clinicId": clinic_id,
            "users": usuarios,
            "total": len(usuarios),
        })

    except Exception as e:
        logger.error(f"Erro ao listar usuarios: {e}")
        return http_response(500, {
            "status": "ERROR", "message": "Erro interno no servidor"})
