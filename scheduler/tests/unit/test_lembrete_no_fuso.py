# -*- coding: utf-8 -*-
"""O lembrete de 24h sai na hora certa, não sai para sessão cancelada e não
sai de madrugada.

Código LATENTE: o lembrete nunca foi ligado em produção (06/10/2026 - tabela
vazia, `completo()` sem `reminder_service`, nenhum template REMINDER_24H).
Estes testes fixam o comportamento para o dia em que alguém ligar. Os três
defeitos que eles fecham:

  1. `sendAt` era hora LOCAL gravada com sufixo Z e comparada com utcnow:
     sessão às 07:15 em Brasília virava lembrete às 04:15.
  2. O processador não conferia se a sessão ainda existia.
  3. O processador não conhecia a janela de silêncio (PRD 020 §3.5).
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


class TestSendAtNoFuso(unittest.TestCase):
    def test_sessao_as_7h15_em_brasilia_lembra_as_7h15_do_dia_anterior_em_brasilia(self):
        """07:15 BRT = 10:15 UTC. Antes saía 07:15Z, que é 04:15 BRT."""
        item = servico().schedule_reminder(sessao(), ESSENCIA)
        self.assertEqual(item["sendAt"], "2026-10-08T10:15:00Z")

    def test_sem_clinica_assume_brasilia(self):
        item = servico().schedule_reminder(sessao())
        self.assertEqual(item["sendAt"], "2026-10-08T10:15:00Z")

    def test_outro_fuso(self):
        manaus = {"timezone": "America/Manaus"}  # UTC-4
        item = servico().schedule_reminder(sessao(), manaus)
        self.assertEqual(item["sendAt"], "2026-10-08T11:15:00Z")

    def test_fuso_invalido_cai_no_padrao(self):
        item = servico().schedule_reminder(sessao(), {"timezone": "Marte/Olympus"})
        self.assertEqual(item["sendAt"], "2026-10-08T10:15:00Z")

    def test_aceita_os_tipos_que_o_banco_devolve(self):
        """psycopg devolve date e time, não string."""
        s = sessao()
        s["appointment_date"] = date(2026, 10, 9)
        s["start_time"] = time(7, 15)
        item = servico().schedule_reminder(s, ESSENCIA)
        self.assertEqual(item["sendAt"], "2026-10-08T10:15:00Z")

    def test_o_sk_e_o_indice_usam_o_mesmo_instante(self):
        item = servico().schedule_reminder(sessao(), ESSENCIA)
        self.assertEqual(item["sk"], f"SEND_AT#{item['sendAt']}")


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


class TestProcessador(unittest.TestCase):
    """O cron: cancelado descarta, madrugada adia, confirmado em horário envia."""

    def _roda(self, status_da_sessao="CONFIRMED", agora_utc=None):
        from src.functions.reminder import processor as modulo

        lembrete = {"reminderId": "r1", "appointmentId": "ap1", "clinicId": "essencia",
                    "phoneNumber": "5511999990000", "patientName": "Yasmin",
                    "appointmentTime": "07:15", "pk": "REMINDER#r1", "sk": "SEND_AT#x"}
        reminder_service = mock.MagicMock()
        reminder_service.get_pending_reminders.return_value = [lembrete]
        db = mock.MagicMock()

        def query(sql, params=None):
            if "FROM scheduler.clinics" in sql:
                return [ESSENCIA]
            if "FROM scheduler.appointments" in sql:
                return [{"status": status_da_sessao}] if status_da_sessao else []
            return []

        db.execute_query.side_effect = query
        provider = mock.MagicMock()
        provider.send_text.return_value = mock.MagicMock(success=True, provider_message_id="z1", raw_response={})
        template = mock.MagicMock()
        template.get_and_render.return_value = "Lembrete: amanhã às 07:15"

        agora = agora_utc or datetime(2026, 10, 8, 10, 15, tzinfo=timezone.utc)  # 07:15 BRT

        class RelogioFalso(datetime):
            @classmethod
            def now(cls, tz=None):
                return agora if tz else agora.replace(tzinfo=None)

            @classmethod
            def utcnow(cls):
                return agora.replace(tzinfo=None)

        with mock.patch.object(modulo, "ReminderService", return_value=reminder_service), \
             mock.patch.object(modulo, "PostgresService", return_value=db), \
             mock.patch.object(modulo, "TemplateService", return_value=template), \
             mock.patch.object(modulo, "MessageTracker"), \
             mock.patch.object(modulo, "get_provider", return_value=provider), \
             mock.patch.object(modulo, "datetime", RelogioFalso):
            resultado = modulo.handler({}, None)
        return resultado, reminder_service, provider

    def test_confirmado_em_horario_envia(self):
        resultado, svc, provider = self._roda()
        provider.send_text.assert_called_once()
        svc.mark_sent.assert_called_once()
        self.assertEqual(resultado["sent"], 1)

    def test_cancelado_nao_envia(self):
        resultado, svc, provider = self._roda(status_da_sessao="CANCELLED")
        provider.send_text.assert_not_called()
        svc.mark_failed.assert_called_once()
        self.assertEqual(svc.mark_failed.call_args[0][3], "agendamento_nao_confirmado")

    def test_sessao_apagada_nao_envia(self):
        _, svc, provider = self._roda(status_da_sessao=None)
        provider.send_text.assert_not_called()
        svc.mark_failed.assert_called_once()

    def test_madrugada_adia_para_as_4h59_e_nao_falha(self):
        agora = SP.localize(datetime(2026, 10, 8, 1, 0)).astimezone(timezone.utc)
        resultado, svc, provider = self._roda(agora_utc=agora)

        provider.send_text.assert_not_called()
        svc.mark_failed.assert_not_called()
        svc.adia.assert_called_once()
        novo = svc.adia.call_args[0][2]
        self.assertEqual(novo, "2026-10-08T07:59:00Z")  # 04:59 BRT
        self.assertEqual(resultado["skipped"], 1)

    def test_o_adiamento_vem_depois_da_conferencia_de_status(self):
        """Cancelado de madrugada é descartado, não adiado para ser descartado às 5h."""
        agora = SP.localize(datetime(2026, 10, 8, 1, 0)).astimezone(timezone.utc)
        _, svc, _ = self._roda(status_da_sessao="CANCELLED", agora_utc=agora)
        svc.adia.assert_not_called()
        svc.mark_failed.assert_called_once()


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
