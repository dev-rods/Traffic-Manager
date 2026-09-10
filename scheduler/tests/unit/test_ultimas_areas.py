# -*- coding: utf-8 -*-
"""A tool que evita perguntar de novo o que já sabemos.

É o que a atendente faz hoje à mão: "as mesmas áreas da última vez?". A tool
existe para o bot fazer a mesma pergunta com a resposta já na mão.

Todo caminho de dúvida devolve `encontrou: false`, porque nesse caso o bot
pergunta - que é o que ele faria de qualquer forma. Área errada faria a paciente
confirmar tratamento que não pediu.
"""
import unittest
from unittest import mock

from src.services.ai_tools import TOOL_DEFINITIONS, ToolExecutor

CLINIC = "clinicaessenciaestetica-9668a4"
FONE = "5511970522647"


def executor(respostas):
    """`respostas` é a fila devolvida por execute_query, em ordem."""
    db = mock.MagicMock()
    db.execute_query.side_effect = list(respostas)
    return ToolExecutor(db, mock.MagicMock(), mock.MagicMock()), db


def roda(respostas):
    ex, db = executor(respostas)
    return ex.execute("ultimas_areas_do_paciente", {},
                      {"clinic_id": CLINIC, "phone": FONE}), db


ULTIMA = [{"id": "ap-1", "appointment_date": "2026-08-12"}]
AREAS = [
    {"area_id": "a1", "area_name": "Axilas", "service_id": "s1", "service_name": "Laser"},
    {"area_id": "a2", "area_name": "Virilha", "service_id": "s1", "service_name": "Laser"},
]


class TestRegistrada(unittest.TestCase):
    def test_a_tool_esta_declarada_para_o_modelo(self):
        """Executor sem schema é tool que nunca é chamada."""
        nomes = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        self.assertIn("ultimas_areas_do_paciente", nomes)

    def test_o_executor_resolve_pelo_nome(self):
        resultado, _ = roda([ULTIMA, AREAS])
        self.assertNotIn("error", resultado)


class TestComHistorico(unittest.TestCase):
    def test_devolve_as_areas_da_ultima_sessao(self):
        resultado, _ = roda([ULTIMA, AREAS])

        self.assertTrue(resultado["encontrou"])
        self.assertEqual([a["nome"] for a in resultado["areas"]], ["Axilas", "Virilha"])
        self.assertEqual(resultado["data"], "2026-08-12")

    def test_traz_os_ids_que_o_book_appointment_precisa(self):
        """Sem service_id e area_id o bot teria de adivinhar na hora de agendar."""
        resultado, _ = roda([ULTIMA, AREAS])
        for area in resultado["areas"]:
            self.assertIn("area_id", area)
            self.assertIn("service_id", area)


class TestSoOlhaSessaoRealizada(unittest.TestCase):
    def test_a_query_exige_confirmada_e_passada(self):
        """Sessão futura responde outra pergunta; cancelada não tratou nada."""
        _, db = roda([ULTIMA, AREAS])
        sql = db.execute_query.call_args_list[0][0][0]

        self.assertIn("'CONFIRMED'", sql)
        self.assertIn("appointment_date < CURRENT_DATE", sql)

    def test_pega_a_mais_recente(self):
        _, db = roda([ULTIMA, AREAS])
        sql = db.execute_query.call_args_list[0][0][0]

        self.assertIn("ORDER BY a.appointment_date DESC", sql)
        self.assertIn("LIMIT 1", sql)

    def test_filtra_pela_clinica_e_pelo_telefone(self):
        _, db = roda([ULTIMA, AREAS])
        self.assertEqual(db.execute_query.call_args_list[0][0][1], (CLINIC, FONE))


class TestFalhaFechada(unittest.TestCase):
    def test_sem_historico(self):
        resultado, _ = roda([[]])
        self.assertFalse(resultado["encontrou"])
        self.assertEqual(resultado["areas"], [])

    def test_sessao_antiga_sem_area_registrada(self):
        """A importação do histórico gravou área default - não vale como
        'o que você fez da última vez'."""
        resultado, _ = roda([ULTIMA, []])
        self.assertFalse(resultado["encontrou"])

    def test_banco_fora_do_ar_nao_derruba_a_conversa(self):
        db = mock.MagicMock()
        db.execute_query.side_effect = Exception("connection pool exhausted")
        ex = ToolExecutor(db, mock.MagicMock(), mock.MagicMock())

        resultado = ex.execute("ultimas_areas_do_paciente", {},
                               {"clinic_id": CLINIC, "phone": FONE})

        self.assertFalse(resultado["encontrou"])
        self.assertNotIn("error", resultado)


if __name__ == "__main__":
    unittest.main()
