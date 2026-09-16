# -*- coding: utf-8 -*-
"""Toda área do catálogo pode ser nomeada por uma paciente.

Este teste existe por causa de 16/09/2026. A paciente pediu "Virilha completa +
Ânus"; a área chama-se "Virilha Comp. + ânus" no banco. A trava comparava a
string inteira do cadastro, "virilha comp anus" não é subsequência de "virilha
completa anus", e a área ficou inalcançável: nenhuma frase que um ser humano
escreveria a liberaria, nunca. O bot perguntou cinco vezes, recebeu cinco
respostas certas, recusou as cinco e entregou a conversa a uma atendente, que
teve de pedir desculpa pelo defeito.

Nada disso quebrou. Não houve exceção, não houve teste vermelho: a trava
recusava exatamente como fora escrita. O que faltava era alguém perguntar se o
cadastro REAL passava por ela.

É o que este teste faz, e é por isso que ele mora ao lado do catálogo e não ao
lado da regra: quando alguém renomear uma área no painel, o vermelho aparece
aqui, antes de aparecer numa conversa.

FRASES é escrita à mão de propósito. Gerá-la a partir do nome da área tornaria o
teste circular - ele passaria justamente no caso que o derrubou.
"""
import unittest

from src.services.confirmacao_de_areas import areas_conversadas
from tests.unit.catalogo_real import AREAS, CATALOGO

# Como uma paciente pede cada área no WhatsApp. Uma frase basta: o que se afirma
# é que a área é ALCANÇÁVEL, não que todo sinônimo funciona.
FRASES = {
    "1/2 Braço": "quero 1/2 braço",
    "1/2 Coxa": "1/2 coxa por favor",
    "1/2 Glúteo": "gostaria de 1/2 glúteo",
    "1/2 Perna": "1/2 perna",
    "1/2 Virilha": "queria fazer 1/2 virilha",
    "Abdômen": "quero abdômen",
    "Aréola": "aréola",
    "Axilas": "quero fazer axilas",
    "Barba Comp. + Pescoço": "barba completa e pescoço",
    "Barba contorno": "só o contorno, barba contorno",
    "Braço Completo": "braço completo",
    "Buço": "buco por favor",
    "Costas total + ombros": "costas total + ombros",
    "Costeleta": "costeleta",
    "Coxas": "queria as coxas",
    "Glabela (entre as sobrancelhas)": "quero glabela",
    "Glúteo": "gluteo",
    "Linha alba": "é a linha alba mesmo",
    "Lombar": "lombar",
    "Mão ou Pé + Dedos": "quero mão",
    "Mento/Queixo": "queixo",
    "Nariz": "nariz",
    "Nuca": "nuca",
    "Ombros": "ombros",
    "Orelhas": "orelhas",
    "Peitoral": "peitoral",
    "Peitoral + abdômen": "peitoral e abdômen",
    "Perianal/ânus": "perianal",
    "Perna Completa": "perna completa",
    "Pernas Completas": "quero as pernas completas",
    "Pescoço": "pescoço",
    "Rosto Completo": "rosto completo",
    "Virilha Cavada": "virilha cavada",
    # A frase exata da paciente de 16/09/2026.
    "Virilha Completa + ânus": "Virilha completa + Ânus",
    "Virilha Completa": "virilha completa",
    "Virilha Simples": "virilha simples",
}


def dita_pela_paciente(texto):
    return [{"role": "user", "content": texto}]


class TestTodaAreaEAlcancavel(unittest.TestCase):
    def test_o_catalogo_inteiro_tem_frase(self):
        """Área nova sem frase aqui é área que ninguém conferiu se dá para pedir."""
        self.assertEqual(sorted(FRASES), sorted(CATALOGO))

    def test_cada_area_e_liberada_pela_frase_da_paciente(self):
        for nome, frase in FRASES.items():
            with self.subTest(area=nome):
                self.assertIn(
                    nome,
                    areas_conversadas(dita_pela_paciente(frase), AREAS),
                    f"'{nome}' é inalcançável: a paciente escreveu {frase!r} e a "
                    f"trava recusou. Renomeie a área no cadastro ou ajuste a regra.",
                )


class TestNaoLiberaAVizinha(unittest.TestCase):
    """Alcançável não pode virar frouxo: liberar a área ao lado marca a sessão
    errada, que é o dano que a trava existe para evitar."""

    def test_virilha_completa_nao_libera_a_que_inclui_anus(self):
        liberadas = areas_conversadas(dita_pela_paciente("virilha completa"), AREAS)
        self.assertIn("Virilha Completa", liberadas)
        self.assertNotIn("Virilha Completa + ânus", liberadas)

    def test_virilha_sozinha_nao_libera_nenhuma_virilha(self):
        liberadas = areas_conversadas(dita_pela_paciente("quero virilha"), AREAS)
        self.assertEqual([n for n in liberadas if "irilha" in n], [])

    def test_abdomen_sozinho_nao_libera_o_peitoral_junto(self):
        liberadas = areas_conversadas(dita_pela_paciente("abdômen"), AREAS)
        self.assertIn("Abdômen", liberadas)
        self.assertNotIn("Peitoral + abdômen", liberadas)

    def test_palavra_maior_nao_casa_a_area(self):
        """'Lombar' dentro de 'lombardia' não é pedido de área."""
        self.assertNotIn("Lombar", areas_conversadas(dita_pela_paciente("lombardia"), AREAS))

    def test_a_abreviacao_nao_vale_para_quem_nao_e_abreviacao(self):
        """'Comp.' de 'Barba Comp. + Pescoço' casa por começo porque o cadastro
        a marcou com ponto. 'Coxa' não tem ponto, então 'coxas' não é 'coxa'."""
        liberadas = areas_conversadas(dita_pela_paciente("1/2 coxa"), AREAS)
        self.assertIn("1/2 Coxa", liberadas)
        self.assertNotIn("Coxas", liberadas)


if __name__ == "__main__":
    unittest.main()
