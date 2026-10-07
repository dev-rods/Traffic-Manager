# -*- coding: utf-8 -*-
"""O mapa entre área vendida e área do protocolo, conferido contra o cadastro.

Este teste é o irmão de [test_catalogo_real_e_alcancavel], e nasce da mesma
lição. Em 16/09/2026 uma trava comparou nomes de área por aproximação; `Virilha
Comp. + ânus` ficou inalcançável, a paciente respondeu certo cinco vezes e a
conversa caiu para uma atendente que pediu desculpa por um defeito nosso.

Nada quebrou naquele dia: a regra funcionava exatamente como fora escrita. O que
faltava era alguém perguntar se o cadastro REAL passava por ela.

Aqui o mesmo defeito custaria mais caro. Se uma área do catálogo deixar de casar
com o mapa, a tela não erra visivelmente: ela apenas deixa de sugerir, ou - pior,
se alguém um dia resolver "melhorar" com casamento aproximado - sugere a fluência
de OUTRA área num equipamento que queima pele.

Por isso: toda área do catálogo precisa estar no mapa OU numa lista explícita de
"sem protocolo". Esquecer não é uma opção que o teste aceite.
"""
import unittest

from src.services.protocolo_laser import (
    MAPA_DE_AREAS,
    PROTOCOLO,
    SEM_PROTOCOLO,
    chaves_da_area,
    metodos_disponiveis,
)
from tests.unit.catalogo_real import CATALOGO

CHAVES_DO_PROTOCOLO = {p[2] for p in PROTOCOLO}


class TestOMapaCobreOCatalogo(unittest.TestCase):
    def test_toda_area_vendida_foi_decidida(self):
        """Ou tem protocolo, ou está declarada como sem protocolo.

        Área que não está em lugar nenhum é área que ninguém olhou - e o
        silêncio disso é exatamente o defeito de 16/09.
        """
        for nome in CATALOGO:
            with self.subTest(area=nome):
                self.assertTrue(
                    nome in MAPA_DE_AREAS or nome in SEM_PROTOCOLO,
                    f"'{nome}' está no cadastro e não foi decidida: mapeie no "
                    f"MAPA_DE_AREAS ou declare em SEM_PROTOCOLO.",
                )

    def test_o_mapa_nao_inventa_area_que_nao_existe(self):
        """Renomear uma área no painel deixa uma linha órfã aqui, e a área nova
        fica sem sugestão em silêncio. É o vermelho que avisa."""
        orfas = [n for n in MAPA_DE_AREAS if n not in CATALOGO]
        self.assertEqual(
            orfas, [],
            f"Estas áreas do mapa não existem no cadastro: {orfas}. "
            f"Alguém renomeou no painel?",
        )

    def test_toda_chave_mapeada_existe_no_protocolo(self):
        for nome, chaves in MAPA_DE_AREAS.items():
            for chave in chaves:
                with self.subTest(area=nome, chave=chave):
                    self.assertIn(chave, CHAVES_DO_PROTOCOLO)

    def test_toda_chave_mapeada_tem_pelo_menos_um_metodo(self):
        for nome, chaves in MAPA_DE_AREAS.items():
            for chave in chaves:
                with self.subTest(area=nome, chave=chave):
                    self.assertTrue(metodos_disponiveis(chave))


class TestAreasCompostas(unittest.TestCase):
    """No catálogo é uma área; no protocolo são duas, às vezes com métodos
    diferentes. O registro nasce com as duas linhas, que é o que ela aplica."""

    def test_virilha_completa_mais_anus_abre_em_duas(self):
        self.assertEqual(
            chaves_da_area("Virilha Completa + ânus"),
            ("virilha_completa", "regiao_perianal"),
        )

    def test_e_as_duas_tem_metodos_diferentes(self):
        """Virilha no SHR, perianal no Stacking - por isso não dá para tratar a
        composta como uma linha só."""
        self.assertEqual(metodos_disponiveis("virilha_completa"), ["SHR"])
        self.assertEqual(metodos_disponiveis("regiao_perianal"), ["SHR_STACKING"])

    def test_as_outras_compostas(self):
        self.assertEqual(chaves_da_area("Costas total + ombros"), ("costas", "ombros"))
        self.assertEqual(chaves_da_area("Peitoral + abdômen"), ("peitoral", "abdomen"))
        self.assertEqual(chaves_da_area("Barba Comp. + Pescoço"),
                         ("barba_completa", "pescoco"))


class TestOsNomesQueNaoBatem(unittest.TestCase):
    """As traduções que motivam o mapa existir. Se alguém um dia trocar isto por
    casamento de string, estes casos são os que quebram primeiro."""

    def test_meia_virou_um_meio(self):
        self.assertEqual(chaves_da_area("1/2 Braço"), ("meio_braco",))
        self.assertEqual(chaves_da_area("1/2 Perna"), ("meia_perna",))

    def test_singular_e_plural(self):
        self.assertEqual(chaves_da_area("Glúteo"), ("gluteos",))

    def test_nome_popular_e_nome_do_protocolo(self):
        self.assertEqual(chaves_da_area("Perianal/ânus"), ("regiao_perianal",))
        self.assertEqual(chaves_da_area("Orelhas"), ("orelha_externa",))
        self.assertEqual(chaves_da_area("Barba contorno"), ("barba_contorno",))

    def test_meia_virilha_e_o_interno_da_virilha(self):
        """Decisão do André em 19/09/2026."""
        self.assertEqual(chaves_da_area("1/2 Virilha"), ("interno_virilha",))


class TestAreaInteiraUsaOParametroDaMetade(unittest.TestCase):
    """Confirmado pelo André: o protocolo só tem a versão reduzida."""

    def test_as_que_herdam(self):
        self.assertEqual(chaves_da_area("Braço Completo"), ("meio_braco",))
        self.assertEqual(chaves_da_area("Perna Completa"), ("meia_perna",))
        self.assertEqual(chaves_da_area("Pernas Completas"), ("meia_perna",))
        self.assertEqual(chaves_da_area("1/2 Coxa"), ("coxas",))

    def test_meio_gluteo_tem_linha_propria(self):
        """Aqui o André deu um valor específico, e não herda de Glúteos."""
        self.assertEqual(chaves_da_area("1/2 Glúteo"), ("meio_gluteo",))
        self.assertEqual(chaves_da_area("Glúteo"), ("gluteos",))


class TestSemSugestaoEUmaRespostaValida(unittest.TestCase):
    def test_area_fora_do_catalogo_nao_tem_chave(self):
        """A profissional pode digitar área livre. Isso não é erro."""
        self.assertEqual(chaves_da_area("Área que ela inventou"), ())

    def test_o_mapa_nunca_aproxima(self):
        """'Virilha' sozinho não casa com nenhuma das virilhas."""
        self.assertEqual(chaves_da_area("Virilha"), ())
        self.assertEqual(chaves_da_area("virilha completa"), ())


if __name__ == "__main__":
    unittest.main()
