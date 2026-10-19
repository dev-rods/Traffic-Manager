# -*- coding: utf-8 -*-
"""A conexão volta ao pool limpa quando a query falha.

Sem o rollback, uma escrita que batia num índice único devolvia a conexão com a
transação abortada, e a próxima consulta nela falhava com "current transaction
is aborted". Se nem o rollback funciona, a conexão é descartada.
"""
import unittest
from unittest import mock

from src.services.db import postgres


def conexao(falha_no_execute=None, falha_no_rollback=None):
    conn = mock.MagicMock()
    conn.closed = 0
    cursor = conn.cursor.return_value.__enter__.return_value
    if falha_no_execute:
        cursor.execute.side_effect = falha_no_execute
    if falha_no_rollback:
        conn.rollback.side_effect = falha_no_rollback
    cursor.rowcount = 1
    return conn


class TestRollback(unittest.TestCase):

    def servico(self, conn):
        pool = mock.MagicMock()
        pool.getconn.return_value = conn
        with mock.patch.object(postgres, "_get_connection_pool", return_value=pool):
            return postgres.PostgresService(), pool

    def test_sucesso_nao_faz_rollback_e_devolve_a_conexao(self):
        conn = conexao()
        svc, pool = self.servico(conn)
        self.assertEqual(svc.execute_write("UPDATE x SET y = 1"), 1)
        conn.rollback.assert_not_called()
        pool.putconn.assert_called_once_with(conn, close=False)

    def test_falha_faz_rollback_e_propaga_o_erro(self):
        conn = conexao(falha_no_execute=RuntimeError("duplicate key"))
        svc, pool = self.servico(conn)
        with self.assertRaises(RuntimeError):
            svc.execute_write("INSERT INTO x VALUES (1)")
        conn.rollback.assert_called_once()
        pool.putconn.assert_called_once_with(conn, close=False)

    def test_rollback_que_falha_descarta_a_conexao(self):
        conn = conexao(falha_no_execute=RuntimeError("duplicate key"),
                       falha_no_rollback=RuntimeError("server closed"))
        svc, pool = self.servico(conn)
        with self.assertRaises(RuntimeError) as ctx:
            svc.execute_query("SELECT 1")
        self.assertIn("duplicate key", str(ctx.exception))
        pool.putconn.assert_called_once_with(conn, close=True)

    def test_conexao_ja_fechada_nao_tenta_rollback_e_e_descartada(self):
        conn = conexao(falha_no_execute=RuntimeError("connection lost"))
        conn.closed = 2
        svc, pool = self.servico(conn)
        with self.assertRaises(RuntimeError):
            svc.execute_query("SELECT 1")
        conn.rollback.assert_not_called()
        pool.putconn.assert_called_once_with(conn, close=True)


if __name__ == "__main__":
    unittest.main()
