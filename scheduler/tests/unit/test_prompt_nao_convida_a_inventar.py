# -*- coding: utf-8 -*-
"""O prompt padrão não pode mandar o bot completar o que o FAQ não respondeu.

Em 13/09/2026 o FAQ saiu do contexto do modelo de propósito: despejar a base
inteira no prompt fazia responder de memória ser o caminho normal, e o
verificador de procedência ficava cego justamente na maior classe de respostas.

O bloco (E) do prompt padrão não acompanhou. Ele continuou dizendo que a base
estava "no seu contexto" e - pior - mandava usar itens *relacionados* para
"formular uma resposta útil e natural" quando a pergunta não estivesse coberta.

Foi exatamente isso que aconteceu em 23/09: a paciente perguntou sobre estar
menstruada, o FAQ tem "Posso fazer menstruada?", e o bot devolveu os cuidados
pré-sessão - um item relacionado, que não respondia a pergunta.
"""
import unittest

from src.services.template_service import DEFAULT_TEMPLATES


def prompt_padrao() -> str:
    for chave in ("AI_SYSTEM_PROMPT",):
        if chave in DEFAULT_TEMPLATES:
            return DEFAULT_TEMPLATES[chave]
    raise AssertionError("AI_SYSTEM_PROMPT sumiu de DEFAULT_TEMPLATES")


class TestOFaqNaoEstaNoContexto(unittest.TestCase):
    def test_nao_promete_uma_base_que_nao_existe(self):
        """O FAQ vem de get_faq_answer desde 13/09. Dizer que ele está no
        contexto manda o modelo procurar onde não tem nada."""
        texto = prompt_padrao()

        self.assertNotIn("BASE DE CONHECIMENTO (FAQ) que está no seu contexto", texto)

    def test_manda_chamar_a_tool(self):
        self.assertIn("get_faq_answer", prompt_padrao())


class TestNaoAutorizaCompletarALacuna(unittest.TestCase):
    def test_nao_manda_usar_item_relacionado(self):
        """"Use as informações relacionadas para formular uma resposta útil"
        é a frase que produziu a resposta errada da paciente."""
        texto = prompt_padrao()

        self.assertNotIn("informações relacionadas", texto)
        self.assertNotIn("formular uma resposta útil", texto)

    def test_diz_o_que_fazer_quando_nao_sabe(self):
        texto = prompt_padrao()

        self.assertIn("request_human_handoff", texto)
        self.assertIn("NÃO SABE", texto)


class TestNaoEmpurraAgendamentoSemOlhar(unittest.TestCase):
    def test_manda_conferir_agendamento_existente(self):
        """A paciente de 23/09 tinha sessão marcada para o dia seguinte e foi
        perguntada duas vezes sobre quais áreas queria tratar."""
        self.assertIn("lookup_appointments", prompt_padrao())

    def test_nao_emenda_pergunta_ao_chamar_especialista(self):
        texto = prompt_padrao().lower()

        self.assertIn("não emende outra pergunta", texto.replace("nao", "não"))


if __name__ == "__main__":
    unittest.main()
