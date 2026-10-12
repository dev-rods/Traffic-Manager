# -*- coding: utf-8 -*-
"""PRD 022: conversa vence, identidade não.

Um escritor de sessão que esqueça o `ttl` faz a sessão viver para sempre de
novo, em silêncio. Por isso a conferência é por AST sobre o código de
produção, não por um teste de cada chamador.
"""
import ast
import os
import time
import unittest
from pathlib import Path

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services import atendimento as at
from src.services import retencao
from src.services.session_store import grava_atendimento, mark_conversation_eligible, vincula_lid

RAIZ = Path(__file__).resolve().parents[2] / "src"
AGORA = 1_800_000_000
DIA = 86400


class TestConstantes(unittest.TestCase):
    def test_decisoes_do_andre(self):
        self.assertEqual(retencao.MEMORIA_DO_BOT, 30 * DIA)
        self.assertEqual(retencao.HISTORICO_DO_PAINEL, 60 * DIA)

    def test_ttl_e_epoch_em_segundos(self):
        self.assertEqual(retencao.ttl_da_sessao(AGORA), AGORA + 30 * DIA)
        self.assertEqual(retencao.ttl_do_evento(AGORA), AGORA + 60 * DIA)
        self.assertEqual(retencao.inicio_da_memoria(AGORA), AGORA - 30 * DIA)


class TestSessaoVencida(unittest.TestCase):
    def test_31_dias_venceu_29_nao(self):
        self.assertTrue(retencao.sessao_vencida(retencao.iso(AGORA - 31 * DIA), AGORA))
        self.assertFalse(retencao.sessao_vencida(retencao.iso(AGORA - 29 * DIA), AGORA))

    def test_sem_updated_at_nao_vence(self):
        """Na dúvida, lembrar: sessão nova ou item antigo sem o campo."""
        self.assertFalse(retencao.sessao_vencida(None, AGORA))
        self.assertFalse(retencao.sessao_vencida("", AGORA))
        self.assertFalse(retencao.sessao_vencida("lixo", AGORA))

    def test_le_o_iso_como_utc(self):
        """`updatedAt` é gravado com gmtime; ler no fuso da máquina deslocaria
        o corte em até 3 h, e um teste passaria numa máquina e falharia noutra."""
        exato = retencao.iso(AGORA - 30 * DIA)
        self.assertFalse(retencao.sessao_vencida(exato, AGORA))
        self.assertTrue(retencao.sessao_vencida(retencao.iso(AGORA - 30 * DIA - 1), AGORA))

    def test_so_identidade(self):
        s = {"bot_enabled": True, "lead_id": "l1", "agent_history": [1], "atendimento": {}, "campanha": {}}
        self.assertEqual(retencao.so_identidade(s), {"bot_enabled": True, "lead_id": "l1"})


class TabelaFalsa:
    def __init__(self, item=None):
        self.item = item
        self.puts = []
        self.updates = []

    def get_item(self, Key):
        return {"Item": self.item} if self.item else {}

    def put_item(self, Item, **kw):
        self.puts.append(Item)
        self.item = Item

    def update_item(self, **kw):
        self.updates.append(kw)
        return {}


class TestEscritoresDeSessao(unittest.TestCase):
    def test_marca_de_elegibilidade_renova_o_ttl(self):
        t = TabelaFalsa()
        mark_conversation_eligible(t, "c", "5511999990000")
        self.assertAlmostEqual(t.puts[0]["ttl"], retencao.ttl_da_sessao(), delta=5)

    def test_grava_atendimento_item_novo_tem_ttl(self):
        t = TabelaFalsa()
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA)
        self.assertTrue(grava_atendimento(t, "c", "5511999990000", s))
        self.assertAlmostEqual(t.puts[0]["ttl"], retencao.ttl_da_sessao(), delta=5)

    def test_grava_atendimento_update_renova_o_ttl_na_raiz(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA)
        t = TabelaFalsa({"pk": "CLINIC#c", "sk": "PHONE#5511999990000", "session": dict(s)})
        self.assertTrue(grava_atendimento(t, "c", "5511999990000", s))
        u = t.updates[0]
        self.assertIn("#ttl = :ttl", u["UpdateExpression"])
        self.assertEqual(u["ExpressionAttributeNames"]["#ttl"], "ttl")
        self.assertNotIn("#s.#ttl", u["UpdateExpression"], "ttl e da raiz do item, nao da sessao")
        self.assertAlmostEqual(u["ExpressionAttributeValues"][":ttl"], retencao.ttl_da_sessao(), delta=5)

    def test_vinculo_lid_nao_tem_ttl(self):
        t = TabelaFalsa()
        vincula_lid(t, "c", "123@lid", "5511999990000")
        self.assertNotIn("ttl", t.puts[0])


