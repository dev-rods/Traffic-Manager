# -*- coding: utf-8 -*-
"""Quem atende a conversa, e as duas perguntas que saem disso.

PRD 020 §3.2 a §3.5. O que estes testes fixam, em ordem:

  1. estado()           derivado dos instantes, sem cron
  2. pode_responder     reativo: cooldown e horário NÃO entram
  3. pode_iniciar       proativo: cooldown, janela de silêncio, transacional
  4. transições         só a clínica renova; cliente não; painel limpa tudo
  5. legado             sessão antiga migra na leitura e a projeção é escrita
"""
import os
import unittest
from datetime import datetime, timezone

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at

SP = pytz.timezone("America/Sao_Paulo")
CLINICA = {"clinic_id": "essencia", "timezone": "America/Sao_Paulo", "bot_autoreply_policy": "ALL"}
PHONE = "5511999990000"
H = 3600


def meio_dia(dia=6):
    """Um instante fora da janela de silêncio: 12:00 em Brasília."""
    return int(SP.localize(datetime(2026, 10, dia, 12, 0)).timestamp())


def madrugada(dia=7):
    """01:00 em Brasília: dentro da janela de silêncio."""
    return int(SP.localize(datetime(2026, 10, dia, 1, 0)).timestamp())


T0 = meio_dia()


