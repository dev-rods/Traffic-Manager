# -*- coding: utf-8 -*-
"""Termo de consentimento assinado no check-in (PRD 036).

O banco abaixo guarda clínica, profissionais, pacientes, responsáveis,
agendamentos, termos e eventos em memória e responde às consultas do
`consentimento` pelo conteúdo do SQL. Os dois índices parciais da tabela de
termos (um SIGNING por paciente, um SIGNED/PAPER por versão) são aplicados
no `INSERT`, porque é deles que a corrida de dois toques depende.
"""
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

import psycopg2

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.providers.signature_provider import (
    ASSINADO, ASSINANDO, CANCELADO, EXPIRADO, ErroDoProvedor, SignatureProvider, TermoCriado,
)
from src.services import anamnese, consentimento

CLINIC = "clinica-teste-0001"
FONE = "5511999990000"
OUTRO_FONE = "5511988887777"
CPF_OK = "52998224725"
CPF_RESP = "11144477735"
PAC = "bbbbbbbb-0000-0000-0000-000000000001"
APPT = "aaaaaaaa-0000-0000-0000-000000000001"
APPT_MENOR = "aaaaaaaa-0000-0000-0000-000000000002"
PAC_MENOR = "bbbbbbbb-0000-0000-0000-000000000002"
PROF = "cccccccc-0000-0000-0000-000000000001"
AGORA = datetime(2026, 11, 4, 9, 45, tzinfo=timezone.utc)

DADOS = {"fullName": "Ana Souza", "cpf": CPF_OK, "birthDate": "1990-05-10",
         "email": "ana@exemplo.com", "imageAuthorized": True, "guardian": None}
RESPONSAVEL = {"name": "Carla Souza", "cpf": CPF_RESP, "birthDate": "1980-01-01",
               "phone": "11988887777", "email": "carla@exemplo.com"}


class Provedor(SignatureProvider):
    nome = "clicksign"
    pode_simular = False
    widget_endpoint = "https://sandbox.clicksign.com"

    def __init__(self):
        self.criados = []
        self.cancelados = []
        self.status_remoto = {}
        self.pdf = b"%PDF-teste"
        self.zip = None
        self.falha_download = False

    def cria_termo(self, template_key, filename, dados, signatario, referencia, prazo):
        n = len(self.criados) + 1
        self.criados.append((template_key, filename, dados, signatario, referencia, prazo))
        return TermoCriado("env-%d" % n, "doc-%d" % n, "signer-%d" % n)

    def consulta(self, envelope_id):
        return self.status_remoto.get(envelope_id, ASSINANDO)

    def baixa_pdf(self, envelope_id, document_id):
        if self.falha_download:
            raise ErroDoProvedor("ainda sem PDF")
        return self.pdf

    def baixa_zip(self, envelope_id, document_id):
        return self.zip

    def cancela(self, envelope_id):
        self.cancelados.append(envelope_id)


class Simulado(Provedor):
    nome = "simulado"
    pode_simular = True
    widget_endpoint = ""

    def simula(self, envelope_id):
        self.status_remoto[envelope_id] = ASSINADO


