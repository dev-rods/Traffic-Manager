# -*- coding: utf-8 -*-
"""O site público cobra, desconta e reserva o mesmo que o agente de WhatsApp.

Antes do PRD 023 o site calculava duração no navegador (sem piso, teto, passo
nem combos), não passava pela política de desconto e criava o agendamento com
o que sobrava. Três sintomas: preço maior que o do WhatsApp para o mesmo
pedido; horário oferecido que a criação recusava (409); confirmação sem as
orientações pré-sessão.

O catálogo abaixo tem um combo de verdade (o caso da Aline, 06/10/2026):
"Virilha Completa" + "Perianal/ânus" custam R$ 270 separadas e R$ 195 juntas.
"""
import json
import os
import unittest
from datetime import datetime
from decimal import Decimal
from unittest import mock

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import carrinho
from src.services.ai_tools import ToolExecutor
from src.services.duration_rules import calcula_duracao

CLINIC = "clinica-teste-0001"
FONE = "5511999990000"
PACIENTE_COMPLETO = {"id": "00000000-0000-4000-8000-00000000p001", "name": "Maria Silva",
                     "cpf": "52998224725", "birth_date": "1990-01-01", "email": "maria@x.com"}

SVC = "11111111-1111-1111-1111-111111111111"
SVC_SEM_AREA = "22222222-2222-2222-2222-222222222222"
OUTRA_CLINICA = "99999999-9999-9999-9999-999999999999"
VIRILHA = "aaaaaaaa-0000-0000-0000-000000000001"
PERIANAL = "aaaaaaaa-0000-0000-0000-000000000002"
COMBO = "aaaaaaaa-0000-0000-0000-000000000003"
AXILAS = "aaaaaaaa-0000-0000-0000-000000000004"
INATIVA = "aaaaaaaa-0000-0000-0000-000000000005"
PROFISSIONAL = "bbbbbbbb-0000-0000-0000-000000000001"

AREAS = [
    {"id": VIRILHA, "name": "Virilha Completa"},
    {"id": PERIANAL, "name": "Perianal/ânus"},
    {"id": COMBO, "name": "Virilha Completa + ânus"},
    {"id": AXILAS, "name": "Axilas"},
]
PRECO = {VIRILHA: 17500, PERIANAL: 9500, COMBO: 19500, AXILAS: 6500}
DURACAO = {VIRILHA: 15, PERIANAL: 5, COMBO: 18, AXILAS: 5}
SERVICOS = {
    SVC: {"id": SVC, "duration_minutes": 20, "price_cents": 15000, "name": "Laser"},
    SVC_SEM_AREA: {"id": SVC_SEM_AREA, "duration_minutes": 30, "price_cents": 8000, "name": "Limpeza"},
}
REGRAS = {
    "first_session_discount_pct": 50,
    "tier_2_min_areas": 2, "tier_2_max_areas": 3, "tier_2_discount_pct": 10,
    "tier_3_min_areas": 4, "tier_3_discount_pct": 20,
}
DURACAO_REGRAS = {"floor_minutes": 15, "ceiling_minutes": 60, "step_minutes": 5, "is_active": True}


def _pares_dos_params(params):
    return list(zip(params[0::2], params[1::2]))


