# -*- coding: utf-8 -*-
"""A porta de atendimento está na frente de TODO caminho que fala.

`atendimento.py` responde as duas perguntas; aqui o que se prova é que cada
chamador faz a pergunta certa (PRD 020 §3.5):

  reativo    webhook                          pode_responder
  proativo   fila de abordagem, /send com campanha,
             retomada pelo painel, lembrete   pode_iniciar

E que o que muda de fato acontece: cliente não renova, clínica renova, o
cooldown barra quem inicia e não barra quem responde.
"""
import json
import os
import unittest
from datetime import datetime, timezone
from unittest import mock

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")
os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "test-reminders")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-queue")

from src.services import atendimento as at

SP = pytz.timezone("America/Sao_Paulo")
H = 3600
# 11:00 em Brasília, fora da janela de silêncio.
AGORA_UTC = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)
AGORA = int(AGORA_UTC.timestamp())
MADRUGADA_UTC = SP.localize(datetime(2026, 9, 5, 1, 0)).astimezone(timezone.utc)


def em_cooldown():
    """Atendimento humano que venceu há uma hora."""
    return at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 25 * H)


def com_pessoa():
    return at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - H)


# ── Fila de abordagem ─────────────────────────────────────────────────────

class TestFilaDeAbordagem(unittest.TestCase):
    def _roda(self, sessao, agora_utc=AGORA_UTC, expires_at=None):
        from tests.unit.test_abordagem_com_retry import CLINICA, FilaFalsa, item
        import src.functions.outbound.processor as proc

        fila = FilaFalsa()
        fila._pendentes = [item(expiresAt=expires_at) if expires_at else item()]
        db = mock.MagicMock()
        db.execute_query.return_value = [dict(CLINICA)]

        with mock.patch.object(proc, "OutboundQueueService", return_value=fila), \
             mock.patch.object(proc, "MessageTracker"), \
             mock.patch.object(proc, "PostgresService", return_value=db), \
             mock.patch.object(proc, "get_provider"), \
             mock.patch.object(proc, "_sessions_table"), \
             mock.patch.object(proc, "_load_session", return_value=dict(sessao)), \
             mock.patch.object(proc, "mark_conversation_eligible"), \
             mock.patch.object(proc, "_ja_esta_conversando", return_value=False), \
             mock.patch.object(proc, "falar", return_value=(True, 1)) as falar, \
             mock.patch.object(proc, "datetime") as dt:
            dt.now.return_value = agora_utc
            proc.handler({}, None)
        return fila.acoes, falar

    def test_sem_nada_na_sessao_envia(self):
        acoes, falar = self._roda({})
        falar.assert_called_once()

    def test_em_cooldown_adia(self):
        """Depois de um atendimento humano o bot responde, mas não aborda."""
        acoes, falar = self._roda(em_cooldown())
        falar.assert_not_called()
        self.assertIn(("adia", "politica_nao_permite"), acoes)

    def test_com_pessoa_adia(self):
        acoes, falar = self._roda(com_pessoa())
        falar.assert_not_called()

    def test_de_madrugada_adia(self):
        acoes, falar = self._roda({}, agora_utc=MADRUGADA_UTC,
                                  expires_at="2026-09-06T12:00:00Z")
        falar.assert_not_called()
        self.assertIn(("adia", "politica_nao_permite"), acoes)


# ── /send com campanha ────────────────────────────────────────────────────