class Db:
    def __init__(self):
        self.clinica = {"clinic_id": CLINIC, "name": "Clinica X", "display_name": "Essência",
                        "cidade": "São Paulo", "timezone": "America/Sao_Paulo",
                        "responsible_professional_id": PROF}
        self.profissionais = {PROF: {"id": PROF, "clinic_id": CLINIC, "name": "Dra. Lia", "role": "Biomédica",
                                     "registro_conselho": "CRBM 1234", "active": True}}
        self.pacientes = {
            PAC: {"id": PAC, "phone": FONE, "name": "Ana", "cpf": None, "birth_date": None, "email": None},
            PAC_MENOR: {"id": PAC_MENOR, "phone": FONE, "name": "Bia Souza", "cpf": None,
                        "birth_date": date(2010, 6, 1), "email": None},
        }
        self.responsaveis = {}
        self.agendamentos = {
            APPT: {"id": APPT, "clinic_id": CLINIC, "patient_id": PAC, "status": "CONFIRMED",
                   "appointment_date": date(2026, 11, 4), "full_name": "Ana Souza", "consent_waived_at": None},
            APPT_MENOR: {"id": APPT_MENOR, "clinic_id": CLINIC, "patient_id": PAC_MENOR, "status": "CONFIRMED",
                         "appointment_date": date(2026, 11, 5), "full_name": "Bia Souza",
                         "consent_waived_at": None},
        }
        self.termos = {}
        self.eventos = {}
        self.escritas = []

    def _do_fone(self, fones):
        return [p["id"] for p in self.pacientes.values() if p["phone"] in fones]

    def execute_query(self, sql, params=None):
        if "patient_cpf" in sql and "FROM scheduler.appointments a" in sql:
            appt_id, clinic, fones = params
            a = self.agendamentos.get(appt_id)
            if not a or a["clinic_id"] != clinic or a["patient_id"] not in self._do_fone(fones):
                return []
            p = self.pacientes[a["patient_id"]]
            return [dict(a, patient_uuid=p["id"], patient_name=p["name"], patient_cpf=p["cpf"])]
        if "FROM scheduler.patients p" in sql and "patient_guardians g" in sql:
            p = self.pacientes.get(params[0])
            if not p:
                return []
            g = self.responsaveis.get(params[0]) or {}
            return [dict(p, guardian_name=g.get("name"), guardian_cpf=g.get("cpf"),
                         guardian_birth_date=g.get("birth_date"), guardian_phone=g.get("phone"),
                         guardian_email=g.get("email"))]
        if "FROM scheduler.clinics c" in sql:
            prof = self.profissionais.get(self.clinica.get("responsible_professional_id")) or {}
            if not prof.get("active"):
                prof = {}
            return [dict(self.clinica, profissional_nome=prof.get("name"), profissional_titulo=prof.get("role"),
                         profissional_registro=prof.get("registro_conselho"))]
        if "status IN ('SIGNED', 'PAPER') ORDER BY" in sql:
            clinic, pac, versao = params
            return [dict(t) for t in self.termos.values()
                    if t["clinic_id"] == clinic and t["patient_id"] == pac and t["term_version"] == versao
                    and t["status"] in ("SIGNED", "PAPER")]
        if "status IN ('FILLING', 'SIGNING') LIMIT 1" in sql:
            clinic, pac = params
            return [dict(t) for t in self.termos.values()
                    if t["clinic_id"] == clinic and t["patient_id"] == pac and t["status"] in ("FILLING", "SIGNING")]
        if "SELECT pc.* FROM scheduler.patient_consents pc" in sql:
            cid, clinic, fones = params
            t = self.termos.get(cid)
            if not t or t["clinic_id"] != clinic or t["patient_id"] not in self._do_fone(fones):
                return []
            return [dict(t)]
        if "FROM scheduler.patient_consents WHERE id = %s::uuid AND clinic_id" in sql:
            t = self.termos.get(params[0])
            return [dict(t)] if t and t["clinic_id"] == params[1] else []
        if "FROM scheduler.patient_consents WHERE id = %s::uuid" in sql:
            t = self.termos.get(params[0])
            return [dict(t)] if t else []
        if "provider_document_id = %s" in sql:
            return [dict(t) for t in self.termos.values()
                    if t["provider"] == params[0] and t["provider_document_id"] == params[1]]
        if "provider_envelope_id = %s" in sql:
            return [dict(t) for t in self.termos.values()
                    if t["provider"] == params[0] and t["provider_envelope_id"] == params[1]]
        if "consent_webhook_events WHERE event_id" in sql:
            return [{"x": 1}] if params[0] in self.eventos else []
        if "(provider IS NOT NULL OR status = 'PAPER') ORDER BY created_at DESC" in sql:
            return [dict(t) for t in self.termos.values()
                    if t["clinic_id"] == params[0] and t["patient_id"] == params[1]
                    and (t.get("provider") or t["status"] == "PAPER")]
        raise AssertionError("consulta inesperada: " + sql)

    def execute_write(self, sql, params=None):
        self.escritas.append(sql)
        if "UPDATE scheduler.patient_consents SET status" in sql:
            t = self.termos[params[1]]
            if t["status"] in ("FILLING", "SIGNING"):
                t["status"] = params[0]
            return 1
        if "SET answers = %s" in sql:
            answers, cid = params[0], params[-1]
            t = self.termos[cid]
            if t["status"] == "FILLING":
                t["answers"] = answers.adapted
            return 1
        if "INSERT INTO scheduler.patient_consents" in sql and "'FILLING'" in sql:
            clinic, pac, appt, versao, answers = params
            if any(t["patient_id"] == pac and t["clinic_id"] == clinic and t["status"] in ("FILLING", "SIGNING")
                   for t in self.termos.values()):
                raise psycopg2.IntegrityError("uq_patient_consents_em_andamento")
            cid = "ffffffff-0000-0000-0000-%012d" % (len(self.termos) + 1)
            self.termos[cid] = {"id": cid, "clinic_id": clinic, "patient_id": pac, "appointment_id": appt,
                                "term_version": versao, "status": "FILLING", "signer_kind": "PATIENT",
                                "answers": answers.adapted, "provider": None, "provider_envelope_id": None,
                                "provider_document_id": None, "provider_signer_id": None, "signer_name": None,
                                "image_authorized": None, "pdf_s3_key": None, "audit_s3_key": None,
                                "signed_at": None, "paper_signed_at": None, "paper_registered_by": None,
                                "created_at": AGORA}
            return 1
        if "UPDATE scheduler.patients SET" in sql:
            p = self.pacientes[params[-1]]
            for parte, valor in zip([c.strip() for c in sql.split("SET")[1].split("WHERE")[0].split(",")], params):
                campo = parte.split(" = ")[0]
                if campo in ("name", "cpf", "birth_date", "email"):
                    p[campo] = valor
            return 1
        if "UPDATE scheduler.appointments SET full_name" in sql:
            self.agendamentos[params[1]]["full_name"] = params[0]
            return 1
        if "INSERT INTO scheduler.patient_guardians" in sql:
            pid, nome, cpf, nasc, fone, email = params
            self.responsaveis[pid] = {"name": nome, "cpf": cpf, "birth_date": nasc, "phone": fone, "email": email}
            return 1
        if "INSERT INTO scheduler.consent_webhook_events" in sql:
            self.eventos[params[0]] = params
            return 1
        raise AssertionError("escrita inesperada: " + sql)

    def execute_write_returning(self, sql, params=None):
        self.escritas.append(sql)
        if "INSERT INTO scheduler.patient_consents" in sql and "'SIGNING'" in sql:
            (cid, clinic, pac, appt, versao, kind, nome, cpf, nasc, fone, email, snap, img, resp,
             prov, env, doc, signer, answers) = params
            if any(t["patient_id"] == pac and t["clinic_id"] == clinic and t["status"] in ("FILLING", "SIGNING")
                   for t in self.termos.values()):
                raise psycopg2.IntegrityError("uq_patient_consents_em_andamento")
            row = {"id": cid, "clinic_id": clinic, "patient_id": pac, "appointment_id": appt,
                   "term_version": versao, "status": "SIGNING", "signer_kind": kind, "signer_name": nome,
                   "signer_cpf": cpf, "signer_birth_date": nasc, "signer_phone": fone, "signer_email": email,
                   "patient_snapshot": snap.adapted, "image_authorized": img, "responsible_snapshot": resp.adapted,
                   "provider": prov, "provider_envelope_id": env, "provider_document_id": doc,
                   "provider_signer_id": signer, "pdf_s3_key": None, "pdf_sha256": None, "audit_s3_key": None,
                   "signed_at": None, "paper_signed_at": None, "paper_registered_by": None,
                   "answers": answers.adapted, "created_at": AGORA}
            self.termos[cid] = row
            return dict(row)
        if "SET status = 'REVOKED'" in sql:
            autor, cid, clinic = params
            t = self.termos.get(cid)
            if not t or t["clinic_id"] != clinic or t["status"] not in ("SIGNED", "PAPER"):
                return None
            t.update(status="REVOKED", revoked_at=AGORA, revoked_by=autor)
            return dict(t)
        if "INSERT INTO scheduler.patient_consents" in sql and "'PAPER'" in sql:
            clinic, pac, versao, data, autor = params
            if any(t["patient_id"] == pac and t["clinic_id"] == clinic and t["term_version"] == versao
                   and t["status"] in ("SIGNED", "PAPER") for t in self.termos.values()):
                raise psycopg2.IntegrityError("uq_patient_consents_vigente")
            cid = "dddddddd-0000-0000-0000-%012d" % (len(self.termos) + 1)
            row = {"id": cid, "clinic_id": clinic, "patient_id": pac, "appointment_id": None,
                   "term_version": versao, "status": "PAPER", "signer_kind": "PATIENT", "signer_name": None,
                   "provider": None, "pdf_s3_key": None, "audit_s3_key": None, "signed_at": None,
                   "paper_signed_at": data, "paper_registered_by": autor, "created_at": AGORA,
                   "image_authorized": None}
            self.termos[cid] = row
            return dict(row)
        if "SET status = 'SIGNED'" in sql:
            pdf, sha, zipk, cid = params
            t = self.termos[cid]
            if t["status"] != "SIGNING":
                return None
            t.update(status="SIGNED", signed_at=AGORA, pdf_s3_key=pdf, pdf_sha256=sha, audit_s3_key=zipk)
            return dict(t)
        if "SET consent_waived_at = NOW()" in sql:
            autor, motivo, nota, appt, clinic = params
            a = self.agendamentos.get(appt)
            if not a or a["clinic_id"] != clinic or a["status"] != "CONFIRMED":
                return None
            a.update(consent_waived_at=AGORA, consent_waived_by=autor, consent_waived_reason=motivo,
                     consent_waived_note=nota)
            return {"id": appt, "consent_waived_at": AGORA, "consent_waived_by": autor,
                    "consent_waived_reason": motivo, "consent_waived_note": nota}
        raise AssertionError("escrita inesperada: " + sql)


