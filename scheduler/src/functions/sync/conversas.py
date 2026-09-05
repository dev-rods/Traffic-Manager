# -*- coding: utf-8 -*-
"""Espelha a lista de conversas do WhatsApp de cada clínica ativa.

Roda por cron. Frequência é troca de recência por chamadas: o custo medido em
05/09/2026 foi de 4 requisições e 6,9s para 3378 conversas, entao dinheiro nao e
o limitador - o que se escolhe e quao velha a informacao pode estar.
"""
import logging

from src.services.db.postgres import PostgresService
from src.services.sincroniza_conversas import sincroniza
from src.providers.whatsapp_provider import get_provider

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    db = PostgresService()
    clinicas = db.execute_query(
        "SELECT * FROM scheduler.clinics WHERE active = TRUE "
        "AND zapi_instance_id IS NOT NULL AND zapi_instance_id <> ''"
    )

    total, falhas = 0, []
    for clinic in clinicas:
        clinic_id = clinic["clinic_id"]
        try:
            n = sincroniza(db, clinic, get_provider(clinic))
            total += n
            if n == 0:
                falhas.append(clinic_id)
        except Exception as e:
            # Uma clínica com instância fora do ar não pode impedir as outras.
            logger.error(f"[SyncConversas] {clinic_id} falhou: {e}")
            falhas.append(clinic_id)

    logger.info(
        f"[SyncConversas] {len(clinicas)} clinicas, {total} conversas espelhadas, "
        f"{len(falhas)} sem resultado: {falhas}"
    )
    return {"status": "OK", "clinicas": len(clinicas), "conversas": total,
            "sem_resultado": falhas}
