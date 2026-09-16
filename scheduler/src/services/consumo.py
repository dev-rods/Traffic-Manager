# -*- coding: utf-8 -*-
"""Quantos tokens cada resposta custou.

Em 14/09/2026 a conta da Anthropic ficou sem saldo e o bot parou. A pergunta
"o que consumiu os créditos?" não teve resposta: os logs registravam que uma
chamada aconteceu, nunca o que ela custou. A investigação virou estimativa a
partir de contagem de caracteres, quando a API devolve o número exato em toda
resposta e nós o jogávamos fora.

Agora cada chamada registra o seu `usage`, e cada mensagem atendida registra o
total. Com isso, "qual conversa gastou mais ontem" é uma consulta no CloudWatch
Insights, não uma tarde de arqueologia.

As quatro contagens são cobradas diferente, e é por isso que as quatro
aparecem separadas no log - somá-las daria um número sem significado:

  input_tokens                  preço cheio
  cache_read_input_tokens       ~0,1x  (o prefixo de prompt+tools reaproveitado)
  cache_creation_input_tokens   ~1,25x (a primeira chamada de cada janela)
  output_tokens                 preço de saída, ~5x o de entrada
"""
import logging

logger = logging.getLogger(__name__)

# Preço por milhão de tokens, conferido em 14/09/2026. Modelo fora desta tabela
# tem os tokens registrados e o custo omitido - número errado é pior que número
# ausente, porque ninguém desconfia dele.
PRECOS = {
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
MULTIPLICADOR_DE_LEITURA = 0.10
MULTIPLICADOR_DE_ESCRITA = 1.25

CAMPOS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def do_retorno(resposta) -> dict:
    """O `usage` da resposta, com os quatro campos sempre presentes e inteiros.

    A API nem sempre manda os campos de cache (só aparecem quando há cache), e
    ausência aqui vira `0`, não `None`: quem soma o total não deve precisar
    saber disso.
    """
    bruto = (resposta or {}).get("usage") or {}
    return {campo: int(bruto.get(campo) or 0) for campo in CAMPOS}


def soma(total: dict, parcela: dict) -> dict:
    """Acumula o consumo de uma chamada no total da mensagem."""
    return {campo: int(total.get(campo, 0)) + int(parcela.get(campo, 0)) for campo in CAMPOS}


def custo_em_dolar(uso: dict, modelo: str):
    """O custo estimado deste consumo, ou None se o modelo não está na tabela."""
    precos = PRECOS.get(modelo)
    if not precos:
        return None
    entrada, saida = precos
    return (
        uso["input_tokens"] * entrada
        + uso["cache_read_input_tokens"] * entrada * MULTIPLICADOR_DE_LEITURA
        + uso["cache_creation_input_tokens"] * entrada * MULTIPLICADOR_DE_ESCRITA
        + uso["output_tokens"] * saida
    ) / 1_000_000


def _linha(uso: dict, modelo: str) -> str:
    """Campos em `chave=valor` para o Insights separar sem regex frágil."""
    partes = [
        f"in={uso['input_tokens']}",
        f"out={uso['output_tokens']}",
        f"cache_read={uso['cache_read_input_tokens']}",
        f"cache_write={uso['cache_creation_input_tokens']}",
        f"modelo={modelo}",
    ]
    custo = custo_em_dolar(uso, modelo)
    if custo is not None:
        partes.append(f"usd={custo:.6f}")
    return " ".join(partes)


def registra_chamada(resposta, modelo: str, iteracao=None) -> dict:
    """Loga o consumo de UMA chamada ao modelo e devolve o `usage` lido.

    Nunca levanta: uma falha ao contabilizar não pode derrubar o atendimento -
    seria trocar a resposta da paciente por uma linha de log.
    """
    try:
        uso = do_retorno(resposta)
        marca = f"iteracao={iteracao} " if iteracao is not None else ""
        logger.info(f"[Consumo] {marca}{_linha(uso, modelo)}")
        return uso
    except Exception as e:
        logger.error(f"[Consumo] Falha ao registrar o consumo da chamada: {e}")
        return {campo: 0 for campo in CAMPOS}


def registra_total(uso: dict, modelo: str, phone: str, chamadas: int) -> None:
    """Loga o consumo somado de uma mensagem atendida.

    O total existe separado das chamadas porque a pergunta que se faz depois é
    "quanto custou ATENDER esta pessoa", e uma mensagem são 2 a 4 chamadas.
    """
    try:
        logger.info(
            f"[Consumo] TOTAL phone={phone} chamadas={chamadas} {_linha(uso, modelo)}"
        )
    except Exception as e:
        logger.error(f"[Consumo] Falha ao registrar o total de {phone}: {e}")
