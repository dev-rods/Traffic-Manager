"""
Lambda handler to create/capture a lead (landing page or external form).

POST /leads
Body: {
    "clinicId": "string (required)",
    "phone": "string (required)",
    "name": "string (required)",
    "email": "string (optional)",
    "gclid": "string (optional, Google Click Identifier from the ad URL)",
    "source": "string (optional, default: 'landing-page')",
    "metadata": {} (optional)
}

Observabilidade: cada etapa loga com o prefixo `[CreateLead][req:<awsRequestId>]`
para correlacionar uma submissão da landing page ponta-a-ponta no CloudWatch.
PII (telefone/email) é sempre mascarada nos logs.
"""
import logging
import os
import time
from datetime import datetime, date, time as dtime, timedelta, timezone
from decimal import Decimal

import psycopg2

from src.utils.http import http_response, require_intake_api_key, parse_body
from src.services.db.postgres import PostgresService
from src.services.lead_service import LeadService, normalize_first_name
from src.utils.phone import normalize_phone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Read-back após o commit: confirma que a linha está visível numa query nova
# (transforma "não salvou" em fato verificável). Desligue com LEADS_VERIFY_WRITE=false.
VERIFY_WRITE = os.environ.get("LEADS_VERIFY_WRITE", "true").strip().lower() not in ("0", "false", "no")


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, dtime)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def _mask_phone(phone):
    if not phone:
        return None
    digits = str(phone)
    if len(digits) <= 8:
        return f"***{digits[-2:]}"
    return f"{digits[:4]}{'*' * (len(digits) - 8)}{digits[-4:]}"


def _mask_email(email):
    if not email or "@" not in str(email):
        return None
    local, _, domain = str(email).partition("@")
    return f"{local[:1]}***@{domain}"


def _mask_key(api_key):
    if not api_key:
        return None
    return f"{api_key[:6]}...(len={len(api_key)})"


def _db_target():
    """Destino real do banco conforme as env vars da Lambda (sem senha).

    É o log mais importante quando "a request funciona mas o lead não aparece":
    mostra se esta Lambda está escrevendo no Supabase que você está olhando.
    """
    return (
        f"host={os.environ.get('RDS_HOST')} port={os.environ.get('RDS_PORT', '5432')} "
        f"db={os.environ.get('RDS_DATABASE')} user={os.environ.get('RDS_USERNAME')} "
        f"password_set={bool(os.environ.get('RDS_PASSWORD'))}"
    )


def _log_pg_error(prefix, exc):
    """Detalha erros do Postgres — pgcode/pgerror explicam a causa real.

    Ex.: 42P10 = ON CONFLICT sem constraint UNIQUE correspondente (migration
    não rodada no banco de prod); 42703 = coluna inexistente; 42P01 = tabela
    inexistente; 28P01 = senha inválida; 3D000 = database inexistente.
    """
    diag = getattr(exc, "diag", None)
    logger.error(
        f"{prefix} Erro Postgres: pgcode={getattr(exc, 'pgcode', None)} "
        f"message={getattr(diag, 'message_primary', None)} detail={getattr(diag, 'message_detail', None)} "
        f"hint={getattr(diag, 'message_hint', None)} table={getattr(diag, 'table_name', None)} "
        f"constraint={getattr(diag, 'constraint_name', None)} raw={str(exc).strip()}"
    )


SOURCES_COM_CONTATO_ATIVO = {"landing-page"}

# Janela máxima entre a criação do lead e o disparo. É a guarda que impede que
# qualquer reprocessamento ou backfill dispare mensagem para lead antigo: mesmo
# que created_at == updated_at, um lead de horas atrás não é abordado.
IDADE_MAXIMA_MINUTOS = 10


def should_start_conversation(lead, clinic, *, agora=None) -> bool:
    """O bot deve abrir conversa com este lead?

    Quatro guardas independentes, todas precisam passar. A mensagem chega no
    WhatsApp de uma pessoa real e não tem desfazer, e há 44 leads cadastrados
    com conversa em andamento que jamais podem ser abordados por engano.
    """
    if not lead or not clinic:
        return False

    if lead.get("source") not in SOURCES_COM_CONTATO_ATIVO:
        return False

    if not lead.get("phone"):
        return False

    # Lead recorrente cai em UPDATE no upsert: não é primeiro contato.
    if lead.get("created_at") != lead.get("updated_at"):
        return False

    criado = lead.get("created_at")
    if criado is None:
        return False
    if criado.tzinfo is None:
        criado = criado.replace(tzinfo=timezone.utc)
    referencia = agora or datetime.now(timezone.utc)
    if referencia - criado > timedelta(minutes=IDADE_MAXIMA_MINUTOS):
        return False

    from src.services.bot_policy import should_bot_reply

    # A sessão ainda não existe: é ela que este disparo vai criar. Passamos
    # bot_enabled=True porque a origem landing-page já foi conferida acima, e é
    # exatamente isso que a política LEADS_ONLY exige da conversa.
    return should_bot_reply(clinic, {"bot_enabled": True}, lead["phone"])


