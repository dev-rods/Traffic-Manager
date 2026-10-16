# -*- coding: utf-8 -*-
"""A lista numerada e o número que a paciente responde (opcoes_numeradas).

A conversa de 16/10/2026 (lead do site, Essência): "Virilha" -> o bot oferece
4 tipos como lista numerada -> ela responde "1" -> o modelo, que nunca viu os
números, chama pedir_esclarecimento -> "o que você quer fazer?" -> ela toca
"Agendar" -> a lista de novo -> "2" -> "o que você quer fazer?" de novo -> e
ninguém é avisado. Aqui o dígito vira o rótulo antes do modelo ler, e a
segunda pergunta de esclarecimento seguida já entrega a conversa.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at
from src.services import desambiguacao as ds
from src.services import opcoes_numeradas as on
from src.services.ai_tools import ToolExecutor, get_tool_definitions
from src.services.bot_policy import MOTIVO_INCOMPREENSAO
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, ToolExecutorFalso, mensagem, monta_agente, texto_do_modelo,
)

VIRILHAS = [
    {"id": "fca3a9f6", "label": "Virilha Cavada"},
    {"id": "6c700b63", "label": "Virilha Completa"},
    {"id": "15d673d0", "label": "Virilha Simples"},
    {"id": "9fb59f78", "label": "1/2 Virilha"},
]
TRES = VIRILHAS[:3]


def present_options(options, message="Temos alguns tipos de virilha. Qual você prefere?", id_="t1"):
    return {"content": [{"type": "tool_use", "id": id_, "name": "present_options",
                         "input": {"message": message, "options": options}}],
            "stop_reason": "tool_use"}


def pede(candidatas, id_="t1"):
    return {"content": [{"type": "tool_use", "id": id_, "name": "pedir_esclarecimento",
                         "input": {"candidatas": candidatas}}], "stop_reason": "tool_use"}


class TestResolve(unittest.TestCase):

    def setUp(self):
        self.s = {}
        on.guarda(self.s, VIRILHAS)

    def test_digito_vira_a_opcao(self):
        self.assertEqual(on.resolve(self.s, "1")["label"], "Virilha Cavada")
        self.assertEqual(on.resolve(self.s, "2")["label"], "Virilha Completa")
        self.assertEqual(on.resolve(self.s, "4")["label"], "1/2 Virilha")

    def test_formas_de_escrever_o_numero(self):
        for texto in ["1", " 1 ", "1.", "1)", "1 -", "opção 1", "opcao 1", "a 1", "número 1", "Número 1"]:
            with self.subTest(texto=texto):
                self.assertEqual(on.resolve(self.s, texto)["label"], "Virilha Cavada")

    def test_fora_do_intervalo_fica_para_o_modelo(self):
        self.assertIsNone(on.resolve(self.s, "5"))
        self.assertIsNone(on.resolve(self.s, "0"))
        self.assertIsNone(on.resolve(self.s, "12"))

    def test_texto_que_nao_e_numero_fica_para_o_modelo(self):
        for texto in ["Virilha Cavada", "1 e 2", "quero a 1 e a 3", "dia 22", "15h40", "sim", ""]:
            with self.subTest(texto=texto):
                self.assertIsNone(on.resolve(self.s, texto))

    def test_sem_lista_na_sessao_nada_resolve(self):
        self.assertIsNone(on.resolve({}, "1"))
        self.assertIsNone(on.resolve(None, "1"))
        on.limpa(self.s)
        self.assertIsNone(on.resolve(self.s, "1"))

    def test_guarda_substitui_a_lista_anterior(self):
        on.guarda(self.s, [{"id": "d1", "label": "Qua, 21/10"}, {"id": "d2", "label": "Qui, 22/10"},
                           {"id": "d3", "label": "Ter, 27/10"}, {"id": "d4", "label": "Qua, 28/10"}])
        self.assertEqual(on.resolve(self.s, "1")["label"], "Qua, 21/10")

    def test_limpa_preserva_o_resto_do_bloco(self):
        s = {on.CAMPO: {ds.CHAVE: 1}}
        on.guarda(s, VIRILHAS)
        on.limpa(s)
        self.assertEqual(s[on.CAMPO], {ds.CHAVE: 1})

    def test_numeracao_enviada_e_a_mesma_que_resolve_le(self):
        texto = on.numerada(VIRILHAS)
        for i, opt in enumerate(VIRILHAS, 1):
            self.assertIn(f"{i}. {opt['label']}", texto)
            self.assertEqual(on.resolve(self.s, str(i)), {"id": opt["id"], "label": opt["label"]})


class TestTool(unittest.TestCase):

    def test_descricao_explica_a_lista_numerada(self):
        tools = {t["name"]: t for t in get_tool_definitions(format="anthropic")}
        d = tools["present_options"]["description"]
        self.assertIn("numbered", d)
        self.assertIn("label", d)


class ExecutorReal(ToolExecutorFalso):
    """present_options e pedir_esclarecimento de verdade; o resto falso."""

    def __init__(self):
        super().__init__({"ok": True})
        self.real = object.__new__(ToolExecutor)
        self.real.db = mock.MagicMock()

    def execute(self, nome, args, context=None):
        self.chamadas.append(nome)
        if nome == "present_options":
            return self.real._tool_present_options(args, CLINIC, "55", context or {})
        if nome == "pedir_esclarecimento":
            return self.real._tool_pedir_esclarecimento(args, CLINIC, "55", context or {})
        return super().execute(nome, args, context)


class TestNoAgente(unittest.TestCase):

    def _agente(self, roteiro, sessao=None):
        anthropic = AnthropicRoteiro(roteiro)
        agente = monta_agente(anthropic=anthropic, tool_executor=ExecutorReal())
        agente.db = mock.MagicMock()
        agente.db.execute_query.return_value = [{"id": "tarefa-1"}]
        if sessao:
            agente.sessao_salva.update(sessao)
        return agente, anthropic

    def _ultima_mensagem_da_pessoa(self, anthropic):
        """O que o modelo recebeu como fala da pessoa no último turno."""
        mensagens = anthropic.conversas[-1]
        ultimo = [m for m in mensagens if m["role"] == "user" and isinstance(m["content"], str)][-1]
        # O agente prefixa blocos (calendário, dados consultados); a fala da
        # pessoa é a última linha.
        return ultimo["content"].strip().splitlines()[-1]

    def test_quatro_opcoes_saem_numeradas_e_ficam_na_sessao(self):
        agente, _ = self._agente([present_options(VIRILHAS), texto_do_modelo("Qual delas?")])
        saida = agente.process_message(CLINIC, mensagem("Só a virilha mesmo"))
        self.assertEqual(saida[0].message_type, "text")
        self.assertIn("1. Virilha Cavada", saida[0].content)
        self.assertIn("4. 1/2 Virilha", saida[0].content)
        self.assertEqual([o["label"] for o in on.pendentes(agente.sessao_salva)],
                         [o["label"] for o in VIRILHAS])

    def test_tres_opcoes_saem_como_botoes_e_nao_ficam_na_sessao(self):
        agente, _ = self._agente([present_options(TRES), texto_do_modelo("")])
        saida = agente.process_message(CLINIC, mensagem("virilha"))
        self.assertEqual(saida[0].message_type, "buttons")
        self.assertEqual(on.pendentes(agente.sessao_salva), [])

    def test_o_caso_de_16_10_o_1_chega_ao_modelo_como_virilha_cavada(self):
        """A conversa da Haylla. Turno 1: a lista. Turno 2: ela responde "1";
        o modelo tem de ler "Virilha Cavada", não "1"."""
        agente, anthropic = self._agente([
            present_options(VIRILHAS), texto_do_modelo("Qual delas?"),
            texto_do_modelo("Virilha Cavada, ótimo! Vamos ver as datas."),
        ])
        agente.process_message(CLINIC, mensagem("Só a virilha mesmo"))
        agente.process_message(CLINIC, mensagem("1"))
        self.assertIn("Virilha Cavada", self._ultima_mensagem_da_pessoa(anthropic))
        self.assertNotIn("pedir_esclarecimento", agente.tool_executor.chamadas)
        self.assertEqual(ds.tentativas(agente.sessao_salva), 0)

    def test_a_lista_some_quando_o_bot_fala_outra_coisa(self):
        """Depois de "Virilha Cavada" o bot segue para datas sem lista; um "1"
        solto agora não é mais a Cavada."""
        agente, anthropic = self._agente([
            present_options(VIRILHAS), texto_do_modelo(""),
            texto_do_modelo("Perfeito. Quer ver as datas?"),
            texto_do_modelo("..."),
        ])
        agente.process_message(CLINIC, mensagem("virilha"))
        agente.process_message(CLINIC, mensagem("1"))
        self.assertEqual(on.pendentes(agente.sessao_salva), [])
        agente.process_message(CLINIC, mensagem("1"))
        self.assertEqual(self._ultima_mensagem_da_pessoa(anthropic), "1")

    def test_a_lista_de_datas_do_dia_13(self):
        """A conversa da Rege: 4 datas numeradas e "1" como resposta."""
        datas = [{"id": "2026-10-21", "label": "Qua, 21/10"}, {"id": "2026-10-22", "label": "Qui, 22/10"},
                 {"id": "2026-10-27", "label": "Ter, 27/10"}, {"id": "2026-10-28", "label": "Qua, 28/10"}]
        agente, anthropic = self._agente([
            present_options(datas, message="Essas são as próximas datas disponíveis:"), texto_do_modelo(""),
            texto_do_modelo("Vou ver os horários dessa data."),
        ])
        agente.process_message(CLINIC, mensagem("sim"))
        agente.process_message(CLINIC, mensagem("1"))
        self.assertEqual(self._ultima_mensagem_da_pessoa(anthropic), "Qua, 21/10")

    def test_segunda_pergunta_de_esclarecimento_seguida_ja_entrega(self):
        """O outro defeito de 16/10: a entrega vinha só na TERCEIRA pergunta,
        e quem para de responder depois da segunda fica sem ninguém. Agora a
        segunda ambiguidade seguida vai a pessoa, com aviso e tarefa."""
        agente, _ = self._agente([pede(["agendar", "duvida"]), texto_do_modelo("")],
                                 sessao={ds.CAMPO: {ds.CHAVE: 1}})
        saida = agente.process_message(CLINIC, mensagem("2"))
        self.assertEqual([m.content for m in saida], [ds.TEXTO_DE_ESGOTAMENTO])
        sessao = agente.sessao_salva
        self.assertEqual(at.estado(sessao), at.HUMAN_ACTIVE)
        self.assertEqual(sessao[at.CAMPO]["handoff_reason"], MOTIVO_INCOMPREENSAO)
        self.assertEqual(sessao[at.CAMPO]["pending_task_id"], "tarefa-1")

    def test_prompt_diz_que_resposta_a_opcao_nao_e_incompreensao(self):
        import inspect
        from src.services.conversation_agent import ConversationAgent
        fonte = inspect.getsource(ConversationAgent._build_system_prompt)
        self.assertIn("lista", fonte)
        self.assertIn("numerada", fonte)
