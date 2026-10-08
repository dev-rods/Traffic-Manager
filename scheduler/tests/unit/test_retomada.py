# -*- coding: utf-8 -*-
"""A retomada por vencimento falha fechada: seis guardas antes do modelo, e
o modelo só classifica. PRD 020 §3.7.
"""
import os
import time
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at
from src.services import retomada

CLINICA = {"clinic_id": "c1", "timezone": "America/Sao_Paulo", "idade_maxima_da_pendencia_horas": 72}
PHONE = "5511999990000"
H = 3600
# 15:00 UTC = 12:00 em Brasília, fora da janela de silêncio.
AGORA = int(time.mktime(time.strptime("2026-10-08T15:00:00", "%Y-%m-%dT%H:%M:%S")) - time.timezone)


def _iso(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def evento(direction, content, ha_horas):
    return {"direction": direction, "content": content, "sk": f"MSG#{_iso(AGORA - ha_horas * H)}#x"}


def sessao_vencida(**kw):
    return at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 30 * H, **kw)


class TestGuardas(unittest.TestCase):
    def test_tudo_passa(self):
        ev = [evento("OUTBOUND", "Oi!", 40), evento("INBOUND", "tem horário sábado de manhã?", 30)]
        pode, motivo = retomada.pode_retomar(sessao_vencida(), ev, 0, CLINICA, PHONE, AGORA)
        self.assertTrue(pode, motivo)

    def test_ultima_fala_do_bot_nao_retoma(self):
        ev = [evento("INBOUND", "tem horário?", 31), evento("OUTBOUND", "Tenho sim, 10h.", 30)]
        self.assertEqual(retomada.pode_retomar(sessao_vencida(), ev, 0, CLINICA, PHONE, AGORA),
                         (False, retomada.ULTIMA_FALA_NAO_E_DO_CLIENTE))

    def test_fecho_social_nao_retoma(self):
        for texto in ("obrigada!", "ok", "Boa noite", "combinado", "valeu, até mais"):
            with self.subTest(texto=texto):
                ev = [evento("INBOUND", texto, 30)]
                self.assertEqual(retomada.pode_retomar(sessao_vencida(), ev, 0, CLINICA, PHONE, AGORA)[1],
                                 retomada.FECHO_SOCIAL)

    def test_pendencia_velha_nao_retoma(self):
        ev = [evento("INBOUND", "tem horário sábado?", 73)]
        self.assertEqual(retomada.pode_retomar(sessao_vencida(), ev, 0, CLINICA, PHONE, AGORA)[1],
                         retomada.PENDENCIA_VELHA)

    def test_idade_maxima_e_por_clinica(self):
        ev = [evento("INBOUND", "tem horário sábado?", 73)]
        clinica = {**CLINICA, "idade_maxima_da_pendencia_horas": 96}
        self.assertTrue(retomada.pode_retomar(sessao_vencida(), ev, 0, clinica, PHONE, AGORA)[0])

    def test_efeito_depois_da_fala_e_resolvido_fora(self):
        """Agendamento criado depois da pergunta: a atendente resolveu por
        telefone ou no balcão. Responder agora seria repetir."""
        ev = [evento("INBOUND", "tem horário sábado?", 30)]
        self.assertEqual(retomada.pode_retomar(sessao_vencida(), ev, 1, CLINICA, PHONE, AGORA)[1],
                         retomada.RESOLVIDO_FORA)

    def test_uma_retomada_por_pendencia(self):
        ev = [evento("INBOUND", "tem horário sábado?", 30)]
        s = sessao_vencida()
        at.marca_retomada(s, AGORA - H)
        self.assertEqual(retomada.pode_retomar(s, ev, 0, CLINICA, PHONE, AGORA)[1], retomada.JA_RETOMADO)

    def test_porta_fechada_nao_retoma(self):
        ev = [evento("INBOUND", "tem horário sábado?", 30)]
        self.assertEqual(retomada.pode_retomar(sessao_vencida(), ev, 0, {**CLINICA, "bot_paused": True}, PHONE, AGORA)[1],
                         retomada.PORTA_FECHADA)

    def test_de_madrugada_espera(self):
        """A retomada é proativa: respeita a janela de silêncio."""
        madrugada = AGORA - 9 * H  # 03:00 em Brasília
        ev = [evento("INBOUND", "tem horário sábado?", 30)]
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=madrugada - 30 * H)
        self.assertEqual(retomada.pode_retomar(s, ev, 0, CLINICA, PHONE, madrugada)[1], retomada.PORTA_FECHADA)

    def test_conversa_vazia(self):
        self.assertEqual(retomada.pode_retomar(sessao_vencida(), [], 0, CLINICA, PHONE, AGORA)[1],
                         retomada.ULTIMA_FALA_NAO_E_DO_CLIENTE)


class AnthropicFalso:
    def __init__(self, texto):
        self.texto = texto
        self.chamadas = []

    def create_message(self, system, messages, max_tokens=None, **kw):
        self.chamadas.append((system, messages))
        return {"content": [{"type": "text", "text": self.texto}]}


class TestClassificador(unittest.TestCase):
    EV = [evento("OUTBOUND", "Oi!", 40), evento("INBOUND", "tem horário sábado de manhã?", 30)]

    def test_pendente(self):
        r = retomada.classifica(AnthropicFalso('{"pendente": true, "o_que": "horário no sábado de manhã"}'), self.EV)
        self.assertTrue(r["pendente"])
        self.assertIn("sábado", r["o_que"])

    def test_nao_pendente(self):
        self.assertFalse(retomada.classifica(AnthropicFalso('{"pendente": false, "o_que": ""}'), self.EV)["pendente"])

    def test_saida_invalida_e_nao_pendente(self):
        """Falha fechada: o modelo divagou, o bot cala."""
        for lixo in ("Acho que sim, ela quer marcar.", "", "{pendente: talvez}"):
            with self.subTest(lixo=lixo):
                self.assertFalse(retomada.classifica(AnthropicFalso(lixo), self.EV)["pendente"])

    def test_erro_na_api_e_nao_pendente(self):
        class Quebrado:
            def create_message(self, **kw):
                raise RuntimeError("down")
        self.assertFalse(retomada.classifica(Quebrado(), self.EV)["pendente"])

    def test_o_classificador_nao_recebe_tools(self):
        a = AnthropicFalso('{"pendente": true, "o_que": "x"}')
        retomada.classifica(a, self.EV)
        system, messages = a.chamadas[0]
        self.assertIn("SOMENTE com JSON", system)
        self.assertIn("PESSOA: tem horário sábado de manhã?", messages[0]["content"])


class TestContexto(unittest.TestCase):
    def test_bloco_reconhece_o_atraso_e_repergunta_a_data(self):
        b = retomada.bloco_de_contexto(30, "horário no sábado")
        self.assertIn("30h", b)
        self.assertIn("NÃO a resolva", b)
        self.assertIn("horário no sábado", b)


if __name__ == "__main__":
    unittest.main()
