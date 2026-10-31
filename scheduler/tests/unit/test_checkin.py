# -*- coding: utf-8 -*-
"""Check-in de autoatendimento com pagamento (PRD 026).

O banco abaixo guarda agendamentos e pagamentos em memória e responde às
consultas do `checkin` pelo conteúdo do SQL. É o suficiente para exercitar
as regras que importam para o caixa: de quem é o agendamento, quanto se
cobra, um pagamento vivo por agendamento, troca de método e webhook.
"""
import json
import os
import unittest
import uuid
from datetime import date, datetime, time
from unittest import mock

import psycopg2

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.providers.payment_provider import (
    AGUARDANDO_DINHEIRO, CANCELADO, Cobranca, PAGO, PENDENTE, PaymentProvider,
)
from src.services import checkin

CLINIC = "clinica-teste-0001"
FONE = "5511999990000"
OUTRO_FONE = "5511988887777"
CPF_OK = "52998224725"
APPT = "aaaaaaaa-0000-0000-0000-000000000001"
APPT_FILHA = "aaaaaaaa-0000-0000-0000-000000000002"
APPT_SEM_VALOR = "aaaaaaaa-0000-0000-0000-000000000003"


class Provedor(PaymentProvider):
    nome = "asaas"

    def __init__(self):
        self.criadas = []
        self.canceladas = []
        self.status_remoto = {}
        self.dinheiro = []

    def cria_cobranca(self, pagador, metodo, valor_cents, vencimento, descricao, referencia):
        cid = f"pay_{len(self.criadas) + 1}"
        self.criadas.append((cid, pagador, metodo, valor_cents, vencimento, referencia))
        if metodo == "PIX":
            return Cobranca(cid, PENDENTE, pix_payload="000201PIX")
        if metodo == "CASH":
            return Cobranca(cid, PENDENTE)
        return Cobranca(cid, PENDENTE, invoice_url=f"https://asaas/i/{cid}")

    def cancela(self, cobranca_id):
        self.canceladas.append(cobranca_id)

    def consulta_status(self, cobranca_id):
        return self.status_remoto.get(cobranca_id)

    def recebe_em_dinheiro(self, cobranca_id, valor_cents, data):
        self.dinheiro.append((cobranca_id, valor_cents))


