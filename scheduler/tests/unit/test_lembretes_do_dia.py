# -*- coding: utf-8 -*-
"""O botao do painel: previa conta sem escrever; o envio enfileira e acorda o
processador; dia passado e dia invalido sao recusados."""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")
os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "t")

from src.functions.appointment import lembretes_do_dia as h
from src.utils.acesso import Identidade, STAFF

IDENT = Identidade(papel=STAFF, user_id="u1", clinic_id="c1")
CLINIC = {"clinic_id": "c1", "timezone": "America/Sao_Paulo", "custom_domain": "x.com", "janela_de_silencio": None}
RESULTADO = {"enfileirados": 2, "ja_lembrados": 1, "sem_telefone": 0, "enfileirados_antes": 0,
             "send_at": "2026-11-05T12:00:00Z"}


def evento(dia, simular=False):
    return {"pathParameters": {"clinicId": "c1", "dia": dia},
            "queryStringParameters": {"simular": "true"} if simular else None,
            "headers": {"x-api-key": "k"}, "body": None}


class TestEndpoint(unittest.TestCase):
    def chama(self, ev, clinic=CLINIC, resultado=None):
        db = mock.MagicMock()
        db.execute_query.return_value = [clinic] if clinic else []
        with mock.patch.object(h, "require_acesso", return_value=(IDENT, None)), \
             mock.patch.object(h, "PostgresService", return_value=db), \
             mock.patch.object(h, "ReminderService"), \
             mock.patch.object(h, "enfileira", return_value=dict(resultado or RESULTADO)) as enf, \
             mock.patch.object(h, "_acorda_processador") as acorda, \
             mock.patch.object(h, "_hoje", return_value="2026-11-05"):
            return h.handler(ev, None), enf, acorda

    def test_simular_devolve_contagens_e_nao_acorda(self):
        r, enf, acorda = self.chama(evento("2026-11-06", simular=True))
        self.assertEqual(r["statusCode"], 200)
        self.assertTrue(enf.call_args.kwargs["simular"])
        acorda.assert_not_called()
        corpo = json.loads(r["body"])
        self.assertTrue(corpo["tem_link_de_autoatendimento"])
        self.assertEqual(corpo["ja_lembrados"], 1)

    def test_real_enfileira_e_acorda(self):
        r, enf, acorda = self.chama(evento("2026-11-06"))
        self.assertEqual(json.loads(r["body"])["enfileirados"], 2)
        self.assertFalse(enf.call_args.kwargs["simular"])
        acorda.assert_called_once()

    def test_sem_nada_a_enfileirar_nao_acorda(self):
        _, _, acorda = self.chama(evento("2026-11-06"), resultado=dict(RESULTADO, enfileirados=0))
        acorda.assert_not_called()

    def test_sem_site_avisa(self):
        r, _, _ = self.chama(evento("2026-11-06", simular=True), clinic=dict(CLINIC, custom_domain=None))
        self.assertFalse(json.loads(r["body"])["tem_link_de_autoatendimento"])

    def test_dia_passado_recusa(self):
        r, _, _ = self.chama(evento("2026-11-04"))
        self.assertEqual(r["statusCode"], 400)

    def test_dia_invalido_recusa(self):
        r, _, _ = self.chama(evento("06-11-2026"))
        self.assertEqual(r["statusCode"], 400)

    def test_clinica_inexistente_404(self):
        r, _, _ = self.chama(evento("2026-11-06"), clinic=None)
        self.assertEqual(r["statusCode"], 404)

    def test_sem_permissao_passa_o_erro(self):
        with mock.patch.object(h, "require_acesso", return_value=(None, {"statusCode": 403, "body": "{}"})):
            self.assertEqual(h.handler(evento("2026-11-06"), None)["statusCode"], 403)


if __name__ == "__main__":
    unittest.main()
