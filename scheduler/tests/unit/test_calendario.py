# -*- coding: utf-8 -*-
"""O que a pessoa quis dizer com "amanhã", e o que o agente pode citar.

Em 04/09/2026 uma paciente pediu "gostaria de agendar para amanhã" e o bot
respondeu que não conseguia calcular amanhã automaticamente. Não havia regra
mandando recusar: nada informava a data ao modelo, e as regras de proveniência
transformaram a ausência de dado em recusa.

Data fixa em todos os testes: `date(2026, 9, 4)`, uma SEXTA-FEIRA. Usar
`hoje_brt()` aqui faria a suíte mudar de resultado conforme o dia em que roda.
"""
import unittest
from datetime import date

from src.services.calendario import (
    bloco_de_contexto,
    hoje_brt,
    referencias,
    rotulo,
)

SEXTA = date(2026, 9, 4)


def datas(texto, hoje=SEXTA):
    """Só as datas, achatadas - a maioria dos testes não olha a expressão."""
    return [d for _, ds in referencias(texto, hoje) for d in ds]


class TestReferenciasSimples(unittest.TestCase):
    def test_a_frase_que_falhou_em_producao(self):
        self.assertEqual(datas("Não, gostaria de agendar para amanhã"),
                         [date(2026, 9, 5)])

    def test_hoje(self):
        self.assertEqual(datas("tem vaga hoje?"), [SEXTA])

    def test_depois_de_amanha_nao_vira_amanha(self):
        """"depois de amanhã" contém "amanhã": a ordem do casamento importa."""
        self.assertEqual(datas("pode ser depois de amanhã"), [date(2026, 9, 6)])

    def test_sem_acento(self):
        self.assertEqual(datas("queria amanha"), [date(2026, 9, 5)])

    def test_mensagem_sem_referencia_nao_devolve_nada(self):
        for frase in ["quanto custa?", "buço e axilas", "oi, tudo bem?", "", None]:
            with self.subTest(frase=frase):
                self.assertEqual(referencias(frase, SEXTA), [])


class TestDiaDaSemana(unittest.TestCase):
    def test_proxima_ocorrencia(self):
        # 04/09/2026 e sexta. A proxima segunda e 07/09.
        self.assertEqual(datas("pode ser segunda?"), [date(2026, 9, 7)])
        self.assertEqual(datas("quarta que vem"), [date(2026, 9, 9)])

    def test_o_mesmo_dia_da_semana_cai_na_semana_seguinte(self):
        """Quem diz "sexta" numa sexta está marcando a próxima, não hoje."""
        self.assertEqual(datas("consegue sexta?"), [date(2026, 9, 11)])

    def test_variantes_de_escrita(self):
        for frase in ["na terça", "terça-feira", "próxima terça", "terca que vem"]:
            with self.subTest(frase=frase):
                self.assertEqual(datas(frase), [date(2026, 9, 8)])

    def test_ordinal_nao_vira_dia_da_semana(self):
        """"segunda sessão" é tratamento, não agenda - e "terça" nunca é ordinal
        sozinha, mas "segunda" é, e foi o caso que quase passou."""
        for frase in ["quando é a segunda sessão?", "na segunda vez doeu menos",
                      "a segunda área"]:
            with self.subTest(frase=frase):
                self.assertEqual(datas(frase), [])


class TestPeriodos(unittest.TestCase):
    def test_semana_que_vem_cobre_a_semana_inteira(self):
        d = datas("tem alguma coisa semana que vem?")
        self.assertEqual(len(d), 7)
        self.assertEqual(d[0], date(2026, 9, 7))   # segunda
        self.assertEqual(d[-1], date(2026, 9, 13))  # domingo

    def test_fim_de_semana(self):
        self.assertEqual(datas("dá pra fazer no fim de semana?"),
                         [date(2026, 9, 5), date(2026, 9, 6)])

    def test_daqui_a_n_dias(self):
        self.assertEqual(datas("daqui a 10 dias"), [date(2026, 9, 14)])

    def test_daqui_a_muitos_dias_e_ignorado(self):
        """Numero fora de escala e erro de digitacao, nao pedido."""
        self.assertEqual(datas("daqui a 90 dias"), [])


class TestDiaDoMes(unittest.TestCase):
    def test_dia_ainda_por_vir_no_mes_corrente(self):
        self.assertEqual(datas("pode ser dia 23"), [date(2026, 9, 23)])

    def test_dia_ja_passado_cai_no_mes_seguinte(self):
        self.assertEqual(datas("dia 2 dá?"), [date(2026, 10, 2)])

    def test_dia_que_nao_existe_no_mes_seguinte_pula(self):
        """31 em novembro nao existe; a resposta e dezembro, nao um erro."""
        self.assertEqual(datas("dia 31", date(2026, 11, 5)), [date(2026, 12, 31)])

    def test_data_numerica_nao_e_capturada_aqui(self):
        """`23/09` ja e data explicita - quem resolve e o modelo lendo o texto."""
        self.assertEqual(datas("dia 23/09"), [])


class TestBlocoDeContexto(unittest.TestCase):
    def test_hoje_aparece_mesmo_sem_referencia(self):
        bloco, iso = bloco_de_contexto("quanto custa?", SEXTA)

        self.assertIn("sexta-feira, 04/09/2026", bloco)
        self.assertEqual(iso, ["2026-09-04"])

    def test_traduz_a_expressao_da_pessoa(self):
        bloco, _ = bloco_de_contexto("quero amanhã", SEXTA)

        self.assertIn('"amanhã" = sábado, 05/09/2026', bloco)

    def test_periodo_vira_intervalo(self):
        bloco, _ = bloco_de_contexto("semana que vem", SEXTA)

        self.assertIn("de segunda-feira, 07/09/2026 a domingo, 13/09/2026", bloco)

    def test_as_datas_saem_em_iso_para_o_respaldo(self):
        """Sem isso, "amanhã (05/09) não temos vaga" seria data sem origem e a
        resposta cairia no bloqueio de proveniência."""
        _, iso = bloco_de_contexto("quero amanhã", SEXTA)

        self.assertEqual(iso, ["2026-09-04", "2026-09-05"])

    def test_iso_sem_repeticao_e_ordenado(self):
        _, iso = bloco_de_contexto("hoje ou amanhã, ou hoje mesmo", SEXTA)

        self.assertEqual(iso, sorted(set(iso)))


class TestFusoDaClinica(unittest.TestCase):
    def test_as_23h_de_brasilia_hoje_ainda_e_o_dia_de_brasilia(self):
        """A Lambda roda em UTC. As 23h BRT ja sao 02h UTC do dia seguinte: sem
        o deslocamento, "amanha" pularia dois dias para quem escreve a noite."""
        from datetime import datetime, timezone
        from unittest import mock

        # 05/09 02:00 UTC == 04/09 23:00 em Brasilia.
        agora = datetime(2026, 9, 5, 2, 0, tzinfo=timezone.utc)
        with mock.patch("src.services.calendario.datetime") as dt:
            dt.now.side_effect = lambda tz: agora.astimezone(tz)
            self.assertEqual(hoje_brt(), date(2026, 9, 4))

    def test_rotulo_traz_dia_da_semana_e_data(self):
        self.assertEqual(rotulo(SEXTA), "sexta-feira, 04/09/2026")


if __name__ == "__main__":
    unittest.main()
