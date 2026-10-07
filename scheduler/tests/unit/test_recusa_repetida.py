# -*- coding: utf-8 -*-
"""O laço da trava tem fim, e a conta é da clínica, não da paciente.

Regressão de 16/09/2026: a área chamava-se "Virilha Comp. + ânus" no cadastro,
a trava comparava a string inteira do nome e nenhuma frase humana a liberava. O
bot perguntou cinco vezes, a paciente respondeu certo as cinco, e a conversa só
acabou uma hora e meia depois porque o próprio modelo desistiu.

A trava está certa em recusar. O que faltava era reconhecer que recusar o MESMO
duas vezes não é a trava trabalhando, é a trava presa.
"""
import unittest

from src.services.recusa_repetida import LIMITE, assinatura, e_laco, registra

# As recusas reais que saíram no log daquela conversa.
BARRA_VIRILHA = {
    "error": "areas_nao_confirmadas",
    "areas_barradas": ["Virilha Comp. + ânus"],
}
BARRA_PERIANAL = {
    "error": "areas_nao_confirmadas",
    "areas_barradas": ["Perianal/ânus"],
}
PEDE_DESAMBIGUACAO = {
    "error": "areas_ambiguas",
    "areas_a_confirmar": ["Virilha Completa"],
}
PASSOU = {"discount_pct": 10, "discounted_price_cents": 46350}


class TestAssinatura(unittest.TestCase):
    def test_reconhece_as_duas_travas(self):
        self.assertTrue(assinatura(BARRA_VIRILHA))
        self.assertTrue(assinatura(PEDE_DESAMBIGUACAO))

    def test_resultado_bom_nao_e_recusa(self):
        self.assertIsNone(assinatura(PASSOU))

    def test_erro_de_outra_natureza_nao_e_recusa(self):
        """'service_area_pairs is required' é o modelo errando a chamada, não a
        trava barrando - contá-lo entregaria conversa sadia a uma atendente."""
        self.assertIsNone(assinatura({"error": "service_area_pairs is required"}))

    def test_areas_diferentes_sao_recusas_diferentes(self):
        self.assertNotEqual(assinatura(BARRA_VIRILHA), assinatura(BARRA_PERIANAL))

    def test_a_ordem_das_areas_nao_cria_recusa_nova(self):
        """O modelo remonta a lista a cada tentativa e a ordem varia. Se a ordem
        contasse, o laço nunca fecharia."""
        self.assertEqual(
            assinatura({"error": "areas_nao_confirmadas", "areas_barradas": ["A", "B"]}),
            assinatura({"error": "areas_nao_confirmadas", "areas_barradas": ["B", "A"]}),
        )

    def test_nao_quebra_com_lixo(self):
        for entulho in (None, "erro", [], 7):
            self.assertIsNone(assinatura(entulho))


class TestOLacoFecha(unittest.TestCase):
    def test_a_primeira_recusa_e_a_trava_trabalhando(self):
        """Ela ainda não tinha nomeado a área. Perguntar é legítimo."""
        self.assertFalse(e_laco({}, BARRA_VIRILHA))

    def test_a_segunda_recusa_igual_e_defeito_nosso(self):
        contador = {}
        self.assertFalse(e_laco(contador, BARRA_VIRILHA))
        self.assertTrue(e_laco(contador, BARRA_VIRILHA))

    def test_duas_recusas_de_areas_diferentes_nao_fecham_o_laco(self):
        """O modelo procurando saída não é o mesmo que bater na mesma parede."""
        contador = {}
        self.assertFalse(e_laco(contador, BARRA_VIRILHA))
        self.assertFalse(e_laco(contador, BARRA_PERIANAL))

    def test_o_contador_atravessa_turnos(self):
        """Cada pergunta da trava é uma mensagem nova, com sessão recarregada.
        Um contador de uma rodada só veria a primeira recusa - que é exatamente
        como o laço de 16/09 sobreviveu a cinco mensagens."""
        sessao = {}
        primeira = dict(sessao.get("recusas_de_area") or {})
        e_laco(primeira, BARRA_VIRILHA)
        sessao["recusas_de_area"] = primeira

        segunda = dict(sessao.get("recusas_de_area") or {})
        self.assertTrue(e_laco(segunda, BARRA_VIRILHA))

    def test_resultado_bom_nao_conta(self):
        contador = {}
        for _ in range(5):
            self.assertFalse(e_laco(contador, PASSOU))
        self.assertEqual(contador, {})

    def test_registra_devolve_a_contagem(self):
        contador = {}
        self.assertEqual(registra(contador, BARRA_VIRILHA), 1)
        self.assertEqual(registra(contador, BARRA_VIRILHA), 2)
        self.assertEqual(registra(contador, PASSOU), 0)

    def test_o_limite_e_dois(self):
        """Documentado como teste porque a escolha é do André, não do código:
        três tentativas já são duas perguntas inúteis para a paciente."""
        self.assertEqual(LIMITE, 2)


class TestAConversaDe1609(unittest.TestCase):
    def test_a_conversa_real_teria_parado_na_segunda_recusa(self):
        """Seis recusas saíram no log da sessão: quatro de 'Virilha Comp. +
        ânus' e uma de 'Perianal/ânus'. O laço fecha na segunda da virilha, que
        aconteceu na PRIMEIRA mensagem - antes de qualquer pergunta repetida
        chegar à paciente."""
        recusas = [BARRA_VIRILHA, BARRA_VIRILHA, BARRA_VIRILHA,
                   BARRA_PERIANAL, BARRA_VIRILHA, BARRA_VIRILHA]
        contador = {}
        parou_em = next(
            (i for i, r in enumerate(recusas, 1) if e_laco(contador, r)), None
        )
        self.assertEqual(parou_em, 2)


if __name__ == "__main__":
    unittest.main()
