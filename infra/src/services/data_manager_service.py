# -*- coding: utf-8 -*-
"""Envia conversao offline ao Google pela Data Manager API.

## Por que este arquivo existe

O Google fechou o `ConversionUploadService.UploadClickConversions` do Google Ads
API para integracoes novas. Descoberto em 03/10/2026, no teste de fumaca em
producao: as 20 conversoes da Essencia voltaram recusadas, uma a uma, com

    New integrations for uploading click conversions should use the Data
    Manager API. Usage of ConversionUploadService.UploadClickConversions is
    limited to existing users.

Nao ha correcao possivel do lado antigo. O caminho e a Data Manager API, que e
outra API: outro host, outro escopo OAuth, outro formato.

## Por que REST e nao o pacote google-ads-datamanager

E um endpoint so. Adicionar um SDK inteiro para uma chamada traz de volta
exatamente o problema que nos custou o dia: o `infra/` fixava
`google-ads==27.0.0`, que falava versoes de API ja mortas, e TODAS as chamadas
ao Google Ads falhavam com `501 GRPC target method can't be resolved` - em
silencio, por meses. Um pin a menos e um modo de falhar a menos. `requests` e
`google-auth` ja estao na imagem.

## O que esta API NAO faz

**Nao existe RETRACTION.** O Google Ads API permitia negar uma conversao
enviada por engano; a Data Manager so permite *restatement* de valor. Ver
`restate_cancelled_to_zero` para o que sobra e o que isso custa.
"""

import logging
import os
from typing import Dict, List, Optional

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logger = logging.getLogger()

ENDPOINT = "https://datamanager.googleapis.com/v1/events:ingest"
ESCOPO = "https://www.googleapis.com/auth/datamanager"

# A referencia REST marca `eventSource` como opcional, mas o destino do Google
# Ads o EXIGE: o primeiro ensaio em producao (03/10/2026) voltou
# `events.events[0].event_source: Required field is missing`. Quando a doc e a
# API discordam, a API ganha.
#
# Duas actions, dois sources. A compra acontece na clinica; o agendamento,
# numa conversa de WhatsApp. WEB descreveria a origem do CLIQUE, que nao e o
# evento que estamos enviando em nenhum dos dois casos.
EVENT_SOURCE_COMPRA = "IN_STORE"
EVENT_SOURCE_AGENDAMENTO = "MESSAGE"

# Limite da API. Coincide com o lote que o uploader ja usava.
MAX_EVENTOS_POR_REQUISICAO = 2000

TIMEOUT_SEGUNDOS = 60


