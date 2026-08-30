"""Reconstrução do histórico de conversa a partir do MessageEvents.

Um lead pode escrever para a clínica antes de o bot abordá-lo. Quando o bot
finalmente inicia, a sessão pode estar vazia mas a conversa já existe no
MessageEvents (retenção de 90 dias). Sem reconstruir, o bot recomeçaria do zero
por cima de uma conversa em andamento, repetindo perguntas já respondidas.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.conversation_agent import events_to_history


class TestConversao(unittest.TestCase):
    def test_inbound_vira_user_e_outbound_vira_assistant(self):
        eventos = [
            {"direction": "INBOUND", "content": "oi, quanto custa?"},
            {"direction": "OUTBOUND", "content": "Olá! Depende das áreas."},
            {"direction": "INBOUND", "content": "virilha"},
        ]

        history = events_to_history(eventos)

        self.assertEqual([t["role"] for t in history], ["user", "assistant", "user"])
        self.assertEqual(history[0]["content"], "oi, quanto custa?")

    def test_ignora_eventos_sem_conteudo(self):
        eventos = [
            {"direction": "INBOUND", "content": ""},
            {"direction": "INBOUND", "content": None},
            {"direction": "INBOUND", "content": "   "},
        ]

        self.assertEqual(events_to_history(eventos), [])

    def test_lista_vazia(self):
        self.assertEqual(events_to_history([]), [])

    def test_none(self):
        self.assertEqual(events_to_history(None), [])

    def test_status_update_e_tratado_como_user(self):
        """Qualquer direction que não seja OUTBOUND é da pessoa."""
        eventos = [{"direction": "INBOUND", "content": "oi"}]

        self.assertEqual(events_to_history(eventos)[0]["role"], "user")


class TestAlternancia(unittest.TestCase):
    """A API da Anthropic exige alternância entre user e assistant."""

    def test_mensagens_seguidas_da_pessoa_sao_unidas(self):
        eventos = [
            {"direction": "INBOUND", "content": "oi"},
            {"direction": "INBOUND", "content": "queria saber o preço"},
            {"direction": "OUTBOUND", "content": "Olá!"},
        ]

        history = events_to_history(eventos)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["content"], "oi\nqueria saber o preço")

    def test_mensagens_seguidas_do_bot_sao_unidas(self):
        eventos = [
            {"direction": "INBOUND", "content": "oi"},
            {"direction": "OUTBOUND", "content": "Olá!"},
            {"direction": "OUTBOUND", "content": "Quais áreas?"},
        ]

        history = events_to_history(eventos)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["content"], "Olá!\nQuais áreas?")

    def test_historico_nao_comeca_com_assistant(self):
        """A API rejeita histórico que abre com assistant."""
        eventos = [
            {"direction": "OUTBOUND", "content": "Olá! Bem-vinda."},
            {"direction": "INBOUND", "content": "oi"},
        ]

        history = events_to_history(eventos)

        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(len(history), 1)

    def test_conversa_so_do_bot_vira_vazia(self):
        """Disparo em massa sem resposta: não há conversa a retomar."""
        eventos = [
            {"direction": "OUTBOUND", "content": "Olá! Bem-vinda."},
            {"direction": "OUTBOUND", "content": "Ainda tem interesse?"},
        ]

        self.assertEqual(events_to_history(eventos), [])


if __name__ == "__main__":
    unittest.main()
