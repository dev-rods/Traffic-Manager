# -*- coding: utf-8 -*-
"""TESTE E2E EM DEV: o bot pausa com atendente humano e nao pausa com o proprio eco.

Invoca a lambda WhatsAppWebhook do stage dev com dois payloads sinteticos e
confere o efeito real na sessao do DynamoDB. Nenhuma mensagem sai no WhatsApp:
o payload fromMe representa uma mensagem JA enviada, o webhook so a interpreta.

Numero usado: +55 11 97052-2647 (numero de teste do Andre).

    python -X utf8 tests/evaluation/teste_dev_atendimento_humano.py            # roda
    python -X utf8 tests/evaluation/teste_dev_atendimento_humano.py --limpar   # so limpa

Sai com codigo 1 se algum dos dois cenarios falhar.
"""
import argparse
import json
import sys
import time
import uuid

import boto3

PERFIL = "dev-andre"
REGIAO = "us-east-1"
STAGE = "dev"
LAMBDA_WEBHOOK = f"clinic-scheduler-infra-{STAGE}-WhatsAppWebhook"
TABELA_SESSOES = f"clinic-scheduler-infra-{STAGE}-conversation-sessions"
TABELA_EVENTOS = f"clinic-scheduler-infra-{STAGE}-message-events"

CLINICA = "clinicaessenciaestetica-9668a4"
TELEFONE = "5511970522647"

sessao_aws = boto3.Session(profile_name=PERFIL, region_name=REGIAO)
dynamo = sessao_aws.resource("dynamodb")
lambda_client = sessao_aws.client("lambda")


def instancia_zapi_da_clinica():
    """O webhook resolve a clinica pelo instanceId; sem o valor certo ele ignora."""
    import os
    ssm = sessao_aws.client("ssm")
    for env, param in [("RDS_HOST", "SUPABASE_DB_HOST"), ("RDS_PORT", "SUPABASE_DB_PORT"),
                       ("RDS_DATABASE", "SUPABASE_DB_NAME"), ("RDS_USERNAME", "SUPABASE_DB_USER"),
                       ("RDS_PASSWORD", "SUPABASE_DB_PASSWORD")]:
        os.environ[env] = ssm.get_parameter(
            Name=f"/{STAGE}/{param}", WithDecryption=True)["Parameter"]["Value"]
    sys.path.insert(0, ".")
    from src.services.db.postgres import PostgresService
    linhas = PostgresService().execute_query(
        "SELECT zapi_instance_id FROM scheduler.clinics WHERE clinic_id = %s", (CLINICA,))
    return linhas[0]["zapi_instance_id"] if linhas else None


def limpa_estado():
    dynamo.Table(TABELA_SESSOES).delete_item(
        Key={"pk": f"CLINIC#{CLINICA}", "sk": f"PHONE#{TELEFONE}"})
    tabela = dynamo.Table(TABELA_EVENTOS)
    from boto3.dynamodb.conditions import Key
    pk = f"CLINIC#{CLINICA}#PHONE#{TELEFONE}"
    itens = tabela.query(KeyConditionExpression=Key("pk").eq(pk)).get("Items", [])
    for i in itens:
        tabela.delete_item(Key={"pk": i["pk"], "sk": i["sk"]})
    return len(itens)


def registra_mensagem_do_bot(provider_id):
    """Simula o rastro que o bot deixa ao enviar: e esse id que o webhook procura."""
    agora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dynamo.Table(TABELA_EVENTOS).put_item(Item={
        "pk": f"CLINIC#{CLINICA}#PHONE#{TELEFONE}",
        "sk": f"MSG#{agora}#{uuid.uuid4()}",
        "direction": "OUTBOUND", "status": "SENT",
        "providerMessageId": provider_id,
        "content": "Mensagem que o bot enviou (teste)",
        "clinicId": CLINICA, "phone": TELEFONE,
        "messageId": str(uuid.uuid4()), "provider": "zapi",
        "createdAt": agora,
    })


def dispara_webhook(instance_id, provider_id, texto):
    payload = {
        "body": json.dumps({
            "instanceId": instance_id,
            "phone": TELEFONE,
            "fromMe": True,
            "status": "SENT",
            "messageId": provider_id,
            "momment": int(time.time() * 1000),
            "type": "ReceivedCallback",
            "isGroup": False,
            "isStatusReply": False,
            "senderName": "Clinica Essencia Estetica",
            "text": {"message": texto},
        }),
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
    }
    r = lambda_client.invoke(FunctionName=LAMBDA_WEBHOOK, InvocationType="RequestResponse",
                             Payload=json.dumps(payload).encode())
    return json.loads(r["Payload"].read())


def bot_esta_pausado():
    item = dynamo.Table(TABELA_SESSOES).get_item(
        Key={"pk": f"CLINIC#{CLINICA}", "sk": f"PHONE#{TELEFONE}"}).get("Item") or {}
    sessao = item.get("session", {})
    ate = sessao.get("attendant_active_until")
    return bool(ate and int(ate) > int(time.time())), sessao.get("state"), ate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limpar", action="store_true", help="so apaga o estado de teste")
    args = ap.parse_args()

    print(f"stage={STAGE} | clinica={CLINICA} | telefone={TELEFONE}")
    apagados = limpa_estado()
    print(f"estado de teste limpo ({apagados} evento(s) removido(s))")
    if args.limpar:
        return

    instance_id = instancia_zapi_da_clinica()
    if not instance_id:
        print("ERRO: clinica sem zapi_instance_id em dev; o webhook nao resolveria a clinica")
        sys.exit(1)
    print(f"instanceId da clinica em dev: {instance_id[:14]}...")
    print()

    falhas = []

    # ---- Cenario 1: eco do proprio bot NAO pode pausar ----
    print("[1] eco do proprio bot")
    id_do_bot = f"3EB0{uuid.uuid4().hex[:18].upper()}"
    registra_mensagem_do_bot(id_do_bot)
    dispara_webhook(instance_id, id_do_bot, "Mensagem que o bot enviou (teste)")
    time.sleep(2)
    pausado, estado, _ = bot_esta_pausado()
    print(f"    bot pausado? {pausado} (state={estado})")
    if pausado:
        falhas.append("O eco do proprio bot pausou o bot - ele ficaria mudo apos responder")
    else:
        print("    OK: o bot reconheceu a propria mensagem e seguiu ativo")
    print()

    # ---- Cenario 2: mensagem digitada no celular PRECISA pausar ----
    print("[2] atendente digitando no celular")
    id_do_celular = f"2A{uuid.uuid4().hex[:20].upper()}"   # id que o bot nunca registrou
    dispara_webhook(instance_id, id_do_celular, "Oi! Aqui e a Clara, vou te atender")
    time.sleep(2)
    pausado, estado, ate = bot_esta_pausado()
    restante = (int(ate) - int(time.time())) / 3600 if ate else 0
    print(f"    bot pausado? {pausado} (state={estado}, faltam {restante:.1f}h)")
    if not pausado:
        falhas.append("Mensagem do celular NAO pausou o bot - ele atropelaria o atendimento")
    elif restante < 23 or restante > 25:
        falhas.append(f"TTL fora do esperado: {restante:.1f}h (deveria ser ~24h)")
    else:
        print("    OK: bot pausado por 24h")
    print()

    if falhas:
        print("*** FALHAS ***")
        for f in falhas:
            print(f"  - {f}")
        sys.exit(1)
    print("OK - os dois cenarios passaram.")
    print(f"Rode com --limpar para apagar o estado de teste do telefone {TELEFONE}.")


if __name__ == "__main__":
    main()
