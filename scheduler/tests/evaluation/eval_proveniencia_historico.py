# -*- coding: utf-8 -*-
"""EVALUATION: quantas respostas ja emitidas afirmaram fato sem consultar.

Roda o extrator de proveniencia contra as respostas reais do bot no
MessageEvents. Serve a dois propositos:

  1. LINHA DE BASE - quantas vezes o bot afirmou data, hora, preco ou status.
     E o numero que diz se vale ligar o bloqueio.
  2. FALSO POSITIVO - respostas de conversa comum que o extrator marca como
     fato. Se muitas saudacoes virarem "fato sensivel", o guardrail vai calar
     o bot a toa.

Nao confere contra as tools (o MessageEvents nao guarda o que foi consultado);
mede quanto da conversa CONTEM afirmacao factual. E o teto do problema.

    python -X utf8 tests/evaluation/eval_proveniencia_historico.py [--amostra N]
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "x")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "x")

from src.services.proveniencia import fatos_sensiveis  # noqa: E402

TABELA = "clinic-scheduler-infra-prod-message-events"
PERFIL = "dev-andre"
CLINICA = "clinicaessenciaestetica-9668a4"


def respostas_do_bot(limite):
    import boto3
    tabela = boto3.Session(profile_name=PERFIL, region_name="us-east-1") \
        .resource("dynamodb").Table(TABELA)
    prefixo = f"CLINIC#{CLINICA}#PHONE#"

    kwargs = dict(
        FilterExpression="begins_with(pk, :p) AND direction = :d AND #s = :st",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":p": prefixo, ":d": "OUTBOUND", ":st": "SENT"},
    )
    r = tabela.scan(**kwargs)
    itens = r.get("Items", [])
    while "LastEvaluatedKey" in r and len(itens) < limite:
        r = tabela.scan(ExclusiveStartKey=r["LastEvaluatedKey"], **kwargs)
        itens += r.get("Items", [])
    return itens[:limite]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amostra", type=int, default=2000)
    ap.add_argument("--exemplos", type=int, default=6)
    args = ap.parse_args()

    respostas = respostas_do_bot(args.amostra)
    com_fato, sem_fato = [], []
    tipos = Counter()

    for item in respostas:
        texto = (item.get("content") or "").strip()
        if not texto:
            continue
        achados = fatos_sensiveis(texto)
        if achados:
            com_fato.append((texto, achados))
            for f in achados:
                tipos["status" if f.startswith("status:")
                      else "dinheiro" if f.startswith("R$")
                      else "hora" if ":" in f and len(f) == 5
                      else "data"] += 1
        else:
            sem_fato.append(texto)

    total = len(com_fato) + len(sem_fato)
    print(f"respostas do bot analisadas: {total}")
    print(f"  COM afirmacao factual : {len(com_fato)} ({100*len(com_fato)/total:.0f}%)")
    print(f"  sem afirmacao factual : {len(sem_fato)} ({100*len(sem_fato)/total:.0f}%)")
    print(f"  tipos encontrados     : {dict(tipos)}")
    print()
    print("--- EXEMPLOS COM FATO (guardrail exigiria origem) ---")
    for texto, achados in com_fato[:args.exemplos]:
        print(f"  {sorted(achados)}")
        print(f"     {texto[:100]!r}")
    print()
    print("--- EXEMPLOS SEM FATO (guardrail nao interfere) ---")
    for texto in sem_fato[:args.exemplos]:
        print(f"     {texto[:100]!r}")


if __name__ == "__main__":
    main()
