"""
Lambda mensal: leva COMPRAS ao Google Ads, e zera o valor das canceladas.

Este evento e uma COMPRA (`PURCHASE`, valor = `final_price_cents`), por decisao
do Andre em 03/10/2026. O evento de "WhatsApp qualificado" - que conta no
agendamento e INCLUI quem cancelou - sera uma conversion action separada, com
categoria propria. Dois eventos honestos em vez de um hibrido afirmando as duas
coisas.

Roda no ULTIMO DIA de cada mes, 7h BRT (era semanal, as segundas, ate
03/10/2026). Para cada clinica mapeada a uma conta do Google Ads, faz duas
coisas:

A periodicidade e afirmada em mais lugares que este, e divergir e silencioso.
Ao mudar o cron, mude tambem:

  - infra/sls/functions/conversions/interface.yml  (a FONTE: o cron de fato)
  - frontend/src/pages/leads/LeadsPage.tsx         (texto que a clinica le)
  - scheduler/src/scripts/liga_conversao_offline.py
  - scheduler/src/scripts/backfill_conversoes_perdidas.py
  - scheduler/tests/integration/lead-gclid-offline-conversions.md

1. SOBE todo agendamento CONFIRMED cuja SESSAO JA PASSOU, ligado a um lead com
   gclid, dentro da janela de 90 dias do clique e ainda nao enviado.

   Atencao ao limite: sessao passada sem cancelamento NAO e presenca
   comprovada. O scheduler nao registra comparecimento, entao um no-show entra
   aqui como compra. E o melhor proxy disponivel, nao a regra final - ver
   `_get_pending_conversions`.

2. ZERA O VALOR do que subiu e depois foi cancelado. Era para ser RETRATAR,
   mas a Data Manager API nao tem retratacao (ver `data_manager_service.py`):
   o valor vai a zero, a CONTAGEM permanece.

   Com o guard do item 1 isso virou caso de BORDA, e nao a regra: o
   cancelamento que chega antes da sessao nunca sobe. Sobra o que e cancelado
   NO DIA ou DEPOIS - metade dos cancelamentos medidos na Essencia. Para esses
   zerar o valor e tudo o que existe.

   Taxa de cancelamento medida em 03/10/2026: 33% (10 de 30 conversoes). O
   numero 42% que circulava vinha de 5 de 12, e 3 dos 10 cancelados sao
   artefato do backfill - cancelados antes de a linha existir.

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
    """Conversoes prontas para subir: sessao JA PASSOU e nao foi cancelada.

    ## Historia da regra, porque ela ja mudou duas vezes

    Ate 27/09/2026 havia `a.appointment_date < CURRENT_DATE`. Ele saiu naquele
    dia para que a conversao contasse no AGENDAMENTO: o sinal chegava semanas
    antes (mediana medida depois: 13 dias) e a `RETRACTION` seria a
    contrapartida para o cancelamento.

    Em 03/10/2026 o guard VOLTOU, por decisao do Andre, e por dois motivos
    que se somaram:

    1. O Google fechou a RETRACTION (ver `data_manager_service.py`). A
       contrapartida que sustentava o desenho de 27/09 deixou de existir: hoje
       so da para zerar o VALOR do cancelado, nao remover a conversao.
    2. A decisao de desenho passou a ser que este evento e uma COMPRA
       (`PURCHASE`, com `final_price_cents`), nao um agendamento. Enviar compra
       no momento do agendamento afirma algo que ainda nao aconteceu.

    ## O que este filtro NAO garante

    Ele nao prova comparecimento, e e importante nao confundir as duas coisas.
    `CONFIRMED` com data passada significa "ninguem cancelou" - nao "a pessoa
    veio".

    Desde 04/10/2026 existe o status NO_SHOW, e falta marcada sai daqui pelo
    `= CONFIRMED` do filtro. Mas isso **nao fecha** o problema: depende de
    alguem marcar. Enquanto a cobertura de NO_SHOW nao se provar, um no-show
    nao marcado continua entrando como compra, e o prontuario - a outra fonte
    possivel - cobre 4% das sessoes passadas.

    Medir antes de confiar: contar NO_SHOW em 60 dias. Ver PRD 016.

    Pior: metade dos cancelamentos medidos chega NO DIA ou DEPOIS da sessao,
    entao parte do que este filtro libera ainda vira cancelamento.

    Isto e portanto o melhor proxy disponivel, e nao a regra final. A regra
    final depende de registrar presenca - feature em aberto.

    `conversion_date` e a data da SESSAO, nao a do agendamento - e o que o
    `record_conversion` grava. Com o guard de volta ela e sempre passada, o que
    torna o `LEAST(..., NOW())` abaixo redundante; ele fica como cinto de
    seguranca, porque o Google recusa carimbo no futuro e a regra ja mudou duas
    vezes.
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
          -- O guard que voltou em 03/10/2026: compra so e afirmada depois de a
          -- sessao acontecer. NAO prova presenca - ver o docstring.
          --
          -- A data e a de SAO PAULO, nao `CURRENT_DATE`. O banco roda em UTC
          -- (conferido em prod), e UTC esta A FRENTE do Brasil: entre 21h e
          -- meia-noite BRT o `CURRENT_DATE` ja e o dia seguinte, e a sessao de
          -- HOJE passaria por realizada. Numa invocacao manual nessa faixa, a
          -- compra seria afirmada ao Google antes de o dia terminar.
          AND a.appointment_date < (NOW() AT TIME ZONE 'America/Sao_Paulo')::date
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
    """Conversoes que subiram ao Google e depois cairam: canceladas ou falta.

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
          -- NO_SHOW entrou em 04/10/2026: falta descoberta DEPOIS do upload
          -- precisa do mesmo tratamento que cancelamento, porque a compra que
          -- afirmamos ao Google nao aconteceu nos dois casos.
          AND a.status IN ('CANCELLED', 'NO_SHOW')
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
