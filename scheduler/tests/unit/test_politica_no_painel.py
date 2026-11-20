# -*- coding: utf-8 -*-
"""A política da clínica vale também no agendamento feito pelo painel (PRD 053).

Até 20/11/2026 o painel era a única porta que não passava por
`politica_de_desconto.decide`: sem opinião da recepção, o serviço aplicava só
o combinado da paciente. Primeira sessão e faixa por áreas nunca entravam.
Agora as três portas (bot, site, painel) gravam a mesma decisão.

"Sem desconto" escolhido no painel chega como pct 0 com razão "none", e é o
que impede a política de entrar por cima. Na edição, `discountPolicy: true`
re-decide depois da troca de áreas. A cotação é `POST appointments?simular=true`.
"""
import json
import os
import unittest
from decimal import Decimal
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.appointment import create as create_mod
from src.functions.appointment import update as update_mod
from src.services.appointment_service import AppointmentService, ConflictError
from src.services.carrinho import Cotacao
from src.services.politica_de_desconto import (
    Decisao, RAZAO_NENHUM, RAZOES_DA_POLITICA, razao_e_da_politica,
)
from src.utils.acesso import ADMIN, Identidade

CLINIC = "c"
FONE = "5511999990001"
APPT = "11111111-1111-1111-1111-111111111111"
_ADMIN = Identidade(papel=ADMIN, chave_mestra=True)

REGRAS_COM_ESTREIA = {"first_session_discount_pct": 10, "tier_2_min_areas": 2,
                      "tier_2_discount_pct": 15, "tier_3_min_areas": 5,
                      "tier_3_discount_pct": 20, "is_active": True}


def _colunas_do_insert(sql):
    dentro = sql.split("scheduler.appointments (", 1)[1].split(")", 1)[0]
    return [c.strip() for c in dentro.split(",") if c.strip()]


class DbDeCriacao:
    """Banco falso da criação. `sessoes_confirmadas` alimenta `e_primeira_visita`;
    `regras` é a linha de `discount_rules` (None = clínica sem política)."""

    def __init__(self, regras=REGRAS_COM_ESTREIA, sessoes_confirmadas=0, personalizado=None):
        self.regras, self.sessoes, self.personalizado = regras, sessoes_confirmadas, personalizado
        self.consultas = []
        self.gravado = {}

    def execute_query(self, sql, params=None):
        self.consultas.append(sql)
        if "custom_discount_pct" in sql:
            return [{"custom_discount_pct": self.personalizado}]
        if "discount_rules" in sql:
            return [dict(self.regras)] if self.regras else []
        if "COUNT(*) AS total" in sql and "scheduler.appointments" in sql:
            return [{"total": self.sessoes}]
        if "FROM scheduler.patients" in sql:
            return [{"id": "p1", "deleted_at": None, "name": "Maria"}]
        if "FROM scheduler.services" in sql:
            return [{"id": "s1", "duration_minutes": 20, "name": "Laser", "price_cents": 20000}]
        if "duration_rules" in sql:
            return [{"floor_minutes": 10, "ceiling_minutes": 50, "step_minutes": 5, "is_active": True}]
        if "AS total" in sql:
            return [{"total": 20}]
        if "total_price" in sql:
            return [{"total_price": 20000}]
        return []

    def execute_write(self, sql, params=None):
        return 1

    def execute_write_returning(self, sql, params=None):
        if "INSERT INTO scheduler.appointments" in sql:
            self.gravado = dict(zip(_colunas_do_insert(sql), params))
        return {"id": "ap1"}

    def consultou_a_politica(self):
        return any("discount_rules" in q for q in self.consultas)


def cria(db, areas=1, **kw):
    pares = [{"service_id": "s1", "area_id": f"a{i}"} for i in range(areas)]
    AppointmentService(db).create_appointment(
        clinic_id=CLINIC, phone=FONE, service_id="s1",
        date="2026-11-27", time="14:00", service_area_pairs=pares, **kw)
    return db.gravado


