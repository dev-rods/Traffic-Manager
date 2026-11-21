# -*- coding: utf-8 -*-
"""Uma sessão por mês-calendário por paciente (PRD 056), no serviço.

Criar e remarcar levantam `SessaoNoMesmoMes` com a sessão existente;
`substituir_mesmo_mes` cancela essa sessão com o desfecho da antecedência e o
novo nasce vinculado a ela, levando pagamento e link dos documentos;
`permitir_duas` grava quem autorizou e por quê. O banco falso roteia por SQL
e guarda as escritas, como em test_remarcacao.
"""
import os
import unittest
from datetime import date, time
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.services import appointment_service as mod
from src.services.appointment_service import (
    AppointmentService, ConflictError, SessaoNoMesmoMes,
)

CLINIC = "c"
FONE = "5511999990001"
EXISTENTE = "11111111-1111-1111-1111-111111111111"
NOVO = "22222222-2222-2222-2222-222222222222"
MOVIDO = "33333333-3333-3333-3333-333333333333"


class Db:
    def __init__(self, no_mes=True, conflito=False):
        self.no_mes = no_mes
        self.conflito = conflito
        self.escritas = []
        self.consultas = []
        self.existente = {
            "id": EXISTENTE, "clinic_id": CLINIC, "patient_id": "p1", "service_id": "s1",
            "appointment_date": date(2026, 11, 25), "start_time": time(14, 0), "end_time": time(14, 30),
            "status": "CONFIRMED", "version": 1, "total_duration_minutes": 30,
            "discount_pct": 0, "discount_cents": None, "discount_reason": None,
            "original_price_cents": 20000, "final_price_cents": 20000,
            "full_name": "Maria", "notes": None, "is_first_visit": False,
            "consent_link_sent_at": "2026-11-20T10:00:00Z", "professional_id": None,
            "manual_duration_minutes": None,
        }

    def execute_query(self, sql, params=None):
        self.consultas.append((sql, params))
        if "date_trunc('month', a.appointment_date)" in sql:
            if not self.no_mes:
                return []
            return [{"id": EXISTENTE, "appointment_date": date(2026, 11, 25), "start_time": time(14, 0),
                     "areas_display": "Axilas", "patient_name": "Maria"}]
        if "SELECT * FROM scheduler.appointments WHERE id" in sql:
            alvo = params[0]
            linha = dict(self.existente)
            if alvo == MOVIDO:
                linha.update({"id": MOVIDO, "appointment_date": date(2026, 12, 2), "consent_link_sent_at": None})
            return [linha]
        if "FROM scheduler.appointment_service_areas" in sql and "service_id, area_id" in sql:
            return [{"service_id": "s1", "area_id": "a1"}]
        if "SELECT phone FROM scheduler.patients" in sql:
            return [{"phone": FONE}]
        if "AS pairs(service_id, area_id)" in sql and "area_name" in sql:
            return [{"service_id": "s1", "area_id": "a1", "service_name": "Laser", "area_name": "Axilas",
                     "duration_minutes": 15, "price_cents": 10000}]
        if "SELECT id FROM scheduler.appointments" in sql and "start_time <" in sql:
            return [{"id": "outro"}] if self.conflito else []
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
        if "SET status = %s" in sql:
            linha = dict(self.existente)
            linha["id"] = params[-1]
            linha["status"] = params[0]
            return linha
        if "rescheduled_to_id = %(novo)s" in sql:
            return None  # a janela do vincula_antecessor nao pegou nada
        return {"id": EXISTENTE}

    def sql_com(self, trecho):
        return [(s, p) for s, p in self.escritas if trecho in s]


def _servico(db):
    s = AppointmentService(db)
    s.lead_service = None
    return s


def _cria(db, **kw):
    with mock.patch.object(mod, "desfecho_do_agendamento", return_value=kw.pop("automatico", "CANCELLED")), \
         mock.patch.object(mod, "passa_a_marca_adiante"), \
         mock.patch.object(mod, "e_primeira_visita", return_value=False), \
         mock.patch.object(mod, "decide", return_value=mock.MagicMock(pct=0, razao=None)):
        return _servico(db).create_appointment(
            clinic_id=CLINIC, phone=FONE, service_id="s1", date="2026-11-28", time="10:00",
            service_area_pairs=[{"service_id": "s1", "area_id": "a1"}], full_name="Maria", **kw)


class TestConsulta(unittest.TestCase):
    def test_pergunta_pelo_mes_e_pelas_variantes_do_numero(self):
        db = Db()
        r = _servico(db).sessao_no_mesmo_mes(CLINIC, "(11) 99999-0001", "2026-11-28")
        self.assertEqual(r["id"], EXISTENTE)
        sql, params = db.consultas[0]
        self.assertIn("date_trunc('month'", sql)
        self.assertIn("appointment_date >=", sql)
        self.assertIn("LIMIT 1", sql)
        self.assertIn(FONE, params[2])
        self.assertEqual(params[3], "2026-11-28")

    def test_excluir_id_entra_na_consulta(self):
        db = Db()
        _servico(db).sessao_no_mesmo_mes(CLINIC, FONE, "2026-11-28", excluir_id=MOVIDO)
        sql, params = db.consultas[0]
        self.assertIn("a.id <> %s::uuid", sql)
        self.assertEqual(params[-1], MOVIDO)

    def test_duble_que_nao_devolve_lista_nao_e_conflito(self):
        db = mock.MagicMock()
        db.execute_query.return_value = mock.MagicMock()
        self.assertIsNone(_servico(db).sessao_no_mesmo_mes(CLINIC, FONE, "2026-11-28"))

    def test_sem_telefone_ou_data_nao_consulta(self):
        db = Db()
        self.assertIsNone(_servico(db).sessao_no_mesmo_mes(CLINIC, "", "2026-11-28"))
        self.assertIsNone(_servico(db).sessao_no_mesmo_mes(CLINIC, FONE, None))
        self.assertEqual(db.consultas, [])


