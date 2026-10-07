# -*- coding: utf-8 -*-
"""A cadeia inteira, do disparo à resposta do bot.

Cada peça tem teste próprio, e mesmo assim o fluxo pode estar morto: foi o que
aconteceu com a agregação de rajada, com todas as peças verdes e a permissão de
IAM faltando. Aqui as peças reais são ligadas umas nas outras, sem dublê entre
elas, e o que se mede é o percurso.

Percurso da campanha (o que tem de acontecer):
  disparo grava a campanha na sessão
  → a sessão passa a EXISTIR, então a checagem de conversa anterior nem roda
  → should_bot_reply libera sob LEADS_ONLY
  → o prompt ganha o bloco de campanha

Percurso do lead (o que NÃO pode mudar):
  sem campanha, cada passo se comporta exatamente como antes.
"""
import time
import unittest
from unittest import mock

from src.services.bot_policy import POLICY_LEADS_ONLY, should_bot_reply
from src.services.campanha import abre, esta_viva
from src.services.conversation_agent import ConversationAgent

CLINIC_LEADS_ONLY = {"bot_autoreply_policy": POLICY_LEADS_ONLY, "use_agent": True}
FONE = "5511970522647"
DATAS = ["2026-10-07", "2026-10-14", "2026-10-21"]


class TabelaFalsa:
    """Guarda itens em memória, com a mesma forma do DynamoDB."""

    def __init__(self):
        self.itens = {}

    def get_item(self, Key):
        item = self.itens.get((Key["pk"], Key["sk"]))
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.itens[(Item["pk"], Item["sk"])] = Item


def agente_real():
    a = object.__new__(ConversationAgent)
    a.db = mock.MagicMock()
    a.db.execute_query.side_effect = lambda sql, params=None: (
        [{"name": "Maria Silva"}] if "FROM scheduler.patients" in sql else []
    )
    a.template_service = mock.MagicMock()
    a.template_service.get_and_render.return_value = "PROMPT BASE"
    return a


class TestPercursoDaCampanha(unittest.TestCase):
    def setUp(self):
        from src.services.session_store import abre_campanha

        self.tabela = TabelaFalsa()
        # 1. O disparo grava - a função real, não um dublê.
        self.gravou = abre_campanha(
            self.tabela, "clinica-x", FONE, abre(DATAS, agora=int(time.time())))
        self.sessao = self.tabela.itens[("CLINIC#clinica-x", f"PHONE#{FONE}")]["session"]

    def test_o_disparo_grava(self):
        self.assertTrue(self.gravou)
        self.assertTrue(esta_viva(self.sessao))

    def test_a_sessao_passa_a_existir(self):
        """É o que faz a checagem de conversa anterior nem rodar.

        O webhook só pergunta 'já havia conversa antes de nós?' quando a sessão
        não existe (`primeira_vez = not session`). Toda paciente cadastrada tem
        histórico no WhatsApp, e essa pausa é permanente - sem a sessão criada
        no disparo, a base inteira ficaria muda para sempre.
        """
        self.assertTrue(bool(self.sessao), "sem sessão, PAUSA_CHAT_ANTERIOR pega todas")

    def test_o_bot_responde(self):
        self.assertTrue(should_bot_reply(CLINIC_LEADS_ONLY, self.sessao, FONE))

    def test_o_prompt_ganha_o_bloco(self):
        prompt = agente_real()._build_system_prompt("clinica-x", FONE, self.sessao)
        self.assertIn("CONVERSA DE CAMPANHA", prompt)
        for d in DATAS:
            self.assertIn(d, prompt)

    def test_a_campanha_zera_a_conversa_anterior(self):
        """Campanha COMEÇA uma conversa - não continua a do mês passado.

        Achado no piloto de 09/09/2026: o número de teste tinha 36 turnos de
        05 dias antes parados na sessão. O bloco de campanha diz "acabamos de
        te escrever" e o histórico dizia outra coisa - e na prática quem manda
        é o histórico, porque é ele que vai nas mensagens do modelo.

        Sem TTL na tabela, isso não se resolve sozinho: o mês que vem teria a
        conversa deste mês por baixo.
        """
        from src.services.session_store import abre_campanha

        sessao = self.tabela.itens[("CLINIC#clinica-x", f"PHONE#{FONE}")]["session"]
        sessao["agent_history"] = [{"role": "user", "content": "mes passado"}]
        sessao["state"] = "WELCOME"

        abre_campanha(self.tabela, "clinica-x", FONE, abre(DATAS))

        nova = self.tabela.itens[("CLINIC#clinica-x", f"PHONE#{FONE}")]["session"]
        self.assertEqual(nova["agent_history"], [])
        self.assertNotIn("state", nova)

    def test_mas_preserva_o_que_nao_e_conversa(self):
        """Zerar o histórico não pode levar junto quem é a pessoa."""
        from src.services.session_store import abre_campanha

        sessao = self.tabela.itens[("CLINIC#clinica-x", f"PHONE#{FONE}")]["session"]
        sessao["lead_id"] = "lead-123"
        sessao["bot_enabled"] = True

        abre_campanha(self.tabela, "clinica-x", FONE, abre(DATAS))

        nova = self.tabela.itens[("CLINIC#clinica-x", f"PHONE#{FONE}")]["session"]
        self.assertEqual(nova["lead_id"], "lead-123")
        self.assertTrue(nova["bot_enabled"])

    def test_a_campanha_nao_apaga_o_resto_da_sessao(self):
        """Ler-mesclar-gravar: só PutItem apagaria o histórico já acumulado."""
        from src.services.session_store import abre_campanha

        self.tabela.itens[("CLINIC#clinica-x", f"PHONE#{FONE}")]["session"]["lead_id"] = "L1"
        abre_campanha(self.tabela, "clinica-x", FONE, abre(DATAS))

        sessao = self.tabela.itens[("CLINIC#clinica-x", f"PHONE#{FONE}")]["session"]
        self.assertEqual(sessao["lead_id"], "L1")
        self.assertTrue(esta_viva(sessao))


class TestPercursoDoLeadNaoMuda(unittest.TestCase):
    """A outra metade do pedido: o fluxo antigo intacto."""

    def test_lead_continua_respondendo(self):
        self.assertTrue(should_bot_reply(CLINIC_LEADS_ONLY, {"bot_enabled": True}, FONE))

    def test_desconhecido_continua_mudo(self):
        self.assertFalse(should_bot_reply(CLINIC_LEADS_ONLY, {}, FONE))

    def test_o_prompt_do_lead_e_identico_ao_de_antes(self):
        a = agente_real()
        self.assertEqual(a._build_system_prompt("clinica-x", FONE),
                         a._build_system_prompt("clinica-x", FONE, {"bot_enabled": True}))


class TestCampanhaVencida(unittest.TestCase):
    """No 8º dia tudo volta ao que era, sem ninguém precisar limpar nada."""

    def setUp(self):
        velha = abre(DATAS, agora=int(time.time()) - 8 * 86400)
        self.sessao = {"campanha": velha}

    def test_o_bot_cala(self):
        self.assertFalse(should_bot_reply(CLINIC_LEADS_ONLY, self.sessao, FONE))

    def test_o_prompt_perde_o_bloco(self):
        prompt = agente_real()._build_system_prompt("clinica-x", FONE, self.sessao)
        self.assertNotIn("CONVERSA DE CAMPANHA", prompt)


if __name__ == "__main__":
    unittest.main()
