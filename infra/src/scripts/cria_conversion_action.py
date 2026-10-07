#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cria uma conversion action offline no Google Ads.

Cada clinica precisa de DUAS (PRD 016 e 017):

    --compra        PURCHASE, so confirmado e com sessao passada. Mede receita.
    --agendamento   BOOK_APPOINTMENT, todo agendamento inclusive cancelado e
                    falta. E o que vai guiar o lance.

Um evento otimiza, o outro mede. Ver docs/work/prd/017-agendou-pelo-whatsapp.md.

    python -m src.scripts.cria_conversion_action <customer_id> --agendamento
    python -m src.scripts.cria_conversion_action <customer_id> --agendamento --aplicar

Sem `--aplicar` usa `validate_only` da propria API do Google: ele valida a
criacao e NAO cria nada. Mesma disciplina do `validateOnly` do uploader - a
alternativa e descobrir o erro tendo criado uma action torta na conta do
cliente, e action nao se apaga, so se remove (irreversivel).

## As duas nascem SECUNDARIAS, e isso e deliberado

`primary_for_goal=False` e o que mantem a action fora do Smart Bidding,
independente da categoria. Promover e decisao de painel, depois de 4-6 semanas
de historico - e vem junto com a despromocao da `Lead - Formulario`, nao somada
a ela.

Deixar as duas biddable contaria a MESMA jornada duas vezes: um lead preenche o
formulario (conversao 1) e depois agenda (conversao 2). O tCPA de R$78 viraria
efetivamente R$39, e o algoritmo pagaria mais caro do que se pediu. E o mesmo
defeito que a `Lead jardins` duplicada causava nos relatorios.

## Por que BOOK_APPOINTMENT e nao SUBMIT_LEAD_FORM

