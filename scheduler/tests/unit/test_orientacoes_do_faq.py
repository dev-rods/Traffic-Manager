# -*- coding: utf-8 -*-
"""Todo agendamento termina com as orientações de preparo que a clínica escreveu.

Regra do André, 13/09/2026. A informação já existe no FAQ; o que faltava era o
bot entregar sem depender de a paciente perguntar - e preparo vem antes de
pós-procedimento, porque é o que muda a conduta dela ANTES da sessão.
"""
import unittest

from src.services.orientacoes_do_faq import busca, como_texto


class BancoFake:
    def __init__(self, linhas, erro=None):
        self.linhas = linhas
        self.erro = erro

    def execute_query(self, sql, params=None):
        if self.erro:
            raise self.erro
        return self.linhas


FAQ = [
    {"question_label": "Quanto custa?", "answer": "Depende das áreas."},
    {"question_label": "Cuidados depois da sessão", "answer": "Evite piscina por 48h."},
    {"question_label": "Como me preparar?", "answer": "Raspe com lâmina na véspera."},
    {"question_label": "Posso tomar sol?", "answer": "Não se exponha ao sol antes."},
]


class TestBusca(unittest.TestCase):
    def test_so_traz_orientacao_preparo_primeiro(self):
        itens = busca(BancoFake(FAQ), "c1")
        self.assertEqual(
            [i["pergunta"] for i in itens],
            ["Como me preparar?", "Posso tomar sol?", "Cuidados depois da sessão"],
        )
        self.assertEqual([i["tipo"] for i in itens], ["preparo", "preparo", "pos"])

    def test_pergunta_de_preco_fica_de_fora(self):
        itens = busca(BancoFake(FAQ), "c1")
        self.assertNotIn("Quanto custa?", [i["pergunta"] for i in itens])

    def test_clinica_sem_faq_nao_recebe_nada_inventado(self):
        self.assertEqual(busca(BancoFake([]), "c1"), [])

    def test_banco_fora_do_ar_nao_derruba_o_agendamento(self):
        self.assertEqual(busca(BancoFake(None, erro=RuntimeError("timeout")), "c1"), [])


class TestTexto(unittest.TestCase):
    def test_formata_para_whatsapp(self):
        texto = como_texto(busca(BancoFake(FAQ), "c1"))
        self.assertTrue(texto.startswith("*Como me preparar?*\nRaspe com lâmina na véspera."))
        self.assertIn("*Cuidados depois da sessão*", texto)

    def test_sem_itens_texto_vazio(self):
        self.assertEqual(como_texto([]), "")


if __name__ == "__main__":
    unittest.main()
