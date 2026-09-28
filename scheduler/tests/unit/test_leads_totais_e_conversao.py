# -*- coding: utf-8 -*-
"""Os contadores do painel de leads descrevem o conjunto todo, e não a página.

O handler devolvia `len(leads)` como `total`. Numa clínica com 77 leads e
`limit=50`, o card "Total de leads" mostrava 50. Pior: "Convertidos" era
contado no cliente sobre a página carregada, então a taxa de conversão saía de
uma divisão entre um numerador da página e um denominador do servidor - e era
justamente o número usado para julgar a campanha.

A segunda parte é a camada que não existia: quantas dessas conversões o Google
efetivamente recebeu. Eram 24 leads marcados como convertidos e ZERO enviados,
por semanas, sem nada na tela que dissesse isso.
"""
import os
import unittest
from datetime import datetime, timezone
from unittest import mock

os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")
os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.functions.lead import list as lead_list
from src.services.lead_service import LeadService


def evento(query=None):
    return {
        "headers": {"x-api-key": "chave-de-teste"},
        "pathParameters": {"clinicId": "clinica-1"},
        "queryStringParameters": query,
    }


class TestContagemNoBanco(unittest.TestCase):
    """contar_leads conta no banco, com os mesmos filtros da listagem."""

    def setUp(self):
        self.db = mock.MagicMock()
        self.service = LeadService(self.db)

    def test_conta_o_conjunto_inteiro(self):
        self.db.execute_query.return_value = [{"total": 77, "convertidos": 24}]

        r = self.service.contar_leads(clinic_id="clinica-1")

        self.assertEqual(r, {"total": 77, "convertidos": 24, "nao_convertidos": 53})

    def test_usa_o_mesmo_filtro_da_listagem(self):
        """Se a contagem e a listagem filtrarem diferente, a tela mostra um
        total que não corresponde às linhas exibidas."""
        self.db.execute_query.return_value = [{"total": 0, "convertidos": 0}]

        self.service.contar_leads(
            clinic_id="clinica-1", start_date="2026-09-01",
            exclude_sources=["whatsapp"])
        sql_contagem = self.db.execute_query.call_args[0][0]
        params_contagem = self.db.execute_query.call_args[0][1]

        self.db.execute_query.return_value = []
        self.service.list_leads(
            clinic_id="clinica-1", start_date="2026-09-01",
            exclude_sources=["whatsapp"])
        sql_lista = self.db.execute_query.call_args[0][0]

        for pedaco in ("clinic_id = %s", "created_at >= %s", "NOT IN"):
            with self.subTest(pedaco):
                self.assertIn(pedaco, sql_contagem)
                self.assertIn(pedaco, sql_lista)
        # os parâmetros da contagem não carregam LIMIT/OFFSET
        self.assertEqual(params_contagem, ("clinica-1", "2026-09-01", "whatsapp"))

    def test_ignora_o_filtro_booked(self):
        """Com a aba "Convertidos" aberta, `booked=true` chega ao handler. Se a
        contagem o respeitasse, o total viraria igual aos convertidos e a taxa
        mostraria sempre 100%."""
        self.db.execute_query.return_value = [{"total": 77, "convertidos": 24}]

        self.service.contar_leads(clinic_id="clinica-1")

        self.assertNotIn("booked = %s", self.db.execute_query.call_args[0][0])


class TestResumoDeConversoes(unittest.TestCase):
    def setUp(self):
        self.db = mock.MagicMock()
        self.service = LeadService(self.db)

    def test_separa_o_que_subiu_do_que_espera(self):
        self.db.execute_query.return_value = [{
            "aguardando": 21, "aguardando_cents": 544600,
            "enviadas": 0, "enviadas_cents": 0,
            "retratadas": 0, "canceladas": 8, "ultimo_envio": None,
        }]

        r = self.service.resumo_de_conversoes("clinica-1")

        self.assertEqual(r["aguardando"], 21)
        self.assertEqual(r["aguardando_cents"], 544600)
        self.assertEqual(r["enviadas"], 0)
        self.assertIsNone(r["ultimo_envio"])

    def test_nao_reimplementa_a_elegibilidade(self):
        """A regra de o que sobe tem um dono: o uploader do infra.

        Este resumo relata fato (existe / subiu / foi retratada). Se ele
        tentasse prever quais conversões o uploader aceita, seria a TERCEIRA
        cópia da regra - e a segunda já custou uma suíte verde afirmando o
        oposto da decisão tomada. Ver test_elegibilidade_tem_um_dono.
        """
        self.db.execute_query.return_value = [{
            "aguardando": 0, "aguardando_cents": 0, "enviadas": 0,
            "enviadas_cents": 0, "retratadas": 0, "canceladas": 0,
            "ultimo_envio": None,
        }]

        self.service.resumo_de_conversoes("clinica-1")
        sql = self.db.execute_query.call_args[0][0]

        self.assertNotIn("90 days", sql)
        self.assertNotIn("CURRENT_DATE", sql)


