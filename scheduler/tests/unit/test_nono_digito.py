# -*- coding: utf-8 -*-
"""O mesmo celular escrito com e sem o nono dígito.

Em 05/09/2026 a lead "Julia Dalçóquio" aparecia como sem contato tendo conversa
desenvolvida no WhatsApp. O z-api guardava `554797053940` e o formulário da
landing page gravou `5547997053940`: 12 dígitos contra 13, mesma pessoa,
casamento exato nunca acha.

Medido na base: 3 dos 37 leads do site estavam invisíveis só por isso.
"""
import unittest

from src.utils.phone import mesmo_numero, normalize_phone, variantes_do_numero


class TestVariantes(unittest.TestCase):
    def test_o_caso_da_julia(self):
        self.assertEqual(variantes_do_numero("5547997053940"),
                         {"5547997053940", "554797053940"})

    def test_o_caminho_inverso(self):
        self.assertEqual(variantes_do_numero("554797053940"),
                         {"5547997053940", "554797053940"})

    def test_sao_paulo_nao_perde_o_nove(self):
        """Em 11-28 o nono dígito é obrigatório: tirar produz outra pessoa."""
        for ddd in ("11", "19", "21", "28"):
            with self.subTest(ddd=ddd):
                self.assertEqual(variantes_do_numero(f"55{ddd}999990000"),
                                 {f"55{ddd}999990000"})

    def test_ddds_reais_do_caso(self):
        """47 (SC), 91 (PA) e 83 (PB) - os três leads que sumiram."""
        for numero in ("5547997053940", "5591984121868", "5583986157993"):
            with self.subTest(numero=numero):
                self.assertEqual(len(variantes_do_numero(numero)), 2)

    def test_fixo_nao_ganha_nove(self):
        """8 dígitos que não começam com 9 são fixo; inventar o 9 daria um
        celular que pode ser de outra pessoa."""
        self.assertEqual(variantes_do_numero("554733334444"),
                         {"554733334444", "5547933334444"})

    def test_lixo_nao_explode(self):
        self.assertEqual(variantes_do_numero(""), set())
        self.assertEqual(variantes_do_numero(None), set())
        self.assertEqual(variantes_do_numero("123"), {"55123"})


class TestMesmoNumero(unittest.TestCase):
    def test_julia(self):
        self.assertTrue(mesmo_numero("5547997053940", "554797053940"))

    def test_formatos_diferentes_da_mesma_pessoa(self):
        self.assertTrue(mesmo_numero("+55 (47) 99705-3940", "554797053940"))

    def test_pessoas_diferentes(self):
        self.assertFalse(mesmo_numero("5547997053940", "5547997053941"))

    def test_sao_paulo_nao_casa_por_engano(self):
        """O risco de afrouxar demais: dois números de SP que só diferem pelo 9
        são pessoas diferentes."""
        self.assertFalse(mesmo_numero("5511999990000", "551199990000"))


class TestNormalizeNaoMudou(unittest.TestCase):
    """`normalize_phone` continua devolvendo UM valor.

    Ela é a chave de identidade do lead e do paciente; devolver duas formas
    tornaria a chave ambígua. A tolerância é para comparar, não para gravar.
    """

    def test_devolve_um_valor_so(self):
        self.assertEqual(normalize_phone("5547997053940"), "5547997053940")
        self.assertEqual(normalize_phone("554797053940"), "554797053940")


if __name__ == "__main__":
    unittest.main()
