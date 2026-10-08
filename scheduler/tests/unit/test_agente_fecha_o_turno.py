# -*- coding: utf-8 -*-
"""O turno do agente termina com uma resposta ou com uma pessoa - nunca com
o aviso que o modelo escreveu junto de uma ferramenta.

Em 08/10/2026, duas pacientes da Essência receberam "Agora vamos ver os
horários disponíveis" / "Vou confirmar os horários disponíveis" e mais nada:
o laço estourou as 5 rodadas no meio das consultas e mandou como resposta o
texto que veio junto da última tool. Uma delas respondeu "Sim" e o bot propôs
o único horário que tinha visto, sem a pessoa nunca ter visto a lista.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at
from src.services import conversation_agent as modulo
from src.services.bot_policy import MOTIVO_ESGOTOU
from src.services.conversation_agent import MAX_AGENT_ITERATIONS, _anexa_ao_turno_do_usuario
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, mensagem, monta_agente, texto_do_modelo, usa_tool,
)


def narra_e_usa_tool(texto, nome):
    """Texto E tool_use no mesmo bloco: 'vou ver os horários' + check_availability."""
    return {
        "content": [
            {"type": "text", "text": texto},
            {"type": "tool_use", "id": "t1", "name": nome, "input": {}},
        ],
        "stop_reason": "tool_use",
    }


class TestNarracaoNaoEResposta(unittest.TestCase):

    def test_texto_junto_da_tool_nao_sai_quando_vem_resposta_depois(self):
        anthropic = AnthropicRoteiro([
            narra_e_usa_tool("Agora vamos ver os horários disponíveis.", "get_time_slots"),
            texto_do_modelo("Para o dia 21 tenho 16:25. Fica bom?"),
        ])
        agente = monta_agente(anthropic=anthropic, resultado_da_tool={"available_slots": ["16:25"]})
        saida = agente.process_message(CLINIC, mensagem("dia 21, axilas"))
        self.assertEqual(len(saida), 1)
        self.assertIn("16:25", saida[0].content)
        self.assertNotIn("vamos ver", saida[0].content)


class TestEstourouAsRodadas(unittest.TestCase):

    def _roteiro_que_so_consulta(self, fim):
        """MAX rodadas de ferramenta, todas narrando, e então `fim`."""
        return [narra_e_usa_tool("Vou confirmar os horários disponíveis.", "get_time_slots")
                for _ in range(MAX_AGENT_ITERATIONS)] + [fim]

    def test_fechamento_sem_ferramentas_responde_com_o_que_apurou(self):
        anthropic = AnthropicRoteiro(self._roteiro_que_so_consulta(
            texto_do_modelo("Tenho 09:35 disponível. Fica bom?")
        ))
        agente = monta_agente(anthropic=anthropic, resultado_da_tool={"available_slots": ["09:35"]})
        saida = agente.process_message(CLINIC, mensagem("27/10, perna inteira, axila e buço"))

        self.assertEqual(anthropic.chamadas, MAX_AGENT_ITERATIONS + 1)
        self.assertEqual(anthropic.forcados[-1], {"type": "none"}, "o fechamento é sem ferramentas")
        self.assertEqual(len(saida), 1)
        self.assertIn("09:35", saida[0].content)
        self.assertNotIn("Vou confirmar", saida[0].content, "a narração nunca vira resposta")
        ultima_conversa = anthropic.conversas[-1]
        self.assertEqual(ultima_conversa[-1]["role"], "user")
        self.assertIn("PARE.", str(ultima_conversa[-1]["content"]))

    def test_sem_resposta_no_fechamento_cala_e_entrega_a_uma_pessoa(self):
        anthropic = AnthropicRoteiro(self._roteiro_que_so_consulta(
            usa_tool("get_time_slots")  # insistiu em ferramenta no fechamento
        ))
        agente = monta_agente(anthropic=anthropic, resultado_da_tool={"available_slots": []})
        agente.db = mock.MagicMock()
        agente.db.execute_query.return_value = [{"id": "tarefa-1"}]
        saida = agente.process_message(CLINIC, mensagem("27/10, perna inteira"))

        self.assertEqual(saida, [], "nada de 'vou confirmar os horários' sozinho")
        sessao = agente.sessao_salva
        self.assertEqual(at.estado(sessao), at.HUMAN_ACTIVE, "a pessoa ficou com uma atendente")
        self.assertEqual(sessao[at.CAMPO]["handoff_reason"], MOTIVO_ESGOTOU)
        self.assertIsNotNone(sessao[at.CAMPO].get("pending_intent"), "a fila vê a pendência")

    def test_historico_salvo_continua_valido_sem_tool_use_pendente(self):
        """O fechamento que pediu ferramenta não entra no histórico: um
        tool_use sem tool_result derrubaria a próxima mensagem num 400."""
        anthropic = AnthropicRoteiro(self._roteiro_que_so_consulta(usa_tool("get_time_slots")))
        agente = monta_agente(anthropic=anthropic, resultado_da_tool={})
        agente.process_message(CLINIC, mensagem("27/10"))
        historico = agente.sessao_salva.get("agent_history") or []
        for turno in historico:
            if turno["role"] == "assistant" and isinstance(turno["content"], list):
                ids = [b["id"] for b in turno["content"] if b.get("type") == "tool_use"]
                seguinte = historico[historico.index(turno) + 1] if historico.index(turno) + 1 < len(historico) else None
                if ids:
                    self.assertIsNotNone(seguinte, "tool_use sem tool_result no fim do histórico")
                    respondidos = [b.get("tool_use_id") for b in seguinte["content"] if isinstance(b, dict)]
                    for i in ids:
                        self.assertIn(i, respondidos)

    def test_caminho_feliz_de_cinco_consultas_cabe_sem_fechamento(self):
        """list_services, list_areas, calculate_discount, check_availability,
        get_time_slots e a resposta: era exatamente o que não cabia em 5."""
        roteiro = [usa_tool(n) for n in ("list_services", "list_areas", "calculate_discount",
                                         "check_availability", "get_time_slots")]
        roteiro.append(texto_do_modelo("Tenho 16:25 no dia 21. Pode ser?"))
        anthropic = AnthropicRoteiro(roteiro)
        agente = monta_agente(anthropic=anthropic, resultado_da_tool={"available_slots": ["16:25"]})
        saida = agente.process_message(CLINIC, mensagem("dia 21, axilas"))
        self.assertEqual(anthropic.chamadas, 6)
        self.assertNotIn({"type": "none"}, anthropic.forcados, "não precisou do fechamento")
        self.assertIn("16:25", saida[0].content)


class TestAnexaAoTurnoDoUsuario(unittest.TestCase):
    """Dois turnos `user` seguidos são 400 na API; o PARE do fechamento se
    junta ao turno anterior quando ele já é do usuário."""

    def test_depois_de_tool_results_vira_bloco_de_texto(self):
        h = [{"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "x", "input": {}}]},
             {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{}"}]}]
        _anexa_ao_turno_do_usuario(h, "PARE. responda")
        self.assertEqual(len(h), 2)
        self.assertEqual(h[-1]["content"][-1], {"type": "text", "text": "PARE. responda"})

    def test_depois_de_um_pare_em_texto_concatena(self):
        h = [{"role": "assistant", "content": "oi"}, {"role": "user", "content": "PARE. consulte"}]
        _anexa_ao_turno_do_usuario(h, "PARE. responda")
        self.assertEqual(len(h), 2)
        self.assertTrue(h[-1]["content"].endswith("PARE. responda"))

    def test_depois_do_assistente_cria_turno_novo(self):
        h = [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "olá"}]
        _anexa_ao_turno_do_usuario(h, "PARE. responda")
        self.assertEqual(len(h), 3)
        self.assertEqual(h[-1], {"role": "user", "content": "PARE. responda"})


class TestListAreasSemServico(unittest.TestCase):
    """`list_areas` sem service_ids (ou com "<UNKNOWN>") custava duas rodadas:
    o erro, list_services e list_areas de novo. Agora usa os serviços ativos."""

    SERVICO = "e5c550d6-6deb-434b-b42d-13137af071a8"

    def _executor(self):
        from src.services.ai_tools import ToolExecutor
        ex = object.__new__(ToolExecutor)
        db = mock.MagicMock()
        self.consultas = []

        def query(sql, params=None):
            self.consultas.append((sql, params))
            if "FROM scheduler.services" in sql and "WHERE clinic_id" in sql:
                return [{"id": self.SERVICO, "name": "Depilação a Laser", "description": "",
                         "duration_minutes": 20, "price_cents": 15000}]
            if "FROM scheduler.service_areas sa" in sql:
                return [{"service_area_id": "sa1", "service_id": self.SERVICO, "service_name": "Depilação a Laser",
                         "area_id": "a1", "area_name": "Axilas", "duration_minutes": 10, "price_cents": 6500}]
            return []

        db.execute_query.side_effect = query
        ex.db = db
        return ex

    def test_sem_service_ids_usa_os_servicos_da_clinica(self):
        ex = self._executor()
        r = ex._tool_list_areas({"service_ids": []}, CLINIC, "55", {})
        self.assertNotIn("error", r)
        self.assertEqual([a["area_name"] for a in r["areas"]], ["Axilas"])
        self.assertEqual(self.consultas[-1][1], (self.SERVICO,))

    def test_placeholder_do_modelo_nao_vai_ao_banco(self):
        ex = self._executor()
        r = ex._tool_list_areas({"service_ids": ["<UNKNOWN>"]}, CLINIC, "55", {})
        self.assertNotIn("error", r)
        for sql, params in self.consultas:
            self.assertNotIn("<UNKNOWN>", str(params))

    def test_service_id_valido_continua_direto(self):
        ex = self._executor()
        ex._tool_list_areas({"service_ids": [self.SERVICO]}, CLINIC, "55", {})
        self.assertEqual(len(self.consultas), 1, "não consultou list_services à toa")


if __name__ == "__main__":
    unittest.main()
