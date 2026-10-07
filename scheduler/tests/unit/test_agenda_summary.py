# -*- coding: utf-8 -*-
"""O resumo da agenda dia a dia, que é o que a gerência pergunta.

O dashboard antigo respondia "como foi hoje" e "quantos por dia nesta semana".
Quem gerencia uma clínica pergunta quanto entra na quinta, quanto está sendo
dado de desconto e quantas desmarcaram - por data, e para datas que ainda vão
acontecer.
"""
import os
import unittest
from datetime import date, timedelta
from unittest import mock

os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.functions.clinic import agenda_summary as mod

HOJE = date.today()


def linha(dia, confirmados=2, cancelados=0, bruto=20000, liquido=18000,
          minutos=60, perdido=0, pacientes=2):
    return {
        "dia": dia, "confirmados": confirmados, "cancelados": cancelados,
        "pacientes": pacientes, "bruto_cents": bruto, "liquido_cents": liquido,
        "minutos": minutos, "perdido_cents": perdido,
    }


def chama(linhas, query=None):
    db = mock.MagicMock()
    db.execute_query.return_value = linhas
    with mock.patch.object(mod, "PostgresService", return_value=db), \
         mock.patch.object(mod, "require_api_key", return_value=("k", None)):
        resposta = mod.handler({
            "headers": {"x-api-key": "chave-de-teste"},
            "pathParameters": {"clinicId": "clinica-1"},
            "queryStringParameters": query,
        }, None)
    import json
    return json.loads(resposta["body"]), db


class TestPorDia(unittest.TestCase):
    def test_cada_dia_traz_o_que_a_gerencia_pergunta(self):
        corpo, _ = chama([linha(HOJE)])
        dia = corpo["days"][0]

        for campo in ("confirmed", "cancelled", "gross_cents", "discount_cents",
                      "net_cents", "lost_cents", "booked_minutes",
                      "avg_ticket_cents", "cancellation_rate", "patients"):
            with self.subTest(campo=campo):
                self.assertIn(campo, dia)

    def test_desconto_e_a_diferenca_entre_bruto_e_liquido(self):
        corpo, _ = chama([linha(HOJE, bruto=20000, liquido=18000)])

        self.assertEqual(corpo["days"][0]["discount_cents"], 2000)

    def test_ticket_medio_ignora_cancelado(self):
        """Dividir pelo total incluindo cancelado daria um valor que nenhuma
        sessão custou."""
        corpo, _ = chama([linha(HOJE, confirmados=2, cancelados=3, liquido=18000)])

        self.assertEqual(corpo["days"][0]["avg_ticket_cents"], 9000)

    def test_dia_so_com_cancelamento_nao_divide_por_zero(self):
        corpo, _ = chama([linha(HOJE, confirmados=0, cancelados=2, liquido=0)])
        dia = corpo["days"][0]

        self.assertEqual(dia["avg_ticket_cents"], 0)
        self.assertEqual(dia["cancellation_rate"], 100)

    def test_perda_por_cancelamento_e_separada_do_desconto(self):
        """Desconto é escolha da clínica; cancelamento é perda. Somar os dois
        num número só esconde qual das duas está crescendo."""
        corpo, _ = chama([linha(HOJE, perdido=15000)])
        dia = corpo["days"][0]

        self.assertEqual(dia["lost_cents"], 15000)
        self.assertNotEqual(dia["lost_cents"], dia["discount_cents"])


class TestJanela(unittest.TestCase):
    def test_padrao_olha_para_frente(self):
        """A pergunta da gerência é sobre o que vem."""
        corpo, _ = chama([])

        self.assertEqual(corpo["start"], HOJE.isoformat())
        self.assertGreater(corpo["end"], corpo["start"])

    def test_passado_e_permitido(self):
        inicio = (HOJE - timedelta(days=60)).isoformat()
        corpo, _ = chama([], {"start": inicio, "end": HOJE.isoformat()})

        self.assertEqual(corpo["start"], inicio)

    def test_janela_absurda_e_limitada(self):
        """Sem teto, um start de 2020 varreria a tabela a cada abertura."""
        corpo, _ = chama([], {"start": "2020-01-01", "end": "2030-01-01"})

        self.assertEqual(
            (date.fromisoformat(corpo["end"]) - date.fromisoformat(corpo["start"])).days,
            mod.MAX_DIAS)

    def test_datas_invertidas_sao_corrigidas(self):
        corpo, _ = chama([], {"start": "2026-09-30", "end": "2026-09-01"})

        self.assertLess(corpo["start"], corpo["end"])

    def test_data_invalida_cai_no_padrao(self):
        corpo, _ = chama([], {"start": "ontem", "end": "amanha"})

        self.assertEqual(corpo["start"], HOJE.isoformat())


class TestTotal(unittest.TestCase):
    def test_soma_os_dias(self):
        corpo, _ = chama([linha(HOJE), linha(HOJE + timedelta(days=1))])

        self.assertEqual(corpo["total"]["confirmed"], 4)
        self.assertEqual(corpo["total"]["days_with_agenda"], 2)

    def test_periodo_vazio(self):
        corpo, _ = chama([])

        self.assertEqual(corpo["days"], [])
        self.assertEqual(corpo["total"]["confirmed"], 0)
        self.assertEqual(corpo["total"]["days_with_agenda"], 0)


if __name__ == "__main__":
    unittest.main()