class TestFonteUnicaPorAst(unittest.TestCase):
    """Todo `Item={...}` literal gravado com sk `PHONE#...` carrega `ttl`; os de
    `LID#` não. Pega o escritor novo que alguém escreva sem olhar para cá."""

    def _itens_literais(self):
        for caminho in RAIZ.rglob("*.py"):
            arvore = ast.parse(caminho.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if not isinstance(no, ast.Dict):
                    continue
                chaves = {k.value: v for k, v in zip(no.keys, no.values)
                          if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                sk = chaves.get("sk")
                if sk is None:
                    continue
                prefixo = ""
                if isinstance(sk, ast.JoinedStr) and sk.values and isinstance(sk.values[0], ast.Constant):
                    prefixo = str(sk.values[0].value)
                # So itens de sessao carregam `session`; `sk` pode vir de variavel
                # (session_store monta `sk = f"PHONE#{phone}"` antes do dict).
                if "session" in chaves:
                    prefixo = prefixo or "PHONE#"
                yield caminho.relative_to(RAIZ), prefixo, chaves

    def test_phone_tem_ttl_e_lid_nao(self):
        vistos = {"PHONE#": 0, "LID#": 0}
        for arquivo, prefixo, chaves in self._itens_literais():
            if prefixo.startswith("PHONE#") and "session" in chaves:
                vistos["PHONE#"] += 1
                with self.subTest(arquivo=str(arquivo)):
                    self.assertIn("ttl", chaves, f"{arquivo}: sessao PHONE# gravada sem ttl")
            elif prefixo.startswith("LID#"):
                vistos["LID#"] += 1
                with self.subTest(arquivo=str(arquivo)):
                    self.assertNotIn("ttl", chaves, f"{arquivo}: LID# nao vence")
        self.assertGreaterEqual(vistos["PHONE#"], 5, "o teste tem que estar vendo os cinco escritores")
        self.assertGreaterEqual(vistos["LID#"], 1)


class TestEventos(unittest.TestCase):
    def _tracker(self):
        from src.services.message_tracker import MessageTracker
        t = object.__new__(MessageTracker)
        t.table = TabelaFalsa()
        return t

    def test_todo_evento_nasce_com_ttl_de_60_dias(self):
        from src.providers.whatsapp_provider import IncomingMessage
        t = self._tracker()
        t.track_outbound("c", "55", "m1", "c#55", "TEXT", "oi", "SENT")
        t.track_inbound("c", "55", "m2", "c#55", IncomingMessage(
            message_id="m2", phone="55", sender_name="x", timestamp=0, message_type="TEXT", content="oi"))
        t.update_status("c", "55", "m1", "DELIVERED", timestamp=AGORA)
        for item in t.table.puts[:2]:
            self.assertAlmostEqual(item["ttl"], retencao.ttl_do_evento(), delta=5)
        self.assertEqual(t.table.puts[2]["ttl"], AGORA + 60 * DIA, "status usa o instante do evento")

    def test_desde_corta_na_chave_e_nao_em_filtro(self):
        t = self._tracker()
        capturado = {}

        def query(**kw):
            capturado.update(kw)
            return {"Items": []}
        t.table.query = query
        t.get_conversation_messages("c", "55", limit=20, desde=AGORA - 30 * DIA)
        self.assertNotIn("FilterExpression", capturado)
        expr = capturado["KeyConditionExpression"]
        valores = expr.get_expression()["values"]
        # (pk = ...) AND (sk BETWEEN MSG#<iso> AND MSG#~)
        limites = valores[1].get_expression()["values"]
        self.assertEqual(limites[1], f"MSG#{retencao.iso(AGORA - 30 * DIA)}")
        self.assertEqual(limites[2], "MSG#~")

    def test_sem_desde_le_tudo_como_antes(self):
        t = self._tracker()
        capturado = {}

        def query(**kw):
            capturado.update(kw)
            return {"Items": []}
        t.table.query = query
        t.get_conversation_messages("c", "55", limit=5)
        self.assertEqual(capturado["KeyConditionExpression"].get_expression()["operator"], "=")


if __name__ == "__main__":
    unittest.main()
