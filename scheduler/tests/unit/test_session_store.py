"""Marca de elegibilidade da conversa.

O ponto central: a sessão é gravada aninhada em `item["session"]`, e é de lá que
`_load_session` lê. Marcar na raiz do item passaria despercebido — com a política
LEADS_ONLY o bot ficaria mudo para todo mundo, sem erro nenhum aparecendo.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.session_store import mark_conversation_eligible


class FakeTable:
    def __init__(self, item=None):
        self.item = item
        self.gravado = None

    def get_item(self, Key):
        return {"Item": self.item} if self.item else {}

    def put_item(self, Item):
        self.gravado = Item
        self.item = Item


class TableQuebrada:
    def get_item(self, Key):
        raise RuntimeError("dynamo fora do ar")

    def put_item(self, Item):
        raise RuntimeError("dynamo fora do ar")


class TestMarcacao(unittest.TestCase):
    def test_marca_dentro_de_session_e_nao_na_raiz(self):
        table = FakeTable()

        mark_conversation_eligible(table, "clinica-x", "5511999999999")

        self.assertTrue(table.gravado["session"]["bot_enabled"])
        self.assertNotIn("bot_enabled", table.gravado)

    def test_preserva_historico_existente(self):
        """O agente acabou de gravar o histórico; a marca não pode apagá-lo."""
        table = FakeTable({
            "pk": "CLINIC#clinica-x", "sk": "PHONE#5511999999999",
            "session": {"agent_history": [{"role": "user", "content": "oi"}], "mode": "agent"},
        })

        mark_conversation_eligible(table, "clinica-x", "5511999999999")

        session = table.gravado["session"]
        self.assertEqual(len(session["agent_history"]), 1)
        self.assertEqual(session["mode"], "agent")
        self.assertTrue(session["bot_enabled"])

    def test_grava_lead_id_quando_informado(self):
        table = FakeTable()

        mark_conversation_eligible(table, "clinica-x", "5511999999999", lead_id="lead-42")

        self.assertEqual(table.gravado["session"]["lead_id"], "lead-42")

    def test_sem_lead_id_nao_cria_a_chave(self):
        table = FakeTable()

        mark_conversation_eligible(table, "clinica-x", "5511999999999")

        self.assertNotIn("lead_id", table.gravado["session"])

    def test_chaves_do_item_seguem_o_padrao(self):
        table = FakeTable()

        mark_conversation_eligible(table, "clinica-x", "5511999999999")

        self.assertEqual(table.gravado["pk"], "CLINIC#clinica-x")
        self.assertEqual(table.gravado["sk"], "PHONE#5511999999999")

    def test_sessao_inexistente_e_criada(self):
        table = FakeTable()

        self.assertTrue(mark_conversation_eligible(table, "clinica-x", "5511999999999"))

    def test_atendente_ativo_e_preservado(self):
        """Marcar elegível não pode reativar o bot numa conversa assumida por humano."""
        table = FakeTable({
            "pk": "CLINIC#c", "sk": "PHONE#p",
            "session": {"attendant_active_until": 9999999999},
        })

        mark_conversation_eligible(table, "clinica-x", "5511999999999")

        self.assertEqual(table.gravado["session"]["attendant_active_until"], 9999999999)


class TestFalha(unittest.TestCase):
    def test_falha_no_dynamo_nao_levanta(self):
        """O envio já aconteceu; derrubar aqui não desfaz nada e piora o log."""
        self.assertFalse(mark_conversation_eligible(TableQuebrada(), "c", "p"))


if __name__ == "__main__":
    unittest.main()
