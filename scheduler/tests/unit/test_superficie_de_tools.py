# -*- coding: utf-8 -*-
"""O que o modelo enxerga e consegue chamar está de fato ligado.

Esta é a costura que já quebrou duas vezes sem a suíte perceber:

  - `calcula_duracao` existia e o agente a usava, mas ninguém a importava:
    NameError em produção, com todos os testes verdes, porque nenhum teste
    exercitava `process_message`.
  - `calculate_duration` não existia como tool. O prompt mandava consultar a
    duração e não havia o que chamar - o modelo não desobedeceu, não tinha
    como obedecer.

São asserções baratas sobre a fronteira: existe, está exposto, está ligado.
"""
import inspect
import unittest

from src.services.ai_tools import ToolExecutor, get_tool_definitions


def nomes_expostos():
    return {t["name"] for t in get_tool_definitions(format="anthropic")}


class TestToolsExpostasAoModelo(unittest.TestCase):
    def test_as_tools_que_o_fluxo_depende_estao_expostas(self):
        expostas = nomes_expostos()
        for nome in ("calculate_duration", "sem_consulta_necessaria",
                     "get_faq_answer", "get_time_slots", "check_availability",
                     "book_appointment", "request_human_handoff"):
            with self.subTest(tool=nome):
                self.assertIn(nome, expostas)

    def test_toda_tool_exposta_tem_executor(self):
        """Tool anunciada sem executor vira 'Unknown tool' em runtime."""
        for nome in nomes_expostos():
            with self.subTest(tool=nome):
                self.assertTrue(
                    hasattr(ToolExecutor, f"_tool_{nome}"),
                    f"{nome} está no schema mas não tem _tool_{nome}",
                )


class TestCosturaComOAgente(unittest.TestCase):
    """O NameError que passou: símbolos usados em process_message existiam nos
    seus módulos, mas não estavam importados no agente."""

    def test_simbolos_estao_ligados_no_modulo_do_agente(self):
        import src.services.conversation_agent as agente

        for nome in ("intencoes", "tools_obrigatorias", "exige_consulta",
                     "fatos_sem_origem", "fatos_de_agenda"):
            with self.subTest(simbolo=nome):
                self.assertTrue(callable(getattr(agente, nome, None)))


class TestDuracaoSoVemDaTool(unittest.TestCase):
    def test_list_areas_nao_expoe_duracao_por_area(self):
        """Ver a duração de cada área convida o modelo a somar sozinho - e a
        soma crua ignora piso, teto e arredondamento."""
        corpo = inspect.getsource(ToolExecutor._tool_list_areas)
        depois_do_select = corpo.split("areas.append")[1]

        self.assertNotIn('"duration_minutes"', depois_do_select)


class TestSaidaSemAdivinhacao(unittest.TestCase):
    """A tool que substituiu a inferência por formato da mensagem."""

    def test_nao_respalda_afirmacao_factual(self):
        """Devolve vazio: declarar que não consultou não pode virar respaldo."""
        from src.services.proveniencia import fatos_sem_origem

        executor = object.__new__(ToolExecutor)
        resultado = executor._tool_sem_consulta_necessaria(
            {"motivo": "paciente mandou o nome"}, "clinica", "5511999990000", {}
        )

        self.assertEqual(resultado, {})
        self.assertIn("18:00", fatos_sem_origem("Tenho 18:00.", [resultado]))


if __name__ == "__main__":
    unittest.main()
