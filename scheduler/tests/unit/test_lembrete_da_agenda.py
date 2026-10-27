# -*- coding: utf-8 -*-
"""Um lembrete por agendamento confirmado do dia, nunca repetido; o lote sai
de uma vez, no fim do silencio se preciso."""
import unittest
from datetime import date, datetime, time, timezone
from unittest import mock

import pytz

from src.services import lembrete_da_agenda as LA

TZ = pytz.timezone("America/Sao_Paulo")
CLINIC = {"clinic_id": "c1", "timezone": "America/Sao_Paulo", "name": "Essencia", "display_name": "Essência",
          "janela_de_silencio": None}


def appt(i, **kw):
    base = {"id": f"a{i}", "clinic_id": "c1", "appointment_date": date(2026, 11, 6), "start_time": time(9 + i, 0),
            "status": "CONFIRMED", "patient_phone": f"551199999000{i}", "full_name": f"Pessoa {i}",
            "patient_name": None, "areas": "Axilas", "lembrete_enviado_em": None, "lembrete_status": None}
    base.update(kw)
    return base


class BancoFalso:
    def __init__(self, linhas):
        self.linhas = linhas
        self.escritas = []

    def execute_query(self, sql, params=None):
        return self.linhas

    def execute_write(self, sql, params=None):
        self.escritas.append((" ".join(sql.split()), params))
        return 1


class TestSeleciona(unittest.TestCase):
    def test_separa_enfileiraveis_lembrados_e_sem_telefone(self):
        db = BancoFalso([appt(1),
                         appt(2, lembrete_enviado_em=datetime.now(timezone.utc), lembrete_status="ENVIADO"),
                         appt(3, patient_phone=None),
                         appt(4, lembrete_status="ENFILEIRADO")])
        r = LA.seleciona(db, "c1", "2026-11-06")
        self.assertEqual([a["id"] for a in r["enfileiraveis"]], ["a1"])
        self.assertEqual((r["ja_lembrados"], r["sem_telefone"], r["enfileirados_antes"]), (1, 1, 1))

    def test_duas_sessoes_da_mesma_pessoa_sao_dois_lembretes(self):
        db = BancoFalso([appt(1), appt(2, patient_phone="5511999990001")])
        self.assertEqual(len(LA.seleciona(db, "c1", "2026-11-06")["enfileiraveis"]), 2)


class TestInicioESendAt(unittest.TestCase):
    def test_inicio_e_o_menor_horario(self):
        self.assertEqual(LA.inicio_da_agenda([appt(2), appt(1)]), time(10, 0))
        self.assertIsNone(LA.inicio_da_agenda([]))

    def test_fora_do_silencio_e_agora(self):
        agora = TZ.localize(datetime(2026, 11, 5, 10, 0))
        self.assertEqual(LA.send_at_do_lote(CLINIC, agora), agora)

    def test_dentro_do_silencio_vai_para_o_fim(self):
        agora = TZ.localize(datetime(2026, 11, 5, 23, 0))
        s = LA.send_at_do_lote(CLINIC, agora)
        self.assertGreater(s, agora)
        self.assertEqual(s.astimezone(TZ).date(), date(2026, 11, 6))


class TestEnfileira(unittest.TestCase):
    def test_simular_nao_escreve(self):
        db = BancoFalso([appt(1)]); rs = mock.MagicMock()
        r = LA.enfileira(db, rs, CLINIC, "2026-11-06", datetime.now(timezone.utc), simular=True)
        self.assertEqual(r["enfileirados"], 1)
        rs.agenda_lembrete.assert_not_called()
        self.assertEqual(db.escritas, [])

    def test_enfileira_e_marca(self):
        db = BancoFalso([appt(1), appt(2)]); rs = mock.MagicMock()
        send_at = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        r = LA.enfileira(db, rs, CLINIC, "2026-11-06", send_at)
        self.assertEqual(r["enfileirados"], 2)
        self.assertEqual(rs.agenda_lembrete.call_count, 2)
        self.assertTrue(all("lembrete_status = 'ENFILEIRADO'" in s for s, _ in db.escritas))
        self.assertEqual(r["send_at"], "2026-11-05T12:00:00Z")


class TestVariaveis(unittest.TestCase):
    def test_variaveis(self):
        v = LA.variaveis_do_template(appt(1, areas="Axilas, Virilha Completa, Buço"), CLINIC)
        self.assertEqual(v["nome"], "Pessoa")
        self.assertEqual(v["areas"], "Axilas, Virilha Completa e Buço")
        self.assertEqual(v["clinic_name"], "Essência")
        self.assertEqual(v["dia"], "sexta, 06/11")
        self.assertEqual(v["hora"], "10:00")

    def test_sem_nome_nem_area_tem_fallback(self):
        v = LA.variaveis_do_template(appt(1, full_name=None, areas=None, appointment_date="2026-11-06", start_time="09:30:00"), CLINIC)
        self.assertEqual((v["nome"], v["areas"], v["hora"]), ("tudo bem", "depilação a laser", "09:30"))


if __name__ == "__main__":
    unittest.main()
