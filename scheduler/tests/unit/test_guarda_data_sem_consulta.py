# -*- coding: utf-8 -*-
"""O guarda no laço: pedir data sem consultar não sai daqui (PRD 044).

O teste central não é o texto da correção, é o que a pessoa NÃO recebe: a
pergunta aberta não chega a ela. Numa clínica que atende em cerca de uma data
por mês, essa pergunta custa alguém aparecendo num dia que não existe.
"""
import unittest

from tests.unit.dublagem_agente import (
    CLINIC,
    PHONE,
    AnthropicRoteiro,
    ToolExecutorFalso,
    mensagem,
    monta_agente,
    texto_do_modelo,
    usa_tool,
)
from src.services.bot_policy import (
    CAMPO_DO_MOTIVO,
    MOTIVO_PEDIU_DATA_SEM_CONSULTA,
)
from src.services import atendimento

AREAS = {"service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}
# O resultado da tool tem de conter as datas que a resposta cita: senão a
# proveniência barra a mensagem boa, e o teste mediria o guarda errado.
DATAS = {"available_dates": [{"date": "2026-12-03", "label": "Qui, 03/12"},
                             {"date": "2026-12-10", "label": "Qui, 10/12"}]}
PERGUNTA_ABERTA = ("Fechado! Total: R$ 238,00.\n\nAgora me diz: qual data fica "
                   "melhor pra você?")
COM_AS_DATAS = ("Temos estas datas:\n1. Qui, 03/12\n2. Qui, 10/12\n\nQual delas "
                "fica melhor?")


def roda(roteiro, resultado_da_tool=None):
    executor = ToolExecutorFalso(resultado_da_tool or DATAS)
    agente = monta_agente(anthropic=AnthropicRoteiro(roteiro), tool_executor=executor)
    saida = agente.process_message(CLINIC, mensagem("Completa e perianal"))
    return agente, saida


def textos(saida):
    """As mensagens que iriam para a pessoa."""
    if isinstance(saida, dict):
        return [m.get("content", "") for m in (saida.get("messages") or [])] or \
               ([saida["text"]] if saida.get("text") else [])
    return [str(saida)] if saida else []


class TestRefazUmaVez(unittest.TestCase):
    def test_a_pergunta_aberta_nao_chega_a_pessoa(self):
        agente, saida = roda([
            usa_tool("calculate_discount", AREAS),   # as áreas ficam conhecidas
            texto_do_modelo(PERGUNTA_ABERTA),        # pede data sem consultar
            usa_tool("check_availability", AREAS),   # obrigado a consultar
            texto_do_modelo(COM_AS_DATAS),
        ])
        enviados = " ".join(textos(saida))
        self.assertNotIn("qual data fica melhor", enviados.lower())
        self.assertIn("03/12", enviados)

    def test_o_modelo_recebe_a_correcao_e_a_consulta_obrigatoria(self):
        agente, _ = roda([
            usa_tool("calculate_discount", AREAS),
            texto_do_modelo(PERGUNTA_ABERTA),
            usa_tool("check_availability", AREAS),
            texto_do_modelo(COM_AS_DATAS),
        ])
        correcoes = " ".join(agente.anthropic.correcoes)
        self.assertIn("sem consultar a agenda", correcoes)
        self.assertIn("check_availability", correcoes)
        # A volta seguinte vai com tool obrigatória (o que `forcar_proxima` liga)
        self.assertIn({"type": "any"}, agente.anthropic.forcados)


class TestInsistencia(unittest.TestCase):
    def test_insistiu_uma_pessoa_assume(self):
        agente, saida = roda([
            usa_tool("calculate_discount", AREAS),
            texto_do_modelo(PERGUNTA_ABERTA),
            texto_do_modelo(PERGUNTA_ABERTA),  # insistiu
        ])
        enviados = " ".join(textos(saida))
        self.assertNotIn("qual data fica melhor", enviados.lower())
        self.assertIn("especialista", enviados)
        bloco = atendimento.bloco(agente.sessao_salva)
        self.assertEqual(bloco.get(CAMPO_DO_MOTIVO), MOTIVO_PEDIU_DATA_SEM_CONSULTA)


class TestNaoBarraOQueEstaCerto(unittest.TestCase):
    def test_pergunta_depois_da_consulta_passa_intacta(self):
        agente, saida = roda([
            usa_tool("check_availability", AREAS),
            texto_do_modelo(COM_AS_DATAS),
        ])
        self.assertIn("03/12", " ".join(textos(saida)))
        self.assertEqual(agente.anthropic.correcoes, [])

    def test_sem_areas_no_turno_nao_barra(self):
        """Decisão §7.2: no começo da conversa o prompt manda NÃO consultar
        ainda. Barrar ali brigaria com uma regra que está certa."""
        agente, saida = roda([
            usa_tool("list_areas", {"service_ids": ["s1"]}),  # catálogo, não escolha
            texto_do_modelo("Qual data fica melhor pra você?"),
        ])
        self.assertEqual(agente.anthropic.correcoes, [])
        self.assertIn("qual data", " ".join(textos(saida)).lower())

    def test_a_variante_branda_nao_barra(self):
        """§7.3: "quer ver as datas?" é medido, não bloqueado."""
        agente, saida = roda([
            usa_tool("calculate_discount", AREAS),
            texto_do_modelo("Quer ver as datas disponíveis?"),
        ])
        self.assertEqual(agente.anthropic.correcoes, [])
        self.assertIn("datas", " ".join(textos(saida)).lower())


if __name__ == "__main__":
    unittest.main()
