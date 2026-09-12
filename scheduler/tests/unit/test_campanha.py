# -*- coding: utf-8 -*-
"""A campanha de reagendamento: abre, vence, e falha fechada.

O prazo é o que faz a trava LEADS_ONLY voltar sozinha. Sem TTL na tabela de
sessões, uma campanha que não vencesse deixaria o bot atendendo aquela paciente
para sempre - por isso quase todo teste aqui mira o vencimento.
"""
import unittest

from src.services.campanha import (
    DURACAO_PADRAO_DIAS,
    MAX_DATAS,
    MODO_REAGENDAMENTO,
    abre,
    datas_da_campanha,
    esta_viva,
)

AGORA = 1_760_000_000
DATAS = ["2026-10-07", "2026-10-14", "2026-10-21"]


class TestAbre(unittest.TestCase):
    def test_prazo_de_sete_dias(self):
        """Decisão do André em 09/09/2026."""
        c = abre(DATAS, agora=AGORA)
        self.assertEqual(c["expira_em"], AGORA + 7 * 86400)
        self.assertEqual(DURACAO_PADRAO_DIAS, 7)

    def test_marca_o_modo(self):
        self.assertEqual(abre(DATAS, agora=AGORA)["modo"], MODO_REAGENDAMENTO)

    def test_guarda_as_datas(self):
        self.assertEqual(abre(DATAS, agora=AGORA)["datas"], DATAS)

    def test_corta_no_maximo_de_datas(self):
        c = abre(DATAS + ["2026-10-28", "2026-11-04"], agora=AGORA)
        self.assertEqual(len(c["datas"]), MAX_DATAS)

    def test_prazo_parametrizavel(self):
        self.assertEqual(abre(DATAS, dias=14, agora=AGORA)["expira_em"],
                         AGORA + 14 * 86400)

    def test_sem_data_nao_abre(self):
        """Campanha sem data anunciada não tem o que oferecer."""
        with self.assertRaises(ValueError):
            abre([], agora=AGORA)


class TestEstaViva(unittest.TestCase):
    def test_recem_aberta(self):
        self.assertTrue(esta_viva({"campanha": abre(DATAS, agora=AGORA)}, agora=AGORA))

    def test_ultimo_instante_ainda_vale(self):
        s = {"campanha": abre(DATAS, agora=AGORA)}
        self.assertTrue(esta_viva(s, agora=AGORA + 7 * 86400 - 1))

    def test_no_vencimento_ja_morreu(self):
        """`>` e não `>=`: no segundo exato do prazo a campanha acabou."""
        s = {"campanha": abre(DATAS, agora=AGORA)}
        self.assertFalse(esta_viva(s, agora=AGORA + 7 * 86400))

    def test_oitavo_dia_nao_responde(self):
        s = {"campanha": abre(DATAS, agora=AGORA)}
        self.assertFalse(esta_viva(s, agora=AGORA + 8 * 86400))

    def test_sessao_sem_campanha(self):
        self.assertFalse(esta_viva({"bot_enabled": True}, agora=AGORA))

    def test_sessao_vazia_ou_ausente(self):
        for s in ({}, None):
            with self.subTest(s=s):
                self.assertFalse(esta_viva(s, agora=AGORA))

    def test_campanha_malformada_falha_fechada(self):
        """Qualquer lixo no campo cala o bot em vez de soltá-lo."""
        for ruim in ("REAGENDAMENTO", [], 1, {"modo": "X"},
                     {"expira_em": None}, {"expira_em": "amanha"}):
            with self.subTest(ruim=ruim):
                self.assertFalse(esta_viva({"campanha": ruim}, agora=AGORA))

    def test_expira_em_string_numerica_vale(self):
        """O DynamoDB devolve número como Decimal/str conforme o caminho."""
        s = {"campanha": {"modo": MODO_REAGENDAMENTO,
                          "expira_em": str(AGORA + 100), "datas": DATAS}}
        self.assertTrue(esta_viva(s, agora=AGORA))


class TestDatas(unittest.TestCase):
    def test_campanha_viva_devolve_as_datas(self):
        s = {"campanha": abre(DATAS, agora=AGORA)}
        self.assertEqual(datas_da_campanha(s, agora=AGORA), DATAS)

    def test_campanha_morta_nao_vaza_data_velha(self):
        """Data de campanha vencida é data de um mês que já passou."""
        s = {"campanha": abre(DATAS, agora=AGORA)}
        self.assertEqual(datas_da_campanha(s, agora=AGORA + 8 * 86400), [])

    def test_sem_campanha(self):
        self.assertEqual(datas_da_campanha({}, agora=AGORA), [])

    def test_datas_corrompidas_nao_quebram(self):
        s = {"campanha": {"modo": MODO_REAGENDAMENTO,
                          "expira_em": AGORA + 100, "datas": "07/10"}}
        self.assertEqual(datas_da_campanha(s, agora=AGORA), [])


if __name__ == "__main__":
    unittest.main()
