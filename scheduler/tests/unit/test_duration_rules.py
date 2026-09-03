"""Quanto tempo dura uma sessão.

Havia cinco respostas para a mesma pergunta: as faixas por quantidade de áreas,
a soma das durações cadastradas, o SUM do fallback de reagendamento, o
max_session_minutes da clínica e o número que o agente inventava - em
02/09/2026 ele pediu horário para uma sessão de 4 minutos. Agora é uma só.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.duration_rules import (
    DEFAULT_DURATION_RULES,
    arredonda_para_passo,
    calcula_duracao,
    duracao_da_sessao,
    soma_das_areas,
)


class DbFalso:
    """Devolve a soma que o teste mandar, sem tocar em banco."""

    def __init__(self, total=0, regras=None):
        self._total = total
        self._regras = regras
        self.consultas = []

    def execute_query(self, query, params=None):
        self.consultas.append(query)
        if "duration_rules" in query:
            return [self._regras] if self._regras else []
        return [{"total": self._total}]


class TestArredondamento(unittest.TestCase):
    def test_arredonda_para_cima(self):
        """Para cima de propósito: subestimar sobrepõe agendamentos."""
        self.assertEqual(arredonda_para_passo(21, 5), 25)
        self.assertEqual(arredonda_para_passo(24, 5), 25)

    def test_multiplo_exato_nao_muda(self):
        self.assertEqual(arredonda_para_passo(25, 5), 25)

    def test_passo_invalido_devolve_intacto(self):
        """Configuração ruim não pode zerar a duração."""
        self.assertEqual(arredonda_para_passo(23, 0), 23)
        self.assertEqual(arredonda_para_passo(23, -5), 23)


class TestPisoTetoPasso(unittest.TestCase):
    def test_abaixo_do_piso_sobe_para_o_piso(self):
        self.assertEqual(duracao_da_sessao(4), 15)
        self.assertEqual(duracao_da_sessao(10), 15)

    def test_acima_do_teto_desce_para_o_teto(self):
        self.assertEqual(duracao_da_sessao(60), 50)
        self.assertEqual(duracao_da_sessao(600), 50)

    def test_no_meio_arredonda_para_multiplo_de_cinco(self):
        self.assertEqual(duracao_da_sessao(24), 25)
        self.assertEqual(duracao_da_sessao(31), 35)
        self.assertEqual(duracao_da_sessao(35), 35)

    def test_resultado_e_sempre_multiplo_do_passo(self):
        for bruto in range(0, 121):
            self.assertEqual(duracao_da_sessao(bruto) % 5, 0, f"bruto={bruto}")

    def test_resultado_esta_sempre_entre_piso_e_teto(self):
        for bruto in range(0, 121):
            self.assertGreaterEqual(duracao_da_sessao(bruto), 15)
            self.assertLessEqual(duracao_da_sessao(bruto), 50)

    def test_zero_e_none_caem_no_piso(self):
        self.assertEqual(duracao_da_sessao(0), 15)
        self.assertEqual(duracao_da_sessao(None), 15)

    def test_negativo_cai_no_piso(self):
        self.assertEqual(duracao_da_sessao(-30), 15)

    def test_idempotente(self):
        """Reaplicar sobre um valor já calculado não muda nada.

        O reagendamento passa a duração gravada por aqui de novo; se não fosse
        idempotente, cada remarcação esticaria a sessão.
        """
        for bruto in (4, 24, 37, 60, 600):
            uma = duracao_da_sessao(bruto)
            self.assertEqual(duracao_da_sessao(uma), uma)


class TestRegrasDaClinica(unittest.TestCase):
    def test_regra_propria_vence_o_padrao(self):
        regras = {"floor_minutes": 30, "ceiling_minutes": 90, "step_minutes": 10, "is_active": True}

        self.assertEqual(duracao_da_sessao(12, regras), 30)
        self.assertEqual(duracao_da_sessao(62, regras), 70)
        self.assertEqual(duracao_da_sessao(200, regras), 90)

    def test_regra_inativa_cai_no_padrao(self):
        regras = {"floor_minutes": 30, "ceiling_minutes": 90, "step_minutes": 10, "is_active": False}

        self.assertEqual(duracao_da_sessao(60, regras), 50)

    def test_campo_nulo_cai_no_padrao_daquele_campo(self):
        """Coluna nova em linha antiga não pode zerar a duração."""
        regras = {"floor_minutes": None, "ceiling_minutes": None, "step_minutes": None}

        self.assertEqual(duracao_da_sessao(24, regras), 25)

    def test_piso_acima_do_teto_o_piso_vence(self):
        """Configuração impossível degrada para sessão longa, nunca curta."""
        regras = {"floor_minutes": 40, "ceiling_minutes": 20, "step_minutes": 5}

        self.assertEqual(duracao_da_sessao(10, regras), 40)


class TestSomaDasAreas(unittest.TestCase):
    def test_sem_pares_soma_zero_sem_consultar(self):
        db = DbFalso()

        self.assertEqual(soma_das_areas(db, []), 0)
        self.assertEqual(soma_das_areas(db, None), 0)
        self.assertEqual(db.consultas, [])

    def test_ignora_par_incompleto(self):
        db = DbFalso(total=40)

        soma_das_areas(db, [{"service_id": "s1"}, {"area_id": "a1"}])

        self.assertEqual(db.consultas, [])


class TestCalculaDuracao(unittest.TestCase):
    def test_soma_das_areas_passa_por_piso_teto_e_passo(self):
        """6 áreas de 10min somam 60 e o teto corta em 50."""
        db = DbFalso(total=60)

        self.assertEqual(calcula_duracao(db, "clinica", [{"service_id": "s", "area_id": f"a{i}"} for i in range(6)]), 50)

    def test_area_unica_curta_sobe_para_o_piso(self):
        db = DbFalso(total=8)

        self.assertEqual(calcula_duracao(db, "clinica", [{"service_id": "s", "area_id": "a"}]), 15)

    def test_sem_areas_devolve_o_piso(self):
        db = DbFalso(total=0)

        self.assertEqual(calcula_duracao(db, "clinica", []), 15)


class TestPadrao(unittest.TestCase):
    def test_padrao_e_o_combinado(self):
        self.assertEqual(DEFAULT_DURATION_RULES["floor_minutes"], 15)
        self.assertEqual(DEFAULT_DURATION_RULES["ceiling_minutes"], 50)
        self.assertEqual(DEFAULT_DURATION_RULES["step_minutes"], 5)


if __name__ == "__main__":
    unittest.main()
