"""Marca conversas como elegíveis para resposta automática do bot.

A sessão é gravada aninhada: o item do DynamoDB tem {"pk", "sk", "session": {...}},
e `_load_session` devolve o conteúdo de `session`. Um `SET bot_enabled` na raiz do
item seria invisível para quem lê a sessão — com a política LEADS_ONLY o bot
ficaria mudo para todo mundo, silenciosamente. Por isso a marca entra dentro de
`session`.

Lê, mescla e grava em vez de usar UpdateExpression com caminho aninhado: o
`session` pode ainda não existir, e a leitura extra é irrelevante no volume aqui
(uma abordagem a cada 10 minutos).
"""
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def mark_conversation_eligible(table, clinic_id: str, phone: str,
                               lead_id: Optional[str] = None) -> bool:
    """Marca a conversa como elegível, preservando o histórico já gravado.

    Devolve True se gravou. Nunca levanta: falhar aqui não pode derrubar o envio
    que já aconteceu.
    """
    pk, sk = f"CLINIC#{clinic_id}", f"PHONE#{phone}"
    try:
        item = table.get_item(Key={"pk": pk, "sk": sk}).get("Item") or {}
        session = item.get("session") or {}

        session["bot_enabled"] = True
        if lead_id:
            session["lead_id"] = str(lead_id)

        table.put_item(
            Item={
                "pk": pk,
                "sk": sk,
                "session": session,
                "clinicId": clinic_id,
                "phone": phone,
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()))),
            }
        )
        logger.info(f"[SessionStore] Conversa {phone} marcada como elegível")
        return True
    except Exception as e:
        logger.error(f"[SessionStore] Falha ao marcar {phone} como elegível: {e}")
        return False
