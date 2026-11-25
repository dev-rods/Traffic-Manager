# -*- coding: utf-8 -*-
"""Despedida depois da despedida: o bot cala (PRD 064).

Em 24/11/2026 uma paciente da Nobre agradeceu, o bot se despediu, ela
respondeu "Até 🙂" e o bot se despediu de novo. A regra vive num módulo só
e vale para o fluxo normal e para as duas retomadas.
"""
import time
import unittest

from src.services import fecho_social


def evento(direction, content, ha_segundos=60, autor=None):
    quando = time.gmtime(time.time() - ha_segundos)
    sk = f"MSG#{time.strftime('%Y-%m-%dT%H:%M:%S', quando)}Z#x"
    e = {"direction": direction, "content": content, "sk": sk}
    if autor:
        e["metadata"] = {"autor": autor}
    return e


class TestEFechoSocial(unittest.TestCase):

    def test_so_despedida_ou_agradecimento(self):
        for t in ["Até 🙂", "Muito obrigada 😊", "Obrigada!", "tchau", "Ok", "Valeu, até mais",
                  "Boa noite", "perfeito 💕💕"]:
            self.assertTrue(fecho_social.e_fecho_social(t), t)

    def test_pergunta_ou_dado_nao_e_fecho(self):
        for t in ["Obrigada, e amanhã abre?", "Até dia 3 então", "Pode ser 15:40",
                  "obrigada mas posso usar perspirex?"]:
            self.assertFalse(fecho_social.e_fecho_social(t) and not fecho_social.tem_conteudo_novo(t), t)


class TestDeveCalar(unittest.TestCase):

    def test_despedida_depois_da_despedida_do_bot_cala(self):
        eventos = [
            evento("INBOUND", "Muito obrigada 😊", 120),
            evento("OUTBOUND", "Por nada! Até o dia 03/12 💛", 60),
        ]
        self.assertTrue(fecho_social.deve_calar(eventos, "Até 🙂"))

    def test_bot_deixou_pergunta_entao_responde(self):
        eventos = [evento("OUTBOUND", "Qual horário fica melhor para você?", 60)]
        self.assertFalse(fecho_social.deve_calar(eventos, "ok"))

    def test_ultima_fala_foi_da_recepcao_entao_responde(self):
        eventos = [evento("OUTBOUND", "Até mais!", 60, autor="HUMANO")]
        self.assertFalse(fecho_social.deve_calar(eventos, "até"))

    def test_envio_do_sistema_nao_e_despedida_do_bot(self):
        eventos = [evento("OUTBOUND", "Agendamento confirmado! Te esperamos no dia 03/12.", 60, autor="SISTEMA")]
        self.assertFalse(fecho_social.deve_calar(eventos, "Muito obrigada"))

    def test_despedida_velha_nao_conta(self):
        eventos = [evento("OUTBOUND", "Até lá! 💛", 2 * 24 * 3600)]
        self.assertFalse(fecho_social.deve_calar(eventos, "oi, boa tarde"))

    def test_pergunta_junto_da_despedida_responde(self):
        eventos = [evento("OUTBOUND", "Até lá! 💛", 60)]
        self.assertFalse(fecho_social.deve_calar(eventos, "obrigada! e preciso raspar antes?"))

    def test_sem_eventos_responde(self):
        self.assertFalse(fecho_social.deve_calar([], "obrigada"))


class TestMotivoDeclarado(unittest.TestCase):

    def test_despedida_e_agradecimento_contam(self):
        for m in ["despedida, nada a consultar", "paciente apenas agradeceu, conversa encerrada", "Tchau"]:
            self.assertTrue(fecho_social.motivo_e_despedida(m), m)

    def test_dados_de_cadastro_nao_contam(self):
        self.assertFalse(fecho_social.motivo_e_despedida("paciente mandou nome e CPF"))
