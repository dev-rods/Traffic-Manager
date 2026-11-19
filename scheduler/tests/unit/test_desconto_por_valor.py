# -*- coding: utf-8 -*-
"""Desconto por valor em reais, e percentual com duas casas na edição (PRD 050).

Duas fontes, uma função. `discount_cents` preenchido é o desconto; o percentual
gravado ao lado é cópia para leitura, e todo recálculo de preço (criar, trocar
áreas, editar o desconto) passa por `desconto_personalizado.aplica`, que
recebe os centavos e os faz vencer o percentual.

O handler de edição fazia `int()` no percentual: 12,5 virava 12 em silêncio.
"""
import os
import re
import unittest
from decimal import Decimal
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.appointment import update as handler_mod
from src.services.appointment_service import AppointmentService
from src.services.desconto_personalizado import (
    DescontoInvalido, aplica, normaliza_centavos, pct_equivalente,
)
from src.utils.acesso import ADMIN, Identidade

CLINIC = "c"
APPT = "11111111-1111-1111-1111-111111111111"
SERVICO = "22222222-2222-2222-2222-222222222222"
_ADMIN = Identidade(papel=ADMIN, chave_mestra=True)


class TestAplicaComCentavos(unittest.TestCase):
    def test_subtracao_exata(self):
        self.assertEqual(aplica(19500, None, cents=2000), 17500)
        self.assertEqual(aplica(19500, Decimal("50"), cents=2000), 17500, "centavos vencem o percentual")

    def test_desconto_igual_ao_total_zera(self):
        self.assertEqual(aplica(19500, None, cents=19500), 0)

    def test_maior_que_o_total_e_erro_nao_zero(self):
        with self.assertRaises(DescontoInvalido) as ctx:
            aplica(19500, None, cents=19501)
        self.assertIn("195.01", str(ctx.exception))
        self.assertIn("195.00", str(ctx.exception))

    def test_sem_centavos_e_o_caminho_de_sempre(self):
        self.assertEqual(aplica(19500, Decimal("12.5")), 17062)


class TestNormalizaCentavos(unittest.TestCase):
    def test_vazio_e_nao_e_por_valor(self):
        for v in (None, "", "  "):
            self.assertEqual(normaliza_centavos(v), (True, None), repr(v))

    def test_inteiro_ou_string_de_digitos(self):
        self.assertEqual(normaliza_centavos(2000), (True, 2000))
        self.assertEqual(normaliza_centavos("2000"), (True, 2000))
        self.assertEqual(normaliza_centavos(2000.0), (True, 2000))

    def test_recusa_zero_negativo_fracao_e_lixo(self):
        for v in (0, -1, "20,00", "20.00", 1.5, "abc", True):
            self.assertEqual(normaliza_centavos(v), (False, None), repr(v))


class TestPctEquivalente(unittest.TestCase):
    def test_duas_casas_arredondando(self):
        self.assertEqual(pct_equivalente(19500, 2000), Decimal("10.26"))
        self.assertEqual(pct_equivalente(10000, 1), Decimal("0.01"))
        self.assertEqual(pct_equivalente(100000, 1), Decimal("0.00"))
        self.assertEqual(pct_equivalente(30000, 2000), Decimal("6.67"))

    def test_total_zerado(self):
        self.assertEqual(pct_equivalente(0, 1), Decimal(0))


# ───────────────────────── serviço ─────────────────────────

def _colunas_do_insert(sql):
    dentro = sql.split("scheduler.appointments (", 1)[1].split(")", 1)[0]
    return [c.strip() for c in dentro.split(",") if c.strip()]


class DbDeCriacao:
    def __init__(self):
        self.gravado = {}
        self.consultou_paciente = False

    def execute_query(self, sql, params=None):
        if "custom_discount_pct" in sql:
            self.consultou_paciente = True
            return [{"custom_discount_pct": 30}]
        if "FROM scheduler.patients" in sql:
            return [{"id": "p1", "deleted_at": None, "name": "Maria"}]
        if "FROM scheduler.services" in sql:
            return [{"id": "s1", "duration_minutes": 20, "name": "Laser", "price_cents": 19500}]
        if "duration_rules" in sql:
            return [{"floor_minutes": 10, "ceiling_minutes": 50, "step_minutes": 5, "is_active": True}]
        if "AS total" in sql:
            return [{"total": 20}]
        if "total_price" in sql:
            return [{"total_price": 19500}]
        return []

    def execute_write(self, sql, params=None):
        return 1

    def execute_write_returning(self, sql, params=None):
        if "INSERT INTO scheduler.appointments" in sql:
            self.gravado = dict(zip(_colunas_do_insert(sql), params))
        return {"id": "ap1"}