class Base(unittest.TestCase):
    def setUp(self):
        self.db = Db()
        self.prov = Provedor()
        self.gravados = {}
        for alvo, valor in (("TCLE_VERSION", "2026-11"), ("CLICKSIGN_TCLE_TEMPLATE_KEY", "tpl-1"),
                            ("CLICKSIGN_BASE_URL", "https://sandbox.clicksign.com")):
            p = mock.patch.dict(os.environ, {alvo: valor})
            p.start()
            self.addCleanup(p.stop)
        for alvo in ("src.services.relogio.agora_na_clinica",):
            p = mock.patch(alvo, return_value=AGORA)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch("src.services.documentos_s3.grava", side_effect=self._grava)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch("src.services.documentos_s3.url_assinada", side_effect=lambda k, **kw: "https://s3/" + k)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch("src.services.consentimento._agora", side_effect=lambda tz=None: AGORA)
        p.start()
        self.addCleanup(p.stop)

    def _grava(self, chave, conteudo, content_type="application/pdf"):
        self.gravados[chave] = conteudo
        return "sha-" + str(len(conteudo))

    def responde(self, appt=APPT, **over):
        """As quatro telas da ficha, tudo "Não" salvo o que vier em `over`."""
        r = {p.chave: False for p in anamnese.PERGUNTAS if p.tipo == anamnese.SIM_NAO}
        r.update(queixa_principal="Pelos encravados", fototipo="III")
        r.update(over)
        saida = None
        for tela in anamnese.TELAS:
            chaves = [p.chave for p in anamnese.PERGUNTAS if p.tela == tela]
            saida = consentimento.guarda_respostas(self.db, self.prov, CLINIC, FONE, appt, tela,
                                                   {k: v for k, v in r.items() if k in chaves})
        return saida["anamnesis"]

    def inicia(self, appt=APPT, dados=None, responde=True):
        if responde and not any(t["patient_id"] == self.db.agendamentos[appt]["patient_id"]
                                and t["status"] in ("FILLING", "SIGNING") for t in self.db.termos.values()):
            try:
                self.responde(appt)
            except consentimento.ConsentimentoInvalido:
                pass  # não precisa assinar: o `inicia` de verdade responde NOT_REQUIRED
        return consentimento.inicia(self.db, self.prov, CLINIC, FONE, appt, dados or DADOS)["consent"]


