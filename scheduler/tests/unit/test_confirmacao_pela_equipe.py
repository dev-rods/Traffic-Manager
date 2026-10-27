# -*- coding: utf-8 -*-
"""A recepcao confirma (ou desfaz) a presenca pelo popover; e a antecedencia do
lembrete automatico tem limites (PRD 027)."""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "t")
os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.appointment import update as h
from src.functions.clinic import update as hc
from src.utils.acesso import Identidade, STAFF

IDENT = Identidade(papel=STAFF, user_id="u1", clinic_id="c1")


def evento(body):
    return {"pathParameters": {"appointmentId": "a1"}, "headers": {"x-api-key": "k"}, "body": json.dumps(body)}


class TestConfirmado(unittest.TestCase):
    def chama(self, body, linha=None):
        db = mock.MagicMock()
        db.execute_write_returning.return_value = linha if linha is not None else {
            "id": "a1", "confirmado_em": "2026-11-05T12:00:00Z", "confirmado_por": "EQUIPE"}
        with mock.patch.object(h, "require_acesso", return_value=(IDENT, None)), \
             mock.patch.object(h, "PostgresService", return_value=db), \
             mock.patch.object(h, "pode_tocar_agendamento", return_value=True), \
             mock.patch.object(h, "AppointmentService") as svc:
            return h.handler(evento(body), None), db, svc

    def test_confirma_grava_equipe(self):
        r, db, svc = self.chama({"confirmado": True})
        self.assertEqual(r["statusCode"], 200)
        sql = " ".join(db.execute_write_returning.call_args[0][0].split())
        self.assertIn("confirmado_por = 'EQUIPE'", sql)
        self.assertIn("status = 'CONFIRMED'", sql)
        svc.completo.assert_not_called()

    def test_desconfirma_limpa(self):
        r, db, _ = self.chama({"confirmado": False})
        self.assertEqual(r["statusCode"], 200)
        sql = " ".join(db.execute_write_returning.call_args[0][0].split())
        self.assertIn("confirmado_em = NULL", sql)

    def test_e_exclusivo(self):
        r, db, _ = self.chama({"confirmado": True, "notes": "x"})
        self.assertEqual(r["statusCode"], 400)
        db.execute_write_returning.assert_not_called()

    def test_404_quando_nao_confirmado(self):
        r, _, _ = self.chama({"confirmado": True}, linha={})
        self.assertEqual(r["statusCode"], 404)


class TestAntecedencia(unittest.TestCase):
    def chama(self, body):
        ev = {"pathParameters": {"clinicId": "c1"}, "headers": {"x-api-key": "k"}, "body": json.dumps(body)}
        db = mock.MagicMock()
        db.execute_write_returning.return_value = {"clinic_id": "c1", "lembrete_antecedencia_horas": 24}
        with mock.patch.object(hc, "require_api_key", return_value=("k", None)), \
             mock.patch.object(hc, "PostgresService", return_value=db):
            return hc.handler(ev, None), db

    def test_fora_dos_limites_recusa(self):
        for valor in (0, 73, "x", None):
            with self.subTest(valor=valor):
                r, db = self.chama({"lembrete_antecedencia_horas": valor})
                self.assertEqual(r["statusCode"], 400)
                db.execute_write_returning.assert_not_called()

    def test_dentro_passa_como_inteiro(self):
        r, db = self.chama({"lembrete_antecedencia_horas": "24", "lembrete_automatico": True})
        self.assertEqual(r["statusCode"], 200)
        sql, params = db.execute_write_returning.call_args[0]
        self.assertIn("lembrete_antecedencia_horas = %s", sql)
        self.assertIn("lembrete_automatico = %s", sql)
        self.assertIn(24, params)


if __name__ == "__main__":
    unittest.main()
