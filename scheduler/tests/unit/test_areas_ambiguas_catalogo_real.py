# -*- coding: utf-8 -*-
"""A regra conferida contra o catálogo que está no banco (dev e prod, 13/09/2026).

A regra casa por NOME de área, então ela depende de como a clínica escreve o
nome. Renomear "Virilha Completa + ânus" para "Virilha Total", por exemplo, faria a
área voltar a ser ambígua - e ninguém perceberia sem este teste, porque nada
quebra: a sessão só é marcada errada.

Nomes copiados do cadastro real da Essência / Nobre Laser / Depilação Premium.
"""
import unittest

from src.services.areas_ambiguas import pendencias

from tests.unit.catalogo_real import AREAS, CATALOGO

# Sem nada conversado: o que exige pergunta antes de seguir.
ESPERADO = {
    "Abdômen": ["linha_alba"],
    "Peitoral + abdômen": ["linha_alba"],
    "1/2 Virilha": ["virilha_com_anus"],
    "Virilha Cavada": ["virilha_com_anus"],
    "Virilha Completa": ["virilha_com_anus"],
    "Virilha Simples": ["virilha_com_anus"],
}


class TestCatalogoReal(unittest.TestCase):
    def test_cada_area_do_catalogo(self):
        for nome in CATALOGO:
            with self.subTest(area=nome):
                p = pendencias([{"service_id": "s1", "area_id": nome}], AREAS, [])
                self.assertEqual([i["id"] for i in p], ESPERADO.get(nome, []))

    def test_as_areas_que_ja_dizem_tudo_passam_direto(self):
        """'Virilha Comp. + ânus', 'Perianal/ânus' e 'Linha alba' não são ambíguas:
        o nome que ela escolheu já diz o que ela quer."""
        for nome in ("Virilha Completa + ânus", "Perianal/ânus", "Linha alba"):
            with self.subTest(area=nome):
                self.assertEqual(
                    pendencias([{"service_id": "s1", "area_id": nome}], AREAS, []), []
                )


if __name__ == "__main__":
    unittest.main()
