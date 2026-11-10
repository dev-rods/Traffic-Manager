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

    def test_termo_na_listagem(self):
        """PRD 047: o LATERAL do termo entra no SELECT com a versao como
        primeiro parametro; o envelope diz se ha versao configurada."""
        with mock.patch(f"{MODULO}.consentimento.versao", return_value="2026-12"):
            r, chamadas = self.chama({})
        self.assertEqual(r["statusCode"], 200, r["body"])
        sql_count, params_count = chamadas[0]
        sql, params = chamadas[1]
        self.assertNotIn("patient_consents", sql_count)
        self.assertIn("patient_consents", sql)
        self.assertIn("ct.consent_status", sql)
        self.assertIn("GROUP BY p.id, ct.consent_status", sql)
        self.assertEqual(params[0], "2026-12")
        self.assertEqual(sql.count("%s"), len(params), sql)
        self.assertTrue(json.loads(r["body"])["consent_enabled"])

    def test_filtro_do_termo(self):
        for valor, trecho in (("missing", "ct.consent_status IS NULL OR ct.consent_status = 'SIGNING'"),
                              ("ok", "ct.consent_status IN ('SIGNED', 'PAPER')")):
            with self.subTest(valor), mock.patch(f"{MODULO}.consentimento.versao", return_value="2026-12"):
                r, chamadas = self.chama({"consent": valor})
                self.assertEqual(r["statusCode"], 200, r["body"])
                for sql, params in chamadas:
                    self.assertIn("patient_consents", sql)
                    self.assertIn(trecho, sql)
                    self.assertEqual(params[0], "2026-12")
                    self.assertEqual(sql.count("%s"), len(params), sql)

    def test_filtro_do_termo_ignorado(self):
        """Valor desconhecido, ou clinica sem versao do termo: a lista nao filtra."""
        with mock.patch(f"{MODULO}.consentimento.versao", return_value="2026-12"):
            r, chamadas = self.chama({"consent": "qualquer"})
        self.assertNotIn("ct.consent_status", chamadas[0][0])
        self.assertNotIn("ct.consent_status IS NULL", chamadas[1][0])
        with mock.patch(f"{MODULO}.consentimento.versao", return_value=""):
            r, chamadas = self.chama({"consent": "missing"})
        self.assertEqual(r["statusCode"], 200, r["body"])
        self.assertNotIn("ct.consent_status IS NULL", chamadas[1][0])
        self.assertFalse(json.loads(r["body"])["consent_enabled"])


if __name__ == "__main__":
    unittest.main()
