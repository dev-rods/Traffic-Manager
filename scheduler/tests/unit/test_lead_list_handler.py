# -*- coding: utf-8 -*-
"""O handler de listagem repassa `excludeSource` para a query.

Este e o ponto de falha silenciosa do fix: se o handler lesse outro nome de
parametro, o front continuaria mandando `excludeSource=whatsapp`, o filtro
nunca aplicaria e a tela voltaria a mostrar quem chegou direto no WhatsApp -
sem erro, sem log, sem teste vermelho.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.functions.lead import list as lead_list


def evento(query=None):
    return {
        "headers": {"x-api-key": "chave-de-teste"},
        "pathParameters": {"clinicId": "clinica-1"},
        "queryStringParameters": query,
    }


class TestExcludeSourceNoHandler(unittest.TestCase):
    def setUp(self):
        mock.patch.object(lead_list, "PostgresService").start()
        self.servico = mock.patch.object(lead_list, "LeadService").start().return_value
        self.servico.list_leads.return_value = []
        mock.patch.object(lead_list, "require_api_key",
                          return_value=("chave-de-teste", None)).start()
        self.addCleanup(mock.patch.stopall)

    def _chama(self, query=None):
        resposta = lead_list.handler(evento(query), None)
        self.assertEqual(resposta["statusCode"], 200)
        return self.servico.list_leads.call_args.kwargs

    def test_o_nome_do_parametro_e_o_que_o_front_manda(self):
        self.assertEqual(self._chama({"excludeSource": "whatsapp"})["exclude_sources"],
                         ["whatsapp"])

    def test_aceita_varias_origens_separadas_por_virgula(self):
        kwargs = self._chama({"excludeSource": "whatsapp, importacao"})
        self.assertEqual(kwargs["exclude_sources"], ["whatsapp", "importacao"])

    def test_sem_o_parametro_nao_exclui_nada(self):
        for query in (None, {}, {"excludeSource": ""}):
            with self.subTest(query=query):
                self.assertEqual(self._chama(query)["exclude_sources"], [])

    def test_nao_atrapalha_os_outros_filtros(self):
        kwargs = self._chama({"excludeSource": "whatsapp", "booked": "true",
                              "limit": "100"})
        self.assertEqual(kwargs["exclude_sources"], ["whatsapp"])
        self.assertIs(kwargs["booked"], True)
        self.assertEqual(kwargs["limit"], 100)


if __name__ == "__main__":
    unittest.main()