class TestCriacaoComDescontoEmReais(unittest.TestCase):
    def cria(self, **kw):
        db = DbDeCriacao()
        AppointmentService(db).create_appointment(
            clinic_id=CLINIC, phone="5511999990001", service_id="s1",
            date="2026-11-27", time="14:00",
            service_area_pairs=[{"service_id": "s1", "area_id": "a1"}], **kw)
        return db

    def test_grava_a_coluna_o_equivalente_e_o_preco(self):
        g = self.cria(discount_cents=2000, discount_reason="custom").gravado
        self.assertEqual(g["discount_cents"], 2000)
        self.assertEqual(g["discount_pct"], Decimal("10.26"))
        self.assertEqual(g["discount_reason"], "custom")
        self.assertEqual(g["final_price_cents"], 17500)

    def test_sem_razao_vira_personalizado(self):
        g = self.cria(discount_cents=500).gravado
        self.assertEqual(g["discount_reason"], "personalizado")

    def test_nao_consulta_o_combinado_da_paciente(self):
        """Quem manda reais opinou; o combinado permanente não entra."""
        db = self.cria(discount_cents=2000)
        self.assertFalse(db.consultou_paciente)

    def test_sem_desconto_em_reais_a_coluna_fica_nula(self):
        g = self.cria().gravado
        self.assertIsNone(g["discount_cents"])

    def test_maior_que_o_preco_recusa(self):
        with self.assertRaises(DescontoInvalido):
            self.cria(discount_cents=99999)


class DbDeTroca:
    """Agendamento com R$ 20 de desconto em reais; o subtotal novo é parâmetro."""

    def __init__(self, subtotal_novo, cents=2000):
        self.agendamento = {
            "id": APPT, "clinic_id": "c", "service_id": SERVICO,
            "appointment_date": "2026-11-27", "start_time": "12:30:00",
            "end_time": "12:50:00", "status": "CONFIRMED", "version": 1,
            "total_duration_minutes": 20, "manual_duration_minutes": None,
            "discount_pct": Decimal("10.26"), "discount_cents": cents,
        }
        self.subtotal = subtotal_novo
        self.escritas = []

    def execute_query(self, sql, params=None):
        if "SELECT id FROM" in sql:
            return []
        if "FROM scheduler.appointments" in sql:
            return [dict(self.agendamento)]
        if "duration_rules" in sql:
            return [{"floor_minutes": 10, "ceiling_minutes": 50, "step_minutes": 5, "is_active": True}]
        if "FROM scheduler.services" in sql:
            return [{"id": SERVICO, "duration_minutes": 15, "name": "Laser", "price_cents": 19500}]
        if "AS total" in sql:
            return [{"total": 20}]
        if "total_price" in sql:
            return [{"total_price": self.subtotal}]
        return []

    def execute_write(self, sql, params=None):
        self.escritas.append((sql, params))
        return 1

    def execute_write_returning(self, sql, params=None):
        self.escritas.append((sql, params))
        return dict(self.agendamento)

    def update_principal(self):
        for sql, params in self.escritas:
            if "UPDATE" in sql and "service_id" in sql:
                return sql, params
        raise AssertionError("sem UPDATE principal")


class TestTrocaDeAreasReaplicaOsReais(unittest.TestCase):
    def test_subtotal_novo_menos_os_mesmos_reais(self):
        db = DbDeTroca(subtotal_novo=30000)

        AppointmentService(db).update_appointment_services(
            APPT, SERVICO, [{"serviceId": "s1", "areaId": "a1"}])

        sql, params = db.update_principal()
        self.assertIn("discount_pct = %s", sql, "o equivalente tem de ser reescrito")
        self.assertIn(28000, params)
        self.assertIn(Decimal("6.67"), params)

    def test_subtotal_menor_que_o_desconto_recusa_a_troca(self):
        db = DbDeTroca(subtotal_novo=1500)
        with self.assertRaises(DescontoInvalido):
            AppointmentService(db).update_appointment_services(
                APPT, SERVICO, [{"serviceId": "s1", "areaId": "a1"}])
        self.assertEqual([s for s, _ in db.escritas if "UPDATE" in s], [], "nada gravado")

    def test_sem_reais_o_percentual_segue_mandando(self):
        db = DbDeTroca(subtotal_novo=30000, cents=None)
        db.agendamento["discount_pct"] = Decimal("12.5")

        AppointmentService(db).update_appointment_services(
            APPT, SERVICO, [{"serviceId": "s1", "areaId": "a1"}])

        _, params = db.update_principal()
        self.assertIn(26250, params)
        self.assertIn(Decimal("12.5"), params)


# ───────────────────────── handler ─────────────────────────

def _duble(servico):
    classe = mock.MagicMock()
    classe.completo.return_value = servico
    classe.return_value = servico
    return classe


