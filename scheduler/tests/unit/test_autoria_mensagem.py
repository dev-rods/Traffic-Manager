"""Quem enviou a mensagem que saiu do número da clínica.

O z-api devolve toda mensagem enviada pelo número da clínica com fromMe=true e
status=SENT, tenha ela saído do bot ou do celular da atendente. Distinguir pelo
status não funciona: foi o que deixou o bot responder por cima de um atendimento
humano em 01/09/2026, cinco vezes, até a cliente reclamar.

O identificador é factual. Verificado contra o próprio incidente: o payload do
webhook trazia messageId=3EB0E3041A2A1041F6857D, e o MessageEvents tinha esse
mesmo valor em providerMessageId na mensagem que o bot enviou às 13:36:18.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services.autoria_mensagem import foi_enviada_pelo_bot


class TestEcoDoBot(unittest.TestCase):
    """O falso positivo aqui é grave: se o eco do bot não for reconhecido, ele
    pausa a si mesmo e fica mudo por 24h depois de uma única resposta."""

    def test_id_registrado_pelo_bot_e_eco(self):
        eventos = [{"providerMessageId": "ABC123"}, {"providerMessageId": "DEF456"}]
        self.assertTrue(foi_enviada_pelo_bot(eventos, "ABC123"))

    def test_reconhece_o_caso_real_do_incidente(self):
        eventos = [
            {"providerMessageId": "3EB038389A5C37BCA5FD07"},
            {"providerMessageId": "3EB0E3041A2A1041F6857D"},
            {"providerMessageId": "3EB0FF2377FF02C168F687"},
        ]
        self.assertTrue(foi_enviada_pelo_bot(eventos, "3EB0E3041A2A1041F6857D"))

    def test_ignora_eventos_sem_provider_id(self):
        """QUEUED entra no MessageEvents antes do envio, ainda sem id: 36% das
        linhas OUTBOUND em produção. Não podem atrapalhar a busca."""
        eventos = [{"providerMessageId": None}, {}, {"providerMessageId": "ABC123"}]
        self.assertTrue(foi_enviada_pelo_bot(eventos, "ABC123"))


class TestMensagemDoCelular(unittest.TestCase):
    def test_id_desconhecido_veio_do_celular(self):
        eventos = [{"providerMessageId": "ABC123"}]
        self.assertFalse(foi_enviada_pelo_bot(eventos, "XYZ789"))

    def test_conversa_sem_historico(self):
        """Atendente escreve primeiro, antes de o bot ter falado."""
        self.assertFalse(foi_enviada_pelo_bot([], "XYZ789"))
        self.assertFalse(foi_enviada_pelo_bot(None, "XYZ789"))

    def test_sem_id_no_payload_trata_como_humano(self):
        """Sem id não dá para afirmar que foi o bot. Errar para 'humano' cala o
        bot; errar para 'bot' o deixa atropelar um atendimento. O primeiro é o
        erro barato."""
        self.assertFalse(foi_enviada_pelo_bot([{"providerMessageId": "ABC"}], ""))
        self.assertFalse(foi_enviada_pelo_bot([{"providerMessageId": "ABC"}], None))
