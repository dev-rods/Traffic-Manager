# -*- coding: utf-8 -*-
"""As datas da campanha sao respaldo - a guarda nao pode barrar quem esta certo.

Em 11/09/2026 o Andre pediu "Gostaria de agendar dia 25". O bot compos a
resposta CERTA:

    "As datas disponiveis sao as que ja te passei: *23, 24 e 29 de setembro.*
     Dia 25 nao temos agenda."

e a proveniencia a BLOQUEOU - "agenda sem respaldo ['2026-09-29']" - porque
aquela data nao tinha vindo de tool naquela rodada. A resposta caiu no fallback
e o bot transferiu para uma especialista sem necessidade.

As datas da campanha vem da sessao, gravadas no ato do disparo, e o bloco de
campanha as poe no prompt. Sao fato tao legitimo quanto resultado de tool - e
foi por isso que o calendario ja entrava no respaldo pelo mesmo motivo.

Uma guarda que barra a resposta correta custa duas vezes: a paciente nao e
atendida E alguem da clinica e chamado a toa.
"""
import time
import unittest

from src.services.campanha import abre
from src.services.proveniencia import fatos_de_agenda, fatos_sem_origem

DATAS = ["2026-09-23", "2026-09-24", "2026-09-29"]
RESPOSTA_BLOQUEADA = (
    "As datas disponiveis sao as que ja te passei: *23, 24 e 29 de setembro.* "
    "Dia 25 nao temos agenda."
)


def bloqueia(resposta, respaldo):
    return bool(fatos_de_agenda(fatos_sem_origem(resposta, respaldo, ano=2026)))


class TestOCasoQueAconteceu(unittest.TestCase):
    def test_sem_o_respaldo_da_campanha_a_resposta_certa_e_barrada(self):
        """Prende o defeito: se alguem remover o respaldo, isto volta a falhar."""
        self.assertTrue(bloqueia(RESPOSTA_BLOQUEADA, [{"calendario": []}]))

    def test_com_o_respaldo_da_campanha_ela_passa(self):
        respaldo = [{"calendario": []}, {"campanha": DATAS}]
        self.assertFalse(bloqueia(RESPOSTA_BLOQUEADA, respaldo))


class TestAGuardaContinuaGuardando(unittest.TestCase):
    """O respaldo nao pode virar passe livre para qualquer data."""

    def test_data_fora_da_campanha_continua_sem_origem(self):
        resposta = "Tenho vaga tambem no dia *30 de setembro*."
        self.assertTrue(bloqueia(resposta, [{"campanha": DATAS}]))

    def test_campanha_vazia_nao_da_respaldo_a_nada(self):
        self.assertTrue(bloqueia(RESPOSTA_BLOQUEADA, [{"campanha": []}]))


class TestFiacao(unittest.TestCase):
    """O respaldo precisa SER montado no fluxo, nao so existir a funcao."""

    def test_o_agente_poe_as_datas_da_campanha_no_respaldo(self):
        from tests.unit.dublagem_agente import mensagem, monta_agente

        agente = monta_agente()
        agente.sessao_salva.update({"campanha": abre(DATAS, agora=int(time.time()))})
        agente.process_message("clinica-x", mensagem("quero agendar"))

        respaldo = agente.sessao_salva.get("respaldo_anterior") or []
        achou = any("campanha" in r for r in respaldo if isinstance(r, dict))
        self.assertTrue(
            achou,
            "as datas da campanha nao entraram no respaldo; a proveniencia vai "
            "bloquear a resposta certa e o bot vai transferir a toa")

    def test_conversa_sem_campanha_nao_ganha_respaldo_extra(self):
        from tests.unit.dublagem_agente import mensagem, monta_agente

        agente = monta_agente()
        agente.sessao_salva.update({"bot_enabled": True})
        agente.process_message("clinica-x", mensagem("quero agendar"))

        respaldo = agente.sessao_salva.get("respaldo_anterior") or []
        self.assertFalse(
            any("campanha" in r for r in respaldo if isinstance(r, dict)))


if __name__ == "__main__":
    unittest.main()
