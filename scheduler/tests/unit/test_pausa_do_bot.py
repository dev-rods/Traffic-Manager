# -*- coding: utf-8 -*-
"""Quando o bot cala, e o que faz ele voltar.

A regra combinada em 06/09/2026: humano tocou a conversa, o bot para - e só
volta quando uma pessoa clicar "Retomar bot" no painel. Nunca por tempo.

Antes a pausa era um prazo de 24h. Uma atendente assumia hoje e o bot voltava
amanhã, no meio do atendimento dela, sem ninguém ter pedido. Bot que volta
sozinho é pior que bot desligado: ninguém está esperando por ele.
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


class TestAPausaNaoVence(unittest.TestCase):
    """O coração da mudança."""

    def test_pausa_sem_prazo_continua_valendo(self):
        self.assertTrue(esta_pausado({CAMPO_DE_PAUSA: PAUSA_ATENDENTE}))

    def test_pausa_persiste_mesmo_com_prazo_vencido(self):
        """O prazo de 24h vira só informação de tela. Se ele ainda mandasse, a
        pausa se desfaria sozinha - o defeito que este teste existe para travar."""
        pausada = {CAMPO_DE_PAUSA: PAUSA_ATENDENTE, "attendant_active_until": PASSADO}

        self.assertTrue(esta_pausado(pausada))
        self.assertFalse(should_bot_reply(CLINICA_ABERTA, pausada, "5511999990000"))

    def test_sem_pausa_o_bot_fala(self):
        self.assertFalse(esta_pausado({}))
        self.assertFalse(esta_pausado(None))
        self.assertTrue(should_bot_reply(CLINICA_ABERTA, {}, "5511999990000"))

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
        pausada = {CAMPO_DE_PAUSA: PAUSA_ATENDENTE, "bot_enabled": True}
        for clinic in (CLINICA_ABERTA, CLINICA_LEADS,
                       {"bot_autoreply_policy": "PILOT",
                        "bot_pilot_phones": ["5511999990000"]}):
            with self.subTest(policy=clinic["bot_autoreply_policy"]):
                self.assertFalse(should_bot_reply(clinic, pausada, "5511999990000"))

    def test_todos_os_motivos_pausam(self):
        """O valor é informativo; o que pausa é o campo existir."""
        for motivo in (PAUSA_ATENDENTE, PAUSA_CONTATO_MANUAL,
                       PAUSA_CHAT_ANTERIOR, PAUSA_HANDOFF):
            with self.subTest(motivo=motivo):
                self.assertFalse(
                    should_bot_reply(CLINICA_ABERTA, {CAMPO_DE_PAUSA: motivo}, "5511999990000"))


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
