# -*- coding: utf-8 -*-
"""Grava o estagio no lead e a transicao no log (PRD 057).

Um lugar so para as duas escritas, porque esquecer o evento e silencioso.
`lead_stage_events` e append-only e ninguem le daqui nesta entrega: existe para
que o funil e a taxa de erro do classificador tenham historico desde o dia 1.
"""
import logging
from datetime import datetime
from typing import Optional

from src.services.estagio_do_lead import Decisao, MANUAL

logger = logging.getLogger(__name__)


def _evento(db, lead: dict, para: str, fonte: str, motivo: Optional[str], usuario_id: Optional[str]) -> None:
    db.execute_write(
        """
        INSERT INTO scheduler.lead_stage_events (clinic_id, lead_id, de, para, fonte, motivo, usuario_id)
        VALUES (%s, %s::uuid, %s, %s, %s, %s, %s::uuid)
        """,
        (lead["clinic_id"], str(lead["id"]), lead.get("stage"), para, fonte, motivo, usuario_id),
    )


def grava_estagio(db, lead: dict, decisao: Decisao, usuario_id: Optional[str] = None,
                  ultima_em: Optional[datetime] = None, ultima_de: Optional[str] = None) -> bool:
    """True se gravou (stage ou motivo mudou). Sempre atualiza ultima_mensagem_*."""
    # Decisao MANUAL vinda da regra (mantem o que esta) nao traz motivo: o que
    # ja esta gravado fica. Um motivo novo so chega por correcao manual (PATCH).
    if decisao.reason is not None:
        motivo = decisao.reason or None
    elif decisao.source == MANUAL or decisao.stage == lead.get("stage"):
        motivo = lead.get("stage_reason")
    else:
        motivo = None
    mudou = decisao.stage != lead.get("stage") or (motivo or None) != (lead.get("stage_reason") or None)
    if mudou:
        db.execute_write(
            """
            UPDATE scheduler.leads
               SET stage = %s, stage_reason = %s, stage_source = %s, stage_updated_at = NOW(),
                   ultima_mensagem_em = %s, ultima_mensagem_de = %s, updated_at = NOW()
             WHERE id = %s::uuid
            """,
            (decisao.stage, motivo, decisao.source, ultima_em, ultima_de, str(lead["id"])),
        )
        _evento(db, lead, decisao.stage, decisao.source, motivo, usuario_id)
        return True
    db.execute_write(
        "UPDATE scheduler.leads SET ultima_mensagem_em = %s, ultima_mensagem_de = %s WHERE id = %s::uuid",
        (ultima_em, ultima_de, str(lead["id"])),
    )
    return False


def registra_tentativa(db, lead: dict, motivo: str) -> None:
    """Desfecho que voltou AINDA_ABERTO: nada muda no lead, mas fica o rastro."""
    _evento(db, lead, lead.get("stage") or "", "MODELO", motivo, None)


def marca_triagem(db, lead_id: str) -> None:
    db.execute_write("UPDATE scheduler.leads SET triagem_feita_em = NOW() WHERE id = %s::uuid", (lead_id,))


def marca_desfecho_tentado(db, lead_id: str) -> None:
    db.execute_write("UPDATE scheduler.leads SET desfecho_tentado_em = NOW() WHERE id = %s::uuid", (lead_id,))
