# -*- coding: utf-8 -*-
"""O "a partir de R$ X" do prompt vem do banco, e nunca derruba o agente.

O valor estava escrito no texto do `AI_SYSTEM_PROMPT`, em dois lugares. Estava
certo em 06/09/2026, e não era esse o problema: quando a clínica reajustar a
tabela, `service_areas` muda e o prompt continua anunciando o preço velho. A
proveniência não pega - ela extrai dinheiro, mas só data e horário bloqueiam.

Metade destes testes é sobre o preço. A outra metade é sobre não quebrar o
agente: o prompt é montado a cada mensagem, e uma falha aqui deixaria a paciente
sem resposta por causa de um argumento de venda.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.conversation_agent import ConversationAgent
from src.services.preco_minimo import (
    SEM_PRECO,
    formata_reais,
    preco_minimo_por_area,
)

CLINIC = "clinica-teste-0001"


def db_com(minimo):
    db = mock.MagicMock()
    db.execute_query.return_value = [{"minimo": minimo}]
    return db


class TestFormato(unittest.TestCase):
    def test_formato_brasileiro(self):
        self.assertEqual(formata_reais(6500), "R$ 65,00")
        self.assertEqual(formata_reais(24500), "R$ 245,00")

    def test_milhar_com_ponto(self):
        """`f"{x:,.2f}"` produz 1,234.56 - o formato errado para cá."""
        self.assertEqual(formata_reais(123456), "R$ 1.234,56")


class TestPrecoMinimo(unittest.TestCase):
    def test_devolve_o_menor_preco_formatado(self):
        self.assertEqual(preco_minimo_por_area(db_com(6500), CLINIC), "R$ 65,00")

    def test_a_consulta_filtra_o_que_deve(self):
        db = db_com(6500)
        preco_minimo_por_area(db, CLINIC)
        sql = db.execute_query.call_args[0][0]

        self.assertIn("MIN(sa.price_cents)", sql)
        self.assertIn("sa.active = TRUE", sql)
        self.assertIn("a.active = TRUE", sql)
        # Preço zero é área sem preço cadastrado, não área de graça: entrar no
        # MIN faria o prompt anunciar "a partir de R$ 0,00".
        self.assertIn("sa.price_cents > 0", sql)

    def test_e_por_clinica(self):
        """Sem o filtro, o prompt de uma clínica anunciaria o preço de outra."""
        db = db_com(6500)
        preco_minimo_por_area(db, CLINIC)

        self.assertIn(CLINIC, db.execute_query.call_args[0][1])


class TestNuncaDerrubaOAgente(unittest.TestCase):
    """O prompt é montado a cada mensagem. Falhar aqui é a paciente sem resposta."""

    def test_banco_fora_devolve_texto_generico(self):
        db = mock.MagicMock()
        db.execute_query.side_effect = RuntimeError("conexao caiu")

        self.assertEqual(preco_minimo_por_area(db, CLINIC), SEM_PRECO)

    def test_clinica_sem_area_com_preco(self):
        for vazio in ([], [{"minimo": None}]):
            with self.subTest(retorno=vazio):
                db = mock.MagicMock()
                db.execute_query.return_value = vazio
                self.assertEqual(preco_minimo_por_area(db, CLINIC), SEM_PRECO)

    def test_o_fallback_nao_finge_ser_preco(self):
        """"A partir de R$ 0" seria mentira; melhor não ter número."""
        self.assertNotIn("R$", SEM_PRECO)
        self.assertNotIn("0", SEM_PRECO)
        self.assertTrue(SEM_PRECO.strip())

    def test_o_fallback_cabe_na_frase(self):
        """Ele entra no meio de "A partir de ___ por área"."""
        frase = f"A partir de {SEM_PRECO} por área."
        self.assertNotIn("  ", frase)
        self.assertLess(len(SEM_PRECO), 30)


class TestPromptMontado(unittest.TestCase):
    """O que chega ao modelo."""

    def _agente(self, template, minimo=6500):
        agente = object.__new__(ConversationAgent)
        agente.db = mock.MagicMock()
        agente.db.execute_query.side_effect = lambda sql, params=None: (
            [{"minimo": minimo}] if "MIN(sa.price_cents)" in sql else []
        )
        agente.template_service = mock.MagicMock()
        agente.template_service.get_and_render.side_effect = (
            lambda c, k, variables: template.replace(
                "{{preco_minimo}}", str(variables.get("preco_minimo", "")))
        )
        return agente

    def test_o_valor_do_banco_entra_no_prompt(self):
        agente = self._agente("Sessão avulsa a partir de {{preco_minimo}} por área.")

        prompt = agente._build_system_prompt(CLINIC, "5511999990000")

        self.assertIn("R$ 65,00", prompt)

    def test_reajuste_no_banco_aparece_no_prompt(self):
        """O ponto do PR: mudar a tabela muda o que o bot diz."""
        agente = self._agente("a partir de {{preco_minimo}}", minimo=7900)

        self.assertIn("R$ 79,00", agente._build_system_prompt(CLINIC, "5511999990000"))

    def test_prompt_nao_sai_com_placeholder_cru(self):
        """`render_template` deixa variável desconhecida literal no texto. Se o
        nome divergir entre o template e o código, a paciente lê
        "{{preco_minimo}}" - visível, mas só depois de chegar nela."""
        agente = self._agente("a partir de {{preco_minimo}} por área")

        prompt = agente._build_system_prompt(CLINIC, "5511999990000")

        self.assertNotIn("{{", prompt)

    def test_prefixo_estavel_entre_chamadas(self):
        """O prompt é o prefixo cacheado. Se variasse entre mensagens da mesma
        conversa, o cache morreria e o custo voltaria ao de antes."""
        agente = self._agente("a partir de {{preco_minimo}}")

        primeiro = agente._build_system_prompt(CLINIC, "5511999990000")
        segundo = agente._build_system_prompt(CLINIC, "5511999990000")

        self.assertEqual(primeiro, segundo)

    def test_banco_fora_nao_levanta_na_montagem(self):
        agente = object.__new__(ConversationAgent)
        agente.db = mock.MagicMock()
        agente.db.execute_query.side_effect = RuntimeError("banco fora")
        agente.template_service = mock.MagicMock()
        agente.template_service.get_and_render.return_value = "BASE"

        with self.assertRaises(RuntimeError):
            # A montagem TODA depende do banco: clínica, serviços, descontos.
            # Este teste registra que o preço não é o elo que quebra - as
            # consultas anteriores já teriam falhado.
            agente._build_system_prompt(CLINIC, "5511999990000")


if __name__ == "__main__":
    unittest.main()
