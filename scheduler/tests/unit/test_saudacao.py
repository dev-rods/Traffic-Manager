# -*- coding: utf-8 -*-
"""Saudação pelo relógio da clínica (PRD 064)."""
import unittest
from datetime import datetime

from src.services import saudacao


class TestPeriodo(unittest.TestCase):

    def test_faixas(self):
        self.assertEqual(saudacao.periodo(datetime(2026, 11, 25, 8, 12)), "manhã")
        self.assertEqual(saudacao.periodo(datetime(2026, 11, 25, 11, 59)), "manhã")
        self.assertEqual(saudacao.periodo(datetime(2026, 11, 25, 12, 0)), "tarde")
        self.assertEqual(saudacao.periodo(datetime(2026, 11, 25, 17, 59)), "tarde")
        self.assertEqual(saudacao.periodo(datetime(2026, 11, 25, 18, 0)), "noite")
        self.assertEqual(saudacao.periodo(datetime(2026, 11, 25, 23, 30)), "noite")

    def test_linha_do_calendario(self):
        self.assertEqual(saudacao.linha_do_calendario(datetime(2026, 11, 25, 8, 5)), "Agora: 08:05, manhã.")


class TestCorrige(unittest.TestCase):

    def test_boa_noite_de_manha_vira_bom_dia(self):
        self.assertEqual(saudacao.corrige("Olá, boa noite! Tudo bem?", "manhã"), "Olá, bom dia! Tudo bem?")

    def test_maiuscula_preservada(self):
        self.assertEqual(saudacao.corrige("Boa noite, Maria!", "tarde"), "Boa tarde, Maria!")

    def test_saudacao_certa_fica(self):
        self.assertEqual(saudacao.corrige("Bom dia! Aqui é da clínica.", "manhã"), "Bom dia! Aqui é da clínica.")
        self.assertFalse(saudacao.saudacao_errada("Bom dia!", "manhã"))

    def test_sem_periodo_vira_ola(self):
        self.assertEqual(saudacao.corrige("Boa tarde, tudo bem?", None), "Olá, tudo bem?")

    def test_sem_saudacao_nao_mexe(self):
        self.assertEqual(saudacao.corrige("Temos 15:40 e 17:40. Algum serve?", "noite"),
                         "Temos 15:40 e 17:40. Algum serve?")
        self.assertEqual(saudacao.corrige("", "noite"), "")