class Db:
    """Responde por conteúdo do SQL, com o catálogo acima."""

    def __init__(self, personalizado=None, clinica=True, datas_futuras=None, paciente="completo",
                 dono_do_cpf=None):
        self.personalizado = personalizado
        self.clinica = clinica
        self.datas_futuras = datas_futuras
        # "completo": FONE e de um paciente com os quatro dados (os testes
        # antigos nao mudam); None: numero novo; dict: cadastro parcial.
        self.paciente = paciente
        # id de outro paciente que ja tem o CPF informado (PRD 032).
        self.dono_do_cpf = dono_do_cpf
        self.consultas = []

    def execute_query(self, sql, params=None):
        self.consultas.append((sql, params))
        if "FROM scheduler.clinics" in sql:
            if not self.clinica:
                return []
            return [{"clinic_id": CLINIC, "timezone": "America/Sao_Paulo", "max_future_dates": self.datas_futuras,
                     "zapi_instance_id": "i", "zapi_instance_token": "t", "buffer_minutes": 10}]
        if "FROM scheduler.areas WHERE clinic_id" in sql:
            return AREAS
        if "total_price" in sql:
            return [{"total_price": sum(PRECO[a] for _, a in _pares_dos_params(params)) or None}]
        if "SUM(COALESCE(sa.duration_minutes" in sql:
            return [{"total": sum(DURACAO[a] for _, a in _pares_dos_params(params))}]
        if "COUNT(*) AS total" in sql and "service_areas" in sql:
            return [{"total": sum(1 for _, a in _pares_dos_params(params) if a in PRECO)}]
        if "as price_cents" in sql and "sa.area_id = %s" in sql:
            return [{"price_cents": PRECO[params[1]]}] if params[1] in PRECO else []
        if "duration_rules" in sql:
            return [DURACAO_REGRAS]
        if "discount_rules" in sql:
            return [REGRAS]
        if "FROM scheduler.patients" in sql and "cpf = %s" in sql:
            return [{"id": self.dono_do_cpf}] if self.dono_do_cpf else []
        if "FROM scheduler.patients" in sql:
            if self.paciente == "completo":
                return [PACIENTE_COMPLETO]
            return [self.paciente] if self.paciente else []
        if "FROM scheduler.professionals" in sql:
            return [{"id": params[0]}] if params[0] == PROFISSIONAL and params[1] == CLINIC else []
        if "custom_discount_pct" in sql:
            return [{"custom_discount_pct": self.personalizado}]
        if "FROM scheduler.services" in sql:
            ids = params[1:] if "clinic_id = %s" in sql else params
            return [SERVICOS[i] for i in ids if i in SERVICOS]
        return []


def par(area, svc=SVC):
    return {"service_id": svc, "area_id": area}


