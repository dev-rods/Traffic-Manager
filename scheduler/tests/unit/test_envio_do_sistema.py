# -*- coding: utf-8 -*-
"""O que o sistema manda pelo WhatsApp deixa rastro com origem (PRD 034).

Em 21/10/2026 20:02 UTC o site mandou OTP, confirmação e orientações para uma
paciente; para cada eco o webhook registrou "Atendente humano respondeu pelo
celular; pausando o bot por 24h". O eco só é reconhecido pelo providerMessageId
gravado no MessageEvents - e o site não gravava nada.

A tabela aqui é falsa mas GRAVA: o teste lê o item que ficou, não o mock.
"""
import os
import unittest

os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services import envio_do_sistema as es
from src.services.autoria_mensagem import autor_da_mensagem, foi_enviada_pelo_bot


class Resultado:
    def __init__(self, success=True, provider_message_id="3EB0ID", error=None):
        self.success = success
        self.provider_message_id = provider_message_id
        self.error = error
        self.raw_response = {"ok": success}


class Provedor:
    def __init__(self, resultado=None):
        self.resultado = resultado or Resultado()
        self.enviados = []

    def send_text(self, phone, content):
        self.enviados.append((phone, content))
        return self.resultado


class Tabela:
    """Guarda cada put_item; opcionalmente levanta, como o DynamoDB sem permissão."""

    def __init__(self, levanta=None):
        self.itens = []
        self.levanta = levanta

    def put_item(self, Item):
        if self.levanta:
            raise self.levanta
        self.itens.append(Item)


def _tracker(tabela):
    from src.services.message_tracker import MessageTracker
    t = MessageTracker.__new__(MessageTracker)
    t.table = tabela
    return t


CLINICA = {"clinic_id": "c1", "zapi_instance_id": "i", "zapi_instance_token": "t"}


class TestRastro(unittest.TestCase):
    def test_grava_queued_e_sent_com_id_e_origem(self):
        tabela, prov = Tabela(), Provedor()
        r = es.envia_texto(CLINICA, "5511999990000", "Agendado!", es.SITE_AGENDAMENTO,
                           provider=prov, tracker=_tracker(tabela))
        self.assertTrue(r.success)
        self.assertEqual([i["status"] for i in tabela.itens], ["QUEUED", "SENT"])
        self.assertEqual(len({i["messageId"] for i in tabela.itens}), 1)
        sent = tabela.itens[1]
        self.assertEqual(sent["providerMessageId"], "3EB0ID")
        self.assertEqual(sent["metadata"]["origem"], "SITE_AGENDAMENTO")
        self.assertEqual(sent["pk"], "CLINIC#c1#PHONE#5511999990000")
        self.assertEqual(sent["direction"], "OUTBOUND")

    def test_o_webhook_reconhece_o_eco(self):
        """É para isto que o rastro existe: o id gravado é o id do eco."""
        tabela = Tabela()
        es.envia_texto(CLINICA, "5511999990000", "x", es.CHECKIN,
                       provider=Provedor(), tracker=_tracker(tabela))
        self.assertTrue(foi_enviada_pelo_bot(tabela.itens, "3EB0ID"))
        self.assertEqual(autor_da_mensagem(tabela.itens[1]), "SISTEMA")

    def test_otp_grava_o_aviso_e_envia_o_codigo(self):
        tabela, prov = Tabela(), Provedor()
        es.envia_texto(CLINICA, "5511999990000", "Seu código de confirmação é 123456.",
                       es.SITE_OTP, conteudo_registrado="Código de confirmação enviado.",
                       provider=prov, tracker=_tracker(tabela))
        self.assertEqual(prov.enviados[0][1], "Seu código de confirmação é 123456.")
        for item in tabela.itens:
            self.assertEqual(item["content"], "Código de confirmação enviado.")
            self.assertNotIn("123456", str(item))

    def test_falha_do_provedor_fica_failed_com_erro(self):
        tabela = Tabela()
        prov = Provedor(Resultado(success=False, provider_message_id="", error="z-api 500"))
        r = es.envia_texto(CLINICA, "5511999990000", "x", es.SITE_AGENDAMENTO,
                           provider=prov, tracker=_tracker(tabela))
        self.assertFalse(r.success)
        self.assertEqual(tabela.itens[1]["status"], "FAILED")
        self.assertEqual(tabela.itens[1]["metadata"]["error"], "z-api 500")

    def test_tabela_sem_permissao_nao_impede_o_envio(self):
        """Foi o risco apontado na Spec: a role do site não escrevia em
        message-events. Se faltar, o envio tem que sair mesmo assim."""
        prov = Provedor()
        r = es.envia_texto(CLINICA, "5511999990000", "x", es.SITE_OTP,
                           provider=prov, tracker=_tracker(Tabela(levanta=RuntimeError("AccessDenied"))))
        self.assertTrue(r.success)
        self.assertEqual(len(prov.enviados), 1)

    def test_sem_tracker_envia_do_mesmo_jeito(self):
        prov = Provedor()
        r = es.envia_texto(CLINICA, "5511999990000", "x", es.SITE_OTP, provider=prov, tracker=None)
        self.assertTrue(r.success)
        self.assertEqual(len(prov.enviados), 1)

    def test_origem_desconhecida_nao_envia(self):
        prov = Provedor()
        with self.assertRaises(ValueError):
            es.envia_texto(CLINICA, "5511999990000", "x", "QUALQUER", provider=prov, tracker=None)
        self.assertEqual(prov.enviados, [])


if __name__ == "__main__":
    unittest.main()
