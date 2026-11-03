# -*- coding: utf-8 -*-
"""Reagendamento não é cancelamento (PRD 035): o vínculo nasce no create.

Um terço dos CANCELLED de prod eram pessoas que remarcaram. O vínculo entre o
antigo e o novo nasce em `create_appointment`, por qualquer canal, e a
conversão do Google Ads muda de registro em vez de nascer outra.
"""
import os
import unittest
from datetime import datetime
from unittest import mock

os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.services import reagendamento
from src.services.appointment_service import AppointmentService

CLINIC = "clinica-1"
PHONE = "5511999990000"
NOVO = {"id": "ap-novo", "clinic_id": CLINIC, "patient_id": "p1",
        "created_at": datetime(2026, 10, 21, 12, 31, 16)}


class TestVinculaAntecessor(unittest.TestCase):

    def test_liga_e_devolve_o_antecessor(self):
        db = mock.MagicMock()
        db.execute_write_returning.return_value = {"id": "ap-antigo"}

        self.assertEqual(reagendamento.vincula_antecessor(db, NOVO), "ap-antigo")

        sql, params = db.execute_write_returning.call_args[0]
        self.assertIn("rescheduled_to_id IS NULL", sql)
        self.assertIn("status = 'CANCELLED'", sql)
        self.assertIn("ORDER BY c.updated_at DESC LIMIT 1", sql)
        self.assertEqual(params["novo"], "ap-novo")
        self.assertEqual(params["patient"], "p1")
        self.assertEqual(params["clinic"], CLINIC)

    def test_a_referencia_de_tempo_e_o_created_at_do_novo(self):
        """Não NOW(): o backfill reusa a função com registros antigos."""
        db = mock.MagicMock()
        db.execute_write_returning.return_value = None
        reagendamento.vincula_antecessor(db, NOVO)
        params = db.execute_write_returning.call_args[0][1]
        self.assertEqual(params["criado_em"], NOVO["created_at"])
        self.assertEqual(params["janela"], reagendamento.JANELA_DE_VINCULO_MIN)
        self.assertEqual(params["folga"], reagendamento.FOLGA_DEPOIS_MIN)

    def test_sem_antecessor_devolve_none(self):
        db = mock.MagicMock()
        db.execute_write_returning.return_value = None
        self.assertIsNone(reagendamento.vincula_antecessor(db, NOVO))

    def test_sem_paciente_nao_consulta(self):
        db = mock.MagicMock()
        self.assertIsNone(reagendamento.vincula_antecessor(db, {**NOVO, "patient_id": None}))
        db.execute_write_returning.assert_not_called()

    def test_candidato_nao_escreve(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [{"id": "ap-antigo"}]
        self.assertEqual(reagendamento.candidato_a_antecessor(db, NOVO)["id"], "ap-antigo")
        db.execute_write.assert_not_called()
        db.execute_write_returning.assert_not_called()

    def test_fragmentos_sao_complementares(self):
        """Um CANCELLED é reagendado OU cancelado de verdade, nunca os dois."""
        self.assertIn("rescheduled_to_id IS NOT NULL", reagendamento.E_REAGENDADO.format(a="a"))
        self.assertIn("rescheduled_to_id IS NULL", reagendamento.E_CANCELADO_DE_VERDADE.format(a="a"))
        self.assertIn("a.status = 'CANCELLED'", reagendamento.E_REAGENDADO.format(a="a"))
        self.assertIn("a.status = 'CANCELLED'", reagendamento.E_CANCELADO_DE_VERDADE.format(a="a"))


class DbRoteado:
    """O create inteiro passa por aqui. O que importa: o UPDATE de vínculo é
    distinguível do INSERT e responde com um antecessor quando mandado."""

    def __init__(self, antecessor=None):
        self.antecessor = antecessor
        self.escritas = []

    def execute_query(self, sql, params=None):
        if "FROM scheduler.patients" in sql:
            return [{"id": "p1", "deleted_at": None, "name": "Maria"}]
        if "FROM scheduler.services" in sql:
            return [{"id": "s1", "duration_minutes": 20, "name": "Laser", "price_cents": 9500}]
        if "duration_rules" in sql:
            return [{"floor_minutes": 15, "ceiling_minutes": 50, "step_minutes": 5, "is_active": True}]
        if "AS total" in sql:
            return [{"total": 15}]
        if "total_price" in sql:
            return [{"total_price": 9500}]
        return []

    def execute_write(self, sql, params=None):
        self.escritas.append(sql)
        return 1

    def execute_write_returning(self, sql, params=None):
        self.escritas.append(sql)
        if "INSERT INTO scheduler.appointments" in sql:
            return {"id": "ap-novo", "clinic_id": CLINIC, "patient_id": "p1",
                    "created_at": datetime(2026, 10, 21, 12, 31, 16)}
        if "SET rescheduled_to_id" in sql:
            return {"id": self.antecessor} if self.antecessor else None
        return {"id": "x"}


def cria(db, lead_service):
    service = AppointmentService(db, lead_service=lead_service)
    with mock.patch("src.services.appointment_service.e_primeira_visita", return_value=False):
        return service.create_appointment(
            clinic_id=CLINIC, phone=PHONE, service_id="s1",
            date="2026-10-22", time="14:00",
            service_area_pairs=[{"service_id": "s1", "area_id": "a1"}])


class TestNoCreate(unittest.TestCase):

    def test_com_antecessor_a_conversao_muda_de_registro_e_nao_nasce_outra(self):
        lead = mock.MagicMock()
        lead.move_conversion.return_value = True
        result = cria(DbRoteado(antecessor="ap-antigo"), lead)

        lead.move_conversion.assert_called_once_with("ap-antigo", "ap-novo", "2026-10-22 14:00-03:00")
        lead.record_conversion.assert_not_called()
        lead.mark_as_booked.assert_called_once()
        self.assertEqual(result["rescheduled_from_id"], "ap-antigo")

    def test_antecessor_sem_conversao_grava_a_conversao_nova(self):
        """Paciente orgânico remarcado: não havia conversão para mover, e o
        novo segue o caminho normal (que também é no-op sem gclid)."""
        lead = mock.MagicMock()
        lead.move_conversion.return_value = False
        cria(DbRoteado(antecessor="ap-antigo"), lead)
        lead.record_conversion.assert_called_once()

    def test_sem_antecessor_nada_muda(self):
        lead = mock.MagicMock()
        result = cria(DbRoteado(antecessor=None), lead)
        lead.move_conversion.assert_not_called()
        lead.record_conversion.assert_called_once()
        self.assertIsNone(result["rescheduled_from_id"])

    def test_falha_ao_mover_nao_derruba_o_agendamento(self):
        lead = mock.MagicMock()
        lead.move_conversion.side_effect = RuntimeError("banco fora")
        result = cria(DbRoteado(antecessor="ap-antigo"), lead)
        self.assertEqual(result["id"], "ap-novo")
        lead.record_conversion.assert_called_once()

    def test_sem_lead_service_o_vinculo_ainda_nasce(self):
        db = DbRoteado(antecessor="ap-antigo")
        result = cria(db, None)
        self.assertEqual(result["rescheduled_from_id"], "ap-antigo")
        self.assertTrue(any("SET rescheduled_to_id" in s for s in db.escritas))


class TestMoveConversion(unittest.TestCase):

    def test_move_e_so_redata_o_que_nao_subiu(self):
        from src.services.lead_service import LeadService
        db = mock.MagicMock()
        db.execute_write_returning.return_value = {"id": "lc1"}
        movida = LeadService(db).move_conversion("ap-antigo", "ap-novo", "2026-10-22 14:00-03:00")

        self.assertTrue(movida)
        sql, params = db.execute_write_returning.call_args[0]
        self.assertIn("SET appointment_id = %s::uuid", sql)
        self.assertIn("WHEN uploaded_at IS NULL", sql)
        self.assertEqual(params, ("ap-novo", "2026-10-22 14:00-03:00", "ap-antigo"))

    def test_sem_conversao_devolve_false(self):
        from src.services.lead_service import LeadService
        db = mock.MagicMock()
        db.execute_write_returning.return_value = None
        self.assertFalse(LeadService(db).move_conversion("a", "b", "2026-10-22 14:00-03:00"))


if __name__ == "__main__":
    unittest.main()