class TestParidadeComOAgente(unittest.TestCase):
    """O mesmo pedido, pelos dois caminhos, dá o mesmo preço, desconto e duração."""

    def pelo_agente(self, pares, primeira):
        ex = object.__new__(ToolExecutor)
        ex.db = Db()
        args = {"service_area_pairs": [dict(p) for p in pares]}
        ex._troca_por_combos(args, CLINIC)
        with mock.patch("src.services.ai_tools.e_primeira_visita", return_value=primeira):
            preco = ex._calcula_desconto(args, CLINIC, FONE, {})
        return preco, calcula_duracao(ex.db, CLINIC, args["service_area_pairs"])

    def pelo_site(self, pares, primeira):
        with mock.patch("src.services.politica_de_desconto.e_primeira_visita", return_value=primeira):
            return carrinho.cota(Db(), CLINIC, [SVC], pares, FONE)

    def test_tabela(self):
        casos = (
            ("uma_area", [par(AXILAS)], False),
            ("primeira_sessao", [par(AXILAS)], True),
            ("combo", [par(VIRILHA), par(PERIANAL)], False),
            ("combo_mais_uma_faixa_2", [par(VIRILHA), par(PERIANAL), par(AXILAS)], False),
            ("sem_combo_faixa_2", [par(VIRILHA), par(AXILAS)], False),
        )
        for nome, pares, primeira in casos:
            with self.subTest(caso=nome):
                agente, duracao_agente = self.pelo_agente(pares, primeira)
                site = self.pelo_site(pares, primeira)
                self.assertEqual(site.original_cents, agente["original_price_cents"])
                self.assertEqual(site.final_cents, agente["discounted_price_cents"])
                self.assertEqual(site.desconto.pct, agente["discount_pct"])
                self.assertEqual(site.desconto.razao, agente["discount_reason"])
                self.assertEqual(site.duracao_minutos, duracao_agente)

    def test_o_combo_e_aplicado_e_informado(self):
        c = self.pelo_site([par(VIRILHA), par(PERIANAL), par(AXILAS)], False)
        self.assertEqual([p["area_id"] for p in c.pares], [COMBO, AXILAS])
        self.assertEqual(c.combos[0]["para"], "Virilha Completa + ânus")
        self.assertEqual(c.combos[0]["economia_cents"], 7500)
        self.assertEqual(c.original_cents, 26000)
        # Duas áreas depois do combo: faixa 2, 10%.
        self.assertEqual((c.desconto.razao, c.final_cents), ("tier_2", 23400))

    def test_duracao_passa_por_passo_e_piso(self):
        """O que o navegador somava (15+5+5=25) não é o que a agenda grava:
        o combo dura 18, mais axilas 5 = 23, que o passo de 5 leva a 25; e uma
        área só de 5 minutos sobe para o piso de 15."""
        self.assertEqual(carrinho.duracao(Db(), CLINIC, [SVC], [par(VIRILHA), par(PERIANAL), par(AXILAS)]), 25)
        self.assertEqual(carrinho.duracao(Db(), CLINIC, [SVC], [par(AXILAS)]), 15)

    def test_servico_sem_area_usa_a_duracao_e_o_preco_do_servico(self):
        c = carrinho.cota(Db(), CLINIC, [SVC_SEM_AREA], [], None)
        self.assertEqual((c.duracao_minutos, c.original_cents, c.final_cents), (30, 8000, 8000))

    def test_carrinho_misto_soma_o_servico_sem_area(self):
        """Laser com axilas (5 min, R$ 65) + limpeza de pele (30 min, R$ 80):
        35 minutos e R$ 145. Antes a limpeza sumia da duração e do preço."""
        c = carrinho.cota(Db(), CLINIC, [SVC, SVC_SEM_AREA], [par(AXILAS)], None)
        self.assertEqual((c.duracao_minutos, c.original_cents, c.final_cents), (35, 14500, 14500))
        self.assertEqual(c.qtd_areas, 1)

    def test_carrinho_misto_mesma_duracao_e_preco_na_grade_e_na_criacao(self):
        from src.services.duration_rules import duracao_do_carrinho
        from src.services.politica_de_desconto import preco_de_tabela
        ids, pares = [SVC, SVC_SEM_AREA], [par(AXILAS)]
        linhas = [SERVICOS[SVC], SERVICOS[SVC_SEM_AREA]]
        self.assertEqual(duracao_do_carrinho(Db(), CLINIC, ids, pares, servicos=linhas),
                         carrinho.duracao(Db(), CLINIC, ids, pares))
        self.assertEqual(preco_de_tabela(Db(), ids, pares, servicos=linhas),
                         carrinho.cota(Db(), CLINIC, ids, pares).original_cents)

    def test_sem_telefone_so_a_faixa(self):
        with mock.patch("src.services.politica_de_desconto.e_primeira_visita", return_value=True) as primeira:
            c = carrinho.cota(Db(personalizado=Decimal("30")), CLINIC, [SVC], [par(AXILAS)], None)
        self.assertEqual((c.desconto.pct, c.desconto.razao), (0, None))
        primeira.assert_not_called()


