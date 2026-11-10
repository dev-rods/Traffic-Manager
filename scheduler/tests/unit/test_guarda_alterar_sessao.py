# -*- coding: utf-8 -*-
"""O que o agente oferece ao modelo quando a pessoa JÁ TEM sessão (PRD 045).

Os dois casos reais (Nobre 05/11, Essência 09/11) falharam porque o ambiente
não tinha o caminho "alterar": a agenda contava a vaga dela, não havia tool
para áreas, e o prompt só sabia marcar. Aqui se mede o ambiente que o modelo
recebe num turno dessa pessoa - as tools, o bloco de conduta, a pré-carga - e
o que acontece depois de ele alterar.
"""
import unittest

from tests.unit.dublagem_agente import (
    CLINIC,
    AnthropicRoteiro,
    ToolExecutorFalso,
    mensagem,
    monta_agente,
    texto_do_modelo,
    usa_tool,
)
from src.services import estado_comercial as ec
from src.services.roteador import tools_obrigatorias

FUTURO = {"id": "ap-18", "data": "2026-11-18", "hora": "14:50", "areas": "Axilas, Buço, Linha alba"}
COM_SESSAO = {"encontrado": True, "nome": "Fulana", "cadastro_completo": True,
              "sessoes_feitas": 2, "ultima_sessao": "2026-09-24", "agendamento_futuro": FUTURO}
ESTREIA = dict(COM_SESSAO, sessoes_feitas=0, ultima_sessao=None)
SEM_SESSAO = dict(COM_SESSAO, agendamento_futuro=None)
LEAD = {"encontrado": False}

ALTERADO = {"success": True, "appointment_id": "ap-18", "date": "2026-11-18",
            "date_label": "Qua, 18/11", "time": "14:50", "areas": "Axilas",
            "duration_minutes": 5, "final_price_cents": 9500, "horario_mantido": True}


def roda(paciente, roteiro, resultado_da_tool=None, texto="só a axila"):
    vistas = {}
    anthropic = AnthropicRoteiro(roteiro)
    original = anthropic.create_message

    def create_message(system, messages, tools, max_tokens, tool_choice=None):
        vistas.setdefault("tools", {t["name"] for t in tools})
        vistas.setdefault("system", system)
        vistas.setdefault("turno", messages[-1]["content"] if messages else "")
        return original(system, messages, tools, max_tokens, tool_choice)

    anthropic.create_message = create_message
    executor = ToolExecutorFalso(resultado_da_tool or ALTERADO)
    agente = monta_agente(anthropic=anthropic, tool_executor=executor, paciente=paciente)
    saida = agente.process_message(CLINIC, mensagem(texto))
    return agente, saida, vistas


class TestOAmbienteDeQuemTemSessao(unittest.TestCase):
    def test_enxerga_alterar_e_o_bloco_aponta_para_ele(self):
        _, _, v = roda(COM_SESSAO, [texto_do_modelo("Então fica só axilas, 18/11 às 14:50 - é isso?")])
        self.assertIn("alterar_agendamento", v["tools"])
        self.assertIn("2b. SESSÃO JÁ MARCADA", v["system"])
        self.assertIn("Nunca book_appointment para isso", v["system"])

    def test_o_turno_mostra_o_que_ela_tem_marcado(self):
        """QUEM É com as áreas, em dd/mm: o modelo lê "só a axila" como
        "tirar buço e linha alba", e não copia ISO para a pessoa."""
        _, _, v = roda(COM_SESSAO, [texto_do_modelo("ok")])
        self.assertIn("18/11/2026 às 14:50 - Axilas, Buço, Linha alba", v["turno"])
        self.assertIn("ALTERAÇÃO (alterar_agendamento)", v["turno"])
        self.assertNotIn("As áreas desta sessão você pergunta", v["turno"])

    def test_lookup_e_pre_carregado_sem_depender_da_frase(self):
        """"só a axila" não casa com AGENDAMENTO_PROPRIO; o estado basta."""
        agente, _, _ = roda(COM_SESSAO, [texto_do_modelo("ok")])
        self.assertIn("lookup_appointments", agente.tool_executor.chamadas)

    def test_estreia_tambem(self):
        agente, _, v = roda(ESTREIA, [texto_do_modelo("ok")])
        self.assertIn("alterar_agendamento", v["tools"])
        self.assertIn("lookup_appointments", agente.tool_executor.chamadas)


class TestQuemNaoTemSessao(unittest.TestCase):
    def test_lead_nova_nao_enxerga_alterar_nem_pre_carrega_lookup(self):
        agente, _, v = roda(LEAD, [texto_do_modelo("ok")], texto="quero axilas")
        self.assertNotIn("alterar_agendamento", v["tools"])
        self.assertNotIn("lookup_appointments", agente.tool_executor.chamadas)

    def test_paciente_sem_proxima_continua_ouvindo_pergunte_as_areas(self):
        _, _, v = roda(SEM_SESSAO, [texto_do_modelo("ok")], texto="quero axilas")
        self.assertNotIn("alterar_agendamento", v["tools"])
        self.assertIn("pergunta e confirma com ela", v["turno"])


class TestDepoisDeAlterar(unittest.TestCase):
    def test_alterar_e_efeito_e_leva_o_preparo(self):
        """A mesma trilha de book: a confirmação sai e o aviso pré-sessão vem
        junto - ela continua com sessão marcada, com preparo a fazer."""
        agente, saida, _ = roda(COM_SESSAO, [
            usa_tool("alterar_agendamento", {"appointment_id": "ap-18",
                                             "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}),
            texto_do_modelo("Pronto! Sua sessão de 18/11 às 14:50 agora é só axilas."),
        ])
        self.assertIn("alterar_agendamento", agente.tool_executor.chamadas)
        textos = [m.content for m in saida]
        self.assertTrue(any("14:50" in t for t in textos))
        self.assertGreaterEqual(len(textos), 2, "o aviso pré-sessão acompanha a confirmação")


class TestPreCargaPorEstado(unittest.TestCase):
    def test_estado_com_sessao_inclui_lookup_depois_de_identificar(self):
        for estado in (ec.FIRST_BOOKING, ec.ACTIVE_CUSTOMER):
            t = tools_obrigatorias(set(), estado)
            self.assertEqual(t, ["identificar_paciente", "lookup_appointments"], estado)

    def test_outros_estados_nao_mudam(self):
        for estado in (ec.NEW_LEAD, ec.NO_NEXT_BOOKING, None):
            self.assertEqual(tools_obrigatorias(set(), estado), [], estado)


if __name__ == "__main__":
    unittest.main()
