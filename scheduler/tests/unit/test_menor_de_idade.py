# -*- coding: utf-8 -*-
"""Menor de 18 estreando recebe a exigência do responsável legal - e só ela.

Regra do André, 14/09/2026, válida só no bot de leads. Os dois erros que este
teste existe para impedir são simétricos: mandar a exigência para uma adulta, e
deixar de mandar para quem estreia menor de idade. O primeiro é constrangedor; o
segundo coloca a clínica num problema jurídico.
"""
import os
import time
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.menor_de_idade import TEXTO, precisa_avisar
from src.services.conversation_agent import AVISO_DE_MENOR
from tests.unit.dublagem_agente import (
    CLINIC,
    AnthropicRoteiro,
    mensagem,
    monta_agente,
    texto_do_modelo,
    usa_tool,
)

SESSAO = "2026-09-23"


class BancoFake:
    """Cadastro e histórico de sessões, o mínimo que a regra consulta."""

    def __init__(self, nascimento=None, sessoes_anteriores=0):
        self.nascimento = nascimento
        self.sessoes = sessoes_anteriores

    def execute_query(self, sql, params=None):
        if "birth_date" in sql:
            return [{"birth_date": self.nascimento}] if self.nascimento else []
        if "COUNT(*)" in sql:
            return [{"total": self.sessoes}]
        return []


class TestQuandoAvisa(unittest.TestCase):
    def test_menor_estreando(self):
        self.assertTrue(precisa_avisar(BancoFake("2010-01-01"), CLINIC, "5511", SESSAO))

    def test_faz_18_depois_da_sessao(self):
        """Um dia de diferença muda a resposta - por isso a conta é em dias."""
        self.assertTrue(precisa_avisar(BancoFake("2008-09-24"), CLINIC, "5511", SESSAO))


class TestQuandoNaoAvisa(unittest.TestCase):
    def test_maior_de_idade(self):
        self.assertFalse(precisa_avisar(BancoFake("1994-05-11"), CLINIC, "5511", SESSAO))

    def test_faz_18_no_dia_da_sessao(self):
        self.assertFalse(precisa_avisar(BancoFake("2008-09-23"), CLINIC, "5511", SESSAO))

    def test_menor_que_ja_e_paciente(self):
        """Da segunda sessão em diante a idade deixa de importar para este aviso."""
        banco = BancoFake("2010-01-01", sessoes_anteriores=3)
        self.assertFalse(precisa_avisar(banco, CLINIC, "5511", SESSAO))

    def test_sem_data_de_nascimento_nao_chuta(self):
        self.assertFalse(precisa_avisar(BancoFake(None), CLINIC, "5511", SESSAO))

    def test_banco_fora_do_ar_nao_derruba_o_agendamento(self):
        class Quebrado:
            def execute_query(self, sql, params=None):
                raise RuntimeError("timeout")

        self.assertFalse(precisa_avisar(Quebrado(), CLINIC, "5511", SESSAO))


class TestOTexto(unittest.TestCase):
    def test_as_duas_saidas_estao_escritas(self):
        self.assertIn("acompanhamento de um responsável legal", TEXTO)
        self.assertIn("Gov.br", TEXTO)

    def test_diz_que_vale_so_para_a_primeira(self):
        self.assertIn("apenas para a primeira sessão", TEXTO)


def agenda(anthropic_resultado):
    return AnthropicRoteiro([usa_tool("book_appointment"), texto_do_modelo("Confirmado!")])


class TestNoFluxoDoAgente(unittest.TestCase):
    """O aviso sai pelo código, como o de preparo: o texto tem consequência
    jurídica e não é para o modelo reescrever."""

    def _agente(self, banco, sessao_inicial=None):
        agente = monta_agente(
            agenda(None),
            resultado_da_tool={"appointment_id": "a-1", "date": SESSAO,
                               "status": "CONFIRMED"},
        )
        agente.db = banco
        if sessao_inicial:
            agente.sessao_salva.update(sessao_inicial)
        return agente

    def test_lead_menor_recebe_o_aviso_antes_do_preparo(self):
        agente = self._agente(BancoFake("2010-01-01"))
        saida = agente.process_message(CLINIC, mensagem("pode confirmar"))
        textos = [m.content for m in saida]
        self.assertIn(AVISO_DE_MENOR, textos)
        from src.services.orientacoes_pos_sessao import TEXTO as PREPARO
        self.assertLess(textos.index(AVISO_DE_MENOR), textos.index(PREPARO))

    def test_lead_maior_nao_recebe(self):
        agente = self._agente(BancoFake("1994-05-11"))
        saida = agente.process_message(CLINIC, mensagem("pode confirmar"))
        self.assertNotIn(AVISO_DE_MENOR, [m.content for m in saida])

    def test_campanha_nunca_recebe(self):
        """Na campanha estão pacientes cadastradas, que já estrearam."""
        agente = self._agente(
            BancoFake("2010-01-01"),
            sessao_inicial={"campanha": {"datas": ["2026-09-23"],
                                         "expira_em": int(time.time()) + 3600}},
        )
        saida = agente.process_message(CLINIC, mensagem("pode confirmar"))
        self.assertNotIn(AVISO_DE_MENOR, [m.content for m in saida])


class TestARegraSoEntraNoPromptDoLead(unittest.TestCase):
    """A secao de idade nao pode vazar para a campanha.

    Na campanha estao pacientes cadastradas. Uma instrucao pedindo data de
    nascimento a quem ja tem cadastro e exatamente o erro de 11/09, quando a
    Camila recebeu "me envia: nome completo, data de nascimento, CPF".
    """

    def _prompt(self, sessao):
        from src.services.conversation_agent import ConversationAgent

        agente = object.__new__(ConversationAgent)
        agente.db = BancoFake("2010-01-01")
        agente.db.execute_query = lambda sql, params=None: []
        agente.template_service = type(
            "T", (), {"get_and_render": lambda self, c, k, v=None: "PROMPT BASE"}
        )()
        return agente._build_system_prompt(CLINIC, "5511999999999", sessao)

    def test_lead_recebe_a_secao(self):
        prompt = self._prompt({})
        self.assertIn("IDADE DA PACIENTE", prompt)
        self.assertIn("calculate_patient_age", prompt)
        self.assertIn("Gov.br", prompt)

    def test_campanha_nao_recebe(self):
        prompt = self._prompt(
            {"campanha": {"datas": ["2026-09-23"], "expira_em": int(time.time()) + 3600}}
        )
        self.assertNotIn("IDADE DA PACIENTE", prompt)


if __name__ == "__main__":
    unittest.main()
