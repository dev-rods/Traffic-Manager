# -*- coding: utf-8 -*-
"""Link de cobrança pelo WhatsApp (PRD 029).

Para quem não pagou no check-in: a recepção manda pelo painel um link do
Asaas com forma livre. Um pagamento vivo por agendamento continua valendo, e
falha do WhatsApp não pode deixar uma cobrança criada sem a recepção saber o
link.
"""
import json
import os
import unittest
from datetime import date, time
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.providers.payment_provider import Cobranca
from src.services import checkin

CLINIC = "clinica-teste-0001"
APPT = "aaaaaaaa-0000-0000-0000-000000000001"
CPF = "52998224725"


class Db:
    def __init__(self, vivo=None, status="CONFIRMED", preco=13500, cpf=CPF, full_name="Ana Souza"):
        self.appt = {"id": APPT, "clinic_id": CLINIC, "status": status, "final_price_cents": preco,
                     "full_name": full_name, "patient_name": "Ana Souza", "patient_cpf": cpf,
                     "patient_uuid": "p1", "patient_phone": "5511900000026",
                     "appointment_date": date(2026, 10, 29), "start_time": time(15, 0)}
        self.vivo = vivo
        self.inseridos = []
        self.marcados = []
        self.cpf_gravado = None

    def execute_query(self, sql, params=None):
        if "FROM scheduler.appointments a" in sql:
            return [dict(self.appt)] if params == (APPT, CLINIC) else []
        if "FROM scheduler.clinics" in sql and "SELECT *" in sql:
            return [{"clinic_id": CLINIC, "display_name": "Clinica do rods", "zapi_instance_id": "i"}]
        if "timezone" in sql:
            return [{"timezone": "America/Sao_Paulo"}]
        if "appointment_payments" in sql:
            return [dict(self.vivo)] if self.vivo else []
        raise AssertionError(sql)

    def execute_write_returning(self, sql, params=None):
        assert "INSERT INTO scheduler.appointment_payments" in sql
        cols = ["id", "clinic_id", "appointment_id", "method", "amount_cents", "status", "provider",
                "provider_payment_id", "invoice_url", "pix_payload", "payer_name", "payer_cpf"]
        row = dict(zip(cols, params))
        self.inseridos.append(row)
        return row

    def execute_write(self, sql, params=None):
        if "UPDATE scheduler.patients SET cpf" in sql:
            self.cpf_gravado = params[0]
        elif "UPDATE scheduler.appointment_payments SET status" in sql:
            self.marcados.append((params[2], params[0]))
        return 1


class Provedor:
    nome = "asaas"
    pode_simular = False

    def __init__(self, pago=False):
        self.criadas = []
        self.canceladas = []
        self.pago = pago

    def cria_cobranca(self, pagador, metodo, valor, vencimento, descricao, referencia):
        self.criadas.append((pagador, metodo, valor, vencimento))
        return Cobranca("pay_link", "PENDING", invoice_url="https://asaas/i/link")

    def consulta_status(self, cobranca_id):
        return "PAID" if self.pago else "PENDING"

    def cancela(self, cobranca_id):
        self.canceladas.append(cobranca_id)


class Resposta:
    def __init__(self, ok=True):
        self.success = ok
        self.error = None if ok else "instância desconectada"


class Zap:
    def __init__(self, ok=True, explode=False):
        self.enviados = []
        self.ok = ok
        self.explode = explode

    def __call__(self, clinica):
        return self

    def send_text(self, phone, message):
        if self.explode:
            raise RuntimeError("z-api fora")
        self.enviados.append((phone, message))
        return Resposta(self.ok)


def vivo(**kw):
    base = {"id": "pg-1", "appointment_id": APPT, "method": "PIX", "status": "PENDING", "amount_cents": 13500,
            "provider": "asaas", "provider_payment_id": "pay_old", "invoice_url": "https://asaas/i/old",
            "pix_payload": "000201", "paid_at": None}
    base.update(kw)
    return base