class TestGatilho(Base):
    def test_sem_termo_pede(self):
        self.assertTrue(consentimento.precisa_assinar(self.db, CLINIC, self.db.agendamentos[APPT]))

    def test_signed_da_versao_vigente_nao_pede(self):
        cid = self.inicia()["id"]
        self.prov.status_remoto["env-1"] = ASSINADO
        consentimento.status(self.db, self.prov, CLINIC, FONE, cid)
        self.assertFalse(consentimento.precisa_assinar(self.db, CLINIC, self.db.agendamentos[APPT]))

    def test_signed_de_versao_antiga_pede(self):
        cid = self.inicia()["id"]
        self.prov.status_remoto["env-1"] = ASSINADO
        consentimento.status(self.db, self.prov, CLINIC, FONE, cid)
        with mock.patch.dict(os.environ, {"TCLE_VERSION": "2027-01"}):
            self.assertTrue(consentimento.precisa_assinar(self.db, CLINIC, self.db.agendamentos[APPT]))

    def test_papel_vigente_nao_pede(self):
        consentimento.registra_papel(self.db, CLINIC, PAC, date(2026, 11, 1), "Recepção")
        self.assertFalse(consentimento.precisa_assinar(self.db, CLINIC, self.db.agendamentos[APPT]))

    def test_dispensa_vale_so_nesta_sessao(self):
        consentimento.dispensa(self.db, CLINIC, APPT, "SEM_CELULAR", None, "Recepção")
        self.assertFalse(consentimento.precisa_assinar(self.db, CLINIC, self.db.agendamentos[APPT]))
        proxima = dict(self.db.agendamentos[APPT], id="x", consent_waived_at=None)
        self.assertTrue(consentimento.precisa_assinar(self.db, CLINIC, proxima))

    def test_sem_versao_configurada_nunca_pede(self):
        with mock.patch.dict(os.environ, {"TCLE_VERSION": ""}):
            self.assertFalse(consentimento.precisa_assinar(self.db, CLINIC, self.db.agendamentos[APPT]))
            r = consentimento.resumo_para_o_ipad(self.db, CLINIC, self.db.agendamentos[APPT])
        self.assertEqual(r, {"consentRequired": False, "consentPrefill": None})

    def test_resumo_traz_prefill_mascarado_e_clinica_pronta(self):
        self.db.pacientes[PAC].update(cpf="529.982.247-25", birth_date=date(1990, 5, 10), email="a@b.co")
        r = consentimento.resumo_para_o_ipad(self.db, CLINIC, self.db.agendamentos[APPT])
        self.assertTrue(r["consentRequired"])
        pre = r["consentPrefill"]
        self.assertEqual(pre["cpfMasked"], "***.***.***-25")
        self.assertTrue(pre["cpfKnown"])
        self.assertEqual(pre["birthDate"], "1990-05-10")
        self.assertFalse(pre["isMinor"])
        self.assertTrue(pre["clinicReady"])
        self.assertIsNone(pre["guardian"])

    def test_resumo_marca_menor_e_clinica_sem_responsavel(self):
        self.db.clinica["responsible_professional_id"] = None
        r = consentimento.resumo_para_o_ipad(self.db, CLINIC, self.db.agendamentos[APPT_MENOR])
        self.assertTrue(r["consentPrefill"]["isMinor"])
        self.assertFalse(r["consentPrefill"]["clinicReady"])


