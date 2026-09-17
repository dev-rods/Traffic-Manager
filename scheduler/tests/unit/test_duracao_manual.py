# -*- coding: utf-8 -*-
"""A regra da duração manual, sem banco e sem HTTP.

O que se fixa aqui é o que o override significa: vale sobre o cálculo, não passa
pelos limites da regra da clínica, e recusa o que não é minuto.
"""
import unittest

from src.services.duracao_manual import (
    MAXIMO,
    MINIMO,
    DuracaoInvalida,
    efetiva,
    valida,
)


class TestValida(unittest.TestCase):
    def test_aceita_os_extremos_da_faixa(self):
        self.assertEqual(valida(MINIMO), 5)
        self.assertEqual(valida(MAXIMO), 480)

    def test_aceita_numero_como_texto(self):
        """O corpo HTTP pode trazer string; o formulário quase sempre traz."""
        self.assertEqual(valida("37"), 37)
        self.assertEqual(valida(" 37 "), 37)

    def test_vazio_e_nulo_sao_sem_override(self):
        """Campo limpo na tela e `null` no payload são a mesma intenção."""
        self.assertIsNone(valida(None))
        self.assertIsNone(valida(""))

    def test_recusa_fora_da_faixa(self):
        for valor in (0, 4, 481, -10):
            with self.subTest(valor=valor):
                with self.assertRaises(DuracaoInvalida):
                    valida(valor)

    def test_recusa_o_que_nao_e_minuto(self):
        for valor in ("abc", "3.5", 3.5, [], {}):
            with self.subTest(valor=valor):
                with self.assertRaises(DuracaoInvalida):
                    valida(valor)

    def test_a_mensagem_serve_para_a_atendente(self):
        """Ela chega na tela como 400. Precisa dizer o que fazer, não o stack."""
        with self.assertRaises(DuracaoInvalida) as ctx:
            valida(600)
        mensagem = str(ctx.exception)
        self.assertIn("5", mensagem)
        self.assertIn("480", mensagem)
        self.assertIn("600", mensagem)

    def test_e_um_value_error(self):
        """Os handlers convertem em 400 por ser ValueError. Dedo errado no
        formulário não pode virar 500."""
        self.assertTrue(issubclass(DuracaoInvalida, ValueError))


class TestEfetiva(unittest.TestCase):
    def test_o_manual_vence_o_calculo(self):
        self.assertEqual(efetiva(30, 75), 75)

    def test_sem_manual_vale_o_calculo(self):
        self.assertEqual(efetiva(30, None), 30)

    def test_zero_nao_e_override(self):
        """Um 0 vindo de payload malformado zeraria a sessão na agenda, e o
        silêncio disso é pior que a duração errada."""
        self.assertEqual(efetiva(30, 0), 30)

    def test_devolve_inteiro(self):
        self.assertIsInstance(efetiva(30, "75"), int)
        self.assertEqual(efetiva(30, "75"), 75)


class TestOManualIgnoraARegraDaClinica(unittest.TestCase):
    """O motivo da task. Com piso 10, teto 50 e passo 5, o override precisa
    entregar 75 e 7 intactos - senão não serve para nada."""

    def test_passa_do_teto(self):
        self.assertEqual(efetiva(30, 75), 75)

    def test_fica_abaixo_do_piso_da_regra(self):
        self.assertEqual(efetiva(30, 7), 7)

    def test_nao_arredonda_para_o_passo(self):
        self.assertEqual(efetiva(30, 37), 37)

    def test_a_regra_da_clinica_nunca_entra_na_conta(self):
        """`efetiva` não recebe as regras, e isso é de propósito: sem o
        parâmetro, ninguém consegue clampar 'só um pouquinho' mais tarde."""
        import inspect

        parametros = inspect.signature(efetiva).parameters
        self.assertEqual(list(parametros), ["calculada", "manual"])

    def test_o_modulo_nao_importa_duration_rules(self):
        """A independência é o desenho. Um import aqui seria o primeiro passo
        de volta para o teto que o override existe para furar.

        Confere os imports pela AST, não pelo texto do arquivo: o cabeçalho
        CITA duration_rules de propósito, para explicar a relação entre os dois.
        """
        import ast
        import inspect

        import src.services.duracao_manual as modulo

        arvore = ast.parse(inspect.getsource(modulo))
        importados = []
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados += [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                importados.append(no.module or "")

        self.assertEqual([m for m in importados if "duration_rules" in m], [])


if __name__ == "__main__":
    unittest.main()
