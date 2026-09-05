# -*- coding: utf-8 -*-
"""Espelha a lista de conversas do WhatsApp para o banco.

Existe porque o atendimento humano é invisível para o webhook. A atendente
responde pelo celular, a mensagem chega com LID sem vínculo e é descartada; se a
pessoa nunca falou com o bot, não há INBOUND nenhum. Medido em 05/09/2026 na
Essência: 27 dos 37 leads do site tinham conversa no WhatsApp e o painel
mostrava 10.

O que vem daqui é presença e recência - "existe conversa, a última mensagem foi
tal dia". NÃO vem o conteúdo nem quem falou: `GET /chat-messages/{phone}`
devolve 400 "Does not work in multi device version" nesta instância.

Por isso "tem conversa" e "respondeu" continuam separados. `conversation_started_at`
segue significando que a PESSOA escreveu para nós, que é o que sustenta a taxa
de resposta. Fundir os dois faria o número de conversão mentir.
"""
import logging
from datetime import datetime, timezone

from src.utils.phone import normalize_phone

logger = logging.getLogger(__name__)


def _momento(ms):
    """`lastMessageTime` vem em milissegundos, às vezes zerado ou ausente."""
    try:
        valor = int(ms or 0)
    except (TypeError, ValueError):
        return None
    if valor <= 0:
        return None
    return datetime.fromtimestamp(valor / 1000, tz=timezone.utc)


def linhas_do_zapi(chats):
    """Converte o retorno do z-api nas linhas da tabela, sem grupo nem lixo.

    Grupo não é lead. Conversa sem telefone (só LID) não tem como casar com
    ninguém e viraria linha órfã.
    """
    linhas, vistos = [], set()
    for chat in chats or []:
        if chat.get("isGroup") in (True, "true"):
            continue
        telefone = normalize_phone(str(chat.get("phone") or ""))
        if not telefone or len(telefone) < 12:
            continue
        if telefone in vistos:
            continue
        vistos.add(telefone)
        linhas.append({
            "phone": telefone,
            "lid": (chat.get("lid") or "")[:50] or None,
            "name": (chat.get("name") or "")[:255] or None,
            "last_message_at": _momento(chat.get("lastMessageTime")),
            "unread_count": int(chat.get("messagesUnread") or 0),
        })
    return linhas


def grava(db, clinic_id, linhas):
    """Regrava o espelho da clínica.

    Uma transação: apaga e insere. O z-api é a fonte, então divergir dele não
    tem valor - e um espelho meio velho meio novo seria pior que nenhum.

    Sem linha nenhuma o espelho NÃO é apagado: chats vazio quase sempre é
    instância desconectada ou erro de API, e zerar apagaria informação boa por
    causa de uma falha passageira.
    """
    if not linhas:
        logger.warning(
            f"[SyncConversas] {clinic_id}: z-api devolveu 0 conversas, "
            f"mantendo o espelho anterior"
        )
        return 0

    db.execute_write("DELETE FROM scheduler.whatsapp_chats WHERE clinic_id = %s",
                     (clinic_id,))
    for linha in linhas:
        db.execute_write(
            """
            INSERT INTO scheduler.whatsapp_chats
                (clinic_id, phone, lid, name, last_message_at, unread_count, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (clinic_id, phone) DO UPDATE SET
                lid = EXCLUDED.lid,
                name = EXCLUDED.name,
                last_message_at = EXCLUDED.last_message_at,
                unread_count = EXCLUDED.unread_count,
                synced_at = NOW()
            """,
            (clinic_id, linha["phone"], linha["lid"], linha["name"],
             linha["last_message_at"], linha["unread_count"]),
        )
    logger.info(f"[SyncConversas] {clinic_id}: {len(linhas)} conversas espelhadas")
    return len(linhas)


def sincroniza(db, clinic, provider):
    """Puxa e grava. Devolve quantas conversas foram espelhadas."""
    clinic_id = clinic["clinic_id"]
    try:
        chats = provider.list_chats()
    except Exception as e:
        logger.error(f"[SyncConversas] {clinic_id}: falha ao listar conversas: {e}")
        return 0
    return grava(db, clinic_id, linhas_do_zapi(chats))
