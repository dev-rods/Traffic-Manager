# -*- coding: utf-8 -*-
"""A rajada vira um turno só, e nenhuma mensagem se perde no caminho.

Quem escreve no WhatsApp manda "oi", "queria agendar", "pra semana que vem" em
três balões. O bot respondia cada um - e pior que a repetição: o roteador
classificava cada pedaço isolado, então "queria agendar" ia consultar a agenda
sem saber que a data vinha na mensagem seguinte.

As corridas aqui são o risco real. Uma mensagem que chega no instante da
drenagem não abriu janela nenhuma (o balde existia), então ninguém foi agendado
para buscá-la: perder a condição de versão é perder a mensagem para sempre.
"""
import unittest
from decimal import Decimal
from unittest import mock

from src.services.agregador_de_mensagens import (
    JANELA_PADRAO_SEGUNDOS,
    chegou_mensagem_nova,
    drena,
    enfileira,
    junta_conteudo,
)

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"


class FalhaDeCondicao(Exception):
    pass


class TabelaFalsa:
    """DynamoDB o bastante para exercitar update/get/delete condicional."""

    def __init__(self):
        self.itens = {}
        self.antes_do_delete = None  # gancho para simular corrida

        class _Excs:
            ConditionalCheckFailedException = FalhaDeCondicao

        class _Client:
            exceptions = _Excs()

        class _Meta:
            client = _Client()

        self.meta = _Meta()

    def _k(self, key):
        return (key["pk"], key["sk"])

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues,
                    ExpressionAttributeNames=None, ReturnValues=None):
        item = self.itens.setdefault(self._k(Key), dict(Key))
        item["mensagens"] = (item.get("mensagens") or []) + ExpressionAttributeValues[":nova"]
        # Honra a expressao de verdade em vez de assumir o comportamento: com
        # `setdefault` fixo aqui, trocar if_not_exists por atribuicao direta no
        # codigo de producao nao quebrava teste nenhum.
        if "if_not_exists(processar_em" in UpdateExpression:
            item.setdefault("processar_em", ExpressionAttributeValues[":quando"])
        else:
            item["processar_em"] = ExpressionAttributeValues[":quando"]
        item["ttl"] = ExpressionAttributeValues[":ttl"]
        item["versao"] = Decimal(int(item.get("versao") or 0) + 1)
        return {"Attributes": dict(item)}

    def get_item(self, Key):
        item = self.itens.get(self._k(Key))
        return {"Item": dict(item)} if item else {}

    def delete_item(self, Key, ConditionExpression=None, ExpressionAttributeValues=None):
        if self.antes_do_delete:
            gancho, self.antes_do_delete = self.antes_do_delete, None
            gancho()
        item = self.itens.get(self._k(Key))
        if ExpressionAttributeValues and item:
            if int(item.get("versao") or 0) != int(ExpressionAttributeValues[":v"]):
                raise FalhaDeCondicao("versao mudou")
        self.itens.pop(self._k(Key), None)


def msg(texto, **extra):
    d = {"content": texto, "message_id": texto, "button_id": "", "recebida_em": 0}
    d.update(extra)
    return d


class TestQuemAbreAJanela(unittest.TestCase):
    def setUp(self):
        self.t = TabelaFalsa()

    def test_a_primeira_mensagem_abre_e_as_seguintes_nao(self):
        """Só a primeira agenda o processamento. Se todas agendassem, voltaria a
        ser uma resposta por mensagem - o defeito original."""
        _, _, primeira = enfileira(self.t, CLINIC, PHONE, msg("oi"), 68)
        _, _, segunda = enfileira(self.t, CLINIC, PHONE, msg("queria agendar"), 68)
        _, _, terceira = enfileira(self.t, CLINIC, PHONE, msg("pra sexta"), 68)

        self.assertTrue(primeira)
        self.assertFalse(segunda)
        self.assertFalse(terceira)

    def test_a_janela_nao_reinicia(self):
        """Fixa, não deslizante: quem manda 10 mensagens não empurra o relógio.

        Com reinício, a mediana real de 38s entre mensagens encadearia a espera -
        simulado no histórico, dava pior caso de 140s.

        O relógio é controlado porque duas chamadas seguidas caem no mesmo
        segundo, e aí o prazo coincide mesmo com a janela deslizante: o teste
        passaria sem provar nada.
        """
        with mock.patch("src.services.agregador_de_mensagens.time.time") as agora:
            agora.return_value = 1000
            _, primeiro_prazo, _ = enfileira(self.t, CLINIC, PHONE, msg("oi"), 68)
            agora.return_value = 1030  # 30s depois, ainda dentro da janela
            _, segundo_prazo, _ = enfileira(self.t, CLINIC, PHONE, msg("de novo"), 68)

        self.assertEqual(primeiro_prazo, 1068)
        self.assertEqual(segundo_prazo, 1068, "a janela deslizou")

    def test_a_versao_sobe_a_cada_mensagem(self):
        v1, _, _ = enfileira(self.t, CLINIC, PHONE, msg("a"), 68)
        v2, _, _ = enfileira(self.t, CLINIC, PHONE, msg("b"), 68)

        self.assertEqual((v1, v2), (1, 2))

    def test_conversas_diferentes_nao_se_misturam(self):
        enfileira(self.t, CLINIC, PHONE, msg("da ana"), 68)
        _, _, primeira_da_bia = enfileira(self.t, CLINIC, "5511888880000", msg("da bia"), 68)

        self.assertTrue(primeira_da_bia)
        recebidas, _ = drena(self.t, CLINIC, PHONE)
        self.assertEqual([m["content"] for m in recebidas], ["da ana"])


