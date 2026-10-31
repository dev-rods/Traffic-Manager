# -*- coding: utf-8 -*-
"""A janela do site: as próximas N datas com horário, contadas a partir de hoje.

Fechado e lotado não contam; hoje entra sem os horários que já passaram; N é
o `max_future_dates` da clínica, com o mesmo padrão do bot.
"""
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

import pytz

from src.services import janela_do_site
from src.services.availability_engine import AvailabilityEngine, PADRAO_DATAS_FUTURAS

SP = pytz.timezone("America/Sao_Paulo")
AGORA = SP.localize(datetime(2026, 10, 30, 14, 0))  # quinta


class Engine:
    """Agenda falsa: sábado fechado, 03/11 lotado, hoje com um horário passado."""

    def __init__(self):
        self.consultas = []

    def datas_com_regra(self, clinic_id, inicio, horizonte):
        return [(inicio + timedelta(days=i)).isoformat() for i in range(horizonte + 1)
                if (inicio + timedelta(days=i)).isoweekday() not in (6, 7)]

    def get_days_status(self, clinic_id, dates, duracao, a_partir_de=None):
        self.consultas.append(dates)
        out = {}
        for d in dates:
            if d == "2026-11-03":
                out[d] = {"status": "FULL", "slots": []}
                continue
            slots = ["09:00", "15:00"]
            minimo = (a_partir_de or {}).get(d)
            if minimo is not None:
                slots = [s for s in slots if int(s[:2]) * 60 + int(s[3:]) >= minimo]
            out[d] = {"status": "AVAILABLE" if slots else "FULL", "slots": slots}
        return out


class TestDiasOferecidos(unittest.TestCase):
    def test_as_proximas_n_com_horario_em_ordem(self):
        dias = janela_do_site.dias_oferecidos(Engine(), "c1", 30, AGORA, 4)
        # hoje (qui) só com 15:00, sex, seg; ter 03/11 lotada não conta; qua.
        self.assertEqual(list(dias), ["2026-10-30", "2026-11-02", "2026-11-04", "2026-11-05"])
        self.assertEqual(dias["2026-10-30"]["slots"], ["15:00"])
        self.assertEqual(dias["2026-11-02"]["slots"], ["09:00", "15:00"])

    def test_atravessa_a_virada_do_mes_sem_pedir_licenca(self):
        """Era a regra antiga: em 30/10 o site não oferecia nada de novembro."""
        dias = janela_do_site.dias_oferecidos(Engine(), "c1", 30, AGORA, 5)
        self.assertIn("2026-11-06", dias)

    def test_para_de_consultar_quando_completa(self):
        engine = Engine()
        janela_do_site.dias_oferecidos(engine, "c1", 30, AGORA, 2)
        self.assertEqual(len(engine.consultas), 2)

    def test_menos_que_n_quando_a_agenda_nao_tem(self):
        engine = Engine()
        engine.datas_com_regra = lambda c, i, h: ["2026-10-30", "2026-11-03"]
        self.assertEqual(list(janela_do_site.dias_oferecidos(engine, "c1", 30, AGORA, 5)), ["2026-10-30"])

    def test_hoje_sem_horario_restante_nao_conta(self):
        tarde = SP.localize(datetime(2026, 10, 30, 16, 0))
        dias = janela_do_site.dias_oferecidos(Engine(), "c1", 30, tarde, 1)
        self.assertEqual(list(dias), ["2026-11-02"])


class TestQuantas(unittest.TestCase):
    def test_configurado(self):
        self.assertEqual(janela_do_site.quantas({"max_future_dates": 12}), 12)

    def test_padrao_e_o_mesmo_do_bot(self):
        for clinica in ({}, {"max_future_dates": None}, {"max_future_dates": 0}):
            self.assertEqual(janela_do_site.quantas(clinica), PADRAO_DATAS_FUTURAS)


class TestDatasComRegraDoMotor(unittest.TestCase):
    def test_inclui_o_inicio_diferente_do_bot(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [{"day_of_week": 4, "rule_date": None}]  # quintas
        engine = AvailabilityEngine(db)
        hoje = date(2026, 10, 29)  # quinta
        self.assertEqual(engine.datas_com_regra("c1", hoje, 7)[0], "2026-10-29")
        self.assertEqual(engine._candidate_dates("c1", hoje, 7), ["2026-11-05"])


if __name__ == "__main__":
    unittest.main()
