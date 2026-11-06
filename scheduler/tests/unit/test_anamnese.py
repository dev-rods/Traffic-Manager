# -*- coding: utf-8 -*-
"""Ficha de anamnese (PRD 038): catálogo, validação, variáveis, alertas."""
import os
import re
import unittest

from src.services import anamnese
from src.services.anamnese import AnamneseInvalida

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "..")
GERADOR = os.path.join(RAIZ, "docs", "work", "assets", "038-modelo-compilado", "gera_modelo.js")
VARIAVEIS_DO_TERMO = {
    "nome_completo", "cpf", "data_nascimento", "telefone", "email", "autoriza_imagem", "menor_nome",
    "responsavel_nome", "responsavel_cpf", "signatario_nome", "signatario_cpf", "profissional_nome",
    "profissional_titulo", "profissional_registro", "clinica_nome", "cidade", "data",
}


def completa(**over):
    r = {}
    for p in anamnese.PERGUNTAS:
        if p.tipo == anamnese.SIM_NAO:
            r[p.chave] = False
    r.update(queixa_principal="Pelos encravados", fototipo="III")
    r.update(over)
    return r


class TestCatalogo(unittest.TestCase):
    def test_chaves_batem_com_o_modelo_compilado(self):
        """As variáveis da ficha no .docx são exatamente as perguntas."""
        fonte = open(GERADOR, encoding="utf-8").read()
        no_modelo = set(re.findall(r"(?:pergunta|detalhe)\('[^']*',\s*'([a-z_0-9]+)'\)", fonte))
        no_modelo |= set(re.findall(r"variavel\('([a-z_0-9]+)'", fonte)) - VARIAVEIS_DO_TERMO
        self.assertEqual(no_modelo, set(anamnese.CHAVES))

    def test_chaves_unicas_e_telas(self):
        self.assertEqual(len(anamnese.CHAVES), len(set(anamnese.CHAVES)))
        self.assertEqual(len(anamnese.CHAVES), 50)
        self.assertEqual({p.tela for p in anamnese.PERGUNTAS}, set(anamnese.TELAS))
        for p in anamnese.PERGUNTAS:
            if p.condicional_de:
                pai = anamnese.POR_CHAVE[p.condicional_de]
                self.assertEqual(pai.tela, p.tela, p.chave)
                self.assertEqual(pai.tipo, anamnese.SIM_NAO, p.chave)

    def test_catalogo_para_o_ipad(self):
        c = anamnese.catalogo()
        self.assertEqual(c["version"], "03")
        self.assertEqual([t["n"] for t in c["screens"]], [1, 2, 3, 4])
        self.assertEqual(sum(len(t["questions"]) for t in c["screens"]), 50)
        self.assertEqual(len(c["phototypes"]), 6)
        q = c["screens"][0]["questions"][4]
        self.assertEqual((q["key"], q["conditionalOf"], q["label"]), ("hormonal_quais", "hormonal", "Se sim, quais?"))
        self.assertNotIn("alerta", q)


class TestValidacao(unittest.TestCase):
    def test_tela_descarta_condicionais_desabilitadas(self):
        limpas = anamnese.valida_tela(1, completa(hormonal=False, hormonal_quais="lixo"))
        self.assertNotIn("hormonal_quais", limpas)
        self.assertNotIn("medicamento", limpas)  # é da tela 2

    def test_condicional_obrigatoria_quando_habilitada(self):
        with self.assertRaises(AnamneseInvalida) as cm:
            anamnese.valida_tela(1, completa(hormonal=True, hormonal_quais=""))
        self.assertEqual(cm.exception.campo, "hormonal_quais")
        limpas = anamnese.valida_tela(1, completa(hormonal=True, hormonal_quais=" SOP  policística "))
        self.assertEqual(limpas["hormonal_quais"], "SOP policística")

    def test_sim_nao_faltando(self):
        r = completa()
        del r["gestante"]
        with self.assertRaises(AnamneseInvalida) as cm:
            anamnese.valida_tela(1, r)
        self.assertEqual(cm.exception.campo, "gestante")

    def test_sim_nao_aceita_texto_e_rejeita_lixo(self):
        self.assertTrue(anamnese.valida_tela(2, completa(medicamento="sim", medicamento_quais="x"))["medicamento"])
        with self.assertRaises(AnamneseInvalida):
            anamnese.valida_tela(2, completa(medicamento="talvez"))

    def test_isotretinoina_data(self):
        with self.assertRaises(AnamneseInvalida) as cm:
            anamnese.valida_tela(2, completa(isotretinoina=True, isotretinoina_ultima_dose="ano passado"))
        self.assertEqual(cm.exception.campo, "isotretinoina_ultima_dose")
        for ok in ("10/03/2026", "03/2026"):
            self.assertEqual(anamnese.valida_tela(2, completa(isotretinoina=True, isotretinoina_ultima_dose=ok))
                             ["isotretinoina_ultima_dose"], ok)

    def test_fototipo(self):
        self.assertEqual(anamnese.valida_tela(4, completa(fototipo="iv"))["fototipo"], "IV")
        with self.assertRaises(AnamneseInvalida) as cm:
            anamnese.valida_tela(4, completa(fototipo="VII"))
        self.assertEqual(cm.exception.campo, "fototipo")

    def test_opcionais_podem_faltar(self):
        limpas = anamnese.valida_tela(4, completa(laser_antes=True))
        self.assertEqual(limpas["laser_antes_reacao"], "")
        self.assertEqual(limpas["observacoes"], "")

    def test_texto_longo(self):
        with self.assertRaises(AnamneseInvalida):
            anamnese.valida_tela(1, completa(queixa_principal="x" * 301))

    def test_completa(self):
        self.assertTrue(anamnese.completa(completa()))
        r = completa()
        del r["fuma"]
        self.assertFalse(anamnese.completa(r))
        self.assertFalse(anamnese.completa(None))
        self.assertEqual(set(anamnese.valida_completa(completa())), {
            p.chave for p in anamnese.PERGUNTAS if not p.condicional_de})


class TestVariaveisEAlertas(unittest.TestCase):
    def test_variaveis_sempre_as_51(self):
        v = anamnese.variaveis(completa(hormonal=True, hormonal_quais="SOP", fototipo="II"))
        self.assertEqual(set(v), set(anamnese.CHAVES))
        self.assertEqual((v["gestante"], v["hormonal"], v["hormonal_quais"], v["fototipo"]), ("Não", "Sim", "SOP", "II"))
        self.assertEqual((v["alergia_quais"], v["observacoes"]), ("-", "-"))
        self.assertEqual(anamnese.variaveis({})["gestante"], "-")

    def test_alertas_na_ordem_da_ficha(self):
        r = completa(gestante=True, tatuagem=True, diabetes=True, diabetes_controlada=False, isotretinoina=True,
                     isotretinoina_ultima_dose="03/2026", hormonal=True, hormonal_quais="x")
        self.assertEqual([a["key"] for a in anamnese.alertas(r)],
                         ["gestante", "diabetes_nao_controlada", "isotretinoina", "tatuagem"])
        self.assertEqual(anamnese.alertas(r)[1]["label"], "Diabetes não controlada")

    def test_diabetes_controlada_nao_alerta(self):
        self.assertEqual(anamnese.alertas(completa(diabetes=True, diabetes_controlada=True)), [])
        self.assertEqual(anamnese.alertas(None), [])
        self.assertEqual(anamnese.alertas(completa()), [])