class TestEstadoPorLead(unittest.TestCase):
    def setUp(self):
        self.db = mock.MagicMock()
        self.service = LeadService(self.db)

    def test_enviado_ganha_de_aguardando(self):
        """Lead recorrente tem várias conversões. Se alguma subiu, o Google já
        conhece este lead - é isso que a coluna comunica."""
        self.db.execute_query.return_value = [
            {"lead_id": "a", "enviadas": 1, "aguardando": 2, "retratadas": 0},
            {"lead_id": "b", "enviadas": 0, "aguardando": 3, "retratadas": 0},
            {"lead_id": "c", "enviadas": 0, "aguardando": 0, "retratadas": 1},
        ]

        r = self.service.conversoes_por_lead("clinica-1", ["a", "b", "c"])

        self.assertEqual(r, {"a": "ENVIADO", "b": "AGUARDANDO", "c": "RETRATADO"})

    def test_lead_sem_conversao_fica_de_fora(self):
        """Ausência é a informação correta: não há o que enviar."""
        self.db.execute_query.return_value = []

        self.assertEqual(self.service.conversoes_por_lead("clinica-1", ["a"]), {})

    def test_lista_vazia_nao_consulta_o_banco(self):
        self.assertEqual(self.service.conversoes_por_lead("clinica-1", []), {})
        self.db.execute_query.assert_not_called()


class TestHandlerDegradaSemDerrubar(unittest.TestCase):
    """Os contadores são decoração no topo da tela. Os leads são o trabalho.

    Nenhuma falha ao montar os contadores pode custar a listagem - inclusive
    falha de TIPO, que não levanta exceção sozinha e só estoura lá no
    json.dumps, 500 na cara de quem só queria ver os leads.
    """

    def setUp(self):
        mock.patch.object(lead_list, "PostgresService").start()
        self.servico = mock.patch.object(lead_list, "LeadService").start().return_value
        self.servico.list_leads.return_value = []
        mock.patch.object(lead_list, "require_api_key",
                          return_value=("chave-de-teste", None)).start()
        mock.patch.object(lead_list, "enriquece", side_effect=lambda l, *a, **k: l).start()
        self.addCleanup(mock.patch.stopall)

    def _corpo(self):
        import json
        resposta = lead_list.handler(evento(), None)
        self.assertEqual(resposta["statusCode"], 200)
        return json.loads(resposta["body"])

    def test_caminho_feliz(self):
        self.servico.contar_leads.return_value = {
            "total": 77, "convertidos": 24, "nao_convertidos": 53}
        self.servico.resumo_de_conversoes.return_value = {
            "aguardando": 21, "aguardando_cents": 544600, "enviadas": 0,
            "enviadas_cents": 0, "retratadas": 0, "canceladas": 8,
            "ultimo_envio": datetime(2026, 9, 28, 16, 25, tzinfo=timezone.utc)}
        self.servico.conversoes_por_lead.return_value = {}

        corpo = self._corpo()

        self.assertEqual(corpo["total"], 77)
        self.assertEqual(corpo["totals"]["convertidos"], 24)
        self.assertEqual(corpo["conversions"]["aguardando"], 21)
        self.assertIn("2026-09-28", corpo["conversions"]["ultimo_envio"])

    def test_contagem_explodindo_nao_derruba_a_lista(self):
        self.servico.contar_leads.side_effect = RuntimeError("banco fora")

        corpo = self._corpo()

        self.assertEqual(corpo["leads"], [])
        self.assertIsNone(corpo["conversions"])

    def test_tipo_errado_tambem_nao_derruba(self):
        """Regressão: com MagicMock no lugar dos números, o handler devolvia
        500. O `try` pegava exceção, mas um valor de tipo estranho não levanta
        nada até o json.dumps."""
        self.servico.contar_leads.return_value = mock.MagicMock()
        self.servico.resumo_de_conversoes.return_value = mock.MagicMock()

        corpo = self._corpo()

        self.assertIsNone(corpo["conversions"])

    def test_ultimo_envio_nulo_e_normal(self):
        """Nenhuma conversão enviada ainda - o estado da Essência até hoje."""
        self.servico.contar_leads.return_value = {
            "total": 1, "convertidos": 0, "nao_convertidos": 1}
        self.servico.resumo_de_conversoes.return_value = {
            "aguardando": 0, "aguardando_cents": 0, "enviadas": 0,
            "enviadas_cents": 0, "retratadas": 0, "canceladas": 0,
            "ultimo_envio": None}
        self.servico.conversoes_por_lead.return_value = {}

        self.assertIsNone(self._corpo()["conversions"]["ultimo_envio"])


if __name__ == "__main__":
    unittest.main()
