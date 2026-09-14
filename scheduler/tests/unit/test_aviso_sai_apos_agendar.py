# -*- coding: utf-8 -*-
"""Fechou agendamento, o aviso pré-sessão sai - inteiro e sem passar pelo modelo.

O agente não é instruído a escrever o aviso: o código anexa a mensagem depois
que a tool gravou. A diferença importa porque o texto tem contraindicação
médica (Roacutan, gestante, herpes ativa) em 15 linhas, e "reproduza isto
palavra por palavra" é exatamente o tipo de pedido que modelo resume.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.orientacoes_pos_sessao import TEXTO
from tests.unit.dublagem_agente import (
    CLINIC,
    AnthropicRoteiro,
    mensagem,
    monta_agente,
    texto_do_modelo,
    usa_tool,
)


def roteiro_com(nome_da_tool, fala="Pronto, está confirmado!"):
    return AnthropicRoteiro([usa_tool(nome_da_tool), texto_do_modelo(fala)])


class TestDepoisDeAgendar(unittest.TestCase):
    def test_o_aviso_sai_como_mensagem_propria(self):
        agente = monta_agente(roteiro_com("book_appointment"),
                              resultado_da_tool={"appointment_id": "a-1"})
        saida = agente.process_message(CLINIC, mensagem("pode confirmar"))
        self.assertEqual(saida[-1].content, TEXTO)
        self.assertEqual(saida[-1].message_type, "text")

    def test_a_confirmacao_do_modelo_continua_vindo_antes(self):
        """O aviso acompanha a confirmação, não a substitui."""
        agente = monta_agente(roteiro_com("book_appointment"),
                              resultado_da_tool={"appointment_id": "a-1"})
        saida = agente.process_message(CLINIC, mensagem("pode confirmar"))
        self.assertEqual(len(saida), 2)
        self.assertIn("confirmado", saida[0].content.lower())

    def test_remarcacao_tambem_avisa(self):
        agente = monta_agente(roteiro_com("reschedule_appointment"),
                              resultado_da_tool={"appointment_id": "a-1"})
        saida = agente.process_message(CLINIC, mensagem("quero remarcar pra quinta"))
        self.assertEqual(saida[-1].content, TEXTO)


class TestQuandoNaoSai(unittest.TestCase):
    def test_cancelamento_nao_manda_preparo(self):
        """Mandar 'raspe os pelos' a quem acabou de cancelar é o oposto de cuidado."""
        agente = monta_agente(roteiro_com("cancel_appointment", "Cancelado."),
                              resultado_da_tool={"cancelled": True})
        saida = agente.process_message(CLINIC, mensagem("quero cancelar"))
        self.assertNotIn(TEXTO, [m.content for m in saida])

    def test_conversa_comum_nao_manda_nada(self):
        agente = monta_agente(roteiro_com("get_faq_answer", "O laser é indolor."),
                              resultado_da_tool={"answers": []})
        saida = agente.process_message(CLINIC, mensagem("dói?"))
        self.assertNotIn(TEXTO, [m.content for m in saida])

    def test_tool_que_falhou_nao_avisa(self):
        """Sem agendamento gravado não há sessão para se preparar."""
        agente = monta_agente(roteiro_com("book_appointment", "Deu erro."),
                              resultado_da_tool={"error": "slot_taken"})
        saida = agente.process_message(CLINIC, mensagem("pode confirmar"))
        self.assertNotIn(TEXTO, [m.content for m in saida])


if __name__ == "__main__":
    unittest.main()
