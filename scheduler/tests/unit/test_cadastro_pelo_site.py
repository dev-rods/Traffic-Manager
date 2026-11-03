# -*- coding: utf-8 -*-
"""O site pede o cadastro de quem ainda não é paciente (PRD 032).

A cotação diz o que falta; a criação exige o que falta, pela mesma função;
o serviço grava no paciente novo e completa só o vazio no existente; CPF de
outro paciente é recusado. Reaproveita o catálogo falso de
`test_carrinho_do_site`.
"""
import unittest
from unittest import mock

from src.services import carrinho
from src.services.identificacao_de_paciente import campos_faltantes
from src.utils.cadastro import normaliza_email
from tests.unit.test_carrinho_do_site import (
    AXILAS, Db, FONE, PACIENTE_COMPLETO, SVC, VIRILHA, _Criacao, _Handler, corpo, evento,
)

CPF_VALIDO = "52998224725"
CPF_INVALIDO = "11111111111"
PARCIAL = dict(PACIENTE_COMPLETO, email=None)


class TestCamposFaltantes(unittest.TestCase):
    def test_sem_paciente_faltam_todos(self):
        self.assertEqual(campos_faltantes(None), ["name", "birth_date", "cpf", "email"])

    def test_vazio_conta_como_faltando(self):
        self.assertEqual(campos_faltantes(dict(PACIENTE_COMPLETO, email="  ")), ["email"])

    def test_completo_nao_falta_nada(self):
        self.assertEqual(campos_faltantes(PACIENTE_COMPLETO), [])

    def test_para_o_site_o_nome_sai_da_lista(self):
        self.assertEqual(carrinho.cadastro_para_o_site(None),
                         {"completo": False, "faltam": ["birth_date", "cpf", "email"]})
        self.assertEqual(carrinho.cadastro_para_o_site(PARCIAL), {"completo": False, "faltam": ["email"]})
        self.assertEqual(carrinho.cadastro_para_o_site(PACIENTE_COMPLETO), {"completo": True, "faltam": []})


