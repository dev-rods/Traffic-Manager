# -*- coding: utf-8 -*-
"""O lembrete grava o instante certo na fila, a janela de silêncio é lida no
fuso da clínica, e adiar mantém PENDING.

Até 27/10/2026 o serviço calculava "24h antes de cada sessão" e nunca foi
ligado em produção. O PRD 027 trocou isso por um lote por DIA: quem decide o
`send_at` é `lembrete_da_agenda`, e aqui só se grava - em UTC, porque é com o
relógio UTC que o processador compara. Os testes do processador novo estão em
`test_reminder_processor.py`.
"""
import os
import unittest
from datetime import date, datetime, time, timezone
from unittest import mock

import pytz

os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "test-reminders")
os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services.business_hours import em_silencio, fim_do_silencio, fuso
from src.services.reminder_service import ReminderService

SP = pytz.timezone("America/Sao_Paulo")
ESSENCIA = {"clinic_id": "essencia", "timezone": "America/Sao_Paulo", "name": "Essência"}


def servico():
    s = object.__new__(ReminderService)
    s.table = mock.MagicMock()
    return s


def sessao(data="2026-10-09", hora="07:15"):
    return {"id": "ap1", "clinic_id": "essencia", "appointment_date": data,
            "start_time": hora, "patient_phone": "5511999990000", "patient_name": "Yasmin"}


class TestAgendaLembrete(unittest.TestCase):
    def test_grava_o_send_at_do_lote_em_utc(self):
        """12:00 BRT = 15:00 UTC."""
        send_at = SP.localize(datetime(2026, 10, 8, 12, 0))
        item = servico().agenda_lembrete(sessao(), ESSENCIA, send_at)
        self.assertEqual(item["sendAt"], "2026-10-08T15:00:00Z")
        self.assertEqual(item["reminderType"], "LEMBRETE_SESSAO")
        self.assertEqual(item["status"], "PENDING")

    def test_o_sk_e_o_indice_usam_o_mesmo_instante(self):
        item = servico().agenda_lembrete(sessao(), ESSENCIA, datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(item["sk"], f"SEND_AT#{item['sendAt']}")

    def test_aceita_os_tipos_que_o_banco_devolve(self):
        s = sessao()
        s["appointment_date"] = date(2026, 10, 9)
        s["start_time"] = time(7, 15)
        s["full_name"] = "Yasmin Costa"
        item = servico().agenda_lembrete(s, ESSENCIA, datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc))
        self.assertEqual((item["appointmentDate"], item["appointmentTime"], item["patientName"]),
                         ("2026-10-09", "07:15:00", "Yasmin Costa"))

    def test_grava_na_tabela(self):
        s = servico()
        s.agenda_lembrete(sessao(), ESSENCIA, datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc))
        s.table.put_item.assert_called_once()


class TestAdiar(unittest.TestCase):
    def test_adiar_mantem_pending_e_move_o_send_at(self):
        s = servico()
        s.adia("REMINDER#1", "SEND_AT#x", "2026-10-09T07:59:00Z", "janela_de_silencio")

        kw = s.table.update_item.call_args[1]
        self.assertNotIn("status", kw["UpdateExpression"])
        self.assertEqual(kw["ExpressionAttributeValues"][":s"], "2026-10-09T07:59:00Z")
        self.assertEqual(kw["ExpressionAttributeValues"][":m"], "janela_de_silencio")

    def test_falha_no_banco_nao_levanta(self):
        s = servico()
        s.table.update_item.side_effect = RuntimeError("down")
        s.adia("p", "s", "2026-10-09T07:59:00Z", "x")


class TestJanelaDeSilencio(unittest.TestCase):
    """22:59 inclusivo, 04:59 exclusivo, no fuso da clínica."""

    def _brt(self, h, m, s=0, dia=6):
        return SP.localize(datetime(2026, 10, dia, h, m, s)).astimezone(timezone.utc)

    def test_os_quatro_limites(self):
        casos = [
            ((22, 58, 59), False),
            ((22, 59, 0), True),
            ((4, 58, 59), True),
            ((4, 59, 0), False),
            ((5, 0, 0), False),
            ((1, 30, 0), True),
            ((14, 0, 0), False),
        ]
        for (h, m, s), esperado in casos:
            with self.subTest(hora=f"{h:02}:{m:02}:{s:02}"):
                self.assertEqual(em_silencio(ESSENCIA, self._brt(h, m, s)), esperado)

    def test_le_o_fuso_da_clinica_e_nao_o_utc(self):
        """01:30 UTC é 22:30 em Brasília: fora da janela."""
        agora = datetime(2026, 10, 7, 1, 30, tzinfo=timezone.utc)
        self.assertFalse(em_silencio(ESSENCIA, agora))
        # 02:00 UTC é 23:00 em Brasília: dentro.
        self.assertTrue(em_silencio(ESSENCIA, datetime(2026, 10, 7, 2, 0, tzinfo=timezone.utc)))

    def test_fim_do_silencio_e_as_4h59_local(self):
        fim = fim_do_silencio(ESSENCIA, self._brt(23, 30))
        self.assertEqual(fim.astimezone(SP).strftime("%Y-%m-%d %H:%M"), "2026-10-07 04:59")

    def test_fim_do_silencio_de_madrugada_e_no_mesmo_dia(self):
        fim = fim_do_silencio(ESSENCIA, self._brt(1, 0, dia=7))
        self.assertEqual(fim.astimezone(SP).strftime("%Y-%m-%d %H:%M"), "2026-10-07 04:59")

    def test_fora_da_janela_devolve_agora(self):
        agora = self._brt(14, 0)
        self.assertEqual(fim_do_silencio(ESSENCIA, agora), agora)

    def test_janela_por_clinica(self):
        clinica = {**ESSENCIA, "janela_de_silencio": {"start": "21:00", "end": "08:00"}}
        self.assertTrue(em_silencio(clinica, self._brt(21, 0)))
        self.assertTrue(em_silencio(clinica, self._brt(7, 59)))
        self.assertFalse(em_silencio(clinica, self._brt(8, 0)))

    def test_janela_malformada_cai_no_padrao(self):
        clinica = {**ESSENCIA, "janela_de_silencio": {"start": "x"}}
        self.assertTrue(em_silencio(clinica, self._brt(23, 0)))
        self.assertFalse(em_silencio(clinica, self._brt(22, 0)))

    def test_fuso(self):
        self.assertEqual(fuso(ESSENCIA).zone, "America/Sao_Paulo")
        self.assertEqual(fuso({}).zone, "America/Sao_Paulo")
        self.assertEqual(fuso(None).zone, "America/Sao_Paulo")
        self.assertEqual(fuso({"timezone": "America/Manaus"}).zone, "America/Manaus")


class TestOServicoDeAgendamentoPassaOFuso(unittest.TestCase):
    def test_create_passa_a_clinica_ao_lembrete(self):
        from src.services.appointment_service import AppointmentService

        svc = object.__new__(AppointmentService)
        svc.db = mock.MagicMock()
        svc.db.execute_query.return_value = [{"timezone": "America/Manaus"}]
        svc.reminder_service = mock.MagicMock()

        self.assertEqual(svc._fuso_da_clinica("x"), {"timezone": "America/Manaus"})

    def test_falha_ao_ler_o_fuso_vira_vazio(self):
        from src.services.appointment_service import AppointmentService

        svc = object.__new__(AppointmentService)
        svc.db = mock.MagicMock()
        svc.db.execute_query.side_effect = RuntimeError("down")
        self.assertEqual(svc._fuso_da_clinica("x"), {})


if __name__ == "__main__":
    unittest.main()
