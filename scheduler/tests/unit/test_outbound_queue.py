"""Fila de envio: quando a mensagem pode sair e transições de status.

O DynamoDB é substituído por um fake em memória para o teste cobrir a regra de
negócio (quando a abordagem pode sair) sem depender de infraestrutura.

A fila guarda a INTENÇÃO de falar, não um texto: quem escreve é o
ConversationAgent no momento do envio, com o mesmo prompt usado quando o lead
escreve primeiro. Por isso `enqueue` não recebe conteúdo.
"""
import os
import unittest
from datetime import datetime

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")

TZ = pytz.timezone("America/Sao_Paulo")
ESSENCIA = {d: {"start": "07:15", "end": "21:00"} for d in ["mon", "tue", "wed", "thu", "fri"]}


class FakeTable:
    def __init__(self):
        self.items = []
        self.updates = []

    def put_item(self, Item):
        self.items.append(Item)

    def update_item(self, **kwargs):
        self.updates.append(kwargs)


def _service(table):
    from src.services.outbound_queue import OutboundQueueService

    service = OutboundQueueService.__new__(OutboundQueueService)
    service.table = table
    return service


class TestAtraso(unittest.TestCase):
    """Boa parte dos leads procura a clínica sozinha logo após preencher o
    formulário. Abordar na hora atropelaria essa conversa, então o bot espera."""

    def test_espera_30_minutos_mesmo_dentro_do_horario(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours=ESSENCIA, now=agora)

        self.assertEqual(item["status"], "PENDING")
        # 16:46 + 30min = 17:16 BRT = 20:16 UTC
        self.assertEqual(item["sendAfter"], "2026-08-17T20:16:00Z")

    def test_atraso_que_cruza_o_fechamento_cai_no_dia_seguinte(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 20, 50))  # +30min = 21:20, já fechou

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours=ESSENCIA, now=agora)

        # terça 07:15 BRT = 10:15 UTC
        self.assertEqual(item["sendAfter"], "2026-08-18T10:15:00Z")

    def test_atraso_configuravel(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours=ESSENCIA,
                                       now=agora, atraso_minutos=0)

        self.assertEqual(item["sendAfter"], "2026-08-17T19:46:00Z")


class TestEnqueue(unittest.TestCase):
    def test_fora_do_horario_espera_a_proxima_abertura(self):
        """Caso real: lead Fernanda, sábado 06:45."""
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 15, 6, 45))

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours=ESSENCIA, now=agora)

        # segunda 07:15 BRT = 10:15 UTC; o atraso de 30min não muda nada aqui
        self.assertEqual(item["sendAfter"], "2026-08-17T10:15:00Z")

    def test_sem_horario_configurado_nao_enfileira(self):
        """Sem janela não há quando enviar; o item ficaria preso para sempre."""
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 10, 0))

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours={}, now=agora)

        self.assertIsNone(item)
        self.assertEqual(table.items, [])

    def test_grava_chaves_e_lead(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))

        item = _service(table).enqueue(
            "clinica-x", "5511999999999", lead_id="lead-1", business_hours=ESSENCIA, now=agora
        )

        self.assertEqual(item["leadId"], "lead-1")
        self.assertEqual(item["kind"], "FIRST_CONTACT")
        self.assertEqual(item["pk"], "CLINIC#clinica-x")
        # 16:46 + 30min de atraso = 17:16 BRT = 20:16 UTC
        self.assertTrue(item["sk"].startswith("OUT#2026-08-17T20:16:00Z#"))
        self.assertEqual(len(table.items), 1)

    def test_nao_guarda_texto(self):
        """O texto é do agente, não da fila: dois textos divergiriam com o tempo."""
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours=ESSENCIA, now=agora)

        self.assertNotIn("content", item)

    def test_cada_item_tem_id_proprio(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))
        service = _service(table)

        a = service.enqueue("clinica-x", "5511999999999", business_hours=ESSENCIA, now=agora)
        b = service.enqueue("clinica-x", "5511988888888", business_hours=ESSENCIA, now=agora)

        self.assertNotEqual(a["messageId"], b["messageId"])


class TestTransicoes(unittest.TestCase):
    def test_mark_sent_atualiza_status(self):
        table = FakeTable()

        _service(table).mark_sent("msg-1", "CLINIC#c", "OUT#x#msg-1")

        self.assertEqual(len(table.updates), 1)
        self.assertIn("SENT", str(table.updates[0]))

    def test_mark_failed_registra_erro(self):
        table = FakeTable()

        _service(table).mark_failed("msg-1", "CLINIC#c", "OUT#x#msg-1", "timeout do provider")

        self.assertIn("timeout do provider", str(table.updates[0]))


if __name__ == "__main__":
    unittest.main()
