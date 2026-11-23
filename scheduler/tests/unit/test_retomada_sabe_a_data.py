# -*- coding: utf-8 -*-
"""O modelo sabe que dia e hoje tambem quando ninguem escreveu agora.

Em 23/11/2026 a recepcao da Essencia retomou o bot pelo painel com "dia 08 ou
09 quais horarios?" em aberto. O bloco CALENDARIO so entrava fora dos gatilhos
sinteticos; sem a data de hoje, o modelo consultou 2025-12-08 e 2025-12-09,
recebeu lista vazia e disse que nao havia horario. Havia.

Duas defesas: o calendario entra sempre, e `get_time_slots` recusa data
passada com a data de hoje no erro.
"""
import unittest
from datetime import date
from unittest import mock

from tests.unit.dublagem_agente import CLINIC, AnthropicFalso, mensagem, monta_agente
from tests.unit import test_horario_pedido as hp


class TestCalendarioNoGatilho(unittest.TestCase):
    def _turno(self, texto):
        anthropic = AnthropicFalso()
        agente = monta_agente(anthropic)
        agente.process_message(CLINIC, mensagem(texto))
        return anthropic.conversas[0][-1]["content"]

    def test_retomada_traz_hoje(self):
        turno = self._turno("__RETOMAR_CONVERSA__")
        self.assertIn("═══ CALENDÁRIO ═══", turno)
        self.assertIn("HOJE é", turno)
        self.assertIn(date.today().strftime("%d/%m/%Y"), turno)
        self.assertIn("__RETOMAR_CONVERSA__", turno)

    def test_inicio_de_conversa_tambem(self):
        self.assertIn("HOJE é", self._turno("__INICIAR_CONVERSA__"))

    def test_mensagem_comum_continua_igual(self):
        turno = self._turno("quero amanhã")
        self.assertIn("HOJE é", turno)
        self.assertIn('"amanhã" =', turno)


class TestDataPassada(unittest.TestCase):
    def setUp(self):
        base = hp.TestATool("test_sem_pedido_nada_muda")
        self.ex = base._executor()
        self._chama_base = base._chama

    def _chama(self, **args):
        # A fixacao de hoje em 06/10 do modulo base e sobreposta pela de cada teste.
        return self._chama_base(self.ex, **args)
    def test_data_passada_e_erro_com_a_data_de_hoje(self):
        # O modulo base fixa hoje em 06/10/2026; 2025 e passado para ele tambem.
        r = self._chama(date="2025-12-08")
        self.assertIn("2025-12-08 is in the past", r["error"])
        self.assertIn("Today is 2026-10-06", r["error"])
        self.assertEqual(r["today"], "2026-10-06")
        self.assertNotIn("available_slots", r)

    def test_hoje_e_futuro_passam(self):
        self.assertIn("available_slots", self._chama(date="2026-10-06"))
        self.assertIn("available_slots", self._chama(date=hp.DIA))

    def test_data_ilegivel_segue_como_antes(self):
        r = self._chama(date="amanhã")
        self.assertIn("available_slots", r)
