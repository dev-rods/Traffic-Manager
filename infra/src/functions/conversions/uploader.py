"""
Lambda semanal: leva agendamentos reais ao Google Ads, e desfaz os cancelados.

Roda toda segunda, 7h BRT. Para cada clinica mapeada a uma conta do Google Ads,
faz duas coisas:

1. SOBE como ClickConversion todo agendamento CONFIRMED ligado a um lead com
   gclid, dentro da janela de 90 dias do clique e ainda nao enviado. A sessao
   NAO precisa ter acontecido: a conversao comercial e o agendamento, e segurar
   o sinal ate a sessao atrasava o aprendizado do Google em semanas.

2. ZERA O VALOR do que subiu e depois foi cancelado. Era para ser RETRATAR,
   mas a Data Manager API nao tem retratacao (ver `data_manager_service.py`):
   o valor vai a zero, a CONTAGEM permanece. Como a campanha otimiza por
   contagem, isto corrige relatorio e ROAS mas NAO remove o sinal ruim do
   Smart Bidding. Na Essencia isso nao e marginal: 42% dos agendamentos
   vindos de anuncio sao cancelados. Decisao pendente do Andre: voltar a so
   subir depois da sessao acontecer e a unica correcao real.

Recorrente por desenho: cada agendamento e uma conversao propria, entao o
retorno acumulado de uma paciente que volta flui para o Google ao longo do
tempo.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import boto3

from src.services.postgres_service import PostgresService
from src.services.data_manager_service import (
    DataManagerService,
    MAX_EVENTOS_POR_REQUISICAO,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

# Limite da Data Manager API. Vem de la para nao divergir em silencio.
UPLOAD_CHUNK_SIZE = MAX_EVENTOS_POR_REQUISICAO
_SP_TZ = ZoneInfo("America/Sao_Paulo")


def _format_conversion_dt(conv_dt: datetime) -> str:
    """Formata em ISO 8601 no fuso da clinica (BRT): "...THH:MM:SS-03:00".

    conversion_date e TIMESTAMPTZ; o psycopg2 devolve tz-aware (UTC no Supabase).
    Converte para America/Sao_Paulo e usa o offset real, em vez de carimbar
    -03:00 sobre a hora UTC (o que deslocaria toda conversao).

    O separador e "T", e nao espaco. O Google Ads API antigo aceitava
    "YYYY-MM-DD HH:MM:SS-03:00"; a Data Manager pede ISO 8601 estrito. Trocar
    de API sem trocar o separador faria todo evento ser recusado, e a mensagem
    de erro nao aponta para o formato.
    """
    if conv_dt.tzinfo is None:
        conv_dt = conv_dt.replace(tzinfo=timezone.utc)
    s = conv_dt.astimezone(_SP_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")  # ...-0300
    return s[:-2] + ":" + s[-2:]  # insere o ':' no offset -> -03:00


def _get_mapped_clinics(db: PostgresService):
    """Clinics that have a Google Ads account and an offline conversion action configured."""
    return db.execute_query(
        """
        SELECT clinic_id, google_ads_customer_id, offline_conversion_action_id
        FROM scheduler.clinics
        WHERE google_ads_customer_id IS NOT NULL
          AND offline_conversion_action_id IS NOT NULL
        """
    )


def _get_pending_conversions(db: PostgresService, clinic_id: str):
    """Conversoes prontas para subir: agendamento feito, dentro da janela de 90d.

    A regra mudou em 27/09/2026, por decisao do Andre. Antes havia um
    `a.appointment_date < CURRENT_DATE`: so subia depois da sessao acontecer,
    como protecao contra cancelamento.

    O custo era alto demais. A conversao comercial acontece quando a pessoa
    AGENDA, nao quando comparece, e segurar o sinal ate a sessao atrasava o
    aprendizado do Google em semanas - quem clicou hoje e marcou para daqui a
    um mes so ensinava o algoritmo um mes depois. Medido na Essencia: 3
    conversoes elegiveis contra 7 com a regra nova.

    O cancelamento passa a ser tratado onde deve: por RETRACTION, depois. Ver
    `retractions.py`.

    `conversion_date` continua sendo a data da SESSAO, nao a do agendamento -
    e o que o `record_conversion` grava. Para o Google isso e so o carimbo do
    evento; o que importa e que seja passado e dentro dos 90 dias do clique,
    e o filtro abaixo garante os dois.
    """
    return db.execute_query(
        """
        SELECT lc.id, lc.gclid, lc.value_cents,
               -- Sessao futura sobe com o carimbo de AGORA: o Google recusa
               -- data no futuro, e o momento da decisao e o agendamento.
               LEAST(lc.conversion_date, NOW()) AS conversion_date
        FROM scheduler.lead_conversions lc
        JOIN scheduler.appointments a ON a.id = lc.appointment_id
        WHERE lc.clinic_id = %s
          AND lc.uploaded_at IS NULL
          AND a.status = 'CONFIRMED'
          -- O Google recusa conversao com carimbo no futuro. Sessao marcada
          -- para daqui a duas semanas sobe com a data do AGENDAMENTO.
          AND LEAST(lc.conversion_date, NOW()) > lc.click_date
          AND lc.conversion_date <= lc.click_date + INTERVAL '90 days'
        ORDER BY lc.conversion_date ASC
        """,
        (clinic_id,),
    )


def _mark_uploaded(db: PostgresService, conversion_ids):
    if not conversion_ids:
        return
    db.execute_write(
        "UPDATE scheduler.lead_conversions SET uploaded_at = NOW() WHERE id = ANY(%s::uuid[])",
        (list(conversion_ids),),
    )


def _record_execution(trace_id: str, summary: dict):
    try:
        table_name = os.environ.get("EXECUTION_HISTORY_TABLE")
        if not table_name:
            return
        dynamodb.Table(table_name).put_item(
            Item={
                "traceId": trace_id,
                "stageTm": "offline_conversion_upload",
                "status": "COMPLETED",
                "timestamp": datetime.utcnow().isoformat(),
                "payload": json.dumps(summary),
            }
        )
    except Exception as e:
        logger.error(f"Falha ao registrar execução: {e}")


def _get_pending_retractions(db: PostgresService, clinic_id: str):
    """Conversoes que subiram ao Google e depois foram canceladas.

    `uploaded_at IS NOT NULL` e a condicao que importa: so ha o que desfazer
    se chegou a existir. Cancelamento antes do upload nunca vira conversao -
    a query de pendentes filtra por status CONFIRMED.

    `conversion_date` volta EXATAMENTE como foi enviada (o mesmo LEAST do
    upload), porque e o par (gclid, conversion_date_time) que identifica a
    conversao no Google. Um carimbo diferente devolve CONVERSION_NOT_FOUND.
    """
    return db.execute_query(
        """
        SELECT lc.id, lc.gclid,
               LEAST(lc.conversion_date, lc.uploaded_at) AS conversion_date,
               lc.uploaded_at
        FROM scheduler.lead_conversions lc
        JOIN scheduler.appointments a ON a.id = lc.appointment_id
        WHERE lc.clinic_id = %s
          AND lc.uploaded_at IS NOT NULL
          AND lc.retracted_at IS NULL
          AND a.status = 'CANCELLED'
        ORDER BY lc.uploaded_at ASC
        """,
        (clinic_id,),
    )


def _mark_retracted(db: PostgresService, conversion_ids):
    if not conversion_ids:
        return
    db.execute_write(
        "UPDATE scheduler.lead_conversions SET retracted_at = NOW() "
        "WHERE id = ANY(%s::uuid[])",
        (list(conversion_ids),),
    )


def _zera_valor_dos_cancelados(db, dm, clinic, trace_id, validate_only=False):
    """Zera no Google o valor do que foi cancelado depois de subir.

    Era RETRACTION ate 03/10/2026. A Data Manager API nao tem retratacao, so
    restatement de valor - entao a contagem da conversao permanece e o Smart
    Bidding segue vendo o evento. Ver `restate_cancelled_to_zero`.
    """
    clinic_id = clinic["clinic_id"]
    pendentes = _get_pending_retractions(db, clinic_id)
    if not pendentes:
        return {"pending": 0, "retracted": 0, "failed": 0, "errors": None}

    itens = [
        {
            # O transactionId tem de ser O MESMO usado no upload, senao a Data
            # Manager cria uma conversao nova em vez de ajustar a original -
            # dobrando o estrago em vez de corrigi-lo. `lc.id` nas duas pontas.
            "identifier": str(row["id"]),
            "gclid": row["gclid"],
            "conversion_date_time": _format_conversion_dt(row["conversion_date"]),
            "conversion_value": 0.0,
        }
        for row in pendentes
    ]

    retratadas = 0
    falhas = 0
    erros = []
    for start in range(0, len(itens), UPLOAD_CHUNK_SIZE):
        chunk = itens[start:start + UPLOAD_CHUNK_SIZE]
        resultado = dm.restate_cancelled_to_zero(
            customer_id=clinic["google_ads_customer_id"],
            conversion_action_id=clinic["offline_conversion_action_id"],
            conversions=chunk,
            login_customer_id=os.environ.get("MCC_CUSTOMER_ID"),
            validate_only=validate_only,
        )
        ids = resultado.get("retracted_identifiers", [])
        _mark_retracted(db, ids)
        retratadas += len(ids)
        falhas += resultado.get("failed", 0) if resultado.get("success") else len(chunk)
        if resultado.get("error"):
            erros.append(resultado["error"])

    logger.info(
        f"[traceId: {trace_id}] Valor zerado em {clinic_id}: "
        f"{retratadas} canceladas zeradas, {falhas} falharam"
    )
    return {
        "pending": len(pendentes),
        "retracted": retratadas,
        "failed": falhas,
        "errors": erros or None,
    }

def handler(event, context):
    trace_id = str(uuid.uuid4())

    # `validateOnly` no payload faz um ensaio: a Data Manager valida tudo e nao
    # grava nada. Nao existia no caminho antigo, e e o que permite testar em
    # producao sem queimar conversao - exatamente o que faltou em 03/10/2026,
    # quando o unico jeito de saber era enviar de verdade.
    validate_only = bool((event or {}).get("validateOnly"))

    logger.info(
        f"[traceId: {trace_id}] Iniciando upload de conversões offline"
        + (" (validateOnly: nada sera gravado)" if validate_only else "")
    )

    db = PostgresService()
    dm = DataManagerService()

    summary = {"clinics": 0, "uploaded": 0, "failed": 0,
               "retracted": 0, "retract_failed": 0, "details": []}

    clinics = _get_mapped_clinics(db)
    summary["clinics"] = len(clinics)

    for clinic in clinics:
        clinic_id = clinic["clinic_id"]
        customer_id = clinic["google_ads_customer_id"]
        conversion_action_id = clinic["offline_conversion_action_id"]

        # A retratacao roda ANTES e independente do upload: uma clinica sem
        # nada novo para subir pode ter muito o que desfazer, e o `continue`
        # abaixo pularia a clinica inteira.
        retratacao = _zera_valor_dos_cancelados(
            db, dm, clinic, trace_id, validate_only)
        summary["retracted"] += retratacao["retracted"]
        summary["retract_failed"] += retratacao["failed"]

        pending = _get_pending_conversions(db, clinic_id)
        if not pending:
            if retratacao["retracted"] or retratacao["failed"]:
                summary["details"].append({
                    "clinicId": clinic_id, "pending": 0, "uploaded": 0,
                    "failed": 0, "errors": None, "retraction": retratacao,
                })
            continue

        conversions = []
        for row in pending:
            conversions.append({
                "identifier": str(row["id"]),
                "gclid": row["gclid"],
                "conversion_date_time": _format_conversion_dt(row["conversion_date"]),
                "conversion_value": (row["value_cents"] or 0) / 100.0,
            })

        # Envia em lotes de até 2000 (limite do Google) para não estourar o request
        # inteiro num backlog grande — cada lote é marcado assim que confirmado.
        clinic_uploaded = 0
        clinic_validated = 0
        clinic_failed = 0
        errors = []
        for start in range(0, len(conversions), UPLOAD_CHUNK_SIZE):
            chunk = conversions[start:start + UPLOAD_CHUNK_SIZE]
            result = dm.ingest_offline_conversions(
                customer_id=customer_id,
                conversion_action_id=conversion_action_id,
                conversions=chunk,
                login_customer_id=os.environ.get("MCC_CUSTOMER_ID"),
                validate_only=validate_only,
            )
            uploaded_ids = result.get("uploaded_identifiers", [])
            _mark_uploaded(db, uploaded_ids)
            clinic_uploaded += len(uploaded_ids)
            # Em ensaio nada sobe, entao `uploaded` fica 0 e o resumo diria
            # "0 enviadas, 0 falhas" - que se le como se nada tivesse
            # acontecido. `validated` e o que separa um ensaio verde de uma
            # clinica sem conversao pendente.
            clinic_validated += result.get("validated", 0)
            clinic_failed += result.get("failed", 0) if result.get("success") else len(chunk)
            if result.get("error"):
                errors.append(result["error"])

        summary["uploaded"] += clinic_uploaded
        summary["failed"] += clinic_failed
        summary["details"].append({
            "clinicId": clinic_id,
            "pending": len(pending),
            "uploaded": clinic_uploaded,
            "validated": clinic_validated,
            "failed": clinic_failed,
            "errors": errors or None,
            "retraction": retratacao,
        })
        logger.info(
            f"[traceId: {trace_id}] Clínica {clinic_id}: {clinic_uploaded}/{len(pending)} enviadas"
        )

    _record_execution(trace_id, summary)
    logger.info(f"[traceId: {trace_id}] Concluído: {json.dumps(summary)}")
    return {"traceId": trace_id, "summary": summary}
