# -*- coding: utf-8 -*-
"""O histórico do agente não contém o OTP e rotula o que o sistema mandou
(PRD 034). Antes, "Seu código de confirmação é 362447" entrava como turno
`assistant`, como se o bot tivesse dito."""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services.autoria_mensagem import autor_da_mensagem, foi_de_pessoa_da_clinica
from src.services.conversation_agent import events_to_history


def _sistema(content, origem):
    return {"direction": "OUTBOUND", "status": "SENT", "providerMessageId": "3EB0" + origem,
            "content": content, "metadata": {"origem": origem}}


class TestHistorico(unittest.TestCase):
    def test_otp_some_e_confirmacao_entra_como_sistema(self):
        eventos = [
            {"direction": "INBOUND", "status": "RECEIVED", "content": "oi, agendei pelo site"},
            _sistema("Código de confirmação enviado (expira em 5 minutos).", "SITE_OTP"),
            _sistema("Agendamento confirmado para Paula! 27/10 às 10:05.", "SITE_AGENDAMENTO"),
            {"direction": "INBOUND", "status": "RECEIVED", "content": "qual o horário mesmo?"},
            {"direction": "OUTBOUND", "status": "SENT", "providerMessageId": "3EB0BOT",
             "content": "Dia 27 às 10:05 😊"},
        ]
        h = events_to_history(eventos)
        texto = "\n".join(t["content"] for t in h)
        self.assertNotIn("Código de confirmação", texto)
        self.assertEqual(h[0]["role"], "user")
        self.assertIn("[sistema]: Agendamento confirmado para Paula!", h[0]["content"])
        self.assertIn("qual o horário mesmo?", h[0]["content"])
        self.assertEqual(h[1], {"role": "assistant", "content": "Dia 27 às 10:05 😊"})

    def test_sistema_nao_e_pessoa_mesmo_sem_id(self):
        """Se o put do SENT falhar e sobrar só o QUEUED com origem, continua
        sendo sistema - nunca atendente."""
        evento = {"direction": "OUTBOUND", "status": "SENT", "content": "x",
                  "metadata": {"origem": "CHECKIN"}}
        self.assertFalse(foi_de_pessoa_da_clinica(evento))
        self.assertEqual(autor_da_mensagem(evento), "SISTEMA")

    def test_atendente_continua_atendente(self):
        evento = {"direction": "OUTBOUND", "status": "SENT", "content": "x",
                  "metadata": {"autor": "HUMANO"}}
        self.assertEqual(autor_da_mensagem(evento), "HUMANO")
        self.assertEqual(autor_da_mensagem({"direction": "OUTBOUND", "status": "SENT",
                                            "providerMessageId": "3EB0"}), "BOT")
        self.assertIsNone(autor_da_mensagem({"direction": "INBOUND", "status": "RECEIVED"}))


if __name__ == "__main__":
    unittest.main()
