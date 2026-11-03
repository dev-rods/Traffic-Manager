# -*- coding: utf-8 -*-
"""O que mandamos à ClickSign (API v3), com o HTTP mockado.

O que se confere aqui é o contrato: cinco chamadas na ordem certa e no formato
JSON:API, CPF e nascimento no signatário, celular sem o 55, requisitos de
qualificação e de evidência ligados ao documento e ao signatário, ativação
por PATCH, cancelamento quando um passo falha, e leitura dos downloads com os
dois nomes de chave que a documentação usa.
"""
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from src.providers import signature_provider as sp
from src.providers.clicksign_provider import ClicksignProvider, REQUISITOS_DE_EVIDENCIA
from src.providers.signature_provider import (
    ASSINADO, ASSINANDO, CANCELADO, EXPIRADO, AssinaturaIndisponivel, ErroDoProvedor, Signatario,
)

SIGNATARIA = Signatario(nome="Ana Souza", cpf="52998224725", nascimento=date(1990, 5, 1),
                        telefone="5511999990000", email="ana@example.com")
PRAZO = datetime(2026, 11, 5, 12, 0, tzinfo=timezone(timedelta(hours=-3)))


def resposta(status=200, json=None, content=b""):
    r = mock.MagicMock()
    r.status_code = status
    r.content = content or (b"x" if json is not None else b"")
    r.json.return_value = json or {}
    r.text = str(json)
    return r


class Base(unittest.TestCase):
    def setUp(self):
        self.chamadas = []
        self.falha_em = None
        self.status_do_envelope = "running"
        p = mock.patch("src.providers.clicksign_provider.requests.request", side_effect=self.http)
        p.start()
        self.addCleanup(p.stop)
        g = mock.patch("src.providers.clicksign_provider.requests.get", side_effect=self.download)
        g.start()
        self.addCleanup(g.stop)
        self.clicksign = ClicksignProvider("chave", "https://sandbox.clicksign.com/")

    def http(self, metodo, url, headers=None, json=None, timeout=None):
        caminho = url.split("/api/v3", 1)[1]
        self.chamadas.append((metodo, caminho, json))
        self.assertEqual(headers["Authorization"], "chave")
        self.assertEqual(headers["Content-Type"], "application/vnd.api+json")
        if self.falha_em and caminho.endswith(self.falha_em):
            return resposta(422, json={"errors": [{"detail": "recusado"}]})
        if metodo == "POST" and caminho == "/envelopes":
            return resposta(json={"data": {"id": "env-1"}})
        if metodo == "POST" and caminho == "/envelopes/env-1/documents":
            return resposta(json={"data": {"id": "doc-1"}})
        if metodo == "POST" and caminho == "/envelopes/env-1/signers":
            return resposta(json={"data": {"id": "sig-1"}})
        if metodo == "POST" and caminho == "/envelopes/env-1/requirements":
            return resposta(json={"data": {"id": "req-{}".format(len(self.chamadas))}})
        if metodo == "PATCH" and caminho == "/envelopes/env-1":
            return resposta(json={"data": {"id": "env-1"}})
        if metodo == "GET" and caminho == "/envelopes/env-1":
            return resposta(json={"data": {"attributes": {"status": self.status_do_envelope,
                                                           "deadline_at": PRAZO.isoformat()}}})
        if metodo == "GET" and caminho == "/envelopes/env-1/documents/doc-1":
            return resposta(json={"data": {"attributes": {"downloads": self.downloads},
                                           "links": {"files": self.arquivos}}})
        if metodo == "DELETE" and caminho == "/envelopes/env-1":
            if self.envelope_ativo:
                return resposta(403, json={"errors": [{"detail": "envelope não está com status draft"}]})
            return resposta(204, json=None)
        return resposta(json={})

    downloads = {"signed_file_url": "https://s3/assinado.pdf", "ziped_file_url": "https://s3/tudo.zip"}
    arquivos = {}  # type: dict
    envelope_ativo = False

    def download(self, url, timeout=None):
        self.chamadas.append(("DOWNLOAD", url, None))
        return resposta(json=None, content=b"%PDF-" + url.encode())

    def cria(self):
        return self.clicksign.cria_termo("tpl-1", "TCLE.docx", {"nome_completo": "Ana Souza"},
                                         SIGNATARIA, "clinica/appt-1", PRAZO)