class TestPacienteDoTelefone(unittest.TestCase):
    def test_um_so_e_pelas_variantes(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [PACIENTE_COMPLETO]
        self.assertEqual(carrinho.paciente_do_telefone(db, "c1", FONE), PACIENTE_COMPLETO)
        sql, params = db.execute_query.call_args[0]
        self.assertIn("phone = ANY(%s)", sql)
        self.assertIn(FONE, params[1])

    def test_ambiguo_e_nenhum(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [PACIENTE_COMPLETO, dict(PACIENTE_COMPLETO, id="outro")]
        self.assertIsNone(carrinho.paciente_do_telefone(db, "c1", FONE))


class TestNormalizaEmail(unittest.TestCase):
    def test_minusculo_sem_espacos(self):
        self.assertEqual(normaliza_email("  Maria@X.com "), "maria@x.com")

    def test_vazio_e_none(self):
        for v in (None, "", "   "):
            self.assertIsNone(normaliza_email(v))

    def test_invalido_e_false(self):
        for v in ("maria", "maria@", "@x.com", "maria@x", "ma ria@x.com"):
            with self.subTest(v=v):
                self.assertIs(normaliza_email(v), False)


class TestQuoteDizOQueFalta(_Handler):
    modulo = "src.functions.public_booking.quote"

    def chama(self, body, db=None):
        from src.functions.public_booking.quote import handler
        if db is not None:
            self.db = db
        return handler(evento(body), None)

    CARRINHO = {"serviceIds": [SVC], "serviceAreaPairs": [{"serviceId": SVC, "areaId": AXILAS}]}

    def test_paciente_completo(self):
        q = corpo(self.chama({**self.CARRINHO, "phone": FONE}))["quote"]
        self.assertEqual(q["cadastro"], {"completo": True, "faltam": []})

    def test_numero_novo_falta_tudo_menos_o_nome(self):
        q = corpo(self.chama({**self.CARRINHO, "phone": FONE}, db=Db(paciente=None)))["quote"]
        self.assertEqual(q["cadastro"], {"completo": False, "faltam": ["birth_date", "cpf", "email"]})

    def test_parcial_so_o_que_falta(self):
        q = corpo(self.chama({**self.CARRINHO, "phone": FONE}, db=Db(paciente=PARCIAL)))["quote"]
        self.assertEqual(q["cadastro"]["faltam"], ["email"])

    def test_sem_telefone_nao_ha_cadastro(self):
        q = corpo(self.chama(self.CARRINHO))["quote"]
        self.assertIsNone(q["cadastro"])

    def test_nunca_devolve_valores(self):
        import json
        r = self.chama({**self.CARRINHO, "phone": FONE})
        for valor in (PACIENTE_COMPLETO["cpf"], PACIENTE_COMPLETO["email"], PACIENTE_COMPLETO["birth_date"]):
            self.assertNotIn(valor, json.dumps(corpo(r)))


class TestCriacaoExigeOCadastro(_Criacao):
    CADASTRO = {"cpf": "529.982.247-25", "birthDate": "01/01/1990", "email": " Maria@X.com "}

    def kwargs(self):
        return self.service.create_appointment.call_args.kwargs

    def test_paciente_completo_nao_exige_nada(self):
        self.assertEqual(self.chama()["statusCode"], 201)
        self.assertEqual((self.kwargs()["cpf"], self.kwargs()["birth_date"], self.kwargs()["email"]),
                         (None, None, None))

    def test_numero_novo_sem_os_campos_e_400_com_a_lista(self):
        self.db = Db(paciente=None)
        r = self.chama()
        self.assertEqual(r["statusCode"], 400)
        self.assertEqual(corpo(r)["code"], "CADASTRO_INCOMPLETO")
        self.assertEqual(corpo(r)["faltam"], ["birth_date", "cpf", "email"])
        self.service.create_appointment.assert_not_called()

    def test_numero_novo_com_os_campos_grava_normalizado(self):
        self.db = Db(paciente=None)
        r = self.chama(**self.CADASTRO)
        self.assertEqual(r["statusCode"], 201)
        self.assertEqual((self.kwargs()["cpf"], self.kwargs()["birth_date"], self.kwargs()["email"]),
                         (CPF_VALIDO, "1990-01-01", "maria@x.com"))

    def test_parcial_exige_so_o_que_falta(self):
        self.db = Db(paciente=PARCIAL)
        r = self.chama()
        self.assertEqual((r["statusCode"], corpo(r)["faltam"]), (400, ["email"]))
        self.assertEqual(self.chama(email="m@x.com")["statusCode"], 201)
        self.assertEqual(self.kwargs()["email"], "m@x.com")

    def test_cpf_invalido_data_futura_email_sem_arroba(self):
        self.db = Db(paciente=None)
        for extra, campo in (({**self.CADASTRO, "cpf": CPF_INVALIDO}, "cpf"),
                             ({**self.CADASTRO, "cpf": "123"}, "cpf"),
                             ({**self.CADASTRO, "birthDate": "2099-01-01"}, "birth_date"),
                             ({**self.CADASTRO, "birthDate": "ontem"}, "birth_date"),
                             ({**self.CADASTRO, "email": "maria"}, "email")):
            with self.subTest(campo=campo):
                r = self.chama(**extra)
                self.assertEqual(r["statusCode"], 400)
                self.assertEqual(corpo(r)["code"], "CADASTRO_INCOMPLETO")
                self.assertEqual(corpo(r)["faltam"], [campo])
        self.service.create_appointment.assert_not_called()

    def test_cpf_de_outro_paciente_e_409(self):
        self.db = Db(paciente=None, dono_do_cpf="outro-id")
        r = self.chama(**self.CADASTRO)
        self.assertEqual((r["statusCode"], corpo(r)["code"]), (409, "CPF_EM_USO"))
        self.service.create_appointment.assert_not_called()

    def test_cpf_do_proprio_paciente_nao_e_conflito(self):
        """Paciente parcial informa o CPF que já é dele: a consulta exclui o próprio id."""
        self.db = Db(paciente=dict(PARCIAL, cpf=None), dono_do_cpf=None)
        self.assertEqual(self.chama(cpf=CPF_VALIDO, email="m@x.com")["statusCode"], 201)
        consulta = [c for c in self.db.consultas if "cpf = %s" in c[0]]
        self.assertTrue(consulta)
        self.assertEqual(consulta[0][1][2], PACIENTE_COMPLETO["id"])

    def test_dado_vindo_do_cadastro_completo_nao_quebra(self):
        """Front antigo em cache não manda os campos; paciente completo cria como antes."""
        self.assertEqual(self.chama(cpf=None, birthDate=None, email=None)["statusCode"], 201)


if __name__ == "__main__":
    unittest.main()
