# -*- coding: utf-8 -*-
"""A duração manual sobrevive ao que o sistema faz com o agendamento.

No espírito de [test_trava_de_areas_ligada]: a regra pode estar perfeita e o
override sumir mesmo assim, porque quem o apaga é outro caminho de escrita.

Antes desta task o `reschedule_appointment` reaplicava `duracao_da_sessao` sobre
o valor gravado. Um override de 75 minutos, com teto 50, virava 50 na primeira
remarcação - e o `end_time` mudava sem a coluna mudar, então a agenda mostrava
uma coisa e o banco guardava outra. Nada quebrava.

O que se fixa aqui:
  - remarcar MANTÉM a duração manual
  - remarcar SEM override continua normalizando pela regra
  - `end_time` e `total_duration_minutes` saem sempre coerentes
  - trocar as áreas DESCARTA o override e conta que descartou
  - soltar o override volta ao CÁLCULO, não ao último valor
  - a regra da clínica nunca é escrita
"""
import unittest

from src.services.appointment_service import (
    AppointmentService,
    ConflictError,
)

CLINIC = "clinicaessenciaestetica-9668a4"
APPT = "11111111-1111-1111-1111-111111111111"

# A regra da Essência. O teto de 50 é o que engolia o override de 75.
REGRA = {"floor_minutes": 10, "ceiling_minutes": 50, "step_minutes": 5,
         "is_active": True}


class DbFalso:
    """Guarda os UPDATEs em vez de escrever, e registra tudo que rodou.

    `escritas` é o que os testes inspecionam: cada item é (sql, params), e é
    nele que se confere que `duration_rules` nunca foi escrita.
    """

    def __init__(self, agendamento=None, soma_das_areas=30, conflito=False):
        self.agendamento = {
            "id": APPT,
            "clinic_id": CLINIC,
            "service_id": "22222222-2222-2222-2222-222222222222",
            "appointment_date": "2026-09-23",
            "start_time": "14:00:00",
            "end_time": "14:30:00",
            "status": "CONFIRMED",
            "version": 1,
            "total_duration_minutes": 30,
            "manual_duration_minutes": None,
            "discount_pct": 0,
        }
        self.agendamento.update(agendamento or {})
        self.soma = soma_das_areas
        self.conflito = conflito
        self.escritas = []

    def execute_query(self, sql, params=None):
        if "FROM scheduler.appointments" in sql and "SELECT id FROM" in sql:
            return [{"id": "outro"}] if self.conflito else []
        if "FROM scheduler.appointments" in sql:
            return [dict(self.agendamento)]
        if "duration_rules" in sql:
            return [dict(REGRA)]
        if "FROM scheduler.services" in sql:
            return [{"id": "s1", "duration_minutes": 20, "name": "Laser",
                     "price_cents": 20000}]
        if "appointment_service_areas" in sql and "service_id" in sql:
            return [{"service_id": "s1", "area_id": "a1"}]
        if "AS total" in sql:
            return [{"total": self.soma}]
        if "total_price" in sql:
            return [{"total_price": 20000}]
        return []

    def execute_write(self, sql, params=None):
        self.escritas.append((sql, params))
        return 1

    def execute_write_returning(self, sql, params=None):
        self.escritas.append((sql, params))
        return dict(self.agendamento)

    # ── leitura dos UPDATEs, por nome de coluna ──
    def update_em(self, trecho):
        """O último UPDATE que contém `trecho`, como (sql, params)."""
        for sql, params in reversed(self.escritas):
            if "UPDATE" in sql and trecho in sql:
                return sql, params
        raise AssertionError(f"nenhum UPDATE com {trecho!r} em {len(self.escritas)} escritas")

    def gravou_regra_da_clinica(self):
        return any(
            "duration_rules" in sql and ("UPDATE" in sql or "INSERT" in sql)
            for sql, _ in self.escritas
        )


def servico(db):
    return AppointmentService(db)


class TestRemarcarMantemOOverride(unittest.TestCase):
    def test_o_override_nao_e_engolido_pelo_teto(self):
        """O caso exato: 75 minutos, teto 50. Antes virava 50."""
        db = DbFalso({"manual_duration_minutes": 75, "total_duration_minutes": 75})

        servico(db).reschedule_appointment(APPT, "2026-09-29", "09:00")

        _, params = db.update_em("appointment_date")
        self.assertIn(75, params, "a duracao manual foi perdida ao remarcar")
        self.assertIn("09:00", params)

    def test_o_fim_da_sessao_reflete_a_duracao_manual(self):
        db = DbFalso({"manual_duration_minutes": 75, "total_duration_minutes": 75})

        servico(db).reschedule_appointment(APPT, "2026-09-29", "09:00")

        _, params = db.update_em("appointment_date")
        self.assertIn("10:15", params, "09:00 + 75min = 10:15")

    def test_a_coluna_e_o_end_time_concordam(self):
        """A divergência que já existia antes do override: o reschedule mudava
        o end_time e deixava total_duration_minutes com o valor velho."""
        db = DbFalso({"manual_duration_minutes": 75, "total_duration_minutes": 75})

        servico(db).reschedule_appointment(APPT, "2026-09-29", "09:00")

        sql, params = db.update_em("appointment_date")
        self.assertIn("total_duration_minutes", sql)
        self.assertIn(75, params)