class TestInicia(Base):
    def test_cria_envelope_com_as_variaveis_do_modelo(self):
        c = self.inicia()
        self.assertEqual(c["status"], ASSINANDO)
        self.assertEqual(c["signerId"], "signer-1")
        self.assertEqual(c["widgetEndpoint"], "https://sandbox.clicksign.com")
        self.assertTrue(c["test"])
        self.assertFalse(c["canSimulate"])
        template, filename, dados, signatario, referencia, prazo = self.prov.criados[0]
        self.assertEqual(template, "tpl-1")
        self.assertEqual(filename, "TCLE-2026-11-bbbbbbbb.docx")
        self.assertEqual(referencia, CLINIC + "/" + APPT)
        self.assertEqual(prazo, AGORA + timedelta(days=2))
        self.assertEqual(dados["nome_completo"], "Ana Souza")
        self.assertEqual(dados["cpf"], "529.982.247-25")
        self.assertEqual(dados["data_nascimento"], "10/05/1990")
        self.assertEqual(dados["telefone"], "(11) 99999-0000")
        self.assertEqual(dados["autoriza_imagem"], "Autorizo")
        self.assertEqual(dados["menor_nome"], "")
        self.assertEqual(dados["signatario_nome"], "Ana Souza")
        self.assertEqual(dados["profissional_registro"], "CRBM 1234")
        self.assertEqual(dados["clinica_nome"], "Essência")
        self.assertEqual(dados["cidade"], "São Paulo")
        self.assertEqual(dados["data"], "04/11/2026")
        # A ficha vai no mesmo documento (PRD 038): uma variável por pergunta.
        self.assertEqual((dados["gestante"], dados["fototipo"], dados["queixa_principal"], dados["hormonal_quais"]),
                         ("Não", "III", "Pelos encravados", "-"))
        self.assertEqual(len(dados), 17 + 50)
        self.assertEqual(signatario.cpf, CPF_OK)
        self.assertEqual(signatario.telefone, FONE)
        termo = self.db.termos[c["id"]]
        self.assertEqual(termo["signer_kind"], "PATIENT")
        self.assertEqual(termo["patient_snapshot"]["variaveis"]["cpf"], "529.982.247-25")
        self.assertEqual(termo["patient_snapshot"]["respostas"]["fototipo"], "III")
        self.assertEqual(termo["answers"]["gestante"], False)
        # A linha FILLING virou histórico; só a SIGNING está em andamento.
        self.assertEqual([t["status"] for t in self.db.termos.values()], [EXPIRADO, ASSINANDO])
        self.assertEqual(termo["responsible_snapshot"]["profissional_nome"], "Dra. Lia")

    def test_nao_exigido_quando_ja_assinou(self):
        consentimento.registra_papel(self.db, CLINIC, PAC, date(2026, 11, 1), "Recepção")
        self.assertEqual(self.inicia()["status"], "NOT_REQUIRED")
        self.assertEqual(self.prov.criados, [])

    def test_clinica_sem_responsavel_e_invalido(self):
        self.db.profissionais[PROF]["registro_conselho"] = None
        with self.assertRaises(consentimento.ConsentimentoInvalido):
            self.inicia()
        self.assertEqual(self.prov.criados, [])

    def test_dados_invalidos(self):
        for ruim in ({"fullName": "Ana"}, {"cpf": "11111111111"}, {"birthDate": "2030-01-01"},
                     {"email": "ana"}, {"imageAuthorized": None}):
            with self.subTest(ruim):
                with self.assertRaises(consentimento.ConsentimentoInvalido):
                    self.inicia(dados=dict(DADOS, **ruim))
        self.assertEqual(self.prov.criados, [])

    def test_cpf_nulo_usa_o_do_cadastro(self):
        self.db.pacientes[PAC]["cpf"] = CPF_OK
        self.inicia(dados=dict(DADOS, cpf=None))
        self.assertEqual(self.prov.criados[0][3].cpf, CPF_OK)

    def test_menor_sem_responsavel_e_invalido(self):
        dados = dict(DADOS, fullName="Bia Souza", birthDate="2010-06-01")
        with self.assertRaises(consentimento.ConsentimentoInvalido):
            self.inicia(APPT_MENOR, dados)

    def test_menor_assina_pelo_responsavel(self):
        dados = dict(DADOS, fullName="Bia Souza", birthDate="2010-06-01", guardian=RESPONSAVEL)
        c = self.inicia(APPT_MENOR, dados)
        _, _, variaveis, signatario, _, _ = self.prov.criados[0]
        self.assertEqual(variaveis["menor_nome"], "Bia Souza")
        self.assertEqual(variaveis["responsavel_nome"], "Carla Souza")
        self.assertEqual(variaveis["signatario_nome"], "Carla Souza")
        self.assertEqual(variaveis["signatario_cpf"], "111.444.777-35")
        self.assertEqual(variaveis["telefone"], "(11) 98888-7777")
        self.assertEqual(signatario.nome, "Carla Souza")
        self.assertEqual(signatario.telefone, "5511988887777")
        self.assertEqual(self.db.termos[c["id"]]["signer_kind"], "GUARDIAN")
        self.assertEqual(self.db.responsaveis[PAC_MENOR]["cpf"], CPF_RESP)

    def test_responsavel_com_o_mesmo_cpf_da_menor_e_invalido(self):
        dados = dict(DADOS, fullName="Bia Souza", birthDate="2010-06-01", guardian=dict(RESPONSAVEL, cpf=CPF_OK))
        with self.assertRaises(consentimento.ConsentimentoInvalido):
            self.inicia(APPT_MENOR, dados)

    def test_cadastro_so_ganha_campo_vazio(self):
        # "Ana" (um nome só) conta como vazio; CPF, nascimento e e-mail estavam vazios.
        self.inicia()
        p = self.db.pacientes[PAC]
        self.assertEqual((p["name"], p["cpf"], p["birth_date"], p["email"]),
                         ("Ana Souza", CPF_OK, date(1990, 5, 10), "ana@exemplo.com"))

    def test_nome_editado_atualiza_cadastro_e_agendamento(self):
        # O nome confirmado no termo vale para o cadastro e para o agendamento
        # (o prefill lê o full_name do agendamento primeiro). CPF e e-mail
        # preenchidos não são tocados.
        self.db.pacientes[PAC].update(name="Ana Maria Souza", cpf="52998224725", email="outra@exemplo.com")
        self.db.agendamentos[APPT]["full_name"] = "Ana Maria Souza"
        self.inicia(dados=dict(DADOS, fullName="Ana M. Souza"))
        self.assertEqual(self.db.pacientes[PAC]["name"], "Ana M. Souza")
        self.assertEqual(self.db.agendamentos[APPT]["full_name"], "Ana M. Souza")
        self.assertEqual(self.db.pacientes[PAC]["email"], "outra@exemplo.com")
        self.assertEqual(self.db.pacientes[PAC]["cpf"], "52998224725")

    def test_nome_igual_nao_escreve(self):
        self.db.pacientes[PAC].update(name="Ana Souza")
        self.db.agendamentos[APPT]["full_name"] = "Ana Souza"
        self.inicia()
        self.assertFalse(any("UPDATE scheduler.appointments SET full_name" in e for e in self.db.escritas))

    def test_signing_recente_e_reaproveitado(self):
        a = self.inicia()
        b = self.inicia()
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(self.prov.criados), 1)

    def test_signing_com_dados_editados_e_descartado(self):
        """Editou o nome (ou o CPF, o e-mail, a imagem) antes de gerar: o PDF
        que já está na ClickSign tem os dados antigos, então é outro termo."""
        a = self.inicia()
        b = self.inicia(dados=dict(DADOS, fullName="Ana Souza Editada"))
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.db.termos[a["id"]]["status"], EXPIRADO)
        self.assertEqual(self.prov.cancelados, ["env-1"])
        self.assertEqual(self.prov.criados[-1][2]["nome_completo"], "Ana Souza Editada")
        c = self.inicia(dados=dict(DADOS, fullName="Ana Souza Editada", imageAuthorized=False))
        self.assertNotEqual(b["id"], c["id"])
        d = self.inicia(dados=dict(DADOS, fullName="Ana Souza Editada", imageAuthorized=False))
        self.assertEqual(c["id"], d["id"])

    def test_signing_velho_e_descartado(self):
        a = self.inicia()
        self.db.termos[a["id"]]["created_at"] = AGORA - timedelta(hours=30)
        b = self.inicia()
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.db.termos[a["id"]]["status"], EXPIRADO)
        self.assertEqual(self.prov.cancelados, ["env-1"])
        self.assertEqual(len(self.prov.criados), 2)

    def test_corrida_cancela_o_envelope_novo(self):
        a = self.inicia()
        # Simula o outro toque: os dois leram a mesma linha FILLING; o outro
        # já a promoveu a SIGNING quando ESTE insere.
        original = self.db.execute_query
        self.db.termos["zzz"] = dict(self.db.termos[a["id"]], id="zzz", status="FILLING", provider=None)

        def sem_signing(sql, params=None):
            if "status IN ('FILLING', 'SIGNING') LIMIT 1" in sql and not getattr(sem_signing, "ja", False):
                sem_signing.ja = True
                return [dict(self.db.termos["zzz"])]
            return original(sql, params)
        self.db.execute_query = sem_signing
        b = self.inicia()
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(self.prov.cancelados, ["env-2"])

    def test_agendamento_de_outro_numero_e_inexistente(self):
        from src.services import checkin
        with self.assertRaises(checkin.NaoEncontrado):
            consentimento.inicia(self.db, self.prov, CLINIC, OUTRO_FONE, APPT, DADOS)