class Db:
    def __init__(self, cpf_cadastro=None):
        self.pacientes = {"pac1": {"id": "pac1", "phone": FONE, "name": "Ana Souza", "cpf": cpf_cadastro}}
        self.agendamentos = {
            APPT: {"id": APPT, "clinic_id": CLINIC, "patient_id": "pac1", "status": "CONFIRMED",
                   "appointment_date": date(2026, 10, 20), "start_time": time(10, 0),
                   "full_name": "Ana Souza", "final_price_cents": 22500, "original_price_cents": 25000,
                   "discount_pct": 10, "checked_in_at": None, "service_name": "Laser",
                   "areas_display": "Axilas, Buço"},
            APPT_FILHA: {"id": APPT_FILHA, "clinic_id": CLINIC, "patient_id": "pac1", "status": "CONFIRMED",
                         "appointment_date": date(2026, 10, 22), "start_time": time(9, 0),
                         "full_name": "Bia Souza", "final_price_cents": 9500, "checked_in_at": None,
                         "service_name": "Laser", "areas_display": "Axilas"},
            APPT_SEM_VALOR: {"id": APPT_SEM_VALOR, "clinic_id": CLINIC, "patient_id": "pac1",
                             "status": "CONFIRMED", "appointment_date": date(2026, 10, 25),
                             "start_time": time(9, 0), "full_name": "Ana Souza",
                             "final_price_cents": None, "checked_in_at": None},
        }
        self.pagamentos = {}
        self.eventos = set()

    # -- leitura -----------------------------------------------------------
    def _do_fone(self, fones):
        return [p["id"] for p in self.pacientes.values() if p["phone"] in fones]

    def execute_query(self, sql, params=None):
        if "FROM scheduler.appointments a" in sql and "JOIN scheduler.patients p" in sql and "service_name" in sql:
            clinic, fones = params[0], params[1]
            ids = self._do_fone(fones)
            return sorted([dict(a) for a in self.agendamentos.values() if a["patient_id"] in ids],
                          key=lambda a: (a["appointment_date"], a["start_time"]))
        if "patient_cpf" in sql:
            appt_id, clinic, fones = params
            a = self.agendamentos.get(appt_id)
            if not a or a["clinic_id"] != clinic or a["patient_id"] not in self._do_fone(fones):
                return []
            p = self.pacientes[a["patient_id"]]
            return [dict(a, patient_uuid=p["id"], patient_name=p["name"], patient_cpf=p["cpf"])]
        if "FROM scheduler.appointment_payments pay" in sql:
            pid, clinic, fones = params
            pay = self.pagamentos.get(pid)
            if not pay or pay["clinic_id"] != clinic:
                return []
            a = self.agendamentos[pay["appointment_id"]]
            return [dict(pay)] if a["patient_id"] in self._do_fone(fones) else []
        if "appointment_id = ANY" in sql:
            ids, vivos = params
            return [dict(p) for p in self.pagamentos.values() if p["appointment_id"] in ids and p["status"] in vivos]
        if "provider_payment_id = %s" in sql:
            return [dict(p) for p in self.pagamentos.values() if p["provider_payment_id"] == params[0]]
        if "AND id <> %s::uuid" in sql:
            appt, status, pid = params
            return [dict(p) for p in self.pagamentos.values()
                    if p["appointment_id"] == appt and p["status"] in status and p["id"] != pid]
        if "FROM scheduler.appointment_payments WHERE id = %s::uuid AND clinic_id" in sql:
            p = self.pagamentos.get(params[0])
            return [dict(p)] if p and p["clinic_id"] == params[1] else []
        if "FROM scheduler.appointment_payments WHERE id = %s::uuid" in sql:
            return [dict(self.pagamentos[params[0]])]
        if "payment_webhook_events WHERE event_id" in sql:
            return [{"x": 1}] if params[0] in self.eventos else []
        if "SELECT timezone" in sql:
            return [{"timezone": "America/Sao_Paulo"}]
        raise AssertionError(f"consulta inesperada: {sql}")

    # -- escrita -----------------------------------------------------------
    def execute_write(self, sql, params=None):
        if "SET checked_in_at" in sql:
            self.agendamentos[params[0]]["checked_in_at"] = datetime(2026, 10, 20, 9, 50)
            return 1
        if "UPDATE scheduler.appointment_payments SET status" in sql:
            status, _, pid = params
            p = self.pagamentos[pid]
            p["status"] = status
            if status == PAGO and not p.get("paid_at"):
                p["paid_at"] = datetime(2026, 10, 20, 9, 55)
            return 1
        if "UPDATE scheduler.patients SET cpf" in sql:
            self.pacientes[params[1]]["cpf"] = params[0]
            return 1
        if "INSERT INTO scheduler.payment_webhook_events" in sql:
            self.eventos.add(params[0])
            return 1
        raise AssertionError(f"escrita inesperada: {sql}")

    def execute_write_returning(self, sql, params=None):
        assert "INSERT INTO scheduler.appointment_payments" in sql
        (pid, clinic, appt, metodo, valor, status, provider, prov_id, invoice, pix, nome, cpf) = params
        if any(p["appointment_id"] == appt and p["status"] in checkin.VIVOS for p in self.pagamentos.values()):
            raise psycopg2.IntegrityError("uq_appointment_payments_ativo")
        row = {"id": pid, "clinic_id": clinic, "appointment_id": appt, "method": metodo, "amount_cents": valor,
               "status": status, "provider": provider, "provider_payment_id": prov_id, "invoice_url": invoice,
               "pix_payload": pix, "payer_name": nome, "payer_cpf": cpf, "paid_at": None}
        self.pagamentos[pid] = row
        return dict(row)


AGORA = datetime(2026, 10, 20, 9, 45)


class Base(unittest.TestCase):
    def setUp(self):
        self.db = Db(cpf_cadastro=CPF_OK)
        self.prov = Provedor()
        p = mock.patch("src.services.relogio.agora_na_clinica", return_value=AGORA)
        p.start()
        self.addCleanup(p.stop)


