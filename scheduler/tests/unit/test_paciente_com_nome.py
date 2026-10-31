# -*- coding: utf-8 -*-
"""Paciente criado pelo agendamento nasce com nome.

Descoberto em 08/09/2026 importando o histórico: `_get_or_create_patient`
inseria só clínica e telefone. Todo paciente novo nascia anônimo, e a agenda
mostrava a linha sem nome - dois assim ficaram no banco desde antes.

Não era limitação de dados: o `full_name` chegava até `create_appointment` e era
descartado na porta da função. Valia para o bot e para o painel.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.appointment_service import AppointmentService


class TestPacienteNasceComNome(unittest.TestCase):
    def setUp(self):
        self.db = mock.MagicMock()
        self.service = AppointmentService(self.db)

    def _cria(self, existentes, nome="Maria Silva"):
        self.db.execute_query.return_value = existentes
        self.db.execute_write_returning.return_value = {"id": "p1", "name": nome}
        return self.service._get_or_create_patient("clinica-1", "5511999990000", nome)

    def test_paciente_novo_leva_o_nome(self):
        self._cria([])

        sql, params = self.db.execute_write_returning.call_args[0]
        self.assertIn("INSERT INTO scheduler.patients", sql)
        self.assertIn("name", sql)
        self.assertIn("Maria Silva", params)

    def test_sem_nome_o_insert_grava_nulo_e_nao_string_vazia(self):
        """`name = ''` passaria em toda checagem de "tem nome" e esconderia o
        cadastro incompleto."""
        self.db.execute_query.return_value = []
        self.db.execute_write_returning.return_value = {"id": "p1"}

        self.service._get_or_create_patient("clinica-1", "5511999990000", "   ")

        params = self.db.execute_write_returning.call_args[0][1]
        self.assertIn(None, params)

    def test_cadastro_vazio_e_preenchido_na_primeira_chance(self):
        """Os anônimos que já estão no banco não podem ficar assim para sempre."""
        self._cria([{"id": "p1", "phone": "5511999990000", "name": None,
                     "deleted_at": None}])

        sql, params = self.db.execute_write_returning.call_args[0]
        self.assertIn("UPDATE scheduler.patients", sql)
        self.assertIn("Maria Silva", params)

    def test_nome_existente_nao_e_sobrescrito(self):
        """Quem está no sistema pode ter sido corrigido à mão. O nome que vem no
        agendamento é o que a pessoa digitou no WhatsApp naquele dia."""
        self.db.execute_query.return_value = [
            {"id": "p1", "phone": "5511999990000", "name": "Maria S. Oliveira",
             "deleted_at": None}]

        devolvido = self.service._get_or_create_patient(
            "clinica-1", "5511999990000", "maria")

        self.db.execute_write_returning.assert_not_called()
        self.assertEqual(devolvido["name"], "Maria S. Oliveira")

    def test_sem_nome_novo_nao_toca_no_cadastro(self):
        self.db.execute_query.return_value = [
            {"id": "p1", "phone": "5511999990000", "name": None, "deleted_at": None}]

        self.service._get_or_create_patient("clinica-1", "5511999990000", None)

        self.db.execute_write_returning.assert_not_called()

    def test_o_nome_chega_ate_aqui_a_partir_do_agendamento(self):
        """O elo que estava quebrado: `create_appointment` recebia `full_name` e
        não repassava."""
        import inspect
        fonte = inspect.getsource(AppointmentService.create_appointment)

        self.assertIn("_get_or_create_patient(clinic_id, phone, full_name, cpf, birth_date, email)", fonte)


class TestCadastroPeloSite(unittest.TestCase):
    """PRD 032: CPF, nascimento e e-mail entram junto; o que existe não é tocado."""

    def setUp(self):
        self.db = mock.MagicMock()
        self.db.execute_write_returning.return_value = {"id": "p1"}
        self.service = AppointmentService(self.db)

    def test_paciente_novo_nasce_com_os_quatro(self):
        self.db.execute_query.return_value = []
        self.service._get_or_create_patient("c1", "5511999990000", "Maria", "52998224725", "1990-01-01", "m@x.com")
        sql, params = self.db.execute_write_returning.call_args[0]
        self.assertIn("INSERT INTO scheduler.patients", sql)
        for coluna in ("cpf", "birth_date", "email"):
            self.assertIn(coluna, sql)
        self.assertEqual(params, ("c1", "5511999990000", "Maria", "52998224725", "1990-01-01", "m@x.com"))

    def test_existente_so_completa_o_vazio(self):
        self.db.execute_query.return_value = [
            {"id": "p1", "name": "Maria S.", "cpf": "11122233344", "birth_date": None, "email": "", "deleted_at": None}]
        self.service._get_or_create_patient("c1", "5511999990000", "maria", "52998224725", "1990-01-01", "m@x.com")
        sql, params = self.db.execute_write_returning.call_args[0]
        self.assertIn("UPDATE scheduler.patients", sql)
        # COALESCE(existente, novo): o SQL decide, e o teste confere que o
        # existente vem primeiro em cada coluna.
        for coluna in ("name", "cpf", "email"):
            self.assertIn(f"COALESCE(NULLIF({coluna}, ''), %s)", sql)
        self.assertIn("COALESCE(birth_date, %s::date)", sql)
        self.assertEqual(params[:4], ("maria", "52998224725", "1990-01-01", "m@x.com"))

    def test_existente_completo_nao_e_tocado(self):
        self.db.execute_query.return_value = [
            {"id": "p1", "name": "Maria", "cpf": "11122233344", "birth_date": "1990-01-01",
             "email": "m@x.com", "deleted_at": None}]
        self.service._get_or_create_patient("c1", "5511999990000", "Outra", "52998224725", "2000-01-01", "o@x.com")
        self.db.execute_write_returning.assert_not_called()

    def test_sem_dados_novos_nao_toca(self):
        self.db.execute_query.return_value = [
            {"id": "p1", "name": "Maria", "cpf": None, "birth_date": None, "email": None, "deleted_at": None}]
        self.service._get_or_create_patient("c1", "5511999990000", "Maria", None, None, None)
        self.db.execute_write_returning.assert_not_called()

    def test_restaurado_tambem_completa(self):
        self.db.execute_query.return_value = [
            {"id": "p1", "name": None, "cpf": None, "birth_date": None, "email": None, "deleted_at": "2026-01-01"}]
        self.service._get_or_create_patient("c1", "5511999990000", "Maria", "52998224725", "1990-01-01", "m@x.com")
        sql, params = self.db.execute_write_returning.call_args[0]
        self.assertIn("deleted_at = NULL", sql)
        self.assertEqual(params[:4], ("Maria", "52998224725", "1990-01-01", "m@x.com"))


if __name__ == "__main__":
    unittest.main()
