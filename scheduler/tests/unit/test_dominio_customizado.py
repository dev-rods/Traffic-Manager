# -*- coding: utf-8 -*-
"""Domínio customizado do booking-site (ver docs/work/prd — "Ponto 4").

Três peças, testadas separadas:
- VercelDomainService: fala com a API da Vercel, sem CloudFormation novo.
- UpdateClinic: troca o domínio no banco e reflete na Vercel - nunca ao
  contrário, porque se a Vercel falhar o dado já teria sido persistido.
- resolve_domain: a única rota pública nova - traduz hostname -> clinic_id
  pro booking-site descobrir quem é antes de montar a tela.
"""
import json
import os
import unittest
from unittest import mock


class TestVercelDomainService(unittest.TestCase):
    def _service(self):
        with mock.patch.dict(os.environ, {
            "VERCEL_API_TOKEN": "tok",
            "VERCEL_TEAM_ID": "team_x",
            "BOOKING_SITE_VERCEL_PROJECT_ID": "prj_x",
        }):
            from src.services.vercel_domain_service import VercelDomainService
            return VercelDomainService()

    def test_sem_token_nao_esta_configurado(self):
        with mock.patch.dict(os.environ, {"VERCEL_API_TOKEN": ""}):
            from src.services.vercel_domain_service import VercelDomainService
            self.assertFalse(VercelDomainService().configured)

    def test_add_domain_idempotente_quando_ja_e_deste_projeto(self):
        """domain_already_in_use não é erro se o dono já é ESTE projeto -
        é o estado que a segunda chamada (editar sem trocar) sempre bate."""
        service = self._service()
        resposta_conflito = mock.MagicMock(status_code=409)
        resposta_conflito.json.return_value = {"error": {"code": "domain_already_in_use"}}
        resposta_conflito.content = b"{}"

        with mock.patch("src.services.vercel_domain_service.requests.post", return_value=resposta_conflito), \
             mock.patch.object(service, "get_domain", return_value={"projectId": "prj_x", "name": "a.com"}):
            resultado = service.add_domain("a.com")

        self.assertEqual(resultado["projectId"], "prj_x")

    def test_add_domain_falha_quando_e_de_outro_dono(self):
        service = self._service()
        resposta_conflito = mock.MagicMock(status_code=409)
        resposta_conflito.json.return_value = {"error": {"code": "domain_already_in_use"}}
        resposta_conflito.content = b"{}"

        from src.services.vercel_domain_service import VercelDomainError

        with mock.patch("src.services.vercel_domain_service.requests.post", return_value=resposta_conflito), \
             mock.patch.object(service, "get_domain", return_value={"projectId": "outro_prj", "name": "a.com"}):
            with self.assertRaises(VercelDomainError):
                service.add_domain("a.com")

    def test_status_verificado_apex_sugere_registro_a(self):
        service = self._service()
        with mock.patch.object(service, "get_domain", return_value={"verified": True}):
            status = service.get_domain_status("suaempresa.com")

        self.assertTrue(status["verified"])
        self.assertEqual(status["dns_records"], [{"type": "A", "name": "@", "value": "76.76.21.21"}])

    def test_status_verificado_subdominio_sugere_cname(self):
        service = self._service()
        with mock.patch.object(service, "get_domain", return_value={"verified": True}):
            status = service.get_domain_status("agendar.suaempresa.com")

        self.assertEqual(
            status["dns_records"],
            [{"type": "CNAME", "name": "agendar", "value": "cname.vercel-dns.com"}],
        )

    def test_status_nao_verificado_devolve_o_desafio_da_vercel(self):
        service = self._service()
        info = {
            "verified": False,
            "verification": [{"type": "TXT", "domain": "_vercel.a.com", "value": "vc-domain-verify=..."}],
        }
        with mock.patch.object(service, "get_domain", return_value=info):
            status = service.get_domain_status("a.com")

        self.assertFalse(status["verified"])
        self.assertEqual(status["dns_records"][0]["type"], "TXT")

    def test_status_dominio_nao_registrado(self):
        service = self._service()
        with mock.patch.object(service, "get_domain", return_value=None):
            status = service.get_domain_status("a.com")

        self.assertEqual(status, {"registered": False, "verified": False, "dns_records": []})


