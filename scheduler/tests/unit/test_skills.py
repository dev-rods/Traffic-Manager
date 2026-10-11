# -*- coding: utf-8 -*-
"""Fase 7: skills por estado comercial, e o Router despachando (PRD 020 §6).

O que a skill muda fica em código: as tools que o modelo enxerga (lead nova e
paciente sem horário não têm remarcar/cancelar) e o bloco de conduta. Por
estado, não por intenção: o prefixo cacheado não pode mudar a cada mensagem.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import estado_comercial as ec
from src.services import roteador, skills
from src.services.ai_tools import get_tool_definitions
from tests.unit.dublagem_agente import CLINIC, AnthropicRoteiro, mensagem, monta_agente, texto_do_modelo


def paciente(sessoes=0, futuro=None, encontrado=True):
    return {"encontrado": encontrado, "patient_id": "p1", "nome": "Camila", "cadastro_completo": True,
            "sessoes_feitas": sessoes, "ultima_sessao": "2026-09-24" if sessoes else None,
            "agendamento_futuro": futuro}


class TestDespacho(unittest.TestCase):

    def test_todo_estado_tem_skill_e_so_uma(self):
        for estado in ec.ESTADOS:
            with self.subTest(estado=estado):
                donas = [s for s in skills.SKILLS if estado in s.estados]
                self.assertEqual(len(donas), 1)
                self.assertIs(skills.despacha(estado), donas[0])

    def test_tabela(self):
        self.assertEqual(skills.despacha(ec.NEW_LEAD).nome, "primeiro_agendamento")
        self.assertEqual(skills.despacha(ec.FIRST_BOOKING).nome, "paciente_com_horario")
        self.assertEqual(skills.despacha(ec.ACTIVE_CUSTOMER).nome, "paciente_com_horario")
        self.assertEqual(skills.despacha(ec.NO_NEXT_BOOKING).nome, "paciente_sem_horario")

    def test_estado_desconhecido_cai_na_mais_restrita(self):
        self.assertEqual(skills.despacha(None).nome, "primeiro_agendamento")
        self.assertEqual(skills.despacha("x").nome, "primeiro_agendamento")

    def test_roteador_aponta_para_a_mesma_decisao(self):
        for estado in ec.ESTADOS:
            self.assertIs(roteador.despacha(estado), skills.despacha(estado))


class TestTools(unittest.TestCase):

    def _nomes(self, skill):
        return {t["name"] for t in skill.filtra(get_tool_definitions(format="anthropic"))}

    def test_lead_nova_nao_tem_remarcar_nem_cancelar(self):
        nomes = self._nomes(skills.PRIMEIRO_AGENDAMENTO)
        self.assertNotIn("reschedule_appointment", nomes)
        self.assertNotIn("cancel_appointment", nomes)
        self.assertIn("book_appointment", nomes)
        self.assertIn("lookup_appointments", nomes)

    def test_paciente_sem_horario_nao_tem_remarcar_nem_cancelar(self):
        nomes = self._nomes(skills.PACIENTE_SEM_HORARIO)
        self.assertNotIn("reschedule_appointment", nomes)
        self.assertNotIn("cancel_appointment", nomes)
        self.assertIn("book_appointment", nomes)

    def test_paciente_com_horario_tem_tudo(self):
        todas = {t["name"] for t in get_tool_definitions(format="anthropic")}
        self.assertEqual(self._nomes(skills.PACIENTE_COM_HORARIO), todas)

    def test_filtra_tambem_no_formato_openai(self):
        nomes = {t["function"]["name"] for t in skills.PRIMEIRO_AGENDAMENTO.filtra(get_tool_definitions(format="openai"))}
        self.assertNotIn("cancel_appointment", nomes)
        self.assertIn("book_appointment", nomes)

    def test_as_tools_do_dia_a_dia_nunca_sao_vetadas(self):
        for skill in skills.SKILLS:
            for nome in ("identificar_paciente", "list_areas", "check_availability", "get_time_slots",
                         "calculate_discount", "book_appointment", "request_human_handoff",
                         "pedir_esclarecimento", "sem_consulta_necessaria"):
                with self.subTest(skill=skill.nome, tool=nome):
                    self.assertTrue(skill.permite(nome))


class TestBlocos(unittest.TestCase):

    def test_toda_skill_confirma_areas_e_tem_cabecalho(self):
        for skill in skills.SKILLS:
            with self.subTest(skill=skill.nome):
                self.assertIn("QUEM VOCÊ ESTÁ ATENDENDO", skill.bloco)
                self.assertIn("confirme as áreas", skill.bloco)

    def test_quem_ja_e_paciente_nao_ouve_apresentacao_nem_valor(self):
        for skill in (skills.PACIENTE_COM_HORARIO, skills.PACIENTE_SEM_HORARIO):
            self.assertIn("Não se apresente", skill.bloco)
            self.assertIn("Não repita o valor", skill.bloco)

    def test_lead_nova_ouve_o_valor_e_passa_cadastro_so_ao_agendar(self):
        b = skills.PRIMEIRO_AGENDAMENTO.bloco
        self.assertIn("valor da sessão é informado ao confirmar", b)
        self.assertIn("só na hora de agendar", b)
        self.assertNotIn("Não repita o valor", b)


class TestNoAgente(unittest.TestCase):

    def _roda(self, pac, sessao=None):
        anthropic = AnthropicRoteiro([texto_do_modelo("Oi!")])
        vistas = {}
        original = anthropic.create_message

        def create_message(system, messages, tools, max_tokens, tool_choice=None):
            vistas["tools"] = {t["name"] for t in tools}
            vistas["system"] = system
            return original(system, messages, tools, max_tokens, tool_choice)

        anthropic.create_message = create_message
        agente = monta_agente(anthropic=anthropic, paciente=pac)
        if sessao:
            agente.sessao_salva.update(sessao)
        agente.process_message(CLINIC, mensagem("oi"))
        return vistas

    def test_lead_nova_nao_enxerga_remarcar(self):
        v = self._roda({"encontrado": False})
        self.assertNotIn("reschedule_appointment", v["tools"])
        self.assertNotIn("cancel_appointment", v["tools"])
        self.assertIn("ainda não é paciente", v["system"])

    def test_paciente_com_horario_enxerga_remarcar(self):
        v = self._roda(paciente(sessoes=2, futuro={"data": "2026-10-21", "hora": "16:25"}))
        self.assertIn("reschedule_appointment", v["tools"])
        self.assertIn("já tem sessão marcada", v["system"])

    def test_paciente_sem_horario_nao_enxerga_remarcar(self):
        v = self._roda(paciente(sessoes=3))
        self.assertNotIn("reschedule_appointment", v["tools"])
        self.assertIn("não tem a próxima marcada", v["system"])

    def test_campanha_sobrepoe_e_nao_leva_o_bloco_da_skill(self):
        """A campanha tem roteiro próprio (prompt_da_campanha); o bloco da
        skill não entra para não dar duas condutas ao mesmo tempo."""
        import time
        sessao = {"campanha": {"modo": "REAGENDAMENTO", "datas": ["2026-10-21"], "expira_em": int(time.time()) + 3600}}
        v = self._roda(paciente(sessoes=3), sessao=sessao)
        self.assertNotIn("QUEM VOCÊ ESTÁ ATENDENDO", v["system"])
        self.assertNotIn("reschedule_appointment", v["tools"], "as tools continuam da skill")


if __name__ == "__main__":
    unittest.main()