class TestValidaCarrinho(unittest.TestCase):
    def falha(self, service_ids, pares):
        with self.assertRaises(carrinho.CarrinhoInvalido):
            carrinho.valida_carrinho(Db(), CLINIC, service_ids, pares)

    def test_valido(self):
        self.assertEqual(carrinho.valida_carrinho(Db(), CLINIC, [SVC, SVC], [par(AXILAS)]), [SVC])

    def test_vazio_ou_nao_lista(self):
        self.falha([], [])
        self.falha(None, [])
        self.falha(SVC, [])

    def test_identificador_que_nao_e_uuid(self):
        self.falha(["1; DROP TABLE"], [])
        self.falha([SVC], [par("x")])

    def test_servico_de_outra_clinica(self):
        self.falha([OUTRA_CLINICA], [])

    def test_area_de_servico_fora_do_carrinho(self):
        self.falha([SVC], [par(AXILAS, svc=SVC_SEM_AREA)])

    def test_area_inativa(self):
        self.falha([SVC], [par(INATIVA)])

    def test_area_repetida(self):
        self.falha([SVC], [par(AXILAS), par(AXILAS)])

    def test_carrinho_grande_demais(self):
        self.falha([SVC] * 1, [par(AXILAS)] * (carrinho.MAX_PARES + 1))

    def test_pares_da_query(self):
        self.assertEqual(carrinho.pares_da_query(f"{SVC}:{AXILAS}, {SVC}:{VIRILHA}"),
                         [par(AXILAS), par(VIRILHA)])
        self.assertEqual(carrinho.pares_da_query(None), [])
        with self.assertRaises(carrinho.CarrinhoInvalido):
            carrinho.pares_da_query(SVC)


SP = pytz.timezone("America/Sao_Paulo")
AGORA = SP.localize(datetime(2026, 10, 20, 14, 0))


def evento(body=None, query=None):
    return {
        "pathParameters": {"clinicId": CLINIC},
        "queryStringParameters": query,
        "body": json.dumps(body) if body is not None else None,
        "headers": {"x-api-key": "k"},
    }


def corpo(resposta):
    return json.loads(resposta["body"])


def motor_falso():
    """Agenda de 20/10 (hoje, 14h) em diante: dias 20, 22, 25, 28, 31/10 e 3/11
    com 13:30, 14:00 e 15:00; o corte de hoje tira o que já passou."""
    engine = mock.MagicMock()
    engine.datas_com_regra.return_value = [
        "2026-10-20", "2026-10-22", "2026-10-25", "2026-10-28", "2026-10-31", "2026-11-03"]

    def status(c, ds, dur, a_partir_de=None):
        out = {}
        for d in ds:
            slots = ["13:30", "14:00", "15:00"]
            minimo = (a_partir_de or {}).get(d)
            if minimo is not None:
                slots = [x for x in slots if int(x[:2]) * 60 + int(x[3:]) >= minimo]
            out[d] = {"status": "AVAILABLE" if slots else "FULL", "slots": slots}
        return out
    engine.get_days_status.side_effect = status
    return engine


