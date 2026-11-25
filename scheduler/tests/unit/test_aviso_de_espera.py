# -*- coding: utf-8 -*-
"""Aviso imediato quando a política cala o bot (PRD 064, P5) e o script do
prompt (P6)."""
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services import atendimento, aviso_de_espera, fecho_social, retomada
from src.services.conversation_resume import ha_pergunta_em_aberto
from src.services.envio_do_sistema import AVISO_DE_ESPERA
from src.scripts import corrige_prompt_064 as script

LEADS_ONLY = {"clinic_id": "c1", "display_name": "Nobre Laser", "bot_autoreply_policy": "LEADS_ONLY", "bot_paused": False}
ALL = dict(LEADS_ONLY, bot_autoreply_policy="ALL")


class TestMotivoDaRecusa(unittest.TestCase):
    def test_politica(self):
        self.assertEqual(atendimento.motivo_da_recusa(LEADS_ONLY, {}, "5511999990000"), atendimento.RECUSA_POLITICA)

    def test_outras_portas_vem_antes(self):
        self.assertEqual(atendimento.motivo_da_recusa(LEADS_ONLY, {}, "55", silenciado=True), atendimento.RECUSA_SILENCIADO)
        self.assertEqual(atendimento.motivo_da_recusa(dict(LEADS_ONLY, bot_paused=True), {}, "55"), atendimento.RECUSA_PAUSADO)
        sessao = atendimento.entrega_a_humano({}, por=atendimento.POR_ATENDENTE)
        self.assertEqual(atendimento.motivo_da_recusa(LEADS_ONLY, sessao, "55"), atendimento.RECUSA_COM_PESSOA)

    def test_pode_responder_e_none(self):
        self.assertIsNone(atendimento.motivo_da_recusa(ALL, {}, "55"))
        self.assertIsNone(atendimento.motivo_da_recusa(LEADS_ONLY, {"bot_enabled": True}, "55"))


class TestDeveEnviar(unittest.TestCase):
    def test_so_quando_a_politica_cala(self):
        self.assertTrue(aviso_de_espera.deve_enviar(LEADS_ONLY, {}, "55"))
        self.assertFalse(aviso_de_espera.deve_enviar(ALL, {}, "55"))
        self.assertFalse(aviso_de_espera.deve_enviar(LEADS_ONLY, {}, "55", silenciado=True))
        self.assertFalse(aviso_de_espera.deve_enviar(dict(LEADS_ONLY, bot_paused=True), {}, "55"))

    def test_uma_vez_por_24h(self):
        agora = 1_000_000
        self.assertFalse(aviso_de_espera.deve_enviar(LEADS_ONLY, {aviso_de_espera.CAMPO: agora - 3600}, "55", agora=agora))
        self.assertTrue(aviso_de_espera.deve_enviar(LEADS_ONLY, {aviso_de_espera.CAMPO: agora - 25 * 3600}, "55", agora=agora))


class TestEnvia(unittest.TestCase):
    def test_manda_como_sistema_e_marca_a_sessao(self):
        tpl = mock.MagicMock()
        tpl.get_and_render.return_value = "Oi! Uma especialista da Nobre Laser vai te responder em instantes."
        sessao = {}
        with mock.patch.object(aviso_de_espera, "envia_texto", return_value=mock.MagicMock(success=True)) as env:
            ok = aviso_de_espera.envia(LEADS_ONLY, "5511999990000", tpl, sessao, agora=123)
        self.assertTrue(ok)
        self.assertEqual(sessao[aviso_de_espera.CAMPO], 123)
        self.assertEqual(env.call_args[0][3], AVISO_DE_ESPERA)
        tpl.get_and_render.assert_called_once_with("c1", "AVISO_DE_ESPERA", {"clinic_display_name": "Nobre Laser"})

    def test_falha_nao_marca(self):
        tpl = mock.MagicMock(); tpl.get_and_render.return_value = "x"
        sessao = {}
        with mock.patch.object(aviso_de_espera, "envia_texto", side_effect=RuntimeError("fora")):
            self.assertFalse(aviso_de_espera.envia(LEADS_ONLY, "55", tpl, sessao))
        self.assertNotIn(aviso_de_espera.CAMPO, sessao)


def evento(direction, content, ha_segundos=60, origem=None):
    quando = time.gmtime(time.time() - ha_segundos)
    e = {"direction": direction, "content": content,
         "sk": f"MSG#{time.strftime('%Y-%m-%dT%H:%M:%S', quando)}Z#x"}
    if origem:
        e["metadata"] = {"origem": origem}
    return e


class TestOAvisoNaoContaComoResposta(unittest.TestCase):
    def setUp(self):
        self.eventos = [
            evento("INBOUND", "Quanto é a virilha?", 120),
            evento("OUTBOUND", "Oi! Uma especialista vai te responder em instantes.", 100, origem=AVISO_DE_ESPERA),
        ]

    def test_retomada_pelo_painel_ve_a_pergunta_em_aberto(self):
        self.assertTrue(ha_pergunta_em_aberto(self.eventos))

    def test_retomada_automatica_ve_a_pergunta_como_ultima_fala(self):
        self.assertEqual(retomada.ultima_fala(self.eventos)["content"], "Quanto é a virilha?")

    def test_fecho_social_nao_toma_o_aviso_por_despedida_do_bot(self):
        ev = [evento("OUTBOUND", "Oi! Qualquer dúvida, é só chamar. Até breve!", 60, origem=AVISO_DE_ESPERA)]
        self.assertFalse(fecho_social.deve_calar(ev, "obrigada"))


class TestScriptDoPrompt(unittest.TestCase):
    PROMPT = "x\n" + script.DUVIDA_VELHO + "\ny\n" + script.VIRILHA_VELHO + "\nz\n"

    def test_aplica_as_duas_trocas_e_e_idempotente(self):
        novo, status = script.aplica(self.PROMPT)
        self.assertEqual(status, {"DÚVIDA": script.APLICADO, "VIRILHA": script.APLICADO})
        self.assertIn("valor de cada uma", novo)
        self.assertNotIn("já vai para a pessoa como mensagem própria", novo)
        de_novo, status2 = script.aplica(novo)
        self.assertEqual(de_novo, novo)
        self.assertEqual(status2, {"DÚVIDA": script.JA_CORRIGIDO, "VIRILHA": script.JA_CORRIGIDO})

    def test_bloco_editado_a_mao_e_pulado(self):
        _, status = script.aplica("prompt sem os blocos")
        self.assertEqual(status, {"DÚVIDA": script.BLOCO_AUSENTE, "VIRILHA": script.BLOCO_AUSENTE})
