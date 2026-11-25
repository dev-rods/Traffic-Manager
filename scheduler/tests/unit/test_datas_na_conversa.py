# -*- coding: utf-8 -*-
"""Datas: o bot mostra a agenda em vez de perguntar "tem data em mente?", e a
lista numerada nunca sai duas vezes (PRD 064, 25/11/2026)."""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import opcoes_numeradas, pergunta_de_data, pergunta_em_aberto
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, ToolExecutorFalso, mensagem, monta_agente, texto_do_modelo, usa_tool,
)

DATAS = [{"id": "2026-12-03", "label": "Qui, 3 de dez"}, {"id": "2026-12-04", "label": "Sex, 4 de dez"},
         {"id": "2027-01-15", "label": "Sex, 15 de jan"}, {"id": "2027-01-29", "label": "Sex, 29 de jan"}]


class TestPedeDataEmMente(unittest.TestCase):
    def test_pergunta_aberta_de_data(self):
        for t in ["Agora me diz, você tem data em mente ou posso te mostrar as próximas disponíveis?",
                  "Tem alguma data em mente?", "Qual a melhor data pra você?", "Você prefere algum dia?"]:
            self.assertTrue(pergunta_de_data.pede_data_sem_consulta(t), t)

    def test_oferecer_ver_as_datas_tambem_e_pedido(self):
        self.assertTrue(pergunta_de_data.oferece_ver_as_datas("Quer que eu veja as datas disponíveis?"))

    def test_com_datas_na_mensagem_nao_e(self):
        self.assertFalse(pergunta_de_data.pede_data_sem_consulta(
            "As próximas datas são 03/12 e 04/12. Qual dia fica melhor pra você?"))


class TestSemAsOpcoes(unittest.TestCase):
    def test_tira_a_lista_que_o_modelo_escreveu(self):
        texto = ("Horários dependem da data - me diz qual prefere:\n\n"
                 "1. Qui, 3 de dez\n2. Sex, 4 de dez\n3. Sex, 15 de jan\n4. Sex, 29 de jan")
        self.assertEqual(opcoes_numeradas.sem_as_opcoes(texto, DATAS),
                         "Horários dependem da data - me diz qual prefere:")

    def test_texto_sem_lista_fica_igual(self):
        self.assertEqual(opcoes_numeradas.sem_as_opcoes("Qual dessas datas fica melhor?", DATAS),
                         "Qual dessas datas fica melhor?")
        self.assertEqual(opcoes_numeradas.sem_as_opcoes("", DATAS), "")


class TestRespondeuAgenda(unittest.TestCase):
    def test_oferecer_datas_responde_pergunta_de_horario(self):
        self.assertTrue(pergunta_em_aberto.respondeu(
            "Horários dependem da data escolhida - me diz qual dessas prefere:", "Qual sao os horários disponíveis?"))


class TestNoAgente(unittest.TestCase):
    def _opcoes(self):
        return {"content": [{"type": "tool_use", "id": "t1", "name": "present_options",
                             "input": {"message": "Qual dessas datas fica melhor pra você?", "options": DATAS}}],
                "stop_reason": "tool_use"}

    def test_lista_numerada_sai_uma_vez_mesmo_se_o_modelo_a_escrever(self):
        class Executor(ToolExecutorFalso):
            def execute(self, nome, args, context=None):
                self.chamadas.append(nome)
                if nome == "present_options":
                    return {"presented": True, **args}
                return {"available_dates": [{"date": d["id"], "label": d["label"]} for d in DATAS]}

        anthropic = AnthropicRoteiro([
            usa_tool("check_availability", {"service_area_pairs": []}),
            self._opcoes(),
            texto_do_modelo("Horários dependem da data - me diz qual prefere:\n\n1. Qui, 3 de dez\n2. Sex, 4 de dez\n3. Sex, 15 de jan\n4. Sex, 29 de jan"),
        ])
        agente = monta_agente(anthropic=anthropic, tool_executor=Executor())
        saida = agente.process_message(CLINIC, mensagem("quais os horários?"))
        self.assertEqual(len(saida), 1)
        self.assertEqual(saida[0].content.count("Qui, 3 de dez"), 1)
        self.assertIn("1. Qui, 3 de dez", saida[0].content)

    def test_data_em_mente_vira_consulta_obrigatoria(self):
        class Executor(ToolExecutorFalso):
            def execute(self, nome, args, context=None):
                self.chamadas.append(nome)
                if nome == "present_options":
                    return {"presented": True, **args}
                if nome == "check_availability":
                    return {"available_dates": [{"date": d["id"], "label": d["label"]} for d in DATAS]}
                return {"discount_pct": 15, "original_price_display": "R$ 185,00", "discounted_price_display": "R$ 157,25"}

        anthropic = AnthropicRoteiro([
            usa_tool("calculate_discount", {"service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}),
            texto_do_modelo("Fechado: buço + meia perna. Agora me diz, você tem data em mente ou posso te mostrar as próximas disponíveis?"),
            usa_tool("check_availability", {"service_area_pairs": []}),
            self._opcoes(),
            texto_do_modelo("Fechado: buço + meia perna. Essas são as próximas datas:"),
        ])
        agente = monta_agente(anthropic=anthropic, tool_executor=Executor())
        saida = agente.process_message(CLINIC, mensagem("meia"))
        self.assertGreaterEqual(anthropic.chamadas, 4)
        self.assertIn("check_availability", agente.tool_executor.chamadas)
        self.assertEqual(len(saida), 1)
        self.assertIn("1. Qui, 3 de dez", saida[0].content)
        self.assertNotIn("data em mente", saida[0].content)
