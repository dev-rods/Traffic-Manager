# -*- coding: utf-8 -*-
"""A lista de pacientes monta o SQL com `{where}` e `{having}` numa f-string.

Em 06/11/2026 o PR #173 trocou `CURRENT_DATE` por `HOJE_SQL` com um patch que
escapou as chaves da f-string: `{where}` virou o texto literal `{where}` e a
rota respondeu 500 em produção ("not all arguments converted during string
formatting"). Este teste executa o handler com um banco falso e confere o SQL
que sai: nenhum marcador literal, a data de Brasília no lugar de
`CURRENT_DATE`, e o número de `%s` igual ao de parâmetros.
"""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.patient import list as h
from src.services import relogio

MODULO = "src.functions.patient.list"


class Db:
    def __init__(self):
        self.chamadas = []

    def execute_query(self, sql, params=None):
        self.chamadas.append((sql, params))
        if "COUNT(*) as total" in sql:
            return [{"total": 0}]
        return []


def evento(query):
    return {"httpMethod": "GET", "pathParameters": {"clinicId": "clinica-teste-0001"},
            "queryStringParameters": query, "headers": {}}


class TestSql(unittest.TestCase):
    def chama(self, query):
        db = Db()
        identidade = mock.Mock(user_id="u1", nome="Recepção")
        with mock.patch(f"{MODULO}.require_acesso", return_value=(identidade, None)), \
             mock.patch(f"{MODULO}.PostgresService", return_value=db), \
             mock.patch(f"{MODULO}.para_o_staff", side_effect=lambda ident, corpo: corpo):
            r = h.handler(evento(query), None)
        return r, db.chamadas

    def test_sem_filtro(self):
        r, chamadas = self.chama({"page": "1", "per_page": "20"})
        self.assertEqual(r["statusCode"], 200, r["body"])
        self.assertEqual(len(chamadas), 2)
        for sql, params in chamadas:
            self.assertNotIn("{where}", sql)
            self.assertNotIn("{having}", sql)
            self.assertNotIn("CURRENT_DATE", sql)
            self.assertEqual(sql.count("%s"), len(params), sql)
        self.assertIn("appointment_date >= " + relogio.HOJE_SQL, chamadas[1][0])

    def test_filtro_de_proxima_visita(self):
        for valor in ("with", "without"):
            with self.subTest(valor):
                r, chamadas = self.chama({"next_visit": valor})
                self.assertEqual(r["statusCode"], 200, r["body"])
                sql, params = chamadas[0]
                self.assertIn("HAVING", sql)
                self.assertIn(relogio.HOJE_SQL, sql)
                self.assertEqual(sql.count("%s"), len(params), sql)


if __name__ == "__main__":
    unittest.main()
