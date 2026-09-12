# -*- coding: utf-8 -*-
"""O desconto combinado com a paciente vence a politica da clinica.

NULO e ZERO sao coisas diferentes, e essa distincao e o centro do desenho:

    NULO  -> nao ha combinado; vale a politica (primeira sessao, faixas)
    ZERO  -> ha um combinado, e ele e "nenhum desconto"

Com zero como padrao as duas ficariam indistinguiveis, e ninguem descobriria o
engano olhando a tabela.
"""
import unittest
from unittest import mock

from decimal import Decimal

from src.services.desconto_personalizado import (
    RAZAO,
    do_paciente,
    normaliza_entrada,
)

CLINIC = "clinicaessenciaestetica-9668a4"
FONE = "5511970522647"


def db_com(valor, erro=False):
    db = mock.MagicMock()
    if erro:
        db.execute_query.side_effect = Exception("connection pool exhausted")
    else:
        db.execute_query.return_value = [{"custom_discount_pct": valor}]
    return db


class TestLeitura(unittest.TestCase):
    def test_paciente_com_combinado(self):
        self.assertEqual(do_paciente(db_com(30), CLINIC, FONE), Decimal(30))

    def test_combinado_com_casas_decimais(self):
        self.assertEqual(do_paciente(db_com(Decimal("12.50")), CLINIC, FONE),
                         Decimal("12.50"))

    def test_zero_e_um_combinado_legitimo(self):
        """"Esta paciente nunca recebe desconto" e uma decisao, nao ausencia."""
        self.assertEqual(do_paciente(db_com(0), CLINIC, FONE), Decimal(0))

    def test_nulo_significa_sem_combinado(self):
        self.assertIsNone(do_paciente(db_com(None), CLINIC, FONE))

    def test_paciente_inexistente(self):
        db = mock.MagicMock()
        db.execute_query.return_value = []
        self.assertIsNone(do_paciente(db, CLINIC, FONE))

    def test_so_olha_paciente_ativo_da_clinica(self):
        db = db_com(30)
        do_paciente(db, CLINIC, FONE)
        sql, params = db.execute_query.call_args[0]

        self.assertIn("deleted_at IS NULL", sql)
        self.assertEqual(params, (CLINIC, FONE))


class TestFalhaFechada(unittest.TestCase):
    """Sem resposta confiavel, vale a politica normal.

    O contrario - assumir um desconto que ninguem conferiu - daria dinheiro da
    clinica por causa de uma consulta que falhou.
    """

    def test_banco_fora_do_ar(self):
        self.assertIsNone(do_paciente(db_com(None, erro=True), CLINIC, FONE))

    def test_valor_ilegivel(self):
        self.assertIsNone(do_paciente(db_com("trinta"), CLINIC, FONE))

    def test_fora_da_faixa(self):
        """O CHECK do banco impede, mas dado antigo ou escrita manual nao passam
        por ele - e percentual acima de 100 viraria preco negativo."""
        for ruim in (-10, 101, 1000):
            with self.subTest(ruim=ruim):
                self.assertIsNone(do_paciente(db_com(ruim), CLINIC, FONE))


class TestNormalizaEntrada(unittest.TestCase):
    def test_vazio_desfaz_o_combinado(self):
        for vazio in (None, "", "   "):
            with self.subTest(vazio=vazio):
                self.assertEqual(normaliza_entrada(vazio), (True, None))

    def test_aceita_numero_e_texto_numerico(self):
        self.assertEqual(normaliza_entrada(30), (True, Decimal("30.00")))
        self.assertEqual(normaliza_entrada(" 30 "), (True, Decimal("30.00")))

    def test_zero_passa(self):
        self.assertEqual(normaliza_entrada(0), (True, Decimal("0.00")))

    def test_duas_casas_decimais(self):
        """O pedido do Andre em 11/09/2026: 12,5% e 33,33% sao combinados reais."""
        self.assertEqual(normaliza_entrada("12.5"), (True, Decimal("12.50")))
        self.assertEqual(normaliza_entrada("33.33"), (True, Decimal("33.33")))

    def test_virgula_como_separador(self):
        """E como se digita percentual em portugues. Recusar obrigaria a
        recepcao a adivinhar o formato."""
        self.assertEqual(normaliza_entrada("12,5"), (True, Decimal("12.50")))

    def test_mais_de_duas_casas_e_recusado(self):
        """A coluna e NUMERIC(5,2): a terceira casa seria truncada em silencio,
        e o combinado gravado ficaria diferente do que a clinica digitou."""
        for demais in ("12.555", "0.001", "99.999"):
            with self.subTest(demais=demais):
                self.assertFalse(normaliza_entrada(demais)[0])

    def test_recusa_fora_da_faixa_e_lixo(self):
        for ruim in (-1, 101, "abc", "30%", "100.01"):
            with self.subTest(ruim=ruim):
                self.assertFalse(normaliza_entrada(ruim)[0])


class TestRazao(unittest.TestCase):
    def test_a_razao_gravada_identifica_a_origem(self):
        """Sem razao propria, o relatorio nao distingue combinado de faixa."""
        self.assertEqual(RAZAO, "personalizado")


if __name__ == "__main__":
    unittest.main()
