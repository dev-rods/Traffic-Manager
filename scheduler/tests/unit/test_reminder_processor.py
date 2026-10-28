# -*- coding: utf-8 -*-
"""O processador entrega o lembrete, grava o rastro no agendamento e abre a
sobreposicao. Cancelado e pulado; bot pausado falha; silencio adia; humano e
cooldown destravam (como o disparo em lote)."""
import os
import unittest
from datetime import date, datetime, time, timezone
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")
os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "t")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "t")

from src.functions.reminder import processor as P
from src.services import atendimento

CLINIC = {"clinic_id": "c1", "name": "Essencia", "display_name": "Essência", "timezone": "America/Sao_Paulo",
          "bot_paused": False, "custom_domain": "agendar.x.com.br", "janela_de_silencio": None, "active": True}
REM = {"reminderId": "r1", "appointmentId": "a1", "clinicId": "c1", "phoneNumber": "5511999990001",
       "patientName": "Maria", "pk": "REMINDER#r1", "sk": "SEND_AT#x", "reminderType": "LEMBRETE_SESSAO"}
APPT = {"id": "a1", "clinic_id": "c1", "status": "CONFIRMED", "appointment_date": date(2026, 11, 6),
        "start_time": time(9, 0), "full_name": "Maria Silva", "patient_phone": "5511999990001", "areas": "Axilas"}
MEIO_DIA = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)  # 12:00 BRT
MADRUGADA = datetime(2026, 11, 6, 4, 0, tzinfo=timezone.utc)  # 01:00 BRT


def deps(appt=APPT, clinic=CLINIC, sessao=None, envio_ok=True):
    db = mock.MagicMock()
    db.execute_query.side_effect = lambda sql, p=None: (
        [clinic] if "FROM scheduler.clinics" in sql else ([appt] if appt else []))
    template = mock.MagicMock(); template.get_and_render.return_value = "Oi Maria!"
    provider = mock.MagicMock()
    provider.send_text.return_value = mock.MagicMock(
        success=envio_ok, provider_message_id="pm", raw_response={}, error=None if envio_ok else "boom")
    return P.Deps(db=db, reminder_service=mock.MagicMock(), template_service=template,
                  tracker=mock.MagicMock(), provider=provider, tabela_sessoes=mock.MagicMock(),
                  abre_lembrete=mock.MagicMock(return_value=True),
                  grava_atendimento=mock.MagicMock(return_value=True),
                  carrega_sessao=lambda c, p: dict(sessao or {}))


def escritas(d):
    return [(" ".join(c.args[0].split()), c.args[1]) for c in d.db.execute_write.call_args_list]


class TestEntrega(unittest.TestCase):
    def test_sucesso_grava_enviado_e_abre_sobreposicao(self):
        d = deps()
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "enviado")
        sql, params = escritas(d)[-1]
        self.assertIn("lembrete_enviado_em = NOW()", sql)
        self.assertEqual(params[0], "ENVIADO")
        d.abre_lembrete.assert_called_once()
        aberto = d.abre_lembrete.call_args[0][3]
        self.assertEqual(aberto["appointment_id"], "a1")
        d.reminder_service.mark_sent.assert_called_once()
        d.grava_atendimento.assert_not_called()
        d.template_service.get_and_render.assert_called_once()
        self.assertEqual(d.template_service.get_and_render.call_args[0][1], "LEMBRETE_SESSAO")

    def test_cancelado_e_descartado_e_limpa_status(self):
        d = deps(appt=dict(APPT, status="CANCELLED"))
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "descartado")
        self.assertIn("lembrete_status = NULL", escritas(d)[0][0])
        d.provider.send_text.assert_not_called()
        d.reminder_service.mark_failed.assert_called_once()

    def test_sessao_apagada_e_descartado(self):
        d = deps(appt=None)
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "descartado")
        d.provider.send_text.assert_not_called()

    def test_bot_pausado_falha_com_motivo(self):
        d = deps(clinic=dict(CLINIC, bot_paused=True))
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "falhou")
        sql, params = escritas(d)[-1]
        self.assertEqual((params[0], params[1]), ("FALHOU", "bot pausado"))
        d.provider.send_text.assert_not_called()

    def test_silencio_adia_e_marca_adiado(self):
        d = deps()
        self.assertEqual(P.entrega(REM, d, MADRUGADA), "adiado")
        d.reminder_service.adia.assert_called_once()
        self.assertEqual(d.reminder_service.adia.call_args[0][2], "2026-11-06T07:59:00Z")  # 04:59 BRT
        self.assertEqual(escritas(d)[-1][1][0], "ADIADO")
        d.provider.send_text.assert_not_called()

    def test_cancelado_de_madrugada_e_descartado_nao_adiado(self):
        d = deps(appt=dict(APPT, status="CANCELLED"))
        self.assertEqual(P.entrega(REM, d, MADRUGADA), "descartado")
        d.reminder_service.adia.assert_not_called()

    def test_humano_destrava_e_envia(self):
        sessao = atendimento.entrega_a_humano({}, por=atendimento.POR_ATENDENTE, agora=int(MEIO_DIA.timestamp()) - 3600)
        d = deps(sessao=sessao)
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "enviado")
        d.grava_atendimento.assert_called_once()
        gravada = d.grava_atendimento.call_args[0][3]
        self.assertEqual(atendimento.estado(gravada, int(MEIO_DIA.timestamp())), atendimento.BOT_ACTIVE)

    def test_cooldown_destrava_e_envia(self):
        sessao = atendimento.entrega_a_humano({}, por=atendimento.POR_ATENDENTE, agora=int(MEIO_DIA.timestamp()) - 25 * 3600)
        d = deps(sessao=sessao)
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "enviado")
        d.grava_atendimento.assert_called_once()

    def test_falha_do_provider(self):
        d = deps(envio_ok=False)
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "falhou")
        d.reminder_service.mark_failed.assert_called_once()
        self.assertEqual(escritas(d)[-1][1][:2], ("FALHOU", "boom"))
        d.abre_lembrete.assert_not_called()


class TestHandler(unittest.TestCase):
    def test_conta_por_resultado_e_erro_vira_falhou(self):
        rs = mock.MagicMock()
        rs.get_pending_reminders.return_value = [dict(REM), dict(REM, reminderId="r2")]
        resultados = iter(["enviado", RuntimeError("boom")])

        def entrega(r, d, agora):
            x = next(resultados)
            if isinstance(x, Exception):
                raise x
            return x

        with mock.patch.object(P, "ReminderService", return_value=rs), \
             mock.patch.object(P, "PostgresService"), mock.patch.object(P, "TemplateService"), \
             mock.patch.object(P, "MessageTracker"), mock.patch.object(P, "get_provider"), \
             mock.patch("boto3.resource"), mock.patch.object(P, "entrega", side_effect=entrega):
            r = P.handler({}, None)
        self.assertEqual((r["processed"], r["enviado"], r["falhou"]), (2, 1, 1))
        rs.mark_failed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
