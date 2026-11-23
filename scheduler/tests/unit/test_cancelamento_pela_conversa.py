# -*- coding: utf-8 -*-
"""PRD 059: o cancelamento feito pelo bot termina com o texto da clínica,
palavra por palavra, convidando a remarcar pelo site.

Em 60 dias de prod (medição de 23/11/2026) o bot cancelou 4 vezes e a
resposta foi a que o modelo quis. Aqui a resposta não é dele.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import cancelamento_pela_conversa as C
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, mensagem, monta_agente, texto_do_modelo, usa_tool,
)

LINK = "https://agendar.x.com.br/"


class TemplateVazio:
    def get_and_render(self, clinic_id, chave, variables=None):
        return ""


class TemplateDaClinica:
    def __init__(self, por_chave):
        self.por_chave = por_chave

    def get_and_render(self, clinic_id, chave, variables=None):
        t = self.por_chave.get(chave, "")
        for k, v in (variables or {}).items():
            t = t.replace("{{%s}}" % k, v)
        return t


class TemplateQueFalha:
    def get_and_render(self, *a, **k):
        raise RuntimeError("banco fora")


class TestMensagem(unittest.TestCase):
    def test_com_link_tem_o_texto_da_clinica_e_o_link(self):
        m = C.mensagem(TemplateVazio(), CLINIC, LINK)
        self.assertTrue(m.startswith(C.TEXTO))
        self.assertIn("link de agendamento", m)
        self.assertTrue(m.endswith(LINK))
        self.assertNotIn("{{", m)

    def test_sem_link_nao_fala_em_link(self):
        m = C.mensagem(TemplateVazio(), CLINIC, None)
        self.assertTrue(m.startswith(C.TEXTO))
        self.assertNotIn("link", m)
        self.assertIn("remarcar", m)

    def test_template_da_clinica_vence_o_padrao(self):
        ts = TemplateDaClinica({C.CHAVE: "Cancelado, querida!", C.CHAVE_DO_LINK: "Remarque em {{link}}"})
        self.assertEqual(C.mensagem(ts, CLINIC, LINK), "Cancelado, querida!\n\nRemarque em " + LINK)

    def test_banco_fora_cai_no_padrao(self):
        m = C.mensagem(TemplateQueFalha(), CLINIC, LINK)
        self.assertTrue(m.startswith(C.TEXTO))
        self.assertIn(LINK, m)


class TestNoAgente(unittest.TestCase):
    """Depois de cancel_appointment, o que sai é a confirmação padrão, não a
    fala do modelo. book_appointment segue como era."""

    def _agente(self, roteiro, dominio=None):
        agente = monta_agente(anthropic=AnthropicRoteiro(roteiro),
                              resultado_da_tool={"success": True, "appointment_id": "a1"},
                              paciente={"id": "p1", "full_name": "Fulana"})
        agente.template_service = TemplateVazio()
        agente._clinica = lambda c: {"clinic_id": c, "custom_domain": dominio}
        return agente

    def test_cancelou_sai_a_confirmacao_padrao_com_link(self):
        agente = self._agente([usa_tool("cancel_appointment", {"appointment_id": "a1"}),
                               texto_do_modelo("Pronto, cancelei sua sessão.")], dominio="agendar.x.com.br")
        saida = agente.process_message(CLINIC, mensagem("preciso cancelar"))
        textos = [m.content for m in saida if m.message_type == "text"]
        self.assertEqual(len(textos), 1)
        self.assertTrue(textos[0].startswith(C.TEXTO), textos[0])
        self.assertIn(LINK, textos[0])
        self.assertNotIn("Pronto, cancelei", textos[0])

    def test_sem_dominio_a_confirmacao_nao_tem_link(self):
        agente = self._agente([usa_tool("cancel_appointment", {"appointment_id": "a1"}),
                               texto_do_modelo("Cancelado!")])
        saida = agente.process_message(CLINIC, mensagem("preciso cancelar"))
        textos = [m.content for m in saida if m.message_type == "text"]
        self.assertEqual(len(textos), 1)
        self.assertTrue(textos[0].startswith(C.TEXTO))
        self.assertNotIn("http", textos[0])

    def test_cancelamento_que_falhou_nao_manda_a_confirmacao(self):
        agente = monta_agente(anthropic=AnthropicRoteiro([
            usa_tool("cancel_appointment", {"appointment_id": "a1"}),
            texto_do_modelo("Não encontrei esse agendamento, pode me confirmar a data?"),
        ]), resultado_da_tool={"error": "nao encontrado"}, paciente={"id": "p1"})
        agente._clinica = lambda c: {"clinic_id": c, "custom_domain": "agendar.x.com.br"}
        saida = agente.process_message(CLINIC, mensagem("preciso cancelar"))
        textos = [m.content for m in saida if m.message_type == "text"]
        self.assertEqual(len(textos), 1)
        self.assertNotIn(C.TEXTO, textos[0])
        self.assertIn("confirmar a data", textos[0])


if __name__ == "__main__":
    unittest.main()
