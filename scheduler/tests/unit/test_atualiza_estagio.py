# -*- coding: utf-8 -*-
"""PATCH do estagio: grava MANUAL com o usuario, recusa fato da agenda e exige papel."""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.lead import atualiza_estagio as h
from src.utils.acesso import Identidade, STAFF

LEAD_ID = "11111111-1111-1111-1111-111111111111"


def evento(body, lead_id=LEAD_ID):
    return {"pathParameters": {"clinicId": "c1", "leadId": lead_id}, "headers": {"x-api-key": "k"},
            "body": json.dumps(body)}


class TestPatch(unittest.TestCase):
    def setUp(self):
        self.ident = Identidade(papel=STAFF, user_id="u1", clinic_id="c1", nome="Ana")
        self.db = mock.MagicMock()
        self.db.execute_query.return_value = [{"id": LEAD_ID, "clinic_id": "c1", "stage": "SUMIU",
                                               "stage_source": "REGRA", "stage_reason": None,
                                               "ultima_mensagem_em": None, "ultima_mensagem_de": None}]

    def chama(self, body):
        with mock.patch.object(h, "require_acesso", return_value=(self.ident, None)), \
             mock.patch.object(h, "PostgresService", return_value=self.db):
            return h.handler(evento(body), None)

    def test_grava_manual_com_usuario(self):
        r = self.chama({"stage": "NAO_AGENDOU", "reason": "achou caro"})
        self.assertEqual(r["statusCode"], 200)
        escritas = [(" ".join(c.args[0].split()), c.args[1]) for c in self.db.execute_write.call_args_list]
        self.assertTrue(any("UPDATE scheduler.leads SET stage" in a[0] and a[1][2] == "MANUAL" for a in escritas))
        self.assertTrue(any("lead_stage_events" in a[0] and "u1" in a[1] for a in escritas))
        corpo = json.loads(r["body"])
        self.assertEqual(corpo["lead"]["stage_source"], "MANUAL")
        self.assertEqual(corpo["lead"]["stage_reason"], "achou caro")

    def test_sem_motivo_limpa_o_motivo_antigo(self):
        self.db.execute_query.return_value[0]["stage_reason"] = "do modelo"
        r = self.chama({"stage": "EM_ANDAMENTO"})
        self.assertEqual(r["statusCode"], 200)
        upd = [c.args for c in self.db.execute_write.call_args_list if "SET stage" in c.args[0]][0]
        self.assertIsNone(upd[1][1])

    def test_motivo_e_truncado(self):
        r = self.chama({"stage": "NAO_AGENDOU", "reason": "x" * 300})
        self.assertLessEqual(len(json.loads(r["body"])["lead"]["stage_reason"]), 120)

    def test_recusa_fato_da_agenda(self):
        for stage in ("AGENDOU", "CANCELOU", "FALTOU"):
            r = self.chama({"stage": stage})
            self.assertEqual(r["statusCode"], 400, stage)
            self.assertIn("agenda", json.loads(r["body"])["message"])
        self.db.execute_write.assert_not_called()

    def test_recusa_estagio_desconhecido(self):
        self.assertEqual(self.chama({"stage": "X"})["statusCode"], 400)
        self.assertEqual(self.chama({})["statusCode"], 400)

    def test_404_sem_lead(self):
        self.db.execute_query.return_value = []
        self.assertEqual(self.chama({"stage": "SUMIU"})["statusCode"], 404)

    def test_lead_e_procurado_na_clinica_do_caminho(self):
        self.chama({"stage": "SUMIU"})
        args = self.db.execute_query.call_args[0]
        self.assertIn("clinic_id = %s", args[0])
        self.assertEqual(args[1], (LEAD_ID, "c1"))

    def test_403_sem_permissao(self):
        with mock.patch.object(h, "require_acesso", return_value=(None, {"statusCode": 403, "body": "{}"})):
            self.assertEqual(h.handler(evento({"stage": "SUMIU"}), None)["statusCode"], 403)


class TestPermissao(unittest.TestCase):
    def test_staff_tem_crm(self):
        from src.utils.acesso import PERMISSOES_DO_STAFF
        self.assertIn("crm.ler", PERMISSOES_DO_STAFF)
        self.assertIn("crm.escrever", PERMISSOES_DO_STAFF)


if __name__ == "__main__":
    unittest.main()
