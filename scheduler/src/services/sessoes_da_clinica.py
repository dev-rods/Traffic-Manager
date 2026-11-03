# -*- coding: utf-8 -*-
"""Todas as sessoes de uma clinica, de uma vez.

Separado de `session_store` de proposito: aquele modulo e importado pelo
webhook e pelo envio, cujas roles nao tem `dynamodb:Query` (o teste de
permissoes varre os modulos importados). So a lista de conversas do painel
precisa disto (PRD 031).
"""
import logging

logger = logging.getLogger(__name__)


def carrega_sessoes_da_clinica(clinic_id: str, table=None) -> dict:
    """{telefone: sessao} de todas as conversas da clinica. Nunca levanta.

    Uma query so, pela chave da clinica; so os itens PHONE# (os LID# sao
    vinculos, nao conversas). E o que a lista de conversas do painel usa para
    dizer por que o bot esta calado em cada uma (PRD 031).
    """
    import os

    import boto3
    from boto3.dynamodb.conditions import Key

    try:
        table = table or boto3.resource("dynamodb").Table(
            os.environ["CONVERSATION_SESSIONS_TABLE"]
        )
        sessoes = {}
        kwargs = {"KeyConditionExpression": Key("pk").eq(f"CLINIC#{clinic_id}")}
        while True:
            resposta = table.query(**kwargs)
            for item in resposta.get("Items", []):
                sk = str(item.get("sk") or "")
                if not sk.startswith("PHONE#"):
                    continue
                sessoes[sk[len("PHONE#"):]] = dict(item.get("session") or {})
            ultima = resposta.get("LastEvaluatedKey")
            if not ultima:
                return sessoes
            kwargs["ExclusiveStartKey"] = ultima
    except Exception as e:
        logger.error(f"[SessionStore] Falha ao ler sessoes de {clinic_id}: {e}")
        return {}