class _Handler(unittest.TestCase):
    modulo = None

    def setUp(self):
        self.db = Db()
        patches = [
            mock.patch(f"{self.modulo}.require_booking_intake_api_key", return_value=("k", None)),
            mock.patch(f"{self.modulo}.PostgresService", side_effect=lambda: self.db),
            mock.patch("src.services.relogio.agora_na_clinica", return_value=AGORA),
            mock.patch("src.services.politica_de_desconto.e_primeira_visita", return_value=False),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


class TestQuote(_Handler):
    modulo = "src.functions.public_booking.quote"

    def chama(self, body):
        from src.functions.public_booking.quote import handler
        return handler(evento(body), None)

    def test_cotacao_com_combo_e_faixa(self):
        r = self.chama({"serviceIds": [SVC], "serviceAreaPairs": [
            {"serviceId": SVC, "areaId": VIRILHA}, {"serviceId": SVC, "areaId": PERIANAL},
            {"serviceId": SVC, "areaId": AXILAS}], "phone": FONE})
        self.assertEqual(r["statusCode"], 200)
        q = corpo(r)["quote"]
        self.assertEqual(q["originalPriceCents"], 26000)
        self.assertEqual(q["finalPriceCents"], 23400)
        self.assertEqual((q["discountPct"], q["discountReason"], q["areaCount"]), (10, None, 2))
        self.assertEqual(q["combos"], [{"from": ["Virilha Completa", "Perianal/ânus"],
                                        "to": "Virilha Completa + ânus", "savingsCents": 7500}])
        self.assertNotIn("duration", json.dumps(q).lower())

    def test_sem_telefone_o_motivo_vem(self):
        q = corpo(self.chama({"serviceIds": [SVC], "serviceAreaPairs": [
            {"serviceId": SVC, "areaId": VIRILHA}, {"serviceId": SVC, "areaId": AXILAS}]}))["quote"]
        self.assertEqual((q["discountPct"], q["discountReason"]), (10, "tier_2"))

    def test_com_telefone_o_motivo_nao_vem_mas_o_valor_cai(self):
        with mock.patch("src.services.politica_de_desconto.e_primeira_visita", return_value=True):
            q = corpo(self.chama({"serviceIds": [SVC], "serviceAreaPairs": [
                {"serviceId": SVC, "areaId": AXILAS}], "phone": FONE}))["quote"]
        self.assertEqual((q["originalPriceCents"], q["discountPct"], q["finalPriceCents"]), (6500, 50, 3250))
        self.assertIsNone(q["discountReason"])

    def test_telefone_invalido(self):
        self.assertEqual(self.chama({"serviceIds": [SVC], "phone": "123"})["statusCode"], 400)

    def test_carrinho_invalido(self):
        self.assertEqual(self.chama({"serviceIds": [OUTRA_CLINICA]})["statusCode"], 400)

    def test_clinica_inexistente(self):
        self.db.clinica = False
        self.assertEqual(self.chama({"serviceIds": [SVC]})["statusCode"], 404)


class TestAvailability(_Handler):
    modulo = "src.functions.public_booking.availability"

    def chama(self, query, db=None):
        from src.functions.public_booking.availability import handler
        if db is not None:
            self.db = db
        engine = motor_falso()
        with mock.patch(f"{self.modulo}.AvailabilityEngine", return_value=engine):
            return handler(evento(query=query), None), engine

    def test_duracao_vem_do_carrinho_e_as_datas_sao_as_proximas_com_horario(self):
        r, engine = self.chama({
            "serviceIds": SVC,
            "serviceAreaPairs": f"{SVC}:{VIRILHA},{SVC}:{PERIANAL},{SVC}:{AXILAS}",
        })
        self.assertEqual(r["statusCode"], 200)
        args, kwargs = engine.get_days_status.call_args
        self.assertEqual(args[2], 25)
        self.assertEqual(kwargs["a_partir_de"], {"2026-10-20": 840})
        dias = corpo(r)["days"]
        # 5 por padrão (o mesmo do bot), atravessando a virada do mês; hoje sem o que passou.
        self.assertEqual(list(dias), ["2026-10-20", "2026-10-22", "2026-10-25", "2026-10-28", "2026-10-31"])
        self.assertEqual(dias["2026-10-20"]["slots"], ["14:00", "15:00"])
        self.assertNotIn("window", corpo(r))

    def test_respeita_as_datas_futuras_da_clinica(self):
        r, _ = self.chama({"serviceIds": SVC, "serviceAreaPairs": f"{SVC}:{AXILAS}"}, db=Db(datas_futuras=6))
        self.assertEqual(list(corpo(r)["days"])[-1], "2026-11-03")

    def test_dates_do_front_antigo_e_ignorado(self):
        r, _ = self.chama({"dates": "2026-10-21,2026-10-22", "serviceIds": SVC, "serviceAreaPairs": f"{SVC}:{AXILAS}"})
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(len(corpo(r)["days"]), 5)

    def test_carrinho_misto_pede_horario_com_o_servico_sem_area(self):
        r, engine = self.chama({"serviceIds": f"{SVC},{SVC_SEM_AREA}", "serviceAreaPairs": f"{SVC}:{AXILAS}"})
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(engine.get_days_status.call_args[0][2], 35)

    def test_total_duration_legado_continua_aceito(self):
        r, engine = self.chama({"totalDuration": "40"})
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(engine.get_days_status.call_args[0][2], 40)

    def test_sem_carrinho_nem_duracao(self):
        r, _ = self.chama({})
        self.assertEqual(r["statusCode"], 400)

    def test_carrinho_de_outra_clinica(self):
        r, _ = self.chama({"serviceIds": OUTRA_CLINICA})
        self.assertEqual(r["statusCode"], 400)


class _Criacao(_Handler):
    modulo = "src.functions.public_booking.create_appointment"

    def setUp(self):
        super().setUp()
        self.service = mock.MagicMock()
        self.service.get_active_appointments_by_phone.return_value = []
        self.service.create_appointment.return_value = {
            "id": "ap1", "full_name": "Maria Silva", "appointment_date": "2026-10-22", "start_time": "15:00:00",
            "total_duration_minutes": 25, "original_price_cents": 26000,
            "final_price_cents": 23400, "discount_pct": Decimal("10"), "discount_reason": "tier_2",
        }
        self.provider = mock.MagicMock()
        self.provider.send_text.return_value = mock.MagicMock(success=True)
        self.template = mock.MagicMock()
        self.template.get_and_render.side_effect = lambda c, k, v=None: f"BOOKED {v['price']}"
        self.renderizado = lambda: self.template.get_and_render.call_args[0][2]
        for p in (
            mock.patch(f"{self.modulo}.AppointmentService.completo", return_value=self.service),
            mock.patch(f"{self.modulo}.ZApiProvider", return_value=self.provider),
            mock.patch(f"{self.modulo}.TemplateService", return_value=self.template),
            mock.patch(f"{self.modulo}.orientacoes_da_clinica", return_value="Não tome sol 48h antes."),
            mock.patch(f"{self.modulo}.AvailabilityEngine", return_value=motor_falso()),
        ):
            p.start()
            self.addCleanup(p.stop)

    def chama(self, **extra):
        from src.functions.public_booking.create_appointment import handler
        body = {
            "phone": "(11) 99999-0000", "fullName": "  Maria Silva ", "serviceIds": [SVC],
            "date": "2026-10-22", "time": "15:00",
            "serviceAreaPairs": [{"serviceId": SVC, "areaId": VIRILHA}, {"serviceId": SVC, "areaId": PERIANAL},
                                 {"serviceId": SVC, "areaId": AXILAS}],
        }
        body.update(extra)
        return handler(evento(body), None)


class TestCreate(_Criacao):
    def test_grava_com_combo_e_desconto_da_politica(self):
        r = self.chama()
        self.assertEqual(r["statusCode"], 201)
        kw = self.service.create_appointment.call_args.kwargs
        self.assertEqual(kw["phone"], FONE)
        self.assertEqual(kw["full_name"], "Maria Silva")
        self.assertEqual([p["area_id"] for p in kw["service_area_pairs"]], [COMBO, AXILAS])
        self.assertEqual((kw["discount_pct"], kw["discount_reason"]), (10, "tier_2"))
        self.assertIsNone(kw["professional_id"])

    def test_confirmacao_tem_desconto_e_orientacoes(self):
        self.chama()
        enviados = [c.args[1] for c in self.provider.send_text.call_args_list]
        self.assertEqual(enviados, [
            "BOOKED ~R$ 260,00~ → R$ 234,00 (10% off - 2 áreas)",
            "Não tome sol 48h antes.",
        ])

    def test_falha_na_confirmacao_nao_impede_as_orientacoes_nem_o_201(self):
        self.provider.send_text.side_effect = [Exception("z-api fora"), mock.MagicMock(success=True)]
        r = self.chama()
        self.assertEqual(r["statusCode"], 201)
        self.assertEqual(self.provider.send_text.call_count, 2)

    def test_data_fora_da_grade_oferecida(self):
        """03/11 tem horário, mas é a 6ª data e o site só oferece 5: a criação
        recusa o que a tela não oferece - uma requisição direta não passa pelo calendário."""
        self.assertEqual(self.chama(date="2026-11-03")["statusCode"], 400)
        self.assertEqual(self.chama(date="2026-10-21")["statusCode"], 400)
        self.service.create_appointment.assert_not_called()

    def test_horario_fora_da_grade_do_dia(self):
        self.assertEqual(self.chama(date="2026-10-22", time="16:00")["statusCode"], 400)
        self.service.create_appointment.assert_not_called()

    def test_horario_que_ja_passou_hoje(self):
        self.assertEqual(self.chama(date="2026-10-20", time="13:30")["statusCode"], 400)
        self.assertEqual(self.chama(date="2026-10-20", time="14:00")["statusCode"], 201)

    def test_entradas_invalidas(self):
        for extra in ({"time": "25:00"}, {"date": "22/10/2026"}, {"phone": "12"},
                      {"serviceIds": [OUTRA_CLINICA]}, {"fullName": "   "}):
            with self.subTest(**{k: str(v) for k, v in extra.items()}):
                self.assertEqual(self.chama(**extra)["statusCode"], 400)
        self.service.create_appointment.assert_not_called()

    def test_profissional_do_front_antigo_continua_aceito(self):
        self.chama(professionalId=PROFISSIONAL)
        self.assertEqual(self.service.create_appointment.call_args.kwargs["professional_id"], PROFISSIONAL)

    def test_profissional_de_outra_clinica_ou_inativo_e_ignorado(self):
        for pid in ("p1", "bbbbbbbb-0000-0000-0000-000000000002"):
            with self.subTest(pid=pid):
                r = self.chama(professionalId=pid)
                self.assertEqual(r["statusCode"], 201)
                self.assertIsNone(self.service.create_appointment.call_args.kwargs["professional_id"])

    def test_conflito_vira_409_e_deixa_rastro(self):
        from src.services.appointment_service import ConflictError
        self.service.create_appointment.side_effect = ConflictError("ocupado")
        with self.assertLogs("src.functions.public_booking.create_appointment", level="WARNING") as logs:
            r = self.chama()
        self.assertEqual(r["statusCode"], 409)
        self.assertIn("409", "\n".join(logs.output))
        self.provider.send_text.assert_not_called()

    def test_confirmacao_leva_o_nome_deste_agendamento(self):
        self.chama()
        self.assertEqual(self.renderizado()["full_name"], "Maria Silva")


class TestAvisoDeAgendamentoRepetido(_Criacao):
    """Número com agendamento futuro: o site pergunta antes de criar outro.
    Pede confirmação, não bloqueia."""

    def setUp(self):
        super().setUp()
        self.service.get_active_appointments_by_phone.return_value = [
            {"id": "x1", "appointment_date": "2026-10-25", "start_time": "10:00:00", "full_name": "Ana"},
            {"id": "x2", "appointment_date": "2026-10-28", "start_time": "11:00:00", "full_name": "Ana"},
        ]

    def test_sem_confirmacao_responde_409_com_a_contagem(self):
        r = self.chama()
        self.assertEqual(r["statusCode"], 409)
        corpo = json.loads(r["body"])
        self.assertEqual((corpo["code"], corpo["existingCount"]), ("HAS_FUTURE_APPOINTMENT", 2))
        self.service.create_appointment.assert_not_called()
        self.provider.send_text.assert_not_called()
        self.assertEqual(self.service.get_active_appointments_by_phone.call_args[0], (CLINIC, FONE))

    def test_resposta_nao_entrega_a_agenda_de_ninguem(self):
        """Criar não exige código: quem digita o número de outra pessoa não
        pode descobrir quando, nem quem, ela agendou."""
        corpo = self.chama()["body"]
        for vazamento in ("2026-10-25", "10:00", "Ana", "x1"):
            self.assertNotIn(vazamento, corpo)

    def test_confirmado_cria(self):
        r = self.chama(confirmDuplicate=True)
        self.assertEqual(r["statusCode"], 201)
        self.service.create_appointment.assert_called_once()

    def test_so_true_conta_como_confirmacao(self):
        for valor in ("true", 1, "sim"):
            with self.subTest(valor=valor):
                self.assertEqual(self.chama(confirmDuplicate=valor)["statusCode"], 409)


class TestFaixasDeDesconto(unittest.TestCase):
    """As faixas que o site anuncia na escolha das áreas são as que `decide`
    cobra, não o que está gravado em `tier_2_max_areas`."""

    def faixas(self, **regras):
        from src.services.politica_de_desconto import faixas_de_desconto
        return faixas_de_desconto(dict(REGRAS, **regras))

    def test_padrao(self):
        self.assertEqual(self.faixas(), [
            {"minAreas": 2, "maxAreas": 3, "pct": 10},
            {"minAreas": 4, "maxAreas": None, "pct": 20},
        ])

    def test_teto_gravado_diferente_nao_muda_o_anuncio(self):
        self.assertEqual(self.faixas(tier_2_max_areas=2)[0]["maxAreas"], 3)

    def test_so_a_faixa_2_nao_tem_teto(self):
        self.assertEqual(self.faixas(tier_3_discount_pct=0), [{"minAreas": 2, "maxAreas": None, "pct": 10}])

    def test_so_a_faixa_3(self):
        self.assertEqual(self.faixas(tier_2_discount_pct=0), [{"minAreas": 4, "maxAreas": None, "pct": 20}])

    def test_faixa_3_que_engole_a_2(self):
        self.assertEqual(self.faixas(tier_3_min_areas=2), [{"minAreas": 2, "maxAreas": None, "pct": 20}])

    def test_sem_regra(self):
        from src.services.politica_de_desconto import faixas_de_desconto
        self.assertEqual(faixas_de_desconto(None), [])

    def test_anuncio_bate_com_a_cobranca(self):
        from src.services import politica_de_desconto as politica
        faixas = self.faixas()
        for qtd in range(1, 9):
            with self.subTest(qtd=qtd):
                anunciada = next((f["pct"] for f in faixas if qtd >= f["minAreas"]
                                  and (f["maxAreas"] is None or qtd <= f["maxAreas"])), 0)
                self.assertEqual(politica.decide(Db(), CLINIC, None, qtd).pct, anunciada)


class TestBootstrapAnunciaAsFaixas(_Handler):
    modulo = "src.functions.public_booking.bootstrap"

    def chama(self):
        from src.functions.public_booking.bootstrap import handler
        return handler({"pathParameters": {"clinicId": CLINIC}, "headers": {}}, None)

    def test_com_regra(self):
        corpo = json.loads(self.chama()["body"])
        self.assertEqual([f["pct"] for f in corpo["discountTiers"]], [10, 20])

    def test_sem_regra(self):
        self.db.execute_query = lambda sql, params=None: (
            [] if "discount_rules" in sql else Db().execute_query(sql, params))
        self.assertEqual(json.loads(self.chama()["body"])["discountTiers"], [])


class TestRotaPublica(unittest.TestCase):
    """Rota nova entra na Lambda única PublicBooking (PRD 013), nos dois lados."""

    def test_router_e_interface(self):
        from src.functions.public_booking import quote
        from src.functions.public_booking.router import ROUTES
        self.assertIs(ROUTES[("POST", "public/clinics/{clinicId}/quote")], quote.handler)
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(raiz, "sls", "functions", "public_booking", "interface.yml"), encoding="utf-8") as f:
            self.assertIn("path: public/clinics/{clinicId}/quote", f.read())


if __name__ == "__main__":
    unittest.main()
