"""Validação das regras de duração vindas do painel.

Uma configuração inválida não estoura na hora: ela vaza para a agenda. Duração
zero cria agendamento com fim antes do início, e piso acima do teto produz uma
regra que se contradiz. Por isso a validação é no endpoint, não no cálculo.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.functions.duration_rules.update import _valida

ATUAIS = {"floor_minutes": 15, "ceiling_minutes": 50, "step_minutes": 5}


class TestMinutos(unittest.TestCase):
    def test_configuracao_valida_passa(self):
        self.assertIsNone(_valida({"floor_minutes": 15, "ceiling_minutes": 50}, ATUAIS))

    def test_duracao_zero_e_recusada(self):
        erro = _valida({"floor_minutes": 0}, ATUAIS)

        self.assertIsNotNone(erro)
        self.assertIn("maior que zero", erro)

    def test_negativo_e_recusado(self):
        self.assertIsNotNone(_valida({"ceiling_minutes": -10}, ATUAIS))

    def test_texto_e_recusado(self):
        erro = _valida({"step_minutes": "cinco"}, ATUAIS)

        self.assertIn("inteiro", erro)

    def test_booleano_nao_passa_por_inteiro(self):
        """True é int em Python; aceitar viraria passo de 1 minuto."""
        self.assertIsNotNone(_valida({"step_minutes": True}, ATUAIS))


class TestCoerencia(unittest.TestCase):
    def test_piso_acima_do_teto_e_recusado(self):
        erro = _valida({"floor_minutes": 60, "ceiling_minutes": 50}, ATUAIS)

        self.assertIn("floor_minutes", erro)

    def test_piso_isolado_e_conferido_contra_o_teto_gravado(self):
        """Sem os valores atuais, mudar só o piso escaparia da checagem."""
        erro = _valida({"floor_minutes": 90}, ATUAIS)

        self.assertIsNotNone(erro)

    def test_passo_maior_que_o_teto_e_recusado(self):
        """Passo de 60 com teto de 50 não produz nenhum valor possível."""
        self.assertIsNotNone(_valida({"step_minutes": 60}, ATUAIS))

    def test_piso_igual_ao_teto_e_valido(self):
        """Sessão de duração fixa é configuração legítima."""
        self.assertIsNone(_valida({"floor_minutes": 30, "ceiling_minutes": 30}, ATUAIS))

    def test_sem_valores_atuais_nao_quebra(self):
        """Clínica sem linha gravada ainda pode receber a primeira config."""
        self.assertIsNone(_valida({"floor_minutes": 15, "ceiling_minutes": 50}, None))


class TestIsActive(unittest.TestCase):
    def test_is_active_nao_e_validado_como_minuto(self):
        self.assertIsNone(_valida({"is_active": False}, ATUAIS))


if __name__ == "__main__":
    unittest.main()
