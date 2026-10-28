# -*- coding: utf-8 -*-
"""As tools que chegam ao modelo depois de um lembrete (PRD 027).

Nao e so prompt: com site, cancelar e remarcar nao EXISTEM para o modelo; e
`confirm_attendance` so existe enquanto o lembrete esta vivo. Tambem cobre a
tool em si: ela confirma o agendamento DA SESSAO, e e idempotente.
"""
import os
import unittest
from datetime import date, datetime, time
from unittest import mock

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")
os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "test-reminders")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-queue")

from src.services import lembrete as L
from src.services import skills
from src.services.ai_tools import ToolExecutor, get_tool_definitions
from src.services.conversation_agent import _ferramentas_para

TZ = pytz.timezone("America/Sao_Paulo")
COM_SITE = {"timezone": "America/Sao_Paulo", "custom_domain": "agendar.x.com.br"}
SEM_SITE = {"timezone": "America/Sao_Paulo", "custom_domain": None}
APPT = {"id": "a1", "appointment_date": date(2026, 11, 6), "start_time": time(9, 0), "areas": "Axilas"}
AGORA = int(TZ.localize(datetime(2026, 11, 5, 12, 0)).timestamp())


def nomes(session, clinic, skill=skills.PACIENTE_COM_HORARIO):
    with mock.patch("src.services.lembrete.time.time", return_value=AGORA):
        return {t["name"] for t in _ferramentas_para(session, clinic, skill, get_tool_definitions(format="anthropic"))}


class TestFerramentasNoAgente(unittest.TestCase):
    def test_com_lembrete_e_site_sai_cancelar_entra_confirmar(self):
        n = nomes({"lembrete": L.abre(APPT, COM_SITE, AGORA)}, COM_SITE)
        self.assertNotIn("cancel_appointment", n)
        self.assertNotIn("reschedule_appointment", n)
        self.assertIn("confirm_attendance", n)
        self.assertIn("lookup_appointments", n)

    def test_com_lembrete_sem_site_mantem_cancelar(self):
        n = nomes({"lembrete": L.abre(APPT, SEM_SITE, AGORA)}, SEM_SITE)
        self.assertIn("cancel_appointment", n)
        self.assertIn("reschedule_appointment", n)
        self.assertIn("confirm_attendance", n)

    def test_sem_lembrete_nada_muda(self):
        self.assertNotIn("confirm_attendance", nomes({}, COM_SITE))
        self.assertIn("cancel_appointment", nomes({}, COM_SITE))

    def test_a_skill_continua_podando(self):
        n = nomes({"lembrete": L.abre(APPT, SEM_SITE, AGORA)}, SEM_SITE, skill=skills.PRIMEIRO_AGENDAMENTO)
        self.assertNotIn("cancel_appointment", n)
        self.assertIn("confirm_attendance", n)


class TestConfirmAttendance(unittest.TestCase):
    def _executor(self):
        db = mock.MagicMock()
        db.execute_write.return_value = 1
        return ToolExecutor(db, mock.MagicMock(), mock.MagicMock()), db

    def test_confirma_o_agendamento_da_sessao(self):
        ex, db = self._executor()
        with mock.patch("src.services.lembrete.time.time", return_value=AGORA):
            r = ex.execute("confirm_attendance", {}, {"clinic_id": "c1", "phone": "55", "session": {"lembrete": L.abre(APPT, COM_SITE, AGORA)}})
        self.assertEqual(r, {"success": True, "appointment_id": "a1"})
        sql, params = db.execute_write.call_args[0]
        self.assertIn("COALESCE(confirmado_em, NOW())", " ".join(sql.split()))
        self.assertIn("'PACIENTE'", sql)
        self.assertEqual(params, ("a1",))

    def test_sem_lembrete_vivo_recusa(self):
        ex, db = self._executor()
        r = ex.execute("confirm_attendance", {}, {"clinic_id": "c1", "phone": "55", "session": {}})
        self.assertIn("error", r)
        db.execute_write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
