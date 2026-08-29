"""Validação das regras de duração vindas do painel.

Uma configuração inválida não estoura na hora: ela vaza para a agenda. Duração
zero cria agendamento com fim antes do início, e faixas fora de ordem fazem todo
mundo cair na última faixa. Por isso a validação é no endpoint, não no cálculo.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.functions.duration_rules.update import _valida


class TestMinutos(unittest.TestCase):
    def test_configuracao_valida_passa(self):
        self.assertIsNone(_valida({"base_duration_minutes": 15, "tier_2_duration_minutes": 20}))

    def test_duracao_zero_e_recusada(self):
        erro = _valida({"base_duration_minutes": 0})

        self.assertIn("maior que zero", erro)

    def test_duracao_negativa_e_recusada(self):
        self.assertIsNotNone(_valida({"tier_3_duration_minutes": -10}))

    def test_texto_e_recusado(self):
        erro = _valida({"base_duration_minutes": "quinze"})

        self.assertIn("inteiro", erro)

    def test_booleano_nao_passa_como_inteiro(self):
        """True é int em Python; sem checagem explícita viraria 1 minuto."""
        self.assertIsNotNone(_valida({"base_duration_minutes": True}))


class TestFronteiras(unittest.TestCase):
    def test_max_menor_que_min_e_recusado(self):
        erro = _valida({"tier_2_min_areas": 5, "tier_2_max_areas": 3})

        self.assertIn("nao pode ser menor", erro)

    def test_faixas_em_ordem_crescente_passam(self):
        self.assertIsNone(_valida({
            "tier_2_min_areas": 2, "tier_3_min_areas": 4, "tier_4_min_areas": 7,
        }))

    def test_faixa_3_antes_da_faixa_2_e_recusada(self):
        erro = _valida({"tier_2_min_areas": 5, "tier_3_min_areas": 3})

        self.assertIn("deve ser maior", erro)

    def test_faixas_iguais_sao_recusadas(self):
        """Empate deixaria uma faixa inalcançável."""
        self.assertIsNotNone(_valida({"tier_3_min_areas": 4, "tier_4_min_areas": 4}))

    def test_valida_so_o_que_foi_informado(self):
        """O update é parcial: campo ausente não pode invalidar o payload."""
        self.assertIsNone(_valida({"tier_4_min_areas": 7}))

    def test_payload_vazio_passa(self):
        self.assertIsNone(_valida({}))

    def test_is_active_nao_e_tratado_como_numero(self):
        self.assertIsNone(_valida({"is_active": False}))


if __name__ == "__main__":
    unittest.main()
