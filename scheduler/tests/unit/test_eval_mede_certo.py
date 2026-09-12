# -*- coding: utf-8 -*-
"""O eval mede o que diz medir.

Em 04/09/2026 quatro defeitos de medição no eval custaram ~US$ 16 em rodadas
descartadas, e nenhum deles apareceu como erro - todos devolveram número
plausível:

  1. HUMAN_HANDOFF é grudento na sessão: um bloqueio no turno 6 contava como
     bloqueio nos turnos 7 a 11 também. Inflou 1 evento em 6.
  2. Handoff que o modelo pediu com request_human_handoff era contado como
     bloqueio do guardrail - acerto virava custo.
  3. DbFalso não servia message_templates, então o TemplateService caía em
     DEFAULT_TEMPLATES: dois baselines mediram um prompt de 6.115 chars que
     não está em produção.
  4. I1 conferia contra as tools da rodada, janela mais estrita que a de
     produção, e acusava violação onde o agente não bloquearia.

Estes testes rodam de graça e prendem os quatro. A regra que eles codificam:
antes de gastar numa rodada completa, o instrumento tem que provar que mede.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "eval-sem-dynamo")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "eval-sem-dynamo")

from src.services.conversation_agent import RESPALDO_GUARDADO
from tests.evaluation.eval_fluxo_agente import (
    FIXTURES,
    DbFalso,
    avalia_turno,
    custo,
    nota_valida,
)
from src.services.ai_tools import get_tool_definitions


class TestI3ContaEventoNaoEstado(unittest.TestCase):
    """Defeito 1: estado grudento inflava bloqueio."""

    def test_transicao_conta(self):
        v = avalia_turno("ok", [], [], None, "HUMAN_HANDOFF")
        self.assertTrue(v["I3_bloqueio"])

    def test_estado_que_ja_era_handoff_nao_conta_de_novo(self):
        v = avalia_turno("ok", [], [], "HUMAN_HANDOFF", "HUMAN_HANDOFF")
        self.assertFalse(v["I3_bloqueio"])


class TestI3IgnoraHandoffLegitimo(unittest.TestCase):
    """Defeito 2: o modelo pedir transferência é acerto dele, não custo."""

    def test_handoff_pedido_pelo_modelo_nao_e_bloqueio(self):
        v = avalia_turno("vou te transferir", ["request_human_handoff"],
                         ["request_human_handoff"], None, "HUMAN_HANDOFF")

        self.assertFalse(v["I3_bloqueio"])
        self.assertTrue(v["handoff_pedido_pelo_modelo"])


class TestPromptSobTeste(unittest.TestCase):
    """Defeito 3: o eval mediu um prompt que ninguém deploya."""

    def test_dbfalso_serve_o_prompt_recebido(self):
        db = DbFalso("PROMPT DE TESTE 123")

        linhas = db.execute_query(
            "SELECT content FROM scheduler.message_templates WHERE clinic_id=%s", ("x",))

        self.assertEqual(linhas[0]["content"], "PROMPT DE TESTE 123")

    def test_template_service_nao_cai_no_default(self):
        """Se o DbFalso parar de servir templates, o TemplateService silencia
        e devolve DEFAULT_TEMPLATES - sem erro, com prompt errado."""
        from src.services.template_service import DEFAULT_TEMPLATES, TemplateService

        conteudo = TemplateService(DbFalso("PROMPT REAL")).get_template("x", "AI_SYSTEM_PROMPT")

        self.assertEqual(conteudo["content"], "PROMPT REAL")
        self.assertNotEqual(conteudo["content"],
                            DEFAULT_TEMPLATES.get("AI_SYSTEM_PROMPT"))


class TestI1UsaAJanelaDeProducao(unittest.TestCase):
    """Defeito 4: a régua era mais estrita que o código."""

    def test_fato_consultado_em_rodada_anterior_nao_e_violacao(self):
        v = avalia_turno("Tenho 18:00.", [], ["get_time_slots"], None, None)

        self.assertEqual(v["I1_agenda_sem_respaldo"], [])

    def test_fato_nunca_consultado_e_violacao(self):
        v = avalia_turno("Tenho 21:30.", [], ["get_time_slots"], None, None)

        self.assertIn("21:30", v["I1_agenda_sem_respaldo"])

    def test_janela_do_eval_e_a_mesma_do_agente(self):
        """Se alguém mudar RESPALDO_GUARDADO, o eval acompanha sozinho."""
        import inspect

        from tests.evaluation import eval_fluxo_agente

        self.assertIn("RESPALDO_GUARDADO", inspect.getsource(eval_fluxo_agente.avalia_turno))
        self.assertIsInstance(RESPALDO_GUARDADO, int)


class TestFixturesCobremAsTools(unittest.TestCase):
    """Tool sem fixture devolve {"error": ...} e o eval mede o agente lidando
    com erro, não com dado. Silencioso, igual aos outros quatro."""

    def test_toda_tool_exposta_tem_fixture(self):
        expostas = {t["name"] for t in get_tool_definitions(format="anthropic")}

        faltando = expostas - set(FIXTURES)

        self.assertEqual(faltando, set(), f"tools sem fixture no eval: {faltando}")


class TestNotaInvalida(unittest.TestCase):
    """A guarda que impediu a quinta rodada de mentir."""

    BASE = {"erros_de_api": 0, "chamadas_modelo": 10, "turnos": 5,
            "tokens_in": 100, "tokens_cache_read": 0, "primeiro_erro": None}

    def test_execucao_boa_e_valida(self):
        self.assertTrue(nota_valida(self.BASE)[0])

    def test_erro_de_api_invalida(self):
        self.assertFalse(nota_valida({**self.BASE, "erros_de_api": 1})[0])

    def test_zero_token_invalida(self):
        """O caminho de erro do agente responde texto e parece turno normal."""
        self.assertFalse(nota_valida({**self.BASE, "tokens_in": 0})[0])

    def test_zero_turno_invalida(self):
        self.assertFalse(nota_valida({**self.BASE, "turnos": 0})[0])


class TestCusto(unittest.TestCase):
    """Rodei cinco vezes sem contabilidade e só soube o gasto quando
    perguntaram. Agora o número sai em toda execução."""

    def test_conta_as_quatro_faixas(self):
        r = {"modelo": "claude-sonnet-5", "tokens_in": 1_000_000,
             "tokens_out": 1_000_000, "tokens_cache_read": 1_000_000,
             "tokens_cache_write": 1_000_000}

        self.assertAlmostEqual(custo(r), 3.00 + 15.00 + 0.30 + 3.75, places=2)

    def test_haiku_e_mais_barato(self):
        r = {"tokens_in": 1_000_000, "tokens_out": 0,
             "tokens_cache_read": 0, "tokens_cache_write": 0}

        self.assertLess(custo({**r, "modelo": "claude-haiku-4-5"}),
                        custo({**r, "modelo": "claude-sonnet-5"}))

    def test_escrita_de_cache_entra_na_conta(self):
        """Era a faixa invisível: 1,25x a entrada, ~US$ 1,42 por rodada."""
        sem = {"modelo": "claude-sonnet-5", "tokens_in": 0, "tokens_out": 0,
               "tokens_cache_read": 0, "tokens_cache_write": 0}

        self.assertGreater(custo({**sem, "tokens_cache_write": 1_000_000}), 0)


if __name__ == "__main__":
    unittest.main()