class TestStatus(Base):
    def test_assinado_baixa_grava_e_marca(self):
        c = self.inicia()
        self.prov.status_remoto["env-1"] = ASSINADO
        self.prov.zip = b"PK-zip"
        r = consentimento.status(self.db, self.prov, CLINIC, FONE, c["id"])["consent"]
        self.assertEqual(r["status"], ASSINADO)
        self.assertEqual(r["signedAt"], AGORA.isoformat())
        t = self.db.termos[c["id"]]
        self.assertEqual(t["pdf_s3_key"], "clinics/%s/patients/%s/consents/%s/tcle-assinado.pdf" % (CLINIC, PAC, c["id"]))
        self.assertEqual(t["pdf_sha256"], "sha-10")
        self.assertTrue(t["audit_s3_key"].endswith("tcle-auditoria.zip"))
        self.assertEqual(self.gravados[t["pdf_s3_key"]], b"%PDF-teste")

    def test_download_falho_nao_marca(self):
        c = self.inicia()
        self.prov.status_remoto["env-1"] = ASSINADO
        self.prov.falha_download = True
        r = consentimento.status(self.db, self.prov, CLINIC, FONE, c["id"])["consent"]
        self.assertEqual(r["status"], ASSINANDO)
        self.assertEqual(self.gravados, {})

    def test_cancelado_e_expirado_sao_gravados(self):
        c = self.inicia()
        self.prov.status_remoto["env-1"] = EXPIRADO
        self.assertEqual(consentimento.status(self.db, self.prov, CLINIC, FONE, c["id"])["consent"]["status"], EXPIRADO)

    def test_termo_de_outro_numero_e_inexistente(self):
        c = self.inicia()
        with self.assertRaises(consentimento.NaoEncontrado):
            consentimento.status(self.db, self.prov, CLINIC, OUTRO_FONE, c["id"])

    def test_simula_so_com_provedor_simulado(self):
        c = self.inicia()
        with self.assertRaises(consentimento.ConsentimentoInvalido):
            consentimento.simula(self.db, self.prov, CLINIC, FONE, c["id"])
        sim = Simulado()
        self.responde(APPT_MENOR)
        c2 = consentimento.inicia(self.db, sim, CLINIC, FONE, APPT_MENOR,
                                  dict(DADOS, fullName="Bia Souza", birthDate="2010-06-01",
                                       guardian=RESPONSAVEL))["consent"]
        self.assertTrue(c2["canSimulate"])
        r = consentimento.simula(self.db, sim, CLINIC, FONE, c2["id"])["consent"]
        self.assertEqual(r["status"], ASSINADO)


