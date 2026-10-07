# -*- coding: utf-8 -*-
"""Os valores do protocolo, conferidos contra os PDFs da clínica.

Este é um teste de TRANSCRIÇÃO, e por isso os números estão escritos aqui de
novo, à mão, em vez de derivados do módulo. Derivar tornaria o teste circular:
ele passaria justamente se alguém digitasse um número errado nos dois lugares.

Os valores saem de `Documentos Laser/Parâmetros Peles Brancas.pdf` e
`Parâmetros Pele Negra.pdf`, 19/09/2026, e do anexo do PRD 012.

Número de laser não se altera de passagem: mexer no módulo sem mexer aqui
quebra, de propósito.
"""
import unittest

from src.services.protocolo_laser import (
    BRANCA,
    HR,
    NEGRA,
    PROTOCOLO,
    SHR,
    SHR_STACKING,
    avisos,
    campos_do_metodo,
    hr_desaconselhado,
    metodos_disponiveis,
    sugestao,
    tabela_para_a_tela,
)

# (chave, branca_fluencia, branca_energia, negra_fluencia, negra_energia)
SHR_ESPERADO = [
    ("linha_alba", 7, 5, 5, 4),
    ("axilas", 7, 8, 5, 7),
    ("meio_braco", 7, 8, 5, 7),
    ("lombar", 7, 8, 5, 7),
    ("gluteos", 8, 14, 7, 12),
    ("coxas", 8, 14, 7, 12),
    ("meia_perna", 8, 14, 7, 12),
    ("virilha_simples", 7, 5, 5, 4),
    ("virilha_cavada", 7, 5, 5, 4),
    ("virilha_completa", 7, 6, 5, 5),
    ("interno_virilha", 6, 3, 4, 2.5),
    ("peitoral", 7, 8, 5, 7),
    ("abdomen", 7, 8, 5, 7),
    ("costas", 7, 8, 5, 7),
    ("ombros", 7, 8, 5, 7),
]

# (chave, branca_fluencia, negra_fluencia). Stacks 3 e passadas 2 em todas.
STACKING_ESPERADO = [
    ("buco", 6, 5),
    ("mento_queixo", 6, 5),
    ("rosto_completo", 6, 5),
    ("pescoco", 6, 5),
    ("areola", 6, 5),
    ("mao_pe_dedos", 6, 5),
    ("regiao_perianal", 6, 5),
    ("interno_virilha", 6, 4),
    ("costeleta", 6, 5),
    ("barba_contorno", 6, 5),
    ("barba_completa", 5, 4),
    ("nuca", 5, 4),
    ("orelha_externa", 5, 4),
]

# (chave, branca_fluencia, negra_fluencia). Energia 1,0 em todas.
HR_ESPERADO = [
    ("buco", 17, 14),
    ("mento_queixo", 17, 14),
    ("areola", 17, 14),
    ("costeleta", 17, 14),
    ("barba_contorno", 15, 12),
    ("interno_virilha", 15, 12),
    ("axilas", 17, 14),
    ("joelho", 15, 12),
    ("cotovelo", 17, 14),
]


class TestTranscricaoSHR(unittest.TestCase):
    def test_cada_linha_do_documento(self):
        for chave, bf, be, nf, ne in SHR_ESPERADO:
            with self.subTest(area=chave, pele="branca"):
                s = sugestao(chave, SHR, BRANCA)
                self.assertIsNotNone(s, f"{chave} sumiu do SHR branca")
                self.assertEqual(float(s["fluence_j"]), float(bf))
                self.assertEqual(float(s["energy_kj"]), float(be))
            with self.subTest(area=chave, pele="negra"):
                s = sugestao(chave, SHR, NEGRA)
                self.assertIsNotNone(s, f"{chave} sumiu do SHR negra")
                self.assertEqual(float(s["fluence_j"]), float(nf))
                self.assertEqual(float(s["energy_kj"]), float(ne))

    def test_o_shr_nao_usa_stacks_nem_passadas(self):
        s = sugestao("axilas", SHR, BRANCA)
        self.assertIsNone(s["stacks"])
        self.assertIsNone(s["passes"])


class TestTranscricaoStacking(unittest.TestCase):
    def test_cada_linha_do_documento(self):
        for chave, bf, nf in STACKING_ESPERADO:
            for pele, esperado in ((BRANCA, bf), (NEGRA, nf)):
                with self.subTest(area=chave, pele=pele):
                    s = sugestao(chave, SHR_STACKING, pele)
                    self.assertIsNotNone(s, f"{chave} sumiu do Stacking {pele}")
                    self.assertEqual(float(s["fluence_j"]), float(esperado))
                    self.assertEqual(s["stacks"], 3)
                    self.assertEqual(s["passes"], 2)

    def test_o_stacking_nao_usa_energia(self):
        self.assertIsNone(sugestao("buco", SHR_STACKING, BRANCA)["energy_kj"])


