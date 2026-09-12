# -*- coding: utf-8 -*-
"""Extrai conversas reais do MessageEvents para o eval de fluxo replayar.

O corpus fica gravado em disco de proposito. Duas razoes:

  1. Comparabilidade. O eval so serve para aprovar mudanca de prompt ou de
     modelo se a entrada for a MESMA entre execucoes. Corpus lido do DynamoDB
     a cada rodada muda sozinho e a nota deixa de significar nada.
  2. Custo. A tabela e dominada por STATUS_UPDATE (95% da amostra); varrer
     tudo a cada eval e caro e lento.

O que vira caso de teste: a sequencia de mensagens INBOUND de uma conversa, na
ordem em que a pessoa escreveu. O que o bot respondeu NAO entra - o eval mede o
que o agente faz hoje, nao reproduz o que ele fez.

    python -X utf8 tests/evaluation/corpus_conversas.py --atualizar
    python -X utf8 tests/evaluation/corpus_conversas.py            # so mostra
"""
import argparse
import json
import os
import re
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, RAIZ)

TABELA = "clinic-scheduler-infra-prod-message-events"
PERFIL = "dev-andre"
CLINICA = "clinicaessenciaestetica-9668a4"
DESTINO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus", "conversas.json")

# Gatilhos sinteticos nao sao fala de ninguem e a pre-carga os ignora - deixa-los
# no corpus mediria um caminho que o eval nao quer medir.
GATILHOS = ("__INICIAR_CONVERSA__", "__RETOMAR_CONVERSA__")

MIN_TURNOS = 2   # conversa de um turno so nao exercita memoria nem contexto
MAX_TURNOS = 12  # conversa longa demais estoura custo por caso sem ganho


def _anonimiza(texto):
    """Tira o que identifica a pessoa. O corpus vai para o repositorio."""
    texto = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "<CPF>", texto)
    texto = re.sub(r"\S+@\S+\.\S+", "<EMAIL>", texto)
    texto = re.sub(r"\b\d{2}\s?9?\d{4}[-\s]?\d{4}\b", "<TELEFONE>", texto)
    return texto


def baixa(limite_itens):
    import boto3

    tabela = boto3.Session(profile_name=PERFIL, region_name="us-east-1") \
        .resource("dynamodb").Table(TABELA)

    kwargs = dict(
        FilterExpression="begins_with(pk, :p) AND direction = :d",
        ExpressionAttributeValues={":p": f"CLINIC#{CLINICA}#PHONE#", ":d": "INBOUND"},
    )
    r = tabela.scan(**kwargs)
    itens = r.get("Items", [])
    while "LastEvaluatedKey" in r and len(itens) < limite_itens:
        r = tabela.scan(ExclusiveStartKey=r["LastEvaluatedKey"], **kwargs)
        itens += r.get("Items", [])
    return itens


def monta_conversas(itens):
    por_conversa = {}
    for i in itens:
        conteudo = (i.get("content") or "").strip()
        if not conteudo or conteudo in GATILHOS:
            continue
        por_conversa.setdefault(i["pk"], []).append(
            (str(i.get("createdAt") or ""), conteudo)
        )

    conversas = []
    for indice, (pk, turnos) in enumerate(sorted(por_conversa.items())):
        turnos.sort()
        mensagens = [_anonimiza(t) for _, t in turnos][:MAX_TURNOS]
        if len(mensagens) < MIN_TURNOS:
            continue
        conversas.append({
            # Identificador estavel e anonimo: o telefone nao vai para o repo.
            "id": f"conversa-{indice:03d}",
            "turnos": mensagens,
        })
    return conversas


def carrega():
    """O corpus gravado. Levanta se nao existir - eval sem corpus nao tem nota."""
    if not os.path.exists(DESTINO):
        raise SystemExit(
            f"Corpus ausente em {DESTINO}.\n"
            "Rode: python -X utf8 tests/evaluation/corpus_conversas.py --atualizar"
        )
    with open(DESTINO, encoding="utf-8") as f:
        return json.load(f)["conversas"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atualizar", action="store_true", help="rebaixa do DynamoDB e grava")
    ap.add_argument("--itens", type=int, default=4000)
    args = ap.parse_args()

    if args.atualizar:
        itens = baixa(args.itens)
        conversas = monta_conversas(itens)
        os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
        with open(DESTINO, "w", encoding="utf-8", newline="") as f:
            json.dump({"conversas": conversas}, f, ensure_ascii=False, indent=2)
        print(f"{len(itens)} eventos INBOUND -> {len(conversas)} conversas gravadas")
        print(f"destino: {DESTINO}")
    else:
        conversas = carrega()

    turnos = sum(len(c["turnos"]) for c in conversas)
    print(f"\ncorpus: {len(conversas)} conversas, {turnos} turnos")
    for c in conversas[:3]:
        print(f"\n  {c['id']} ({len(c['turnos'])} turnos)")
        for t in c["turnos"][:4]:
            print(f"    - {t[:70]!r}")


if __name__ == "__main__":
    main()