class TestWebhook(Base):
    def evento(self, nome, doc="doc-1", env="env-1", occurred="2026-11-04T12:00:00Z"):
        return {"event": {"name": nome, "occurred_at": occurred},
                "document": {"key": doc}, "envelope": {"key": env}}

    def test_fechado_marca_assinado_e_grava_o_evento_uma_vez(self):
        c = self.inicia()
        ev = self.evento("auto_close")
        eid = consentimento.event_id_de(ev)
        self.assertEqual(eid, "auto_close:doc-1:2026-11-04T12:00:00Z")
        self.assertEqual(consentimento.aplica_evento(self.db, self.prov, ev, eid), ASSINADO)
        self.assertEqual(self.db.termos[c["id"]]["status"], ASSINADO)
        self.assertEqual(consentimento.aplica_evento(self.db, self.prov, ev, eid), "repetido")
        self.assertEqual(len(self.db.eventos), 1)

    def test_payload_v3_aninhado_tambem_localiza(self):
        c = self.inicia()
        ev = {"event": {"name": "envelope.closed", "id": "evt-9",
                        "data": {"envelope": {"id": "env-1", "documents": [{"id": "doc-1"}]}}}}
        self.assertEqual(consentimento.event_id_de(ev), "evt-9")
        self.assertEqual(consentimento.aplica_evento(self.db, self.prov, ev, "evt-9"), ASSINADO)
        self.assertEqual(self.db.termos[c["id"]]["status"], ASSINADO)

    def test_cancel_e_deadline(self):
        c = self.inicia()
        self.assertEqual(consentimento.aplica_evento(self.db, self.prov, self.evento("cancel"), "e1"), CANCELADO)
        self.assertEqual(self.db.termos[c["id"]]["status"], CANCELADO)
        self.assertEqual(consentimento.aplica_evento(self.db, self.prov, self.evento("deadline"), "e2"),
                         "ignorado: já CANCELLED")

    def test_pdf_indisponivel_nao_grava_como_assinado(self):
        self.inicia()
        self.prov.falha_download = True
        self.assertEqual(consentimento.aplica_evento(self.db, self.prov, self.evento("close"), "e1"),
                         "pendente: PDF indisponível")

    def test_evento_desconhecido_e_ignorado(self):
        self.assertEqual(consentimento.aplica_evento(self.db, self.prov, self.evento("sign"), "e1"),
                         "ignorado: sign")
        self.assertEqual(consentimento.aplica_evento(self.db, self.prov, self.evento("close", doc="x"), "e2"),
                         "ignorado: termo desconhecido")


class TestPainel(Base):
    def test_papel_duas_vezes_devolve_o_mesmo(self):
        a, criado_a = consentimento.registra_papel(self.db, CLINIC, PAC, date(2026, 11, 1), "Recepção")
        b, criado_b = consentimento.registra_papel(self.db, CLINIC, PAC, date(2026, 11, 2), "Recepção")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(a["status"], "PAPER")
        self.assertEqual(a["paper_registered_by"], "Recepção")
        # PRD 047: a segunda vez diz que já tinha, e a data da primeira fica.
        self.assertTrue(criado_a)
        self.assertFalse(criado_b)
        self.assertEqual(b["paper_signed_at"], "2026-11-01")

    def test_papel_com_data_futura_falha(self):
        with self.assertRaises(consentimento.ConsentimentoInvalido):
            consentimento.registra_papel(self.db, CLINIC, PAC, date(2027, 1, 1), "x")

    def test_dispensa_com_motivo_invalido_falha(self):
        with self.assertRaises(consentimento.ConsentimentoInvalido):
            consentimento.dispensa(self.db, CLINIC, APPT, "PREGUICA", None, "x")
        with self.assertRaises(consentimento.ConsentimentoInvalido):
            consentimento.dispensa(self.db, CLINIC, APPT, "OUTRO", "", "x")
        r = consentimento.dispensa(self.db, CLINIC, APPT, "OUTRO", "veio sem óculos", "Recepção")
        self.assertEqual(r["consent_waived_reason"], "OUTRO")
        self.assertEqual(r["consent_waived_by"], "Recepção")

    def test_lista_e_urls(self):
        c = self.inicia()
        self.prov.status_remoto["env-1"] = ASSINADO
        consentimento.status(self.db, self.prov, CLINIC, FONE, c["id"])
        lista = consentimento.lista_do_paciente(self.db, CLINIC, PAC)
        self.assertEqual(len(lista), 1)
        self.assertTrue(lista[0]["has_pdf"])
        self.assertFalse(lista[0]["has_zip"])
        self.assertTrue(lista[0]["test"])
        self.assertTrue(consentimento.url_do_pdf(self.db, CLINIC, c["id"])["url"].startswith("https://s3/clinics/"))
        with self.assertRaises(consentimento.NaoEncontrado):
            consentimento.url_do_zip(self.db, CLINIC, c["id"])
        with self.assertRaises(consentimento.NaoEncontrado):
            consentimento.url_do_pdf(self.db, "outra-clinica", c["id"])