class TestTranscricaoHR(unittest.TestCase):
    def test_cada_linha_do_documento(self):
        for chave, bf, nf in HR_ESPERADO:
            for pele, esperado in ((BRANCA, bf), (NEGRA, nf)):
                with self.subTest(area=chave, pele=pele):
                    s = sugestao(chave, HR, pele)
                    self.assertIsNotNone(s, f"{chave} sumiu do HR {pele}")
                    self.assertEqual(float(s["fluence_j"]), float(esperado))

    def test_a_energia_do_hr_e_fixa_em_um(self):
        """"O valor em kJ é mantido fixo do início ao fim do tratamento.\""""
        for chave, _, _ in HR_ESPERADO:
            for pele in (BRANCA, NEGRA):
                with self.subTest(area=chave, pele=pele):
                    self.assertEqual(float(sugestao(chave, HR, pele)["energy_kj"]), 1.0)


class TestAsLinhasQueNaoVieramDoPDF(unittest.TestCase):
    """Acréscimos da clínica. Ficam marcados porque a tabela é referência
    clínica: daqui a um ano ninguém lembra o que era do material impresso."""

    def test_glabela_e_nariz_sao_da_clinica(self):
        """4 J na branca, 2 J na negra. Ponteira pontual, 2 stacks - todas as
        linhas dos PDFs são 3."""
        for chave in ("glabela", "nariz"):
            for pele, fluencia in ((BRANCA, 4.0), (NEGRA, 2.0)):
                with self.subTest(area=chave, pele=pele):
                    s = sugestao(chave, SHR_STACKING, pele)
                    self.assertEqual(s["source"], "CLINICA")
                    self.assertEqual(float(s["fluence_j"]), fluencia)
                    self.assertEqual(s["stacks"], 2, "ponteira pontual, 2 stacks")
                    self.assertEqual(s["passes"], 2)

    def test_meio_gluteo_e_da_clinica_nas_duas_peles(self):
        """Mesma fluência do glúteo inteiro, metade da energia.

        A energia escala com a área tratada, e isso vale nas duas peles:
        branca 8/14 -> 8/7, negra 7/12 -> 7/6.
        """
        for pele, fluencia, energia in ((BRANCA, 8.0, 7.0), (NEGRA, 7.0, 6.0)):
            with self.subTest(pele=pele):
                s = sugestao("meio_gluteo", SHR, pele)
                self.assertEqual(s["source"], "CLINICA")
                self.assertEqual(float(s["fluence_j"]), fluencia)
                self.assertEqual(float(s["energy_kj"]), energia)

    def test_o_meio_gluteo_nunca_passa_do_gluteo_inteiro(self):
        """A fluência da metade não pode ser maior que a da área inteira na
        MESMA pele: seria sugerir acima do protocolo, que é a direção que
        queima. Foi por isso que a linha da pele negra ficou aberta até o André
        dar o número."""
        for pele in (BRANCA, NEGRA):
            with self.subTest(pele=pele):
                metade = float(sugestao("meio_gluteo", SHR, pele)["fluence_j"])
                inteiro = float(sugestao("gluteos", SHR, pele)["fluence_j"])
                self.assertLessEqual(metade, inteiro)

    def test_todo_o_resto_veio_do_pdf(self):
        da_clinica = {(p[0], p[1], p[2]) for p in PROTOCOLO if p[8] == "CLINICA"}
        self.assertEqual(da_clinica, {
            (BRANCA, SHR_STACKING, "glabela"), (NEGRA, SHR_STACKING, "glabela"),
            (BRANCA, SHR_STACKING, "nariz"), (NEGRA, SHR_STACKING, "nariz"),
            (BRANCA, SHR, "meio_gluteo"), (NEGRA, SHR, "meio_gluteo"),
        })


