# -*- coding: utf-8 -*-
"""Fase 6: perguntar antes de desistir, e desistir depois de duas (PRD 020 §4.1).

A pergunta é texto fixo com botões; o modelo só escolhe as opções. O contador
vive na sessão, zera quando uma intenção se resolve, e na terceira
ambiguidade seguida a conversa vai a pessoa com `incompreensao`.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at
from src.services import desambiguacao as ds
from src.services import policy_do_faq as pf
from src.services.ai_tools import ToolExecutor, get_tool_definitions
from src.services.bot_policy import MOTIVO_INCOMPREENSAO, MOTIVO_PEDIDO
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, ToolExecutorFalso, mensagem, monta_agente, texto_do_modelo,
)


def pede(candidatas, id_="t1"):
    return {"content": [{"type": "tool_use", "id": id_, "name": "pedir_esclarecimento",
                         "input": {"candidatas": candidatas}}], "stop_reason": "tool_use"}


def handoff(reason, id_="t1"):
    return {"content": [{"type": "tool_use", "id": id_, "name": "request_human_handoff",
                         "input": {"reason": reason}}], "stop_reason": "tool_use"}


class TestContador(unittest.TestCase):

    def test_sobe_e_zera(self):
        s = {}
        self.assertEqual(ds.tentativas(s), 0)
        self.assertEqual(ds.registra_tentativa(s), 1)
        self.assertEqual(ds.registra_tentativa(s), 2)
        self.assertTrue(ds.esgotou(s))
        ds.zera(s)
        self.assertEqual(ds.tentativas(s), 0)
        self.assertFalse(ds.esgotou(s))

    def test_zera_nao_cria_o_bloco_a_toa(self):
        s = {}
        ds.zera(s)
        self.assertNotIn(ds.CAMPO, s)

    def test_opcoes_validas_na_ordem_ate_tres(self):
        self.assertEqual([o["id"] for o in ds.opcoes(["duvida", "agendar", "x"])], ["agendar", "duvida"])
        self.assertEqual([o["id"] for o in ds.opcoes(["cancelar", "remarcar", "agendar", "duvida"])],
                         ["agendar", "remarcar", "cancelar"])
        self.assertEqual([o["id"] for o in ds.opcoes([])], list(ds.PADRAO))
        self.assertEqual([o["id"] for o in ds.opcoes(None)], list(ds.PADRAO))

    def test_rotulos_cabem_no_botao(self):
        for rotulo in ds.OPCOES.values():
            self.assertLessEqual(len(rotulo), 24)

    def test_pede_pergunta_e_depois_desiste(self):
        s = {}
        r1 = ds.pede(s, ["agendar", "duvida"])
        self.assertTrue(r1["esclarecimento"])
        self.assertEqual(r1["message"], ds.TEXTO)
        self.assertEqual([o["id"] for o in r1["options"]], ["agendar", "duvida"])
        r2 = ds.pede(s, None)
        self.assertTrue(r2["esclarecimento"])
        r3 = ds.pede(s, None)
        self.assertFalse(r3["esclarecimento"])
        self.assertTrue(r3["handoff_requested"])
        self.assertEqual(r3["reason"], MOTIVO_INCOMPREENSAO)
        self.assertEqual(ds.tentativas(s), 2, "a terceira não conta: já foi a pessoa")


class TestTool(unittest.TestCase):

    def test_exposta_com_enum_fechado(self):
        tools = {t["name"]: t for t in get_tool_definitions(format="anthropic")}
        self.assertIn("pedir_esclarecimento", tools)
        enum = tools["pedir_esclarecimento"]["input_schema"]["properties"]["candidatas"]["items"]["enum"]
        self.assertEqual(enum, ["agendar", "remarcar", "cancelar", "duvida"])

    def test_executor_usa_a_sessao_do_contexto(self):
        ex = object.__new__(ToolExecutor)
        sessao = {}
        r = ex._tool_pedir_esclarecimento({"candidatas": ["remarcar"]}, CLINIC, "55", {"session": sessao})
        self.assertTrue(r["esclarecimento"])
        self.assertEqual(ds.tentativas(sessao), 1)

    def test_handoff_por_incompreensao_vira_pergunta_enquanto_ha_tentativas(self):
        ex = object.__new__(ToolExecutor)
        sessao = {}
        r = ex._tool_request_human_handoff({"reason": MOTIVO_INCOMPREENSAO}, CLINIC, "55", {"session": sessao})
        self.assertTrue(r.get("esclarecimento"))
        self.assertNotIn("handoff_requested", r)
        self.assertEqual(ds.tentativas(sessao), 1)

    def test_handoff_por_incompreensao_passa_quando_esgotou(self):
        ex = object.__new__(ToolExecutor)
        sessao = {ds.CAMPO: {ds.CHAVE: 2}}
        r = ex._tool_request_human_handoff({"reason": MOTIVO_INCOMPREENSAO}, CLINIC, "55", {"session": sessao})
        self.assertTrue(r["handoff_requested"])
        self.assertEqual(r["reason"], MOTIVO_INCOMPREENSAO)

    def test_outros_motivos_de_handoff_nao_mudam(self):
        ex = object.__new__(ToolExecutor)
        r = ex._tool_request_human_handoff({"reason": MOTIVO_PEDIDO}, CLINIC, "55", {"session": {}})
        self.assertTrue(r["handoff_requested"])
        self.assertEqual(r["reason"], MOTIVO_PEDIDO)

    def test_sem_sessao_no_contexto_o_handoff_segue_como_antes(self):
        ex = object.__new__(ToolExecutor)
        r = ex._tool_request_human_handoff({"reason": MOTIVO_INCOMPREENSAO}, CLINIC, "55", {})
        self.assertTrue(r["handoff_requested"])


class ExecutorReal(ToolExecutorFalso):
    """pedir_esclarecimento e request_human_handoff de verdade; o resto falso."""

    def __init__(self, resultado=None):
        super().__init__(resultado or {"ok": True})
        self.real = object.__new__(ToolExecutor)
        self.real.db = mock.MagicMock()

    def execute(self, nome, args, context=None):
        self.chamadas.append(nome)
        if nome == "pedir_esclarecimento":
            return self.real._tool_pedir_esclarecimento(args, CLINIC, "55", context or {})
        if nome == "request_human_handoff":
            return self.real._tool_request_human_handoff(args, CLINIC, "55", context or {})
        return super().execute(nome, args, context)


class TestNoAgente(unittest.TestCase):

    def _agente(self, roteiro, sessao=None, resultado=None):
        anthropic = AnthropicRoteiro(roteiro)
        agente = monta_agente(anthropic=anthropic, tool_executor=ExecutorReal(resultado))
        agente.db = mock.MagicMock()
        agente.db.execute_query.return_value = [{"id": "tarefa-1"}]
        if sessao:
            agente.sessao_salva.update(sessao)
        return agente, anthropic

    def test_pergunta_sai_com_texto_fixo_e_botoes(self):
        agente, _ = self._agente([pede(["agendar", "duvida"]), texto_do_modelo("Você quer agendar ou tirar dúvida?")])
        saida = agente.process_message(CLINIC, mensagem("quero marcar aquele negócio"))
        self.assertEqual(len(saida), 1)
        self.assertEqual(saida[0].message_type, "buttons")
        self.assertEqual(saida[0].content, ds.TEXTO, "a fala do modelo junto da pergunta é descartada")
        self.assertEqual([b["id"] for b in saida[0].buttons], ["agendar", "duvida"])
        self.assertEqual(ds.tentativas(agente.sessao_salva), 1, "o contador fica na sessão gravada")
        self.assertNotEqual(at.estado(agente.sessao_salva), at.HUMAN_ACTIVE)

    def test_terceira_vez_vai_a_pessoa(self):
        agente, _ = self._agente([pede(["agendar"]), texto_do_modelo("")],
                                 sessao={ds.CAMPO: {ds.CHAVE: 2}})
        saida = agente.process_message(CLINIC, mensagem("aquilo"))
        self.assertEqual([m.content for m in saida], [ds.TEXTO_DE_ESGOTAMENTO])
        sessao = agente.sessao_salva
        self.assertEqual(at.estado(sessao), at.HUMAN_ACTIVE)
        self.assertEqual(sessao[at.CAMPO]["handoff_reason"], MOTIVO_INCOMPREENSAO)
        self.assertEqual(sessao[at.CAMPO]["pending_task_id"], "tarefa-1", "a fila vê a tarefa")

    def test_handoff_cedo_por_incompreensao_vira_pergunta(self):
        agente, _ = self._agente([handoff(MOTIVO_INCOMPREENSAO), texto_do_modelo("")])
        saida = agente.process_message(CLINIC, mensagem("hmm"))
        self.assertEqual(saida[0].message_type, "buttons")
        self.assertEqual(saida[0].content, ds.TEXTO)
        self.assertNotEqual(at.estado(agente.sessao_salva), at.HUMAN_ACTIVE)

    def test_tool_com_efeito_zera_o_contador(self):
        agente, _ = self._agente(
            [{"content": [{"type": "tool_use", "id": "t1", "name": "book_appointment", "input": {}}],
              "stop_reason": "tool_use"},
             texto_do_modelo("Agendamento registrado! Uma especialista confirma os detalhes 😊")],
            sessao={ds.CAMPO: {ds.CHAVE: 2}},
            resultado={"success": True, "appointment_id": "a1", "date": "2026-10-21", "time": "16:25"})
        agente.process_message(CLINIC, mensagem("Agendar uma sessão"))
        self.assertEqual(ds.tentativas(agente.sessao_salva), 0)

    def test_faq_entregue_zera_o_contador(self):
        faq = [{"question_key": "PAIN", "question_label": "Dói?", "answer": "Incomoda pouco, é bem tolerável."}]
        anthropic = AnthropicRoteiro([
            {"content": [{"type": "tool_use", "id": "t1", "name": "get_faq_answer", "input": {"question_key": "PAIN"}}],
             "stop_reason": "tool_use"},
            texto_do_modelo("")])

        class Exec(ExecutorReal):
            def execute(self, nome, args, context=None):
                if nome == "get_faq_answer":
                    self.chamadas.append(nome)
                    return self.real._tool_get_faq_answer(args, CLINIC, "55", context or {})
                return super().execute(nome, args, context)

        agente = monta_agente(anthropic=anthropic, tool_executor=Exec())
        agente.sessao_salva.update({ds.CAMPO: {ds.CHAVE: 1}})
        with mock.patch.object(pf, "itens", return_value=faq):
            agente.process_message(CLINIC, mensagem("Tirar uma dúvida: dói?"))
        self.assertEqual(ds.tentativas(agente.sessao_salva), 0)

    def test_prompt_manda_perguntar_antes_de_desistir(self):
        import inspect
        from src.services.conversation_agent import ConversationAgent
        fonte = inspect.getsource(ConversationAgent._build_system_prompt)
        self.assertIn("QUANDO NÃO ENTENDER", fonte)
        self.assertIn("pedir_esclarecimento", fonte)


if __name__ == "__main__":
    unittest.main()
