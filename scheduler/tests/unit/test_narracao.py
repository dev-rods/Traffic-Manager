# -*- coding: utf-8 -*-
"""O bot fala COM a pessoa, não SOBRE ela.

06/10/2026, Olivia: "Já sendo virilha completa + perianal, ela mencionou
exatamente a *Virilha Completa + ânus*. Confirmando as áreas..." - o
raciocínio do modelo saiu como resposta. Uma em 3020 mensagens, mas uma na
conversa de alguém.
"""
import unittest

from src.services.narracao import narra_a_pessoa
from tests.unit.dublagem_agente import (
    CLINIC,
    AnthropicRoteiro,
    mensagem,
    monta_agente,
    texto_do_modelo,
)

VAZADO = (
    "Já sendo virilha completa + perianal, ela mencionou exatamente a *Virilha "
    "Completa + ânus*. Confirmando as áreas que você quer fazer: Buço, Axilas."
)


class TestDetecta(unittest.TestCase):
    def test_o_caso_real(self):
        self.assertEqual(narra_a_pessoa(VAZADO), "ela mencionou")

    def test_variantes(self):
        for t in ("A paciente quer axilas e virilha.", "Ela já disse que pode às 17h.",
                  "A pessoa pediu o horário das 14h", "A cliente escolheu dia 21."):
            with self.subTest(t=t):
                self.assertIsNotNone(narra_a_pessoa(t))

    def test_falar_com_ela_nao_casa(self):
        for t in ("Você mencionou virilha completa + ânus, certo?",
                  "Perfeito! Confirmando as áreas que você quer fazer: Buço, Axilas.",
                  "A especialista vai te confirmar os detalhes em instantes.",
                  "Ela é a nossa especialista em laser e vai te atender.",
                  "Sua sessão está marcada para dia 21/10 às 17:35."):
            with self.subTest(t=t):
                self.assertIsNone(narra_a_pessoa(t))

    def test_vazio(self):
        self.assertIsNone(narra_a_pessoa(""))
        self.assertIsNone(narra_a_pessoa(None))


class TestNoAgente(unittest.TestCase):
    def test_manda_reescrever_e_a_resposta_sai_falando_com_ela(self):
        anthropic = AnthropicRoteiro([
            texto_do_modelo(VAZADO),
            texto_do_modelo("Confirmando as áreas que você quer fazer: Buço, Axilas. Posso seguir?"),
        ])
        agente = monta_agente(anthropic)

        saida = agente.process_message(CLINIC, mensagem("quero buço e axilas"))

        self.assertEqual(len(anthropic.correcoes), 1)
        self.assertIn("terceira pessoa", anthropic.correcoes[0])
        self.assertNotIn("ela mencionou", saida[0].content.lower())

    def test_se_insistir_a_resposta_segue(self):
        """Erro de forma, não de fato: não vale uma transferência."""
        anthropic = AnthropicRoteiro([texto_do_modelo(VAZADO), texto_do_modelo(VAZADO)])
        agente = monta_agente(anthropic)

        saida = agente.process_message(CLINIC, mensagem("quero buço e axilas"))

        self.assertEqual(len(anthropic.correcoes), 1)
        self.assertEqual(len(saida), 1)
        self.assertNotEqual(agente.sessao_salva.get("bot_pausado_por"), "HANDOFF")

    def test_resposta_normal_nao_e_tocada(self):
        anthropic = AnthropicRoteiro([texto_do_modelo("Perfeito! Buço e axilas. Qual dia fica melhor?")])
        agente = monta_agente(anthropic)

        agente.process_message(CLINIC, mensagem("quero buço e axilas"))

        self.assertEqual(anthropic.correcoes, [])


if __name__ == "__main__":
    unittest.main()
