# -*- coding: utf-8 -*-
"""`atendimento.motivo_da_recusa`: qual porta fechou (diagnostico e logs)."""
import unittest

from src.services import atendimento

LEADS_ONLY = {"clinic_id": "c1", "bot_autoreply_policy": "LEADS_ONLY", "bot_paused": False}
ALL = dict(LEADS_ONLY, bot_autoreply_policy="ALL")


class TestMotivoDaRecusa(unittest.TestCase):
    def test_politica(self):
        self.assertEqual(atendimento.motivo_da_recusa(LEADS_ONLY, {}, "5511999990000"), atendimento.RECUSA_POLITICA)

    def test_outras_portas_vem_antes(self):
        self.assertEqual(atendimento.motivo_da_recusa(LEADS_ONLY, {}, "55", silenciado=True), atendimento.RECUSA_SILENCIADO)
        self.assertEqual(atendimento.motivo_da_recusa(dict(LEADS_ONLY, bot_paused=True), {}, "55"), atendimento.RECUSA_PAUSADO)
        sessao = atendimento.entrega_a_humano({}, por=atendimento.POR_ATENDENTE)
        self.assertEqual(atendimento.motivo_da_recusa(LEADS_ONLY, sessao, "55"), atendimento.RECUSA_COM_PESSOA)

    def test_pode_responder_e_none(self):
        self.assertIsNone(atendimento.motivo_da_recusa(ALL, {}, "55"))
        self.assertIsNone(atendimento.motivo_da_recusa(LEADS_ONLY, {"bot_enabled": True}, "55"))