class TestRemarcarSemOverrideNaoMuda(unittest.TestCase):
    def test_a_normalizacao_pela_regra_continua(self):
        """A correção não pode desligar a normalização de agendamento antigo:
        é para isso que aquela linha existe."""
        db = DbFalso({"manual_duration_minutes": None,
                      "total_duration_minutes": 200})

        servico(db).reschedule_appointment(APPT, "2026-09-29", "09:00")

        _, params = db.update_em("appointment_date")
        self.assertIn(50, params, "sem override, o teto de 50 tem de valer")
        self.assertNotIn(200, params)

    def test_e_a_coluna_passa_a_ser_gravada_tambem(self):
        db = DbFalso({"manual_duration_minutes": None,
                      "total_duration_minutes": 200})

        servico(db).reschedule_appointment(APPT, "2026-09-29", "09:00")

        sql, _ = db.update_em("appointment_date")
        self.assertIn("total_duration_minutes", sql)


class TestTrocarAreasDescartaOOverride(unittest.TestCase):
    def test_a_coluna_e_zerada(self):
        db = DbFalso({"manual_duration_minutes": 75})

        servico(db).update_appointment_services(
            APPT, "22222222-2222-2222-2222-222222222222",
            [{"serviceId": "s1", "areaId": "a1"}],
        )

        sql, _ = db.update_em("service_id")
        self.assertIn("manual_duration_minutes = NULL", sql)

    def test_e_quem_chamou_fica_sabendo(self):
        """Sem isto o valor some da tela e a atendente não entende por quê."""
        db = DbFalso({"manual_duration_minutes": 75})

        r = servico(db).update_appointment_services(
            APPT, "22222222-2222-2222-2222-222222222222",
            [{"serviceId": "s1", "areaId": "a1"}],
        )

        self.assertTrue(r["manual_duration_descartada"])

    def test_sem_override_nao_ha_o_que_avisar(self):
        db = DbFalso({"manual_duration_minutes": None})

        r = servico(db).update_appointment_services(
            APPT, "22222222-2222-2222-2222-222222222222",
            [{"serviceId": "s1", "areaId": "a1"}],
        )

        self.assertFalse(r["manual_duration_descartada"])


class TestFixarESoltar(unittest.TestCase):
    def test_fixar_grava_a_duracao_e_o_fim(self):
        db = DbFalso()

        servico(db).set_manual_duration(APPT, 75)

        sql, params = db.update_em("manual_duration_minutes = %s")
        self.assertIn(75, params)
        self.assertIn("15:15", params, "14:00 + 75min = 15:15")

    def test_soltar_volta_ao_calculo_das_areas(self):
        """Não ao último valor gravado: 'voltar ao cálculo' tem de recalcular,
        senão soltar só congela o override com outro nome."""
        db = DbFalso({"manual_duration_minutes": 75, "total_duration_minutes": 75},
                     soma_das_areas=30)

        servico(db).set_manual_duration(APPT, None)

        sql, params = db.update_em("manual_duration_minutes = %s")
        self.assertIn(None, params, "a coluna precisa voltar a NULL")
        self.assertIn(30, params, "30 e a soma das areas, nao os 75 gravados")

    def test_o_manual_ignora_o_teto_da_clinica(self):
        db = DbFalso()

        servico(db).set_manual_duration(APPT, 75)

        _, params = db.update_em("manual_duration_minutes = %s")
        self.assertIn(75, params)
        self.assertNotIn(50, params)

    def test_duracao_longa_que_invade_a_proxima_paciente_e_recusada(self):
        db = DbFalso(conflito=True)

        with self.assertRaises(ConflictError):
            servico(db).set_manual_duration(APPT, 240)

    def test_sem_verificar_conflito_nao_confere(self):
        """Quando o mesmo request também remarca, a checagem aqui rodaria contra
        a data ANTIGA - e acusaria conflito numa data que ninguém vai ocupar."""
        db = DbFalso(conflito=True)

        servico(db).set_manual_duration(APPT, 240, verificar_conflito=False)

        _, params = db.update_em("manual_duration_minutes = %s")
        self.assertIn(240, params)


class TestARegraDaClinicaNaoEToacada(unittest.TestCase):
    """O pedido do André, em uma frase: mudar a duração de UM agendamento não
    pode mexer na regra do banco."""

    def test_fixar_nao_escreve_duration_rules(self):
        db = DbFalso()
        servico(db).set_manual_duration(APPT, 75)
        self.assertFalse(db.gravou_regra_da_clinica())

    def test_soltar_nao_escreve_duration_rules(self):
        db = DbFalso({"manual_duration_minutes": 75})
        servico(db).set_manual_duration(APPT, None)
        self.assertFalse(db.gravou_regra_da_clinica())

    def test_remarcar_com_override_nao_escreve_duration_rules(self):
        db = DbFalso({"manual_duration_minutes": 75})
        servico(db).reschedule_appointment(APPT, "2026-09-29", "09:00")
        self.assertFalse(db.gravou_regra_da_clinica())

    def test_trocar_areas_nao_escreve_duration_rules(self):
        db = DbFalso({"manual_duration_minutes": 75})
        servico(db).update_appointment_services(
            APPT, "22222222-2222-2222-2222-222222222222",
            [{"serviceId": "s1", "areaId": "a1"}],
        )
        self.assertFalse(db.gravou_regra_da_clinica())


if __name__ == "__main__":
    unittest.main()