def _chama(corpo, original=19500):
    servico = mock.MagicMock()
    db = mock.MagicMock()
    db.execute_query.return_value = [
        {"id": APPT, "appointment_date": "2026-11-27", "start_time": "12:30:00",
         "original_price_cents": original}
    ]
    evento = {"headers": {"x-api-key": "k"},
              "pathParameters": {"clinicId": CLINIC, "appointmentId": APPT}, "body": None}
    with mock.patch.object(handler_mod, "require_acesso", return_value=(_ADMIN, None)), \
         mock.patch.object(handler_mod, "parse_body", return_value=corpo), \
         mock.patch.object(handler_mod, "PostgresService", return_value=db), \
         mock.patch.object(handler_mod, "AppointmentService", _duble(servico)):
        resposta = handler_mod.handler(evento, None)
    return db, resposta


def _update_gravado(db):
    for chamada in db.execute_write_returning.call_args_list:
        sql, params = chamada.args
        if "UPDATE scheduler.appointments" in sql:
            campos = re.findall(r"(\w+) = %s", sql)
            return dict(zip(campos, params))
    raise AssertionError("sem UPDATE")


class TestHandlerDeEdicao(unittest.TestCase):
    def test_percentual_com_duas_casas_nao_e_mais_truncado(self):
        db, resposta = _chama({"discountPct": 12.5, "discountReason": "custom"})
        self.assertEqual(resposta["statusCode"], 200, resposta["body"])
        g = _update_gravado(db)
        self.assertEqual(g["discount_pct"], Decimal("12.50"))
        self.assertIsNone(g["discount_cents"])
        self.assertEqual(g["final_price_cents"], 17062)

    def test_percentual_com_virgula(self):
        db, resposta = _chama({"discountPct": "12,5", "discountReason": "custom"})
        self.assertEqual(resposta["statusCode"], 200, resposta["body"])
        self.assertEqual(_update_gravado(db)["discount_pct"], Decimal("12.50"))

    def test_reais_gravam_coluna_equivalente_e_preco(self):
        db, resposta = _chama({"discountCents": 2000, "discountReason": "custom"})
        self.assertEqual(resposta["statusCode"], 200, resposta["body"])
        g = _update_gravado(db)
        self.assertEqual(g["discount_cents"], 2000)
        self.assertEqual(g["discount_pct"], Decimal("10.26"))
        self.assertEqual(g["final_price_cents"], 17500)
        self.assertEqual(g["discount_reason"], "custom")

    def test_tirar_o_desconto_limpa_os_reais(self):
        db, resposta = _chama({"discountPct": 0, "discountReason": None})
        self.assertEqual(resposta["statusCode"], 200, resposta["body"])
        g = _update_gravado(db)
        self.assertEqual(g["discount_pct"], Decimal(0))
        self.assertIsNone(g["discount_cents"])
        self.assertEqual(g["final_price_cents"], 19500)

    def test_os_dois_juntos_e_400(self):
        _, resposta = _chama({"discountPct": 10, "discountCents": 100})
        self.assertEqual(resposta["statusCode"], 400)
        self.assertIn("nao os dois", resposta["body"])

    def test_reais_acima_do_preco_e_400_com_a_mensagem(self):
        _, resposta = _chama({"discountCents": 25000, "discountReason": "custom"})
        self.assertEqual(resposta["statusCode"], 400)
        self.assertIn("maior que o valor", resposta["body"])

    def test_reais_ilegiveis_e_400(self):
        for corpo in ({"discountCents": 0}, {"discountCents": "20,00"}, {"discountCents": None}):
            _, resposta = _chama(corpo)
            self.assertEqual(resposta["statusCode"], 400, corpo)

    def test_percentual_fora_da_faixa_ou_com_tres_casas_e_400(self):
        for pct in (101, -1, "12.555", "abc"):
            _, resposta = _chama({"discountPct": pct, "discountReason": "custom"})
            self.assertEqual(resposta["statusCode"], 400, pct)

    def test_reais_sem_preco_de_tabela_e_400(self):
        _, resposta = _chama({"discountCents": 2000}, original=None)
        self.assertEqual(resposta["statusCode"], 400)


class TestGuardaDoInt(unittest.TestCase):
    """A conversão do percentual é só por `normaliza_entrada`; `int()` trunca."""

    def test_nenhum_handler_converte_o_percentual_com_int(self):
        raiz = os.path.join(os.path.dirname(__file__), "..", "..", "src")
        padrao = re.compile(r"int\((new_discount_pct|body\.get\(\"discountPct\")")
        culpados = []
        for pasta, _, arquivos in os.walk(raiz):
            for nome in arquivos:
                if nome.endswith(".py"):
                    caminho = os.path.join(pasta, nome)
                    with open(caminho, encoding="utf-8") as f:
                        if padrao.search(f.read()):
                            culpados.append(os.path.relpath(caminho, raiz))
        self.assertEqual(culpados, [])


if __name__ == "__main__":
    unittest.main()
