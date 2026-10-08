# -*- coding: utf-8 -*-
"""Tarefa humana: o que uma pessoa precisa fazer numa conversa que o bot entregou.

A fila do painel (PR #88) mostra CONVERSAS; uma tarefa é diferente: tem dono
implícito, tem estado (aberta/fechada) e não some quando o prazo do
atendimento humano vence. É o que impede `HUMAN_PENDING` de virar conversa
esquecida com cara de resolvida (PRD 020 §3.6 e §9.4).

Nasce no handoff do bot, com a intenção que ele não conseguiu atender. Fecha
pelo painel, e fechar é o que devolve a conversa ao cooldown.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

ABERTA = "OPEN"
FECHADA = "CLOSED"


def abre(db, clinic_id: str, phone: str, intent: str, motivo: str) -> Optional[str]:
    """Cria a tarefa e devolve o id. Uma aberta por conversa: se já houver,
    devolve a existente. Nunca levanta: falhar aqui não pode derrubar o handoff."""
    try:
        existente = db.execute_query(
            "SELECT id FROM scheduler.tarefas WHERE clinic_id = %s AND phone = %s AND status = %s "
            "ORDER BY aberta_em DESC LIMIT 1",
            (clinic_id, phone, ABERTA),
        )
        if existente:
            return str(existente[0]["id"])
        linhas = db.execute_query(
            "INSERT INTO scheduler.tarefas (clinic_id, phone, intent, motivo) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (clinic_id, phone, (intent or motivo or "")[:40], (motivo or "")[:40]),
        )
        return str(linhas[0]["id"]) if linhas else None
    except Exception as e:
        logger.error(f"[Tarefas] Falha ao abrir tarefa de {phone}: {e}")
        return None


def abertas(db, clinic_id: str) -> List[Dict]:
    try:
        return db.execute_query(
            "SELECT id::text, phone, intent, motivo, aberta_em FROM scheduler.tarefas "
            "WHERE clinic_id = %s AND status = %s ORDER BY aberta_em",
            (clinic_id, ABERTA),
        ) or []
    except Exception as e:
        logger.error(f"[Tarefas] Falha ao listar tarefas de {clinic_id}: {e}")
        return []


def fecha(db, clinic_id: str, tarefa_id: str, por: str = "") -> Optional[Dict]:
    """Fecha e devolve {phone} para o chamador mover a conversa. None se não achou."""
    try:
        linhas = db.execute_query(
            "UPDATE scheduler.tarefas SET status = %s, fechada_em = NOW(), fechada_por = %s "
            "WHERE id = %s::uuid AND clinic_id = %s AND status = %s RETURNING phone",
            (FECHADA, por[:100], tarefa_id, clinic_id, ABERTA),
        )
        return {"phone": linhas[0]["phone"]} if linhas else None
    except Exception as e:
        logger.error(f"[Tarefas] Falha ao fechar tarefa {tarefa_id}: {e}")
        return None
