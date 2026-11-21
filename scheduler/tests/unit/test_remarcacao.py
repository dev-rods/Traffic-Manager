# -*- coding: utf-8 -*-
"""Cancelar classifica pela antecedência; remarcar para outra data encerra o
antigo e cria o novo, vinculados (PRD 054).

O banco falso roteia por SQL e guarda as escritas: é o que se inspeciona.
"""
import os
import unittest
from datetime import date, time
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.services import appointment_service as mod
from src.services.appointment_service import (
    AppointmentService, ConflictError, MudancaDeData, NotFoundError,
)
from src.services.desfecho import DesfechoInvalido

CLINIC = "c"
APPT = "11111111-1111-1111-1111-111111111111"
NOVO = "22222222-2222-2222-2222-222222222222"


def _colunas(sql):
    dentro = sql.split("scheduler.appointments (", 1)[1].split(")", 1)[0]
    return [c.strip() for c in dentro.split(",") if c.strip()]


class Db:
    def __init__(self, conflito=False, consent_link=None):
        self.conflito = conflito
        self.escritas = []
        self.antigo = {
            "id": APPT, "clinic_id": CLINIC, "patient_id": "p1", "professional_id": None,
            "service_id": "s1", "appointment_date": date(2026, 11, 27), "start_time": time(14, 0),
            "end_time": time(14, 30), "status": "CONFIRMED", "version": 2,
            "total_duration_minutes": 30, "manual_duration_minutes": 45,
            "discount_pct": 10, "discount_cents": None, "discount_reason": "tier_2",
            "original_price_cents": 20000, "final_price_cents": 18000,
            "full_name": "Maria", "notes": "obs", "is_first_visit": True,
            "consent_link_sent_at": consent_link,
        }

    def execute_query(self, sql, params=None):
        if "SELECT * FROM scheduler.appointments WHERE id" in sql:
            return [dict(self.antigo)]
        if "FROM scheduler.appointment_service_areas" in sql and "service_id, area_id" in sql:
            return [{"service_id": "s1", "area_id": "a1"}, {"service_id": "s1", "area_id": "a2"}]
        if "SELECT phone FROM scheduler.patients" in sql:
            return [{"phone": "5511999990001"}]
        if "AS pairs(service_id, area_id)" in sql and "area_name" in sql:
            return [{"service_id": "s1", "area_id": a, "service_name": "Laser", "area_name": n,
                     "duration_minutes": 15, "price_cents": 10000} for a, n in (("a1", "Axilas"), ("a2", "Buço"))]
        if "SELECT id FROM scheduler.appointments" in sql and "start_time <" in sql:
            return [{"id": "outro"}] if self.conflito else []
        # o create_appointment
        if "FROM scheduler.patients" in sql:
            return [{"id": "p1", "deleted_at": None, "name": "Maria"}]
        if "FROM scheduler.services" in sql:
            return [{"id": "s1", "duration_minutes": 20, "name": "Laser", "price_cents": 20000}]
        if "duration_rules" in sql:
            return [{"floor_minutes": 10, "ceiling_minutes": 50, "step_minutes": 5, "is_active": True}]
        if "AS total" in sql:
            return [{"total": 20}]
        if "total_price" in sql:
            return [{"total_price": 20000}]
        return []

    def execute_write(self, sql, params=None):
        self.escritas.append((sql, params))
        return 1

    def execute_write_returning(self, sql, params=None):
        self.escritas.append((sql, params))
        if "INSERT INTO scheduler.appointments" in sql:
            return {"id": NOVO, "clinic_id": CLINIC, "patient_id": "p1", "created_at": None}
        if "UPDATE scheduler.appointments a" in sql and "rescheduled_to_id = %(novo)s" in sql:
            return {"id": APPT}  # vincula_antecessor achou o antigo
        if "SET status = %s" in sql:
            linha = dict(self.antigo)
            linha["status"] = params[0]
            return linha
        return {"id": APPT}

    def sql_com(self, trecho):
        return [(s, p) for s, p in self.escritas if trecho in s]


