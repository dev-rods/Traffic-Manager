# -*- coding: utf-8 -*-
"""Rotas do termo no painel (PRD 036): permissão por rota, corpo, erros e interface."""
import json
import os
import unittest
from datetime import date
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.functions.consent import router
from src.services import consentimento
from src.utils.acesso import ADMIN, STAFF, Identidade
from src.utils.http import http_response

CLINIC = "clinica-teste-0001"
PAC = "bbbbbbbb-0000-0000-0000-000000000001"
APPT = "aaaaaaaa-0000-0000-0000-000000000001"
TERMO = "dddddddd-0000-0000-0000-000000000001"
MODULO = "src.functions.consent.router"
RECEPCAO = Identidade(papel=STAFF, user_id="u1", clinic_id=CLINIC, nome="Joana")
MESTRE = Identidade(papel=ADMIN, chave_mestra=True)


def evento(metodo, proxy, body=None):
    return {"httpMethod": metodo, "pathParameters": {"clinicId": CLINIC, "proxy": proxy},
            "body": json.dumps(body) if body is not None else None}


class Base(unittest.TestCase):
    def setUp(self):
        p = mock.patch(f"{MODULO}.PostgresService")
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.dict(os.environ, {"TCLE_VERSION": "2026-11"})
        p.start()
        self.addCleanup(p.stop)

    def acesso(self, identidade=RECEPCAO):
        return mock.patch(f"{MODULO}.require_acesso", return_value=(identidade, None))


class TestPermissoes(Base):
    def test_cada_rota_pede_a_permissao_certa(self):
        casos = [
            ("GET", f"patients/{PAC}", "prontuario.ler", "lista_do_paciente", []),
            ("POST", f"patients/{PAC}/paper", "agenda.escrever", "registra_papel", {"signedAt": "2026-11-01"}),
            ("POST", f"appointments/{APPT}/waive", "agenda.escrever", "dispensa", {"reason": "RECUSOU"}),
            ("GET", f"{TERMO}/pdf-url", "prontuario.ler", "url_do_pdf", {"url": "u", "expiresInSeconds": 300}),
            ("GET", f"{TERMO}/zip-url", "prontuario.ler", "url_do_zip", {"url": "u", "expiresInSeconds": 300}),
        ]
        for metodo, proxy, permissao, funcao, retorno in casos:
            with self.subTest(proxy):
                with mock.patch(f"{MODULO}.require_acesso", return_value=(RECEPCAO, None)) as acesso, \
                        mock.patch(f"src.services.consentimento.{funcao}", return_value=retorno):
                    r = router.handler(evento(metodo, proxy, {} if metodo == "POST" else None), None)
                self.assertIn(r["statusCode"], (200, 201, 400), r["body"])
                self.assertEqual(acesso.call_args[0][1], permissao)

    def test_barrado_devolve_a_resposta_do_acesso(self):
        with mock.patch(f"{MODULO}.require_acesso", return_value=(None, http_response(403, {"x": 1}))):
            r = router.handler(evento("GET", f"patients/{PAC}"), None)
        self.assertEqual(r["statusCode"], 403)


class TestRotas(Base):
    def test_lista_traz_versao_e_se_esta_ligado(self):
        with self.acesso(), mock.patch("src.services.consentimento.lista_do_paciente", return_value=[{"id": TERMO}]):
            r = router.handler(evento("GET", f"patients/{PAC}"), None)
        corpo = json.loads(r["body"])
        self.assertEqual(corpo["consents"], [{"id": TERMO}])
        self.assertTrue(corpo["consent_enabled"])
        self.assertEqual(corpo["term_version"], "2026-11")

    def test_papel_passa_data_e_autor(self):
        with self.acesso(), mock.patch("src.services.consentimento.registra_papel", return_value={"id": TERMO}) as papel:
            r = router.handler(evento("POST", f"patients/{PAC}/paper", {"signedAt": "2026-11-01"}), None)
        self.assertEqual(r["statusCode"], 201)
        self.assertEqual(papel.call_args[0][2:], (PAC, date(2026, 11, 1), "Joana"))

    def test_papel_com_data_ruim_e_400(self):
        with self.acesso():
            r = router.handler(evento("POST", f"patients/{PAC}/paper", {"signedAt": "01/11/2026"}), None)
        self.assertEqual(r["statusCode"], 400)

    def test_dispensa_passa_motivo_nota_e_autor_admin(self):
        with self.acesso(MESTRE), mock.patch("src.services.consentimento.dispensa", return_value={"id": APPT}) as disp:
            r = router.handler(evento("POST", f"appointments/{APPT}/waive", {"reason": "OUTRO", "note": "sem óculos"}), None)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(disp.call_args[0][2:], (APPT, "OUTRO", "sem óculos", "admin"))

    def test_motivo_invalido_e_400(self):
        with self.acesso(), mock.patch("src.services.consentimento.dispensa",
                                       side_effect=consentimento.ConsentimentoInvalido("Motivo inválido")):
            r = router.handler(evento("POST", f"appointments/{APPT}/waive", {"reason": "X"}), None)
        self.assertEqual(r["statusCode"], 400)
        self.assertIn("Motivo", json.loads(r["body"])["message"])

    def test_corpo_invalido_e_400(self):
        with self.acesso():
            ev = evento("POST", f"appointments/{APPT}/waive")
            ev["body"] = "{nao"
            self.assertEqual(router.handler(ev, None)["statusCode"], 400)

    def test_sem_pdf_e_404(self):
        with self.acesso(), mock.patch("src.services.consentimento.url_do_pdf", side_effect=consentimento.NaoEncontrado()):
            self.assertEqual(router.handler(evento("GET", f"{TERMO}/pdf-url"), None)["statusCode"], 404)

    def test_rota_desconhecida(self):
        self.assertEqual(router.handler(evento("GET", "qualquer"), None)["statusCode"], 404)
        self.assertEqual(router.handler(evento("DELETE", f"patients/{PAC}"), None)["statusCode"], 404)