class TestCriaTermo(Base):
    def test_cinco_passos_na_ordem_e_ids_devolvidos(self):
        termo = self.cria()
        self.assertEqual(termo, ("env-1", "doc-1", "sig-1"))
        caminhos = [(m, c) for m, c, _ in self.chamadas]
        self.assertEqual(caminhos[:3], [("POST", "/envelopes"), ("POST", "/envelopes/env-1/documents"),
                                        ("POST", "/envelopes/env-1/signers")])
        self.assertEqual(caminhos[-1], ("PATCH", "/envelopes/env-1"))
        requisitos = [j for m, c, j in self.chamadas if c == "/envelopes/env-1/requirements"]
        self.assertEqual(len(requisitos), 1 + len(REQUISITOS_DE_EVIDENCIA))

    def test_envelope_em_portugues_fecha_sozinho_e_com_prazo(self):
        self.cria()
        env = self.chamadas[0][2]["data"]
        self.assertEqual(env["type"], "envelopes")
        self.assertEqual(env["attributes"]["locale"], "pt-BR")
        self.assertTrue(env["attributes"]["auto_close"])
        self.assertEqual(env["attributes"]["deadline_at"], "2026-11-05T12:00:00-03:00")
        # Vencido sem assinatura vira "canceled", para "closed" significar assinado.
        self.assertEqual(env["attributes"]["deadline_partial_signature_action"], "canceled")
        self.assertIn("clinica/appt-1", env["attributes"]["name"])

    def test_documento_vem_do_modelo_com_as_variaveis(self):
        self.cria()
        doc = self.chamadas[1][2]["data"]["attributes"]
        self.assertEqual(doc["template"], {"key": "tpl-1", "data": {"nome_completo": "Ana Souza"}})
        self.assertEqual(doc["filename"], "TCLE.docx")
        self.assertEqual(doc["metadata"]["referencia"], "clinica/appt-1")

    def test_signataria_com_cpf_formatado_nascimento_e_celular_sem_55(self):
        self.cria()
        s = self.chamadas[2][2]["data"]["attributes"]
        self.assertEqual(s["documentation"], "529.982.247-25")
        self.assertEqual(s["birthday"], "1990-05-01")
        self.assertEqual(s["phone_number"], "11999990000")
        self.assertTrue(s["has_documentation"])
        # Convite não (assina no iPad); cópia assinada por e-mail sim.
        self.assertEqual(s["communicate_events"]["signature_request"], "none")
        self.assertEqual(s["communicate_events"]["document_signed"], "email")

    def test_requisitos_ligados_ao_documento_e_a_signataria(self):
        self.cria()
        requisitos = [j["data"] for m, c, j in self.chamadas if c == "/envelopes/env-1/requirements"]
        self.assertEqual(requisitos[0]["attributes"], {"action": "agree", "role": "sign"})
        auths = [r["attributes"]["auth"] for r in requisitos[1:]]
        self.assertEqual(tuple(auths), REQUISITOS_DE_EVIDENCIA)
        for r in requisitos:
            self.assertEqual(r["relationships"]["document"]["data"], {"type": "documents", "id": "doc-1"})
            self.assertEqual(r["relationships"]["signer"]["data"], {"type": "signers", "id": "sig-1"})

    def test_ativa_por_patch_running(self):
        self.cria()
        patch = self.chamadas[-1][2]["data"]
        self.assertEqual(patch["attributes"], {"status": "running"})
        self.assertEqual(patch["id"], "env-1")

    def test_falha_depois_do_envelope_cancela_e_relanca(self):
        self.falha_em = "/signers"
        with self.assertRaises(ErroDoProvedor):
            self.cria()
        # Ainda em draft: a API aceita apagar.
        self.assertEqual([(m, c) for m, c, _ in self.chamadas if m == "DELETE"], [("DELETE", "/envelopes/env-1")])

    def test_falha_no_proprio_envelope_nao_tenta_cancelar(self):
        self.falha_em = "/envelopes"
        with self.assertRaises(ErroDoProvedor):
            self.cria()
        self.assertEqual(len(self.chamadas), 1)


