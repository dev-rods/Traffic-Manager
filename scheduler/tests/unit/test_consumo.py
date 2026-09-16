# -*- coding: utf-8 -*-
"""O consumo de cada chamada fica no log.

Quando a conta ficou sem saldo em 14/09/2026, a pergunta "o que consumiu os
créditos?" não teve resposta: os logs diziam que uma chamada aconteceu, nunca o
que ela custou. A resposta virou estimativa por contagem de caracteres — e a API
devolve o número exato em `usage`, que era descartado.

As quatro contagens ficam separadas porque são cobradas diferente: leitura de
cache custa ~0,1x, escrita ~1,25x, e somá-las daria um número sem significado.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.consumo import (
    CAMPOS,
    PRECOS,
    custo_em_dolar,
    do_retorno,
    registra_chamada,
    registra_total,
    soma,
)

RESPOSTA = {
    "content": [{"type": "text", "text": "oi"}],
    "usage": {
        "input_tokens": 1200,
        "output_tokens": 300,
        "cache_read_input_tokens": 6000,
        "cache_creation_input_tokens": 0,
    },
}


class TestLeituraDoUsage(unittest.TestCase):
    def test_le_os_quatro_campos(self):
        uso = do_retorno(RESPOSTA)
        self.assertEqual(uso["input_tokens"], 1200)
        self.assertEqual(uso["output_tokens"], 300)
        self.assertEqual(uso["cache_read_input_tokens"], 6000)
        self.assertEqual(uso["cache_creation_input_tokens"], 0)

    def test_campo_de_cache_ausente_vira_zero_e_nao_none(self):
        """A API só manda os campos de cache quando há cache; quem soma não
        deveria precisar saber disso."""
        uso = do_retorno({"usage": {"input_tokens": 10, "output_tokens": 5}})
        self.assertEqual(uso["cache_read_input_tokens"], 0)
        self.assertEqual(uso["cache_creation_input_tokens"], 0)

    def test_resposta_sem_usage_nao_quebra(self):
        for vazio in ({}, None, {"content": []}):
            with self.subTest(resposta=vazio):
                self.assertEqual(do_retorno(vazio), {c: 0 for c in CAMPOS})


class TestSoma(unittest.TestCase):
    def test_acumula_por_campo(self):
        total = soma({}, do_retorno(RESPOSTA))
        total = soma(total, do_retorno(RESPOSTA))
        self.assertEqual(total["input_tokens"], 2400)
        self.assertEqual(total["cache_read_input_tokens"], 12000)

    def test_comeca_do_zero(self):
        self.assertEqual(soma({}, {})["output_tokens"], 0)


class TestCusto(unittest.TestCase):
    def test_usa_os_multiplicadores_de_cache(self):
        """Leitura a 0,1x e escrita a 1,25x - é o que torna o cache vantajoso."""
        uso = {"input_tokens": 0, "output_tokens": 0,
               "cache_read_input_tokens": 1_000_000,
               "cache_creation_input_tokens": 0}
        entrada, _ = PRECOS["claude-sonnet-5"]
        self.assertAlmostEqual(custo_em_dolar(uso, "claude-sonnet-5"), entrada * 0.10)

        uso_escrita = dict(uso, cache_read_input_tokens=0,
                           cache_creation_input_tokens=1_000_000)
        self.assertAlmostEqual(
            custo_em_dolar(uso_escrita, "claude-sonnet-5"), entrada * 1.25
        )

    def test_saida_custa_mais_que_entrada(self):
        so_entrada = dict({c: 0 for c in CAMPOS}, input_tokens=1_000_000)
        so_saida = dict({c: 0 for c in CAMPOS}, output_tokens=1_000_000)
        self.assertGreater(
            custo_em_dolar(so_saida, "claude-sonnet-5"),
            custo_em_dolar(so_entrada, "claude-sonnet-5"),
        )

    def test_modelo_fora_da_tabela_nao_chuta_numero(self):
        """Custo errado é pior que custo ausente: ninguém desconfia dele."""
        self.assertIsNone(custo_em_dolar(do_retorno(RESPOSTA), "modelo-que-nao-existe"))


class TestOQueVaiParaOLog(unittest.TestCase):
    def test_a_chamada_loga_os_quatro_campos(self):
        with self.assertLogs("src.services.consumo", level="INFO") as registro:
            uso = registra_chamada(RESPOSTA, "claude-sonnet-5", iteracao=2)
        linha = registro.output[0]
        for esperado in ("iteracao=2", "in=1200", "out=300",
                         "cache_read=6000", "cache_write=0",
                         "modelo=claude-sonnet-5", "usd="):
            with self.subTest(campo=esperado):
                self.assertIn(esperado, linha)
        self.assertEqual(uso["input_tokens"], 1200)

    def test_o_total_identifica_a_conversa(self):
        """A pergunta que se faz depois é 'quanto custou atender esta pessoa'."""
        with self.assertLogs("src.services.consumo", level="INFO") as registro:
            registra_total(do_retorno(RESPOSTA), "claude-sonnet-5", "5511999999999", 3)
        linha = registro.output[0]
        self.assertIn("TOTAL", linha)
        self.assertIn("phone=5511999999999", linha)
        self.assertIn("chamadas=3", linha)

    def test_modelo_desconhecido_loga_tokens_sem_custo(self):
        with self.assertLogs("src.services.consumo", level="INFO") as registro:
            registra_chamada(RESPOSTA, "modelo-novo")
        linha = registro.output[0]
        self.assertIn("in=1200", linha)
        self.assertNotIn("usd=", linha)

    def test_contabilidade_que_falha_nao_derruba_o_atendimento(self):
        """Trocar a resposta da paciente por uma linha de log seria absurdo."""
        class RespostaHostil:
            def get(self, *a, **k):
                raise RuntimeError("corrompida")

        with self.assertLogs("src.services.consumo", level="ERROR"):
            uso = registra_chamada(RespostaHostil(), "claude-sonnet-5")
        self.assertEqual(uso, {c: 0 for c in CAMPOS})


class TestLigadoNoServico(unittest.TestCase):
    def test_toda_resposta_de_200_registra_consumo(self):
        """Sem isto o log volta a dizer só que a chamada aconteceu."""
        import inspect

        from src.services import anthropic_service

        fonte = inspect.getsource(anthropic_service.AnthropicService.create_message)
        self.assertIn("registra_consumo", fonte)


if __name__ == "__main__":
    unittest.main()
