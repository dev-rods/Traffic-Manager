# -*- coding: utf-8 -*-
"""A trava de cadastro esta ligada no fluxo, nao so implementada.

Retirar o roteiro do prompt reduz a chance de o bot pedir CPF a uma paciente
cadastrada. So a trava garante - e uma trava dessas morre calada de dois jeitos:
a condicao para de ser avaliada, ou o refazer some.
"""
import time
import unittest

from src.services.campanha import abre

CLINIC = "clinicaessenciaestetica-9668a4"
DATAS = ["2026-09-23", "2026-09-24", "2026-09-29"]

PEDIDO = ("Perfeito! Para finalizar o cadastro, me envia:\n"
          "Nome completo:\nData de nascimento:\nCPF:\nE-mail:")
# Sem data nem horario: a proveniencia tambem dispara sobre esta mensagem,
# e o teste mediria as duas travas ao mesmo tempo.
OK = "Otimo! Qual area voce quer tratar desta vez?"


def roda(sessao, respostas):
    """Devolve (texto_enviado, correcoes_recebidas_pelo_modelo)."""
    from tests.unit.dublagem_agente import (
        AnthropicRoteiro, mensagem, monta_agente, texto_do_modelo)

    anthropic = AnthropicRoteiro([texto_do_modelo(t) for t in respostas])
    agente = monta_agente(anthropic=anthropic)
    agente.sessao_salva.update(sessao)
    saida = agente.process_message(CLINIC, mensagem("sim"))
    texto = " ".join(getattr(m, "content", "") or "" for m in (saida or []))
    return texto, anthropic.correcoes


def com_campanha():
    return {"campanha": abre(DATAS, agora=int(time.time()))}


class TestEmCampanha(unittest.TestCase):
    def test_o_pedido_de_cadastro_e_refeito(self):
        texto, correcoes = roda(com_campanha(), [PEDIDO, OK])

        self.assertTrue(correcoes, "o modelo nao recebeu o PARE")
        self.assertIn("JA E PACIENTE CADASTRADA", correcoes[0])
        self.assertNotIn("CPF", texto)
        self.assertIn("area", texto)

    def test_mensagem_normal_nao_e_refeita(self):
        texto, correcoes = roda(com_campanha(), [OK])

        self.assertEqual(correcoes, [])
        self.assertIn("area", texto)

    def test_insistir_apos_o_PARE_nao_chega_a_paciente(self):
        """Ultima rede. Rarissimo por construcao, mas e o erro que nao pode sair."""
        texto, _ = roda(com_campanha(), [PEDIDO, PEDIDO])

        self.assertNotIn("CPF", texto)
        self.assertNotIn("Nome completo", texto)


class TestForaDaCampanha(unittest.TestCase):
    """No fluxo de lead, pedir cadastro e o comportamento CERTO."""

    def test_lead_pode_pedir_cadastro(self):
        texto, correcoes = roda({"bot_enabled": True}, [PEDIDO])

        self.assertEqual(correcoes, [])
        self.assertIn("CPF", texto)

    def test_campanha_vencida_volta_a_permitir(self):
        vencida = {"campanha": abre(DATAS, agora=int(time.time()) - 8 * 86400)}
        texto, correcoes = roda(vencida, [PEDIDO])

        self.assertEqual(correcoes, [])
        self.assertIn("CPF", texto)


if __name__ == "__main__":
    unittest.main()
