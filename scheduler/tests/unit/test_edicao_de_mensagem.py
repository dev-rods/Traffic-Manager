# -*- coding: utf-8 -*-
"""Mensagem editada não é duplicata.

10/10/2026, Essência: a paciente escreveu "Gostaria de fazer virilha completa
+ perianal" (13:26:22), editou 15s depois para "... + axilas" (13:26:37), e o
webhook descartou a edição com "Duplicate message" porque a z-api reaproveita
o messageId da original. O bot cotou e agendou só virilha. A janela de 68s
ainda estava aberta; bastava trocar o texto no balde.
"""
import os
import unittest
from decimal import Decimal
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")
os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.functions.webhook import handler as wh
from src.providers.whatsapp_provider import IncomingMessage
from src.providers.zapi_provider import ZApiProvider
from src.services import agregador_de_mensagens as ag
from src.services.message_tracker import MessageTracker

CLINIC = "clinicaessenciaestetica-9668a4"
PHONE = "5511990185177"
ORIGINAL = "Gostaria de fazer virilha completa + perianal"
EDITADA = "Gostaria de fazer virilha completa + perianal + axilas"

PAYLOAD_ORIGINAL = {
    "instanceId": "I1", "messageId": "3A426D4D2D59A301BB80", "phone": PHONE, "fromMe": False,
    "momment": 1791638780000, "status": "RECEIVED", "senderName": "stephanie ", "isEdit": False,
    "type": "ReceivedCallback", "text": {"message": ORIGINAL},
}
PAYLOAD_EDICAO = {
    **PAYLOAD_ORIGINAL, "isEdit": True, "editMessageId": "3ABCC4350C05AD7F66EB",
    "phone": "250989600841884@lid", "momment": 1791638793000, "text": {"message": EDITADA},
}


def provider():
    p = object.__new__(ZApiProvider)
    return p


class TestParse(unittest.TestCase):

    def test_edicao_traz_o_id_da_original_e_o_da_edicao(self):
        m = provider().parse_incoming_message(PAYLOAD_EDICAO)
        self.assertTrue(m.is_edit)
        self.assertEqual(m.message_id, "3A426D4D2D59A301BB80")
        self.assertEqual(m.edit_message_id, "3ABCC4350C05AD7F66EB")
        self.assertEqual(m.content, EDITADA)
        self.assertEqual(m.message_type, "TEXT")

    def test_mensagem_normal_nao_e_edicao(self):
        m = provider().parse_incoming_message(PAYLOAD_ORIGINAL)
        self.assertFalse(m.is_edit)
        self.assertIsNone(m.edit_message_id)


class FalhaDeCondicao(Exception):
    pass


class BaldeFalso:
    """O balde do agregador, com update por índice e condição de versão."""

    def __init__(self, mensagens=None, versao=1):
        self.item = {"mensagens": list(mensagens or []), "versao": Decimal(versao)}
        self.updates = []
        self.muda_antes_do_update = False

        class _Excs:
            ConditionalCheckFailedException = FalhaDeCondicao

        class _Client:
            exceptions = _Excs()

        class _Meta:
            client = _Client()

        self.meta = _Meta()

    def get_item(self, Key):
        return {"Item": dict(self.item)} if self.item["mensagens"] else {}

    def update_item(self, Key, UpdateExpression, ConditionExpression, ExpressionAttributeValues):
        if self.muda_antes_do_update:
            self.item["versao"] += 1
            self.muda_antes_do_update = False
        if int(self.item["versao"]) != ExpressionAttributeValues[":v"]:
            raise FalhaDeCondicao()
        import re
        i = int(re.search(r"mensagens\[(\d+)\]", UpdateExpression).group(1))
        self.item["mensagens"][i]["content"] = ExpressionAttributeValues[":c"]
        self.item["versao"] += 1
        self.updates.append(UpdateExpression)


class TestEditaNoBalde(unittest.TestCase):

    def test_troca_o_texto_da_mensagem_certa(self):
        balde = BaldeFalso([{"message_id": "m1", "content": "oi"},
                            {"message_id": "m2", "content": ORIGINAL}])
        self.assertTrue(ag.edita(balde, CLINIC, PHONE, "m2", EDITADA))
        self.assertEqual([m["content"] for m in balde.item["mensagens"]], ["oi", EDITADA])
        self.assertEqual(ag.junta_conteudo(balde.item["mensagens"]), f"oi\n{EDITADA}")

    def test_mensagem_ja_drenada_devolve_false(self):
        self.assertFalse(ag.edita(BaldeFalso([]), CLINIC, PHONE, "m2", EDITADA))
        self.assertFalse(ag.edita(BaldeFalso([{"message_id": "outra", "content": "x"}]),
                                  CLINIC, PHONE, "m2", EDITADA))

    def test_corrida_relê_e_aplica(self):
        balde = BaldeFalso([{"message_id": "m2", "content": ORIGINAL}])
        balde.muda_antes_do_update = True
        self.assertTrue(ag.edita(balde, CLINIC, PHONE, "m2", EDITADA))
        self.assertEqual(balde.item["mensagens"][0]["content"], EDITADA)