class TestUpdateClinicSincronizaDominio(unittest.TestCase):
    def _chama(self, body, linha_existente):
        from src.functions.clinic import update as modulo

        evento = {
            "pathParameters": {"clinicId": "clinica-x"},
            "headers": {"x-api-key": "k"},
            "body": json.dumps(body),
        }

        db = mock.MagicMock()
        db.execute_query.return_value = [linha_existente] if linha_existente is not None else []
        db.execute_write_returning.return_value = {
            "clinic_id": "clinica-x", "custom_domain": body.get("custom_domain"),
        }

        vercel = mock.MagicMock()
        vercel.configured = True

        with mock.patch.object(modulo, "require_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "PostgresService", return_value=db), \
             mock.patch.object(modulo, "VercelDomainService", return_value=vercel):
            resposta = modulo.handler(evento, None)

        return resposta, vercel

    def test_domain_novo_registra_na_vercel(self):
        resposta, vercel = self._chama({"custom_domain": "agendar.a.com"}, {"custom_domain": None})

        vercel.add_domain.assert_called_once_with("agendar.a.com")
        vercel.remove_domain.assert_not_called()
        self.assertNotIn("domainWarning", json.loads(resposta["body"]))

    def test_troca_de_domain_remove_o_antigo_e_adiciona_o_novo(self):
        resposta, vercel = self._chama(
            {"custom_domain": "novo.a.com"}, {"custom_domain": "antigo.a.com"}
        )

        vercel.remove_domain.assert_called_once_with("antigo.a.com")
        vercel.add_domain.assert_called_once_with("novo.a.com")

    def test_limpar_o_domain_so_remove(self):
        resposta, vercel = self._chama({"custom_domain": None}, {"custom_domain": "antigo.a.com"})

        vercel.remove_domain.assert_called_once_with("antigo.a.com")
        vercel.add_domain.assert_not_called()

    def test_falha_na_vercel_nao_derruba_a_resposta_so_avisa(self):
        from src.functions.clinic import update as modulo
        from src.services.vercel_domain_service import VercelDomainError

        evento = {
            "pathParameters": {"clinicId": "clinica-x"},
            "headers": {"x-api-key": "k"},
            "body": json.dumps({"custom_domain": "a.com"}),
        }
        db = mock.MagicMock()
        db.execute_query.return_value = [{"custom_domain": None}]
        db.execute_write_returning.return_value = {"clinic_id": "clinica-x", "custom_domain": "a.com"}

        vercel = mock.MagicMock()
        vercel.configured = True
        vercel.add_domain.side_effect = VercelDomainError("domínio já em uso por outra conta")

        with mock.patch.object(modulo, "require_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "PostgresService", return_value=db), \
             mock.patch.object(modulo, "VercelDomainService", return_value=vercel):
            resposta = modulo.handler(evento, None)

        corpo = json.loads(resposta["body"])
        self.assertEqual(resposta["statusCode"], 200)
        self.assertIn("domínio já em uso", corpo["domainWarning"])

    def test_sem_mudar_custom_domain_nao_toca_na_vercel(self):
        resposta, vercel = self._chama({"name": "Novo nome"}, {"custom_domain": "x.com"})

        vercel.add_domain.assert_not_called()
        vercel.remove_domain.assert_not_called()


class TestResolveDomain(unittest.TestCase):
    def _chama(self, host, linhas):
        from src.functions.public_booking import resolve_domain as modulo

        evento = {
            "queryStringParameters": {"host": host},
            "headers": {"x-api-key": "k"},
        }
        with mock.patch.object(modulo, "require_booking_intake_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "db_lookup", return_value=linhas):
            return modulo.handler(evento, None)

    def test_resolve_pelo_hostname(self):
        resposta = self._chama("agendar.a.com", [{"clinic_id": "clinica-x"}])
        corpo = json.loads(resposta["body"])

        self.assertEqual(resposta["statusCode"], 200)
        self.assertEqual(corpo["clinicId"], "clinica-x")

    def test_ignora_porta_no_host(self):
        """O browser manda host:porta em dev (localhost:5174) - o registro
        salvo nunca tem porta, então ela tem que cair antes do lookup."""
        from src.functions.public_booking import resolve_domain as modulo

        evento = {"queryStringParameters": {"host": "agendar.a.com:443"}, "headers": {"x-api-key": "k"}}
        with mock.patch.object(modulo, "require_booking_intake_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "db_lookup", return_value=[{"clinic_id": "clinica-x"}]) as lookup:
            modulo.handler(evento, None)

        lookup.assert_called_once_with("agendar.a.com")

    def test_domain_desconhecido_e_404(self):
        resposta = self._chama("naoexiste.com", [])
        self.assertEqual(resposta["statusCode"], 404)

    def test_sem_host_e_400(self):
        from src.functions.public_booking import resolve_domain as modulo

        evento = {"queryStringParameters": {}, "headers": {"x-api-key": "k"}}
        with mock.patch.object(modulo, "require_booking_intake_api_key", return_value=("k", None)):
            resposta = modulo.handler(evento, None)

        self.assertEqual(resposta["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