class TestConsultaEDownload(Base):
    def test_status_traduzido(self):
        for deles, nosso in (("running", ASSINANDO), ("closed", ASSINADO), ("canceled", CANCELADO)):
            self.status_do_envelope = deles
            self.assertEqual(self.clicksign.consulta("env-1"), nosso)

    def test_running_com_prazo_vencido_e_expirado(self):
        self.status_do_envelope = "running"
        with mock.patch("src.providers.clicksign_provider.datetime") as dt:
            dt.now.return_value = PRAZO + timedelta(days=1)
            dt.fromisoformat = datetime.fromisoformat
            self.assertEqual(self.clicksign.consulta("env-1"), EXPIRADO)

    def test_baixa_pdf_pela_url_temporaria(self):
        pdf = self.clicksign.baixa_pdf("env-1", "doc-1")
        self.assertEqual(pdf, b"%PDF-https://s3/assinado.pdf")

    def test_baixa_pdf_aceita_o_outro_nome_de_chave(self):
        self.downloads = {"signed": "https://s3/outro.pdf"}
        self.assertEqual(self.clicksign.baixa_pdf("env-1", "doc-1"), b"%PDF-https://s3/outro.pdf")

    def test_baixa_pdf_prefere_links_files_como_o_sandbox_devolve(self):
        self.downloads = {}
        self.arquivos = {"original": "https://s3/original.docx", "signed": "https://s3/links.pdf"}
        self.assertEqual(self.clicksign.baixa_pdf("env-1", "doc-1"), b"%PDF-https://s3/links.pdf")

    def test_sem_pdf_ainda_e_erro_do_provedor(self):
        self.downloads = {}
        with self.assertRaises(ErroDoProvedor):
            self.clicksign.baixa_pdf("env-1", "doc-1")

    def test_zip_opcional(self):
        self.assertEqual(self.clicksign.baixa_zip("env-1", "doc-1"), b"%PDF-https://s3/tudo.zip")
        self.downloads = {"signed_file_url": "https://s3/assinado.pdf"}
        self.assertIsNone(self.clicksign.baixa_zip("env-1", "doc-1"))

    def test_cancelar_envelope_ativo_e_so_log(self):
        self.envelope_ativo = True
        self.clicksign.cancela("env-1")  # 403 "não está em draft": não levanta, vence pelo prazo

    def test_cancelar_sem_resposta_levanta(self):
        import requests as req
        with mock.patch("src.providers.clicksign_provider.requests.request",
                        side_effect=req.RequestException("x")):
            with self.assertRaises(ErroDoProvedor):
                self.clicksign.cancela("env-1")

    def test_simular_nao_existe(self):
        self.assertFalse(self.clicksign.pode_simular)
        with self.assertRaises(ErroDoProvedor):
            self.clicksign.simula("env-1")

    def test_widget_endpoint_sem_api(self):
        self.assertEqual(self.clicksign.widget_endpoint, "https://sandbox.clicksign.com")


class TestProvedorAtivo(unittest.TestCase):
    def test_com_chave_usa_clicksign_na_base_do_stage(self):
        with mock.patch.dict(os.environ, {"CLICKSIGN_API_KEY": "k", "CLICKSIGN_BASE_URL": "https://app.clicksign.com"}):
            p = sp.provedor_ativo()
        self.assertEqual(p.nome, "clicksign")
        self.assertEqual(p.widget_endpoint, "https://app.clicksign.com")
        self.assertFalse(sp.termo_de_teste("clicksign"))

    def test_sem_chave_em_dev_simula(self):
        with mock.patch.dict(os.environ, {"CLICKSIGN_API_KEY": "", "STAGE": "dev"}):
            p = sp.provedor_ativo()
        self.assertEqual(p.nome, "simulado")
        self.assertTrue(p.pode_simular)
        self.assertTrue(sp.termo_de_teste("simulado"))

    def test_sem_chave_fora_de_dev_e_indisponivel(self):
        with mock.patch.dict(os.environ, {"CLICKSIGN_API_KEY": "", "STAGE": "prod"}):
            with self.assertRaises(AssinaturaIndisponivel):
                sp.provedor_ativo()

    def test_sandbox_e_teste(self):
        with mock.patch.dict(os.environ, {"CLICKSIGN_BASE_URL": "https://sandbox.clicksign.com"}):
            self.assertTrue(sp.termo_de_teste("clicksign"))


class TestSimulado(unittest.TestCase):
    def test_fecha_so_pelo_simula_e_pdf_valido(self):
        from src.providers.simulated_signature_provider import SimulatedSignatureProvider
        with mock.patch.dict(os.environ, {"STAGE": "dev"}):
            p = SimulatedSignatureProvider()
        termo = p.cria_termo("tpl", "TCLE.docx", {}, SIGNATARIA, "ref", PRAZO)
        self.assertEqual(p.consulta(termo.envelope_id), ASSINANDO)
        p.simula(termo.envelope_id)
        self.assertEqual(p.consulta(termo.envelope_id), ASSINADO)
        pdf = p.baixa_pdf(termo.envelope_id, termo.document_id)
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"ref", pdf)
        self.assertIsNone(p.baixa_zip(termo.envelope_id, termo.document_id))

    def test_recusa_fora_de_dev(self):
        from src.providers.simulated_signature_provider import SimulatedSignatureProvider
        with mock.patch.dict(os.environ, {"STAGE": "prod"}):
            with self.assertRaises(AssinaturaIndisponivel):
                SimulatedSignatureProvider()


if __name__ == "__main__":
    unittest.main()
