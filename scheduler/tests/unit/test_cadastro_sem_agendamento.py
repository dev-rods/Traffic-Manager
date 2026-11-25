# -*- coding: utf-8 -*-
"""PRD 061: o site cadastra a pessoa assim que ela confirma o codigo, antes
de escolher data. A rota exige o token, valida pela mesma regua da criacao,
grava pelo mesmo `completa_paciente` e nunca devolve dado sensivel."""
import json
import unittest
from unittest import mock

from src.functions.public_booking import cadastro as modulo
from src.services import cadastro_pelo_site as cps

CLINIC = "clinicadepilacaopremium-3fbce9"
FONE = "5511999990061"
COMPLETA = {"id": "p1", "name": "Ana Souza", "cpf": "52998224725", "birth_date": "1990-01-01", "email": "a@b.com"}
PARCIAL = {"id": "p2", "name": "Bia Lima", "cpf": None, "birth_date": None, "email": "b@b.com"}


def _corpo(r):
    return json.loads(r["body"])


class TestRota(unittest.TestCase):
    def chama(self, corpo, paciente=None, token_ok=True, conflito=False):
        evento = {"pathParameters": {"clinicId": CLINIC}, "headers": {"x-api-key": "k"}, "body": json.dumps(corpo)}
        db = mock.MagicMock()
        db.execute_query.return_value = [{"clinic_id": CLINIC}]
        gravado = dict(paciente or {"id": "novo", "name": corpo.get("fullName"), "cpf": corpo.get("cpf"),
                                    "birth_date": corpo.get("birthDate"), "email": corpo.get("email")})
        with mock.patch.object(modulo, "require_booking_intake_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "PostgresService", return_value=db), \
             mock.patch.object(modulo, "verify_token", return_value=token_ok), \
             mock.patch.object(modulo.carrinho, "paciente_do_telefone", return_value=paciente), \
             mock.patch.object(modulo, "conflito_de_cpf", return_value=conflito), \
             mock.patch.object(modulo, "completa_paciente", return_value=gravado) as completa:
            return modulo.handler(evento, None), completa

    def test_sem_token_401(self):
        r, completa = self.chama({"phone": FONE, "fullName": "Ana"}, token_ok=False)
        self.assertEqual(r["statusCode"], 401)
        completa.assert_not_called()
        r, _ = self.chama({"phone": FONE, "fullName": "Ana"} | {"token": ""})
        self.assertEqual(r["statusCode"], 401)

    def test_celular_novo_sem_nome_400(self):
        r, completa = self.chama({"phone": FONE, "token": "t", "cpf": "529.982.247-25",
                                  "birthDate": "1990-01-01", "email": "a@b.com"})
        self.assertEqual(r["statusCode"], 400)
        self.assertEqual(_corpo(r)["faltam"], ["name"])
        completa.assert_not_called()

    def test_celular_novo_faltando_campo_400(self):
        r, completa = self.chama({"phone": FONE, "token": "t", "fullName": "Ana Souza", "cpf": "529.982.247-25"})
        self.assertEqual(r["statusCode"], 400)
        self.assertEqual(_corpo(r)["code"], "CADASTRO_INCOMPLETO")
        self.assertEqual(sorted(_corpo(r)["faltam"]), ["birth_date", "email"])
        completa.assert_not_called()

    def test_cpf_invalido_400(self):
        r, _ = self.chama({"phone": FONE, "token": "t", "fullName": "Ana", "cpf": "111.111.111-11",
                           "birthDate": "1990-01-01", "email": "a@b.com"})
        self.assertEqual(r["statusCode"], 400)
        self.assertEqual(_corpo(r)["faltam"], ["cpf"])

    def test_cpf_de_outro_409(self):
        r, completa = self.chama({"phone": FONE, "token": "t", "fullName": "Ana Souza", "cpf": "529.982.247-25",
                                  "birthDate": "1990-01-01", "email": "a@b.com"}, conflito=True)
        self.assertEqual(r["statusCode"], 409)
        self.assertEqual(_corpo(r)["code"], "CPF_EM_USO")
        completa.assert_not_called()

    def test_celular_novo_cria_a_ficha_e_responde_so_o_primeiro_nome(self):
        r, completa = self.chama({"phone": FONE, "token": "t", "fullName": "Ana Souza", "cpf": "529.982.247-25",
                                  "birthDate": "1990-01-01", "email": "a@b.com"})
        self.assertEqual(r["statusCode"], 200)
        args = completa.call_args.args
        self.assertEqual(args[1:], (CLINIC, FONE, "Ana Souza", "52998224725", "1990-01-01", "a@b.com"))
        corpo = _corpo(r)
        self.assertEqual(corpo["paciente"], {"nome": "Ana", "faltam": []})
        self.assertNotIn("cpf", json.dumps(corpo))
        self.assertNotIn("52998224725", r["body"])
        self.assertNotIn("a@b.com", r["body"])

    def test_paciente_parcial_so_precisa_do_que_falta(self):
        r, completa = self.chama({"phone": FONE, "token": "t", "cpf": "529.982.247-25", "birthDate": "1990-01-01"},
                                 paciente=PARCIAL)
        self.assertEqual(r["statusCode"], 200)
        args = completa.call_args.args
        self.assertEqual(args[3:], (None, "52998224725", "1990-01-01", None))

    def test_paciente_parcial_sem_o_que_falta_400(self):
        r, completa = self.chama({"phone": FONE, "token": "t", "cpf": "529.982.247-25"}, paciente=PARCIAL)
        self.assertEqual(r["statusCode"], 400)
        self.assertEqual(_corpo(r)["faltam"], ["birth_date"])
        completa.assert_not_called()

    def test_so_phone_e_token_consulta_sem_gravar(self):
        r, completa = self.chama({"phone": FONE, "token": "t"}, paciente=PARCIAL)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(_corpo(r)["paciente"], {"nome": "Bia", "faltam": ["birth_date", "cpf"]})
        completa.assert_not_called()
        r, completa = self.chama({"phone": FONE, "token": "t"}, paciente=None)
        self.assertIsNone(_corpo(r)["paciente"])
        completa.assert_not_called()

    def test_rota_registrada(self):
        from src.functions.public_booking.router import ROUTES
        self.assertIs(ROUTES[("POST", "public/clinics/{clinicId}/cadastro")], modulo.handler)


class TestCompletaPaciente(unittest.TestCase):
    """A extracao nao mudou a gravacao: a criacao chama o mesmo codigo."""

    def test_criacao_delega(self):
        import inspect
        from src.services.appointment_service import AppointmentService
        fonte = inspect.getsource(AppointmentService._get_or_create_patient)
        self.assertIn("completa_paciente(self.db, clinic_id, phone, full_name, cpf, birth_date, email)", fonte)

    def test_insert_quando_nao_ha_ficha(self):
        db = mock.MagicMock()
        db.execute_query.return_value = []
        db.execute_write_returning.return_value = {"id": "n"}
        cps.completa_paciente(db, CLINIC, FONE, "Ana Souza", "52998224725", "1990-01-01", "a@b.com")
        sql, params = db.execute_write_returning.call_args.args
        self.assertIn("INSERT INTO scheduler.patients", sql)
        self.assertEqual(params, (CLINIC, FONE, "Ana Souza", "52998224725", "1990-01-01", "a@b.com"))

    def test_so_o_vazio_e_preenchido(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [dict(PARCIAL, phone=FONE, deleted_at=None)]
        db.execute_write_returning.return_value = {"id": "p2"}
        cps.completa_paciente(db, CLINIC, FONE, "Outro Nome", "52998224725", None, "x@y.com")
        sql, params = db.execute_write_returning.call_args.args
        self.assertIn("COALESCE(NULLIF(name, ''), %s)", sql)
        self.assertEqual(params, ("Outro Nome", "52998224725", None, "x@y.com", "p2"))

    def test_nada_a_completar_nao_escreve(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [dict(COMPLETA, phone=FONE, deleted_at=None)]
        self.assertEqual(cps.completa_paciente(db, CLINIC, FONE, "Ana", "52998224725", "1990-01-01", "a@b.com")["id"], "p1")
        db.execute_write_returning.assert_not_called()

    def test_primeiro_nome(self):
        self.assertEqual(cps.primeiro_nome("  Edna Maria  Silva "), "Edna")
        self.assertEqual(cps.primeiro_nome(None), "")

    def test_conflito_de_cpf(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [{"id": "outro"}]
        self.assertTrue(cps.conflito_de_cpf(db, CLINIC, "52998224725", "p1"))
        self.assertFalse(cps.conflito_de_cpf(db, CLINIC, None, "p1"))
        db.execute_query.return_value = []
        self.assertFalse(cps.conflito_de_cpf(db, CLINIC, "52998224725", None))


if __name__ == "__main__":
    unittest.main()
