# -*- coding: utf-8 -*-
"""TESTE E2E EM DEV com os payloads que o z-api manda de verdade.

Os corpos abaixo foram COPIADOS DOS LOGS de producao (conversa de 02/09/2026 com
+5511970522647), nao escritos a mao. A versao anterior deste teste passou sem
provar nada porque eu supus o formato: usei o numero no campo `phone`, enquanto
a mensagem digitada no celular chega com o LID ali.

Nenhuma mensagem sai no WhatsApp: o payload representa uma mensagem JA enviada,
o webhook so a interpreta.

    python -X utf8 tests/evaluation/teste_dev_atendimento_humano.py
    python -X utf8 tests/evaluation/teste_dev_atendimento_humano.py --limpar
"""
import argparse
import json
import sys
import time
import uuid

import boto3

PERFIL = "dev-andre"
STAGE = "dev"
LAMBDA_WEBHOOK = f"clinic-scheduler-infra-{STAGE}-WhatsAppWebhook"
TABELA_SESSOES = f"clinic-scheduler-infra-{STAGE}-conversation-sessions"
TABELA_EVENTOS = f"clinic-scheduler-infra-{STAGE}-message-events"

CLINICA = "clinicaessenciaestetica-9668a4"
TELEFONE = "5511970522647"
LID = "176209673617532@lid"
NUMERO_DA_CLINICA = "5511963352425"
INSTANCIA = "3F143E782FFCB14D71B9E29123FA23F4"

sessao_aws = boto3.Session(profile_name=PERFIL, region_name="us-east-1")
dynamo = sessao_aws.resource("dynamodb")
lambda_client = sessao_aws.client("lambda")


def corpo_cliente_escreveu(texto="Ola, gostaria de agendar"):
    """22:53:34 real — traz numero e chatLid: e o que ensina o vinculo."""
    return {
        "isStatusReply": False, "chatLid": LID, "connectedPhone": NUMERO_DA_CLINICA,
        "waitingMessage": False, "isEdit": False, "isGroup": False,
        "isNewsletter": False, "instanceId": INSTANCIA,
        "messageId": f"3ACF{uuid.uuid4().hex[:16].upper()}",
        "phone": TELEFONE, "fromMe": False, "momment": int(time.time() * 1000),
        "type": "ReceivedCallback", "text": {"message": texto},
    }


def corpo_eco_do_bot(provider_id, texto="Resposta do bot"):
    """22:53:39 real — enviada pela API: numero no phone, status SENT."""
    return {
        "isStatusReply": False, "chatLid": LID, "connectedPhone": NUMERO_DA_CLINICA,
        "waitingMessage": False, "isEdit": False, "isGroup": False,
        "isNewsletter": False, "instanceId": INSTANCIA,
        "messageId": provider_id, "phone": TELEFONE, "fromMe": True,
        "momment": int(time.time() * 1000), "status": "SENT",
        "senderName": "Clinica Essencia Estetica",
        "type": "ReceivedCallback", "text": {"message": texto},
    }


def corpo_atendente_no_celular(texto="Desculpe, corrigindo..."):
    """22:54:54 real — O CASO QUE FALHOU: LID no lugar do numero, status RECEIVED."""
    return {
        "isStatusReply": False, "chatLid": LID, "connectedPhone": NUMERO_DA_CLINICA,
        "waitingMessage": False, "isEdit": False, "isGroup": False,
        "isNewsletter": False, "instanceId": INSTANCIA,
        "messageId": f"3CF0{uuid.uuid4().hex[:16].upper()}",
        "phone": LID, "fromMe": True, "momment": int(time.time() * 1000),
        "status": "RECEIVED", "chatName": "Amor", "photo": None,
        "senderName": "Clinica Essencia Estetica",
        "type": "ReceivedCallback", "text": {"message": texto},
    }


def limpa_estado():
    from boto3.dynamodb.conditions import Key
    sessoes = dynamo.Table(TABELA_SESSOES)
    sessoes.delete_item(Key={"pk": f"CLINIC#{CLINICA}", "sk": f"PHONE#{TELEFONE}"})
    sessoes.delete_item(Key={"pk": f"CLINIC#{CLINICA}", "sk": f"LID#{LID}"})
    eventos = dynamo.Table(TABELA_EVENTOS)
    itens = eventos.query(
        KeyConditionExpression=Key("pk").eq(f"CLINIC#{CLINICA}#PHONE#{TELEFONE}")
    ).get("Items", [])
    for i in itens:
        eventos.delete_item(Key={"pk": i["pk"], "sk": i["sk"]})
    return len(itens)