class TestInterface(unittest.TestCase):
    def test_yml_coringa_e_s3(self):
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(raiz, "sls", "functions", "consent", "interface.yml"), encoding="utf-8") as f:
            yml = f.read()
        self.assertIn("src.functions.consent.router.handler", yml)
        self.assertIn("path: clinics/{clinicId}/consents/{proxy+}", yml)
        self.assertIn("s3:GetObject", yml)
        with open(os.path.join(raiz, "sls", "functions", "professional", "interface.yml"), encoding="utf-8") as f:
            prof = f.read()
        self.assertIn("src.functions.professional.update.handler", prof)
        self.assertIn("path: clinics/{clinicId}/professionals/{professionalId}", prof)


class TestUpdateProfessional(unittest.TestCase):
    def test_atualiza_so_campos_permitidos_desta_clinica(self):
        from src.functions.professional import update
        db = mock.Mock()
        db.execute_write_returning.return_value = {"id": "p1", "registro_conselho": "CRBM 1", "name": "Lia"}
        ev = {"httpMethod": "PUT", "pathParameters": {"clinicId": CLINIC, "professionalId": "p1"},
              "body": json.dumps({"registro_conselho": " CRBM 1 ", "clinic_id": "outra", "name": "Lia"})}
        with mock.patch("src.functions.professional.update.require_api_key", return_value=("k", None)), \
                mock.patch("src.functions.professional.update.PostgresService", return_value=db):
            r = update.handler(ev, None)
        self.assertEqual(r["statusCode"], 200)
        sql, params = db.execute_write_returning.call_args[0]
        self.assertIn("name = %s", sql)
        self.assertIn("registro_conselho = %s", sql)
        self.assertNotIn("clinic_id = %s,", sql)
        self.assertEqual(params, ("Lia", "CRBM 1", "p1", CLINIC))

    def test_nao_encontrado_e_404(self):
        from src.functions.professional import update
        db = mock.Mock()
        db.execute_write_returning.return_value = None
        ev = {"httpMethod": "PUT", "pathParameters": {"clinicId": CLINIC, "professionalId": "p1"},
              "body": json.dumps({"active": False})}
        with mock.patch("src.functions.professional.update.require_api_key", return_value=("k", None)), \
                mock.patch("src.functions.professional.update.PostgresService", return_value=db):
            self.assertEqual(update.handler(ev, None)["statusCode"], 404)


class TestUpdateClinic(unittest.TestCase):
    def _chama(self, body, ativa):
        from src.functions.clinic import update
        db = mock.Mock()
        db.execute_query.return_value = [{"x": 1}] if ativa else []
        db.execute_write_returning.return_value = {"clinic_id": CLINIC, **body}
        ev = {"httpMethod": "PUT", "pathParameters": {"clinicId": CLINIC}, "body": json.dumps(body)}
        with mock.patch("src.functions.clinic.update.require_api_key", return_value=("k", None)), \
                mock.patch("src.functions.clinic.update.PostgresService", return_value=db):
            return update.handler(ev, None), db

    def test_responsavel_tem_de_ser_profissional_ativa_da_clinica(self):
        r, _ = self._chama({"responsible_professional_id": "cccccccc-0000-0000-0000-000000000001"}, ativa=False)
        self.assertEqual(r["statusCode"], 400)
        r, db = self._chama({"responsible_professional_id": "cccccccc-0000-0000-0000-000000000001"}, ativa=True)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(db.execute_query.call_args[0][1][1], CLINIC)

    def test_responsavel_nula_e_cidade_aparada(self):
        r, db = self._chama({"responsible_professional_id": None, "cidade": "  São  Paulo  "}, ativa=False)
        self.assertEqual(r["statusCode"], 200)
        sql, params = db.execute_write_returning.call_args[0]
        self.assertIn("São Paulo", params)
        self.assertIn(None, params)


if __name__ == "__main__":
    unittest.main()
