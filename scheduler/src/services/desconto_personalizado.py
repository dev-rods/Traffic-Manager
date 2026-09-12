# -*- coding: utf-8 -*-
"""O desconto fixo de uma paciente, quando ela tem um.

A clinica combina um percentual com alguem - funcionaria, indicacao, acordo
antigo - e esse percentual passa a valer em todo agendamento dela, no lugar da
politica normal (primeira sessao, faixas de areas).

NULO e o normal, e a distincao entre NULO e ZERO e o centro do desenho:

    NULO  -> nao ha combinado; vale a politica da clinica
    ZERO  -> ha um combinado, e ele e "nenhum desconto"

Se o padrao fosse zero, as duas situacoes ficariam indistinguiveis, e quem
olhasse a tabela nao teria como saber qual e qual. Por isso a funcao devolve
`None` para ausencia e um inteiro para presenca - inclusive o 0.

Fica num modulo proprio porque a pergunta e feita em dois lugares - a tool do
bot e a criacao pelo painel - e resposta duplicada diverge em silencio.
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Union

logger = logging.getLogger(__name__)

RAZAO = "personalizado"

# Duas casas decimais: 12,5% e 33,33% sao combinados reais, e o inteiro os
# arredondava em silencio. O percentual e gravado no agendamento tambem, entao
# a coluna de la e NUMERIC(5,2) pelo mesmo motivo.
CASAS = 2
PASSO = Decimal("0.01")


def aplica(total_cents: int, pct: Union[int, float, Decimal, None]) -> int:
    """O preco em centavos depois do desconto.

    Existe porque o calculo estava repetido em cinco lugares do backend, cada um
    com sua divisao inteira. Com percentual fracionario isso viraria cinco
    arredondamentos possivelmente diferentes para o mesmo agendamento - e a
    divergencia apareceria como um centavo a mais num relatorio e a menos em
    outro, sem ninguem saber qual esta certo.

    TRUNCA, nao arredonda, para manter o que ja acontecia com percentual
    inteiro: `total * (100 - pct) // 100`. Trocar para arredondamento mudaria
    precos de agendamentos antigos ao recalcula-los.

    Decimal e nao float porque 0.1 nao existe exato em binario, e preco errado
    por um centavo e o tipo de defeito que ninguem consegue explicar depois.
    """
    if not total_cents:
        return total_cents or 0
    if pct is None:
        return int(total_cents)
    try:
        p = Decimal(str(pct))
    except (InvalidOperation, ValueError):
        logger.error(f"[Desconto] percentual ilegivel: {pct!r}; aplicando zero")
        return int(total_cents)
    restante = (Decimal(100) - p) / Decimal(100)
    return int(Decimal(total_cents) * restante)


def do_paciente(db, clinic_id: str, phone: str) -> Optional[Decimal]:
    """O percentual combinado com esta paciente, ou None se nao ha.

    Falha fechada em None: sem resposta do banco, vale a politica normal. O
    contrario - assumir um desconto que ninguem conferiu - daria dinheiro da
    clinica por causa de uma consulta que falhou.
    """
    try:
        linhas = db.execute_query(
            "SELECT custom_discount_pct FROM scheduler.patients "
            "WHERE clinic_id = %s AND phone = %s AND deleted_at IS NULL LIMIT 1",
            (clinic_id, phone),
        )
    except Exception as e:
        logger.error(f"[DescontoPersonalizado] falha ao ler {phone}: {e}")
        return None

    if not linhas:
        return None

    valor = linhas[0].get("custom_discount_pct")
    if valor is None:
        return None

    try:
        pct = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        logger.error(f"[DescontoPersonalizado] valor ilegivel para {phone}: {valor!r}")
        return None

    if not Decimal(0) <= pct <= Decimal(100):
        # O CHECK do banco impede, mas dado antigo ou escrita manual nao passam
        # por ele. Percentual fora da faixa viraria preco negativo.
        logger.error(f"[DescontoPersonalizado] {phone} fora da faixa: {pct}")
        return None

    return pct


def normaliza_entrada(valor):
    """Converte o que chega da API no que vai ao banco.

    Devolve (ok, valor). Vazio, nulo e string em branco viram None - e o campo
    volta a ser "sem combinado", que e como a clinica desfaz um desconto.
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return True, None
    try:
        # Virgula tambem: e como se digita percentual em portugues, e recusar
        # "12,5" obrigaria a recepcao a adivinhar o formato.
        pct = Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return False, None
    if not Decimal(0) <= pct <= Decimal(100):
        return False, None
    if pct != pct.quantize(PASSO):
        # Mais de duas casas nao cabe na coluna e seria truncado em silencio.
        return False, None
    return True, pct.quantize(PASSO)