class EventosFalsos:
    def __init__(self, itens):
        self.itens = itens
        self.update = None

    def query(self, **kw):
        m = kw["ExpressionAttributeValues"][":m"]
        return {"Items": [i for i in self.itens if i.get("messageId") == m and i.get("direction") == "INBOUND"]}

    def update_item(self, **kw):
        self.update = kw


class TestAplicaEdicaoNoRegistro(unittest.TestCase):

    def _tracker(self, itens):
        t = object.__new__(MessageTracker)
        t.table = EventosFalsos(itens)
        return t

    def test_original_recebe_o_texto_novo_e_guarda_o_anterior(self):
        t = self._tracker([{"pk": "p", "sk": "MSG#2026-10-10T13:26:22Z#3A42", "messageId": "3A42",
                            "direction": "INBOUND", "content": ORIGINAL}])
        self.assertTrue(t.aplica_edicao(CLINIC, PHONE, "3A42", EDITADA))
        u = t.table.update
        self.assertEqual(u["Key"], {"pk": "p", "sk": "MSG#2026-10-10T13:26:22Z#3A42"})
        self.assertEqual(u["ExpressionAttributeValues"][":c"], EDITADA)
        self.assertEqual(u["ExpressionAttributeValues"][":a"], ORIGINAL)
        self.assertIn("editadoEm", u["UpdateExpression"])

    def test_sem_original_nao_inventa(self):
        t = self._tracker([{"messageId": "3A42", "direction": "OUTBOUND", "content": "x"}])
        self.assertFalse(t.aplica_edicao(CLINIC, PHONE, "3A42", EDITADA))
        self.assertIsNone(t.table.update)


class TestNoWebhook(unittest.TestCase):

    def _incoming(self):
        return provider().parse_incoming_message({**PAYLOAD_EDICAO, "phone": PHONE})

    def test_janela_aberta_troca_no_balde_e_para(self):
        """O caso de 10/10: a edição chegou 15s depois, dentro da janela."""
        tracker = mock.MagicMock()
        balde = BaldeFalso([{"message_id": "3A426D4D2D59A301BB80", "content": ORIGINAL}])
        incoming = self._incoming()
        self.assertTrue(wh._trata_edicao(tracker, balde, CLINIC, incoming))
        self.assertEqual(balde.item["mensagens"][0]["content"], EDITADA)
        tracker.aplica_edicao.assert_called_once_with(CLINIC, PHONE, "3A426D4D2D59A301BB80", EDITADA)

    def test_depois_da_resposta_vira_correcao_para_o_agente(self):
        tracker = mock.MagicMock()
        incoming = self._incoming()
        self.assertFalse(wh._trata_edicao(tracker, BaldeFalso([]), CLINIC, incoming))
        self.assertEqual(incoming.content, f"{wh.PREFIXO_DE_CORRECAO} {EDITADA}")
        tracker.aplica_edicao.assert_called_once()

    def test_edicao_sem_texto_so_atualiza_o_registro(self):
        tracker = mock.MagicMock()
        incoming = IncomingMessage(message_id="m", phone=PHONE, sender_name="", timestamp=0,
                                   message_type="IMAGE", content="", is_edit=True, edit_message_id="e")
        self.assertTrue(wh._trata_edicao(tracker, BaldeFalso([{"message_id": "m", "content": "x"}]), CLINIC, incoming))

    def test_dedupe_usa_o_id_da_edicao(self):
        """A chave do dedupe não pode ser o messageId da original, senão a
        edição é 'duplicata' sempre. Lê o fonte porque a chave é montada
        inline no handler."""
        import inspect
        fonte = inspect.getsource(wh.handler)
        self.assertIn("incoming.edit_message_id or incoming.message_id", fonte)
        self.assertIn('f"MSG#{chave_de_dedupe}"', fonte)
        self.assertNotIn('f"MSG#{incoming.message_id}"', fonte)
