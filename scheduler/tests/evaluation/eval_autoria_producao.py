# -*- coding: utf-8 -*-
"""EVALUATION: o bot nunca pode pausar a si mesmo.

Roda `foi_enviada_pelo_bot` contra o MessageEvents real de producao. Cada
mensagem que o bot enviou (tem providerMessageId) precisa ser reconhecida como
eco; se uma unica escapar, o bot se pausa por 24h logo depois de responder.

Nao e teste unitario: depende de credencial AWS e de dado real, por isso fica
fora de tests/unit e nao roda no pytest. Rodar antes de mexer na deteccao de
autoria e depois de qualquer deploy que a envolva.

    python -X utf8 tests/evaluation/eval_autoria_producao.py [--clinica ID]

Sai com codigo 1 se alguma mensagem do bot nao for reconhecida.
"""
import os
import sys
import argparse
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from src.services.autoria_mensagem import foi_enviada_pelo_bot  # noqa: E402

TABELA = "clinic-scheduler-infra-prod-message-events"
PERFIL_AWS = "dev-andre"
# Mesma janela que o webhook usa (ECO_JANELA_DE_BUSCA). Se divergir, a
# evaluation valida um cenario que nao acontece em producao.
JANELA = 20


def carrega_conversas(clinic_id):
    import boto3
    from boto3.dynamodb.conditions import Key

    tabela = boto3.Session(profile_name=PERFIL_AWS, region_name="us-east-1") \
        .resource("dynamodb").Table(TABELA)
    prefixo = f"CLINIC#{clinic_id}#PHONE#"

    r = tabela.scan(ProjectionExpression="pk", FilterExpression="begins_with(pk, :p)",
                    ExpressionAttributeValues={":p": prefixo})
    pks = {i["pk"] for i in r.get("Items", [])}
    while "LastEvaluatedKey" in r:
        r = tabela.scan(ProjectionExpression="pk", FilterExpression="begins_with(pk, :p)",
                        ExpressionAttributeValues={":p": prefixo},
                        ExclusiveStartKey=r["LastEvaluatedKey"])
        pks |= {i["pk"] for i in r.get("Items", [])}

    for pk in sorted(pks):
        eventos = tabela.query(KeyConditionExpression=Key("pk").eq(pk),
                               ScanIndexForward=False, Limit=200)["Items"]
        yield pk.split("#")[-1], list(reversed(eventos))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clinica", default="clinicaessenciaestetica-9668a4")
    args = ap.parse_args()

    total = reconhecidas = falhas = humanas = 0
    exemplos_falha = []
    por_conversa = Counter()

    for telefone, eventos in carrega_conversas(args.clinica):
        do_bot = [e for e in eventos if e.get("direction") == "OUTBOUND"
                  and (e.get("providerMessageId") or "").strip()]
        humanas += len([e for e in eventos if e.get("direction") == "OUTBOUND"
                        and e.get("status") == "SENT"
                        and not (e.get("providerMessageId") or "").strip()])

        for indice, evento in enumerate(eventos):
            if evento not in do_bot:
                continue
            total += 1
            pid = evento["providerMessageId"]
            # O webhook so enxerga as ultimas JANELA mensagens da conversa.
            visivel = eventos[max(0, indice - JANELA + 1): indice + 1]
            if foi_enviada_pelo_bot(visivel, pid):
                reconhecidas += 1
            else:
                falhas += 1
                por_conversa[telefone] += 1
                if len(exemplos_falha) < 5:
                    exemplos_falha.append(
                        (telefone, str(evento.get("sk"))[4:23], str(evento.get("content"))[:50]))

    print(f"clinica: {args.clinica}")
    print(f"mensagens enviadas pelo bot (com providerMessageId): {total}")
    print(f"  reconhecidas como eco : {reconhecidas}")
    print(f"  NAO reconhecidas      : {falhas}")
    print(f"mensagens humanas (SENT sem providerMessageId)      : {humanas}")
    print()
    if falhas:
        print("*** FALHA: essas mensagens fariam o bot pausar a si mesmo ***")
        for tel, quando, txt in exemplos_falha:
            print(f"   {tel} {quando} {txt!r}")
        print(f"   conversas afetadas: {dict(por_conversa)}")
        sys.exit(1)
    print("OK - toda mensagem do bot e reconhecida como eco. Ele nao se pausa.")


if __name__ == "__main__":
    main()
