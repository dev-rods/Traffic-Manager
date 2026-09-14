# -*- coding: utf-8 -*-
"""A tool que diz a idade na data da sessão - em dias, anos e maioridade.

O modelo não calcula idade. Ele erra data e erra com convicção: o bloco
CALENDÁRIO existe porque ele se enrolava com dia da semana. Aqui a conta é do
código e a resposta diz de onde veio a data de nascimento, para ele não afirmar
idade a partir de um cadastro que não existe.
"""
import os
import unittest
from datetime import date

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor

CTX = {"clinic_id": "c1", "phone": "5511999999999"}


class BancoFake:
    def __init__(self, nascimento=None):
        self.nascimento = nascimento

    def execute_query(self, sql, params=None):
        if "birth_date" in sql:
            return [{"birth_date": self.nascimento}] if self.nascimento else []
        return []


def executa(args, nascimento_no_cadastro=None):
    executor = ToolExecutor(BancoFake(nascimento_no_cadastro),
                            availability_engine=None, appointment_service=None)
    return executor.execute("calculate_patient_age", args, CTX)


class TestAContaNaDataDaSessao(unittest.TestCase):
    def test_idade_em_dias_e_em_anos(self):
        r = executa({"birth_date": "2008-11-05", "appointment_date": "2026-09-23"})
        self.assertEqual(r["age_in_days"], 6531)
        self.assertEqual(r["age_in_years"], 17)
        self.assertTrue(r["is_minor"])
        self.assertEqual(r["reference_date"], "2026-09-23")

    def test_maior_de_idade(self):
        r = executa({"birth_date": "1994-05-11", "appointment_date": "2026-09-23"})
        self.assertFalse(r["is_minor"])
        self.assertLess(r["days_until_18"], 0)

    def test_o_caso_de_virada(self):
        """17 hoje, 18 na sessão: a resposta muda com a data de referência."""
        antes = executa({"birth_date": "2008-09-24", "appointment_date": "2026-09-23"})
        depois = executa({"birth_date": "2008-09-24", "appointment_date": "2026-09-25"})
        self.assertTrue(antes["is_minor"])
        self.assertFalse(depois["is_minor"])

    def test_quantos_dias_faltam_para_os_18(self):
        r = executa({"birth_date": "2008-09-30", "appointment_date": "2026-09-23"})
        self.assertEqual(r["days_until_18"], 7)


class TestDeOndeVemONascimento(unittest.TestCase):
    def test_usa_o_cadastro_quando_nao_veio_na_chamada(self):
        r = executa({"appointment_date": "2026-09-23"}, nascimento_no_cadastro=date(2010, 1, 1))
        self.assertEqual(r["birth_date"], "2010-01-01")
        self.assertEqual(r["birth_date_origem"], "cadastro")
        self.assertTrue(r["is_minor"])

    def test_o_que_veio_na_conversa_tem_prioridade(self):
        r = executa({"birth_date": "05/11/2008", "appointment_date": "2026-09-23"},
                    nascimento_no_cadastro=date(1990, 1, 1))
        self.assertEqual(r["birth_date"], "2008-11-05")
        self.assertEqual(r["birth_date_origem"], "informada na conversa")

    def test_sem_nascimento_manda_perguntar(self):
        """Sem data ninguém sabe a idade - e supor maioridade é o erro caro."""
        r = executa({"appointment_date": "2026-09-23"})
        self.assertEqual(r["error"], "sem_data_de_nascimento")
        self.assertIn("Pergunte a data de nascimento", r["o_que_fazer"])

    def test_data_impossivel_nao_vira_idade(self):
        r = executa({"birth_date": "30/02/2008", "appointment_date": "2026-09-23"})
        self.assertEqual(r["error"], "sem_data_de_nascimento")

    def test_nascimento_depois_da_sessao_e_erro_de_digitacao(self):
        r = executa({"birth_date": "2027-01-01", "appointment_date": "2026-09-23"})
        self.assertEqual(r["error"], "data_de_nascimento_invalida")
        self.assertIn("Confirme a data de nascimento", r["o_que_fazer"])


class TestSemDataDeSessao(unittest.TestCase):
    def test_cai_em_hoje_e_diz_qual_data_usou(self):
        """Data ainda não escolhida: hoje é a aproximação, e o retorno declara."""
        from src.services.calendario import hoje_brt

        r = executa({"birth_date": "1994-05-11"})
        self.assertEqual(r["reference_date"], hoje_brt().isoformat())


if __name__ == "__main__":
    unittest.main()
