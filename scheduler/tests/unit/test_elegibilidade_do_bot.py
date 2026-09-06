# -*- coding: utf-8 -*-
"""Quando o botão "Iniciar pelo Bot" pode aparecer aceso.

O disparo automático foi removido em 05/09/2026 porque não há como saber por API
que a atendente já falou com um lead que nunca respondeu: a mensagem dela chega
ao webhook como LID sem telefone, e o z-api também não resolve (4 de 27 LIDs
testados, e os 4 já estavam na agenda do aparelho).

Agora quem decide é a atendente, e esta função é a regra. Ela roda em dois
lugares - para desenhar o botão e para validar o clique - e é a MESMA nos dois
de propósito: duas cópias divergiriam em silêncio, que é como um lead com
conversa desenvolvida apareceu como "sem contato".
"""
import unittest

from src.services.elegibilidade_do_bot import (
    MOTIVOS,
    motivo_legivel,
    pode_desmarcar,
    pode_iniciar,
    por_que_nao_pode,
)

PILOTO = "5511970522647"
CLINICA_ABERTA = {"bot_autoreply_policy": "ALL", "bot_paused": False}
CLINICA_PILOTO = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PILOTO],
                  "bot_paused": False}


def lead(**over):
    d = {
        "phone": "5511999990000",
        "source": "landing-page",
        "conversation_started_at": None,
        "first_contact_at": None,
        "first_contact_status": None,
        "first_contact_channel": None,
        "has_whatsapp_chat": False,
    }
    d.update(over)
    return d


class TestPodeIniciar(unittest.TestCase):
    def test_lead_da_landing_page_intocado(self):
        self.assertTrue(pode_iniciar(lead(), CLINICA_ABERTA))
        self.assertIsNone(por_que_nao_pode(lead(), CLINICA_ABERTA))


class TestNaoPode(unittest.TestCase):
    """Cada caso é uma mensagem que não pode sair."""

    def test_origem_que_nao_e_landing_page(self):
        for origem in ("whatsapp", "harmonizacao", None, ""):
            with self.subTest(origem=origem):
                self.assertEqual(por_que_nao_pode(lead(source=origem), CLINICA_ABERTA),
                                 "ORIGEM")

    def test_a_pessoa_ja_escreveu(self):
        self.assertEqual(
            por_que_nao_pode(lead(conversation_started_at="2026-09-01"), CLINICA_ABERTA),
            "JA_RESPONDEU")

    def test_o_bot_ja_enviou(self):
        self.assertEqual(
            por_que_nao_pode(lead(first_contact_status="SENT", first_contact_at="2026-09-01",
                                  first_contact_channel="BOT"), CLINICA_ABERTA),
            "JA_CONTATADA")

    def test_ja_esta_na_fila(self):
        """QUEUED sem first_contact_at: clicar de novo enfileiraria em dobro."""
        self.assertEqual(
            por_que_nao_pode(lead(first_contact_status="QUEUED"), CLINICA_ABERTA),
            "JA_CONTATADA")

    def test_a_atendente_marcou_ja_iniciada(self):
        self.assertEqual(
            por_que_nao_pode(lead(first_contact_status="SENT", first_contact_at="2026-09-01",
                                  first_contact_channel="HUMANO"), CLINICA_ABERTA),
            "JA_CONTATADA")

    def test_existe_conversa_no_espelho_do_whatsapp(self):
        self.assertEqual(por_que_nao_pode(lead(has_whatsapp_chat=True), CLINICA_ABERTA),
                         "TEM_CONVERSA")

    def test_sem_telefone(self):
        for vazio in (None, ""):
            with self.subTest(phone=vazio):
                self.assertEqual(por_que_nao_pode(lead(phone=vazio), CLINICA_ABERTA),
                                 "SEM_TELEFONE")

    def test_lead_ou_clinica_ausente(self):
        self.assertIsNotNone(por_que_nao_pode(None, CLINICA_ABERTA))
        self.assertIsNotNone(por_que_nao_pode(lead(), None))


class TestPoliticaValeParaOBotao(unittest.TestCase):
    """Decisão do André em 05/09/2026: o piloto vale para o botão.

    Sem isto o clique enfileiraria um item que o dispatcher recusa por política
    e adia até expirar - a atendente veria "na fila" parado e não entenderia.
    """

    def test_fora_do_piloto_nao_pode(self):
        self.assertEqual(por_que_nao_pode(lead(phone="5511988887777"), CLINICA_PILOTO),
                         "POLITICA")

    def test_dentro_do_piloto_pode(self):
        self.assertIsNone(por_que_nao_pode(lead(phone=PILOTO), CLINICA_PILOTO))

    def test_bot_pausado_nao_pode(self):
        self.assertEqual(
            por_que_nao_pode(lead(), {**CLINICA_ABERTA, "bot_paused": True}), "POLITICA")

    def test_leads_only_pode_para_landing_page(self):
        self.assertIsNone(
            por_que_nao_pode(lead(), {"bot_autoreply_policy": "LEADS_ONLY"}))


class TestOrdemDosMotivos(unittest.TestCase):
    """A mensagem precisa ser útil, não só verdadeira."""

    def test_o_motivo_especifico_vence_a_politica(self):
        """Um lead de WhatsApp em clínica piloto tem dois problemas. Dizer
        "política" esconde o que a atendente precisa saber."""
        self.assertEqual(
            por_que_nao_pode(lead(source="whatsapp", phone="5511988887777"), CLINICA_PILOTO),
            "ORIGEM")

    def test_ja_respondeu_vence_ja_contatada(self):
        self.assertEqual(
            por_que_nao_pode(lead(conversation_started_at="2026-09-01",
                                  first_contact_status="SENT"), CLINICA_ABERTA),
            "JA_RESPONDEU")

    def test_todo_motivo_tem_texto(self):
        """Botão apagado sem explicação vira chamado de suporte."""
        for chave in MOTIVOS:
            with self.subTest(chave=chave):
                self.assertTrue(motivo_legivel(chave).strip())

    def test_motivo_desconhecido_nao_explode(self):
        self.assertEqual(motivo_legivel(None), "")
        self.assertEqual(motivo_legivel("INVENTADO"), "")


class TestDesmarcar(unittest.TestCase):
    def test_o_que_a_pessoa_marcou_ela_desmarca(self):
        self.assertTrue(pode_desmarcar(lead(first_contact_channel="HUMANO")))

    def test_envio_do_bot_nao_se_desmarca(self):
        """A mensagem está no WhatsApp de alguém. Desmarcar seria mentira, e
        reabriria o botão para mandar uma segunda."""
        self.assertFalse(pode_desmarcar(lead(first_contact_channel="BOT")))

    def test_sem_contato_nao_ha_o_que_desmarcar(self):
        self.assertFalse(pode_desmarcar(lead()))
        self.assertFalse(pode_desmarcar(None))


if __name__ == "__main__":
    unittest.main()
