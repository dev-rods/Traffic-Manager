# -*- coding: utf-8 -*-
"""Por que o bot está calado, em palavras: a função única do painel (PRD 031).

Era calculado inline em três handlers. Aqui o contrato: os três motivos, a
ordem entre eles, e a coerência com `pode_responder` - quando um diz que
responde, o outro não pode apontar motivo.
"""
import itertools
import unittest

from src.services import atendimento as at

AGORA = 1_800_000_000
FONE = "5511999990000"


def com_pessoa():
    return at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 60)


class TestOsMotivos(unittest.TestCase):
    def test_com_pessoa_vence_tudo(self):
        clinica = {"bot_paused": True, "bot_autoreply_policy": "OFF"}
        self.assertEqual(at.motivo_da_pausa(clinica, com_pessoa(), FONE, AGORA), at.PAUSA_ATENDENTE)

    def test_clinica_pausada(self):
        self.assertEqual(at.motivo_da_pausa({"bot_paused": True}, {}, FONE, AGORA), at.PAUSA_CLINICA)

    def test_leads_only_sem_marca_e_fora_da_regra(self):
        clinica = {"bot_autoreply_policy": "LEADS_ONLY"}
        self.assertEqual(at.motivo_da_pausa(clinica, {}, FONE, AGORA), at.PAUSA_FORA_DA_REGRA)
        self.assertEqual(at.motivo_da_pausa(clinica, None, FONE, AGORA), at.PAUSA_FORA_DA_REGRA)

    def test_leads_only_com_marca_responde(self):
        clinica = {"bot_autoreply_policy": "LEADS_ONLY"}
        self.assertIsNone(at.motivo_da_pausa(clinica, {"bot_enabled": True}, FONE, AGORA))

    def test_all_responde_e_off_nao(self):
        self.assertIsNone(at.motivo_da_pausa({"bot_autoreply_policy": "ALL"}, {}, FONE, AGORA))
        self.assertIsNone(at.motivo_da_pausa({}, {}, FONE, AGORA))
        self.assertEqual(at.motivo_da_pausa({"bot_autoreply_policy": "OFF"}, {}, FONE, AGORA),
                         at.PAUSA_FORA_DA_REGRA)

    def test_piloto(self):
        clinica = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [FONE]}
        self.assertIsNone(at.motivo_da_pausa(clinica, {}, FONE, AGORA))
        self.assertEqual(at.motivo_da_pausa(clinica, {}, "5511888880000", AGORA), at.PAUSA_FORA_DA_REGRA)

    def test_os_valores_sao_os_que_o_painel_conhece(self):
        self.assertEqual({at.PAUSA_ATENDENTE, at.PAUSA_CLINICA, at.PAUSA_FORA_DA_REGRA},
                         {"attendant", "clinic_paused", "not_eligible"})


class TestCoerenciaComPodeResponder(unittest.TestCase):
    """Se as duas funções divergirem, o painel mente sobre o que o webhook fará."""

    def test_motivo_ausente_e_poder_responder_sao_a_mesma_coisa(self):
        clinicas = [
            {}, {"bot_paused": True}, {"bot_autoreply_policy": "OFF"},
            {"bot_autoreply_policy": "LEADS_ONLY"},
            {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [FONE]},
            {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": []},
        ]
        sessoes = [{}, {"bot_enabled": True}, com_pessoa(),
                   at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 25 * 3600)]  # cooldown
        for clinica, sessao in itertools.product(clinicas, sessoes):
            with self.subTest(clinica=clinica, sessao=at.estado(sessao, AGORA)):
                self.assertEqual(at.motivo_da_pausa(clinica, sessao, FONE, AGORA) is None,
                                 at.pode_responder(clinica, sessao, FONE, AGORA))


if __name__ == "__main__":
    unittest.main()
