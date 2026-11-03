# -*- coding: utf-8 -*-
"""O eco do bot não vira atendente humana quando o WhatsApp tira o nono dígito.

Caso real de 03/11/2026 (Nobre SJC): o lead do site gravou `5531994157070`, o
bot abriu a conversa nesse número, e a z-api devolveu o eco com
`phone=553194157070`. O webhook procurou o envio do bot só sob o número de 12
dígitos, não achou, pausou o bot por 24h numa segunda sessão - e a resposta
"Virilha" da pessoa caiu nessa sessão em silêncio.
"""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.functions.webhook import handler as wh

CLINIC = "nobrelaser-sjc"
COM_NOVE = "5531994157070"
SEM_NOVE = "553194157070"
MSG_ID = "3EB0285703A739FFB210E3"


def payload_de_eco(phone):
    return {"body": json.dumps({
        "instanceId": "inst-1", "messageId": MSG_ID, "phone": phone,
        "fromMe": True, "status": "SENT", "type": "ReceivedCallback",
        "chatLid": "199402597675222@lid", "connectedPhone": "5511915252767",
        "text": {"message": "Oi! Vi que você se interessou pela Nobre Laser SJC"},
    })}


class TabelaDeSessoes:
    def __init__(self, *telefones):
        self.itens = {f"PHONE#{t}": {"session": {}} for t in telefones}
        self.gravados = []

    def get_item(self, Key):
        item = self.itens.get(Key["sk"])
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.gravados.append(Item)


class TestEcoComNonoDigito(unittest.TestCase):
    def setUp(self):
        self.tabela = TabelaDeSessoes(COM_NOVE)
        mock.patch.object(wh, "PostgresService").start()
        mock.patch.object(wh, "_resolve_clinic_id", return_value=CLINIC).start()
        mock.patch.object(wh, "_get_sessions_table", return_value=self.tabela).start()
        self.pausa = mock.patch.object(wh, "_activate_attendant_mode").start()
        self.tracker = mock.patch.object(wh, "MessageTracker").start().return_value
        self.addCleanup(mock.patch.stopall)

        # O envio do bot está gravado sob o número COM nove, e só sob ele.
        def eventos(clinic_id, phone, limit=None):
            if phone == COM_NOVE:
                return [{"direction": "OUTBOUND", "providerMessageId": MSG_ID}]
            return []
        self.tracker.get_conversation_messages.side_effect = eventos

    def test_eco_sem_nove_e_reconhecido_como_do_bot(self):
        wh.handler(payload_de_eco(SEM_NOVE), None)
        self.pausa.assert_not_called()
        self.tracker.track_outbound.assert_not_called()

    def test_atendente_de_verdade_continua_pausando_na_sessao_existente(self):
        """Mensagem do celular que o bot não enviou: pausa, mas na sessão que já
        existe, não numa segunda."""
        self.tracker.get_conversation_messages.side_effect = None
        self.tracker.get_conversation_messages.return_value = []
        wh.handler(payload_de_eco(SEM_NOVE), None)
        self.pausa.assert_called_once_with(CLINIC, COM_NOVE)

    def test_vinculo_do_lid_aprende_a_forma_canonica(self):
        wh.handler(payload_de_eco(SEM_NOVE), None)
        lids = [i for i in self.tabela.gravados if i["sk"].startswith("LID#")]
        self.assertEqual([i["phone"] for i in lids], [COM_NOVE])

    def test_sem_sessao_previa_nada_muda(self):
        self.tabela.itens.clear()
        self.tracker.get_conversation_messages.side_effect = None
        self.tracker.get_conversation_messages.return_value = []
        wh.handler(payload_de_eco(SEM_NOVE), None)
        self.pausa.assert_called_once_with(CLINIC, SEM_NOVE)
