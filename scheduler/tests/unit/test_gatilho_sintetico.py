"""Como o agente monta o histórico quando fala por iniciativa da clínica.

Nos gatilhos sintéticos (abrir conversa, retomar conversa) ninguém escreveu
agora, e a conversa pode ter andado sem o agente saber: o webhook grava toda
mensagem recebida no MessageEvents, mas com o bot pausado ele não chama o
agente, então o agent_history da sessão fica velho.

Foi o que aconteceu com uma cliente real: ela mandou duas perguntas com o bot
pausado, e ao retomar o agente respondeu "tudo certo por aqui" - porque as
perguntas não estavam no histórico que ele carregou.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services.conversation_agent import eh_gatilho_sintetico, limpar_gatilhos
from src.services.conversation_resume import GATILHO_RETOMADA


class TestReconhecimento(unittest.TestCase):
    def test_reconhece_os_dois_gatilhos(self):
        self.assertTrue(eh_gatilho_sintetico("__RETOMAR_CONVERSA__"))
        self.assertTrue(eh_gatilho_sintetico("__INICIAR_CONVERSA__"))

    def test_mensagem_de_gente_nao_e_gatilho(self):
        self.assertFalse(eh_gatilho_sintetico("oi, quanto custa?"))
        self.assertFalse(eh_gatilho_sintetico(""))
        self.assertFalse(eh_gatilho_sintetico(None))


class TestLimpezaAntesDeSalvar(unittest.TestCase):
    """O gatilho não pode ficar no histórico salvo.

    Ele não é fala de ninguém. Persistido, reaparece como turno da pessoa na
    conversa seguinte, e numa segunda retomada o agente vê dois gatilhos
    seguidos com respostas genéricas - o que reforça "não há nada a fazer".
    """

    def test_remove_o_gatilho_e_preserva_a_resposta(self):
        history = [
            {"role": "user", "content": "tem horário sábado?"},
            {"role": "assistant", "content": "Temos sim!"},
            {"role": "user", "content": GATILHO_RETOMADA},
            {"role": "assistant", "content": "Sobre a manutenção: depende de cada caso."},
        ]

        limpo = limpar_gatilhos(history)

        self.assertNotIn(GATILHO_RETOMADA, str(limpo))
        self.assertIn("Sobre a manutenção", str(limpo))

    def test_nao_deixa_dois_assistants_seguidos(self):
        """A API da Anthropic exige alternância entre user e assistant."""
        history = [
            {"role": "user", "content": "tem horário sábado?"},
            {"role": "assistant", "content": "Temos sim!"},
            {"role": "user", "content": GATILHO_RETOMADA},
            {"role": "assistant", "content": "Ficou alguma dúvida?"},
        ]

        limpo = limpar_gatilhos(history)

        papeis = [t["role"] for t in limpo]
        for anterior, seguinte in zip(papeis, papeis[1:]):
            self.assertNotEqual(anterior, seguinte, f"papéis repetidos: {papeis}")

    def test_historico_sem_gatilho_fica_intacto(self):
        history = [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "Olá!"},
        ]
        self.assertEqual(limpar_gatilhos(history), history)

    def test_lista_vazia(self):
        self.assertEqual(limpar_gatilhos([]), [])
