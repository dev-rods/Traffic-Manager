# -*- coding: utf-8 -*-
"""Áreas são conversa; botões são só para datas e horários (PRD 037).

Em 03/11/2026 a pessoa escreveu "Virilha" e o bot mandou botões duas vezes
(perianal sim/não, depois Simples/Cavada/Completa) sem explicar os tipos. O
prompt dizia "entenda em texto livre" e a descrição da tool dizia "ALWAYS use
this when showing choices (services, areas, ...)". Duas fontes para a mesma
regra; o modelo seguia uma ou outra.

O prompt que roda é o do banco; a troca entra por `corrige_prompt_areas.aplica`,
que aqui é testada nos três ramos. O texto do prompt só admite teste de texto;
o comportamento está no roteiro de integração 037.
"""
import re
import unittest

from src.scripts.corrige_prompt_areas import (
    APLICADO, BLOCO_AUSENTE, JA_CORRIGIDO, NOVO, VELHO, aplica,
)
from src.services.ai_tools import TOOL_DEFINITIONS
from src.services.template_service import DEFAULT_TEMPLATES


def _descricao(nome):
    for d in TOOL_DEFINITIONS:
        fn = d.get("function") or d
        if fn.get("name") == nome:
            return fn["description"]
    raise AssertionError(f"tool {nome} não encontrada")


ANTES = "2. DÚVIDA\n   Chame get_faq_answer e responda.\n\n"
DEPOIS = "\n\n4. DATA E HORÁRIO\n   Chame check_availability."
PROMPT = ANTES + VELHO + DEPOIS


class TestDescricaoDaTool(unittest.TestCase):
    def test_e_so_para_datas_e_horarios(self):
        d = _descricao("present_options")
        self.assertIn("ONLY for dates", d)
        self.assertIn("check_availability", d)
        self.assertIn("get_time_slots", d)

    def test_proibe_areas_e_servicos(self):
        d = _descricao("present_options")
        self.assertIn("NEVER use it for services, treatment areas", d)
        self.assertNotIn("ALWAYS use this when showing choices", d)


class TestAplica(unittest.TestCase):
    def test_troca_o_bloco_uma_vez(self):
        novo, status = aplica(PROMPT)
        self.assertEqual(status, APLICADO)
        self.assertEqual(novo, ANTES + NOVO + DEPOIS)
        self.assertNotIn(VELHO, novo)

    def test_e_idempotente(self):
        uma_vez, _ = aplica(PROMPT)
        duas, status = aplica(uma_vez)
        self.assertEqual(status, JA_CORRIGIDO)
        self.assertEqual(duas, uma_vez)

    def test_recusa_prompt_editado(self):
        editado = PROMPT.replace("mostre o valor", "informe o valor")
        novo, status = aplica(editado)
        self.assertEqual(status, BLOCO_AUSENTE)
        self.assertEqual(novo, editado)


class TestTextoDoPrompt(unittest.TestCase):
    def test_novo_so_cita_botoes_para_negar(self):
        """Toda menção a present_options no bloco novo é proibição."""
        frases = [f for f in re.split(r"(?<=[.:])\s", NOVO) if "present_options" in f]
        self.assertTrue(frases)
        for f in frases:
            self.assertIn("Nunca", f, f)

    def test_novo_explica_variantes_e_perianal(self):
        self.assertIn("simples, cavada, completa", NOVO)
        self.assertIn("get_faq_answer", NOVO)
        self.assertIn("perianal", NOVO)

    def test_default_do_codigo_nao_manda_botoes_para_areas(self):
        linhas = DEFAULT_TEMPLATES["AI_SYSTEM_PROMPT"].split("\n")
        areas = [l for l in linhas if l.strip().startswith("2. ÁREAS")]
        datas = [l for l in linhas if l.strip().startswith("3. DATAS")]
        horarios = [l for l in linhas if l.strip().startswith("4. HORÁRIOS")]
        self.assertEqual(len(areas), 1)
        self.assertNotIn("→ present_options", areas[0])
        self.assertTrue(datas and horarios)
        self.assertIn("present_options", horarios[0])
