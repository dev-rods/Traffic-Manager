# -*- coding: utf-8 -*-
"""Em campanha, o roteiro de lead nao esta no prompt - nao basta proibi-lo.

Em 11/09/2026 a Camila, paciente cadastrada, recebeu do bot o pedido de nome
completo, nascimento, CPF e e-mail, e o valor da sessao sem ter perguntado.

O bloco de campanha ESTAVA no prompt, com "NUNCA peca nome, CPF" e "NAO anuncie
preco" - conferido reconstruindo o prompt com a sessao real. A mensagem enviada
era palavra por palavra o passo 6 do roteiro base.

Entre um roteiro longo com texto pronto e uma negacao curta no fim, o modelo
segue o roteiro. Por isso o roteiro sai do prompt.
"""
import unittest

from src.services.prompt_da_campanha import adapta, pede_cadastro

# Um recorte fiel do template de producao, com os cabecalhos de caixa dupla.
C = chr(0x2550) * 3
PROMPT_BASE = (
    f"{C} COMO VOCE ESCREVE {C}\n"
    "Tom humano, mensagens curtas.\n"
    f"{C} COMO CONDUZIR A CONVERSA {C}\n"
    "1. PRIMEIRO CONTATO\n"
    "   Cumprimente e apresente a clinica.\n"
    "3. AREAS\n"
    "   Confirme as areas, chame calculate_discount e mostre o valor.\n"
    "6. CADASTRO\n"
    "   \"Perfeito! Para finalizar o cadastro, me envia:\n"
    "   Nome completo:\n"
    "   Data de nascimento:\n"
    "   CPF:\n"
    "   E-mail:\"\n"
    f"{C} ABERTURA DE CONVERSA {C}\n"
    "Se a mensagem for __INICIAR_CONVERSA__, e a clinica iniciando o contato.\n"
    f"{C} AO FECHAR O AGENDAMENTO {C}\n"
    "Passe o endereco: Rua Augusta, 2709.\n"
)


class TestOQueSai(unittest.TestCase):
    def test_o_roteiro_de_cadastro_some(self):
        """A mensagem que a Camila recebeu era este texto, literal."""
        adaptado = adapta(PROMPT_BASE)

        self.assertNotIn("Para finalizar o cadastro", adaptado)
        self.assertNotIn("Nome completo", adaptado)
        self.assertNotIn("CPF", adaptado)

    def test_a_ordem_de_mostrar_o_valor_some(self):
        self.assertNotIn("mostre o valor", adapta(PROMPT_BASE))

    def test_as_boas_vindas_somem(self):
        self.assertNotIn("PRIMEIRO CONTATO", adapta(PROMPT_BASE))

    def test_o_gatilho_de_lead_some(self):
        """__INICIAR_CONVERSA__ e da landing page, nao da campanha."""
        self.assertNotIn("__INICIAR_CONVERSA__", adapta(PROMPT_BASE))


class TestOQueFica(unittest.TestCase):
    """Duplicar as regras comuns criaria duas fontes para a mesma verdade."""

    def test_o_tom_de_escrita_fica(self):
        self.assertIn("Tom humano", adapta(PROMPT_BASE))

    def test_o_endereco_fica(self):
        self.assertIn("Rua Augusta", adapta(PROMPT_BASE))

    def test_entra_o_fluxo_da_campanha(self):
        adaptado = adapta(PROMPT_BASE)

        self.assertIn("COMO CONDUZIR A CONVERSA (CAMPANHA)", adaptado)
        self.assertIn("DESTA VEZ", adaptado)
        self.assertIn("NAO peca dados de cadastro", adaptado)


class TestTemplateEditadoPelaClinica(unittest.TestCase):
    """A clinica edita o template pelo painel: nao dá para exigir formato."""

    def test_sem_a_secao_de_fluxo_nao_quebra(self):
        prompt = f"{C} COMO VOCE ESCREVE {C}\nTom humano.\n"
        self.assertEqual(adapta(prompt), prompt)

    def test_prompt_vazio_ou_nulo(self):
        for p in ("", None):
            with self.subTest(p=p):
                self.assertEqual(adapta(p), p)

    def test_secao_no_fim_do_texto(self):
        prompt = f"{C} COMO CONDUZIR A CONVERSA {C}\n1. PRIMEIRO CONTATO\n"
        adaptado = adapta(prompt)

        self.assertNotIn("PRIMEIRO CONTATO", adaptado)
        self.assertIn("CAMPANHA", adaptado)


class TestTravaDeSaida(unittest.TestCase):
    """Tirar do prompt reduz a chance; a trava e o que garante."""

    def test_pega_a_mensagem_real_da_camila(self):
        texto = ("Perfeito! Para finalizar o cadastro, me envia:\n"
                 "Nome completo:\nData de nascimento:\nCPF:\nE-mail:")

        self.assertTrue(pede_cadastro(texto))

    def test_pega_cada_termo_isolado(self):
        for texto in ("Me manda seu CPF, por favor",
                      "Qual seu nome completo?",
                      "Preciso da sua data de nascimento"):
            with self.subTest(texto=texto):
                self.assertTrue(pede_cadastro(texto))

    def test_sem_acento_e_em_caixa_alta(self):
        self.assertTrue(pede_cadastro("DATA DE NASCIMENTO"))

    def test_mensagem_normal_passa(self):
        for texto in ("Para quinta, 24/09 tenho 09:15 e 10:05. Qual prefere?",
                      "Confirmo: Axilas, dia 24/09 as 14:10. Confirmo?",
                      "Agendamento confirmado! Rua Augusta, 2709."):
            with self.subTest(texto=texto):
                self.assertEqual(pede_cadastro(texto), [])

    def test_texto_vazio(self):
        self.assertEqual(pede_cadastro(""), [])
        self.assertEqual(pede_cadastro(None), [])


if __name__ == "__main__":
    unittest.main()
