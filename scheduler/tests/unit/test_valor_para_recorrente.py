# -*- coding: utf-8 -*-
"""Quem já é paciente não ouve o valor ao confirmar - só se perguntar.

Decisão do André (06/10/2026, PRD 020 fase 2). O roteiro de lead mostra o
valor no passo 3 e no resumo do passo 5; para quem está marcando a segunda
sessão em diante, repetir soa a cobrança.
"""
import unittest

from src.services.valor_para_recorrente import (
    BLOCO_DO_PROMPT,
    anuncia_valor,
    e_recorrente,
    pediu_valor,
    sem_valor_no_roteiro,
)
from tests.unit.dublagem_agente import (
    CLINIC,
    AnthropicRoteiro,
    mensagem,
    monta_agente,
    texto_do_modelo,
)
from tests.unit.test_identificacao_de_paciente import PROMPT_REAL

RECORRENTE = {"encontrado": True, "nome": "Olivia", "cadastro_completo": True,
              "sessoes_feitas": 3, "ultima_sessao": "2026-09-23", "agendamento_futuro": None}
PRIMEIRA = {"encontrado": True, "nome": "Nova", "cadastro_completo": True,
            "sessoes_feitas": 0, "ultima_sessao": None, "agendamento_futuro": None}
# Sem data nem horario de proposito: a proveniencia e outra trava, e um
# fixture com "21/10 as 17:35" sem tool a dispararia junto.
COM_VALOR = ("Fechando: *axilas e buço*. Total: ~R$ 160,00~ por "
             "*R$ 144,00* (10% de desconto). Confirmo?")
SEM_VALOR = "Fechando: *axilas e buço*. Confirmo?"


class TestQuemERecorrente(unittest.TestCase):
    def test_ja_fez_sessao(self):
        self.assertTrue(e_recorrente(RECORRENTE))

    def test_tem_sessao_marcada_mesmo_sem_ter_feito(self):
        self.assertTrue(e_recorrente({**PRIMEIRA, "agendamento_futuro": {"id": "x"}}))

    def test_primeira_vez_nao_e(self):
        """A primeira é a que vê o valor: o preço faz parte da decisão."""
        self.assertFalse(e_recorrente(PRIMEIRA))

    def test_desconhecida_nao_e(self):
        self.assertFalse(e_recorrente({"encontrado": False}))
        self.assertFalse(e_recorrente({}))
        self.assertFalse(e_recorrente(None))


class TestPediuValor(unittest.TestCase):
    def test_formas_de_perguntar(self):
        for t in ("quanto custa?", "qual o valor?", "me passa os valores de cada área",
                  "tem desconto?", "quanto fica axila e buço", "Depois me confirma os valores?"):
            with self.subTest(t=t):
                self.assertTrue(pediu_valor([{"role": "user", "content": t}]))

    def test_so_conta_a_fala_dela(self):
        self.assertFalse(pediu_valor([{"role": "assistant", "content": "O valor é R$ 95,00"}]))

    def test_sem_pergunta(self):
        self.assertFalse(pediu_valor([{"role": "user", "content": "pode ser 17:35"},
                                      {"role": "user", "content": "confirmo"}]))


class TestAnunciaValor(unittest.TestCase):
    def test_detecta(self):
        for t in (COM_VALOR, "São R$95 a axila", "Com 15% de desconto fica", "Valor total: 283,50"):
            with self.subTest(t=t):
                self.assertIsNotNone(anuncia_valor(t))

    def test_nao_detecta(self):
        for t in (SEM_VALOR, "Agendado! Até lá.", "Rua Augusta, 2709, conj. 26"):
            with self.subTest(t=t):
                self.assertIsNone(anuncia_valor(t))


class TestRoteiroSemValor(unittest.TestCase):
    def setUp(self):
        self.prompt = sem_valor_no_roteiro(PROMPT_REAL)

    def test_o_resumo_perde_o_valor(self):
        self.assertNotIn("horário e valor total", self.prompt)
        self.assertIn("áreas, data e horário. SEM valor", self.prompt)

    def test_o_bloco_entra(self):
        self.assertIn("PACIENTE RECORRENTE", self.prompt)
        self.assertIn(BLOCO_DO_PROMPT.strip(), self.prompt)

    def test_o_resto_fica(self):
        for trecho in ("5. CONFIRMAÇÃO", "6. CADASTRO", "COMO LIDAR COM OBJEÇÃO"):
            self.assertIn(trecho, self.prompt)

    def test_mostre_o_valor_do_passo_de_areas(self):
        prompt = "═══ COMO CONDUZIR A CONVERSA ═══\n3. ÁREAS\n   Confirme as áreas, chame calculate_discount e mostre o valor.\n"
        saida = sem_valor_no_roteiro(prompt)
        self.assertNotIn("e mostre o valor", saida)
        self.assertIn("NÃO mostre o valor", saida)
        self.assertIn("calculate_discount", saida)

    def test_sem_secao_so_o_bloco(self):
        self.assertEqual(sem_valor_no_roteiro("x"), "x" + BLOCO_DO_PROMPT)
        self.assertEqual(sem_valor_no_roteiro(""), "")


class TestNoAgente(unittest.TestCase):
    def test_recorrente_que_nao_perguntou_nao_ouve_o_valor(self):
        anthropic = AnthropicRoteiro([texto_do_modelo(COM_VALOR), texto_do_modelo(SEM_VALOR)])
        agente = monta_agente(anthropic, paciente=RECORRENTE)

        saida = agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertEqual(len(anthropic.correcoes), 1)
        self.assertIn("nao perguntou o valor", anthropic.correcoes[0])
        self.assertNotIn("R$", saida[0].content)

    def test_recorrente_que_perguntou_ouve(self):
        anthropic = AnthropicRoteiro([texto_do_modelo(COM_VALOR)])
        agente = monta_agente(anthropic, paciente=RECORRENTE)

        saida = agente.process_message(CLINIC, mensagem("qual o valor?"))

        self.assertEqual(anthropic.correcoes, [])
        self.assertIn("R$", saida[0].content)

    def test_primeira_vez_ouve_o_valor(self):
        anthropic = AnthropicRoteiro([texto_do_modelo(COM_VALOR)])
        agente = monta_agente(anthropic, paciente=PRIMEIRA)

        saida = agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertEqual(anthropic.correcoes, [])
        self.assertIn("R$", saida[0].content)

    def test_o_prompt_do_recorrente_perde_o_valor(self):
        from tests.unit.dublagem_agente import AnthropicFalso

        anthropic = AnthropicFalso("ok")
        agente = monta_agente(anthropic, paciente=RECORRENTE)
        agente._build_system_prompt = lambda c, p, sessao=None: PROMPT_REAL

        agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertIn("PACIENTE RECORRENTE", anthropic.prompts[0])
        self.assertNotIn("horário e valor total", anthropic.prompts[0])

    def test_se_insistir_a_resposta_segue(self):
        anthropic = AnthropicRoteiro([texto_do_modelo(COM_VALOR), texto_do_modelo(COM_VALOR)])
        agente = monta_agente(anthropic, paciente=RECORRENTE)

        saida = agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertEqual(len(anthropic.correcoes), 1)
        self.assertEqual(len(saida), 1)


if __name__ == "__main__":
    unittest.main()