class TestCriacaoPelaPolitica(unittest.TestCase):
    def test_sem_opiniao_a_politica_decide_primeira_sessao(self):
        g = cria(DbDeCriacao(sessoes_confirmadas=0))
        self.assertEqual(g["discount_pct"], 10)
        self.assertEqual(g["discount_reason"], "first_session")
        self.assertEqual(g["final_price_cents"], 18000)

    def test_sem_opiniao_a_faixa_de_areas_vence_quando_e_maior(self):
        g = cria(DbDeCriacao(sessoes_confirmadas=0), areas=5)
        self.assertEqual(g["discount_pct"], 20)
        self.assertEqual(g["discount_reason"], "tier_3")

    def test_quem_ja_tem_sessao_confirmada_nao_e_estreia(self):
        g = cria(DbDeCriacao(sessoes_confirmadas=1), areas=1)
        self.assertEqual(g["discount_pct"], 0)
        self.assertIsNone(g["discount_reason"], "razão None é 'a política não deu nada'")
        self.assertEqual(g["final_price_cents"], 20000)

    def test_o_combinado_da_paciente_segue_vencendo(self):
        g = cria(DbDeCriacao(sessoes_confirmadas=0, personalizado=30))
        self.assertEqual(g["discount_pct"], 30)
        self.assertEqual(g["discount_reason"], "personalizado")

    def test_clinica_sem_politica_nao_desconta(self):
        g = cria(DbDeCriacao(regras=None))
        self.assertEqual(g["discount_pct"], 0)
        self.assertIsNone(g["discount_reason"])

    def test_sem_desconto_de_proposito_nao_consulta_a_politica(self):
        """'none' é a escolha da recepção: a política não entra por cima."""
        db = DbDeCriacao(sessoes_confirmadas=0)
        g = cria(db, discount_pct=0, discount_reason=RAZAO_NENHUM)
        self.assertFalse(db.consultou_a_politica())
        self.assertEqual(g["discount_pct"], 0)
        self.assertEqual(g["discount_reason"], "none")
        self.assertEqual(g["final_price_cents"], 20000)

    def test_escolha_explicita_tambem_nao_consulta(self):
        db = DbDeCriacao(sessoes_confirmadas=0)
        g = cria(db, discount_pct=Decimal("12.5"), discount_reason="custom")
        self.assertFalse(db.consultou_a_politica())
        self.assertEqual(g["discount_reason"], "custom")


# ───────────────────────── aplica_politica ─────────────────────────

class DbDaEdicao:
    def __init__(self, qtd_areas, original=20000, versao=3, regras=REGRAS_COM_ESTREIA, sessoes=1):
        self.qtd_areas, self.original, self.versao, self.regras, self.sessoes = (
            qtd_areas, original, versao, regras, sessoes)
        self.escritas = []
        self.responde_update = True

    def execute_query(self, sql, params=None):
        if "qtd_areas" in sql:
            return [{"clinic_id": CLINIC, "original_price_cents": self.original,
                     "version": self.versao, "phone": FONE, "qtd_areas": self.qtd_areas}]
        if "custom_discount_pct" in sql:
            return [{"custom_discount_pct": None}]
        if "discount_rules" in sql:
            return [dict(self.regras)]
        if "COUNT(*) AS total" in sql:
            return [{"total": self.sessoes}]
        return []

    def execute_write_returning(self, sql, params=None):
        self.escritas.append((sql, params))
        return {"id": APPT} if self.responde_update else None


