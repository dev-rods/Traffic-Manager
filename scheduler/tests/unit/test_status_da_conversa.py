# -*- coding: utf-8 -*-
"""Em que pé está a conversa do lead, lido das fontes e não de coluna copiada.

Em 05/09/2026 a lead "Julia Dalçóquio" aparecia como "Sem contato" tendo
conversa desenvolvida no WhatsApp. Duas causas somadas: o nono dígito (o z-api
guarda 554797053940, o formulário gravou 5547997053940) e o atendimento humano,
que não passa pelo webhook e por isso não deixa rastro em lugar nenhum nosso.

Medido: 27 dos 37 leads do site tinham conversa e o painel mostrava 10.
"""
import time
import unittest

from src.services import atendimento as at
from src.services.status_da_conversa import (
    AGUARDA_HUMANO,
    BOT,
    HUMANO,
    SEM_CONVERSA,
    enriquece,
    status_de_uma_sessao,
)

FUTURO = int(time.time()) + 3600
PASSADO = int(time.time()) - 3600


def entregue(por, ate=FUTURO):
    return at.entrega_a_humano({}, por=por, ate=ate)


class TestStatusDeUmaSessao(unittest.TestCase):
    def test_sem_sessao(self):
        self.assertEqual(status_de_uma_sessao(None), SEM_CONVERSA)
        self.assertEqual(status_de_uma_sessao({}), SEM_CONVERSA)

    def test_bot_conduzindo(self):
        for sessao in ({"agent_history": []}, {at.CAMPO: {"handler": at.BOT_ACTIVE}}):
            with self.subTest(sessao=sessao):
                self.assertEqual(status_de_uma_sessao(sessao), BOT)

    def test_atendente_assumiu(self):
        self.assertEqual(
            status_de_uma_sessao(entregue(at.POR_ATENDENTE)), HUMANO)

    def test_marca_de_atendente_vencida_volta_para_o_bot(self):
        """A marca dura 24h. Sem o vencimento, uma conversa atendida uma vez
        ficaria marcada como humana para sempre."""
        self.assertEqual(
            status_de_uma_sessao(entregue(at.POR_ATENDENTE, PASSADO)), BOT)

    def test_bot_pediu_ajuda_e_ninguem_assumiu(self):
        """Estado diferente de "atendente atuando": é fila, não atendimento."""
        self.assertEqual(status_de_uma_sessao(entregue(at.POR_HANDOFF)),
                         AGUARDA_HUMANO)


def lead(phone, **extra):
    d = {"phone": phone, "name": "Fulana", "conversation_started_at": None}
    d.update(extra)
    return d


def chat(phone, quando="2026-08-27"):
    return {phone: {"phone": phone, "name": "Fulana",
                    "last_message_at": quando, "unread_count": 0}}


class TestEnriquece(unittest.TestCase):
    def test_o_caso_da_julia(self):
        """O z-api guarda sem o nono dígito; o lead tem com. Mesma pessoa."""
        saida = enriquece([lead("5547997053940")], {}, chat("554797053940"))

        self.assertTrue(saida[0]["has_whatsapp_chat"])
        self.assertEqual(saida[0]["whatsapp_last_message_at"], "2026-08-27")

    def test_conversa_sem_sessao_e_atendimento_humano(self):
        """Existe conversa no WhatsApp e nenhuma sessão nossa: quem falou foi
        gente, pelo celular. Chamar isso de "sem conversa" é o defeito que
        trouxe esta feature."""
        saida = enriquece([lead("5547997053940")], {}, chat("554797053940"))

        self.assertEqual(saida[0]["conversation_status"], HUMANO)

    def test_sem_conversa_em_lugar_nenhum(self):
        saida = enriquece([lead("5511999990000")], {}, {})

        self.assertFalse(saida[0]["has_whatsapp_chat"])
        self.assertEqual(saida[0]["conversation_status"], SEM_CONVERSA)

    def test_sessao_manda_no_status(self):
        saida = enriquece(
            [lead("5511999990000")],
            {"5511999990000": entregue(at.POR_HANDOFF)},
            chat("5511999990000"),
        )

        self.assertEqual(saida[0]["conversation_status"], AGUARDA_HUMANO)

    def test_nao_mexe_no_respondeu(self):
        """A lista de chats não diz QUEM falou. Usá-la para "respondeu" inflaria
        a taxa de conversão com conversas em que só a clínica falou."""
        saida = enriquece([lead("5547997053940")], {}, chat("554797053940"))

        self.assertIsNone(saida[0]["conversation_started_at"])

    def test_nao_altera_a_lista_recebida(self):
        original = lead("5511999990000")
        enriquece([original], {}, {})

        self.assertNotIn("conversation_status", original)

    def test_lista_vazia(self):
        self.assertEqual(enriquece([], {}, {}), [])


if __name__ == "__main__":
    unittest.main()
