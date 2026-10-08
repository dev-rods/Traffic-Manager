# -*- coding: utf-8 -*-
"""Tarefa humana (PRD 020 §3.6) e a fala da atendente rotulada no histórico (§3.4)."""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at
from src.services import tarefas
from src.services.conversation_agent import events_to_history, foi_de_pessoa_da_clinica


class TestTarefas(unittest.TestCase):
    def test_abre_devolve_o_id(self):
        db = mock.MagicMock()
        db.execute_query.side_effect = [[], [{"id": "t1"}]]
        self.assertEqual(tarefas.abre(db, "c1", "55", "faq_sem_resposta", "faq_sem_resposta"), "t1")

    def test_uma_aberta_por_conversa(self):
        db = mock.MagicMock()
        db.execute_query.side_effect = [[{"id": "ja-existe"}]]
        self.assertEqual(tarefas.abre(db, "c1", "55", "x", "x"), "ja-existe")
        self.assertEqual(db.execute_query.call_count, 1, "nao insere de novo")

    def test_falha_no_banco_nao_levanta(self):
        db = mock.MagicMock(); db.execute_query.side_effect = RuntimeError("down")
        self.assertIsNone(tarefas.abre(db, "c1", "55", "x", "x"))

    def test_fecha_devolve_o_telefone(self):
        db = mock.MagicMock(); db.execute_query.return_value = [{"phone": "55"}]
        self.assertEqual(tarefas.fecha(db, "c1", "t1", por="1.2.3.4"), {"phone": "55"})
        sql = db.execute_query.call_args[0][0]
        self.assertIn("status = %s", sql)
        self.assertIn("RETURNING phone", sql)

    def test_fechar_tarefa_inexistente(self):
        db = mock.MagicMock(); db.execute_query.return_value = []
        self.assertIsNone(tarefas.fecha(db, "c1", "nao-existe"))


class TestRouterDeTarefas(unittest.TestCase):
    def _evento(self, metodo, resource, **params):
        return {"httpMethod": metodo, "resource": resource, "pathParameters": params,
                "headers": {"x-api-key": "k"}, "requestContext": {"identity": {"sourceIp": "1.2.3.4"}}}

    def test_fechar_move_a_conversa_para_cooldown(self):
        from src.functions.tarefa import router
        import json

        sessao = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="x", agora=0, pending_intent="x")
        at.vincula_tarefa(sessao, "t1")
        gravadas = []
        db = mock.MagicMock(); db.execute_query.return_value = [{"phone": "5511999990000"}]
        with mock.patch.object(router, "require_api_key", return_value=("k", None)), \
             mock.patch("src.services.db.postgres.PostgresService", return_value=db), \
             mock.patch.object(router, "_tabela"), \
             mock.patch.object(router, "carrega_sessao", return_value=sessao), \
             mock.patch.object(router, "grava_atendimento", side_effect=lambda t, c, p, s, **k: gravadas.append(s) or True):
            r = router.handler(self._evento("POST", "/clinics/{clinicId}/tarefas/{tarefaId}/close",
                                            clinicId="c1", tarefaId="t1"), None)
        self.assertEqual(r["statusCode"], 200, r)
        self.assertEqual(json.loads(r["body"])["handler"], at.COOLDOWN)
        self.assertIsNone(gravadas[0][at.CAMPO]["pending_task_id"])

    def test_rota_desconhecida(self):
        from src.functions.tarefa import router
        with mock.patch.object(router, "require_api_key", return_value=("k", None)):
            r = router.handler(self._evento("DELETE", "/x"), None)
        self.assertEqual(r["statusCode"], 404)


class TestFalaDaAtendenteNoHistorico(unittest.TestCase):
    """A fala da atendente virava turno do bot, e ele 'continuava' promessas
    que não fez. Agora entra rotulada, como turno do usuário."""

    def test_marcada_pelo_webhook(self):
        self.assertTrue(foi_de_pessoa_da_clinica({"direction": "OUTBOUND", "status": "SENT",
                                                  "metadata": {"autor": "HUMANO"}}))

    def test_legado_sem_provider_id(self):
        self.assertTrue(foi_de_pessoa_da_clinica({"direction": "OUTBOUND", "status": "SENT"}))

    def test_do_bot(self):
        self.assertFalse(foi_de_pessoa_da_clinica({"direction": "OUTBOUND", "status": "SENT",
                                                   "providerMessageId": "3EB0"}))
        self.assertFalse(foi_de_pessoa_da_clinica({"direction": "INBOUND", "status": "RECEIVED"}))

    def test_historico_rotula_e_alterna(self):
        eventos = [
            {"direction": "INBOUND", "content": "tem desconto?", "status": "RECEIVED"},
            {"direction": "OUTBOUND", "content": "Te dou 20% hoje", "status": "SENT",
             "metadata": {"autor": "HUMANO"}},
            {"direction": "INBOUND", "content": "fechado", "status": "RECEIVED"},
            {"direction": "OUTBOUND", "content": "Agendado!", "status": "SENT", "providerMessageId": "3EB0"},
        ]
        h = events_to_history(eventos)
        self.assertEqual(h[0]["role"], "user")
        self.assertIn("[atendente da clínica]: Te dou 20% hoje", h[0]["content"])
        self.assertIn("fechado", h[0]["content"])
        self.assertEqual(h[1], {"role": "assistant", "content": "Agendado!"})

    def test_o_prompt_explica_o_rotulo(self):
        import inspect
        from src.services.conversation_agent import ConversationAgent
        fonte = inspect.getsource(ConversationAgent._build_system_prompt)
        self.assertIn("FALA DA ATENDENTE", fonte)
        self.assertIn("[atendente da clinica]", fonte)


