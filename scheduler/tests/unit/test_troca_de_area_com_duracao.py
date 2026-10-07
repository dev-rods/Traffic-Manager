# -*- coding: utf-8 -*-
"""Trocar a área e fixar a duração no mesmo pedido.

Caso real de 20/09/2026. A Larissa Darcie tinha 12:30-12:40 (10 minutos) com a
área "Virilha Completa", e a paciente seguinte começa 12:40 em ponto. O André
trocou a área para "Virilha Completa + ânus" e fixou 10 minutos — e recebeu
conflito de horário.

    área antiga "Virilha Completa"        -> 10 min -> termina 12:40  (cabe)
    área nova   "Virilha Completa + ânus" -> 15 min -> termina 12:45  (colide)

A troca de área recalculava os 15 minutos, conferia o conflito com ESSE número e
recusava — antes de a duração que ele digitou sequer ser lida. A etapa que
aplicava a duração manual vinha depois, e nunca era alcançada.

Era o mesmo defeito que eu já tinha corrigido no `reschedule` e no
`available-slots`: uma decisão tomada com um número que o pedido já substituiu.
Três vezes o mesmo erro, em três lugares.

O que NÃO muda: trocar a área continua descartando um override ANTERIOR, como o
André decidiu em 17/09. Aquele valor foi escolhido para outras áreas. Um valor
mandado no mesmo pedido não é override anterior — é a decisão de agora.
"""
import unittest

from src.services.appointment_service import (
    SEM_MUDANCA,
    AppointmentService,
    ConflictError,
)

APPT = "11111111-1111-1111-1111-111111111111"
SERVICO = "22222222-2222-2222-2222-222222222222"
PARES = [{"serviceId": "s1", "areaId": "a1"}]

REGRA = {"floor_minutes": 10, "ceiling_minutes": 50, "step_minutes": 5,
         "is_active": True}


class DbFalso:
    """A agenda da Larissa: 12:30, e a próxima paciente às 12:40."""

    def __init__(self, soma_das_areas=15, manual_atual=None, ha_conflito=True):
        self.agendamento = {
            "id": APPT, "clinic_id": "c", "service_id": SERVICO,
            "appointment_date": "2026-09-23", "start_time": "12:30:00",
            "end_time": "12:40:00", "status": "CONFIRMED", "version": 1,
            "total_duration_minutes": 10,
            "manual_duration_minutes": manual_atual,
            "discount_pct": 0,
        }
        self.soma = soma_das_areas
        self.ha_conflito = ha_conflito
        self.escritas = []

    def execute_query(self, sql, params=None):
        if "FROM scheduler.appointments" in sql and "SELECT id FROM" in sql:
            # O conflito depende do fim calculado: 12:45 colide, 12:40 não.
            fim = params[3] if params and len(params) > 3 else ""
            return [{"id": "luiza"}] if (self.ha_conflito and fim > "12:40") else []
        if "FROM scheduler.appointments" in sql:
            return [dict(self.agendamento)]
        if "duration_rules" in sql:
            return [dict(REGRA)]
        if "FROM scheduler.services" in sql:
            return [{"id": SERVICO, "duration_minutes": 15, "name": "Laser",
                     "price_cents": 19500}]
        if "AS total" in sql:
            return [{"total": self.soma}]
        if "total_price" in sql:
            return [{"total_price": 19500}]
        return []

    def execute_write(self, sql, params=None):
        self.escritas.append((sql, params))
        return 1

    def execute_write_returning(self, sql, params=None):
        self.escritas.append((sql, params))
        return dict(self.agendamento)

    def update_de(self, trecho):
        for sql, params in reversed(self.escritas):
            if "UPDATE" in sql and trecho in sql:
                return sql, params
        raise AssertionError(f"nenhum UPDATE com {trecho!r}")


def troca(db, **kw):
    return AppointmentService(db).update_appointment_services(
        APPT, SERVICO, PARES, **kw)


class TestOCasoDaLarissa(unittest.TestCase):
    def test_sem_duracao_no_pedido_o_conflito_e_real(self):
        """A área nova dá 15 minutos e a próxima paciente começa 12:40. Sem uma
        duração no pedido, recusar está CERTO."""
        with self.assertRaises(ConflictError):
            troca(DbFalso())

    def test_com_a_duracao_no_pedido_nao_ha_conflito(self):
        """É o que ele pediu: trocar a área e manter 10 minutos."""
        db = DbFalso()

        troca(db, manual_duration_minutes=10)

        sql, params = db.update_de("service_id")
        self.assertIn("12:40", params, "12:30 + 10min = 12:40, e cabe")
        self.assertIn(10, params, "a duração manual tinha de ser gravada")

    def test_e_a_duracao_manual_fica_registrada(self):
        db = DbFalso()

        troca(db, manual_duration_minutes=10)

        sql, params = db.update_de("service_id")
        self.assertIn("manual_duration_minutes", sql)
        self.assertIn(10, params)

    def test_a_duracao_do_pedido_vence_o_calculo_das_areas(self):
        """O protocolo das áreas novas dá 15; ela fixou 10. Vale 10."""
        db = DbFalso(soma_das_areas=15)

        troca(db, manual_duration_minutes=10)

        _, params = db.update_de("service_id")
        self.assertNotIn(15, params)


class TestODescarteContinuaValendo(unittest.TestCase):
    """Decisão do André em 17/09: trocar a área descarta o override ANTERIOR."""

    def test_sem_duracao_no_pedido_o_override_antigo_e_zerado(self):
        db = DbFalso(soma_das_areas=10, manual_atual=75)

        r = troca(db)

        _, params = db.update_de("service_id")
        self.assertIn(None, params, "o override antigo tinha de ser zerado")
        self.assertTrue(r["manual_duration_descartada"])

    def test_com_duracao_no_pedido_NAO_e_descarte(self):
        """O valor não foi perdido, foi substituído. Avisar "descartada" na tela
        seria mentira, e a atendente iria procurar o que não sumiu."""
        db = DbFalso(soma_das_areas=10, manual_atual=75)

        r = troca(db, manual_duration_minutes=10)

        self.assertFalse(r["manual_duration_descartada"])

    def test_mandar_null_limpa_o_override(self):
        """`None` é "volte ao cálculo"; SEM_MUDANCA é "o pedido não falou
        disso". Sem separar os dois, toda troca de área pareceria um pedido de
        limpar."""
        db = DbFalso(soma_das_areas=10, manual_atual=75)

        troca(db, manual_duration_minutes=None)

        _, params = db.update_de("service_id")
        self.assertIn(None, params)


class TestOConflitoPodeSerAdiado(unittest.TestCase):
    """Quando um reschedule vem a seguir, a data aqui ainda é a antiga."""

    def test_sem_verificar_conflito_a_troca_passa(self):
        db = DbFalso()

        troca(db, verificar_conflito=False)

        _, params = db.update_de("service_id")
        self.assertIn("12:45", params, "gravou o fim novo sem recusar")

    def test_e_com_verificacao_ligada_recusa(self):
        with self.assertRaises(ConflictError):
            troca(DbFalso(), verificar_conflito=True)


class TestSemMudancaNaoEONone(unittest.TestCase):
    def test_sao_coisas_diferentes(self):
        self.assertIsNot(SEM_MUDANCA, None)
        self.assertNotEqual(SEM_MUDANCA, None)

    def test_o_padrao_e_nao_mexer(self):
        import inspect

        padrao = inspect.signature(
            AppointmentService.update_appointment_services
        ).parameters["manual_duration_minutes"].default

        self.assertIs(padrao, SEM_MUDANCA)


if __name__ == "__main__":
    unittest.main()