def _servico(db):
    s = AppointmentService(db)
    s.lead_service = None
    return s


class TestCancelarClassifica(unittest.TestCase):
    def test_automatico_cancelamento(self):
        db = Db()
        with mock.patch.object(mod, "desfecho_do_agendamento", return_value="CANCELLED"), \
             mock.patch.object(mod, "passa_a_marca_adiante"):
            r = _servico(db).cancel_appointment(APPT)
        self.assertEqual(r["outcome"], "CANCELLED")
        sql, params = db.sql_com("SET status = %s")[0]
        self.assertEqual(params[:3], ("CANCELLED", None, None))
        self.assertIn("status = 'CONFIRMED'", sql)

    def test_automatico_falta_tambem_passa_a_marca_e_cancela_lembrete(self):
        db = Db()
        lembretes = mock.MagicMock()
        s = _servico(db)
        s.reminder_service = lembretes
        with mock.patch.object(mod, "desfecho_do_agendamento", return_value="NO_SHOW"), \
             mock.patch.object(mod, "passa_a_marca_adiante") as passa:
            r = s.cancel_appointment(APPT)
        self.assertEqual(r["outcome"], "NO_SHOW")
        self.assertEqual(db.sql_com("SET status = %s")[0][1][0], "NO_SHOW")
        passa.assert_called_once_with(db, APPT)
        lembretes.cancel_reminder.assert_called_once_with(APPT)

    def test_sobrepor_exige_motivo_e_grava_quem_e_por_que(self):
        db = Db()
        with mock.patch.object(mod, "desfecho_do_agendamento", return_value="NO_SHOW"), \
             mock.patch.object(mod, "passa_a_marca_adiante"):
            with self.assertRaises(DesfechoInvalido):
                _servico(db).cancel_appointment(APPT, desfecho="CANCELLED")
            with self.assertRaises(DesfechoInvalido):
                _servico(db).cancel_appointment(APPT, desfecho="CANCELLED", motivo="   ")
            r = _servico(db).cancel_appointment(APPT, desfecho="CANCELLED", motivo="doença", autor="Ana")
        self.assertEqual(r["outcome"], "CANCELLED")
        _, params = db.sql_com("SET status = %s")[-1]
        self.assertEqual(params[:3], ("CANCELLED", "Ana", "doença"))

    def test_desfecho_igual_ao_automatico_nao_e_sobreposicao(self):
        db = Db()
        with mock.patch.object(mod, "desfecho_do_agendamento", return_value="NO_SHOW"), \
             mock.patch.object(mod, "passa_a_marca_adiante"):
            _servico(db).cancel_appointment(APPT, desfecho="NO_SHOW", autor="Ana")
        _, params = db.sql_com("SET status = %s")[0]
        self.assertEqual(params[:3], ("NO_SHOW", None, None))

    def test_desfecho_desconhecido_recusa(self):
        with mock.patch.object(mod, "desfecho_do_agendamento", return_value="NO_SHOW"):
            with self.assertRaises(DesfechoInvalido):
                _servico(Db()).cancel_appointment(APPT, desfecho="RESCHEDULED", motivo="x")

    def test_sem_agendamento_confirmado_404(self):
        db = Db()
        db.antigo["status"] = "CANCELLED"
        db.execute_query = lambda sql, params=None: []
        with self.assertRaises(NotFoundError):
            _servico(db).cancel_appointment(APPT)