class TestAgenteNaoTemMaisAPorta(unittest.TestCase):
    def test_is_attendant_active_sumiu(self):
        from src.services.conversation_agent import ConversationAgent
        self.assertFalse(hasattr(ConversationAgent, "_is_attendant_active"))

    def test_chamado_com_pessoa_na_conversa_cala_e_loga(self):
        from tests.unit.dublagem_agente import AnthropicFalso, CLINIC, mensagem, monta_agente
        anthropic = AnthropicFalso("oi")
        agente = monta_agente(anthropic)
        agente.sessao_salva = at.entrega_a_humano({}, por=at.POR_ATENDENTE)
        with self.assertLogs("src.services.conversation_agent", level="ERROR") as log:
            saida = agente.process_message(CLINIC, mensagem("oi"))
        self.assertEqual(saida, [])
        self.assertEqual(anthropic.chamadas, 0)
        self.assertIn("pulou a porta", " ".join(log.output))


if __name__ == "__main__":
    unittest.main()


class TestEspelhoParaOIndice(unittest.TestCase):
    """`handler` e `humanUntil` vão na raiz do item: a GSI não indexa caminho
    aninhado. A fonte continua sendo session.atendimento."""

    def test_update_grava_as_copias_na_raiz(self):
        from src.services.session_store import grava_atendimento
        table = mock.MagicMock()
        table.get_item.return_value = {"Item": {"session": {"x": 1}}}
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=1000)

        self.assertTrue(grava_atendimento(table, "c1", "55", s))

        kw = table.update_item.call_args[1]
        self.assertIn("#h = :h", kw["UpdateExpression"])
        self.assertIn("#hu = :hu", kw["UpdateExpression"])
        self.assertEqual(kw["ExpressionAttributeValues"][":h"], at.HUMAN_ACTIVE)
        self.assertEqual(kw["ExpressionAttributeValues"][":hu"], 1000 + at.TTL_HUMANO)

    def test_sem_prazo_remove_a_copia(self):
        from src.services.session_store import grava_atendimento
        table = mock.MagicMock()
        table.get_item.return_value = {"Item": {"session": {"x": 1}}}
        s = at.retoma_pelo_painel(at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=1000))

        grava_atendimento(table, "c1", "55", s)

        kw = table.update_item.call_args[1]
        self.assertIn("REMOVE", kw["UpdateExpression"])
        self.assertIn("#hu", kw["UpdateExpression"].split("REMOVE")[1])
        self.assertEqual(kw["ExpressionAttributeValues"][":h"], at.BOT_ACTIVE)

    def test_condicao_e_a_versao_lida_e_grava_a_seguinte(self):
        """Duas transições encadeadas, uma escrita: a condição é a versão que
        foi lida (5), o bloco gravado leva 6, e a sessão em memória também."""
        from src.services.session_store import grava_atendimento
        table = mock.MagicMock()
        table.get_item.return_value = {"Item": {"session": {"x": 1}}}
        s = {at.CAMPO: {"handler": at.HUMAN_ACTIVE, "human_until": 900, "versao": 5}}
        at.marca_alerta(s, "fecho_social")
        at.encerra_atendimento_humano(s, agora=1000)

        self.assertTrue(grava_atendimento(table, "c1", "55", s))

        kw = table.update_item.call_args[1]
        self.assertEqual(kw["ExpressionAttributeValues"][":v"], 5)
        self.assertEqual(kw["ExpressionAttributeValues"][":a"]["versao"], 6)
        self.assertEqual(kw["ExpressionAttributeValues"][":a"]["handler"], at.COOLDOWN)
        self.assertEqual(s[at.CAMPO]["versao"], 6)

    def test_conflito_quando_o_banco_ja_passou_da_versao_lida(self):
        from src.services.session_store import grava_atendimento
        table = mock.MagicMock()
        table.get_item.return_value = {"Item": {"session": {"x": 1}}}
        table.update_item.side_effect = type("ConditionalCheckFailedException", (Exception,), {})("x")
        s = {at.CAMPO: {"handler": at.HUMAN_ACTIVE, "human_until": 900, "versao": 5}}
        at.encerra_atendimento_humano(s, agora=1000)
        self.assertFalse(grava_atendimento(table, "c1", "55", s))
        self.assertEqual(s[at.CAMPO]["versao"], 5, "descartada: a memoria nao finge que gravou")

    def test_item_novo_nasce_com_as_copias(self):
        from src.services.session_store import grava_atendimento
        table = mock.MagicMock()
        table.get_item.return_value = {}
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=1000)
        grava_atendimento(table, "c1", "55", s)
        item = table.put_item.call_args[1]["Item"]
        self.assertEqual(item["handler"], at.HUMAN_ACTIVE)
        self.assertEqual(item["humanUntil"], 1000 + at.TTL_HUMANO)