class TestEnviaLink(unittest.TestCase):
    def test_cria_cobranca_livre_e_manda_pelo_whatsapp(self):
        db, prov, zap = Db(), Provedor(), Zap()
        r = checkin.envia_link(db, prov, CLINIC, APPT, whatsapp_de=zap)
        self.assertEqual((r["sent"], r["invoiceUrl"], r["payment"]["method"]), (True, "https://asaas/i/link", "LINK"))
        pagador, metodo, valor, vencimento = prov.criadas[0]
        self.assertEqual((pagador.cpf, metodo, valor), (CPF, "LINK", 13500))
        self.assertGreater(vencimento, date.today())
        telefone, texto = zap.enviados[0]
        self.assertEqual(telefone, "5511900000026")
        for trecho in ("Olá, Ana!", "29/10 às 15:00", "Clinica do rods", "R$ 135,00", "https://asaas/i/link"):
            self.assertIn(trecho, texto)

    def test_link_pendente_e_reenviado_sem_nova_cobranca(self):
        db, prov, zap = Db(vivo=vivo(method="LINK", invoice_url="https://asaas/i/ja")), Provedor(), Zap()
        r = checkin.envia_link(db, prov, CLINIC, APPT, whatsapp_de=zap)
        self.assertEqual((prov.criadas, r["invoiceUrl"]), ([], "https://asaas/i/ja"))
        self.assertIn("https://asaas/i/ja", zap.enviados[0][1])

    def test_pix_abandonado_do_ipad_e_substituido(self):
        db, prov = Db(vivo=vivo()), Provedor()
        checkin.envia_link(db, prov, CLINIC, APPT, whatsapp_de=Zap())
        self.assertEqual(prov.canceladas, ["pay_old"])
        self.assertEqual(db.marcados, [("pg-1", "CANCELLED")])
        self.assertEqual(len(prov.criadas), 1)

    def test_pago_no_meio_tempo_nao_envia(self):
        db, prov, zap = Db(vivo=vivo()), Provedor(pago=True), Zap()
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.envia_link(db, prov, CLINIC, APPT, whatsapp_de=zap)
        self.assertEqual((prov.criadas, zap.enviados), ([], []))

    def test_ja_pago_nao_envia(self):
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.envia_link(Db(vivo=vivo(status="PAID")), Provedor(), CLINIC, APPT, whatsapp_de=Zap())

    def test_sem_cpf_pede_ao_painel(self):
        with self.assertRaises(checkin.PrecisaDeCpf):
            checkin.envia_link(Db(cpf=None), Provedor(), CLINIC, APPT, whatsapp_de=Zap())

    def test_cpf_de_outra_pessoa_no_cadastro_nao_serve(self):
        # Telefone compartilhado: o cadastro é da mãe, o agendamento da filha.
        with self.assertRaises(checkin.PrecisaDeCpf):
            checkin.envia_link(Db(full_name="Bia Souza"), Provedor(), CLINIC, APPT, whatsapp_de=Zap())

    def test_cpf_informado_vai_para_a_cobranca_e_para_o_cadastro_vazio(self):
        db, prov = Db(cpf=None), Provedor()
        checkin.envia_link(db, prov, CLINIC, APPT, cpf="529.982.247-25", whatsapp_de=Zap())
        self.assertEqual((prov.criadas[0][0].cpf, db.cpf_gravado), (CPF, CPF))

    def test_cpf_invalido(self):
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.envia_link(Db(cpf=None), Provedor(), CLINIC, APPT, cpf="111.111.111-11", whatsapp_de=Zap())

    def test_whatsapp_falhou_a_cobranca_fica_e_o_link_volta(self):
        for zap in (Zap(ok=False), Zap(explode=True)):
            db, prov = Db(), Provedor()
            r = checkin.envia_link(db, prov, CLINIC, APPT, whatsapp_de=zap)
            self.assertEqual((r["sent"], r["invoiceUrl"], prov.canceladas), (False, "https://asaas/i/link", []))

    def test_sem_valor_cancelado_ou_inexistente(self):
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.envia_link(Db(preco=None), Provedor(), CLINIC, APPT, whatsapp_de=Zap())
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.envia_link(Db(status="CANCELLED"), Provedor(), CLINIC, APPT, whatsapp_de=Zap())
        with self.assertRaises(checkin.NaoEncontrado):
            checkin.envia_link(Db(), Provedor(), "outra-clinica", APPT, whatsapp_de=Zap())
        with self.assertRaises(checkin.NaoEncontrado):
            checkin.envia_link(Db(), Provedor(), CLINIC, "nao-e-uuid", whatsapp_de=Zap())


class TestRota(unittest.TestCase):
    def _evento(self, corpo=None):
        return {"httpMethod": "POST", "pathParameters": {"clinicId": CLINIC, "proxy": f"agendamentos/{APPT}/link"},
                "headers": {}, "body": json.dumps(corpo or {})}

    def _chama(self, corpo=None, **efeito):
        from src.functions.caixa import router
        with mock.patch.object(router, "require_acesso", return_value=(None, None)), \
                mock.patch.object(router, "PostgresService"), \
                mock.patch.object(router, "provedor_ativo"), \
                mock.patch("src.services.checkin.envia_link", **efeito) as envia:
            return router.handler(self._evento(corpo), None), envia

    def test_envia(self):
        resp, envia = self._chama({"cpf": CPF}, return_value={"payment": {"id": "x"}, "invoiceUrl": "u", "sent": True})
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(json.loads(resp["body"])["sent"], True)
        self.assertEqual(envia.call_args.kwargs["cpf"], CPF)

    def test_sem_cpf_responde_codigo_para_o_painel(self):
        resp, _ = self._chama(side_effect=checkin.PrecisaDeCpf())
        self.assertEqual((resp["statusCode"], json.loads(resp["body"])["code"]), (409, "CPF_REQUIRED"))

    def test_agendamento_inexistente(self):
        resp, _ = self._chama(side_effect=checkin.NaoEncontrado())
        self.assertEqual(resp["statusCode"], 404)

    def test_sem_acesso(self):
        from src.functions.caixa import router
        negado = {"statusCode": 403, "body": "{}"}
        with mock.patch.object(router, "require_acesso", return_value=(None, negado)):
            self.assertEqual(router.handler(self._evento(), None)["statusCode"], 403)


class TestAsaasLink(unittest.TestCase):
    def test_forma_livre(self):
        from src.providers.asaas_provider import TIPO_DE_COBRANCA
        self.assertEqual(TIPO_DE_COBRANCA["LINK"], "UNDEFINED")


if __name__ == "__main__":
    unittest.main()
