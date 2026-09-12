# -*- coding: utf-8 -*-
"""O CPF que a pessoa dita no WhatsApp chega ao cadastro.

O bot pede nome, nascimento, CPF e e-mail antes de agendar, e a pessoa
respondia. Mesmo assim, dos 272 pacientes da Essência, 3 tinham CPF - e os 3
já eram pacientes antes de agendar.

`_salva_cadastro_do_paciente` faz UPDATE e rodava ANTES de `create_appointment`,
que é quem cria o paciente. Para quem agenda pela primeira vez o UPDATE acertava
zero linhas, e os dados sumiam sem erro, sem log e sem teste vermelho.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"


# A trava de areas consulta as areas da clinica e a transcricao da conversa.
# Aqui a paciente pede "axilas" em voz alta, que e o caminho normal - sem isso
# `book_appointment` recusa, e com razao.
AREAS = [{"id": "a1", "name": "Axilas"}]
CONVERSA = {"turnos": [{"role": "user", "content": "quero fazer axilas"}]}


def executor(rowcount=1):
    db = mock.MagicMock()
    db.execute_write.return_value = rowcount
    # So a consulta de areas e roteada; o resto segue MagicMock como antes,
    # senao `duration_rules` recebe a lista de areas no lugar da duracao.
    db.execute_query.side_effect = lambda sql, params=None: (
        AREAS if "FROM scheduler.areas" in sql else mock.MagicMock())
    ex = object.__new__(ToolExecutor)
    ex.db = db
    ex.appointment_service = mock.MagicMock()
    ex.appointment_service.create_appointment.return_value = {"id": "ap1"}
    ex.availability_engine = mock.MagicMock()
    return ex


class TestOrdemDaGravacao(unittest.TestCase):
    """O paciente precisa existir antes do UPDATE que o completa."""

    def test_o_cadastro_e_gravado_depois_de_criar_o_agendamento(self):
        ex = executor()
        ordem = []
        ex.appointment_service.create_appointment.side_effect = (
            lambda **kw: (ordem.append("cria_agendamento"), {"id": "ap1"})[1])
        original = ex._salva_cadastro_do_paciente
        ex._salva_cadastro_do_paciente = (
            lambda *a, **k: (ordem.append("salva_cadastro"), original(*a, **k))[1])

        ex._tool_book_appointment({
            "date": "2026-09-23", "time": "14:00",
            "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}],
            "full_name": "Maria Silva", "cpf": "079.039.845-19",
            "birth_date": "1999-12-29", "email": "m@x.com",
        }, CLINIC, PHONE, dict(CONVERSA))

        self.assertEqual(ordem, ["cria_agendamento", "salva_cadastro"],
                         "o UPDATE do cadastro rodou antes de o paciente existir")


class TestGravacao(unittest.TestCase):
    def test_cpf_vai_so_com_digitos(self):
        """Guardar como veio faria a busca depender de a pessoa ter digitado
        com ponto ou sem."""
        ex = executor()
        ex._salva_cadastro_do_paciente(CLINIC, PHONE, cpf="079.039.845-19")

        params = ex.db.execute_write.call_args[0][1]
        self.assertIn("07903984519", params)

    def test_sem_dado_nenhum_nao_toca_no_banco(self):
        ex = executor()
        ex._salva_cadastro_do_paciente(CLINIC, PHONE)

        ex.db.execute_write.assert_not_called()

    def test_coalesce_preserva_o_que_ja_existe(self):
        """A pessoa pode informar parte numa conversa e o resto em outra."""
        ex = executor()
        ex._salva_cadastro_do_paciente(CLINIC, PHONE, cpf="07903984519")

        sql = ex.db.execute_write.call_args[0][0]
        self.assertEqual(sql.count("COALESCE"), 3)

    def test_update_sem_efeito_vira_aviso(self):
        """Zero linhas era o defeito antigo. Sem o aviso ele volta invisível."""
        ex = executor(rowcount=0)

        with self.assertLogs("src.services.ai_tools", level="WARNING") as log:
            ex._salva_cadastro_do_paciente(CLINIC, PHONE, cpf="07903984519")

        self.assertIn("nao encontrado", " ".join(log.output))

    def test_falha_no_cadastro_nao_derruba_o_agendamento(self):
        """Perder a sessão por causa de um CPF mal formatado seria pior."""
        ex = executor()
        ex.db.execute_write.side_effect = RuntimeError("banco fora")

        ex._salva_cadastro_do_paciente(CLINIC, PHONE, cpf="07903984519")


if __name__ == "__main__":
    unittest.main()
