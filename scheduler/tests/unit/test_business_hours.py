"""Janela de envio a partir do horário comercial cadastrado.

Os casos usam o horário real da Essência (seg-sex 07:15-21:00, sem fim de semana)
porque é ele que expõe o comportamento que importa: dos 7 leads analisados em
agosto, só 2 chegaram dentro dessa janela. O salto para a próxima abertura é o
caminho comum, não a exceção.
"""
import os
import unittest
from datetime import datetime

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.business_hours import is_open, next_opening

TZ = pytz.timezone("America/Sao_Paulo")
ESSENCIA = {d: {"start": "07:15", "end": "21:00"} for d in ["mon", "tue", "wed", "thu", "fri"]}


def _local(ano, mes, dia, hora, minuto):
    return TZ.localize(datetime(ano, mes, dia, hora, minuto))


class TestIsOpen(unittest.TestCase):
    def test_dentro_da_janela(self):
        self.assertTrue(is_open(ESSENCIA, _local(2026, 8, 17, 16, 46)))

    def test_antes_da_abertura(self):
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 17, 7, 0)))

    def test_na_abertura_esta_aberto(self):
        self.assertTrue(is_open(ESSENCIA, _local(2026, 8, 17, 7, 15)))

    def test_no_fechamento_esta_fechado(self):
        """21:00 é o instante em que fecha, não o último minuto aberto."""
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 17, 21, 0)))

    def test_um_minuto_antes_do_fechamento(self):
        self.assertTrue(is_open(ESSENCIA, _local(2026, 8, 17, 20, 59)))

    def test_dia_nao_configurado_esta_fechado(self):
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 15, 10, 0)))

    def test_sem_configuracao(self):
        self.assertFalse(is_open({}, _local(2026, 8, 17, 10, 0)))

    def test_configuracao_nula(self):
        self.assertFalse(is_open(None, _local(2026, 8, 17, 10, 0)))


class TestNextOpening(unittest.TestCase):
    def test_ja_aberto_devolve_o_proprio_momento(self):
        momento = _local(2026, 8, 17, 16, 46)

        self.assertEqual(next_opening(ESSENCIA, momento), momento)

    def test_antes_da_abertura_salta_para_hoje(self):
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 17, 6, 0)), _local(2026, 8, 17, 7, 15))

    def test_depois_do_fechamento_salta_para_o_dia_seguinte(self):
        """Caso real: lead Guiguilson, quarta 23:46."""
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 12, 23, 46)), _local(2026, 8, 13, 7, 15))

    def test_sabado_salta_para_segunda(self):
        """Caso real: lead Fernanda, sábado 06:45 — espera quase 49 horas."""
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 15, 6, 45)), _local(2026, 8, 17, 7, 15))

    def test_domingo_salta_para_segunda(self):
        """Caso real: lead Amanda, domingo 19:02."""
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 16, 19, 2)), _local(2026, 8, 17, 7, 15))

    def test_sexta_a_noite_salta_para_segunda(self):
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 14, 22, 0)), _local(2026, 8, 17, 7, 15))

    def test_sem_configuracao_devolve_none(self):
        """Sem nenhum dia configurado a busca não terminaria."""
        self.assertIsNone(next_opening({}, _local(2026, 8, 17, 10, 0)))

    def test_clinica_que_atende_todo_dia(self):
        todos = {d: {"start": "08:00", "end": "18:00"}
                 for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}

        self.assertEqual(next_opening(todos, _local(2026, 8, 15, 19, 0)), _local(2026, 8, 16, 8, 0))


if __name__ == "__main__":
    unittest.main()