class TestEstadoDerivado(unittest.TestCase):
    def test_sessao_vazia_e_bot(self):
        self.assertEqual(at.estado({}, T0), at.BOT_ACTIVE)
        self.assertEqual(at.estado(None, T0), at.BOT_ACTIVE)

    def test_entregue_e_human_active_ate_vencer(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertEqual(at.estado(s, T0), at.HUMAN_ACTIVE)
        self.assertEqual(at.estado(s, T0 + 24 * H - 1), at.HUMAN_ACTIVE)

    def test_vencido_vira_cooldown_e_depois_bot(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertEqual(at.estado(s, T0 + 24 * H), at.COOLDOWN)
        self.assertEqual(at.estado(s, T0 + 48 * H - 1), at.COOLDOWN)
        self.assertEqual(at.estado(s, T0 + 48 * H), at.BOT_ACTIVE)

    def test_pausa_de_origem_vence_como_qualquer_outra(self):
        """Decisão 9.1 (André, 05/10/2026): CONTATO_MANUAL e CHAT_ANTERIOR
        vencem pelo TTL. Quem chama passa `ate` contado da última mensagem
        conhecida; sem `ate`, conta de agora."""
        for por in (at.POR_CONTATO_MANUAL, at.POR_CHAT_ANTERIOR):
            with self.subTest(por=por):
                s = at.entrega_a_humano({}, por=por, agora=T0)
                self.assertEqual(s[at.CAMPO]["human_until"], T0 + 24 * H)
                self.assertEqual(at.estado(s, T0 + H), at.HUMAN_ACTIVE)
                self.assertEqual(at.estado(s, T0 + 25 * H), at.COOLDOWN)

    def test_chat_anterior_de_meses_atras_vence_na_hora(self):
        """O prazo conta da última mensagem do espelho: conversa velha não
        segura o bot nem um minuto."""
        s = at.entrega_a_humano({}, por=at.POR_CHAT_ANTERIOR, agora=T0, ate=T0 - 60 * 24 * H)
        self.assertEqual(at.estado(s, T0), at.BOT_ACTIVE)

    def test_vencido_com_pendencia_fica_com_pessoa(self):
        """Handoff com intenção em aberto não volta ao bot quando o TTL vence:
        vira HUMAN_PENDING até alguém fechar a tarefa (PRD 020 §3.6)."""
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="faq_sem_resposta", agora=T0,
                                pending_intent="faq_sem_resposta")
        self.assertEqual(at.estado(s, T0 + 25 * H), at.HUMAN_PENDING)
        self.assertEqual(at.estado(s, T0 + 365 * 24 * H), at.HUMAN_PENDING)
        self.assertFalse(at.pode_responder(CLINICA, s, PHONE, T0 + 48 * H))

    def test_avalia_vencimento_com_e_sem_pendencia(self):
        com = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="x", agora=T0, pending_intent="x")
        com, acao = at.avalia_vencimento(com, T0 + 25 * H)
        self.assertEqual(acao, at.ACAO_PENDENTE)
        self.assertEqual(com[at.CAMPO]["handler"], at.HUMAN_PENDING)
        sem = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        sem, acao = at.avalia_vencimento(sem, T0 + 25 * H)
        self.assertEqual(acao, at.ACAO_AVALIAR_RETOMADA)

    def test_fechar_a_tarefa_devolve_ao_cooldown(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="x", agora=T0, pending_intent="x")
        at.vincula_tarefa(s, "t1")
        self.assertEqual(s[at.CAMPO]["pending_task_id"], "t1")
        at.avalia_vencimento(s, T0 + 25 * H)
        at.fecha_pendencia(s, agora=T0 + 30 * H)
        self.assertEqual(at.estado(s, T0 + 30 * H), at.COOLDOWN)
        self.assertIsNone(s[at.CAMPO]["pending_intent"])
        self.assertTrue(at.pode_responder(CLINICA, s, PHONE, T0 + 31 * H))
        self.assertFalse(at.pode_iniciar(CLINICA, s, PHONE, T0 + 31 * H))

    def test_retomar_pelo_painel_limpa_a_pendencia(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="x", agora=T0, pending_intent="x")
        at.retoma_pelo_painel(s)
        self.assertEqual(at.estado(s, T0 + 48 * H), at.BOT_ACTIVE)
        self.assertIsNone(s[at.CAMPO]["pending_intent"])

    def test_marca_retomada_e_alerta(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        at.marca_retomada(s, T0 + 25 * H)
        at.marca_alerta(s, "fecho_social")
        self.assertEqual(s[at.CAMPO]["retomada_em"], T0 + 25 * H)
        self.assertEqual(s[at.CAMPO]["alerta"], "fecho_social")
        at.encerra_atendimento_humano(s, T0 + 25 * H)
        self.assertEqual(s[at.CAMPO]["alerta"], "fecho_social", "o alerta sobrevive ao cooldown")

    def test_contexto_de_retomada_vai_e_volta(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        at.poe_contexto_de_retomada(s, "═══ RETOMADA ═══ ...")
        self.assertTrue(s[at.CAMPO]["retomada_contexto"])
        at.limpa_contexto_de_retomada(s)
        self.assertIsNone(s[at.CAMPO]["retomada_contexto"])

    def test_cooldown_explicito_vence(self):
        s = at.encerra_atendimento_humano({}, agora=T0)
        self.assertEqual(at.estado(s, T0), at.COOLDOWN)
        self.assertEqual(at.estado(s, T0 + 24 * H), at.BOT_ACTIVE)

    def test_pending_nao_vence_sozinho(self):
        s = {at.CAMPO: {"handler": at.HUMAN_PENDING, "versao": 1}}
        self.assertEqual(at.estado(s, T0 + 365 * 24 * H), at.HUMAN_PENDING)


class TestPodeResponder(unittest.TestCase):
    def test_bot_ativo_responde(self):
        self.assertTrue(at.pode_responder(CLINICA, {}, PHONE, T0))

    def test_com_pessoa_nao_responde(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertFalse(at.pode_responder(CLINICA, s, PHONE, T0 + H))

    def test_em_cooldown_RESPONDE(self):
        """É a distinção que não existia: responder sim, iniciar não."""
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertTrue(at.pode_responder(CLINICA, s, PHONE, T0 + 25 * H))

    def test_de_madrugada_RESPONDE(self):
        """Decisão do André (05/10/2026): quem escreve de madrugada é
        respondido na hora - é quando o lead está mais quente."""
        self.assertTrue(at.pode_responder(CLINICA, {}, PHONE, madrugada()))

    def test_clinica_com_bot_pausado_nao_responde(self):
        self.assertFalse(at.pode_responder({**CLINICA, "bot_paused": True}, {}, PHONE, T0))

    def test_politicas(self):
        piloto = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PHONE]}
        self.assertTrue(at.pode_responder(piloto, {}, PHONE, T0))
        self.assertFalse(at.pode_responder(piloto, {}, "5511988887777", T0))
        leads = {"bot_autoreply_policy": "LEADS_ONLY"}
        self.assertFalse(at.pode_responder(leads, {}, PHONE, T0))
        self.assertTrue(at.pode_responder(leads, {"bot_enabled": True}, PHONE, T0))
        self.assertFalse(at.pode_responder({"bot_autoreply_policy": "OFF"}, {}, PHONE, T0))
        self.assertTrue(at.pode_responder({}, {}, PHONE, T0), "política ausente é ALL")


class TestPodeIniciar(unittest.TestCase):
    def test_bot_ativo_de_dia_inicia(self):
        self.assertTrue(at.pode_iniciar(CLINICA, {}, PHONE, T0))

    def test_em_cooldown_nao_inicia(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertFalse(at.pode_iniciar(CLINICA, s, PHONE, T0 + 25 * H))

    def test_passado_o_cooldown_inicia(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertTrue(at.pode_iniciar(CLINICA, s, PHONE, T0 + 49 * H))

    def test_de_madrugada_nao_inicia(self):
        self.assertFalse(at.pode_iniciar(CLINICA, {}, PHONE, madrugada()))

    def test_limites_da_janela(self):
        casos = [((22, 58, 59), True), ((22, 59, 0), False), ((4, 58, 59), False), ((4, 59, 0), True)]
        for (h, m, s), esperado in casos:
            agora = int(SP.localize(datetime(2026, 10, 7, h, m, s)).timestamp())
            with self.subTest(hora=f"{h:02}:{m:02}:{s:02}"):
                self.assertEqual(at.pode_iniciar(CLINICA, {}, PHONE, agora), esperado)

    def test_transacional_passa_pelo_cooldown_mas_nao_pela_janela(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertTrue(at.pode_iniciar(CLINICA, s, PHONE, T0 + 25 * H, transacional=True))
        self.assertFalse(at.pode_iniciar(CLINICA, {}, PHONE, madrugada(), transacional=True))

    def test_transacional_nao_passa_por_pessoa_nem_por_bot_pausado(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertFalse(at.pode_iniciar(CLINICA, s, PHONE, T0 + H, transacional=True))
        self.assertFalse(at.pode_iniciar({**CLINICA, "bot_paused": True}, {}, PHONE, T0, transacional=True))

    def test_tudo_que_barra_responder_barra_iniciar(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="x", agora=T0)
        self.assertFalse(at.pode_iniciar(CLINICA, s, PHONE, T0 + H))
        self.assertFalse(at.pode_iniciar({"bot_autoreply_policy": "OFF"}, {}, PHONE, T0))


class TestTransicoes(unittest.TestCase):
    def test_so_a_clinica_renova(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        at.registra_fala_do_cliente(s, agora=T0 + 20 * H)
        self.assertEqual(s[at.CAMPO]["human_until"], T0 + 24 * H, "cliente NÃO renova")
        at.renova_por_mensagem_da_clinica(s, agora=T0 + 20 * H)
        self.assertEqual(s[at.CAMPO]["human_until"], T0 + 44 * H)

    def test_cliente_insistente_chega_ao_cooldown(self):
        """Se o cliente renovasse, quem está sem resposta nunca sairia do
        lock humano - o inverso do que o TTL quer."""
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        for h in range(1, 24):
            at.registra_fala_do_cliente(s, agora=T0 + h * H)
        self.assertEqual(at.estado(s, T0 + 24 * H + 1), at.COOLDOWN)

    def test_a_fala_do_cliente_fica_registrada(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        at.registra_fala_do_cliente(s, agora=T0 + 5 * H)
        self.assertEqual(s[at.CAMPO]["ultima_fala_cliente_em"], T0 + 5 * H)

    def test_cliente_escreve_em_cooldown_e_a_conversa_volta_ao_bot(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        at.registra_fala_do_cliente(s, agora=T0 + 30 * H)
        self.assertEqual(s[at.CAMPO]["handler"], at.BOT_ACTIVE)
        self.assertTrue(at.pode_iniciar(CLINICA, s, PHONE, T0 + 30 * H))

    def test_mensagem_da_clinica_em_bot_ativo_entrega(self):
        s = at.renova_por_mensagem_da_clinica({}, agora=T0)
        self.assertEqual(at.estado(s, T0), at.HUMAN_ACTIVE)
        self.assertEqual(s[at.CAMPO]["pausado_por"], at.POR_ATENDENTE)

    def test_renovar_pausa_de_origem_renova_o_prazo(self):
        s = at.entrega_a_humano({}, por=at.POR_CHAT_ANTERIOR, agora=T0)
        at.renova_por_mensagem_da_clinica(s, agora=T0 + H)
        self.assertEqual(s[at.CAMPO]["human_until"], T0 + 25 * H)

    def test_retomar_pelo_painel_limpa_tudo_sem_cooldown(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="pedido_da_paciente", agora=T0)
        at.retoma_pelo_painel(s)
        self.assertEqual(at.estado(s, T0), at.BOT_ACTIVE)
        self.assertTrue(at.pode_iniciar(CLINICA, s, PHONE, T0))
        self.assertIsNone(s[at.CAMPO]["handoff_reason"])

    def test_handoff_guarda_motivo_e_quem_entregou(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="faq_sem_resposta", agora=T0)
        b = s[at.CAMPO]
        self.assertEqual(b["pausado_por"], at.POR_HANDOFF)
        self.assertEqual(b["handoff_reason"], "faq_sem_resposta")
        self.assertEqual(b["entregue_em"], T0)
        self.assertTrue(at.aguarda_especialista(s, T0))

    def test_atendente_nao_e_aguardando_especialista(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertTrue(at.esta_com_pessoa(s, T0))
        self.assertFalse(at.aguarda_especialista(s, T0))

    def test_entregar_de_novo_renova_e_mantem_o_motivo_original(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="primeiro", agora=T0)
        at.entrega_a_humano(s, por=at.POR_HANDOFF, agora=T0 + H)
        self.assertEqual(s[at.CAMPO]["handoff_reason"], "primeiro")
        self.assertEqual(s[at.CAMPO]["human_until"], T0 + 25 * H)

    def test_transicao_nao_mexe_na_versao(self):
        """A versão conta escritas no banco, não transições. Subir por
        transição quebrava cadeias (alerta + encerra): a escrita condicional
        esperava uma versão que o banco nunca teve."""
        s = {at.CAMPO: {"handler": at.BOT_ACTIVE, "versao": 7}}
        at.entrega_a_humano(s, por=at.POR_ATENDENTE, agora=T0)
        at.registra_fala_do_cliente(s, agora=T0 + H)
        at.retoma_pelo_painel(s)
        self.assertEqual(s[at.CAMPO]["versao"], 7)

    def test_pendencia_gravada_no_handoff(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="x", agora=T0, pending_intent="RESCHEDULE")
        self.assertEqual(s[at.CAMPO]["pending_intent"], "RESCHEDULE")
        self.assertEqual(s[at.CAMPO]["pending_since"], T0)


class TestLegado(unittest.TestCase):
    """Sessão gravada antes deste módulo é lida pela mesma regra de antes."""

    def test_attendant_active_until_no_futuro_e_pessoa(self):
        s = {"attendant_active_until": T0 + H, "bot_pausado_por": "HANDOFF", "handoff_reason": "x"}
        self.assertEqual(at.estado(s, T0), at.HUMAN_ACTIVE)
        self.assertTrue(at.aguarda_especialista(s, T0))

    def test_attendant_active_until_vencido_e_cooldown(self):
        """Antes voltava direto ao bot; agora passa 24h sem iniciar nada."""
        s = {"attendant_active_until": T0 - H, "bot_pausado_por": "ATENDENTE"}
        self.assertEqual(at.estado(s, T0), at.COOLDOWN)
        self.assertTrue(at.pode_responder(CLINICA, s, PHONE, T0))
        self.assertFalse(at.pode_iniciar(CLINICA, s, PHONE, T0))

    def test_pausas_de_origem_antigas_sem_prazo_ja_venceram(self):
        """Decisão 9.1: sessão legada sem data é tratada como vencida há muito.
        O bot responde se a pessoa escrever; a retomada não a alcança."""
        for por in ("CONTATO_MANUAL", "CHAT_ANTERIOR"):
            with self.subTest(por=por):
                s = {"bot_pausado_por": por}
                self.assertEqual(at.estado(s, T0), at.BOT_ACTIVE)
                self.assertTrue(at.pode_responder(CLINICA, s, PHONE, T0))

    def test_pausa_de_origem_antiga_com_prazo_futuro_segura(self):
        s = {"bot_pausado_por": "CONTATO_MANUAL", "attendant_active_until": T0 + H}
        self.assertEqual(at.estado(s, T0), at.HUMAN_ACTIVE)

    def test_sem_nada_e_bot(self):
        self.assertEqual(at.estado({"state": "SELECT_TIME", "agent_history": []}, T0), at.BOT_ACTIVE)

    def test_prazo_ilegivel_nao_pausa(self):
        self.assertEqual(at.estado({"attendant_active_until": "ontem"}, T0), at.BOT_ACTIVE)

    def test_bloco_novo_vence_o_legado(self):
        """Quando o bloco existe, os campos antigos são projeção, não fonte."""
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        s["attendant_active_until"] = T0 + 999 * H  # alguém mexeu no campo antigo
        self.assertEqual(at.estado(s, T0 + 25 * H), at.COOLDOWN)


class TestProjecaoNoLegado(unittest.TestCase):
    """O painel ainda lê os campos antigos. Só este módulo os escreve."""

    def test_entrega_escreve_os_campos_que_o_painel_le(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="pedido_da_paciente", agora=T0)
        self.assertEqual(s["state"], "HUMAN_HANDOFF")
        self.assertEqual(s["bot_pausado_por"], "HANDOFF")
        self.assertEqual(s["attendant_active_until"], T0 + 24 * H)
        self.assertEqual(s["handoff_reason"], "pedido_da_paciente")
        self.assertEqual(s["human_handoff_requested_at"], T0)

    def test_atendente_e_attendant_active(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=T0)
        self.assertEqual(s["state"], "HUMAN_ATTENDANT_ACTIVE")

    def test_pausa_de_origem_tem_prazo_projetado(self):
        s = at.entrega_a_humano({}, por=at.POR_CHAT_ANTERIOR, agora=T0)
        self.assertEqual(s["attendant_active_until"], T0 + 24 * H)
        self.assertEqual(s["bot_pausado_por"], "CHAT_ANTERIOR")

    def test_retomar_limpa_a_projecao(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="x", agora=T0)
        at.retoma_pelo_painel(s)
        for campo in ("attendant_active_until", "bot_pausado_por", "handoff_reason", "human_handoff_requested_at"):
            self.assertNotIn(campo, s)
        self.assertEqual(s["state"], "")

    def test_retomar_nao_apaga_state_de_fluxo(self):
        s = {"state": "SELECT_TIME"}
        at.retoma_pelo_painel(s)
        self.assertEqual(s["state"], "SELECT_TIME")


if __name__ == "__main__":
    unittest.main()