class TestSugestaoNuncaAproxima(unittest.TestCase):
    """O módulo inteiro existe para não cometer este erro."""

    def test_sem_linha_devolve_none(self):
        self.assertIsNone(sugestao("joelho", SHR, BRANCA))
        self.assertIsNone(sugestao("gluteos", HR, BRANCA))
        self.assertIsNone(sugestao("glabela", HR, BRANCA))

    def test_nao_cai_no_outro_tipo_de_pele(self):
        """Cada pele tem o seu número, e nunca o da outra."""
        self.assertEqual(float(sugestao("meio_gluteo", SHR, BRANCA)["fluence_j"]), 8.0)
        self.assertEqual(float(sugestao("meio_gluteo", SHR, NEGRA)["fluence_j"]), 7.0)
        self.assertEqual(float(sugestao("glabela", SHR_STACKING, BRANCA)["fluence_j"]), 4.0)
        self.assertEqual(float(sugestao("glabela", SHR_STACKING, NEGRA)["fluence_j"]), 2.0)

    def test_nao_cai_no_outro_metodo(self):
        """rosto_completo existe no Stacking e não no SHR nem no HR."""
        self.assertIsNotNone(sugestao("rosto_completo", SHR_STACKING, BRANCA))
        self.assertIsNone(sugestao("rosto_completo", SHR, BRANCA))
        self.assertIsNone(sugestao("rosto_completo", HR, BRANCA))

    def test_chave_inventada_devolve_none(self):
        self.assertIsNone(sugestao("virilha_comp_anus", SHR, BRANCA))


class TestMetodosDisponiveis(unittest.TestCase):
    def test_area_de_um_metodo_so(self):
        self.assertEqual(metodos_disponiveis("linha_alba"), [SHR])
        self.assertEqual(metodos_disponiveis("rosto_completo"), [SHR_STACKING])

    def test_area_de_mais_de_um_metodo(self):
        """Buço tem Stacking e HR. A tela não escolhe por ela."""
        self.assertEqual(metodos_disponiveis("buco"), [SHR_STACKING, HR])

    def test_interno_da_virilha_tem_os_tres(self):
        """A mesma região aparece nos PDFs como 'lábios' no SHR e 'reforço' no
        Stacking e no HR. Unificada numa chave, com três métodos."""
        self.assertEqual(metodos_disponiveis("interno_virilha"),
                         [SHR, SHR_STACKING, HR])

    def test_area_sem_protocolo(self):
        self.assertEqual(metodos_disponiveis("nao_existe"), [])


class TestCamposDoMetodo(unittest.TestCase):
    def test_cada_metodo_tem_a_sua_forma(self):
        self.assertEqual(campos_do_metodo(SHR), ("fluence_j", "energy_kj"))
        self.assertEqual(campos_do_metodo(SHR_STACKING),
                         ("fluence_j", "stacks", "passes"))
        self.assertEqual(campos_do_metodo(HR), ("fluence_j", "energy_kj"))

    def test_metodo_desconhecido_nao_levanta(self):
        """Payload velho não pode deixar a tela sem desenhar nada."""
        self.assertEqual(campos_do_metodo("LASER_MAGICO"), ())
        self.assertEqual(campos_do_metodo(None), ())


class TestAvisos(unittest.TestCase):
    def test_bronzeada_avisa_e_proibe_hr_no_texto(self):
        texto = " ".join(avisos(SHR, BRANCA, bronzeada=True))
        self.assertIn("bronzeada", texto.lower())
        self.assertIn("Nunca utilize o método HR", texto)

    def test_hr_em_pele_negra_traz_o_aviso_do_fototipo_vi(self):
        texto = " ".join(avisos(HR, NEGRA))
        self.assertIn("fototipo VI", texto)

    def test_hr_sempre_avisa_do_risco(self):
        self.assertIn("queimaduras", " ".join(avisos(HR, BRANCA)))

    def test_shr_em_pele_clara_nao_avisa_nada(self):
        self.assertEqual(avisos(SHR, BRANCA), [])

    def test_o_hr_e_desaconselhado_so_em_bronzeada(self):
        """O documento é categórico só aqui. Desaconselhar é tirar da sugestão;
        BLOQUEAR é decisão clínica, e não é do software."""
        self.assertTrue(hr_desaconselhado(BRANCA, bronzeada=True))
        self.assertTrue(hr_desaconselhado(NEGRA, bronzeada=True))
        self.assertFalse(hr_desaconselhado(NEGRA, bronzeada=False))


class TestTabelaCompleta(unittest.TestCase):
    def test_o_total_de_linhas(self):
        """74 dos PDFs + 6 da clínica."""
        self.assertEqual(len(PROTOCOLO), 80)

    def test_nao_ha_linha_duplicada(self):
        chaves = [(p[0], p[1], p[2]) for p in PROTOCOLO]
        self.assertEqual(len(chaves), len(set(chaves)))

    def test_toda_linha_tem_fluencia(self):
        for p in PROTOCOLO:
            with self.subTest(linha=p[:3]):
                self.assertIsNotNone(p[4])
                self.assertGreater(float(p[4]), 0)

    def test_a_tela_recebe_a_tabela_inteira(self):
        self.assertEqual(len(tabela_para_a_tela()), len(PROTOCOLO))


if __name__ == "__main__":
    unittest.main()