class TestDrenagem(unittest.TestCase):
    def setUp(self):
        self.t = TabelaFalsa()

    def test_devolve_tudo_na_ordem_e_esvazia(self):
        for texto in ("oi", "queria agendar", "pra sexta"):
            enfileira(self.t, CLINIC, PHONE, msg(texto), 68)

        recebidas, versao = drena(self.t, CLINIC, PHONE)

        self.assertEqual([m["content"] for m in recebidas],
                         ["oi", "queria agendar", "pra sexta"])
        self.assertEqual(versao, 3)
        self.assertEqual(drena(self.t, CLINIC, PHONE), ([], 0))

    def test_balde_vazio(self):
        self.assertEqual(drena(self.t, CLINIC, PHONE), ([], 0))

    def test_mensagem_que_chega_durante_a_drenagem_nao_se_perde(self):
        """A corrida que custaria uma mensagem para sempre.

        Ela não abriu janela (o balde existia), então não há execução agendada
        para buscá-la. Sem a condição de versão, o delete levaria ela junto."""
        enfileira(self.t, CLINIC, PHONE, msg("oi"), 68)
        self.t.antes_do_delete = lambda: enfileira(
            self.t, CLINIC, PHONE, msg("esqueci de dizer"), 68)

        recebidas, _ = drena(self.t, CLINIC, PHONE)

        self.assertEqual([m["content"] for m in recebidas], ["oi", "esqueci de dizer"])

    def test_decimal_do_dynamo_vira_int(self):
        enfileira(self.t, CLINIC, PHONE, msg("oi", recebida_em=Decimal(7)), 68)

        recebidas, _ = drena(self.t, CLINIC, PHONE)

        self.assertIsInstance(recebidas[0]["recebida_em"], int)


class TestMensagemNovaDepois(unittest.TestCase):
    def setUp(self):
        self.t = TabelaFalsa()

    def test_balde_vazio_significa_ninguem_escreveu(self):
        enfileira(self.t, CLINIC, PHONE, msg("oi"), 68)
        drena(self.t, CLINIC, PHONE)

        self.assertFalse(chegou_mensagem_nova(self.t, CLINIC, PHONE))

    def test_escreveu_durante_o_processamento(self):
        enfileira(self.t, CLINIC, PHONE, msg("oi"), 68)
        drena(self.t, CLINIC, PHONE)
        enfileira(self.t, CLINIC, PHONE, msg("na verdade..."), 68)

        self.assertTrue(chegou_mensagem_nova(self.t, CLINIC, PHONE))


class TestJuntaConteudo(unittest.TestCase):
    def test_uma_linha_por_balao_na_ordem(self):
        juntado = junta_conteudo([msg("oi"), msg("queria agendar"), msg("pra sexta")])

        self.assertEqual(juntado, "oi\nqueria agendar\npra sexta")

    def test_mensagem_sem_texto_nao_vira_linha_em_branco(self):
        """Áudio e imagem chegam sem conteúdo."""
        self.assertEqual(junta_conteudo([msg("oi"), msg(""), msg("  "), msg("tchau")]),
                         "oi\ntchau")

    def test_lista_vazia(self):
        self.assertEqual(junta_conteudo([]), "")
        self.assertEqual(junta_conteudo(None), "")


class TestPadrao(unittest.TestCase):
    def test_a_janela_padrao_e_a_medida(self):
        """68s: junta 49% dos turnos nas conversas reais e fica no joelho da
        curva. Mudar isso é decisão de produto, não detalhe de implementação."""
        self.assertEqual(JANELA_PADRAO_SEGUNDOS, 68)


if __name__ == "__main__":
    unittest.main()
