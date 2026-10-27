# -*- coding: utf-8 -*-
"""O lote automatico sai `antecedencia` horas antes do primeiro horario do dia,
uma vez por dia, e so para clinica com o interruptor ligado."""
import os
import unittest
from datetime import datetime, time, timezone
from unittest import mock

import pytz

os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "t")

from src.functions.reminder import automaticos as A

TZ = pytz.timezone("America/Sao_Paulo")
CLINIC = {"clinic_id": "c1", "timezone": "America/Sao_Paulo", "lembrete_automatico": True,
          "lembrete_antecedencia_horas": 24, "janela_de_silencio": None, "active": True}


def appts(*horas, **kw):
    base = {"status": "CONFIRMED", "lembrete_enviado_em": None, "lembrete_status": None, "patient_phone": "551199"}
    base.update(kw)
    return [dict(base, id=f"a{h}", start_time=time(h, 0)) for h in horas]


class TestSendAtSeVencido(unittest.TestCase):
    def test_antes_da_hora_nao(self):
        agora = TZ.localize(datetime(2026, 11, 5, 8, 59))
        self.assertIsNone(A.send_at_se_vencido(CLINIC, "2026-11-06", appts(9, 11), agora))

    def test_na_hora_sim_e_e_agora(self):
        agora = TZ.localize(datetime(2026, 11, 5, 9, 0))
        self.assertEqual(A.send_at_se_vencido(CLINIC, "2026-11-06", appts(9, 11), agora), agora)

    def test_usa_o_primeiro_horario_nao_o_ultimo(self):
        agora = TZ.localize(datetime(2026, 11, 5, 10, 30))
        self.assertIsNotNone(A.send_at_se_vencido(CLINIC, "2026-11-06", appts(11, 10), agora))
        self.assertIsNone(A.send_at_se_vencido(CLINIC, "2026-11-06", appts(11, 12), agora))

    def test_sem_agendamento_nao(self):
        agora = TZ.localize(datetime(2026, 11, 5, 12, 0))
        self.assertIsNone(A.send_at_se_vencido(CLINIC, "2026-11-06", [], agora))

    def test_ja_lembrado_ou_na_fila_nao_repete(self):
        agora = TZ.localize(datetime(2026, 11, 5, 12, 0))
        self.assertIsNone(A.send_at_se_vencido(CLINIC, "2026-11-06", appts(9, lembrete_enviado_em=agora), agora))
        self.assertIsNone(A.send_at_se_vencido(CLINIC, "2026-11-06", appts(9, lembrete_status="ENFILEIRADO"), agora))

    def test_antecedencia_da_clinica(self):
        clinic = dict(CLINIC, lembrete_antecedencia_horas=2)
        self.assertIsNone(A.send_at_se_vencido(clinic, "2026-11-06", appts(9), TZ.localize(datetime(2026, 11, 6, 6, 59))))
        self.assertIsNotNone(A.send_at_se_vencido(clinic, "2026-11-06", appts(9), TZ.localize(datetime(2026, 11, 6, 7, 0))))

    def test_vencido_dentro_do_silencio_vai_para_o_fim(self):
        clinic = dict(CLINIC, lembrete_antecedencia_horas=10)  # 9h - 10h = 23h do dia anterior
        agora = TZ.localize(datetime(2026, 11, 5, 23, 30))
        s = A.send_at_se_vencido(clinic, "2026-11-06", appts(9), agora)
        self.assertGreater(s, agora)
        self.assertEqual(s.astimezone(TZ).strftime("%H:%M"), "04:59")


class TestHandler(unittest.TestCase):
    def test_so_clinica_ligada_e_so_uma_vez(self):
        db = mock.MagicMock()
        db.execute_query.side_effect = lambda sql, p=None: (
            [CLINIC] if "FROM scheduler.clinics" in sql else appts(9))
        agora = TZ.localize(datetime(2026, 11, 5, 10, 0)).astimezone(timezone.utc)
        with mock.patch.object(A, "PostgresService", return_value=db), \
             mock.patch.object(A, "ReminderService"), \
             mock.patch.object(A, "enfileira", return_value={"enfileirados": 1}) as enf, \
             mock.patch.object(A, "_agora", return_value=agora):
            r = A.handler({}, None)
        # So o SQL filtra pelo interruptor; aqui conferimos que o filtro esta la.
        sql_clinicas = [c.args[0] for c in db.execute_query.call_args_list if "FROM scheduler.clinics" in c.args[0]][0]
        self.assertIn("lembrete_automatico = TRUE", sql_clinicas)
        # 3 dias olhados, os 3 com 9h e vencidos (24h antes de 06, 07 e 08/11 ja passou para o dia 06 apenas)
        dias = [c.args[3] for c in enf.call_args_list]
        self.assertEqual(dias, ["2026-11-06"])
        self.assertEqual(r["lotes"], 1)

    def test_erro_num_dia_nao_derruba_os_outros(self):
        db = mock.MagicMock()
        chamadas = {"n": 0}

        def query(sql, p=None):
            if "FROM scheduler.clinics" in sql:
                return [dict(CLINIC, lembrete_antecedencia_horas=72)]
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise RuntimeError("boom")
            return appts(9)

        db.execute_query.side_effect = query
        agora = TZ.localize(datetime(2026, 11, 5, 10, 0)).astimezone(timezone.utc)
        with mock.patch.object(A, "PostgresService", return_value=db), \
             mock.patch.object(A, "ReminderService"), \
             mock.patch.object(A, "enfileira", return_value={"enfileirados": 1}) as enf, \
             mock.patch.object(A, "_agora", return_value=agora):
            r = A.handler({}, None)
        self.assertEqual(len(enf.call_args_list), 2)
        self.assertEqual(r["lotes"], 2)


if __name__ == "__main__":
    unittest.main()
