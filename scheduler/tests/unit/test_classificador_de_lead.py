# -*- coding: utf-8 -*-
"""O classificador le a transcricao e devolve classe + motivo curto, ou nada.

Sem chamar o modelo: o cliente e injetado e devolve o que o teste manda.
"""
import unittest
from datetime import datetime, timedelta, timezone

from src.services import classificador_de_lead as c
from src.services import estagio_do_lead as e
from src.services.transcricao import Mensagem

AGORA = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
CLINIC = {"clinic_id": "x", "name": "Clinica Teste", "display_name": "Clinica Teste"}


class AnthropicFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def create_message(self, **kw):
        self.chamadas.append(kw)
        return {"content": [{"type": "text", "text": self.respostas.pop(0)}]}


def conversa(n_lead=3):
    ms = [Mensagem("NOS", AGORA - timedelta(days=10), "Ola! Como posso ajudar?")]
    for i in range(n_lead):
        ms.append(Mensagem("LEAD", AGORA - timedelta(days=9, hours=-i), "msg {}".format(i)))
    return ms


class TestInterpreta(unittest.TestCase):
    def test_json_valido(self):
        v = c.interpreta('{"classe": "NAO_E_LEAD", "motivo": "fornecedor de insumos"}', {"LEAD", "NAO_E_LEAD"})
        self.assertEqual(v, c.Veredito("NAO_E_LEAD", "fornecedor de insumos"))

    def test_json_dentro_de_texto(self):
        v = c.interpreta('Claro: {"classe":"LEAD","motivo":"quer agendar"} fim', {"LEAD", "NAO_E_LEAD"})
        self.assertEqual(v.classe, "LEAD")

    def test_classe_fora_do_enum_descarta(self):
        self.assertIsNone(c.interpreta('{"classe": "TALVEZ", "motivo": "x"}', {"LEAD", "NAO_E_LEAD"}))

    def test_nao_json_descarta(self):
        self.assertIsNone(c.interpreta("nao sei", {"LEAD"}))
        self.assertIsNone(c.interpreta("", {"LEAD"}))
        self.assertIsNone(c.interpreta("{}", {"LEAD"}))

    def test_motivo_truncado_e_sem_quebra(self):
        v = c.interpreta('{"classe": "LEAD", "motivo": "' + "a\\nb " * 80 + '"}', {"LEAD"})
        self.assertLessEqual(len(v.motivo), 120)
        self.assertNotIn("\n", v.motivo)

    def test_motivo_ausente_vira_vazio(self):
        self.assertEqual(c.interpreta('{"classe": "LEAD"}', {"LEAD"}).motivo, "")


class TestTriagem(unittest.TestCase):
    def test_lead_de_site_nunca_passa(self):
        lead = {"source": "landing-page", "triagem_feita_em": None}
        self.assertFalse(c.precisa_de_triagem(lead, conversa(5)))

    def test_whatsapp_com_poucas_mensagens_espera(self):
        lead = {"source": "whatsapp", "triagem_feita_em": None}
        self.assertFalse(c.precisa_de_triagem(lead, conversa(2)))

    def test_whatsapp_com_tres_mensagens_passa(self):
        lead = {"source": "whatsapp", "triagem_feita_em": None}
        self.assertTrue(c.precisa_de_triagem(lead, conversa(3)))

    def test_ja_triado_nao_repete(self):
        lead = {"source": "whatsapp", "triagem_feita_em": AGORA}
        self.assertFalse(c.precisa_de_triagem(lead, conversa(5)))

    def test_chama_o_modelo_e_devolve_veredito(self):
        falso = AnthropicFalso(['{"classe":"NAO_E_LEAD","motivo":"proposta comercial"}'])
        v = c.Classificador(falso).triagem(conversa(), CLINIC)
        self.assertEqual(v.classe, "NAO_E_LEAD")
        chamada = falso.chamadas[0]
        self.assertEqual(chamada["model"], c.MODELO_DO_CLASSIFICADOR)
        self.assertEqual(chamada["temperature"], 0)
        self.assertIn("Clinica Teste", chamada["system"])
        self.assertIn("CONTATO: msg 0", chamada["messages"][0]["content"])


class TestDesfecho(unittest.TestCase):
    def test_so_para_sumiu_ou_iniciada_parados(self):
        lead = {"desfecho_tentado_em": None}
        self.assertTrue(c.precisa_de_desfecho(lead, e.Decisao(e.SUMIU, e.REGRA), conversa(), AGORA, 7))
        self.assertFalse(c.precisa_de_desfecho(lead, e.Decisao(e.EM_ANDAMENTO, e.REGRA), conversa(), AGORA, 7))
        self.assertFalse(c.precisa_de_desfecho(lead, e.Decisao(e.AGENDOU, e.REGRA), conversa(), AGORA, 7))

    def test_exige_que_o_lead_tenha_falado(self):
        lead = {"desfecho_tentado_em": None}
        so_nos = [Mensagem("NOS", AGORA - timedelta(days=10), "Oi")]
        self.assertFalse(c.precisa_de_desfecho(lead, e.Decisao(e.INICIADA_SEM_RESPOSTA, e.REGRA), so_nos, AGORA, 7))

    def test_parado_ha_menos_que_n_dias_espera(self):
        lead = {"desfecho_tentado_em": None}
        self.assertFalse(c.precisa_de_desfecho(lead, e.Decisao(e.SUMIU, e.REGRA), conversa(), AGORA, 30))

    def test_ja_tentado_depois_da_ultima_mensagem_nao_repete(self):
        lead = {"desfecho_tentado_em": AGORA - timedelta(days=1)}
        self.assertFalse(c.precisa_de_desfecho(lead, e.Decisao(e.SUMIU, e.REGRA), conversa(), AGORA, 7))

    def test_tentado_antes_de_mensagem_nova_repete(self):
        lead = {"desfecho_tentado_em": AGORA - timedelta(days=30)}
        self.assertTrue(c.precisa_de_desfecho(lead, e.Decisao(e.SUMIU, e.REGRA), conversa(), AGORA, 7))

    def test_ainda_aberto_e_veredito_valido(self):
        falso = AnthropicFalso(['{"classe":"AINDA_ABERTO","motivo":"sem decisao"}'])
        self.assertEqual(c.Classificador(falso).desfecho(conversa(), CLINIC).classe, "AINDA_ABERTO")


class TestTeto(unittest.TestCase):
    def test_estoura_no_limite(self):
        falso = AnthropicFalso(['{"classe":"LEAD","motivo":"x"}'] * 3)
        cl = c.Classificador(falso, max_chamadas=2)
        cl.triagem(conversa(), CLINIC)
        cl.triagem(conversa(), CLINIC)
        with self.assertRaises(c.TetoAtingido):
            cl.triagem(conversa(), CLINIC)
        self.assertEqual(cl.chamadas, 2)

    def test_resposta_invalida_devolve_none_e_conta(self):
        cl = c.Classificador(AnthropicFalso(["???"]))
        self.assertIsNone(cl.triagem(conversa(), CLINIC))
        self.assertEqual(cl.chamadas, 1)

    def test_erro_da_api_devolve_none_e_conta(self):
        class Quebrado:
            def create_message(self, **kw):
                raise RuntimeError("429")
        cl = c.Classificador(Quebrado())
        self.assertIsNone(cl.desfecho(conversa(), CLINIC))
        self.assertEqual(cl.chamadas, 1)


if __name__ == "__main__":
    unittest.main()
