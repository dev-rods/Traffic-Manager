# -*- coding: utf-8 -*-
"""PRD 061: so depois do codigo confirmado o site fica sabendo quem e o dono do
numero - primeiro nome e o que falta no cadastro. Antes dele, nada."""
import json
import unittest
from unittest import mock

from src.functions.public_booking import confirm_otp as modulo
from src.utils.booking_verification import InvalidCodeError

CLINIC = "clinicadepilacaopremium-3fbce9"
FONE = "5511999990061"


def _corpo(r):
    return json.loads(r["body"])


class TestConfirm(unittest.TestCase):
    def chama(self, corpo, paciente=None, codigo_ok=True):
        evento = {"pathParameters": {"clinicId": CLINIC}, "headers": {"x-api-key": "k"}, "body": json.dumps(corpo)}
        confirm = mock.MagicMock(return_value="tok") if codigo_ok else mock.MagicMock(side_effect=InvalidCodeError("errado"))
        with mock.patch.object(modulo, "require_booking_intake_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "confirm_code", confirm), \
             mock.patch.object(modulo, "PostgresService"), \
             mock.patch.object(modulo.carrinho, "paciente_do_telefone", return_value=paciente) as busca:
            return modulo.handler(evento, None), busca

    def test_codigo_valido_devolve_primeiro_nome_e_o_que_falta(self):
        r, _ = self.chama({"phone": FONE, "code": "123456"},
                          paciente={"id": "p1", "name": "Edna Maria", "cpf": None, "birth_date": "1990-01-01", "email": "e@x.com"})
        self.assertEqual(r["statusCode"], 200)
        corpo = _corpo(r)
        self.assertEqual(corpo["token"], "tok")
        self.assertEqual(corpo["paciente"], {"nome": "Edna", "faltam": ["cpf"]})
        self.assertNotIn("Maria", r["body"])
        self.assertNotIn("e@x.com", r["body"])

    def test_celular_sem_ficha_devolve_null(self):
        r, _ = self.chama({"phone": FONE, "code": "123456"}, paciente=None)
        self.assertEqual(r["statusCode"], 200)
        self.assertIsNone(_corpo(r)["paciente"])

    def test_codigo_errado_nao_consulta_nem_devolve(self):
        r, busca = self.chama({"phone": FONE, "code": "000000"}, paciente={"id": "p1", "name": "Edna"}, codigo_ok=False)
        self.assertEqual(r["statusCode"], 400)
        busca.assert_not_called()
        self.assertNotIn("Edna", r["body"])

    def test_escopo_documentos_nao_devolve_paciente(self):
        r, busca = self.chama({"phone": FONE, "code": "123456", "scope": "documentos"}, paciente={"id": "p1", "name": "Edna"})
        self.assertEqual(r["statusCode"], 200)
        self.assertNotIn("paciente", _corpo(r))
        busca.assert_not_called()


if __name__ == "__main__":
    unittest.main()
