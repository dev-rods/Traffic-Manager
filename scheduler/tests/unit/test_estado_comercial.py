# -*- coding: utf-8 -*-
"""Estado comercial derivado a cada mensagem (PRD 020 §3.1, fase 4).

Derivado do que `identificar` já traz em uma consulta; nunca gravado. O bloco
QUEM É entra no turno da pessoa e sai do histórico antes de gravar: o estado
de ontem no histórico de hoje seria o cache envelhecido que o PRD proíbe.

Quatro estados. A "janela de retorno" que dividia o último em dois caiu em
09/10/2026 (André): a distinção não mudava a resposta. E o estado nunca muda
o que o bot assume pela pessoa: as áreas são sempre perguntadas.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import estado_comercial as ec
from src.services.conversation_agent import fala_da_pessoa
from src.services.roteador import AGENDAMENTO_PROPRIO, tools_obrigatorias
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, ToolExecutorFalso, mensagem, monta_agente, texto_do_modelo, usa_tool,
)

def paciente(sessoes=0, ultima=None, futuro=None, completo=True, nome="Camila"):
    return {"encontrado": True, "patient_id": "p1", "nome": nome, "cadastro_completo": completo,
            "sessoes_feitas": sessoes, "ultima_sessao": ultima, "agendamento_futuro": futuro}


class TestDeriva(unittest.TestCase):
    """A tabela do PRD, linha a linha."""

    def test_tabela(self):
        casos = [
            ((0, False), ec.NEW_LEAD),
            ((0, True), ec.FIRST_BOOKING),
            ((1, True), ec.ACTIVE_CUSTOMER),
            ((3, False), ec.NO_NEXT_BOOKING),
        ]
        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                self.assertEqual(ec.deriva(*entrada), esperado)

    def test_sao_quatro_estados_e_nenhum_depende_de_janela(self):
        self.assertEqual(ec.ESTADOS, (ec.NEW_LEAD, ec.FIRST_BOOKING, ec.ACTIVE_CUSTOMER, ec.NO_NEXT_BOOKING))
        self.assertFalse(hasattr(ec, "DUE_FOR_NEXT"))
        self.assertFalse(hasattr(ec, "janela_de_retorno"))

    def test_no_show_e_cancelado_nao_sao_sessao(self):
        """Quem chama ja conta so CONFIRMED passado; aqui zero sessao e lead."""
        self.assertEqual(ec.deriva(0, False), ec.NEW_LEAD)


class TestDoPaciente(unittest.TestCase):

    def test_sem_cadastro_e_new_lead_sem_consulta(self):
        self.assertEqual(ec.do_paciente({"encontrado": False}), ec.NEW_LEAD)
        self.assertEqual(ec.do_paciente(None), ec.NEW_LEAD)

    def test_ambigua_e_tratada_como_lead(self):
        self.assertEqual(ec.do_paciente({"encontrado": False, "ambiguo": True}), ec.NEW_LEAD)

    def test_ja_fez_sessao_sem_proxima_e_um_estado_so(self):
        """Com 15 ou 90 dias desde a ultima, o mesmo estado: quem escreve
        querendo marcar quer marcar."""
        self.assertEqual(ec.do_paciente(paciente(sessoes=2, ultima="2026-09-24")), ec.NO_NEXT_BOOKING)
        self.assertEqual(ec.do_paciente(paciente(sessoes=2, ultima="2026-07-01")), ec.NO_NEXT_BOOKING)
        self.assertEqual(ec.do_paciente(paciente(sessoes=2, ultima=None)), ec.NO_NEXT_BOOKING)

    def test_com_futuro(self):
        futuro = {"id": "a1", "data": "2026-10-21", "hora": "16:25"}
        self.assertEqual(ec.do_paciente(paciente(sessoes=0, futuro=futuro)), ec.FIRST_BOOKING)
        self.assertEqual(ec.do_paciente(paciente(sessoes=4, ultima="2026-09-01", futuro=futuro)),
                         ec.ACTIVE_CUSTOMER)


class TestBloco(unittest.TestCase):

    def test_paciente_cadastrada(self):
        b = ec.bloco(paciente(sessoes=3, ultima="2026-09-24", futuro={"data": "2026-10-21", "hora": "16:25"}),
                     ec.ACTIVE_CUSTOMER)
        self.assertTrue(b.startswith(ec.CABECALHO))
        self.assertIn("ACTIVE_CUSTOMER", b)
        self.assertIn("Camila", b)
        self.assertIn("Sessões feitas: 3", b)
        self.assertIn("2026-10-21 às 16:25", b)
        self.assertIn("Não peça nome, nascimento, CPF nem e-mail", b)
        self.assertIn("não apresente a clínica de novo", b)
        self.assertIn("pergunta e confirma com ela", b, "paciente nao e dispensada da confirmacao de areas")

    def test_lead_nova(self):
        b = ec.bloco({"encontrado": False}, ec.NEW_LEAD)
        self.assertIn("Sem cadastro neste telefone", b)
        self.assertNotIn("Não peça nome", b)
        self.assertNotIn("não apresente a clínica", b)

    def test_nunca_sugere_areas_da_ultima_sessao(self):
        """O bloco diz o que o bot DEIXA de fazer; nunca lista areas por ela."""
        b = ec.bloco(paciente(sessoes=5, ultima="2026-09-24"), ec.NO_NEXT_BOOKING)
        self.assertNotIn("mesmas áreas", b.lower())
        self.assertIn("pergunta e confirma", b)

    def test_ambigua_pede_o_nome(self):
        b = ec.bloco({"encontrado": False, "ambiguo": True, "candidatos": ["A", "B"]}, ec.NEW_LEAD)
        self.assertIn("mais de um cadastro", b)

    def test_cadastro_incompleto(self):
        b = ec.bloco(paciente(sessoes=1, completo=False), ec.NO_NEXT_BOOKING)
        self.assertIn("Cadastro incompleto", b)


class TestSemBloco(unittest.TestCase):
    """O que vai para o banco não carrega o QUEM É."""

    TURNO = ("═══ CALENDÁRIO ═══\nHOJE é sexta.\n\n"
             + ec.bloco(paciente(sessoes=1), ec.NO_NEXT_BOOKING) + "\n\n"
             "═══ DADOS CONSULTADOS AGORA ═══\n[x]\n{}\n\n"
             "═══ MENSAGEM DA PESSOA ═══\nquero marcar")

    def test_tira_so_o_bloco(self):
        h = [{"role": "user", "content": self.TURNO}, {"role": "assistant", "content": "ok"}]
        limpo = ec.sem_bloco(h)
        self.assertNotIn(ec.CABECALHO, limpo[0]["content"])
        self.assertNotIn("Sessões feitas", limpo[0]["content"])
        self.assertIn("═══ CALENDÁRIO ═══\nHOJE é sexta.", limpo[0]["content"])
        self.assertIn("═══ DADOS CONSULTADOS AGORA ═══\n[x]", limpo[0]["content"])
        self.assertIn("═══ MENSAGEM DA PESSOA ═══\nquero marcar", limpo[0]["content"])
        self.assertEqual(limpo[1], h[1])

    def test_nao_mexe_no_que_nao_tem_bloco(self):
        h = [{"role": "user", "content": "oi"}, {"role": "user", "content": [{"type": "tool_result"}]}]
        self.assertEqual(ec.sem_bloco(h), h)

    def test_bloco_no_fim_do_turno(self):
        h = [{"role": "user", "content": "x\n\n" + ec.bloco(None, ec.NEW_LEAD)}]
        self.assertEqual(ec.sem_bloco(h)[0]["content"].strip(), "x")


class TestFalaDaPessoa(unittest.TestCase):
    """As travas leem o que a pessoa DISSE, não os blocos do agente."""

    def test_so_a_mensagem(self):
        self.assertEqual(fala_da_pessoa(TestSemBloco.TURNO), "quero marcar")

    def test_sem_marcador_devolve_tudo(self):
        self.assertEqual(fala_da_pessoa("confirmo"), "confirmo")
        self.assertEqual(fala_da_pessoa([{"type": "text", "text": "x"}]), [{"type": "text", "text": "x"}])


class ExecutorQueGuardaOContexto(ToolExecutorFalso):
    def __init__(self):
        super().__init__({"ok": True})
        self.contextos = []

    def execute(self, nome, args, context=None):
        self.contextos.append(context or {})
        return super().execute(nome, args, context)


class TestNoAgente(unittest.TestCase):

    def test_bloco_vai_no_turno_da_pessoa_e_nao_no_prompt(self):
        anthropic = AnthropicRoteiro([texto_do_modelo("Oi, Camila! Quer marcar a próxima?")])
        agente = monta_agente(anthropic=anthropic, paciente=paciente(sessoes=3, ultima="2026-09-24"))
        agente.process_message(CLINIC, mensagem("oi"))

        turno = anthropic.conversas[-1][-1]
        self.assertEqual(turno["role"], "user")
        self.assertIn(ec.CABECALHO, turno["content"])
        self.assertIn("NO_NEXT_BOOKING", turno["content"])
        self.assertIn("═══ MENSAGEM DA PESSOA ═══\noi", turno["content"])
        self.assertNotIn(ec.CABECALHO, anthropic.prompts[-1], "o prefixo cacheado não muda por mensagem")

    def test_bloco_vem_depois_do_calendario_e_antes_dos_dados(self):
        anthropic = AnthropicRoteiro([usa_tool("lookup_appointments"), texto_do_modelo("Está marcada.")])
        agente = monta_agente(anthropic=anthropic, paciente=paciente(sessoes=1),
                              resultado_da_tool={"appointments": []})
        agente.process_message(CLINIC, mensagem("minha sessão amanhã está confirmada?"))
        conteudo = anthropic.conversas[0][-1]["content"]
        i_cal, i_quem, i_dados, i_msg = (conteudo.find(m) for m in (
            "═══ CALENDÁRIO ═══", ec.CABECALHO, "═══ DADOS CONSULTADOS AGORA ═══", "═══ MENSAGEM DA PESSOA ═══"))
        self.assertTrue(0 <= i_cal < i_quem < i_dados < i_msg, (i_cal, i_quem, i_dados, i_msg))

    def test_bloco_nao_e_gravado_na_sessao(self):
        anthropic = AnthropicRoteiro([texto_do_modelo("Oi!")])
        agente = monta_agente(anthropic=anthropic, paciente=paciente(sessoes=3))
        agente.process_message(CLINIC, mensagem("oi"))
        for turno in agente.sessao_salva["agent_history"]:
            self.assertNotIn(ec.CABECALHO, str(turno.get("content")))
        self.assertNotIn("estado_comercial", agente.sessao_salva)

    def test_estado_vai_no_contexto_das_tools(self):
        anthropic = AnthropicRoteiro([usa_tool("list_services"), texto_do_modelo("Temos laser.")])
        executor = ExecutorQueGuardaOContexto()
        agente = monta_agente(anthropic=anthropic, tool_executor=executor, paciente=paciente(sessoes=2))
        agente.process_message(CLINIC, mensagem("o que vocês fazem?"))
        self.assertTrue(executor.contextos)
        self.assertEqual(executor.contextos[-1].get("estado_comercial"), ec.NO_NEXT_BOOKING)

    def test_lead_nova_e_new_lead(self):
        anthropic = AnthropicRoteiro([texto_do_modelo("Oi! Quer conhecer?")])
        agente = monta_agente(anthropic=anthropic, paciente={"encontrado": False})
        agente.process_message(CLINIC, mensagem("oi"))
        self.assertIn("NEW_LEAD", anthropic.conversas[-1][-1]["content"])

    def test_palavra_valor_no_bloco_nao_e_a_pessoa_perguntando(self):
        """O bloco diz 'não repita o valor'; a trava de valor lê só a fala dela."""
        from src.services.conversation_agent import _turnos_para_trava
        h = [{"role": "user", "content": TestSemBloco.TURNO}]
        self.assertEqual(_turnos_para_trava(h), [{"role": "user", "content": "quero marcar"}])


class TestRoteador(unittest.TestCase):
    def test_estado_entra_e_nao_muda_a_lista_ainda(self):
        """Fase 4 só passa o estado; despachar por ele é a fase 7."""
        sem = tools_obrigatorias([AGENDAMENTO_PROPRIO])
        for estado in ec.ESTADOS:
            self.assertEqual(tools_obrigatorias([AGENDAMENTO_PROPRIO], estado), sem)
        self.assertEqual(sem[0], "identificar_paciente")


class TestMigracao(unittest.TestCase):
    def test_indice_fica_e_a_coluna_da_janela_sai(self):
        from src.scripts import setup_database as sd
        sql = " ".join(s for s in sd.SQL_STATEMENTS if isinstance(s, str))
        self.assertIn("idx_appointments_estado_comercial", sql)
        self.assertIn("(clinic_id, patient_id, status, appointment_date)", sql)
        self.assertIn("DROP COLUMN IF EXISTS janela_de_retorno_dias", sql)
        self.assertNotIn("ADD COLUMN IF NOT EXISTS janela_de_retorno_dias", sql)
        criacao = next(s for s in sd.SQL_STATEMENTS if "CREATE TABLE IF NOT EXISTS scheduler.clinics" in s)
        self.assertNotIn("janela_de_retorno_dias", criacao, "CREATE TABLE em sincronia com a migration")


if __name__ == "__main__":
    unittest.main()
