# -*- coding: utf-8 -*-
"""O webhook decide quem espera, quem agenda e quando a resposta é descartada.

O agregador guarda e devolve mensagem; aqui é onde as decisões acontecem, e
onde um erro é caro: agendar por mensagem traz de volta o defeito original, e
descartar resposta de uma rodada que já gravou no banco deixa a paciente com um
agendamento que ela não sabe que tem.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.functions.webhook import handler as wh

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"


class TestJanelaDaClinica(unittest.TestCase):
    def test_valor_da_clinica_manda(self):
        self.assertEqual(wh._janela_da_clinica({"debounce_seconds": 15}), 15)

    def test_ausente_cai_no_padrao(self):
        self.assertEqual(wh._janela_da_clinica({}), wh.JANELA_PADRAO_SEGUNDOS)
        self.assertEqual(wh._janela_da_clinica({"debounce_seconds": None}),
                         wh.JANELA_PADRAO_SEGUNDOS)

    def test_zero_desliga_o_agrupamento(self):
        """Precisa ser possível desligar sem deploy se algo der errado."""
        self.assertEqual(wh._janela_da_clinica({"debounce_seconds": 0}), 0)

    def test_valor_absurdo_e_limitado(self):
        """Um 3600 digitado no painel derrubaria a Lambda por timeout, e o
        sintoma seria o bot mudo - não um erro."""
        self.assertEqual(wh._janela_da_clinica({"debounce_seconds": 3600}),
                         wh.JANELA_MAXIMA_SEGUNDOS)
        self.assertEqual(wh._janela_da_clinica({"debounce_seconds": -5}), 0)

    def test_lixo_cai_no_padrao(self):
        self.assertEqual(wh._janela_da_clinica({"debounce_seconds": "abc"}),
                         wh.JANELA_PADRAO_SEGUNDOS)


class TestDescarteDaResposta(unittest.TestCase):
    """Descartar é o certo quando a pessoa completou a frase - menos quando a
    rodada já mexeu no banco."""

    def setUp(self):
        mock.patch.object(wh, "_get_sessions_table").start()
        self.chegou = mock.patch.object(wh, "chegou_mensagem_nova").start()
        self.sessao = mock.patch.object(wh, "_load_session", return_value={}).start()
        self.addCleanup(mock.patch.stopall)

    def test_ninguem_escreveu_entao_a_resposta_vai(self):
        self.chegou.return_value = False

        self.assertFalse(wh._pode_descartar(CLINIC, PHONE))

    def test_escreveu_no_meio_entao_descarta(self):
        self.chegou.return_value = True

        self.assertTrue(wh._pode_descartar(CLINIC, PHONE))

    def test_agendamento_gravado_nao_se_descarta(self):
        """book_appointment já rodou: existe uma sessão marcada no banco e calar
        aqui deixaria a paciente sem saber."""
        self.chegou.return_value = True
        self.sessao.return_value = {"efeito_na_ultima_rodada": True}

        self.assertFalse(wh._pode_descartar(CLINIC, PHONE))

    def test_falha_na_conferencia_envia_a_resposta(self):
        """Falha fechada: perder resposta é pior que mandar uma desatualizada."""
        self.chegou.side_effect = RuntimeError("dynamo fora")

        self.assertFalse(wh._pode_descartar(CLINIC, PHONE))


class TestOAgenteMarcaOEfeito(unittest.TestCase):
    """O webhook lê `efeito_na_ultima_rodada` da sessão; se o agente parar de
    gravar, o descarte volta a poder engolir um agendamento."""

    def _sessao_depois_de(self, roteiro, resultado_da_tool=None):
        from tests.unit.dublagem_agente import (
            AnthropicRoteiro, CLINIC as C, mensagem, monta_agente,
        )
        agente = monta_agente(anthropic=AnthropicRoteiro(roteiro),
                              resultado_da_tool=resultado_da_tool)
        agente.process_message(C, mensagem("oi"))
        return agente.sessao_salva

    def test_sem_tool_de_efeito_fica_falso(self):
        from tests.unit.dublagem_agente import texto_do_modelo

        sessao = self._sessao_depois_de([texto_do_modelo("Oi! Tudo bem?")])

        self.assertFalse(sessao.get("efeito_na_ultima_rodada"))

    def test_book_appointment_marca_verdadeiro(self):
        from tests.unit.dublagem_agente import texto_do_modelo, usa_tool

        sessao = self._sessao_depois_de(
            [usa_tool("book_appointment"), texto_do_modelo("Agendado!")],
            resultado_da_tool={"success": True, "appointment_id": "x"},
        )

        self.assertTrue(sessao.get("efeito_na_ultima_rodada"))


if __name__ == "__main__":
    unittest.main()
