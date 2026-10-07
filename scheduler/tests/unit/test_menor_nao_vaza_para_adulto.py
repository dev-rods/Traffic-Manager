# -*- coding: utf-8 -*-
"""Nenhuma adulta ouve que precisa de responsável legal.

Pergunta do André em 14/09/2026, e ela achou o buraco. A primeira versão desta
regra tinha dois caminhos: o aviso enviado pelo CÓDIGO após o agendamento, esse
travado na data de nascimento do cadastro; e a instrução no PROMPT para o modelo
informar durante a conversa, essa sem trava nenhuma.

O segundo é o que vai rodar. Medido em prod no mesmo dia: dos 295 pacientes,
6 têm data de nascimento e NENHUM é menor - o caminho do código praticamente não
dispara hoje, e o do modelo dispara a partir de "estou no ensino médio", de um
"17" solto numa frase sobre outra coisa, ou de nada.

Testar só o caminho determinístico era testar onde o risco não estava.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.menor_de_idade import (
    TEXTO,
    afirma_restricao,
    afirmacao_sem_respaldo,
    tem_respaldo_de_menoridade,
)
from tests.unit.dublagem_agente import (
    CLINIC,
    AnthropicFalso,
    mensagem,
    monta_agente,
)

MENOR = [{"is_minor": True, "age_in_years": 16}]
MAIOR = [{"is_minor": False, "age_in_years": 32}]


class TestOQueContaComoAfirmacao(unittest.TestCase):
    def test_as_formas_de_dizer_a_mesma_coisa(self):
        for frase in (
            "Você precisa vir com um responsável legal na primeira sessão.",
            "Como você é menor de idade, precisamos de autorização.",
            "É necessário autorização do responsável assinada no gov.br",
            "Precisa estar acompanhada por um responsável",
            "Para menor de 18 anos, a regra é diferente.",
            "precisa de responsavel legal",  # sem acento, como chega às vezes
        ):
            with self.subTest(frase=frase):
                self.assertTrue(afirma_restricao(frase))

    def test_o_proprio_aviso_oficial_e_reconhecido(self):
        """Se o texto padrão escapasse do detector, a trava não valeria nada."""
        self.assertTrue(afirma_restricao(TEXTO))

    def test_conversa_normal_nao_dispara(self):
        for frase in (
            "Sua sessão está confirmada para quarta às 14h.",
            "A virilha completa sai por R$ 175,00.",
            "Temos horário na responsável pela agenda?",  # 'responsável' sozinho
            "O laser é indolor, pode ficar tranquila!",
        ):
            with self.subTest(frase=frase):
                self.assertFalse(afirma_restricao(frase))


class TestORespaldo(unittest.TestCase):
    def test_so_is_minor_verdadeiro_respalda(self):
        self.assertTrue(tem_respaldo_de_menoridade(MENOR))
        self.assertFalse(tem_respaldo_de_menoridade(MAIOR))
        self.assertFalse(tem_respaldo_de_menoridade([]))

    def test_respaldo_no_meio_de_outros_resultados(self):
        respaldo = [{"areas": []}, {"available_slots": ["09:00"]}] + MENOR
        self.assertTrue(tem_respaldo_de_menoridade(respaldo))

    def test_lixo_no_respaldo_nao_derruba(self):
        self.assertFalse(tem_respaldo_de_menoridade([None, "texto", 42, {"is_minor": "sim"}]))

    def test_a_conta_final(self):
        frase = "Você precisa de responsável legal na primeira sessão."
        self.assertTrue(afirmacao_sem_respaldo(frase, MAIOR))
        self.assertFalse(afirmacao_sem_respaldo(frase, MENOR))


class TestNoAgente(unittest.TestCase):
    """O que a pessoa recebe de verdade."""

    def _responde(self, texto_do_modelo, respaldo_anterior=None):
        agente = monta_agente(AnthropicFalso(texto_do_modelo))
        if respaldo_anterior is not None:
            agente.sessao_salva["respaldo_anterior"] = respaldo_anterior
        saida = agente.process_message(CLINIC, mensagem("quero agendar axilas"))
        return [m.content for m in saida], agente.sessao_salva

    def test_adulta_nunca_recebe_a_restricao(self):
        """O caso do André: o modelo inventa a restrição e ela não sai."""
        textos, sessao = self._responde(
            "Antes de agendar: como você é menor de idade, precisa de um "
            "responsável legal na primeira sessão, ok?"
        )
        for t in textos:
            self.assertNotIn("responsável legal", t)
        self.assertEqual(sessao["state"], "HUMAN_HANDOFF")

    def test_com_respaldo_da_tool_a_restricao_passa(self):
        """Travar demais seria o outro erro: menor sem aviso nenhum."""
        textos, _ = self._responde(
            "Como você é menor de idade, precisa de responsável legal na primeira sessão.",
            respaldo_anterior=MENOR,
        )
        self.assertIn("responsável legal", " ".join(textos))

    def test_resposta_comum_passa_intacta(self):
        textos, sessao = self._responde("Claro! Qual data prefere?")
        self.assertIn("Claro! Qual data prefere?", textos)
        self.assertNotEqual(sessao.get("state"), "HUMAN_HANDOFF")


if __name__ == "__main__":
    unittest.main()
