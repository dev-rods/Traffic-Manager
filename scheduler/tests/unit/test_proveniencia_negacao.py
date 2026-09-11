# -*- coding: utf-8 -*-
"""O bot pode dizer que algo NAO existe, sem ganhar licenca para inventar.

Em 11/09/2026 uma paciente pediu 9h. O bot listou os horarios reais, vindos da
tool, e acrescentou "nao temos 9h nesse dia - o mais proximo e 09:45". A
mensagem inteira foi descartada: o 09:00 nao tinha respaldo, justamente porque
nao existe. Ela recebeu "vou confirmar com uma especialista".

Negar disponibilidade nao e afirma-la. Mas a isencao e uma brecha em potencial,
e a metade adversarial deste arquivo e a que importa: e ela que garante que
ninguem passa horario inventado escrevendo "nao temos" antes.

A isencao alcanca SO o valor governado pela negacao. Dispensar a frase inteira
deixaria "nao temos 9h, mas tenho 10:30" passar com o 10:30 inventado.
"""
import unittest

from src.services.proveniencia import fatos_sensiveis


def horarios_cobrados(texto):
    """Os horarios que ainda exigem respaldo de tool."""
    return sorted(
        f for f in fatos_sensiveis(texto, ano=2026)
        if ":" in f and not f.startswith(("duracao", "status"))
    )


class TestAResostaHonestaPassa(unittest.TestCase):
    def test_o_caso_real_de_11_09(self):
        texto = ("Os horarios disponiveis sao *09:45, 10:45.* "
                 "Nao temos 9h nesse dia - o mais proximo e *09:45.*")

        cobrados = horarios_cobrados(texto)

        self.assertNotIn("09:00", cobrados, "a negacao ainda exige respaldo")
        self.assertEqual(cobrados, ["09:45", "10:45"],
                         "os horarios afirmados tem de continuar sendo conferidos")

    def test_nega_dois_horarios_encadeados(self):
        self.assertEqual(horarios_cobrados("Nao temos 8h nem 9h nesse dia."), [])

    def test_outras_formas_de_negar(self):
        for texto in ("Nao tenho 9h nesse dia.",
                      "Nao ha 9h disponivel.",
                      "Nao temos 9h."):
            with self.subTest(texto=texto):
                self.assertEqual(horarios_cobrados(texto), [])


class TestABrechaNaoVaza(unittest.TestCase):
    """A metade que importa: ninguem inventa horario dizendo 'nao temos' antes."""

    def test_inventar_depois_do_mas(self):
        self.assertEqual(
            horarios_cobrados("Nao temos 9h, mas tenho 10:30 livre."), ["10:30"])

    def test_colar_um_valor_logo_apos_o_negado(self):
        """Regressao de um vazamento real desta implementacao.

        O extrator era guloso: "9h 14:00" casava como um valor so ("9h 14"), e
        mascarar o negado levava o 14:00 junto. Os minutos agora colam no
        separador.
        """
        self.assertEqual(
            horarios_cobrados("Nao temos 9h 14:00 disponivel."), ["14:00"])

    def test_virgula_nao_encadeia_negacao(self):
        """"Nao temos 8h, 17:45 esta livre" AFIRMA o 17:45."""
        self.assertEqual(
            horarios_cobrados("Nao temos 8h, 17:45 esta livre."), ["17:45"])

    def test_e_nao_encadeia_negacao(self):
        self.assertEqual(horarios_cobrados("Nao temos 8h e 10:30."), ["10:30"])

    def test_encadeamento_para_na_virgula(self):
        self.assertEqual(
            horarios_cobrados("Nao temos 8h nem 9h, tenho 17:45."), ["17:45"])

    def test_negar_e_afirmar_o_mesmo_horario(self):
        """A ocorrencia afirmada sobrevive - por isso se mascara o texto em vez
        de subtrair o valor no fim."""
        self.assertEqual(
            horarios_cobrados("Nao temos 9h. Confirmo sua sessao as 9h."), ["09:00"])

    def test_negacao_decorativa_nao_isenta_nada(self):
        self.assertEqual(
            horarios_cobrados("Nao temos problema! Seu horario e 16:20."), ["16:20"])

    def test_negacao_longe_do_valor_nao_alcanca(self):
        self.assertEqual(
            horarios_cobrados(
                "Nao temos vaga nenhuma naquele periodo da tarde entao 15:30 fica."),
            ["15:30"])

    def test_afirmacao_pura_segue_conferida(self):
        self.assertEqual(
            horarios_cobrados("Confirmo seu horario as 14:00."), ["14:00"])


if __name__ == "__main__":
    unittest.main()