def registra_envio_do_bot(provider_id):
    agora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dynamo.Table(TABELA_EVENTOS).put_item(Item={
        "pk": f"CLINIC#{CLINICA}#PHONE#{TELEFONE}",
        "sk": f"MSG#{agora}#{uuid.uuid4()}",
        "direction": "OUTBOUND", "status": "SENT",
        "providerMessageId": provider_id, "content": "Resposta do bot",
        "clinicId": CLINICA, "phone": TELEFONE,
        "messageId": str(uuid.uuid4()), "provider": "zapi", "createdAt": agora,
    })


def dispara(corpo):
    r = lambda_client.invoke(
        FunctionName=LAMBDA_WEBHOOK, InvocationType="RequestResponse",
        Payload=json.dumps({"body": json.dumps(corpo), "httpMethod": "POST",
                            "headers": {"Content-Type": "application/json"}}).encode())
    return json.loads(r["Payload"].read())


def estado_do_bot():
    item = dynamo.Table(TABELA_SESSOES).get_item(
        Key={"pk": f"CLINIC#{CLINICA}", "sk": f"PHONE#{TELEFONE}"}).get("Item") or {}
    sessao = item.get("session", {})
    ate = sessao.get("attendant_active_until")
    pausado = bool(ate and int(ate) > int(time.time()))
    horas = (int(ate) - int(time.time())) / 3600 if ate else 0
    return pausado, sessao.get("state"), horas


def lid_vinculado():
    item = dynamo.Table(TABELA_SESSOES).get_item(
        Key={"pk": f"CLINIC#{CLINICA}", "sk": f"LID#{LID}"}).get("Item") or {}
    return item.get("phone")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limpar", action="store_true")
    args = ap.parse_args()

    print(f"stage={STAGE} | clinica={CLINICA} | telefone={TELEFONE} | lid={LID}")
    print(f"estado limpo ({limpa_estado()} evento(s) removido(s))")
    if args.limpar:
        return
    print()

    falhas = []

    # ── 1. cliente escreve: ensina o vinculo LID -> telefone ──
    print("[1] cliente escreve (payload real de 22:53:34)")
    dispara(corpo_cliente_escreveu())
    time.sleep(3)
    vinculo = lid_vinculado()
    print(f"    LID vinculado a: {vinculo}")
    if vinculo != TELEFONE:
        falhas.append(f"vinculo LID->telefone nao foi gravado (veio {vinculo!r})")
    else:
        print("    OK: o webhook aprendeu de quem e a conversa")
    print()

    # ── 2. eco do bot: NAO pode pausar ──
    print("[2] eco do proprio bot (payload real de 22:53:39)")
    pid = f"3EB0{uuid.uuid4().hex[:18].upper()}"
    registra_envio_do_bot(pid)
    dispara(corpo_eco_do_bot(pid))
    time.sleep(2)
    pausado, estado, _ = estado_do_bot()
    print(f"    bot pausado? {pausado} (state={estado})")
    if pausado:
        falhas.append("o eco do proprio bot pausou o bot - ele emudeceria apos responder")
    else:
        print("    OK: reconheceu a propria mensagem e seguiu ativo")
    print()

    # ── 3. atendente no celular: PRECISA pausar ──
    print("[3] atendente digitando no celular (payload real de 22:54:54, LID no phone)")
    dispara(corpo_atendente_no_celular())
    time.sleep(3)
    pausado, estado, horas = estado_do_bot()
    print(f"    bot pausado? {pausado} (state={estado}, faltam {horas:.1f}h)")
    if not pausado:
        falhas.append("MENSAGEM DO CELULAR NAO PAUSOU - o bug de 01/09 continua")
    elif not (23 <= horas <= 25):
        falhas.append(f"TTL fora do esperado: {horas:.1f}h (deveria ser ~24h)")
    else:
        print("    OK: bot pausado por 24h")
    print()

    if falhas:
        print("*** FALHAS ***")
        for f in falhas:
            print(f"  - {f}")
        sys.exit(1)
    print("OK - os tres cenarios passaram com os payloads reais.")


if __name__ == "__main__":
    main()