class TestSendComCampanha(unittest.TestCase):
    def _dispara(self, corpo, sessao, agora=AGORA):
        from src.functions.send import handler as modulo

        envio = mock.MagicMock(success=True, provider_message_id="p1", raw_response={})
        provider = mock.MagicMock()
        provider.send_text.return_value = envio
        db = mock.MagicMock()
        db.execute_query.return_value = [{"clinic_id": "c1", "name": "X", "use_agent": True}]
        evento = {"headers": {"x-api-key": "k"}, "body": json.dumps(corpo)}

        with mock.patch.object(modulo, "require_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "PostgresService", return_value=db), \
             mock.patch.object(modulo, "get_provider", return_value=provider), \
             mock.patch.object(modulo, "MessageTracker"), \
             mock.patch.object(modulo, "_tabela_de_sessoes"), \
             mock.patch.object(modulo, "_sessao", return_value=dict(sessao)), \
             mock.patch.object(modulo, "_agora", return_value=agora), \
             mock.patch.object(modulo, "abre_campanha", return_value=True):
            resposta = modulo.handler(evento, None)
        return resposta, provider

    BASE = {"clinicId": "c1", "phone": "5511999990000", "type": "text", "content": "oi"}

    def test_campanha_em_cooldown_e_409_com_motivo(self):
        resposta, provider = self._dispara({**self.BASE, "campanha": {"datas": ["2026-10-07"]}}, em_cooldown())
        self.assertEqual(resposta["statusCode"], 409)
        self.assertEqual(json.loads(resposta["body"])["motivo"], "cooldown")
        provider.send_text.assert_not_called()

    def test_campanha_com_pessoa_e_409(self):
        resposta, _ = self._dispara({**self.BASE, "campanha": {"datas": ["2026-10-07"]}}, com_pessoa())
        self.assertEqual(json.loads(resposta["body"])["motivo"], "atendimento_humano")

    def test_campanha_de_madrugada_e_409(self):
        resposta, _ = self._dispara({**self.BASE, "campanha": {"datas": ["2026-10-07"]}}, {},
                                    agora=int(MADRUGADA_UTC.timestamp()))
        self.assertEqual(json.loads(resposta["body"])["motivo"], "janela_de_silencio")

    def test_campanha_com_porta_aberta_envia(self):
        resposta, provider = self._dispara({**self.BASE, "campanha": {"datas": ["2026-10-07"]}}, {})
        self.assertEqual(resposta["statusCode"], 200)
        provider.send_text.assert_called_once()

    def test_mensagem_manual_nao_passa_pela_porta(self):
        """Sem campanha é a atendente falando: cooldown, pessoa e madrugada
        não barram gente."""
        resposta, provider = self._dispara(self.BASE, com_pessoa(), agora=int(MADRUGADA_UTC.timestamp()))
        self.assertEqual(resposta["statusCode"], 200)
        provider.send_text.assert_called_once()


# ── Retomada pelo painel ──────────────────────────────────────────────────

class TestRetomadaPeloPainel(unittest.TestCase):
    def _retoma(self, sessao, clinic=None):
        from src.services import conversation_resume as modulo

        tracker = mock.MagicMock()
        tracker.get_conversation_messages.return_value = [
            {"direction": "INBOUND", "content": "tem horário?", "sk": "MSG#x"}]
        db = mock.MagicMock()
        db.execute_query.return_value = [clinic or {"clinic_id": "c1"}]

        with mock.patch("src.services.message_tracker.MessageTracker", return_value=tracker), \
             mock.patch("src.services.db.postgres.PostgresService", return_value=db), \
             mock.patch("src.providers.whatsapp_provider.get_provider"), \
             mock.patch("src.services.session_store.carrega_sessao", return_value=dict(sessao)), \
             mock.patch("src.services.agent_runner.falar", return_value=(True, 1)) as falar:
            falou = modulo.responder_se_ficou_em_aberto("c1", "5511999990000")
        return falou, falar

    def test_porta_aberta_responde(self):
        falou, falar = self._retoma({})
        self.assertTrue(falou)
        falar.assert_called_once()

    def test_bot_da_clinica_pausado_nao_responde(self):
        """Antes a retomada não conferia `bot_paused` nem política."""
        falou, falar = self._retoma({}, clinic={"clinic_id": "c1", "bot_paused": True})
        self.assertFalse(falou)
        falar.assert_not_called()

    def test_com_pessoa_nao_responde(self):
        # A retomada usa o relogio real: a pessoa tem de estar na conversa AGORA.
        falou, falar = self._retoma(at.entrega_a_humano({}, por=at.POR_ATENDENTE))
        self.assertFalse(falou)
        falar.assert_not_called()


# ── Lembrete (código latente) ────────────────────────────────────────────

class TestLembrete(unittest.TestCase):
    def _roda(self, sessao):
        from src.functions.reminder import processor as modulo

        lembrete = {"reminderId": "r1", "appointmentId": "ap1", "clinicId": "c1",
                    "phoneNumber": "5511999990000", "patientName": "Y",
                    "appointmentTime": "07:15", "pk": "REMINDER#r1", "sk": "SEND_AT#x"}
        svc = mock.MagicMock()
        svc.get_pending_reminders.return_value = [lembrete]
        db = mock.MagicMock()
        db.execute_query.side_effect = lambda sql, params=None: (
            [{"clinic_id": "c1", "timezone": "America/Sao_Paulo"}] if "clinics" in sql
            else [{"status": "CONFIRMED"}])
        provider = mock.MagicMock()
        provider.send_text.return_value = mock.MagicMock(success=True, provider_message_id="z", raw_response={})

        class Relogio(datetime):
            @classmethod
            def now(cls, tz=None):
                return AGORA_UTC if tz else AGORA_UTC.replace(tzinfo=None)

            @classmethod
            def utcnow(cls):
                return AGORA_UTC.replace(tzinfo=None)

        with mock.patch.object(modulo, "ReminderService", return_value=svc), \
             mock.patch.object(modulo, "PostgresService", return_value=db), \
             mock.patch.object(modulo, "TemplateService"), \
             mock.patch.object(modulo, "MessageTracker"), \
             mock.patch.object(modulo, "get_provider", return_value=provider), \
             mock.patch.object(modulo, "carrega_sessao", return_value=dict(sessao)), \
             mock.patch.object(modulo, "datetime", Relogio):
            modulo.handler({}, None)
        return svc, provider

    def test_em_cooldown_ENVIA(self):
        """Transacional: a sessão existe e a pessoa precisa saber."""
        svc, provider = self._roda(em_cooldown())
        provider.send_text.assert_called_once()

    def test_com_pessoa_adia(self):
        svc, provider = self._roda(com_pessoa())
        provider.send_text.assert_not_called()
        svc.adia.assert_called_once()
        self.assertEqual(svc.adia.call_args[0][3], "porta_fechada")


# ── Webhook: quem renova, quem não ───────────────────────────────────────

class TestWebhookRenovacao(unittest.TestCase):
    def test_mensagem_da_clinica_renova_o_prazo(self):
        from src.functions.webhook import handler as wh

        sessao = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 20 * H)
        gravadas = []
        with mock.patch.object(wh, "_get_sessions_table"), \
             mock.patch.object(wh, "_load_session", return_value=sessao), \
             mock.patch.object(wh, "grava_atendimento", side_effect=lambda t, c, p, s, **k: gravadas.append(dict(s))), \
             mock.patch("src.services.atendimento.time") as relogio:
            relogio.time.return_value = AGORA
            wh._activate_attendant_mode("c1", "5511999990000")

        self.assertEqual(gravadas[0][at.CAMPO]["human_until"], AGORA + 24 * H)
        self.assertEqual(gravadas[0]["attendant_active_until"], AGORA + 24 * H)

    def test_o_webhook_pergunta_pode_responder_e_nao_pode_iniciar(self):
        """Quem escreveu está esperando: cooldown e madrugada não calam."""
        import inspect

        from src.functions.webhook import handler as wh

        fonte = inspect.getsource(wh.handler)
        self.assertIn("pode_responder(", fonte)
        self.assertNotIn("pode_iniciar(", fonte)


# ── Status para o painel ──────────────────────────────────────────────────

class TestStatusDaConversa(unittest.TestCase):
    def test_cooldown_aparece_como_bot(self):
        from src.services.status_da_conversa import BOT, status_de_uma_sessao
        self.assertEqual(status_de_uma_sessao(em_cooldown(), AGORA), BOT)

    def test_handoff_aparece_como_aguardando(self):
        from src.services.status_da_conversa import AGUARDA_HUMANO, status_de_uma_sessao
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="x", agora=AGORA - H)
        self.assertEqual(status_de_uma_sessao(s, AGORA), AGUARDA_HUMANO)

    def test_atendente_aparece_como_humano(self):
        from src.services.status_da_conversa import HUMANO, status_de_uma_sessao
        self.assertEqual(status_de_uma_sessao(com_pessoa(), AGORA), HUMANO)


if __name__ == "__main__":
    unittest.main()
