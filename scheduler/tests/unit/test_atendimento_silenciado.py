# -*- coding: utf-8 -*-
"""O silêncio por contato vence TODAS as portas (PRD 039, decisão §4.1).

Isto é a exceção declarada à decisão 9.1 do PRD 020. Se algum destes testes
cair, o botão "Silenciar" passou a ter exceção invisível - que é exatamente o
que derruba a confiança de quem clica.
"""
import unittest

from src.services import atendimento, campanha, lembrete

PHONE = "5511999990000"
AGORA = 1762000000
LIBERADA = {"bot_autoreply_policy": "ALL"}
SO_LEADS = {"bot_autoreply_policy": "LEADS_ONLY"}


def com_campanha():
    return {"campanha": campanha.abre(["2026-12-01"], agora=AGORA)}


def com_lembrete():
    return {"lembrete": {"appointment_id": "a1", "dia": "2026-11-09",
                         "hora": "10:00", "areas": "",
                         "expira_em": AGORA + 3600}}


class TestPodeResponder(unittest.TestCase):
    def test_silenciado_nao_responde_mesmo_com_tudo_liberado(self):
        self.assertTrue(atendimento.pode_responder(LIBERADA, {}, PHONE, AGORA))
        self.assertFalse(atendimento.pode_responder(LIBERADA, {}, PHONE, AGORA,
                                                    silenciado=True))

    def test_vence_os_tres_caminhos_de_leads_only(self):
        """Lead que escreveu, campanha viva e lembrete vivo abrem a conversa
        sob LEADS_ONLY. Nenhum dos três abre um contato silenciado."""
        for nome, sessao in (("bot_enabled", {"bot_enabled": True}),
                             ("campanha", com_campanha()),
                             ("lembrete", com_lembrete())):
            with self.subTest(caminho=nome):
                self.assertTrue(
                    atendimento.pode_responder(SO_LEADS, sessao, PHONE, AGORA),
                    f"{nome} deveria abrir a conversa quando NÃO silenciada")
                self.assertFalse(
                    atendimento.pode_responder(SO_LEADS, sessao, PHONE, AGORA,
                                               silenciado=True))

    def test_nao_silenciado_segue_como_antes(self):
        """O default não muda nada: `silenciado=False` é o comportamento de
        sempre, em todas as combinações."""
        self.assertEqual(
            atendimento.pode_responder(SO_LEADS, {"bot_enabled": True}, PHONE, AGORA),
            atendimento.pode_responder(SO_LEADS, {"bot_enabled": True}, PHONE, AGORA,
                                       silenciado=False))


class TestPodeIniciar(unittest.TestCase):
    def test_transacional_nao_isenta(self):
        """`transacional=True` pula o cooldown (lembrete e retomada). NÃO pula
        o silêncio: a retomada por vencimento é justamente o caminho que
        devolveria ao bot uma conversa que alguém mandou calar."""
        sessao = atendimento.entrega_a_humano({}, por=atendimento.POR_ATENDENTE,
                                              agora=AGORA - 30 * 3600)
        sessao, _ = atendimento.avalia_vencimento(sessao, AGORA)
        self.assertTrue(atendimento.pode_iniciar(LIBERADA, sessao, PHONE, AGORA,
                                                 transacional=True))
        self.assertFalse(atendimento.pode_iniciar(LIBERADA, sessao, PHONE, AGORA,
                                                  transacional=True, silenciado=True))

    def test_silenciado_nao_inicia(self):
        self.assertTrue(atendimento.pode_iniciar(LIBERADA, {}, PHONE, AGORA))
        self.assertFalse(atendimento.pode_iniciar(LIBERADA, {}, PHONE, AGORA,
                                                  silenciado=True))


class TestMotivoDaPausa(unittest.TestCase):
    def test_muted_vem_na_frente_de_todos(self):
        atendente = atendimento.entrega_a_humano({}, por=atendimento.POR_ATENDENTE,
                                                 agora=AGORA)
        casos = [
            ("conversa limpa", LIBERADA, {}),
            ("com atendente", LIBERADA, atendente),
            ("clínica pausada", {**LIBERADA, "bot_paused": True}, {}),
            ("fora da regra", SO_LEADS, {}),
        ]
        for nome, clinic, sessao in casos:
            with self.subTest(caso=nome):
                self.assertEqual(
                    atendimento.motivo_da_pausa(clinic, sessao, PHONE, AGORA,
                                                silenciado=True),
                    atendimento.PAUSA_SILENCIADO)

    def test_sem_silencio_os_motivos_antigos_ficam(self):
        self.assertIsNone(atendimento.motivo_da_pausa(LIBERADA, {}, PHONE, AGORA))
        self.assertEqual(
            atendimento.motivo_da_pausa({**LIBERADA, "bot_paused": True}, {}, PHONE, AGORA),
            atendimento.PAUSA_CLINICA)
        self.assertEqual(
            atendimento.motivo_da_pausa(SO_LEADS, {}, PHONE, AGORA),
            atendimento.PAUSA_FORA_DA_REGRA)


class TestOSilencioNaoVence(unittest.TestCase):
    """Nenhuma passagem de tempo devolve a conversa ao bot - é a diferença
    inteira em relação à pausa de 24h."""

    def test_um_mes_depois_continua_calado(self):
        um_mes = AGORA + 30 * 24 * 3600
        self.assertFalse(atendimento.pode_responder(LIBERADA, {}, PHONE, um_mes,
                                                    silenciado=True))
        self.assertFalse(atendimento.pode_iniciar(LIBERADA, {}, PHONE, um_mes,
                                                  silenciado=True))


if __name__ == "__main__":
    unittest.main()
