import json
import os
import hashlib
import logging
from datetime import datetime, date, time

import secrets

from src.utils.http import parse_body, http_response
from src.services.db.postgres import PostgresService
from src.utils.acesso import (
    ADMIN,
    FUSO_PADRAO,
    HORAS_DE_SESSAO,
    Identidade,
    hash_do_token,
    janela_da_agenda,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _abre_sessao(db, user_id) -> str:
    """Token novo para um funcionário, e o fim das sessões antigas dele.

    Revogar o que existia faz o login valer como troca de turno: quem entra
    agora é a única sessão viva daquela pessoa. Sem isso, um token esquecido
    num computador da recepção continuaria valendo por 12 horas.
    """
    db.execute_write(
        "UPDATE scheduler.user_sessions SET revoked_at = NOW() "
        "WHERE user_id = %s AND revoked_at IS NULL",
        (user_id,),
    )

    token = secrets.token_urlsafe(32)
    # `make_interval` e nao `INTERVAL '%s hours'`: o psycopg2 citaria o
    # parametro DENTRO da string do intervalo e o SQL nao compilaria.
    db.execute_write(
        "INSERT INTO scheduler.user_sessions (user_id, token_hash, expires_at) "
        "VALUES (%s, %s, NOW() + make_interval(hours => %s))",
        (user_id, hash_do_token(token), HORAS_DE_SESSAO),
    )
    return token


def _hash_password(password: str, salt: str) -> str:
    """PBKDF2-SHA256 with 260k iterations (OWASP 2024 recommendation)."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return dk.hex()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Stored format: pbkdf2:salt:hash"""
    parts = stored_hash.split(":")
    if len(parts) != 3 or parts[0] != "pbkdf2":
        return False
    salt = parts[1]
    expected_hash = parts[2]
    return _hash_password(password, salt) == expected_hash


def hash_password_for_storage(password: str) -> str:
    """Generate a storable password hash. Used by seed scripts."""
    salt = os.urandom(16).hex()
    pw_hash = _hash_password(password, salt)
    return f"pbkdf2:{salt}:{pw_hash}"


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def handler(event, context):
    """Handler para POST /auth/login — autentica usuario e retorna token + clinic."""
    try:
        logger.info("Login attempt received")

        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Body vazio ou invalido"
            })

        email = body.get("email", "").strip().lower()
        password = body.get("password", "")

        if not email or not password:
            return http_response(400, {
                "status": "ERROR",
                "message": "Email e senha sao obrigatorios"
            })

        db = PostgresService()

        # Busca user + clinic em uma query
        rows = db.execute_query("""
            SELECT
                u.id as user_id,
                u.email,
                u.password_hash,
                u.name as user_name,
                u.active as user_active,
                u.role as user_role,
                u.agenda_days_ahead,
                u.agenda_visible_until,
                u.can_see_prices,
                u.can_see_patient_list,
                c.clinic_id,
                c.name as clinic_name,
                c.owner_email,
                c.timezone
            FROM scheduler.clinic_users u
            JOIN scheduler.clinics c ON c.clinic_id = u.clinic_id
            WHERE u.email = %s
        """, (email,))

        if not rows:
            logger.info(f"Login failed: email not found ({email})")
            return http_response(401, {
                "status": "ERROR",
                "message": "Email ou senha invalidos"
            })

        user = rows[0]

        if not user.get("user_active", False):
            return http_response(401, {
                "status": "ERROR",
                "message": "Conta desativada"
            })

        if not _verify_password(password, user["password_hash"]):
            logger.info(f"Login failed: wrong password ({email})")
            return http_response(401, {
                "status": "ERROR",
                "message": "Email ou senha invalidos"
            })

        papel = user.get("user_role") or ADMIN

        # O admin continua recebendo a chave mestra, exatamente como antes.
        #
        # Dar a ele uma sessão nova junto com o resto desta mudança mexeria, de
        # uma vez só, na única conta que hoje funciona. A dívida de a chave
        # compartilhada viajar até o navegador segue registrada e será paga à
        # parte; aqui o objetivo é abrir acesso a funcionário sem pôr em risco
        # quem já entra.
        if papel == ADMIN:
            token = os.environ.get("SCHEDULER_API_KEY", "")
        else:
            token = _abre_sessao(db, user["user_id"])

        inicio, fim = janela_da_agenda(
            Identidade(
                papel=papel,
                dias_a_frente=user.get("agenda_days_ahead"),
                visivel_ate=user.get("agenda_visible_until"),
                # Sem isto a janela devolvida ao painel seria calculada em UTC
                # e discordaria da que o servidor aplica nas rotas.
                fuso=user.get("timezone") or FUSO_PADRAO,
            )
        )

        logger.info(f"Login successful: {email} -> {user['clinic_id']} ({papel})")

        return http_response(200, {
            "status": "SUCCESS",
            "token": token,
            "clinic_id": user["clinic_id"],
            "role": papel,
            "user": {
                "id": str(user["user_id"]),
                "name": user.get("user_name"),
                "email": email,
            },
            # A janela vai para a tela para o painel não oferecer o que o
            # servidor vai recusar. Quem decide continua sendo o servidor.
            "agenda_window": None if papel == ADMIN else {
                "from": inicio.isoformat(),
                "to": fim.isoformat(),
            },
            # A tela usa isto para nao oferecer o que nao ha. O servidor aplica
            # os mesmos dois interruptores por conta propria.
            "permissions": {
                "see_prices": papel == ADMIN or bool(user.get("can_see_prices")),
                "see_patient_list": papel == ADMIN or bool(
                    user.get("can_see_patient_list", True)),
            },
            "clinic": {
                "clinic_id": user["clinic_id"],
                "name": user["clinic_name"],
                "owner_email": user.get("owner_email", email)
            }
        })

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno do servidor"
        })
