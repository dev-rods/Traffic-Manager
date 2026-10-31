# -*- coding: utf-8 -*-
"""A lista de conversas recentes diz por que o bot está calado em cada uma.

Antes a recepção abria conversa por conversa para descobrir quem estava "fora
da regra" (PRD 031). A lista vem do MessageEvents; o motivo vem das sessões e
da política da clínica, e falhar nesses dois não pode derrubar a lista.
"""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("MESSAGE_EVENTS_TABLE", "t")
os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.attendant import conversations as C
from src.services import atendimento as at
from src.services.sessoes_da_clinica import carrega_sessoes_da_clinica

COM_PESSOA = "5511999990001"
AVULSO = "5511999990002"
LEAD = "5511999990003"


def evento(phone, direction, quando):
    return {"phone": phone, "direction": direction, "content": "oi", "createdAt": quando, "senderName": ""}


class TabelaDeEventos:
    def query(self, **kw):
        return {"Items": [evento(COM_PESSOA, "INBOUND", "2026-10-31T10:00:00Z"),
                          evento(AVULSO, "INBOUND", "2026-10-31T09:00:00Z"),
                          evento(LEAD, "INBOUND", "2026-10-31T08:00:00Z")]}


class TabelaDeSessoes:
    def __init__(self):
        self.itens = [
            {"pk": "CLINIC#c1", "sk": f"PHONE#{COM_PESSOA}",
             "session": at.entrega_a_humano({}, por=at.POR_ATENDENTE)},
            {"pk": "CLINIC#c1", "sk": f"PHONE#{LEAD}", "session": {"bot_enabled": True}},
            {"pk": "CLINIC#c1", "sk": "LID#abc", "phone": LEAD},
        ]

    def query(self, **kw):
        return {"Items": self.itens}


def chama(clinica, sessoes=None):
    evento_http = {"pathParameters": {"clinicId": "c1"}, "queryStringParameters": None, "headers": {"x-api-key": "k"}}
    db = mock.MagicMock()
    db.execute_query.side_effect = lambda sql, p=None: [clinica] if "FROM scheduler.clinics" in sql else []
    with mock.patch.object(C, "require_api_key", return_value=("k", None)), \
         mock.patch.object(C, "boto3") as boto, \
         mock.patch("src.services.db.postgres.PostgresService", return_value=db), \
         mock.patch("src.services.sessoes_da_clinica.carrega_sessoes_da_clinica",
                    side_effect=sessoes or (lambda c: carrega_sessoes_da_clinica(c, table=TabelaDeSessoes()))):
        boto.resource.return_value.Table.return_value = TabelaDeEventos()
        r = C.handler(evento_http, None)
    return r["statusCode"], {c["phone"]: c for c in json.loads(r["body"])["conversations"]}


class TestMotivoNaLista(unittest.TestCase):
    def test_leads_only_distingue_os_tres_casos(self):
        status, por_fone = chama({"bot_autoreply_policy": "LEADS_ONLY", "bot_paused": False})
        self.assertEqual(status, 200)
        self.assertEqual(por_fone[COM_PESSOA]["pause_reason"], "attendant")
        self.assertEqual(por_fone[AVULSO]["pause_reason"], "not_eligible")   # sem sessao: cenario 3
        self.assertIsNone(por_fone[LEAD]["pause_reason"])
        self.assertEqual([por_fone[f]["bot_paused"] for f in (COM_PESSOA, AVULSO, LEAD)], [True, True, False])

    def test_clinica_pausada(self):
        _, por_fone = chama({"bot_autoreply_policy": "ALL", "bot_paused": True})
        self.assertEqual(por_fone[AVULSO]["pause_reason"], "clinic_paused")
        self.assertEqual(por_fone[COM_PESSOA]["pause_reason"], "attendant")

    def test_falha_ao_ler_sessoes_nao_derruba_a_lista(self):
        def explode(c):
            raise RuntimeError("dynamo fora")
        status, por_fone = chama({"bot_autoreply_policy": "LEADS_ONLY"}, sessoes=explode)
        self.assertEqual(status, 200)
        self.assertEqual(len(por_fone), 3)
        self.assertNotIn("pause_reason", por_fone[AVULSO])


class TestCarregaSessoesDaClinica(unittest.TestCase):
    def test_so_os_itens_phone_e_pela_chave_do_sk(self):
        sessoes = carrega_sessoes_da_clinica("c1", table=TabelaDeSessoes())
        self.assertEqual(set(sessoes), {COM_PESSOA, LEAD})
        self.assertTrue(sessoes[LEAD]["bot_enabled"])

    def test_pagina(self):
        class Paginada:
            def __init__(self):
                self.chamadas = 0

            def query(self, **kw):
                self.chamadas += 1
                if "ExclusiveStartKey" not in kw:
                    return {"Items": [{"sk": "PHONE#1", "session": {}}], "LastEvaluatedKey": {"sk": "PHONE#1"}}
                return {"Items": [{"sk": "PHONE#2", "session": {}}]}
        t = Paginada()
        self.assertEqual(set(carrega_sessoes_da_clinica("c1", table=t)), {"1", "2"})
        self.assertEqual(t.chamadas, 2)

    def test_falha_vira_vazio(self):
        class Quebrada:
            def query(self, **kw):
                raise RuntimeError("x")
        self.assertEqual(carrega_sessoes_da_clinica("c1", table=Quebrada()), {})


if __name__ == "__main__":
    unittest.main()