class TestCriar(unittest.TestCase):
    def test_mes_ocupado_levanta_com_a_existente_e_nao_escreve(self):
        db = Db()
        with self.assertRaises(SessaoNoMesmoMes) as cm:
            _cria(db)
        self.assertEqual(cm.exception.existente["id"], EXISTENTE)
        self.assertEqual(cm.exception.existente["patient_name"], "Maria")
        self.assertEqual(db.escritas, [])

    def test_mes_livre_cria_normalmente(self):
        db = Db(no_mes=False)
        r = _cria(db)
        self.assertEqual(r["id"], NOVO)
        self.assertFalse(db.sql_com("SET status = %s"))

    def test_substituir_cancela_a_existente_e_vincula(self):
        db = Db()
        r = _cria(db, substituir_mesmo_mes=True, autor="site")
        # a existente saiu pelo desfecho da antecedencia
        sql, params = db.sql_com("SET status = %s")[0]
        self.assertEqual(params[0], "CANCELLED")
        self.assertEqual(params[-1], EXISTENTE)
        # o novo nasceu e aponta para ela, e ela para ele
        self.assertEqual(r["rescheduled_from_id"], EXISTENTE)
        self.assertTrue(db.sql_com("SET rescheduled_from_id = %s::uuid"))
        self.assertEqual(db.sql_com("SET rescheduled_to_id = %s::uuid, updated_at = NOW()")[0][1], (NOVO, EXISTENTE))
        # pagamento vivo e link dos documentos acompanham
        self.assertEqual(db.sql_com("UPDATE scheduler.appointment_payments")[0][1], (NOVO, EXISTENTE))
        self.assertTrue(db.sql_com("SET consent_link_sent_at = %s"))
        self.assertFalse(db.sql_com("second_in_month_by"))

    def test_substituir_nas_ultimas_24h_deixa_a_existente_em_falta(self):
        db = Db()
        _cria(db, substituir_mesmo_mes=True, automatico="NO_SHOW")
        self.assertEqual(db.sql_com("SET status = %s")[0][1][0], "NO_SHOW")

    def test_conflito_de_horario_nao_cancela_a_existente(self):
        db = Db(conflito=True)
        with self.assertRaises(ConflictError):
            _cria(db, substituir_mesmo_mes=True)
        self.assertEqual(db.escritas, [], "um conflito nao pode deixar a paciente sem sessao")

    def test_permitir_duas_mantem_a_existente_e_grava_quem_e_por_que(self):
        db = Db()
        r = _cria(db, permitir_duas=True, autor="Dra. Clara", motivo_das_duas="  duas áreas em dias separados ")
        self.assertEqual(r["id"], NOVO)
        self.assertFalse(db.sql_com("SET status = %s"))
        sql, params = db.sql_com("second_in_month_by")[0]
        self.assertEqual(params, ("Dra. Clara", "duas áreas em dias separados", NOVO))

    def test_permitir_duas_sem_conflito_nao_grava_nada(self):
        db = Db(no_mes=False)
        _cria(db, permitir_duas=True, autor="Dra. Clara", motivo_das_duas="x")
        self.assertFalse(db.sql_com("second_in_month_by"))

    def test_substituir_e_permitir_juntos_mantem_as_duas(self):
        db = Db()
        _cria(db, substituir_mesmo_mes=True, permitir_duas=True, autor="a", motivo_das_duas="m")
        self.assertFalse(db.sql_com("SET status = %s"))


class TestRemarca(unittest.TestCase):
    def _remarca(self, db, **kw):
        with mock.patch.object(mod, "desfecho_do_agendamento", return_value="CANCELLED"), \
             mock.patch.object(mod, "passa_a_marca_adiante"), \
             mock.patch.object(mod, "e_primeira_visita", return_value=False):
            return _servico(db).remarca(MOVIDO, "2026-11-28", "10:00", **kw)

    def test_mes_de_destino_com_outra_sessao_levanta_antes_de_escrever(self):
        db = Db()
        with self.assertRaises(SessaoNoMesmoMes) as cm:
            self._remarca(db)
        self.assertEqual(cm.exception.existente["id"], EXISTENTE)
        self.assertEqual(db.escritas, [])
        sql, params = next(c for c in db.consultas if "date_trunc" in c[0])
        self.assertEqual(params[-1], MOVIDO, "o proprio agendamento nao conta")

    def test_substituir_cancela_a_outra_e_depois_o_antigo(self):
        db = Db()
        r = self._remarca(db, substituir_mesmo_mes=True, autor="Ana")
        cancelados = [p[-1] for s, p in db.sql_com("SET status = %s")]
        self.assertEqual(cancelados, [EXISTENTE, MOVIDO])
        self.assertEqual(r["novo"]["id"], NOVO)

    def test_permitir_duas_nao_consulta_o_mes(self):
        db = Db()
        self._remarca(db, permitir_duas=True, autor="Dra. Clara", motivo_das_duas="m")
        self.assertFalse([c for c in db.consultas if "date_trunc" in c[0] and c[1][-1] == MOVIDO])
        self.assertEqual([p[-1] for s, p in db.sql_com("SET status = %s")], [MOVIDO])

    def test_mes_livre_remarca_como_sempre(self):
        db = Db(no_mes=False)
        r = self._remarca(db)
        self.assertEqual([p[-1] for s, p in db.sql_com("SET status = %s")], [MOVIDO])
        self.assertEqual(r["antigo"]["rescheduled_to_id"], NOVO)


if __name__ == "__main__":
    unittest.main()
