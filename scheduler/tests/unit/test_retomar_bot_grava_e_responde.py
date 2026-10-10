# -*- coding: utf-8 -*-
"""O botão "Retomar bot" grava a transição e responde o que ficou em aberto.

Em 10/10/2026 o André retomou o bot para uma pessoa que tinha perguntado a
forma de pagamento (o FAQ acabara de ganhar o item). Nada aconteceu, por dois
defeitos:

1. `grava_atendimento` recebia `extras={"state": ...}` e "state" já está na
   projeção legada: dois SET no mesmo caminho, e o DynamoDB recusa a escrita
   inteira ("Two document paths overlap"). A sessão continuava com a pessoa.
   Assim desde 06/10 - foi o único clique no botão desde então.
2. `ha_pergunta_em_aberto` olhava a última mensagem com texto: era o aviso do
   bot "já chamei uma especialista", gravado junto da entrega. A pergunta da
   pessoa estava atrás dele e contava como respondida.
"""
import os
import re
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services import atendimento as at
from src.services.conversation_resume import ha_pergunta_em_aberto
from src.services.session_store import grava_atendimento

ENTREGA = 1791652625  # 2026-10-10T17:17:05Z


def ev(direction, content, quando, **extra):
    import time
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(quando))
    e = {"direction": direction, "content": content, "sk": f"MSG#{iso}#x", "status": "SENT"}
    if direction == "OUTBOUND" and not extra.get("humano"):
        e["providerMessageId"] = "pmid"
    if extra.get("humano"):
        e["metadata"] = {"autor": "HUMANO"}
    return e


class TabelaQueRecusaCaminhosRepetidos:
    """Como o DynamoDB: dois SET no mesmo caminho é ValidationException."""

    def __init__(self):
        self.item = {"session": {"x": 1, at.CAMPO: {"handler": at.HUMAN_ACTIVE, "versao": 3}}}
        self.gravou = None

    def get_item(self, Key):
        return {"Item": self.item}

    def update_item(self, Key, UpdateExpression, ConditionExpression, ExpressionAttributeNames, ExpressionAttributeValues):
        caminhos = []
        for parte in re.split(r"\bSET\b|\bREMOVE\b", UpdateExpression):
            for trecho in parte.split(","):
                alvo = trecho.strip().split("=")[0].strip()
                if alvo:
                    for k, v in ExpressionAttributeNames.items():
                        alvo = alvo.replace(k, v)
                    caminhos.append(alvo)
        repetidos = {c for c in caminhos if caminhos.count(c) > 1}
        if repetidos:
            raise type("ValidationException", (Exception,), {})(
                f"Invalid UpdateExpression: Two document paths overlap: {repetidos}")
        self.gravou = (UpdateExpression, ExpressionAttributeValues)


class TestGravaComExtras(unittest.TestCase):

    def test_extras_que_repete_a_projecao_grava_uma_vez(self):
        tabela = TabelaQueRecusaCaminhosRepetidos()
        s = {at.CAMPO: {"handler": at.HUMAN_ACTIVE, "versao": 3}, "state": "WELCOME"}
        at.retoma_pelo_painel(s)
        self.assertTrue(grava_atendimento(tabela, "c1", "55", s, extras={"state": "WELCOME", "bot_enabled": True}))
        expressao, valores = tabela.gravou
        self.assertEqual(expressao.count("session.state") if "session.state" in expressao else
                         sum(1 for k, v in valores.items() if v == "WELCOME"), 1)
        self.assertIn(True, valores.values(), "bot_enabled foi junto")

    def test_sem_extras_continua_igual(self):
        tabela = TabelaQueRecusaCaminhosRepetidos()
        s = {at.CAMPO: {"handler": at.HUMAN_ACTIVE, "versao": 3}}
        at.retoma_pelo_painel(s)
        self.assertTrue(grava_atendimento(tabela, "c1", "55", s))


