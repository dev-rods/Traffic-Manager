"""Duração da sessão por quantidade de áreas.

Antes a duração era a soma das durações cadastradas por área, o que dava números
irreais: 6 áreas de 10 minutos viravam 60 minutos de sessão quando na prática o
atendimento leva 35. A regra passa a ser por faixa de quantidade.

Padrão da clínica: 1 área 15min, 2-3 áreas 20min, 4-6 áreas 35min, 7+ áreas 45min.
As faixas são editáveis por clínica, como já acontece com discount_rules.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.duration_rules import DEFAULT_DURATION_RULES, duration_for_areas


class TestPadraoDaClinica(unittest.TestCase):
    def test_uma_area(self):
        self.assertEqual(duration_for_areas(1, DEFAULT_DURATION_RULES), 15)

    def test_duas_areas(self):
        self.assertEqual(duration_for_areas(2, DEFAULT_DURATION_RULES), 20)

    def test_tres_areas(self):
        self.assertEqual(duration_for_areas(3, DEFAULT_DURATION_RULES), 20)

    def test_quatro_areas(self):
        self.assertEqual(duration_for_areas(4, DEFAULT_DURATION_RULES), 35)

    def test_cinco_areas(self):
        self.assertEqual(duration_for_areas(5, DEFAULT_DURATION_RULES), 35)

    def test_seis_areas(self):
        self.assertEqual(duration_for_areas(6, DEFAULT_DURATION_RULES), 35)

    def test_sete_areas(self):
        self.assertEqual(duration_for_areas(7, DEFAULT_DURATION_RULES), 45)

    def test_muitas_areas(self):
        self.assertEqual(duration_for_areas(20, DEFAULT_DURATION_RULES), 45)


class TestBordas(unittest.TestCase):
    def test_zero_areas_usa_a_duracao_base(self):
        """Não deveria acontecer, mas agendamento sem área não pode ter duração 0."""
        self.assertEqual(duration_for_areas(0, DEFAULT_DURATION_RULES), 15)

    def test_quantidade_negativa_usa_a_base(self):
        self.assertEqual(duration_for_areas(-3, DEFAULT_DURATION_RULES), 15)

    def test_regras_none_usa_o_padrao(self):
        """Clínica sem regra cadastrada continua agendando."""
        self.assertEqual(duration_for_areas(5, None), 35)

    def test_regras_vazias_usa_o_padrao(self):
        self.assertEqual(duration_for_areas(2, {}), 20)


class TestFaixasCustomizadas(unittest.TestCase):
    def test_clinica_pode_redefinir_os_minutos(self):
        regras = dict(DEFAULT_DURATION_RULES, base_duration_minutes=25, tier_2_duration_minutes=40)

        self.assertEqual(duration_for_areas(1, regras), 25)
        self.assertEqual(duration_for_areas(3, regras), 40)

    def test_clinica_pode_redefinir_as_fronteiras(self):
        """Faixa 2 vira 2-5 e faixa 3 vira 6-10."""
        regras = dict(
            DEFAULT_DURATION_RULES,
            tier_2_min_areas=2, tier_2_max_areas=5,
            tier_3_min_areas=6, tier_3_max_areas=10,
            tier_4_min_areas=11,
        )

        self.assertEqual(duration_for_areas(5, regras), 20)
        self.assertEqual(duration_for_areas(6, regras), 35)
        self.assertEqual(duration_for_areas(11, regras), 45)

    def test_quantidade_em_buraco_entre_faixas_cai_na_faixa_anterior(self):
        """Se a clínica configurar faixas com lacuna, a duração não pode zerar.

        Ex.: faixa 2 vai até 3 e faixa 3 começa em 6. O que fazer com 4 e 5?
        Cai na última faixa cuja abertura já foi ultrapassada — nunca na base,
        que subestimaria a sessão e criaria conflito de horário na agenda.
        """
        regras = dict(DEFAULT_DURATION_RULES, tier_3_min_areas=6, tier_3_max_areas=8, tier_4_min_areas=9)

        self.assertEqual(duration_for_areas(4, regras), 20)
        self.assertEqual(duration_for_areas(5, regras), 20)

    def test_faixa_inativa_nao_e_aplicada(self):
        regras = dict(DEFAULT_DURATION_RULES, is_active=False)

        # com a regra desligada, cai no padrão do código
        self.assertEqual(duration_for_areas(5, regras), 35)


if __name__ == "__main__":
    unittest.main()
