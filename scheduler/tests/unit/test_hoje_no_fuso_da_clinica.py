# -*- coding: utf-8 -*-
""""Hoje" no SQL é a data em Brasília, nunca `CURRENT_DATE`.

Em 05/11/2026, às 22h50, o agendamento das 23h50 do mesmo dia sumiu do iPad
("Não encontramos seu agendamento"): `get_active_appointments_by_phone`
filtrava `appointment_date >= CURRENT_DATE`, e o banco, em UTC, já estava no
dia seguinte. O mesmo predicado estava em "Meus agendamentos" do site, na
identificação de paciente do bot e nos filtros de "próxima visita" do
painel. A conversão offline já tinha corrigido o dela em 04/10/2026
(`test_elegibilidade_tem_um_dono`), em separado; agora a expressão mora em
`relogio.HOJE_SQL` e este teste proíbe o `CURRENT_DATE` voltar.
"""
import os
import re
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.services import relogio
from src.services.appointment_service import AppointmentService

SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
CLINIC = "clinica-teste-0001"


class Db:
    def __init__(self):
        self.sqls = []

    def execute_query(self, sql, params=None):
        self.sqls.append(sql)
        return []


class TestHoje(unittest.TestCase):
    def test_nenhum_current_date_em_src(self):
        culpados = []
        for raiz, _, arquivos in os.walk(SRC):
            for nome in arquivos:
                if not nome.endswith(".py"):
                    continue
                caminho = os.path.join(raiz, nome)
                with open(caminho, encoding="utf-8") as f:
                    for n, linha in enumerate(f, 1):
                        if linha.lstrip().startswith("#"):
                            continue  # comentário contando a história, não SQL
                        if re.search(r"\bCURRENT_DATE\b", linha):
                            culpados.append("%s:%d" % (os.path.relpath(caminho, SRC), n))
        self.assertEqual(culpados, [])

    def test_lista_do_ipad_e_meus_agendamentos_usam_a_data_de_brasilia(self):
        db = Db()
        AppointmentService(db).get_active_appointments_by_phone(CLINIC, "5511999990000")
        self.assertEqual(len(db.sqls), 1)
        self.assertIn("appointment_date >= " + relogio.HOJE_SQL, db.sqls[0])

    def test_a_expressao_e_a_mesma_da_conversao_offline(self):
        self.assertEqual(relogio.HOJE_SQL, "(NOW() AT TIME ZONE 'America/Sao_Paulo')::date")
