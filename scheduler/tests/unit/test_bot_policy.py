"""Quem o bot responde automaticamente.

O default tem que continuar respondendo todo mundo: há clínica em produção
dependendo disso (clinicadorods-da7b62, com use_agent=true e bot_paused=false).
Toda restrição é opt-in por clínica.
"""
import os
import time
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.bot_policy import should_bot_reply

PILOTO = "5511970521647"


class TestAll(unittest.TestCase):
    def test_responde_qualquer_um(self):
        self.assertTrue(should_bot_reply({"bot_autoreply_policy": "ALL"}, {}, "5511999999999"))

    def test_coluna_ausente_se_comporta_como_all(self):
        """Clínica lida antes da migration não pode ficar sem bot."""
        self.assertTrue(should_bot_reply({}, {}, "5511999999999"))

    def test_valor_nulo_se_comporta_como_all(self):
        self.assertTrue(should_bot_reply({"bot_autoreply_policy": None}, {}, "5511999999999"))


class TestOff(unittest.TestCase):
    def test_nao_responde_ninguem(self):
        self.assertFalse(should_bot_reply({"bot_autoreply_policy": "OFF"}, {}, PILOTO))


class TestPilot(unittest.TestCase):
    def setUp(self):
        self.clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PILOTO]}

    def test_responde_telefone_do_piloto(self):
        self.assertTrue(should_bot_reply(self.clinic, {}, PILOTO))

    def test_nao_responde_fora_do_piloto(self):
        self.assertFalse(should_bot_reply(self.clinic, {}, "5511988887777"))

    def test_compara_telefone_normalizado(self):
        """O webhook entrega o número em formatos variados."""
        self.assertTrue(should_bot_reply(self.clinic, {}, "+55 (11) 97052-1647"))

    def test_allowlist_tambem_e_normalizada(self):
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": ["(11) 97052-1647"]}

        self.assertTrue(should_bot_reply(clinic, {}, PILOTO))

    def test_piloto_vazio_nao_responde_ninguem(self):
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": []}

        self.assertFalse(should_bot_reply(clinic, {}, PILOTO))

    def test_piloto_nulo_nao_responde_ninguem(self):
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": None}

        self.assertFalse(should_bot_reply(clinic, {}, PILOTO))


class TestLeadsOnly(unittest.TestCase):
    def setUp(self):
        self.clinic = {"bot_autoreply_policy": "LEADS_ONLY"}

    def test_conversa_sem_marca_nao_recebe(self):
        self.assertFalse(should_bot_reply(self.clinic, {}, "5511999999999"))

    def test_conversa_de_lead_recebe(self):
        self.assertTrue(should_bot_reply(self.clinic, {"bot_enabled": True}, "5511999999999"))

    def test_desligado_manualmente_nao_recebe(self):
        self.assertFalse(should_bot_reply(self.clinic, {"bot_enabled": False}, "5511999999999"))


class TestAtendenteHumano(unittest.TestCase):
    """Se alguém da clínica assumiu a conversa, o bot não fala por cima."""

    def test_atendente_ativo_suspende_em_qualquer_politica(self):
        session = {"attendant_active_until": int(time.time()) + 3600, "bot_enabled": True}
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PILOTO]}

        self.assertFalse(should_bot_reply(clinic, session, PILOTO))

    def test_atendente_ativo_suspende_mesmo_com_policy_all(self):
        session = {"attendant_active_until": int(time.time()) + 3600}

        self.assertFalse(should_bot_reply({"bot_autoreply_policy": "ALL"}, session, PILOTO))

    def test_atendente_expirado_nao_bloqueia(self):
        session = {"attendant_active_until": int(time.time()) - 10}
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PILOTO]}

        self.assertTrue(should_bot_reply(clinic, session, PILOTO))


class TestEntradasInvalidas(unittest.TestCase):
    def test_sessao_none(self):
        self.assertTrue(should_bot_reply({"bot_autoreply_policy": "ALL"}, None, PILOTO))

    def test_clinica_none(self):
        """Sem clínica não há política; o default ALL é o comportamento histórico."""
        self.assertTrue(should_bot_reply(None, {}, PILOTO))

    def test_politica_desconhecida_nao_responde(self):
        """Valor fora do CHECK só chegaria por escrita manual: falha fechado."""
        self.assertFalse(should_bot_reply({"bot_autoreply_policy": "XPTO"}, {}, PILOTO))


if __name__ == "__main__":
    unittest.main()