class TestAnamnese(Base):
    def test_grava_tela_a_tela_numa_linha_filling(self):
        r1 = consentimento.guarda_respostas(self.db, self.prov, CLINIC, FONE, APPT, 1, {
            **{p.chave: False for p in anamnese.PERGUNTAS if p.tela == 1 and p.tipo == anamnese.SIM_NAO},
            "queixa_principal": "Virilha", "hormonal": True, "hormonal_quais": "SOP"})["anamnesis"]
        self.assertEqual((r1["screen"], r1["complete"]), (1, False))
        self.assertIn("hormonal_quais", r1["answered"])
        linha = next(iter(self.db.termos.values()))
        self.assertEqual((linha["status"], linha["answers"]["hormonal_quais"]), ("FILLING", "SOP"))
        self.assertEqual(self.responde()["complete"], True)
        self.assertEqual(len(self.db.termos), 1)
        # A tela 1 regravada substitui as chaves dela: a condicional some.
        self.assertNotIn("hormonal_quais", linha["answers"])
        # Nada de prefill no iPad (decisão do André em 06/11): a ficha abre em branco.
        self.assertNotIn("anamnesisPrefill", consentimento.resumo_para_o_ipad(self.db, CLINIC, self.db.agendamentos[APPT]))

    def test_tela_invalida_aponta_o_campo(self):
        with self.assertRaises(anamnese.AnamneseInvalida) as cm:
            consentimento.guarda_respostas(self.db, self.prov, CLINIC, FONE, APPT, 2,
                                           {"medicamento": True, "isotretinoina": False,
                                            "fotossensibilizante": False, "minoxidil": False})
        self.assertEqual(cm.exception.campo, "medicamento_quais")
        with self.assertRaises(anamnese.AnamneseInvalida):
            consentimento.guarda_respostas(self.db, self.prov, CLINIC, FONE, APPT, "x", {})

    def test_inicia_sem_ficha_falha(self):
        with self.assertRaises(consentimento.ConsentimentoInvalido) as cm:
            self.inicia(responde=False)
        self.assertIn("anamnese", str(cm.exception))
        self.assertEqual(self.prov.criados, [])

    def test_mudar_resposta_com_envelope_aberto_cancela_o_envelope(self):
        a = self.inicia()
        consentimento.guarda_respostas(self.db, self.prov, CLINIC, FONE, APPT, 3, {
            **{p.chave: False for p in anamnese.PERGUNTAS if p.tela == 3 and p.tipo == anamnese.SIM_NAO},
            "tatuagem": True})
        self.assertEqual(self.db.termos[a["id"]]["status"], EXPIRADO)
        self.assertEqual(self.prov.cancelados, ["env-1"])
        b = self.inicia()
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.prov.criados[-1][2]["tatuagem"], "Sim")

    def test_mesmas_respostas_reaproveitam_o_envelope(self):
        a = self.inicia()
        b = self.inicia()
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(self.prov.criados), 1)

    def test_painel_traz_respostas_e_alertas(self):
        self.responde(gestante=True, diabetes=True, diabetes_controlada=False)
        c = self.inicia()
        self.prov.status_remoto["env-1"] = ASSINADO
        consentimento.status(self.db, self.prov, CLINIC, FONE, c["id"])
        termo = consentimento.lista_do_paciente(self.db, CLINIC, PAC)[0]
        self.assertTrue(termo["has_anamnesis"])
        self.assertEqual(termo["answers"]["gestante"], True)
        self.assertEqual([a["key"] for a in termo["alertas"]], ["gestante", "diabetes_nao_controlada"])

    def test_renova_revoga_o_vigente_e_o_checkin_pede_de_novo(self):
        c = self.inicia()
        self.prov.status_remoto["env-1"] = ASSINADO
        consentimento.status(self.db, self.prov, CLINIC, FONE, c["id"])
        self.assertFalse(consentimento.precisa_assinar(self.db, CLINIC, self.db.agendamentos[APPT]))
        r = consentimento.renova(self.db, CLINIC, c["id"], "Recepção")
        self.assertEqual((r["status"], r["revoked_by"]), ("REVOKED", "Recepção"))
        self.assertTrue(consentimento.precisa_assinar(self.db, CLINIC, self.db.agendamentos[APPT]))
        with self.assertRaises(consentimento.NaoEncontrado):
            consentimento.renova(self.db, CLINIC, c["id"], "Recepção")

    def test_linha_antiga_sem_respostas_nao_quebra_o_painel(self):
        self.db.termos["x"] = {"id": "x", "clinic_id": CLINIC, "patient_id": PAC, "status": "SIGNED",
                               "term_version": "2026-11", "answers": None, "provider": "clicksign",
                               "created_at": AGORA}
        termo = consentimento.lista_do_paciente(self.db, CLINIC, PAC)[0]
        self.assertEqual((termo["has_anamnesis"], termo["answers"], termo["alertas"]), (False, None, []))


if __name__ == "__main__":
    unittest.main()
