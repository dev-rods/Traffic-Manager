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
from typing import Optional

logger = logging.getLogger(__name__)

RAZAO = "personalizado"


def do_paciente(db, clinic_id: str, phone: str) -> Optional[int]:
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
        pct = int(valor)
    except (TypeError, ValueError):
        logger.error(f"[DescontoPersonalizado] valor ilegivel para {phone}: {valor!r}")
        return None

    if not 0 <= pct <= 100:
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
        pct = int(str(valor).strip())
    except (TypeError, ValueError):
        return False, None
    if not 0 <= pct <= 100:
        return False, None
    return True, pct
