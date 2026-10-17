# -*- coding: utf-8 -*-
"""O status por dia do site público é a mesma agenda que o bot consulta.

`get_days_status` era uma cópia das queries de `janelas_livres` (regras ->
exceções -> agendamentos). Duas cópias da regra de agenda divergem na próxima
mudança, e aí o site oferece um horário que o bot diria estar ocupado. Agora
ela chama as mesmas funções; estes testes conferem que os horários batem dia a
dia com `get_available_slots_multi` e que o corte de "hoje" funciona.
"""
import inspect
import unittest
from datetime import time

from src.services.availability_engine import AvailabilityEngine

CLINIC = "clinica-teste-0001"

# 2026-10-19 segunda (dow 1), 20 terça (2), 21 quarta (3), 25 domingo (0)
REGRAS = {
    1: [{"start_time": time(9, 0), "end_time": time(12, 0), "rule_date": None}],
    2: [{"start_time": time(9, 0), "end_time": time(10, 0), "rule_date": None}],
    3: [{"start_time": time(9, 0), "end_time": time(12, 0), "rule_date": None}],
}
EXCECOES = {
    "2026-10-21": [{"exception_type": "BLOCKED", "start_time": None, "end_time": None}],
}
AGENDAMENTOS = {
    # terça 9h-10h lotada
    "2026-10-20": [{"start_time": time(9, 0), "end_time": time(10, 0)}],
    "2026-10-19": [{"start_time": time(10, 0), "end_time": time(10, 30)}],
}


class Db:
    def __init__(self):
        self.consultas = []

    def execute_query(self, sql, params=None):
        self.consultas.append(sql)
        if "buffer_minutes" in sql:
            return [{"buffer_minutes": 10}]
        if "availability_rules" in sql:
            return REGRAS.get(params[1], [])
        if "availability_exceptions" in sql:
            return EXCECOES.get(params[1], [])
        if "FROM scheduler.appointments" in sql:
            return AGENDAMENTOS.get(params[1], [])
        return []


DATAS = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-25"]


class TestMesmaAgendaDoBot(unittest.TestCase):
    def test_status_de_cada_tipo_de_dia(self):
        dias = AvailabilityEngine(Db()).get_days_status(CLINIC, DATAS, 30)
        self.assertEqual(dias["2026-10-19"]["status"], "AVAILABLE")
        self.assertEqual(dias["2026-10-20"], {"status": "FULL", "slots": []})
        self.assertEqual(dias["2026-10-21"], {"status": "CLOSED", "slots": []})
        self.assertEqual(dias["2026-10-25"], {"status": "CLOSED", "slots": []})

    def test_horarios_iguais_aos_do_bot(self):
        dias = AvailabilityEngine(Db()).get_days_status(CLINIC, DATAS, 30)
        for d in DATAS:
            with self.subTest(data=d):
                bot = AvailabilityEngine(Db()).get_available_slots_multi(CLINIC, d, 30)
                self.assertEqual(dias[d]["slots"], bot)

    def test_nao_tem_query_propria(self):
        fonte = inspect.getsource(AvailabilityEngine.get_days_status)
        for tabela in ("availability_rules", "availability_exceptions", "scheduler.appointments"):
            self.assertNotIn(tabela, fonte)

    def test_buffer_lido_uma_vez_para_a_semana(self):
        db = Db()
        AvailabilityEngine(db).get_days_status(CLINIC, DATAS, 30)
        self.assertEqual(sum("buffer_minutes" in q for q in db.consultas), 1)


class TestCorteDeHoje(unittest.TestCase):
    def test_horario_que_ja_passou_nao_entra(self):
        engine = AvailabilityEngine(Db())
        cheio = engine.get_days_status(CLINIC, ["2026-10-19"], 30)["2026-10-19"]["slots"]
        cortado = engine.get_days_status(
            CLINIC, ["2026-10-19"], 30, a_partir_de={"2026-10-19": 10 * 60 + 41}
        )["2026-10-19"]["slots"]
        self.assertTrue(cheio)
        self.assertEqual(cortado, [s for s in cheio if s >= "10:41"])
        self.assertNotIn("09:00", cortado)

    def test_dia_aberto_sem_horario_restante_e_lotado_e_nao_fechado(self):
        dias = AvailabilityEngine(Db()).get_days_status(
            CLINIC, ["2026-10-19"], 30, a_partir_de={"2026-10-19": 23 * 60})
        self.assertEqual(dias["2026-10-19"], {"status": "FULL", "slots": []})

    def test_corte_so_vale_para_a_data_indicada(self):
        engine = AvailabilityEngine(Db())
        sem = engine.get_days_status(CLINIC, ["2026-10-19"], 30)
        com = engine.get_days_status(CLINIC, ["2026-10-19"], 30, a_partir_de={"2026-10-18": 23 * 60})
        self.assertEqual(sem, com)


if __name__ == "__main__":
    unittest.main()