class TestAvisoDeHandoffNaoEResposta(unittest.TestCase):

    def test_pergunta_atras_do_aviso_continua_em_aberto(self):
        eventos = [
            ev("INBOUND", "eu posso fazer o pix quando chegar ai?", ENTREGA - 60),
            ev("OUTBOUND", "Já chamei uma especialista para te ajudar com os detalhes do pagamento!", ENTREGA + 5),
        ]
        self.assertTrue(ha_pergunta_em_aberto(eventos, entregue_em=ENTREGA))

    def test_sem_o_instante_vale_a_regra_antiga(self):
        eventos = [
            ev("INBOUND", "eu posso fazer o pix quando chegar ai?", ENTREGA - 60),
            ev("OUTBOUND", "Já chamei uma especialista!", ENTREGA + 5),
        ]
        self.assertFalse(ha_pergunta_em_aberto(eventos))

    def test_resposta_de_verdade_do_bot_antes_da_entrega_conta(self):
        eventos = [
            ev("INBOUND", "quanto custa a axila?", ENTREGA - 3600),
            ev("OUTBOUND", "Axila fica R$ 95,00.", ENTREGA - 3500),
        ]
        self.assertFalse(ha_pergunta_em_aberto(eventos, entregue_em=ENTREGA))

    def test_resposta_da_atendente_fecha_a_pergunta(self):
        eventos = [
            ev("INBOUND", "posso fazer o pix na hora?", ENTREGA - 60),
            ev("OUTBOUND", "Já chamei uma especialista!", ENTREGA + 5),
            ev("OUTBOUND", "Pode sim, pix na hora 🥰", ENTREGA + 600, humano=True),
        ]
        self.assertFalse(ha_pergunta_em_aberto(eventos, entregue_em=ENTREGA))

    def test_pessoa_escreveu_depois_do_aviso(self):
        eventos = [
            ev("INBOUND", "posso fazer o pix na hora?", ENTREGA - 60),
            ev("OUTBOUND", "Já chamei uma especialista!", ENTREGA + 5),
            ev("INBOUND", "ok, aguardo", ENTREGA + 300),
        ]
        self.assertTrue(ha_pergunta_em_aberto(eventos, entregue_em=ENTREGA))


class TestHandlerLevaOInstante(unittest.TestCase):

    def test_payload_da_retomada_carrega_entregue_em(self):
        from src.functions.attendant import handler as modulo
        tracker = mock.MagicMock()
        tracker.get_conversation_messages.return_value = [
            ev("INBOUND", "posso fazer o pix na hora?", ENTREGA - 60),
            ev("OUTBOUND", "Já chamei uma especialista!", ENTREGA + 5),
        ]
        lambda_client = mock.MagicMock()
        with mock.patch("src.services.message_tracker.MessageTracker", return_value=tracker), \
             mock.patch.object(modulo, "boto3") as boto:
            boto.client.return_value = lambda_client
            agendou = modulo._agendar_retomada("c1", "5511999990000", mock.MagicMock(invoked_function_arn="arn"), ENTREGA)
        self.assertTrue(agendou, "a pergunta atrás do aviso é pendente")
        import json
        payload = json.loads(lambda_client.invoke.call_args.kwargs["Payload"])
        self.assertEqual(payload["entregue_em"], ENTREGA)

    def test_retomar_que_nao_grava_devolve_erro(self):
        from src.functions.attendant import handler as modulo
        evento = {"httpMethod": "POST", "path": "/attendant/deactivate", "headers": {"x-api-key": "k"},
                  "body": '{"clinic_id": "c1", "phone": "5511999990000"}'}
        with mock.patch.object(modulo, "require_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "_get_sessions_table"), \
             mock.patch.object(modulo, "_load_session", return_value={"session": {at.CAMPO: {"handler": at.HUMAN_ACTIVE, "versao": 1, "entregue_em": ENTREGA}}}), \
             mock.patch.object(modulo, "grava_atendimento", return_value=False), \
             mock.patch.object(modulo, "_agendar_retomada") as agenda:
            resposta = modulo.handler(evento, mock.MagicMock())
        self.assertEqual(resposta["statusCode"], 500)
        agenda.assert_not_called()


if __name__ == "__main__":
    unittest.main()
