# -*- coding: utf-8 -*-
"""A pergunta sobre outro procedimento não chega ao modelo.

O teste de [test_fora_do_escopo] mede a lista. Este mede o FLUXO, que é onde a
regra vale ou não vale: o agente recebe "vocês fazem botox?" e tem de sair pela
especialista sem chamar o modelo, sem chamar o FAQ, e deixando a conversa na
fila do painel com o motivo gravado.

"Sem chamar o modelo" é a parte que importa, e não é economia de token: enquanto
a pergunta chega ao modelo, existe um caminho em que ele compõe a resposta a
partir de um item de FAQ de laser que casou "sessão" ou "preço" - e aí a
paciente recebe preço de depilação para uma pergunta de injetável.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from dublagem_agente import (
    CLINIC,
    PHONE,
    AnthropicFalso,
    ToolExecutorFalso,
    mensagem,
    monta_agente,
)
from src.services.bot_policy import (
    CAMPO_DE_PAUSA,
    CAMPO_DO_MOTIVO,
    MOTIVO_FORA_DO_ESCOPO,
    PAUSA_HANDOFF,
)
from src.services.fora_do_escopo import TEXTO as TEXTO_FORA_DO_ESCOPO


class OModeloNaoVeAPergunta(unittest.TestCase):
    def setUp(self):
        self.anthropic = AnthropicFalso()
        self.tools = ToolExecutorFalso()
        self.agente = monta_agente(anthropic=self.anthropic, tool_executor=self.tools)

    def responde(self, texto):
        return self.agente.process_message(CLINIC, mensagem(texto))

    def test_botox_sai_pela_especialista_sem_modelo_e_sem_faq(self):
        saida = self.responde("oi, vocês fazem botox?")

        self.assertEqual(self.anthropic.chamadas, 0, "a pergunta chegou ao modelo")
        self.assertEqual(self.tools.chamadas, [], "consultou tool para algo que não atende")
        self.assertEqual(len(saida), 1)
        self.assertEqual(saida[0].content, TEXTO_FORA_DO_ESCOPO)

    def test_a_conversa_vai_para_a_fila_com_o_motivo(self):
        self.responde("quanto custa o preenchimento labial?")
        sessao = self.agente.sessao_salva

        self.assertEqual(sessao["state"], "HUMAN_HANDOFF")
        self.assertEqual(sessao[CAMPO_DE_PAUSA], PAUSA_HANDOFF)
        self.assertEqual(sessao[CAMPO_DO_MOTIVO], MOTIVO_FORA_DO_ESCOPO)
        self.assertTrue(sessao["human_handoff_requested_at"])

    def test_o_historico_fica_na_sessao(self):
        # A atendente vai ler a conversa. Entregar sem o turno que motivou a
        # entrega a obrigaria a adivinhar o que foi perguntado.
        self.responde("vocês fazem criolipólise?")
        historico = self.agente.sessao_salva.get("agent_history") or []

        self.assertTrue(historico)
        self.assertEqual(historico[-1]["role"], "user")
        self.assertIn("criolipólise", historico[-1]["content"])

    def test_a_mensagem_nao_devolve_o_nome_do_procedimento(self):
        # O nome que a guarda casou é o NOSSO rótulo, não a palavra dela.
        # Repeti-lo errado numa mensagem de "não sei responder" é a pior
        # combinação possível.
        saida = self.responde("faz enzimas de papada?")
        self.assertNotIn("enzima", saida[0].content.lower())


class OFluxoNormalNaoSofre(unittest.TestCase):
    """A guarda roda em toda mensagem; falso positivo aqui custa agendamento."""

    def setUp(self):
        self.anthropic = AnthropicFalso()
        self.agente = monta_agente(anthropic=self.anthropic)

    def test_agendamento_de_laser_chega_ao_modelo(self):
        self.agente.process_message(
            CLINIC, mensagem("oi, queria agendar depilação a laser de axila")
        )
        self.assertEqual(self.anthropic.chamadas, 1)
        self.assertNotIn("state", self.agente.sessao_salva)

    def test_duvida_de_laser_chega_ao_modelo(self):
        self.agente.process_message(CLINIC, mensagem("quantas sessões preciso fazer?"))
        self.assertEqual(self.anthropic.chamadas, 1)


class AInstrucaoEstaNoPrompt(unittest.TestCase):
    """A segunda rede: o procedimento que a lista não nomeia."""

    def test_o_prompt_proibe_responder_sobre_outro_procedimento(self):
        from src.services.fora_do_escopo import INSTRUCAO_DO_PROMPT

        self.assertIn("SÓ DEPILAÇÃO A LASER", INSTRUCAO_DO_PROMPT)
        self.assertIn("procedimento_fora_do_escopo", INSTRUCAO_DO_PROMPT)
        # Precisa vencer o "toda dúvida começa com get_faq_answer" do bloco de
        # dúvidas, senão o modelo consulta o FAQ de laser e responde dali.
        self.assertIn("NÃO\n   consulta o FAQ", INSTRUCAO_DO_PROMPT)

    def test_a_instrucao_vem_depois_do_bloco_de_duvidas(self):
        # Ordem importa: a última instrução sobre o mesmo assunto é a que o
        # modelo segue na prática.
        import inspect

        from src.services.conversation_agent import ConversationAgent

        fonte = inspect.getsource(ConversationAgent._build_system_prompt)
        self.assertLess(
            fonte.index("COMO RESPONDER DÚVIDAS"),
            fonte.index("INSTRUCAO_FORA_DO_ESCOPO"),
        )


if __name__ == "__main__":
    unittest.main()
