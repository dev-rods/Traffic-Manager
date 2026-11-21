# -*- coding: utf-8 -*-
"""Cancelamento ou falta pela antecedência (PRD 054).

A linha são 24 h antes da ABERTURA DA AGENDA no dia da sessão (o start_time
cadastrado em "Horários"), não antes da hora da sessão - decisão do André em
20/11/2026. Sem regra para o dia, vale a hora da sessão.
"""
import unittest
from datetime import date, datetime, time
from unittest import mock

from src.services import desfecho


class DbDeRegras:
    def __init__(self, regras=(), excecoes=()):
        self.regras, self.excecoes = list(regras), list(excecoes)

    def execute_query(self, sql, params=None):
        if "availability_rules" in sql:
            return self.regras
        if "availability_exceptions" in sql:
            return self.excecoes
        if "FROM scheduler.clinics" in sql:
            return [{"timezone": "America/Sao_Paulo"}]
        return []


DIA = date(2026, 11, 25)  # quarta
SESSAO = time(15, 0)


class TestAberturaDaAgenda(unittest.TestCase):
    def test_a_regra_mais_cedo_do_dia(self):
        db = DbDeRegras([{"start_time": time(13, 0), "rule_date": None},
                         {"start_time": time(9, 0), "rule_date": None}])
        self.assertEqual(desfecho.abertura_da_agenda(db, "c", DIA, SESSAO), time(9, 0))

    def test_regra_de_data_fixa_vence_a_recorrente(self):
        db = DbDeRegras([{"start_time": time(9, 0), "rule_date": None},
                         {"start_time": time(11, 0), "rule_date": DIA}])
        self.assertEqual(desfecho.abertura_da_agenda(db, "c", DIA, SESSAO), time(11, 0))

    def test_special_hours_vence_tudo(self):
        db = DbDeRegras([{"start_time": time(9, 0), "rule_date": None}],
                        [{"exception_type": "SPECIAL_HOURS", "start_time": time(12, 0)}])
        self.assertEqual(desfecho.abertura_da_agenda(db, "c", DIA, SESSAO), time(12, 0))

    def test_sem_regra_ou_bloqueado_vale_a_hora_da_sessao(self):
        self.assertEqual(desfecho.abertura_da_agenda(DbDeRegras(), "c", DIA, SESSAO), SESSAO)
        db = DbDeRegras([{"start_time": time(9, 0), "rule_date": None}],
                        [{"exception_type": "BLOCKED", "start_time": None}])
        self.assertEqual(desfecho.abertura_da_agenda(db, "c", DIA, SESSAO), SESSAO)

    def test_hora_como_texto_tambem_serve(self):
        db = DbDeRegras([{"start_time": "09:00:00", "rule_date": None}])
        self.assertEqual(desfecho.abertura_da_agenda(db, "c", DIA, "15:00:00"), time(9, 0))


class TestClassifica(unittest.TestCase):
    ABERTURA = datetime(2026, 11, 25, 9, 0)

    def test_vinte_e_quatro_horas_antes_da_abertura_e_cancelamento(self):
        self.assertEqual(desfecho.classifica(self.ABERTURA, datetime(2026, 11, 24, 8, 59)), "CANCELLED")
        self.assertEqual(desfecho.classifica(self.ABERTURA, datetime(2026, 11, 24, 9, 0)), "CANCELLED",
                         "exatamente 24 h ainda e cancelamento")

    def test_um_minuto_depois_e_falta(self):
        self.assertEqual(desfecho.classifica(self.ABERTURA, datetime(2026, 11, 24, 9, 1)), "NO_SHOW")

    def test_no_dia_e_depois_da_sessao_e_falta(self):
        self.assertEqual(desfecho.classifica(self.ABERTURA, datetime(2026, 11, 25, 10, 0)), "NO_SHOW")
        self.assertEqual(desfecho.classifica(self.ABERTURA, datetime(2026, 11, 26, 10, 0)), "NO_SHOW")


class TestDesfechoDoAgendamento(unittest.TestCase):
    """A hora da sessao NAO e a referencia: sessao as 15h, agenda abre as 9h,
    cancelar as 10h do dia anterior ja e falta (faltam 23 h para a abertura)."""

    def _agendamento(self):
        return {"id": "ap1", "clinic_id": "c", "appointment_date": DIA, "start_time": SESSAO}

    def test_usa_a_abertura_e_nao_a_hora_da_sessao(self):
        db = DbDeRegras([{"start_time": time(9, 0), "rule_date": None}])
        agora = datetime(2026, 11, 24, 10, 0)
        self.assertEqual(desfecho.desfecho_do_agendamento(db, self._agendamento(), agora=agora), "NO_SHOW")
        self.assertEqual(desfecho.desfecho_do_agendamento(db, self._agendamento(),
                                                          agora=datetime(2026, 11, 24, 8, 30)), "CANCELLED")

    def test_sem_regra_a_hora_da_sessao_e_a_referencia(self):
        db = DbDeRegras()
        self.assertEqual(desfecho.desfecho_do_agendamento(db, self._agendamento(),
                                                          agora=datetime(2026, 11, 24, 14, 59)), "CANCELLED")
        self.assertEqual(desfecho.desfecho_do_agendamento(db, self._agendamento(),
                                                          agora=datetime(2026, 11, 24, 15, 1)), "NO_SHOW")

    def test_sem_relogio_injetado_le_o_fuso_da_clinica(self):
        db = DbDeRegras()
        with mock.patch.object(desfecho.relogio, "agora_na_clinica",
                               return_value=datetime(2026, 11, 20, 10, 0)) as relogio:
            desfecho.desfecho_do_agendamento(db, self._agendamento())
        relogio.assert_called_once_with("America/Sao_Paulo")


if __name__ == "__main__":
    unittest.main()
