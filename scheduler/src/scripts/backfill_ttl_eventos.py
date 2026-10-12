# -*- coding: utf-8 -*-
"""Backfill do `ttl` nos eventos de mensagem que nasceram antes do PRD 022.

    python -X utf8 src/scripts/backfill_ttl_eventos.py prod            # so conta
    python -X utf8 src/scripts/backfill_ttl_eventos.py prod --aplicar  # grava

Idempotente: so toca item sem `ttl`, e a escrita e condicional
(`attribute_not_exists(ttl)`), entao rodar duas vezes, ou em corrida com o
tracker, nao sobrescreve nada. `ttl = createdAt + HISTORICO_DO_PAINEL`; item
que ja passou disso recebe `agora + 1 dia`, para o DynamoDB apagar no proximo
ciclo em vez de ficar com um `ttl` no passado remoto.
"""
import calendar
import sys
import time

import boto3
from boto3.dynamodb.conditions import Attr

from src.services import retencao


def _epoch(iso: str) -> int:
    return calendar.timegm(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))


def main(stage: str, aplicar: bool) -> None:
    tabela = boto3.resource("dynamodb").Table(f"clinic-scheduler-infra-{stage}-message-events")
    agora = int(time.time())
    vistos = gravados = ja_vencidos = ilegiveis = 0
    chave = None
    while True:
        args = {"FilterExpression": Attr("ttl").not_exists(),
                "ProjectionExpression": "pk, sk, createdAt"}
        if chave:
            args["ExclusiveStartKey"] = chave
        pagina = tabela.scan(**args)
        for item in pagina.get("Items", []):
            vistos += 1
            try:
                criado = _epoch(item.get("createdAt") or "")
            except (ValueError, TypeError):
                # STATUS# com ano 58200 (bug antigo de ms vs s): lixo, some
                # no proximo ciclo.
                ilegiveis += 1
                criado = 0
            ttl = retencao.ttl_do_evento(criado)
            if ttl <= agora:
                ja_vencidos += 1
                ttl = agora + retencao.DIA
            if aplicar:
                try:
                    tabela.update_item(
                        Key={"pk": item["pk"], "sk": item["sk"]},
                        UpdateExpression="SET #ttl = :ttl",
                        ConditionExpression="attribute_not_exists(#ttl)",
                        ExpressionAttributeNames={"#ttl": "ttl"},
                        ExpressionAttributeValues={":ttl": ttl},
                    )
                    gravados += 1
                except tabela.meta.client.exceptions.ConditionalCheckFailedException:
                    pass
        chave = pagina.get("LastEvaluatedKey")
        if not chave:
            break
    print(f"{stage}: sem ttl={vistos} | ja alem dos 60 dias={ja_vencidos} | createdAt ilegivel={ilegiveis} | "
          f"{'gravados=' + str(gravados) if aplicar else 'nada gravado (use --aplicar)'}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("dev", "prod"):
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], "--aplicar" in sys.argv)
