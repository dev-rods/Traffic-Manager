# -*- coding: utf-8 -*-
"""As decisões do disparo: adiar, desistir por prazo, ou não falar nunca mais.

A abordagem ativa manda mensagem no WhatsApp de uma pessoa real e não tem
desfazer. Classificar errado tem os dois custos: tratar como terminal o que era
adiável perde a pessoa em silêncio, e tratar como adiável o que era terminal
manda mensagem para quem já está conversando com uma atendente.

Em 02/09/2026 três leads ficaram parados para sempre porque "política não
permite" marcava FAILED terminal - o piloto estava ligado no momento do disparo,
e desligá-lo depois não os trouxe de volta.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.functions.outbound import processor as proc
from src.services.outbound_queue import VALIDADE_HORAS

# 04/09/2026 e SEXTA. 14:00 UTC = 11:00 BRT, dentro do horario da clinica
# de teste. Usar sabado fazia todo teste cair em 'fora_do_horario'.
AGORA = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)
ISO = "%Y-%m-%dT%H:%M:%SZ"
PILOTO = "5511970522647"
CLINICA = {
    "clinic_id": "clinica-1",
    "bot_autoreply_policy": "PILOT",
    "bot_pilot_phones": [PILOTO],
    "bot_paused": False,
    # Formato real do business_hours: chave de 3 letras, `start`/`end`. Inventar
    # o formato fazia todo item cair em "fora_do_horario" e o teste de envio
    # nunca exercitava o caminho feliz.
    "business_hours": {"fri": {"start": "08:00", "end": "20:00"}},
}


def item(**over):
    d = {
        "pk": "CLINIC#clinica-1", "sk": "OUT#x", "messageId": "m1",
        "clinicId": "clinica-1", "phone": PILOTO, "leadId": "lead-1",
        "kind": "FIRST_CONTACT", "status": "PENDING",
        "createdAt": (AGORA - timedelta(minutes=20)).strftime(ISO),
        "expiresAt": (AGORA + timedelta(hours=1)).strftime(ISO),
        "sendAfter": (AGORA - timedelta(minutes=10)).strftime(ISO),
    }
    d.update(over)
    return d


class FilaFalsa:
    def __init__(self):
        self.acoes = []

    def pending_due(self, agora_iso, limit=50):
        return self._pendentes

    def adia(self, mid, pk, sk, motivo):
        self.acoes.append(("adia", motivo))

    def mark_expired(self, mid, pk, sk, motivo):
        self.acoes.append(("expira", motivo))

    def mark_failed(self, mid, pk, sk, motivo):
        self.acoes.append(("falha", motivo))

    def mark_sent(self, mid, pk, sk):
        self.acoes.append(("enviou", None))


def roda(itens, clinic=None, conversando=False, falar_ok=(True, 1)):
    fila = FilaFalsa()
    fila._pendentes = itens
    db = mock.MagicMock()
    db.execute_query.return_value = [dict(clinic or CLINICA)]

    with mock.patch.object(proc, "OutboundQueueService", return_value=fila), \
         mock.patch.object(proc, "MessageTracker"), \
         mock.patch.object(proc, "PostgresService", return_value=db), \
         mock.patch.object(proc, "get_provider"), \
         mock.patch.object(proc, "_sessions_table"), \
         mock.patch.object(proc, "mark_conversation_eligible"), \
         mock.patch.object(proc, "_ja_esta_conversando", return_value=conversando), \
         mock.patch.object(proc, "falar", return_value=falar_ok), \
         mock.patch.object(proc, "datetime") as dt:
        dt.now.return_value = AGORA
        proc.handler({}, None)
    return fila.acoes


class TestPrazo(unittest.TestCase):
    def test_vencido_desiste(self):
        acoes = roda([item(expiresAt=(AGORA - timedelta(minutes=1)).strftime(ISO))])

        self.assertEqual(acoes, [("expira", "prazo_vencido")])

    def test_dentro_do_prazo_segue(self):
        acoes = roda([item()])

        self.assertEqual(acoes[-1], ("enviou", None))

    def test_item_antigo_sem_expiresAt_nao_trava(self):
        """Itens enfileirados antes desta mudança não têm o campo. Tratá-los
        como vencidos apagaria a fila existente; como eternos, seria o bug."""
        acoes = roda([item(expiresAt=None)])

        self.assertNotIn(("expira", "prazo_vencido"), acoes)

    def test_a_validade_e_de_72h(self):
        self.assertEqual(VALIDADE_HORAS, 72)


class TestAdiaEmVezDeFalhar(unittest.TestCase):
    """O coração do retry: o que muda com o tempo não pode ser terminal."""

    def test_politica_adia(self):
        acoes = roda([item(phone="5511988887777")])

        self.assertEqual(acoes, [("adia", "politica_nao_permite")])

    def test_clinica_pausada_adia(self):
        acoes = roda([item()], clinic={**CLINICA, "bot_paused": True})

        self.assertEqual(acoes, [("adia", "politica_nao_permite")])

    def test_fora_do_horario_adia(self):
        acoes = roda([item()], clinic={**CLINICA, "business_hours": {
            "fri": {"start": "20:30", "end": "21:00"}}})

        self.assertEqual(acoes, [("adia", "fora_do_horario")])

    def test_nada_disso_marca_falha_terminal(self):
        """Se voltar a ser FAILED, o lead some da fila e ninguém percebe."""
        for acoes in (roda([item(phone="5511988887777")]),
                      roda([item()], clinic={**CLINICA, "bot_paused": True})):
            with self.subTest(acoes=acoes):
                self.assertNotIn("falha", [a for a, _ in acoes])


class TestJaEstaConversando(unittest.TestCase):
    def test_quem_ja_falou_sai_da_fila(self):
        """Terminal de propósito: quem já escreveu não volta a ser lead frio, e
        adiar deixaria a abordagem pendurada até o prazo."""
        acoes = roda([item()], conversando=True)

        self.assertEqual(acoes, [("falha", "ja_conversando")])

    def test_e_conferido_antes_de_qualquer_envio(self):
        acoes = roda([item()], conversando=True)

        self.assertNotIn("enviou", [a for a, _ in acoes])


class TestJaEstaConversandoDeVerdade(unittest.TestCase):
    """A função em si, sem o handler em volta."""

    def _tracker(self, eventos):
        t = mock.MagicMock()
        t.get_conversation_messages.return_value = eventos
        return t

    def test_inbound_depois_do_cadastro_conta(self):
        desde = "2026-09-05T13:40:00Z"
        t = self._tracker([{"direction": "INBOUND", "createdAt": "2026-09-05T13:50:00Z"}])

        self.assertTrue(proc._ja_esta_conversando(t, "c1", PILOTO, desde))

    def test_inbound_anterior_ao_cadastro_nao_conta(self):
        """Conversa velha não é a conversa deste lead."""
        desde = "2026-09-05T13:40:00Z"
        t = self._tracker([{"direction": "INBOUND", "createdAt": "2026-09-01T10:00:00Z"}])

        self.assertFalse(proc._ja_esta_conversando(t, "c1", PILOTO, desde))

    def test_so_outbound_nao_conta(self):
        """A clínica ter falado não significa que a pessoa respondeu."""
        t = self._tracker([{"direction": "OUTBOUND", "createdAt": "2026-09-05T13:50:00Z"}])

        self.assertFalse(proc._ja_esta_conversando(t, "c1", PILOTO, "2026-09-05T13:40:00Z"))

    def test_tolera_o_nono_digito(self):
        """O WhatsApp guarda DDD fora de 11-28 sem o 9. Casar exato já fez um
        lead com conversa desenvolvida aparecer como sem contato."""
        t = mock.MagicMock()
        t.get_conversation_messages.side_effect = lambda c, phone, limit: (
            [{"direction": "INBOUND", "createdAt": "2026-09-05T13:50:00Z"}]
            if phone == "554797053940" else []
        )

        self.assertTrue(
            proc._ja_esta_conversando(t, "c1", "5547997053940", "2026-09-05T13:40:00Z"))

    def test_falha_ao_conferir_deixa_passar(self):
        """Falha ABERTA: bloquear por dúvida pararia a fila em silêncio toda vez
        que o DynamoDB engasgasse."""
        t = mock.MagicMock()
        t.get_conversation_messages.side_effect = RuntimeError("dynamo fora")

        self.assertFalse(proc._ja_esta_conversando(t, "c1", PILOTO, "2026-09-05T13:40:00Z"))


if __name__ == "__main__":
    unittest.main()