class TestRemarca(unittest.TestCase):
    def _remarca(self, db, **kw):
        with mock.patch.object(mod, "desfecho_do_agendamento", return_value=kw.pop("automatico", "CANCELLED")), \
             mock.patch.object(mod, "passa_a_marca_adiante"), \
             mock.patch.object(mod, "e_primeira_visita", return_value=False):
            return _servico(db).remarca(APPT, "2026-12-03", "10:00", **kw)

    def test_antigo_encerra_e_novo_nasce_igual(self):
        db = Db(consent_link="2026-11-20T10:00:00Z")
        r = self._remarca(db)

        self.assertEqual(r["antigo"]["status"], "CANCELLED")
        self.assertEqual(r["antigo"]["outcome"], "CANCELLED")
        self.assertEqual(r["antigo"]["rescheduled_to_id"], NOVO)
        self.assertEqual(r["novo"]["rescheduled_from_id"], APPT)

        sql, params = db.sql_com("INSERT INTO scheduler.appointments")[0]
        gravado = dict(zip(_colunas(sql), params))
        self.assertEqual(gravado["appointment_date"], "2026-12-03")
        self.assertEqual(str(gravado["start_time"])[:5], "10:00")
        self.assertEqual(gravado["manual_duration_minutes"], 45)
        self.assertEqual(gravado["discount_pct"], 10)
        self.assertEqual(gravado["discount_reason"], "tier_2", "o desconto gravado vai como esta: nao re-decide")
        self.assertEqual(gravado["notes"], "obs")
        self.assertEqual(gravado["full_name"], "Maria")
        # areas copiadas
        self.assertTrue(db.sql_com("INSERT INTO scheduler.appointment_service_areas"))
        # vinculo nos dois sentidos
        self.assertTrue(db.sql_com("SET rescheduled_from_id = %s::uuid"))
        self.assertTrue(db.sql_com("SET rescheduled_to_id = %s::uuid, updated_at = NOW()"))
        # pagamento vivo e link dos documentos acompanham
        sql_pag = db.sql_com("UPDATE scheduler.appointment_payments")[0][0]
        self.assertIn("'PENDING', 'AWAITING_CASH', 'PAID'", sql_pag)
        self.assertTrue(db.sql_com("SET consent_link_sent_at = %s"))

    def test_menos_de_24h_deixa_o_antigo_em_falta(self):
        db = Db()
        r = self._remarca(db, automatico="NO_SHOW")
        self.assertEqual(r["antigo"]["status"], "NO_SHOW")
        self.assertEqual(r["antigo"]["outcome"], "NO_SHOW")

    def test_sobreposicao_do_painel_passa_para_o_antigo(self):
        db = Db()
        r = self._remarca(db, automatico="NO_SHOW", desfecho="CANCELLED", motivo="doença", autor="Ana")
        self.assertEqual(r["antigo"]["outcome"], "CANCELLED")
        _, params = db.sql_com("SET status = %s")[0]
        self.assertEqual(params[1:3], ("Ana", "doença"))

    def test_conflito_no_horario_novo_nao_toca_em_nada(self):
        db = Db(conflito=True)
        with self.assertRaises(ConflictError):
            self._remarca(db)
        self.assertEqual(db.escritas, [], "um conflito nao pode deixar a paciente sem sessao")

    def test_sem_link_de_documentos_nao_escreve_a_coluna(self):
        db = Db(consent_link=None)
        self._remarca(db)
        self.assertFalse(db.sql_com("SET consent_link_sent_at = %s"))

    def test_mesma_data_delega_ao_reschedule(self):
        db = Db()
        s = _servico(db)
        with mock.patch.object(AppointmentService, "reschedule_appointment", return_value={"id": APPT}) as resc:
            r = s.remarca(APPT, "2026-11-27", "16:00", tolerancia_minutos=15)
        self.assertIsNone(r["antigo"])
        resc.assert_called_once_with(APPT, "2026-11-27", "16:00", tolerancia_minutos=15)
        self.assertFalse(db.sql_com("SET status = %s"))


class TestRescheduleSoMesmaData(unittest.TestCase):
    def test_outra_data_e_recusada(self):
        db = Db()
        with self.assertRaises(MudancaDeData):
            _servico(db).reschedule_appointment(APPT, "2026-12-03", "10:00")
        self.assertEqual(db.escritas, [])


if __name__ == "__main__":
    unittest.main()
