# -*- coding: utf-8 -*-
"""A janela do site público: de hoje ao último dia do mês, no fuso da clínica."""
import unittest
from datetime import date, datetime

import pytz

from src.services import mes_vigente

SP = pytz.timezone("America/Sao_Paulo")


def em_sp(*args):
    return SP.localize(datetime(*args))


class TestJanela(unittest.TestCase):
    def test_meio_do_mes(self):
        self.assertEqual(mes_vigente.janela(em_sp(2026, 10, 17, 10, 0)), (date(2026, 10, 17), date(2026, 10, 31)))

    def test_ultimo_dia_e_janela_de_um_dia(self):
        self.assertEqual(mes_vigente.janela(em_sp(2026, 10, 31, 9, 0)), (date(2026, 10, 31), date(2026, 10, 31)))

    def test_fevereiro_bissexto(self):
        self.assertEqual(mes_vigente.janela(em_sp(2028, 2, 10, 9, 0))[1], date(2028, 2, 29))

    def test_dentro(self):
        agora = em_sp(2026, 10, 17, 10, 0)
        self.assertTrue(mes_vigente.dentro(date(2026, 10, 17), agora))
        self.assertTrue(mes_vigente.dentro(date(2026, 10, 31), agora))
        self.assertFalse(mes_vigente.dentro(date(2026, 10, 16), agora))
        self.assertFalse(mes_vigente.dentro(date(2026, 11, 1), agora))

    def test_proximo_mes_abre_no_dia_1(self):
        self.assertEqual(mes_vigente.proximo_mes_abre_em(em_sp(2026, 12, 20, 9, 0)), date(2027, 1, 1))


class TestFuso(unittest.TestCase):
    def test_vale_o_dia_da_clinica_e_nao_o_do_servidor(self):
        """02h30 UTC de 1/11 ainda é 23h30 de 31/10 em São Paulo."""
        utc = pytz.utc.localize(datetime(2026, 11, 1, 2, 30))
        agora = mes_vigente.agora_na_clinica("America/Sao_Paulo", agora_utc=utc)
        self.assertEqual(agora.date(), date(2026, 10, 31))
        self.assertEqual(mes_vigente.janela(agora), (date(2026, 10, 31), date(2026, 10, 31)))

    def test_fuso_invalido_ou_ausente_vira_sao_paulo(self):
        utc = pytz.utc.localize(datetime(2026, 11, 1, 2, 30))
        for fuso in (None, "", "Marte/Olympus"):
            with self.subTest(fuso=fuso):
                self.assertEqual(mes_vigente.agora_na_clinica(fuso, agora_utc=utc).date(), date(2026, 10, 31))


class TestMinutosDeAgora(unittest.TestCase):
    def test_hora_cheia(self):
        self.assertEqual(mes_vigente.minutos_de_agora(em_sp(2026, 10, 17, 14, 0)), 840)

    def test_segundos_arredondam_para_cima(self):
        """Às 14h00min30s, 14h00 já passou."""
        self.assertEqual(mes_vigente.minutos_de_agora(em_sp(2026, 10, 17, 14, 0, 30)), 841)


if __name__ == "__main__":
    unittest.main()
