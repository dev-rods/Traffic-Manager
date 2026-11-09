# -*- coding: utf-8 -*-
"""Remarcar derruba a confirmação de presença (PRD 043).

Quem confirmou confirmou um HORÁRIO. Até 08/11/2026 a agenda seguia exibindo
"Confirmada" depois de o agendamento ir para outro dia - horário que a paciente
nunca viu. E como ninguém a avisa da remarcação, a recepção acreditava numa
confirmação que não existia.

Reusa o dublê de `test_duracao_manual_sobrevive`: ele responde por SQL e guarda
cada UPDATE, que é o que se inspeciona aqui.
"""
import unittest

from tests.unit.test_duracao_manual_sobrevive import APPT, DbFalso
from src.services.appointment_service import AppointmentService


class TestRemarcarLimpaAConfirmacao(unittest.TestCase):
    def _remarca(self, agendamento=None):
        db = DbFalso(agendamento or {})
        AppointmentService(db).reschedule_appointment(APPT, "2026-09-29", "09:00")
        return db

    def test_o_update_zera_confirmado_em_e_por(self):
        db = self._remarca({"confirmado_em": "2026-09-22T10:00:00Z",
                            "confirmado_por": "PACIENTE"})

        sql, _ = db.update_em("appointment_date")
        self.assertIn("confirmado_em = NULL", sql)
        self.assertIn("confirmado_por = NULL", sql)

    def test_vale_tambem_para_quem_nao_estava_confirmado(self):
        """Zerar o que já é nulo é inofensivo, e evita um segundo caminho de
        escrita só para o caso confirmado - que divergiria em silêncio."""
        db = self._remarca({"confirmado_em": None, "confirmado_por": None})

        sql, _ = db.update_em("appointment_date")
        self.assertIn("confirmado_em = NULL", sql)

    def test_o_resto_do_update_continua_igual(self):
        """A data, a hora e a duração seguem no mesmo UPDATE: o PRD 043 não
        mexe no que remarcar já fazia."""
        db = self._remarca({"manual_duration_minutes": 75,
                            "total_duration_minutes": 75})

        sql, params = db.update_em("appointment_date")
        self.assertIn("2026-09-29", params)
        self.assertIn("09:00", params)
        self.assertIn(75, params, "a duração manual foi perdida ao remarcar")
        self.assertIn("version = version + 1", sql)

    def test_nenhum_outro_update_desfaz_a_limpeza(self):
        """Se algum caminho posterior reescrevesse a confirmação, o efeito
        desta mudança se perderia sem sintoma na tela."""
        db = self._remarca({"confirmado_em": "2026-09-22T10:00:00Z"})

        reconfirma = [sql for sql, _ in db.escritas
                      if "confirmado_em = NOW()" in sql]
        self.assertEqual(reconfirma, [])


if __name__ == "__main__":
    unittest.main()
