# -*- coding: utf-8 -*-
"""Os dois fluxos convivem sem se atropelar - nos DOIS sentidos.

Pedido explícito do André em 09/09/2026: garantir que o fluxo de campanha não
quebre o de leads, e que o de leads não atrapalhe o de campanha.

O risco não é teórico. Os dois passam pela mesma política LEADS_ONLY, pela mesma
sessão do DynamoDB e pelo mesmo `should_bot_reply`. E o modo de falha é mudo: o
bot simplesmente não responde, ou responde quem não devia, com a suíte verde.
"""
import time
import unittest

from src.services.bot_policy import (
    CAMPO_DE_PAUSA,
    PAUSA_ATENDENTE,
    PAUSA_CONTATO_MANUAL,
    POLICY_ALL,
    POLICY_LEADS_ONLY,
    POLICY_OFF,
    POLICY_PILOT,
    should_bot_reply,
)
from src.services.campanha import abre

# Ancorado no relogio real: `should_bot_reply` nao aceita injecao de tempo, e
# uma constante fixa envelhece - a campanha "viva" do teste vencia sozinha com
# o passar dos meses e o teste passava a medir outra coisa.
AGORA = int(time.time())
FONE = "5511970522647"
DATAS = ["2026-10-07", "2026-10-14", "2026-10-21"]
LEADS_ONLY = {"bot_autoreply_policy": POLICY_LEADS_ONLY}


def com_campanha(**extra):
    return {"campanha": abre(DATAS, agora=AGORA), **extra}


def campanha_vencida(**extra):
    c = abre(DATAS, agora=AGORA - 8 * 86400)
    return {"campanha": c, **extra}


class TestCampanhaResponde(unittest.TestCase):
    def test_campanha_viva_responde_sob_leads_only(self):
        """O fluxo inteiro depende desta linha. Sem ela, nada responde."""
        self.assertTrue(should_bot_reply(LEADS_ONLY, com_campanha(), FONE))

    def test_campanha_vencida_volta_a_calar(self):
        """A trava LEADS_ONLY tem de voltar sozinha quando o prazo acaba."""
        self.assertFalse(should_bot_reply(LEADS_ONLY, campanha_vencida(), FONE))


class TestCampanhaNaoAtropelaOLead(unittest.TestCase):
    """Sentido 1: a campanha não pode afrouxar nada que já existia."""

    def test_sessao_sem_campanha_segue_como_antes(self):
        self.assertFalse(should_bot_reply(LEADS_ONLY, {}, FONE))
        self.assertTrue(should_bot_reply(LEADS_ONLY, {"bot_enabled": True}, FONE))

    def test_campanha_nao_despausa_atendente(self):
        """Se a atendente está na conversa, o bot não fala por cima dela.

        Disparar campanha para quem está sendo atendida no momento não pode
        colocar o bot na frente da pessoa. Só o 'Retomar bot' libera.
        """
        s = com_campanha(**{CAMPO_DE_PAUSA: PAUSA_ATENDENTE,
                            "attendant_active_until": AGORA + 3600})
        self.assertFalse(should_bot_reply(LEADS_ONLY, s, FONE))

    def test_campanha_nao_vence_pausa_permanente(self):
        """'Já iniciada' no painel continua mandando."""
        s = com_campanha(**{CAMPO_DE_PAUSA: PAUSA_CONTATO_MANUAL})
        self.assertFalse(should_bot_reply(LEADS_ONLY, s, FONE))

    def test_campanha_nao_fura_o_off(self):
        s = com_campanha()
        self.assertFalse(should_bot_reply({"bot_autoreply_policy": POLICY_OFF}, s, FONE))

    def test_campanha_nao_fura_o_piloto(self):
        """Em PILOT, só os números do piloto - campanha não é passe livre."""
        clinic = {"bot_autoreply_policy": POLICY_PILOT, "bot_pilot_phones": ["5511999998888"]}
        self.assertFalse(should_bot_reply(clinic, com_campanha(), FONE))

    def test_campanha_nao_fura_bot_pausado_da_clinica(self):
        """`bot_paused` é conferido no webhook, antes desta função - aqui só
        se garante que a campanha não inventa um caminho paralelo."""
        self.assertFalse(should_bot_reply({"bot_autoreply_policy": POLICY_OFF},
                                          com_campanha(), FONE))


class TestLeadNaoAtrapalhaACampanha(unittest.TestCase):
    """Sentido 2: o que já existia não pode calar a campanha."""

    def test_campanha_responde_mesmo_sem_bot_enabled(self):
        """Paciente cadastrada não é lead da landing page e nunca terá a marca."""
        s = com_campanha()
        self.assertNotIn("bot_enabled", s)
        self.assertTrue(should_bot_reply(LEADS_ONLY, s, FONE))

    def test_campanha_convive_com_bot_enabled(self):
        """Quem foi lead um dia e virou paciente responde pelos dois caminhos."""
        self.assertTrue(should_bot_reply(LEADS_ONLY, com_campanha(bot_enabled=True), FONE))

    def test_bot_enabled_sobrevive_a_campanha_vencida(self):
        """Campanha vencida não pode apagar o direito que o lead já tinha."""
        self.assertTrue(should_bot_reply(LEADS_ONLY, campanha_vencida(bot_enabled=True), FONE))

    def test_politica_all_ignora_tudo_isso(self):
        for s in ({}, com_campanha(), campanha_vencida()):
            with self.subTest(s=s):
                self.assertTrue(should_bot_reply({"bot_autoreply_policy": POLICY_ALL}, s, FONE))


if __name__ == "__main__":
    unittest.main()
