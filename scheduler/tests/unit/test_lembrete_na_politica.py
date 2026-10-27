# -*- coding: utf-8 -*-
"""Em LEADS_ONLY o lembrete de sessao abre a conversa para o bot, como a campanha.

Achado no E2E de prod em 27/10/2026: a Essencia e LEADS_ONLY, e um paciente
comum (sem `bot_enabled`, sem campanha) que respondesse ao lembrete ficaria
sem resposta - o lembrete teria aberto uma porta que a politica fechava.
"""
import unittest
from datetime import date, datetime, time

import pytz

from src.services import atendimento, lembrete

TZ = pytz.timezone("America/Sao_Paulo")
LEADS_ONLY = {"bot_autoreply_policy": "LEADS_ONLY", "bot_paused": False, "timezone": "America/Sao_Paulo"}
APPT = {"id": "a1", "appointment_date": date(2026, 11, 6), "start_time": time(9, 0)}
AGORA = int(TZ.localize(datetime(2026, 11, 5, 12, 0)).timestamp())


class TestLembreteNaPolitica(unittest.TestCase):
    def test_paciente_comum_sem_lembrete_nao_e_atendido(self):
        self.assertFalse(atendimento.pode_responder(LEADS_ONLY, {}, "5511999990000", AGORA))

    def test_com_lembrete_vivo_e_atendido(self):
        sessao = {"lembrete": lembrete.abre(APPT, LEADS_ONLY, AGORA)}
        self.assertTrue(atendimento.pode_responder(LEADS_ONLY, sessao, "5511999990000", AGORA))

    def test_lembrete_vencido_fecha_a_porta_de_novo(self):
        l = lembrete.abre(APPT, LEADS_ONLY, AGORA)
        self.assertFalse(atendimento.pode_responder(LEADS_ONLY, {"lembrete": l}, "5511999990000", l["expira_em"] + 1))

    def test_bot_pausado_vence_o_lembrete(self):
        sessao = {"lembrete": lembrete.abre(APPT, LEADS_ONLY, AGORA)}
        self.assertFalse(atendimento.pode_responder(dict(LEADS_ONLY, bot_paused=True), sessao, "5511999990000", AGORA))


if __name__ == "__main__":
    unittest.main()
