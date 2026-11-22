# -*- coding: utf-8 -*-
"""A transcricao vem do MessageEvents, unindo as variantes do numero.

A tabela falsa devolve o que o DynamoDB devolveria para cada pk; o teste confere
a uniao, a ordem, a traducao de direcao para LEAD/NOS e que a condicao de chave
corta os itens STATUS# (o Limit do DynamoDB e aplicado antes de qualquer filtro).
"""
import unittest
from datetime import datetime, timezone

from src.services import transcricao as t

CLINIC = "clinicaessenciaestetica-9668a4"


class TabelaFalsa:
    def __init__(self, por_pk):
        self.por_pk = por_pk
        self.chamadas = []

    def query(self, **kw):
        self.chamadas.append(kw)
        expr = kw["KeyConditionExpression"].get_expression()
        pk = next(v for v in _valores(expr) if str(v).startswith("CLINIC#"))
        prefixo = next((v for v in _valores(expr) if str(v).startswith("MSG")), "")
        itens = sorted((i for i in self.por_pk.get(pk, []) if i["sk"].startswith(prefixo)),
                       key=lambda i: i["sk"], reverse=True)
        return {"Items": itens[: kw.get("Limit", 50)]}


def _valores(expr):
    """Percorre a arvore do boto3 (ConditionExpression) e devolve os valores literais."""
    saida = []
    for v in expr.get("values", []):
        if isinstance(v, dict) and "values" in v:
            saida.extend(_valores(v))
        elif hasattr(v, "get_expression"):
            saida.extend(_valores(v.get_expression()))
        elif hasattr(v, "name"):
            continue
        else:
            saida.append(v)
    return saida


def msg(iso, direction, content, tipo="MSG"):
    return {"sk": "{}#{}#x".format(tipo, iso), "direction": direction, "content": content, "createdAt": iso}


class TestUltimasMensagens(unittest.TestCase):
    def test_une_variantes_e_ordena_cronologicamente(self):
        tabela = TabelaFalsa({
            "CLINIC#{}#PHONE#5547997053940".format(CLINIC): [msg("2026-11-20T10:00:00Z", "OUTBOUND", "Oi")],
            "CLINIC#{}#PHONE#554797053940".format(CLINIC): [msg("2026-11-21T10:00:00Z", "INBOUND", "Quanto custa?")],
        })
        ms = t.ultimas_mensagens(tabela, CLINIC, "5547997053940")
        self.assertEqual([(m.de, m.texto) for m in ms], [("NOS", "Oi"), ("LEAD", "Quanto custa?")])
        self.assertEqual(ms[1].em, datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(len(tabela.chamadas), 2)

    def test_ddd_11_tem_uma_variante_so(self):
        tabela = TabelaFalsa({})
        t.ultimas_mensagens(tabela, CLINIC, "5511970522647")
        self.assertEqual(len(tabela.chamadas), 1)

    def test_status_update_fica_fora_pela_chave(self):
        tabela = TabelaFalsa({"CLINIC#{}#PHONE#5511999990000".format(CLINIC): [
            msg("2026-11-20T10:00:00Z", "OUTBOUND", "Oi"),
            msg("2026-11-20T10:00:05Z", "STATUS_UPDATE", "", tipo="STATUS"),
        ]})
        ms = t.ultimas_mensagens(tabela, CLINIC, "5511999990000")
        self.assertEqual(len(ms), 1)

    def test_respeita_o_limite_no_total(self):
        itens = [msg("2026-11-{:02d}T10:00:00Z".format(d), "INBOUND", str(d)) for d in range(1, 29)]
        tabela = TabelaFalsa({"CLINIC#{}#PHONE#5511999990000".format(CLINIC): itens})
        ms = t.ultimas_mensagens(tabela, CLINIC, "5511999990000", limite=10)
        self.assertEqual(len(ms), 10)
        self.assertEqual(ms[-1].texto, "28")

    def test_sem_eventos_devolve_vazio(self):
        self.assertEqual(t.ultimas_mensagens(TabelaFalsa({}), CLINIC, "5511999990000"), [])

    def test_item_sem_data_valida_e_ignorado(self):
        tabela = TabelaFalsa({"CLINIC#{}#PHONE#5511999990000".format(CLINIC): [
            {"sk": "MSG#x#y", "direction": "INBOUND", "content": "oi", "createdAt": "ontem"},
        ]})
        self.assertEqual(t.ultimas_mensagens(tabela, CLINIC, "5511999990000"), [])

    def test_erro_na_query_nao_derruba(self):
        class Quebrada:
            def query(self, **kw):
                raise RuntimeError("boom")
        self.assertEqual(t.ultimas_mensagens(Quebrada(), CLINIC, "5511999990000"), [])


class TestResumo(unittest.TestCase):
    def test_vazio(self):
        self.assertEqual(t.resumo([]), {"ultima_de": None, "ultima_em": None, "lead_ja_falou": False})

    def test_so_nos(self):
        ms = [t.Mensagem("NOS", datetime(2026, 11, 1, tzinfo=timezone.utc), "Oi")]
        self.assertEqual(t.resumo(ms)["lead_ja_falou"], False)
        self.assertEqual(t.resumo(ms)["ultima_de"], "NOS")

    def test_lead_falou_antes_e_nos_por_ultimo(self):
        ms = [t.Mensagem("LEAD", datetime(2026, 11, 1, tzinfo=timezone.utc), "Oi"),
              t.Mensagem("NOS", datetime(2026, 11, 2, tzinfo=timezone.utc), "Ola")]
        r = t.resumo(ms)
        self.assertEqual((r["ultima_de"], r["lead_ja_falou"]), ("NOS", True))


if __name__ == "__main__":
    unittest.main()
