# -*- coding: utf-8 -*-
"""Os filtros de estagio e origem entram no MESMO where da listagem e da contagem (PRD 057)."""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.services.lead_service import LeadService


class TestFiltros(unittest.TestCase):
    def setUp(self):
        self.svc = LeadService(mock.MagicMock())

    def test_stages_multiplos(self):
        where, params = self.svc._filtros("c1", stages=["SUMIU", "AGUARDANDO_NOS"])
        self.assertIn("stage IN (%s, %s)", where)
        self.assertEqual(params[-2:], ["SUMIU", "AGUARDANDO_NOS"])

    def test_sources_multiplas(self):
        where, params = self.svc._filtros("c1", sources=["landing-page", "whatsapp"])
        self.assertIn("COALESCE(source, '') IN (%s, %s)", where)
        self.assertEqual(params[-2:], ["landing-page", "whatsapp"])

    def test_stage_desconhecido_e_ignorado(self):
        where, _ = self.svc._filtros("c1", stages=["INVENTADO"])
        self.assertNotIn("stage IN", where)

    def test_sem_filtros_nada_muda(self):
        where, params = self.svc._filtros("c1")
        self.assertEqual((where, params), ("clinic_id = %s", ["c1"]))

    def test_contar_por_estagio_nao_filtra_por_estagio(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [{"stage": "SUMIU", "n": 3}, {"stage": None, "n": 1}]
        r = LeadService(db).contar_por_estagio("c1", sources=["whatsapp"])
        sql = db.execute_query.call_args[0][0]
        self.assertIn("GROUP BY stage", sql)
        self.assertNotIn("stage IN", sql)
        self.assertIn("COALESCE(source, '') IN (%s)", sql)
        self.assertEqual(r, {"SUMIU": 3, "SEM_ESTAGIO": 1})

    def test_contar_leads_aceita_os_filtros_da_fila(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [{"total": 2, "convertidos": 1}]
        LeadService(db).contar_leads("c1", stages=["SUMIU"], sources=["whatsapp"])
        sql = db.execute_query.call_args[0][0]
        self.assertIn("stage IN (%s)", sql)
        self.assertIn("COALESCE(source, '') IN (%s)", sql)

    def test_ordenar_por_dias_parado(self):
        db = mock.MagicMock()
        db.execute_query.return_value = []
        LeadService(db).list_leads("c1", ordenar_por="dias_parado")
        self.assertIn("ORDER BY ultima_mensagem_em ASC NULLS LAST", db.execute_query.call_args[0][0])

    def test_ordem_padrao_continua_por_criacao(self):
        db = mock.MagicMock()
        db.execute_query.return_value = []
        LeadService(db).list_leads("c1")
        self.assertIn("ORDER BY created_at DESC, id DESC", db.execute_query.call_args[0][0])


class TestHandlerDaListagem(unittest.TestCase):
    """O handler repassa stage/source/orderBy e devolve por_estagio e dias_parado."""

    def setUp(self):
        from src.functions.lead import list as lead_list
        self.mod = lead_list
        mock.patch.object(lead_list, "PostgresService").start()
        self.servico = mock.patch.object(lead_list, "LeadService").start().return_value
        self.servico.list_leads.return_value = []
        self.servico.contar_leads.return_value = {"total": 0, "convertidos": 0, "nao_convertidos": 0}
        self.servico.contar_por_estagio.return_value = {"SUMIU": 2}
        self.servico.resumo_de_conversoes.side_effect = RuntimeError("sem resumo")
        mock.patch.object(lead_list, "require_acesso", return_value=(mock.MagicMock(), None)).start()
        mock.patch.object(lead_list, "enriquece", side_effect=lambda l, *a, **k: l).start()
        self.addCleanup(mock.patch.stopall)

    def chama(self, query):
        resposta = self.mod.handler({"pathParameters": {"clinicId": "c1"}, "queryStringParameters": query,
                                     "headers": {"x-api-key": "k"}}, None)
        self.assertEqual(resposta["statusCode"], 200)
        return json.loads(resposta["body"])

    def test_repassa_os_filtros(self):
        self.chama({"stage": "SUMIU,AGUARDANDO_NOS", "source": "whatsapp", "orderBy": "dias_parado"})
        kw = self.servico.list_leads.call_args.kwargs
        self.assertEqual(kw["stages"], ["SUMIU", "AGUARDANDO_NOS"])
        self.assertEqual(kw["sources"], ["whatsapp"])
        self.assertEqual(kw["ordenar_por"], "dias_parado")

    def test_por_estagio_vai_nos_totais(self):
        corpo = self.chama({"stage": "SUMIU"})
        self.assertEqual(corpo["totals"]["por_estagio"], {"SUMIU": 2})
        self.servico.contar_por_estagio.assert_called_once()
        self.assertNotIn("stages", self.servico.contar_por_estagio.call_args.kwargs)

    def test_dias_parado_vem_da_ultima_mensagem(self):
        from datetime import datetime, timedelta, timezone
        self.servico.list_leads.return_value = [
            {"id": "a", "ultima_mensagem_em": datetime.now(timezone.utc) - timedelta(days=9, hours=1)},
            {"id": "b", "ultima_mensagem_em": None},
        ]
        corpo = self.chama({})
        self.assertEqual([l["dias_parado"] for l in corpo["leads"]], [9, None])

    def test_falha_do_por_estagio_nao_zera_os_totais(self):
        self.servico.contar_leads.return_value = {"total": 5, "convertidos": 2, "nao_convertidos": 3}
        self.servico.contar_por_estagio.side_effect = RuntimeError("boom")
        corpo = self.chama({})
        self.assertEqual(corpo["totals"]["total"], 5)
        self.assertEqual(corpo["totals"]["por_estagio"], {})


if __name__ == "__main__":
    unittest.main()