class TestAplicaPolitica(unittest.TestCase):
    def test_re_decide_pela_quantidade_de_areas_atual(self):
        db = DbDaEdicao(qtd_areas=5)
        AppointmentService(db).aplica_politica(APPT)
        sql, params = db.escritas[0]
        self.assertIn("discount_cents = NULL", sql)
        self.assertEqual(params[:3], (20, "tier_3", 16000))
        self.assertEqual(params[3:], (APPT, 3), "optimistic lock com a versão lida")

    def test_politica_sem_desconto_grava_zero_e_razao_nula(self):
        """Razão None, não 'none': 'none' é escolha da recepção."""
        db = DbDaEdicao(qtd_areas=1, sessoes=1)
        AppointmentService(db).aplica_politica(APPT)
        _, params = db.escritas[0]
        self.assertEqual(params[:3], (0, None, 20000))

    def test_versao_batida_recusa(self):
        db = DbDaEdicao(qtd_areas=2)
        db.responde_update = False
        with self.assertRaises(ConflictError):
            AppointmentService(db).aplica_politica(APPT)


class TestRazoes(unittest.TestCase):
    def test_as_da_politica(self):
        for r in RAZOES_DA_POLITICA:
            self.assertTrue(razao_e_da_politica(r), r)
        for r in ("custom", "personalizado", "partnership", RAZAO_NENHUM, None):
            self.assertFalse(razao_e_da_politica(r), r)


# ───────────────────────── handlers ─────────────────────────

def _post(corpo, query=None, servico=None):
    db = mock.MagicMock()
    classe = mock.MagicMock()
    classe.completo.return_value = servico or mock.MagicMock()
    evento = {"headers": {"x-api-key": "k"}, "queryStringParameters": query, "body": None}
    with mock.patch.object(create_mod, "require_acesso", return_value=(_ADMIN, None)), \
         mock.patch.object(create_mod, "clinica_confere", return_value=True), \
         mock.patch.object(create_mod, "parse_body", return_value=corpo), \
         mock.patch.object(create_mod, "PostgresService", return_value=db), \
         mock.patch.object(create_mod, "AppointmentService", classe):
        r = create_mod.handler(evento, None)
    return r["statusCode"], json.loads(r["body"])


CORPO_OK = {"clinicId": CLINIC, "phone": FONE, "serviceId": "s1", "date": "2026-11-27",
            "time": "14:00", "serviceAreaPairs": [{"serviceId": "s1", "areaId": "a1"}]}


class TestHandlerDeCriacao(unittest.TestCase):
    def test_none_com_desconto_e_contradicao(self):
        codigo, corpo = _post({**CORPO_OK, "discountPct": 10, "discountReason": "none"})
        self.assertEqual(codigo, 400)
        self.assertIn("none", corpo["message"])
        codigo, _ = _post({**CORPO_OK, "discountCents": 500, "discountReason": "none"})
        self.assertEqual(codigo, 400)

    def test_none_com_zero_passa_ao_servico(self):
        servico = mock.MagicMock()
        servico.create_appointment.return_value = {"id": APPT}
        codigo, _ = _post({**CORPO_OK, "discountPct": 0, "discountReason": "none"}, servico=servico)
        self.assertEqual(codigo, 201)
        self.assertEqual(servico.create_appointment.call_args.kwargs["discount_reason"], "none")

    def test_simular_cota_sem_criar(self):
        cotacao = Cotacao(pares=[{"service_id": "s1", "area_id": "a1"}], combos=[], duracao_minutos=20,
                          original_cents=20000, final_cents=18000,
                          desconto=Decisao(10, "first_session", True), qtd_areas=1)
        servico = mock.MagicMock()
        with mock.patch.object(create_mod.carrinho, "valida_carrinho", return_value=["s1"]), \
             mock.patch.object(create_mod.carrinho, "cota", return_value=cotacao):
            codigo, corpo = _post({"clinicId": CLINIC, "phone": FONE, "serviceId": "s1",
                                   "serviceAreaPairs": [{"serviceId": "s1", "areaId": "a1"}]},
                                  query={"simular": "true"}, servico=servico)
        self.assertEqual(codigo, 200, corpo)
        self.assertEqual(corpo["quote"], {
            "originalPriceCents": 20000, "discountPct": 10.0, "discountReason": "first_session",
            "finalPriceCents": 18000, "areaCount": 1, "isFirst": True})
        servico.create_appointment.assert_not_called()

    def test_simular_sem_telefone_e_sem_data_passa(self):
        """A cotação não exige phone/date/time: é só a pergunta 'quanto fica'."""
        cotacao = Cotacao(pares=[], combos=[], duracao_minutos=0, original_cents=20000,
                          final_cents=20000, desconto=Decisao(0, None, False), qtd_areas=1)
        with mock.patch.object(create_mod.carrinho, "valida_carrinho", return_value=["s1"]), \
             mock.patch.object(create_mod.carrinho, "cota", return_value=cotacao):
            codigo, corpo = _post({"clinicId": CLINIC, "serviceIds": ["s1"]}, query={"simular": "1"})
        self.assertEqual(codigo, 200, corpo)
        self.assertIsNone(corpo["quote"]["discountReason"])
        self.assertFalse(corpo["quote"]["isFirst"])

    def test_simular_com_telefone_invalido_e_400(self):
        codigo, _ = _post({"clinicId": CLINIC, "phone": "abc", "serviceIds": ["s1"]},
                          query={"simular": "true"})
        self.assertEqual(codigo, 400)