class DataManagerService:
    """Cliente da Data Manager API para conversao offline do Google Ads."""

    def __init__(self):
        self._token: Optional[str] = None

    # ---------------------------------------------------------------- credencial

    def _bearer(self) -> str:
        """Troca o refresh token por um access token com escopo datamanager.

        ## Um token, um parametro

        Houve `DATA_MANAGER_REFRESH_TOKEN` separado, criado em 03/10/2026 sob a
        premissa de que o escopo `datamanager` exigia token proprio. A premissa
        estava errada: um unico consentimento cobre os dois escopos, e e o que
        `generate_refresh_token.py` emite por default desde 05/10.

        Dois parametros nao eram so redundancia - eram risco. Em 04/10 o
        `GOOGLE_ADS_REFRESH_TOKEN` apareceu REVOGADO: gerar o token novo com
        escopo acrescentado invalidou o grant anterior, e isso quebrou TODAS as
        Lambdas que falam com o Google Ads enquanto o uploader de conversao
        seguia funcionando, porque usava o outro parametro. Dois lugares para a
        mesma credencial significam um deles envelhecer sem ninguem notar.

        ## O escopo e conferido, e por que isso importa

        O parametro unico depende de o token carregar `datamanager`. Se alguem
        regenerar so com `adwords`, o upload de conversao para de funcionar - e
        o cron e MENSAL, entao a descoberta viria semanas depois.

        A conferencia abaixo antecipa o diagnostico. Ela nao e a unica defesa: a
        propria Data Manager recusa com HTTP 403 e `_ingest` propaga a mensagem
        do Google. Mas falhar aqui nomeia a causa, em vez de deixar quem le o
        log deduzir de um 403.
        """
        if self._token:
            return self._token

        faltando = [
            nome for nome in
            ("OAUTH2_CLIENT_ID", "OAUTH2_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN")
            if not os.environ.get(nome)
        ]
        if faltando:
            raise ValueError(
                "Credencial do Google ausente: %s. O refresh token precisa ter "
                "sido emitido com o escopo %s - veja "
                "infra/src/scripts/generate_refresh_token.py."
                % (", ".join(faltando), ESCOPO)
            )

        credencial = Credentials(
            token=None,
            refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            client_id=os.environ["OAUTH2_CLIENT_ID"],
            client_secret=os.environ["OAUTH2_CLIENT_SECRET"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[ESCOPO],
        )
        credencial.refresh(Request())

        if not credencial.has_scopes([ESCOPO]):
            raise ValueError(
                "O refresh token em GOOGLE_ADS_REFRESH_TOKEN nao tem o escopo "
                "%s. Ele foi gerado so com `adwords`? Regere com "
                "generate_refresh_token.py, que emite os dois - e DEPLOYE, "
                "porque o serverless injeta o token como env var no deploy."
                % ESCOPO
            )

        self._token = credencial.token
        return self._token

    # ------------------------------------------------------------------ destino

    @staticmethod
    def _destino(customer_id: str, conversion_action_id: str,
                 login_customer_id: Optional[str]) -> Dict:
        """Monta o `destinations[0]` da requisicao.

        `productDestinationId` e o ID da conversion action - a mesma que o
        desenho antigo usava, porque a Data Manager tambem exige tipo
        UPLOAD_CLICKS. Nada a recriar no painel do Google.
        """
        destino = {
            "operatingAccount": {
                "accountType": "GOOGLE_ADS",
                "accountId": str(customer_id).replace("-", ""),
            },
            "productDestinationId": str(conversion_action_id),
        }
        if login_customer_id:
            destino["loginAccount"] = {
                "accountType": "GOOGLE_ADS",
                "accountId": str(login_customer_id).replace("-", ""),
            }
        return destino

    # ------------------------------------------------------------------- evento

    @staticmethod
    def _evento(conv: Dict, event_source: str,
                valor: Optional[float] = None) -> Dict:
        """Converte uma linha de `lead_conversions` num Event da API.

        `transactionId` e o pulo do gato e a diferenca mais importante em
        relacao ao desenho antigo. O Google Ads API identificava a conversao
        pelo par (gclid, conversion_date_time), e um carimbo diferente
        devolvia CONVERSION_NOT_FOUND. A Data Manager identifica por
        `transactionId`: mesmo transactionId na mesma conversion action = a
        API trata como ajuste da conversao original, e nao como nova.

        Ou seja, sem mandar `transactionId` no upload, NENHUM ajuste posterior
        e possivel. E por isso que ele e obrigatorio aqui e nao opcional.

        `event_source` NAO tem default, de proposito. Um default faria o evento
        de agendamento herdar `IN_STORE` em silencio se alguem esquecesse de
        passar, e o erro apareceria como atribuicao estranha no Google semanas
        depois - nao como falha.
        """
        evento = {
            "adIdentifiers": {"gclid": conv["gclid"]},
            "eventTimestamp": conv["conversion_date_time"],
            "transactionId": str(conv["identifier"]),
            "eventSource": event_source,
            "currency": "BRL",
            "conversionValue": float(
                conv["conversion_value"] if valor is None else valor
            ),
        }
        return evento

    # ------------------------------------------------------------------- envio

    def _ingest(self, destino: Dict, eventos: List[Dict],
                validate_only: bool) -> Dict:
        """Faz um POST em events:ingest e traduz a resposta.

        A semantica e mais simples que a do `partial_failure` antigo: ou o
        lote e aceito (HTTP 200, possivelmente com `fieldWarnings`), ou a
        requisicao erra inteira. Nao existe "metade entrou".

        Por isso o retorno nao tem indices de falha: em 200, todos os eventos
        enviados foram aceitos.
        """
        corpo = {
            "destinations": [destino],
            "events": eventos,
            "validateOnly": bool(validate_only),
        }

        try:
            resposta = requests.post(
                ENDPOINT,
                json=corpo,
                headers={"Authorization": "Bearer " + self._bearer()},
                timeout=TIMEOUT_SEGUNDOS,
            )
        except requests.RequestException as erro:
            logger.error("Data Manager inacessivel: %s", erro)
            return {"success": False, "error": "falha de rede: %s" % erro,
                    "accepted": 0}

        if resposta.status_code != 200:
            # A mensagem do Google e o que diz a causa (escopo errado, conta
            # sem permissao, conversion action de outro tipo). Perde-la aqui
            # transforma um diagnostico de um minuto numa tarde de adivinhacao
            # - foi o que o `501` opaco nos custou hoje.
            #
            # O limite era 800 e cortava a resposta no meio: o erro de
            # INVALID_ARGUMENT traz um `fieldViolations` por campo, e o primeiro
            # ensaio mostrou so a primeira violacao antes de ser truncado -
            # escondendo quantas outras existiam. Ficou grande o suficiente para
            # caber a lista inteira.
            detalhe = resposta.text[:4000]
            logger.error("Data Manager recusou (HTTP %s): %s",
                         resposta.status_code, detalhe)
            return {"success": False,
                    "error": "HTTP %s: %s" % (resposta.status_code, detalhe),
                    "accepted": 0}

        dados = resposta.json() if resposta.content else {}
        for aviso in dados.get("fieldWarnings") or []:
            logger.warning("Data Manager avisou: %s", aviso)

        return {
            "success": True,
            "accepted": len(eventos),
            "requestId": dados.get("requestId"),
            "warnings": dados.get("fieldWarnings") or [],
        }

    # ------------------------------------------------------------------ publico

    def ingest_offline_conversions(
        self, customer_id: str, conversion_action_id: str,
        conversions: List[Dict], login_customer_id: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict:
        """Sobe conversoes novas.

        Cada item de `conversions` precisa de `identifier`, `gclid`,
        `conversion_date_time` (ISO 8601) e `conversion_value`.

        Devolve `uploaded_identifiers` com os identifiers aceitos, para o
        chamador marcar `uploaded_at`. Em falha a lista volta VAZIA, de
        proposito: marcar como enviado o que talvez nao tenha ido faz a
        conversao desaparecer para sempre, porque ninguem tentaria de novo.
        """
        if not conversions:
            return {"success": True, "uploaded_identifiers": [], "failed": 0}

        destino = self._destino(customer_id, conversion_action_id, login_customer_id)
        eventos = [self._evento(c, EVENT_SOURCE_COMPRA) for c in conversions]

        resultado = self._ingest(destino, eventos, validate_only)

        if not resultado["success"]:
            return {"success": False, "error": resultado["error"],
                    "uploaded_identifiers": [], "failed": len(conversions)}

        # Em validate_only nada foi gravado no Google, entao nada pode ser
        # marcado como enviado - senao o dry-run queimaria as conversoes.
        if validate_only:
            logger.info("Data Manager validou %d conversoes (validateOnly, nada gravado)",
                        len(eventos))
            return {"success": True, "uploaded_identifiers": [], "failed": 0,
                    "validated": len(eventos)}

        identifiers = [str(c["identifier"]) for c in conversions]
        logger.info("Data Manager aceitou %d conversoes (requestId %s)",
                    len(identifiers), resultado.get("requestId"))
        return {"success": True, "uploaded_identifiers": identifiers, "failed": 0}

    def restate_cancelled_to_zero(
        self, customer_id: str, conversion_action_id: str,
        conversions: List[Dict], login_customer_id: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict:
        """Zera o valor de conversoes que subiram e depois foram canceladas.

        ## Isto NAO e a RETRACTION que o desenho pedia

        A Data Manager API nao tem retratacao: nao existe como negar uma
        conversao ja enviada. O que existe e *restatement* - reenviar o mesmo
        `transactionId` com outro `conversionValue`, que substitui o valor
        gravado "sem incrementar a contagem de conversoes".

        A consequencia precisa, para nao haver ilusao de seguranca:

        - o VALOR do cancelado vai a zero, entao relatorio e ROAS param de
          contar dinheiro que nao entrou;
        - a CONTAGEM permanece. A conversao continua existindo como evento.

        E a campanha da Essencia e `MAXIMIZE_CONVERSIONS` com tCPA, que otimiza
        por CONTAGEM, nao por valor. Logo isto **nao** remove o sinal ruim do
        Smart Bidding. Com 42% de cancelamento medido na Essencia (5 de 12), o
        algoritmo continua aprendendo com quem cancela.

        A unica correcao real para isso nao e codigo, e a regra de
        elegibilidade: voltar a so subir depois da sessao acontecer, trocando
        latencia de sinal por correcao. Decisao do Andre - ver o PR.
        """
        if not conversions:
            return {"success": True, "retracted_identifiers": [], "failed": 0}

        destino = self._destino(customer_id, conversion_action_id, login_customer_id)
        eventos = [self._evento(c, EVENT_SOURCE_COMPRA, valor=0.0)
                   for c in conversions]

        resultado = self._ingest(destino, eventos, validate_only)

        if not resultado["success"]:
            # Mesma logica do upload: nao marcar o que talvez nao tenha ido.
            # Marcar errado aqui deixa a conversao valorizada no Google para
            # sempre, porque ninguem tentaria de novo.
            return {"success": False, "error": resultado["error"],
                    "retracted_identifiers": [], "failed": len(conversions)}

        if validate_only:
            return {"success": True, "retracted_identifiers": [], "failed": 0,
                    "validated": len(eventos)}

        identifiers = [str(c["identifier"]) for c in conversions]
        logger.info("Data Manager zerou o valor de %d conversoes canceladas "
                    "(requestId %s)", len(identifiers), resultado.get("requestId"))
        return {"success": True, "retracted_identifiers": identifiers, "failed": 0}

    def ingest_bookings(
        self, customer_id: str, conversion_action_id: str,
        conversions: List[Dict], login_customer_id: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict:
        """Sobe AGENDAMENTOS - todos, inclusive cancelado e falta.

        E a segunda conversion action (PRD 017), e existe para guiar o lance: a
        campanha otimiza com um sinal so, uma tag de formulario na LP, e
        formulario e intencao enquanto agendar e compromisso com data e preco.

        ## Por que nao e `ingest_offline_conversions` com um parametro

        Os dois eventos tem REGRAS distintas, e e disso que o nome precisa
        avisar. Um `tipo=` convidaria a unificar as regras depois - e unificar
        e exatamente o erro: a compra filtra `CONFIRMED` e sessao passada,
        este nao filtra nada alem da janela de 90 dias.

        ## Por que nao ha retratacao aqui

        Nao e esquecimento. Num evento de agendamento, quem marcou e desmarcou
        AGENDOU de verdade - o lead era qualificado, a pessoa escolheu data e
        servico. Cancelar depois nao desfaz o fato.

        E a propriedade que torna este evento mais simples que o de compra, e
        que dissolve o problema de 03/10/2026: a Data Manager API nao oferece
        retratacao, e aqui ela nao faz falta.
        """
        if not conversions:
            return {"success": True, "uploaded_identifiers": [], "failed": 0}

        destino = self._destino(customer_id, conversion_action_id, login_customer_id)
        eventos = [self._evento(c, EVENT_SOURCE_AGENDAMENTO) for c in conversions]

        resultado = self._ingest(destino, eventos, validate_only)

        if not resultado["success"]:
            return {"success": False, "error": resultado["error"],
                    "uploaded_identifiers": [], "failed": len(conversions)}

        if validate_only:
            logger.info("Data Manager validou %d agendamentos (validateOnly, "
                        "nada gravado)", len(eventos))
            return {"success": True, "uploaded_identifiers": [], "failed": 0,
                    "validated": len(eventos)}

        identifiers = [str(c["identifier"]) for c in conversions]
        logger.info("Data Manager aceitou %d agendamentos (requestId %s)",
                    len(identifiers), resultado.get("requestId"))
        return {"success": True, "uploaded_identifiers": identifiers, "failed": 0}