class TestAgendamentosDoNumero(Base):
    def test_lista_do_mais_proximo_com_nome_areas_e_valor(self):
        lista = checkin.agendamentos_do_numero(self.db, CLINIC, FONE)
        self.assertEqual([a["fullName"] for a in lista[:2]], ["Ana Souza", "Bia Souza"])
        self.assertEqual(lista[0]["areas"], ["Axilas", "Buço"])
        self.assertEqual(lista[0]["finalPriceCents"], 22500)
        self.assertIsNone(lista[0]["payment"])

    def test_outro_numero_nao_ve_nada(self):
        self.assertEqual(checkin.agendamentos_do_numero(self.db, CLINIC, OUTRO_FONE), [])


class TestConfirma(Base):
    def test_grava_check_in_uma_vez(self):
        r = checkin.confirma(self.db, CLINIC, FONE, APPT)
        self.assertEqual(r, {"checkedIn": True, "payerCpfKnown": True})
        self.assertIsNotNone(self.db.agendamentos[APPT]["checked_in_at"])

    def test_cpf_do_cadastro_nao_serve_para_outra_pessoa_do_mesmo_numero(self):
        self.assertFalse(checkin.confirma(self.db, CLINIC, FONE, APPT_FILHA)["payerCpfKnown"])

    def test_agendamento_de_outro_numero_e_inexistente(self):
        with self.assertRaises(checkin.NaoEncontrado):
            checkin.confirma(self.db, CLINIC, OUTRO_FONE, APPT)
        with self.assertRaises(checkin.NaoEncontrado):
            checkin.confirma(self.db, CLINIC, FONE, "nao-e-uuid")


class TestCobra(Base):
    def test_pix_cobra_o_valor_gravado_no_cpf_do_cadastro(self):
        pay = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        self.assertEqual((pay["status"], pay["amountCents"], pay["pixPayload"]), (PENDENTE, 22500, "000201PIX"))
        _, pagador, metodo, valor, venc, ref = self.prov.criadas[0]
        self.assertEqual((pagador.cpf, pagador.nome, valor, venc), (CPF_OK, "Ana Souza", 22500, AGORA.date()))
        self.assertEqual(ref, pay["id"])

    def test_dinheiro_nasce_aguardando(self):
        pay = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "CASH")
        self.assertEqual(pay["status"], AGUARDANDO_DINHEIRO)

    def test_debito_usa_fatura(self):
        pay = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "DEBIT_CARD")
        self.assertTrue(pay["invoiceUrl"])
        self.assertEqual(pay["method"], "DEBIT_CARD")

    def test_sem_cpf_pede_e_valida(self):
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT_FILHA, "PIX")
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT_FILHA, "PIX", cpf="529.982.247-24")
        pay = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT_FILHA, "PIX", cpf="111.444.777-35")
        self.assertEqual(pay["status"], PENDENTE)
        self.assertEqual(self.prov.criadas[0][1].cpf, "11144477735")

    def test_cpf_da_filha_nao_vai_para_o_cadastro_da_mae(self):
        self.db.pacientes["pac1"]["cpf"] = None
        checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT_FILHA, "PIX", cpf="11144477735")
        self.assertIsNone(self.db.pacientes["pac1"]["cpf"])
        checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX", cpf=CPF_OK)
        self.assertEqual(self.db.pacientes["pac1"]["cpf"], CPF_OK)

    def test_sem_valor_vai_para_a_recepcao(self):
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT_SEM_VALOR, "PIX")
        self.assertEqual(self.prov.criadas, [])

    def test_metodo_invalido(self):
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "BOLETO")

    def test_mesmo_metodo_reaproveita_a_cobranca(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        b = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(self.prov.criadas), 1)

    def test_trocar_de_metodo_cancela_a_anterior(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        b = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "CREDIT_CARD")
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.prov.canceladas, ["pay_1"])
        self.assertEqual(self.db.pagamentos[a["id"]]["status"], CANCELADO)

    def test_trocar_depois_de_pagar_o_pix_mantem_o_pix(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        self.prov.status_remoto["pay_1"] = PAGO
        b = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "CREDIT_CARD")
        self.assertEqual((b["id"], b["status"]), (a["id"], PAGO))
        self.assertEqual(len(self.prov.criadas), 1)
        self.assertEqual(self.prov.canceladas, [])

    def test_ja_pago_nao_cobra_de_novo(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        self.db.pagamentos[a["id"]]["status"] = PAGO
        b = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "CASH")
        self.assertEqual(b["id"], a["id"])
        self.assertEqual(len(self.prov.criadas), 1)

    def test_corrida_cancela_a_cobranca_que_sobrou(self):
        original = self.db.execute_write_returning

        def corrida(sql, params=None):
            # O outro toque grava primeiro.
            self.db.pagamentos["outro"] = {"id": "outro", "clinic_id": CLINIC, "appointment_id": APPT,
                                           "method": "PIX", "amount_cents": 22500, "status": PENDENTE,
                                           "provider": "asaas", "provider_payment_id": "pay_x"}
            return original(sql, params)

        self.db.execute_write_returning = corrida
        pay = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        self.assertEqual(pay["id"], "outro")
        self.assertEqual(self.prov.canceladas, ["pay_1"])


    def test_falha_ao_gravar_cancela_a_cobranca_criada(self):
        self.db.execute_write_returning = mock.Mock(side_effect=psycopg2.OperationalError("timeout"))
        with self.assertRaises(psycopg2.OperationalError):
            checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        self.assertEqual(self.prov.canceladas, ["pay_1"])