def _enfileira_contato_ativo(log_prefix, db, lead, clinic_id):
    """Enfileira a abertura de conversa. Nunca propaga erro: capturar o lead vale mais."""
    try:
        clinics = db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            logger.warning(f"{log_prefix} Clínica {clinic_id} não encontrada, sem contato ativo")
            return
        clinic = clinics[0]

        if not should_start_conversation(lead, clinic):
            logger.info(
                f"{log_prefix} Contato ativo não elegível: source={lead.get('source')!r} "
                f"policy={clinic.get('bot_autoreply_policy') or 'ALL'}"
            )
            return

        from src.services.outbound_queue import OutboundQueueService

        item = OutboundQueueService().enqueue(
            clinic_id,
            lead["phone"],
            lead_id=str(lead["id"]),
            business_hours=clinic.get("business_hours") or {},
        )
        if item:
            db.execute_query(
                "UPDATE scheduler.leads SET first_contact_status = 'QUEUED', updated_at = NOW() "
                "WHERE id = %s::uuid",
                (str(lead["id"]),),
            )
            logger.info(
                f"{log_prefix} Contato ativo enfileirado: {item['messageId']} "
                f"sai a partir de {item['sendAfter']}"
            )
    except Exception as e:
        logger.error(f"{log_prefix} Falha ao enfileirar contato ativo: {e}", exc_info=True)


