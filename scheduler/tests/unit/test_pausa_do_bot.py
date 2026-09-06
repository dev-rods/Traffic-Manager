# -*- coding: utf-8 -*-
"""Quando o bot cala, e o que faz ele voltar.

Duas naturezas de pausa, decididas com o André em 06/09/2026:

  ATENDIMENTO EM CURSO (atendente respondeu, bot pediu ajuda) vence em 24h.
  Alguém está na conversa AGORA, e isso deixa de ser verdade. Sem prazo, toda
  conversa atendida uma vez ficaria morta e ninguém lembraria de reabrir.

  DE QUEM É A CONVERSA ("Já iniciada" no painel, chat que já existia antes de
  nós) não vence. Quem começou a conversa não deixa de ter começado amanhã, e
  soltar o bot ali no dia seguinte é o dano que o botão existe para impedir.

Nos dois casos o "Retomar bot" libera na hora.
"""
import time
import unittest

from src.services.bot_policy import (
    CAMPO_DE_PAUSA,
    PAUSA_ATENDENTE,
    PAUSA_CHAT_ANTERIOR,
    PAUSA_CONTATO_MANUAL,
    PAUSA_HANDOFF,
    esta_pausado,
    should_bot_reply,
)

CLINICA_ABERTA = {"bot_autoreply_policy": "ALL"}
CLINICA_LEADS = {"bot_autoreply_policy": "LEADS_ONLY"}
FUTURO = int(time.time()) + 3600
PASSADO = int(time.time()) - 3600


class TestAtendimentoEmCursoVence(unittest.TestCase):
    """Alguém está na conversa agora - e depois de 24h, provavelmente não está."""

    def test_dentro_das_24h_o_bot_cala(self):
        pausada = {CAMPO_DE_PAUSA: PAUSA_ATENDENTE, "attendant_active_until": FUTURO}

        self.assertTrue(esta_pausado(pausada))
        self.assertFalse(should_bot_reply(CLINICA_ABERTA, pausada, "5511999990000"))

    def test_passadas_as_24h_o_bot_volta(self):
        pausada = {CAMPO_DE_PAUSA: PAUSA_ATENDENTE, "attendant_active_until": PASSADO}

        self.assertFalse(esta_pausado(pausada))
        self.assertTrue(should_bot_reply(CLINICA_ABERTA, pausada, "5511999990000"))

    def test_handoff_do_bot_tambem_vence(self):
        """O bot pediu ajuda e ninguém veio: melhor ele voltar do que a pessoa
        ficar falando sozinha para sempre."""
        self.assertFalse(esta_pausado({CAMPO_DE_PAUSA: PAUSA_HANDOFF,
                                       "attendant_active_until": PASSADO}))

    def test_sem_pausa_o_bot_fala(self):
        self.assertFalse(esta_pausado({}))
        self.assertFalse(esta_pausado(None))
        self.assertTrue(should_bot_reply(CLINICA_ABERTA, {}, "5511999990000"))


class TestDeQuemEAConversaNaoVence(unittest.TestCase):
    """Quem começou não deixa de ter começado amanhã."""

    def test_ja_iniciada_no_painel_nao_vence(self):
        """Se vencesse, o bot entraria no dia seguinte numa conversa que uma
        pessoa conduz - o dano exato que o botão existe para impedir."""
        marcada = {CAMPO_DE_PAUSA: PAUSA_CONTATO_MANUAL,
                   "attendant_active_until": PASSADO, "bot_enabled": True}

        self.assertTrue(esta_pausado(marcada))
        self.assertFalse(should_bot_reply(CLINICA_LEADS, marcada, "5511999990000"))

    def test_chat_anterior_nao_vence(self):
        self.assertTrue(esta_pausado({CAMPO_DE_PAUSA: PAUSA_CHAT_ANTERIOR}))

    def test_sem_prazo_nenhum_continuam_pausadas(self):
        for motivo in (PAUSA_CONTATO_MANUAL, PAUSA_CHAT_ANTERIOR):
            with self.subTest(motivo=motivo):
                self.assertTrue(esta_pausado({CAMPO_DE_PAUSA: motivo}))


class TestCompatibilidade(unittest.TestCase):
    def test_pausas_antigas_continuam_valendo(self):
        """Sessões que já estavam pausadas quando isto subiu só têm o prazo.
        Ignorá-lo soltaria o bot em conversas humanas no instante do deploy."""
        antiga = {"attendant_active_until": FUTURO}

        self.assertTrue(esta_pausado(antiga))
        self.assertFalse(should_bot_reply(CLINICA_ABERTA, antiga, "5511999990000"))

    def test_prazo_antigo_vencido_nao_pausa(self):
        """Sem o campo novo, o prazo vencido é o que sempre foi: liberado."""
        self.assertFalse(esta_pausado({"attendant_active_until": PASSADO}))


class TestPausaVenceQualquerPolitica(unittest.TestCase):
    def test_em_toda_politica(self):
        pausada = {CAMPO_DE_PAUSA: PAUSA_ATENDENTE,
                   "attendant_active_until": FUTURO, "bot_enabled": True}
        for clinic in (CLINICA_ABERTA, CLINICA_LEADS,
                       {"bot_autoreply_policy": "PILOT",
                        "bot_pilot_phones": ["5511999990000"]}):
            with self.subTest(policy=clinic["bot_autoreply_policy"]):
                self.assertFalse(should_bot_reply(clinic, pausada, "5511999990000"))


class TestLeadsOnly(unittest.TestCase):
    """A política que o André quer ligar depois."""

    def test_lead_marcado_responde(self):
        self.assertTrue(
            should_bot_reply(CLINICA_LEADS, {"bot_enabled": True}, "5511999990000"))

    def test_quem_nao_e_lead_nao_recebe_resposta(self):
        self.assertFalse(should_bot_reply(CLINICA_LEADS, {}, "5511999990000"))

    def test_lead_com_conversa_humana_nao_recebe_resposta(self):
        """O caso que motivou tudo: o botão "Já iniciada" precisa governar, não
        só registrar. Sem isso o bot respondia por cima da atendente."""
        self.assertFalse(should_bot_reply(
            CLINICA_LEADS,
            {"bot_enabled": True, CAMPO_DE_PAUSA: PAUSA_CONTATO_MANUAL},
            "5511999990000"))


if __name__ == "__main__":
    unittest.main()
