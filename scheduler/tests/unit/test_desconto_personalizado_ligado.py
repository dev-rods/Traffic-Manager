# -*- coding: utf-8 -*-
"""O combinado chega aos DOIS caminhos que criam agendamento.

O bot calcula o desconto pela tool; o painel manda o que a atendente escolheu.
Se o campo so valesse num deles, a mesma paciente teria precos diferentes
conforme quem marcou - e ninguem descobriria olhando o codigo de um lado so.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor
from src.services.appointment_service import AppointmentService

CLINIC = "clinicaessenciaestetica-9668a4"
FONE = "5511970522647"
PARES = [{"service_id": "s1", "area_id": "a1"}]
AREAS = [{"id": "a1", "name": "Axilas"}]
CONVERSA = {"clinic_id": CLINIC, "phone": FONE,
            "turnos": [{"role": "user", "content": "quero axilas"}]}


def executor(personalizado, primeira=False):
    ex = object.__new__(ToolExecutor)
    ex.db = mock.MagicMock()
    ex.appointment_service = mock.MagicMock()
    ex.availability_engine = mock.MagicMock()

    def consulta(sql, params=None):
        if "FROM scheduler.areas" in sql:
            return AREAS
        if "custom_discount_pct" in sql:
            return [{"custom_discount_pct": personalizado}]
        if "service_areas sa" in sql and "price_cents" in sql:
            return [{"price_cents": 20000}]
        if "discount_rules" in sql:
            return [{"first_session_discount_pct": 50, "tier_2_min_areas": 2,
                     "tier_2_max_areas": 3, "tier_2_discount_pct": 10,
                     "tier_3_min_areas": 4, "tier_3_discount_pct": 20}]
        return []

    ex.db.execute_query.side_effect = consulta
    return ex


class TestNaToolDoBot(unittest.TestCase):
    def test_o_combinado_vence_a_politica(self):
        """A politica daria 50% de primeira sessao; o combinado e 30%."""
        with mock.patch("src.services.ai_tools.e_primeira_visita", return_value=True):
            r = executor(30).execute("calculate_discount",
                                     {"service_area_pairs": PARES}, dict(CONVERSA))

        self.assertEqual(r["discount_pct"], 30)
        self.assertEqual(r["discount_reason"], "personalizado")
        self.assertEqual(r["discounted_price_cents"], 14000)

    def test_combinado_de_zero_zera_o_desconto(self):
        """Nao e ausencia: e a clinica dizendo que esta paciente nao tem desconto."""
        with mock.patch("src.services.ai_tools.e_primeira_visita", return_value=True):
            r = executor(0).execute("calculate_discount",
                                    {"service_area_pairs": PARES}, dict(CONVERSA))

        self.assertEqual(r["discount_pct"], 0)
        self.assertEqual(r["discount_reason"], "personalizado")

    def test_sem_combinado_vale_a_politica(self):
        with mock.patch("src.services.ai_tools.e_primeira_visita", return_value=True):
            r = executor(None).execute("calculate_discount",
                                       {"service_area_pairs": PARES}, dict(CONVERSA))

        self.assertEqual(r["discount_pct"], 50)
        self.assertEqual(r["discount_reason"], "first_session")

    def test_a_resposta_traz_os_campos_que_o_bot_le(self):
        """Sao dois caminhos ate a resposta; faltando campo, o bot anuncia vazio."""
        with mock.patch("src.services.ai_tools.e_primeira_visita", return_value=False):
            r = executor(30).execute("calculate_discount",
                                     {"service_area_pairs": PARES}, dict(CONVERSA))

        for campo in ("original_price_display", "discounted_price_display",
                      "original_price_cents", "discounted_price_cents"):
            self.assertIn(campo, r)


class DbDoAgendamento:
    def __init__(self, personalizado):
        self.personalizado = personalizado
        self.gravado = {}

    def execute_query(self, sql, params=None):
        if "custom_discount_pct" in sql:
            return [{"custom_discount_pct": self.personalizado}]
        if "FROM scheduler.patients" in sql:
            return [{"id": "p1", "deleted_at": None, "name": "Maria"}]
        if "FROM scheduler.services" in sql:
            return [{"id": "s1", "duration_minutes": 20, "name": "Laser",
                     "price_cents": 20000}]
        if "duration_rules" in sql:
            return [{"floor_minutes": 10, "ceiling_minutes": 50,
                     "step_minutes": 5, "is_active": True}]
        if "AS total" in sql:
            return [{"total": 20}]
        if "total_price" in sql:
            return [{"total_price": 20000}]
        return []

    def execute_write(self, sql, params=None):
        return 1

    def execute_write_returning(self, sql, params=None):
        if "INSERT INTO scheduler.appointments" in sql:
            self.gravado = {"pct": params[8], "razao": params[9],
                            "original": params[10], "final": params[11]}
        return {"id": "ap1"}


def cria(personalizado, **kw):
    db = DbDoAgendamento(personalizado)
    AppointmentService(db).create_appointment(
        clinic_id=CLINIC, phone=FONE, service_id="s1",
        date="2026-09-23", time="14:00", service_area_pairs=list(PARES), **kw)
    return db.gravado


class TestNaCriacaoPeloPainel(unittest.TestCase):
    def test_sem_escolha_da_atendente_o_combinado_vale(self):
        g = cria(30)

        self.assertEqual(g["pct"], 30)
        self.assertEqual(g["razao"], "personalizado")

    def test_o_preco_gravado_acompanha_o_desconto(self):
        """O desconto entra ANTES do calculo de preco - senao o valor gravado
        diverge do desconto gravado, e o relatorio mente."""
        g = cria(30)

        self.assertEqual(g["original"], 20000)
        self.assertEqual(g["final"], 14000)

    def test_escolha_explicita_da_atendente_vence(self):
        """Decisao de agora vale mais que regra permanente."""
        g = cria(30, discount_pct=100, discount_reason="partnership")

        self.assertEqual(g["pct"], 100)
        self.assertEqual(g["razao"], "partnership")

    def test_sem_combinado_nada_muda(self):
        g = cria(None)

        self.assertEqual(g["pct"], 0)
        self.assertIsNone(g["razao"])


if __name__ == "__main__":
    unittest.main()
