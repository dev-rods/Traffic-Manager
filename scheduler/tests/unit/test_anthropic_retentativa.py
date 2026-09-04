# -*- coding: utf-8 -*-
"""Falha transitória de rede é retentada, não devolvida à paciente.

Em 04/09/2026 o eval fez 300 chamadas seguidas e 130 morreram com
ConnectionResetError. Só `Timeout` era retentado; `ConnectionError` caía no
ramo genérico e estourava de primeira. Em produção isso é a pessoa recebendo
"estou com dificuldades" por um reset de rede que a segunda tentativa resolve.
"""
import os
import unittest
from unittest import mock

import requests

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("ANTHROPIC_API_KEY", "chave-de-teste")

from src.services.anthropic_service import AnthropicError, AnthropicService


def resposta_ok():
    r = mock.Mock()
    r.status_code = 200
    r.json.return_value = {"content": [{"type": "text", "text": "ok"}],
                           "stop_reason": "end_turn"}
    return r


class TestRetentativaDeRede(unittest.TestCase):
    def setUp(self):
        self.servico = AnthropicService()
        # Sem espera real: o teste mede a decisão de retentar, não o backoff.
        self.sleep = mock.patch("src.services.anthropic_service.time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def _chama(self):
        return self.servico.create_message(
            system="s", messages=[{"role": "user", "content": "oi"}],
            tools=[], max_tokens=64,
        )

    def test_conexao_derrubada_e_retentada(self):
        with mock.patch("requests.post", side_effect=[
            requests.exceptions.ConnectionError("reset by peer"),
            resposta_ok(),
        ]) as post:
            r = self._chama()

        self.assertEqual(post.call_count, 2)
        self.assertEqual(r["stop_reason"], "end_turn")

    def test_timeout_continua_retentado(self):
        with mock.patch("requests.post", side_effect=[
            requests.exceptions.Timeout("demorou"),
            resposta_ok(),
        ]) as post:
            self._chama()

        self.assertEqual(post.call_count, 2)

    def test_desiste_depois_do_teto_de_tentativas(self):
        """Retentar para sempre seguraria a Lambda até o timeout dela."""
        with mock.patch("requests.post",
                        side_effect=requests.exceptions.ConnectionError("reset")) as post:
            with self.assertRaises(AnthropicError):
                self._chama()

        self.assertGreater(post.call_count, 1)
        self.assertLessEqual(post.call_count, 6)

    def test_erro_de_requisicao_que_nao_e_de_rede_nao_e_retentado(self):
        """URL inválida não melhora tentando de novo - só gasta tempo."""
        with mock.patch("requests.post",
                        side_effect=requests.exceptions.InvalidURL("url ruim")) as post:
            with self.assertRaises(AnthropicError):
                self._chama()

        self.assertEqual(post.call_count, 1)

    def test_espera_entre_tentativas(self):
        with mock.patch("requests.post", side_effect=[
            requests.exceptions.ConnectionError("reset"),
            resposta_ok(),
        ]):
            self._chama()

        self.sleep.assert_called_once()
        self.assertGreater(self.sleep.call_args[0][0], 0)


if __name__ == "__main__":
    unittest.main()
