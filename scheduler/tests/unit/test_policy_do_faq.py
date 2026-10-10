# -*- coding: utf-8 -*-
"""O FAQ entregue palavra por palavra (PRD 020 §4.3, fase 5).

Decisão do André (10/10/2026): se a clínica escreveu a resposta, ela vai como
está. O modelo escolhe o item numa lista fechada; o texto vai em bolha
própria; a fala do modelo que repete o item é descartada.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at
from src.services import policy_do_faq as pf
from src.services.ai_tools import ToolExecutor, get_tool_definitions
from src.services.bot_policy import MOTIVO_SEM_RESPOSTA
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, ToolExecutorFalso, mensagem, monta_agente, texto_do_modelo,
)

MENSTRUACAO = (
    "Sim, pode fazer menstruada! 😊 A única recomendação é usar absorvente interno "
    "ou coletor no dia da sessão, para o conforto durante o procedimento na virilha."
)
INTERVALO = (
    "O intervalo entre as sessões é de aproximadamente 30 dias, podendo variar um "
    "pouco para mais ou para menos conforme as datas de cada mês."
)
FAQ = [
    {"question_key": "MENSTRUATION", "question_label": "Posso fazer menstruada?", "answer": MENSTRUACAO},
    {"question_key": "SESSION_INTERVAL", "question_label": "Qual o intervalo entre as sessões?", "answer": INTERVALO},
    {"question_key": "PAIN", "question_label": "Dói?", "answer": "Incomoda pouco, é bem tolerável."},
]


def usa_faq(chave, id_="t1"):
    return {"content": [{"type": "tool_use", "id": id_, "name": "get_faq_answer",
                         "input": {"question_key": chave}}], "stop_reason": "tool_use"}


def usa_duas(chave1, chave2):
    return {"content": [
        {"type": "tool_use", "id": "t1", "name": "get_faq_answer", "input": {"question_key": chave1}},
        {"type": "tool_use", "id": "t2", "name": "get_faq_answer", "input": {"question_key": chave2}},
    ], "stop_reason": "tool_use"}


class TestDefinicaoDaTool(unittest.TestCase):

    def test_enum_fechado_com_as_chaves_da_clinica(self):
        d = pf.definicao_da_tool(FAQ)
        self.assertEqual(d["function"]["name"], "get_faq_answer")
        schema = d["function"]["parameters"]
        self.assertEqual(schema["properties"]["question_key"]["enum"],
                         ["MENSTRUATION", "SESSION_INTERVAL", "PAIN"])
        self.assertEqual(schema["required"], ["question_key"])
        self.assertNotIn("question", schema["properties"], "não há texto livre")
        self.assertIn("Posso fazer menstruada?", d["function"]["description"])
        self.assertIn("NOT repeat", d["function"]["description"])

    def test_sem_itens_a_tool_nao_existe(self):
        self.assertIsNone(pf.definicao_da_tool([]))
        nomes = {t["name"] for t in get_tool_definitions(format="anthropic", faq=[])}
        self.assertNotIn("get_faq_answer", nomes)
        nomes = {t["name"] for t in get_tool_definitions(format="anthropic")}
        self.assertNotIn("get_faq_answer", nomes)

    def test_com_itens_entra_no_formato_anthropic(self):
        tools = get_tool_definitions(format="anthropic", faq=FAQ)
        faq = next(t for t in tools if t["name"] == "get_faq_answer")
        self.assertEqual(faq["input_schema"]["properties"]["question_key"]["enum"][0], "MENSTRUATION")
        self.assertEqual(len([t for t in tools if t["name"] == "get_faq_answer"]), 1)


class TestItens(unittest.TestCase):

    def test_le_os_ativos_na_ordem_do_painel(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [
            {"question_key": "PAIN", "question_label": "Dói?", "answer": "Não."},
            {"question_key": "", "question_label": "sem chave", "answer": "x"},
            {"question_key": "VAZIO", "question_label": "sem resposta", "answer": ""},
        ]
        itens = pf.itens(db, CLINIC)
        self.assertEqual([i["question_key"] for i in itens], ["PAIN"])
        sql = db.execute_query.call_args[0][0]
        self.assertIn("active = true", sql)

    def test_banco_fora_nao_derruba(self):
        db = mock.MagicMock()
        db.execute_query.side_effect = RuntimeError("down")
        self.assertEqual(pf.itens(db, CLINIC), [])
        self.assertEqual(pf.itens(None, CLINIC), [])


class TestRepeteOItem(unittest.TestCase):

    def test_copia_inteira(self):
        self.assertTrue(pf.repete_o_item(MENSTRUACAO, MENSTRUACAO))

    def test_copia_sem_acento_sem_negrito(self):
        fala = "*Sim, pode fazer menstruada!* A unica recomendacao e usar absorvente interno ou coletor no dia da sessao, para o conforto durante o procedimento na virilha"
        self.assertTrue(pf.repete_o_item(fala, MENSTRUACAO))

    def test_metade_das_frases_e_repeticao(self):
        fala = "Pode sim! A única recomendação é usar absorvente interno ou coletor no dia da sessão, para o conforto durante o procedimento na virilha. Quer marcar?"
        self.assertTrue(pf.repete_o_item(fala, MENSTRUACAO))

    def test_resposta_propria_passa(self):
        self.assertFalse(pf.repete_o_item("Para o dia 21 tenho 16:25. Fica bom?", INTERVALO))
        self.assertFalse(pf.repete_o_item("", INTERVALO))

    def test_fala_sem_o_item(self):
        self.assertEqual(pf.fala_sem_o_item(MENSTRUACAO, FAQ[:1]), "")
        self.assertEqual(pf.fala_sem_o_item("Tenho 16:25 no dia 21.", FAQ[:1]), "Tenho 16:25 no dia 21.")


class TestExecutor(unittest.TestCase):

    def _executor(self):
        ex = object.__new__(ToolExecutor)
        ex.db = mock.MagicMock()
        ex.db.execute_query.return_value = []
        return ex

    def test_entrega_o_item_e_manda_nao_repetir(self):
        ex = self._executor()
        ctx = {"faq": FAQ, "faq_entregues": []}
        r = ex._tool_get_faq_answer({"question_key": "MENSTRUATION"}, CLINIC, "55", ctx)
        self.assertTrue(r["delivered"])
        self.assertIn("Do NOT repeat", r["instruction"])
        self.assertNotIn(MENSTRUACAO, str(r), "o texto nao volta ao modelo")
        self.assertEqual(ctx["faq_entregues"][0]["question_key"], "MENSTRUATION")

    def test_chave_inventada_e_erro_sem_entregar(self):
        ex = self._executor()
        ctx = {"faq": FAQ, "faq_entregues": []}
        r = ex._tool_get_faq_answer({"question_key": "GRAVIDEZ"}, CLINIC, "55", ctx)
        self.assertIn("error", r)
        self.assertIn(MOTIVO_SEM_RESPOSTA, r["error"])
        self.assertEqual(ctx["faq_entregues"], [])

    def test_texto_livre_do_formato_antigo_e_erro(self):
        ex = self._executor()
        r = ex._tool_get_faq_answer({"question": "dói?"}, CLINIC, "55", {"faq": FAQ, "faq_entregues": []})
        self.assertIn("error", r)

    def test_sem_faq_no_contexto_consulta_o_banco(self):
        ex = self._executor()
        ex.db.execute_query.return_value = [FAQ[2]]
        r = ex._tool_get_faq_answer({"question_key": "PAIN"}, CLINIC, "55", {"faq_entregues": []})
        self.assertTrue(r["delivered"])


class ExecutorComFaq(ToolExecutorFalso):
    """Executa get_faq_answer de verdade (o executor real) e o resto como o falso."""

    def __init__(self):
        # get_time_slots devolve um horario de verdade: a proveniencia barra
        # "16:25" se nenhuma tool o trouxe.
        super().__init__({"available_slots": ["16:25"]})
        self.real = object.__new__(ToolExecutor)
        self.real.db = mock.MagicMock()

    def execute(self, nome, args, context=None):
        self.chamadas.append(nome)
        if nome == "get_faq_answer":
            return self.real._tool_get_faq_answer(args, CLINIC, "55", context or {})
        return super().execute(nome, args, context)


def agente_com_faq(anthropic):
    agente = monta_agente(anthropic=anthropic, tool_executor=ExecutorComFaq())
    # Sem banco no duble: o FAQ da clinica entra por aqui.
    with mock.patch.object(pf, "itens", return_value=list(FAQ)):
        yield agente


class TestNoAgente(unittest.TestCase):

    def _roda(self, roteiro, texto="posso fazer menstruada?"):
        anthropic = AnthropicRoteiro(roteiro)
        agente = monta_agente(anthropic=anthropic, tool_executor=ExecutorComFaq())
        agente.db = mock.MagicMock()
        agente.db.execute_query.return_value = [{"id": "tarefa-1"}]
        with mock.patch.object(pf, "itens", return_value=list(FAQ)):
            saida = agente.process_message(CLINIC, mensagem(texto))
        return saida, anthropic, agente

    def test_a_tool_oferecida_ao_modelo_tem_o_enum_da_clinica(self):
        anthropic = AnthropicRoteiro([texto_do_modelo("Oi!")])
        agente = monta_agente(anthropic=anthropic)
        original = anthropic.create_message
        vistas = []

        def create_message(system, messages, tools, max_tokens, tool_choice=None):
            vistas.append(tools)
            return original(system, messages, tools, max_tokens, tool_choice)

        anthropic.create_message = create_message
        with mock.patch.object(pf, "itens", return_value=list(FAQ)):
            agente.process_message(CLINIC, mensagem("oi"))
        faq = next(t for t in vistas[0] if t["name"] == "get_faq_answer")
        self.assertEqual(faq["input_schema"]["properties"]["question_key"]["enum"][0], "MENSTRUATION")

    def test_o_texto_da_clinica_sai_em_bolha_propria_byte_a_byte(self):
        saida, anthropic, _ = self._roda([usa_faq("MENSTRUATION"), texto_do_modelo("")])
        self.assertEqual([m.content for m in saida], [MENSTRUACAO])
        self.assertEqual(saida[0].message_type, "text")

    def test_fala_do_modelo_que_repete_o_item_e_descartada(self):
        saida, _, _ = self._roda([usa_faq("MENSTRUATION"), texto_do_modelo(
            "Sim, pode fazer menstruada! A única recomendação é usar absorvente interno ou "
            "coletor no dia da sessão, para o conforto durante o procedimento na virilha. 😊")])
        self.assertEqual([m.content for m in saida], [MENSTRUACAO], "a bolha literal basta")

    def test_duas_perguntas_duas_bolhas_e_a_fala_propria_depois(self):
        """'qual o intervalo e tem horário dia 21?': o item numa bolha, os
        horários (consultados) em outra, nunca juntos."""
        saida, _, _ = self._roda(
            [usa_faq("SESSION_INTERVAL"),
             {"content": [{"type": "tool_use", "id": "t2", "name": "get_time_slots", "input": {}}],
              "stop_reason": "tool_use"},
             texto_do_modelo("E para o dia 21 tenho 16:25. Fica bom?")],
            texto="qual o intervalo entre as sessões e tem horário dia 21?")
        self.assertEqual(len(saida), 2)
        self.assertEqual(saida[0].content, INTERVALO)
        self.assertIn("16:25", saida[1].content)
        self.assertNotIn(INTERVALO, saida[1].content)

    def test_dois_itens_cada_um_em_sua_bolha(self):
        saida, _, _ = self._roda([usa_duas("MENSTRUATION", "PAIN"), texto_do_modelo("")],
                                 texto="posso menstruada? e dói?")
        self.assertEqual([m.content for m in saida], [MENSTRUACAO, "Incomoda pouco, é bem tolerável."])

    def test_tres_itens_e_pergunta_confusa_vai_a_pessoa(self):
        saida, _, agente = self._roda(
            [usa_duas("MENSTRUATION", "PAIN"), usa_faq("SESSION_INTERVAL", "t3"), texto_do_modelo("")],
            texto="tudo sobre o laser")
        self.assertEqual(len(saida), 1)
        self.assertIn("especialista", saida[0].content)
        self.assertNotIn(MENSTRUACAO, saida[0].content)
        sessao = agente.sessao_salva
        self.assertEqual(at.estado(sessao), at.HUMAN_ACTIVE)
        self.assertEqual(sessao[at.CAMPO]["handoff_reason"], MOTIVO_SEM_RESPOSTA)

    def test_chave_inventada_nao_entrega_nada(self):
        saida, anthropic, _ = self._roda([usa_faq("GRAVIDEZ"), texto_do_modelo("Vou confirmar com a equipe e já te retorno 😊")])
        self.assertEqual(len(saida), 1)
        self.assertNotIn(MENSTRUACAO, saida[0].content)
        ultimo_resultado = anthropic.conversas[-1][-1]["content"][0]["content"]
        self.assertIn("error", ultimo_resultado)

    def test_o_historico_salvo_nao_carrega_o_texto_do_item(self):
        """O item nao volta ao modelo (nem no tool_result): o que ele le e o
        aviso de que foi entregue. O texto da clinica nao vira contexto que
        o modelo possa reformular numa mensagem seguinte."""
        _, _, agente = self._roda([usa_faq("MENSTRUATION"), texto_do_modelo("")])
        self.assertNotIn(MENSTRUACAO, str(agente.sessao_salva.get("agent_history")))


class TestPrompt(unittest.TestCase):

    def test_o_bloco_de_duvidas_manda_nao_repetir(self):
        from src.services.conversation_agent import ConversationAgent
        import inspect
        fonte = inspect.getsource(ConversationAgent._build_system_prompt)
        self.assertIn("NÃO o repita, NÃO o resuma", fonte)
        self.assertNotIn("Pode resumir e adaptar o tom", fonte)


if __name__ == "__main__":
    unittest.main()