def handler(event, context):
    request_id = getattr(context, "aws_request_id", "local")
    log_prefix = f"[CreateLead][req:{request_id}]"
    started_at = time.time()

    def elapsed_ms():
        return int((time.time() - started_at) * 1000)

    try:
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        request_context = event.get("requestContext") or {}
        raw_body = event.get("body")

        logger.info(
            f"{log_prefix} Request recebida: stage={os.environ.get('STAGE')} "
            f"sourceIp={(request_context.get('identity') or {}).get('sourceIp')} "
            f"origin={headers.get('origin')} referer={headers.get('referer')} "
            f"contentType={headers.get('content-type')} userAgent={headers.get('user-agent')} "
            f"rawBodyLen={len(raw_body) if isinstance(raw_body, str) else 'n/a'} "
            f"isBase64={event.get('isBase64Encoded')}"
        )
        logger.info(f"{log_prefix} Banco de destino: {_db_target()}")

        body = parse_body(event)
        if raw_body and body is None:
            logger.error(
                f"{log_prefix} Falha ao parsear o body (JSON inválido ou tipo inesperado). "
                f"raw[:500]={str(raw_body)[:500]!r}"
            )

        api_key, error_response = require_intake_api_key(event, body)
        if error_response:
            provided = headers.get("x-api-key") or headers.get("authorization")
            logger.warning(
                f"{log_prefix} 401 Não autorizado: keyRecebida={_mask_key(provided)} "
                f"viaHeader={'x-api-key' in headers} viaAuthorization={'authorization' in headers} "
                f"intakeKeyConfigurada={bool(os.environ.get('LEADS_INTAKE_API_KEY'))} "
                f"masterKeyConfigurada={bool(os.environ.get('SCHEDULER_API_KEY'))} ({elapsed_ms()}ms)"
            )
            return error_response

        matched = "intake" if api_key == os.environ.get("LEADS_INTAKE_API_KEY") else "master"
        logger.info(f"{log_prefix} Autorizado com a chave: {matched}")

        if not body:
            logger.warning(f"{log_prefix} 400 Body ausente/vazio ({elapsed_ms()}ms)")
            return http_response(400, {"status": "ERROR", "message": "Request body e obrigatorio"})

        logger.info(
            f"{log_prefix} Payload: keys={sorted(body.keys())} clinicId={body.get('clinicId')!r} "
            f"phone={_mask_phone(body.get('phone'))} name={body.get('name')!r} "
            f"email={_mask_email(body.get('email'))} gclid={body.get('gclid')!r} "
            f"source={body.get('source')!r} metadataKeys={sorted((body.get('metadata') or {}).keys()) if isinstance(body.get('metadata'), dict) else type(body.get('metadata')).__name__}"
        )

        missing = [f for f in ("clinicId", "phone", "name") if not body.get(f)]
        if missing:
            logger.warning(f"{log_prefix} 400 Campos obrigatórios ausentes: {missing} ({elapsed_ms()}ms)")
            return http_response(400, {
                "status": "ERROR",
                "message": f"Campos obrigatorios ausentes: {', '.join(missing)}",
            })

        # Identidade derivada (clinic_id + phone normalizado + first_name):
        # logada porque um phone/nome normalizado diferente do esperado faz o
        # upsert cair em UPDATE de outra linha em vez de INSERT.
        normalized_phone = normalize_phone(body["phone"])
        first_name = normalize_first_name(body["name"])
        logger.info(
            f"{log_prefix} Identidade do lead: clinic={body['clinicId']} "
            f"phoneNormalizado={_mask_phone(normalized_phone)} (len={len(normalized_phone or '')}) "
            f"firstName={first_name!r}"
        )

        connect_started = time.time()
        db = PostgresService()
        health = db.health_check()
        logger.info(
            f"{log_prefix} Conexão com o banco: {health} "
            f"({int((time.time() - connect_started) * 1000)}ms)"
        )
        if health.get("status") != "healthy":
            logger.error(f"{log_prefix} Banco indisponível — o INSERT não vai acontecer. {_db_target()}")

        lead_service = LeadService(db)

        write_started = time.time()
        lead = lead_service.upsert_lead(
            clinic_id=body["clinicId"],
            phone=body["phone"],
            source=body.get("source", "landing-page"),
            name=body["name"],
            email=body.get("email"),
            gclid=body.get("gclid"),
            metadata=body.get("metadata"),
        )
        write_ms = int((time.time() - write_started) * 1000)

        if not lead:
            # RETURNING vazio: o ON CONFLICT DO UPDATE não retornou linha
            # (ex.: conflito em outra constraint) — nada foi persistido.
            logger.error(
                f"{log_prefix} upsert_lead retornou None — nenhuma linha persistida. "
                f"clinic={body['clinicId']} phone={_mask_phone(normalized_phone)} firstName={first_name!r} "
                f"({write_ms}ms)"
            )
        else:
            created_at = lead.get("created_at")
            updated_at = lead.get("updated_at")
            operation = "INSERT (lead novo)" if created_at == updated_at else "UPDATE (lead já existia)"
            logger.info(
                f"{log_prefix} upsert_lead OK — {operation}: id={lead.get('id')} "
                f"clinic={lead.get('clinic_id')} phone={_mask_phone(lead.get('phone'))} "
                f"firstName={lead.get('first_name')!r} gclid={lead.get('gclid')!r} "
                f"source={lead.get('source')!r} booked={lead.get('booked')} "
                f"createdAt={created_at} updatedAt={updated_at} ({write_ms}ms)"
            )

            if VERIFY_WRITE:
                verify = db.execute_query(
                    "SELECT id, created_at, updated_at FROM scheduler.leads WHERE id = %s::uuid",
                    (str(lead["id"]),),
                )
                if verify:
                    logger.info(
                        f"{log_prefix} Read-back pós-commit OK: linha visível no banco "
                        f"id={verify[0]['id']} createdAt={verify[0]['created_at']}"
                    )
                else:
                    logger.error(
                        f"{log_prefix} Read-back pós-commit FALHOU: id={lead.get('id')} não encontrado "
                        f"após o commit — escrita revertida ou banco/schema diferente do lido. {_db_target()}"
                    )

        if lead:
            _enfileira_contato_ativo(log_prefix, db, lead, body["clinicId"])

        logger.info(f"{log_prefix} 201 Lead registrado ({elapsed_ms()}ms total)")
        return http_response(201, {
            "status": "SUCCESS",
            "message": "Lead registrado com sucesso",
            "lead": _serialize_row(lead) if lead else None,
        })

    except psycopg2.Error as e:
        _log_pg_error(log_prefix, e)
        logger.error(f"{log_prefix} 500 Falha de banco ao criar lead ({elapsed_ms()}ms). {_db_target()}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})

    except Exception as e:
        logger.error(
            f"{log_prefix} 500 Erro ao criar lead: {type(e).__name__}: {e} ({elapsed_ms()}ms)",
            exc_info=True,
        )
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
