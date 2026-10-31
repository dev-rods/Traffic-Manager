# -*- coding: utf-8 -*-
"""O relógio da clínica: o dia e a hora são os do fuso dela."""
import unittest
from datetime import date, datetime

import pytz

from src.services import relogio

SP = pytz.timezone("America/Sao_Paulo")


def em_sp(*args):
    return SP.localize(datetime(*args))


class TestFuso(unittest.TestCase):
    def test_vale_o_dia_da_clinica_e_nao_o_do_servidor(self):
        """02h30 UTC de 1/11 ainda é 23h30 de 31/10 em São Paulo."""
        utc = pytz.utc.localize(datetime(2026, 11, 1, 2, 30))
        self.assertEqual(relogio.agora_na_clinica("America/Sao_Paulo", agora_utc=utc).date(), date(2026, 10, 31))

    def test_fuso_invalido_ou_ausente_vira_sao_paulo(self):
        utc = pytz.utc.localize(datetime(2026, 11, 1, 2, 30))
        for fuso in (None, "", "Marte/Olympus"):
            with self.subTest(fuso=fuso):
                self.assertEqual(relogio.agora_na_clinica(fuso, agora_utc=utc).date(), date(2026, 10, 31))


class TestMinutosDeAgora(unittest.TestCase):
    def test_hora_cheia(self):
        self.assertEqual(relogio.minutos_de_agora(em_sp(2026, 10, 17, 14, 0)), 840)

    def test_segundos_arredondam_para_cima(self):
        """Às 14h00min30s, 14h00 já passou."""
        self.assertEqual(relogio.minutos_de_agora(em_sp(2026, 10, 17, 14, 0, 30)), 841)


if __name__ == "__main__":
    unittest.main()
