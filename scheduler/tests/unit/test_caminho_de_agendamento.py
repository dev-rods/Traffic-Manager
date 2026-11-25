# -*- coding: utf-8 -*-
"""Link ou conversa, decidido antes do modelo (PRD 064, frente 3)."""
import time
import unittest

from src.services import caminho_de_agendamento as cam
from src.services.autoatendimento import (
    CAMPO_LINK_ENVIADO, marca_link_enviado, pedidos_de_agendar, zera_pedidos_de_agendar,
)

LINK = "https://agendar.clinica-teste.com.br/"
PACIENTE = {"encontrado": True, "nome": "Fulana", "cadastro_completo": True}
LEAD = {"encontrado": False}
CLINIC = {"clinic_id": "c1", "custom_domain": "agendar.clinica-teste.com.br"}


class TestPedeAgendar(unittest.TestCase):
    def test_pedidos(self):
        for t in ["Podemos marcar dia 3/12 as 15:30?", "quero agendar", "tem horário sexta?",
                  "quais datas vocês têm?", "gostaria de fazer a sessão", "Quero remarcar"]:
            self.assertTrue(cam.pede_agendar(t), t)

    def test_nao_pedidos(self):
        for t in ["quanto custa a virilha?", "obrigada", "qual o endereço?", "quero cancelar a sessão",
                  "não vou poder ir dia 3"]:
            self.assertFalse(cam.pede_agendar(t), t)

    def test_insistencia(self):
        for t in ["não consigo pelo site", "o link não abre", "prefiro aqui", "pode marcar pra mim?",
                  "marca pra mim por favor"]:
            self.assertTrue(cam.insiste_na_conversa(t), t)
        self.assertFalse(cam.insiste_na_conversa("quero agendar"))


class TestDecide(unittest.TestCase):
    def test_lead_sem_cadastro_e_conversa(self):
        self.assertEqual(cam.decide(CLINIC, LEAD, {}, "quero agendar", LINK), cam.CONVERSA)

    def test_sem_dominio_e_conversa(self):
        self.assertEqual(cam.decide(CLINIC, PACIENTE, {}, "quero agendar", None), cam.CONVERSA)

    def test_duvida_de_paciente_e_conversa(self):
        s = {}
        self.assertEqual(cam.decide(CLINIC, PACIENTE, s, "quanto custa a axila?", LINK), cam.CONVERSA)
        self.assertEqual(pedidos_de_agendar(s), 0)

    def test_primeiro_pedido_e_link_e_conta(self):
        s = {}
        self.assertEqual(cam.decide(CLINIC, PACIENTE, s, "Podemos marcar dia 3?", LINK), cam.LINK_PRIMEIRO)
        self.assertEqual(pedidos_de_agendar(s), 1)

    def test_segundo_pedido_e_conversa_por_insistencia(self):
        s = {}
        cam.decide(CLINIC, PACIENTE, s, "quero agendar", LINK)
        self.assertEqual(cam.decide(CLINIC, PACIENTE, s, "pode ser dia 3 às 15h?", LINK),
                         cam.CONVERSA_POR_INSISTENCIA)

    def test_nao_consigo_e_conversa_direto(self):
        s = {}
        cam.decide(CLINIC, PACIENTE, s, "quero agendar", LINK)
        self.assertEqual(cam.decide(CLINIC, PACIENTE, s, "o link não abre aqui", LINK),
                         cam.CONVERSA_POR_INSISTENCIA)

    def test_link_do_bot_ja_enviado_e_conversa(self):
        s = marca_link_enviado({})
        self.assertEqual(cam.decide(CLINIC, PACIENTE, s, "quero agendar", LINK), cam.CONVERSA)

    def test_link_velho_volta_a_ser_link_primeiro(self):
        s = marca_link_enviado({}, agora=int(time.time()) - 10 * 86400)
        self.assertEqual(cam.decide(CLINIC, PACIENTE, s, "quero agendar", LINK), cam.LINK_PRIMEIRO)

    def test_lembrete_vivo_e_conversa(self):
        s = {"lembrete": {"appointment_id": "ap-1", "expira_em": int(time.time()) + 3600}}
        self.assertEqual(cam.decide(CLINIC, PACIENTE, s, "quero remarcar", LINK), cam.CONVERSA)

    def test_campanha_nao_conta_como_link(self):
        """P2: o link do disparo não conta; a primeira resposta é o link."""
        s = {"campanha": {"modo": "REAGENDAMENTO", "datas": ["2026-12-03"], "expira_em": int(time.time()) + 3600}}
        self.assertEqual(cam.decide(CLINIC, PACIENTE, s, "Podemos marcar dia 3/12 as 15:30?", LINK),
                         cam.LINK_PRIMEIRO)

    def test_zera_depois_de_agendar(self):
        s = {}
        cam.decide(CLINIC, PACIENTE, s, "quero agendar", LINK)
        zera_pedidos_de_agendar(s)
        self.assertEqual(pedidos_de_agendar(s), 0)


class TestBlocoEGarantia(unittest.TestCase):
    def test_bloco_do_link_sem_oferta(self):
        b = cam.bloco(cam.LINK_PRIMEIRO, LINK)
        self.assertIn(LINK, b)
        self.assertIn("não ofereça marcar por aqui", b)
        self.assertIn("não chame check_availability", b)

    def test_bloco_da_insistencia_proibe_o_link(self):
        b = cam.bloco(cam.CONVERSA_POR_INSISTENCIA, LINK)
        self.assertIn("Nunca mande\no link de novo", b)
        self.assertNotIn(LINK, b)

    def test_conversa_nao_tem_bloco(self):
        self.assertEqual(cam.bloco(cam.CONVERSA, LINK), "")

    def test_garante_o_link(self):
        self.assertEqual(cam.garante_o_link("Oi! Quais áreas?", cam.LINK_PRIMEIRO, LINK),
                         f"Oi! Quais áreas?\n\n{LINK}")
        com = f"É por aqui: {LINK}"
        self.assertEqual(cam.garante_o_link(com, cam.LINK_PRIMEIRO, LINK), com)
        self.assertEqual(cam.garante_o_link("Oi!", cam.CONVERSA, LINK), "Oi!")
        self.assertIn(LINK, cam.garante_o_link("", cam.LINK_PRIMEIRO, LINK))