class TestStatus(Base):
    def test_pendente_pergunta_ao_asaas(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        self.assertEqual(checkin.status(self.db, self.prov, CLINIC, FONE, a["id"])["status"], PENDENTE)
        self.prov.status_remoto["pay_1"] = PAGO
        r = checkin.status(self.db, self.prov, CLINIC, FONE, a["id"])
        self.assertEqual(r["status"], PAGO)
        self.assertIsNotNone(r["paidAt"])

    def test_outro_numero_nao_ve_o_pagamento(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        with self.assertRaises(checkin.NaoEncontrado):
            checkin.status(self.db, self.prov, CLINIC, OUTRO_FONE, a["id"])


class TestDinheiro(Base):
    def test_recepcao_da_baixa(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "CASH")
        r = checkin.marca_recebido_em_dinheiro(self.db, self.prov, CLINIC, a["id"])
        self.assertEqual(r["status"], PAGO)
        self.assertEqual(self.prov.dinheiro, [("pay_1", 22500)])

    def test_so_o_que_aguarda_dinheiro(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.marca_recebido_em_dinheiro(self.db, self.prov, CLINIC, a["id"])


class TestSimulado(Base):
    def test_so_com_provedor_simulado(self):
        from src.providers.simulated_payment_provider import SimulatedPaymentProvider
        sim = SimulatedPaymentProvider()
        a = checkin.cobra(self.db, sim, CLINIC, FONE, APPT, "PIX")
        self.assertTrue(a["simulated"])
        with self.assertRaises(checkin.NaoEncontrado):
            checkin.simula_pagamento(self.db, self.prov, CLINIC, FONE, a["id"])
        self.assertEqual(checkin.simula_pagamento(self.db, sim, CLINIC, FONE, a["id"])["status"], PAGO)


class TestSimulaNoSandbox(Base):
    def test_asaas_sandbox_confirma_la_e_marca_pago(self):
        self.prov.pode_simular = True
        self.prov.simulados = []
        self.prov.simula = lambda cid: self.prov.simulados.append(cid)
        with mock.patch.dict(os.environ, {"ASAAS_BASE_URL": "https://api-sandbox.asaas.com"}):
            a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
            self.assertTrue(a["canSimulate"])
            r = checkin.simula_pagamento(self.db, self.prov, CLINIC, FONE, a["id"])
        self.assertEqual(r["status"], PAGO)
        self.assertEqual(self.prov.simulados, ["pay_1"])

    def test_no_sandbox_cartao_nao_simula_paga_a_fatura(self):
        self.prov.pode_simular = True
        with mock.patch.dict(os.environ, {"ASAAS_BASE_URL": "https://api-sandbox.asaas.com"}):
            a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "CREDIT_CARD")
            self.assertEqual((a["simulated"], a["canSimulate"]), (True, False))
            with self.assertRaises(checkin.CheckinInvalido):
                checkin.simula_pagamento(self.db, self.prov, CLINIC, FONE, a["id"])

    def test_asaas_de_producao_nao_simula(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        with self.assertRaises(checkin.NaoEncontrado):
            checkin.simula_pagamento(self.db, self.prov, CLINIC, FONE, a["id"])


def evento(eid, tipo, cobranca):
    return {"id": eid, "event": tipo, "payment": {"id": cobranca, "status": "RECEIVED"}}


class TestWebhook(Base):
    def test_pago_e_idempotente(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        self.assertEqual(checkin.aplica_evento(self.db, self.prov, evento("evt_1", "PAYMENT_RECEIVED", "pay_1")), PAGO)
        self.assertEqual(self.db.pagamentos[a["id"]]["status"], PAGO)
        self.assertEqual(checkin.aplica_evento(self.db, self.prov, evento("evt_1", "PAYMENT_RECEIVED", "pay_1")),
                         "repetido")

    def test_evento_fora_de_ordem_nao_despaga(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        checkin.aplica_evento(self.db, self.prov, evento("evt_1", "PAYMENT_CONFIRMED", "pay_1"))
        checkin.aplica_evento(self.db, self.prov, evento("evt_2", "PAYMENT_DELETED", "pay_1"))
        self.assertEqual(self.db.pagamentos[a["id"]]["status"], PAGO)

    def test_falha_no_processamento_nao_marca_o_evento(self):
        checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        with mock.patch.object(checkin, "_processa", side_effect=RuntimeError("banco caiu")):
            with self.assertRaises(RuntimeError):
                checkin.aplica_evento(self.db, self.prov, evento("evt_1", "PAYMENT_RECEIVED", "pay_1"))
        self.assertEqual(checkin.aplica_evento(self.db, self.prov, evento("evt_1", "PAYMENT_RECEIVED", "pay_1")), PAGO)

    def test_pix_pago_depois_da_troca_vira_o_vivo(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        b = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "CREDIT_CARD")
        checkin.aplica_evento(self.db, self.prov, evento("evt_1", "PAYMENT_RECEIVED", "pay_1"))
        self.assertEqual(self.db.pagamentos[a["id"]]["status"], PAGO)
        self.assertEqual(self.db.pagamentos[b["id"]]["status"], CANCELADO)
        self.assertIn("pay_2", self.prov.canceladas)

    def test_segundo_pagamento_pago_nao_trava_a_fila(self):
        a = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "PIX")
        b = checkin.cobra(self.db, self.prov, CLINIC, FONE, APPT, "CREDIT_CARD")
        checkin.aplica_evento(self.db, self.prov, evento("evt_1", "PAYMENT_RECEIVED", "pay_2"))
        with self.assertLogs(checkin.logger, "ERROR"):
            r = checkin.aplica_evento(self.db, self.prov, evento("evt_2", "PAYMENT_RECEIVED", "pay_1"))
        self.assertEqual(r, "conflito: pagamento duplicado")
        self.assertEqual(self.db.pagamentos[a["id"]]["status"], CANCELADO)
        self.assertEqual(self.db.pagamentos[b["id"]]["status"], PAGO)
        self.assertIn("evt_2", self.db.eventos)

    def test_cobranca_desconhecida(self):
        self.assertEqual(checkin.aplica_evento(self.db, self.prov, evento("evt_9", "PAYMENT_RECEIVED", "pay_zz")),
                         "ignorado: cobrança desconhecida")


class TestHandler(unittest.TestCase):
    modulo = "src.functions.public_booking.checkin"

    def setUp(self):
        self.db = Db(cpf_cadastro=CPF_OK)
        self.prov = Provedor()
        for p in (
            mock.patch(f"{self.modulo}.require_booking_intake_api_key", return_value=("k", None)),
            mock.patch(f"{self.modulo}.PostgresService", return_value=self.db),
            mock.patch(f"{self.modulo}.provedor_ativo", return_value=self.prov),
            mock.patch(f"{self.modulo}.verify_token", side_effect=lambda c, ph, t: t == "ok"),
            mock.patch("src.services.relogio.agora_na_clinica", return_value=AGORA),
        ):
            p.start()
            self.addCleanup(p.stop)

    def chama(self, metodo, proxy, body=None, query=None):
        from src.functions.public_booking.checkin import handler
        ev = {"httpMethod": metodo, "pathParameters": {"clinicId": CLINIC, "proxy": proxy},
              "queryStringParameters": query, "headers": {},
              "body": json.dumps(body) if body is not None else None}
        r = handler(ev, None)
        return r["statusCode"], json.loads(r["body"])

    def test_fluxo(self):
        s, b = self.chama("GET", "appointments", query={"phone": "(11) 99999-0000", "token": "ok"})
        self.assertEqual(s, 200)
        appt = b["appointments"][0]["id"]
        s, b = self.chama("POST", f"appointments/{appt}/confirm", {"phone": FONE, "token": "ok"})
        self.assertEqual((s, b["payerCpfKnown"]), (200, True))
        s, b = self.chama("POST", f"appointments/{appt}/payments", {"phone": FONE, "token": "ok", "method": "PIX"})
        self.assertEqual(s, 201)
        s, b = self.chama("GET", f"payments/{b['payment']['id']}", query={"phone": FONE, "token": "ok"})
        self.assertEqual((s, b["payment"]["status"]), (200, PENDENTE))

    def test_sem_token_valido(self):
        s, _ = self.chama("GET", "appointments", query={"phone": FONE, "token": "velho"})
        self.assertEqual(s, 401)
        s, _ = self.chama("GET", "appointments", query={"phone": FONE})
        self.assertEqual(s, 400)

    def test_rota_desconhecida(self):
        self.assertEqual(self.chama("DELETE", "appointments")[0], 404)
        self.assertEqual(self.chama("GET", "../admin")[0], 404)

    def test_erros_viram_mensagem_para_a_tela(self):
        s, b = self.chama("POST", f"appointments/{APPT_SEM_VALOR}/payments",
                          {"phone": FONE, "token": "ok", "method": "PIX"})
        self.assertEqual(s, 400)
        self.assertIn("recepção", b["message"])
        s, _ = self.chama("POST", f"appointments/{uuid.uuid4()}/confirm", {"phone": FONE, "token": "ok"})
        self.assertEqual(s, 404)

    def test_sem_provedor(self):
        from src.providers.payment_provider import PagamentoIndisponivel
        with mock.patch(f"{self.modulo}.provedor_ativo", side_effect=PagamentoIndisponivel()):
            s, _ = self.chama("POST", f"appointments/{APPT}/payments", {"phone": FONE, "token": "ok", "method": "PIX"})
        self.assertEqual(s, 503)

    def test_baixa_em_dinheiro_nao_existe_na_rota_publica(self):
        """Mudou para o painel (functions/caixa), com a permissão da recepção."""
        self.assertEqual(self.chama("POST", f"payments/{uuid.uuid4()}/cash-received", {})[0], 404)


class TestWebhookHandler(unittest.TestCase):
    def chama(self, token, body):
        from src.functions.public_booking.asaas_webhook import handler
        return handler({"headers": {"Asaas-Access-Token": token} if token else {}, "body": json.dumps(body)}, None)

    def test_token(self):
        with mock.patch.dict(os.environ, {"ASAAS_WEBHOOK_TOKEN": "segredo"}):
            self.assertEqual(self.chama(None, {})["statusCode"], 401)
            self.assertEqual(self.chama("errado", {})["statusCode"], 401)
            with mock.patch("src.functions.public_booking.asaas_webhook.PostgresService"), \
                    mock.patch("src.functions.public_booking.asaas_webhook.provedor_ativo"), \
                    mock.patch("src.services.checkin.aplica_evento", return_value=PAGO):
                self.assertEqual(self.chama("segredo", evento("e", "PAYMENT_RECEIVED", "p"))["statusCode"], 200)

    def test_sem_segredo_configurado_recusa_tudo(self):
        with mock.patch.dict(os.environ, {"ASAAS_WEBHOOK_TOKEN": ""}):
            self.assertEqual(self.chama("", {})["statusCode"], 401)


class TestRota(unittest.TestCase):
    def test_router_e_interface(self):
        from src.functions.public_booking import asaas_webhook, checkin as h
        from src.functions.public_booking.router import ROUTES
        self.assertIs(ROUTES[("GET", "public/clinics/{clinicId}/checkin/{proxy+}")], h.handler)
        self.assertIs(ROUTES[("POST", "public/clinics/{clinicId}/checkin/{proxy+}")], h.handler)
        self.assertIs(ROUTES[("POST", "public/asaas/webhook")], asaas_webhook.handler)
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(raiz, "sls", "functions", "public_booking", "interface.yml"), encoding="utf-8") as f:
            yml = f.read()
        self.assertIn("path: public/clinics/{clinicId}/checkin/{proxy+}", yml)
        self.assertIn("path: public/asaas/webhook", yml)


if __name__ == "__main__":
    unittest.main()
