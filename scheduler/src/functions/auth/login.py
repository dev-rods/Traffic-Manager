import json
import os
import hashlib
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
                c.clinic_id,
                c.name as clinic_name,
                c.owner_email
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

        # Token = SCHEDULER_API_KEY (todas as rotas já validam contra ela)
        token = os.environ.get("SCHEDULER_API_KEY", "")

        logger.info(f"Login successful: {email} -> {user['clinic_id']}")

        return http_response(200, {
            "status": "SUCCESS",
            "token": token,
            "clinic_id": user["clinic_id"],
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