def _put(corpo):
    servico = mock.MagicMock()
    servico.update_appointment_services.return_value = {}
    classe = mock.MagicMock()
    classe.completo.return_value = servico
    db = mock.MagicMock()
    db.execute_query.return_value = [{"id": APPT, "appointment_date": "2026-11-27",
                                      "start_time": "12:30:00", "original_price_cents": 20000}]
    evento = {"headers": {"x-api-key": "k"}, "pathParameters": {"appointmentId": APPT}, "body": None}
    with mock.patch.object(update_mod, "require_acesso", return_value=(_ADMIN, None)), \
         mock.patch.object(update_mod, "parse_body", return_value=corpo), \
         mock.patch.object(update_mod, "PostgresService", return_value=db), \
         mock.patch.object(update_mod, "AppointmentService", classe):
        r = update_mod.handler(evento, None)
    return r["statusCode"], json.loads(r["body"]), servico


class TestHandlerDeEdicao(unittest.TestCase):
    def test_discount_policy_re_decide_depois_das_areas(self):
        codigo, corpo, servico = _put({"serviceId": "s1",
                                       "serviceAreaPairs": [{"serviceId": "s1", "areaId": "a1"}],
                                       "discountPolicy": True})
        self.assertEqual(codigo, 200, corpo)
        nomes = [c[0] for c in servico.method_calls]
        self.assertLess(nomes.index("update_appointment_services"), nomes.index("aplica_politica"),
                        "a política lê o preço de tabela das áreas NOVAS")
        servico.aplica_politica.assert_called_once_with(APPT)

    def test_discount_policy_sozinho_tambem_re_decide(self):
        """Trocar de Personalizado para Política sem mexer nas áreas."""
        codigo, _, servico = _put({"discountPolicy": True})
        self.assertEqual(codigo, 200)
        servico.aplica_politica.assert_called_once_with(APPT)

    def test_discount_policy_com_desconto_e_400(self):
        codigo, corpo, _ = _put({"discountPolicy": True, "discountPct": 10})
        self.assertEqual(codigo, 400)
        self.assertIn("nao os dois", corpo["message"])
        codigo, _, _ = _put({"discountPolicy": True, "discountCents": 100})
        self.assertEqual(codigo, 400)

    def test_none_com_desconto_e_400(self):
        codigo, _, _ = _put({"discountPct": 10, "discountReason": "none"})
        self.assertEqual(codigo, 400)

    def test_none_com_zero_grava_a_razao(self):
        codigo, corpo, _ = _put({"discountPct": 0, "discountReason": "none"})
        self.assertEqual(codigo, 200, corpo)


if __name__ == "__main__":
    unittest.main()