`SUBMIT_LEAD_FORM` ja e meta BIDDABLE na campanha ativa. Criar a action nessa
categoria a faria entrar no leilao IMEDIATAMENTE, contrariando o desenho - e o
`primary_for_goal=False` seria a unica coisa segurando. `BOOK_APPOINTMENT`
descreve o evento com precisao e nao colide com meta biddable nenhuma.
"""
import os
import sys

import boto3

PERFIL = "dev-andre"
REGIAO = "us-east-1"
JANELA_DIAS = 90

# (nome, categoria). O tipo e sempre UPLOAD_CLICKS: as duas sobem por upload
# offline, nao por tag.
RECEITAS = {
    "compra": ("Agendamento Real (Offline)", "PURCHASE"),
    "agendamento": ("Agendou pelo WhatsApp", "BOOK_APPOINTMENT"),
}


def _config_do_ssm(stage="prod"):
    """As credenciais do Google Ads, lidas do SSM - nunca de arquivo local.

    O `.env` do repo aponta para um RDS desativado, e o mesmo descuido vale
    aqui: credencial de producao tem um lugar so.
    """
    ssm = boto3.Session(profile_name=PERFIL, region_name=REGIAO).client("ssm")

    def par(nome):
        return ssm.get_parameter(
            Name="/%s/%s" % (stage, nome), WithDecryption=True
        )["Parameter"]["Value"]

    return {
        "developer_token": par("MCC_DEVELOPER_TOKEN"),
        "client_id": par("OAUTH2_CLIENT_ID"),
        "client_secret": par("OAUTH2_CLIENT_SECRET"),
        "refresh_token": par("GOOGLE_ADS_REFRESH_TOKEN"),
        "login_customer_id": par("MCC_ACCOUNT_ID").replace("-", ""),
        "use_proto_plus": True,
    }


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    aplicar = "--aplicar" in sys.argv
    qual = "agendamento" if "--agendamento" in sys.argv else (
        "compra" if "--compra" in sys.argv else None)

    if len(argumentos) != 1 or qual is None:
        print(__doc__)
        raise SystemExit(2)

    customer_id = argumentos[0].replace("-", "")
    nome, categoria = RECEITAS[qual]

    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException

    client = GoogleAdsClient.load_from_dict(_config_do_ssm())
    servico = client.get_service("ConversionActionService")

    # Ja existe uma com este nome? Criar duas iguais e pior que nao criar: o
    # uploader aponta para UMA, e a outra fica recebendo nada enquanto aparece
    # no painel como se existisse.
    ga = client.get_service("GoogleAdsService")
    existentes = list(ga.search(
        customer_id=customer_id,
        query=(
            "SELECT conversion_action.id, conversion_action.name, "
            "conversion_action.status, conversion_action.category "
            "FROM conversion_action WHERE conversion_action.name = '%s'" % nome
        ),
    ))
    if existentes:
        for linha in existentes:
            a = linha.conversion_action
            print("!! ja existe: id=%s status=%s categoria=%s"
                  % (a.id, a.status.name, a.category.name))
        print("   Nao vou criar outra com o mesmo nome.")
        raise SystemExit(1)

    operacao = client.get_type("ConversionActionOperation")
    acao = operacao.create
    acao.name = nome
    acao.type_ = client.enums.ConversionActionTypeEnum.UPLOAD_CLICKS
    acao.category = getattr(client.enums.ConversionActionCategoryEnum, categoria)
    acao.status = client.enums.ConversionActionStatusEnum.ENABLED
    acao.click_through_lookback_window_days = JANELA_DIAS

    # Secundaria. Ver o docstring: promover e decisao de painel, e deixar as
    # duas biddable contaria a mesma jornada duas vezes.
    acao.primary_for_goal = False

    # `include_in_conversions_metric` NAO entra aqui: a API recusa com
    # "The field attempted to be mutated is immutable" na criacao. Ele e
    # derivado da configuracao de metas da conta, nao definido na action.
    #
    # Nao e perda: quem mantem a action fora do Smart Bidding e o
    # `primary_for_goal=False` acima. O `include_in_conversions_metric` decide
    # se ela entra na COLUNA "Conversoes" do relatorio, e isso se ajusta no
    # painel depois - conferir que saiu `false`, como esta na action de compra.

    # Cada agendamento e uma conversao propria: a paciente que volta gera
    # varias do mesmo clique, e isso e o retorno que queremos reportar.
    acao.counting_type = (
        client.enums.ConversionActionCountingTypeEnum.MANY_PER_CLICK)

    print("=== %s na conta %s" % (qual.upper(), customer_id))
    print("  nome:       %s" % nome)
    print("  categoria:  %s" % categoria)
    print("  tipo:       UPLOAD_CLICKS")
    print("  janela:     %d dias" % JANELA_DIAS)
    print("  primaria:   NAO (secundaria - fora do Smart Bidding)")
    print("  contagem:   MANY_PER_CLICK")

    # `validate_only` vai no objeto de request, nao como kwarg - a assinatura
    # do cliente gerado so aceita `customer_id` e `operations` soltos.
    pedido = client.get_type("MutateConversionActionsRequest")
    pedido.customer_id = customer_id
    pedido.operations = [operacao]
    pedido.validate_only = not aplicar

    try:
        resposta = servico.mutate_conversion_actions(request=pedido)
    except GoogleAdsException as erro:
        print("\n  FALHOU:")
        for e in erro.failure.errors:
            # O caminho do campo e o que transforma "campo imutavel" num
            # diagnostico: sem ele, sobra adivinhar qual dos dez.
            caminho = ".".join(
                x.field_name for x in e.location.field_path_elements)
            print("    %s%s" % (e.message, "  [%s]" % caminho if caminho else ""))
        raise SystemExit(1)

    if not aplicar:
        print("\n  (validate_only da API do Google - NADA foi criado)")
        print("  Para criar: acrescente --aplicar")
        return

    nome_recurso = resposta.results[0].resource_name
    action_id = nome_recurso.rsplit("/", 1)[-1]
    print("\n  CRIADA: %s" % nome_recurso)
    print("  id: %s" % action_id)
    print("\n  Proximo passo - ligar a clinica a ela:")
    flag = "--agendamento " if qual == "agendamento" else ""
    print("    cd scheduler && python -m src.scripts.liga_conversao_offline "
          "<clinic_id> %s %s--aplicar" % (action_id, flag))


if __name__ == "__main__":
    main()
