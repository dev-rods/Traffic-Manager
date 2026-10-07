# -*- coding: utf-8 -*-
"""Barriga e virilha não seguem sem a pergunta.

Regra do André, 13/09/2026: "barriga"/"abdômen" pode ser linha alba, e virilha
- inclusive a completa - pode ser com ânus. Errar isso não aparece na conversa,
aparece na sala, com a sessão marcada com duração e preço de outra área.
"""
import unittest

from src.services.areas_ambiguas import pendencias, perguntas, recado_de_recusa

AREAS = [
    {"id": "a-barriga", "name": "Barriga"},
    {"id": "a-abdomen", "name": "Abdômen completo"},
    {"id": "a-alba", "name": "Linha Alba"},
    {"id": "a-virilha", "name": "Virilha Completa"},
    {"id": "a-virilha-anus", "name": "Virilha Completa com Ânus"},
    {"id": "a-axilas", "name": "Axilas"},
]


def conversa(*turnos):
    return [{"role": r, "content": c} for r, c in turnos]


def par(area_id):
    return {"service_id": "s1", "area_id": area_id}


class TestBarriga(unittest.TestCase):
    def test_barriga_sem_conversa_fica_pendente(self):
        p = pendencias([par("a-barriga")], AREAS, conversa(("user", "quero barriga")))
        self.assertEqual([i["id"] for i in p], ["linha_alba"])
        self.assertIn("linha alba", perguntas(p)[0].lower())

    def test_abdomen_tambem_dispara(self):
        p = pendencias([par("a-abdomen")], AREAS, conversa(("user", "abdômen")))
        self.assertEqual([i["id"] for i in p], ["linha_alba"])

    def test_linha_alba_dita_pela_paciente_libera(self):
        turnos = conversa(
            ("assistant", "É a barriga toda ou a linha alba?"),
            ("user", "A barriga toda"),
        )
        self.assertEqual(pendencias([par("a-barriga")], AREAS, turnos), [])

    def test_bot_perguntou_e_ela_nao_respondeu_ainda(self):
        turnos = conversa(("assistant", "É a barriga toda ou a linha alba?"))
        self.assertEqual([i["id"] for i in pendencias([par("a-barriga")], AREAS, turnos)],
                         ["linha_alba"])

    def test_escolher_a_propria_linha_alba_nao_e_ambiguo(self):
        self.assertEqual(pendencias([par("a-alba")], AREAS, conversa(("user", "linha alba"))), [])


class TestVirilha(unittest.TestCase):
    def test_virilha_completa_ainda_precisa_da_pergunta(self):
        """O ponto da regra: 'completa' não quer dizer com ânus."""
        p = pendencias([par("a-virilha")], AREAS, conversa(("user", "virilha completa")))
        self.assertEqual([i["id"] for i in p], ["virilha_com_anus"])
        self.assertIn("ânus", perguntas(p)[0].lower())

    def test_anus_mencionado_libera(self):
        turnos = conversa(
            ("assistant", "Quer incluir a região do ânus (perianal)?"),
            ("user", "não, só a virilha"),
        )
        self.assertEqual(pendencias([par("a-virilha")], AREAS, turnos), [])

    def test_area_que_ja_diz_com_anus_nao_e_ambigua(self):
        self.assertEqual(
            pendencias([par("a-virilha-anus")], AREAS, conversa(("user", "virilha"))), []
        )


class TestGeral(unittest.TestCase):
    def test_area_sem_ambiguidade_passa(self):
        self.assertEqual(pendencias([par("a-axilas")], AREAS, conversa(("user", "axilas"))), [])

    def test_sem_pares_nao_ha_pendencia(self):
        self.assertEqual(pendencias([], AREAS, conversa(("user", "oi"))), [])

    def test_cada_ambiguidade_pergunta_uma_vez_so(self):
        p = pendencias([par("a-barriga"), par("a-abdomen")], AREAS, [])
        self.assertEqual([i["id"] for i in p], ["linha_alba"])

    def test_as_duas_juntas(self):
        p = pendencias([par("a-barriga"), par("a-virilha")], AREAS, [])
        self.assertEqual({i["id"] for i in p}, {"linha_alba", "virilha_com_anus"})

    def test_recado_diz_o_que_fazer(self):
        r = recado_de_recusa(pendencias([par("a-virilha")], AREAS, []))
        self.assertEqual(r["error"], "areas_ambiguas")
        self.assertIn("Virilha Completa", r["areas_a_confirmar"])
        self.assertIn("ESPERE a resposta", r["o_que_fazer"])


if __name__ == "__main__":
    unittest.main()
