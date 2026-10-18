# -*- coding: utf-8 -*-
"""Qual desconto vale para um agendamento - a mesma resposta em toda porta.

A conta morava dentro do `ToolExecutor._calcula_desconto`, a tool do agente de
WhatsApp. O site publico de agendamento nao passava por ela: criava o
agendamento so com o desconto personalizado, sem primeira sessao e sem faixas
por quantidade de areas. O mesmo carrinho, da mesma paciente, custava menos
pelo WhatsApp do que pelo site - e ninguem via, porque cada lado olhado sozinho
parecia certo.

Agora a decisao mora aqui e os dois chamam. A ordem e a de sempre:

    1. personalizado (combinado com a paciente) vence tudo, inclusive quando e 0
    2. senao, o MAIOR entre primeira sessao e a faixa de areas (faixa 3 antes
       da 2) - os descontos nao se somam
    3. sem regra ativa na clinica, nenhum desconto

Sem telefone so a faixa de areas pode valer: primeira sessao e personalizado
dependem de quem e a pessoa. E o caso do site antes de o cliente digitar o
celular - o resumo mostra o desconto que ja e certo e o resto aparece depois.

As duas consultas que dependem da pessoa entram por parametro (`e_primeira`,
`personalizado_de`) para o agente continuar passando as que ele importa: os
testes do agente fazem patch delas em `ai_tools`, e a extracao nao pode deixar
esses testes conferindo uma funcao que ninguem mais chama.
"""
import logging
from decimal import Decimal
from typing import Callable, Dict, List, NamedTuple, Optional, Union

from src.services.desconto_personalizado import RAZAO as RAZAO_PERSONALIZADA
from src.services.desconto_personalizado import aplica as aplica_desconto
from src.services.desconto_personalizado import do_paciente as desconto_do_paciente
from src.services.duration_rules import normaliza_pares, servicos_sem_par
from src.services.primeira_visita import e_primeira_visita

logger = logging.getLogger(__name__)

RAZAO_PRIMEIRA_SESSAO = "first_session"
RAZAO_FAIXA_2 = "tier_2"
RAZAO_FAIXA_3 = "tier_3"

Percentual = Union[int, Decimal]

__all__ = [
    "Decisao", "decide", "faixas_de_desconto", "preco_de_tabela", "texto_do_preco", "aplica_desconto",
    "RAZAO_PERSONALIZADA", "RAZAO_PRIMEIRA_SESSAO", "RAZAO_FAIXA_2", "RAZAO_FAIXA_3",
]


class Decisao(NamedTuple):
    pct: Percentual
    razao: Optional[str]
    is_first: bool
    # A clinica nao tem `discount_rules` ativa. O agente responde nesse caso com
    # um formato proprio (com `price_display`, que a proveniencia le), e a
    # extracao nao muda o que o agente devolve.
    sem_politica: bool = False


SEM_POLITICA = Decisao(0, None, False, sem_politica=True)


def decide(
    db,
    clinic_id: str,
    phone: Optional[str],
    qtd_areas: int,
    e_primeira: Optional[Callable[..., bool]] = None,
    personalizado_de: Optional[Callable[..., Optional[Decimal]]] = None,
) -> Decisao:
    """O desconto que vale para `qtd_areas` areas desta pessoa nesta clinica.

    `qtd_areas` e a contagem DEPOIS dos combos: duas areas que viraram um combo
    contam como uma, igual ao agente.

    Sem `e_primeira`/`personalizado_de`, valem `e_primeira_visita` e
    `desconto_do_paciente` deste modulo - resolvidas na chamada, nao na
    definicao, para um patch aqui valer.
    """
    e_primeira = e_primeira or e_primeira_visita
    personalizado_de = personalizado_de or desconto_do_paciente
    if phone:
        personalizado = personalizado_de(db, clinic_id, phone)
        if personalizado is not None:
            return Decisao(personalizado, RAZAO_PERSONALIZADA, False)

    rules_rows = db.execute_query(
        "SELECT * FROM scheduler.discount_rules WHERE clinic_id = %s AND is_active = TRUE",
        (clinic_id,),
    )
    rules = rules_rows[0] if rules_rows else None
    if not rules:
        return SEM_POLITICA

    # A MESMA funcao que marca a estreia na agenda. Eram duas contas separadas
    # para a mesma pergunta, e campo gravado que nasce de contas diferentes
    # diverge em silencio.
    is_first = bool(phone) and e_primeira(db, clinic_id, phone)

    candidatos = []

    first_pct = int(rules.get("first_session_discount_pct") or 0)
    if is_first and first_pct > 0:
        candidatos.append((first_pct, RAZAO_PRIMEIRA_SESSAO))

    t2_min = int(rules.get("tier_2_min_areas") or 0)
    t3_min = int(rules.get("tier_3_min_areas") or 0)
    t2_pct = int(rules.get("tier_2_discount_pct") or 0)
    t3_pct = int(rules.get("tier_3_discount_pct") or 0)

    if _faixa_vale(t3_min, t3_pct) and qtd_areas >= t3_min:
        candidatos.append((t3_pct, RAZAO_FAIXA_3))
    elif _faixa_vale(t2_min, t2_pct) and qtd_areas >= t2_min:
        candidatos.append((t2_pct, RAZAO_FAIXA_2))

    if not candidatos:
        return Decisao(0, None, is_first)

    pct, razao = max(candidatos, key=lambda c: c[0])
    return Decisao(pct, razao, is_first)


def _faixa_vale(minimo: int, pct: int) -> bool:
    return bool(minimo) and pct > 0


def faixas_de_desconto(regras: Optional[Dict]) -> List[Dict]:
    """As faixas por quantidade de areas, como `decide` as aplica, para o site
    anunciar antes de a pessoa escolher.

    `maxAreas` sai da conta de `decide`, nao de `tier_2_max_areas`: `decide`
    testa a faixa 3 primeiro e cai na 2 para qualquer quantidade a partir do
    minimo dela. Com a faixa 3 valendo, a 2 termina um antes do minimo da 3;
    sem ela, a 2 nao tem teto. Anunciar o teto gravado prometeria uma regra
    que a cobranca nao segue.

    Primeira sessao e personalizado ficam de fora porque dependem de quem e
    a pessoa.
    """
    if not regras:
        return []
    t2_min = int(regras.get("tier_2_min_areas") or 0)
    t3_min = int(regras.get("tier_3_min_areas") or 0)
    t2_pct = int(regras.get("tier_2_discount_pct") or 0)
    t3_pct = int(regras.get("tier_3_discount_pct") or 0)

    faixas = []
    t3_vale = _faixa_vale(t3_min, t3_pct)
    if _faixa_vale(t2_min, t2_pct) and not (t3_vale and t3_min <= t2_min):
        faixas.append({"minAreas": t2_min, "maxAreas": t3_min - 1 if t3_vale else None, "pct": t2_pct})
    if t3_vale:
        faixas.append({"minAreas": t3_min, "maxAreas": None, "pct": t3_pct})
    return faixas


def preco_de_tabela(db, service_ids: List[str], service_area_pairs: Optional[List[Dict]],
                    servicos: Optional[List[Dict]] = None) -> Optional[int]:
    """O preco cheio do carrinho, antes de qualquer desconto.

    E a conta que a criacao de agendamento sempre fez (`AppointmentService`,
    bloco de preco automatico), tirada de la para a cotacao do site usar a
    MESMA: o valor que o cliente ve antes de confirmar tem de ser o gravado.

    Com pares, soma o preco da area (ou o do servico, quando a area nao tem
    preco proprio) mais o preco dos servicos que nenhum par cobre (o carrinho
    misto); sem pares, soma o preco dos servicos. `None` quando nao ha preco
    nenhum - "a consultar", nunca R$ 0.

    `servicos` sao as linhas de `scheduler.services` (com `id` e `price_cents`)
    que o chamador ja leu; sem elas, a funcao le.
    """
    pares = normaliza_pares(service_area_pairs)
    total = 0
    if pares:
        values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(pares))
        params: tuple = ()
        for pair in pares:
            params += (pair["service_id"], pair["area_id"])
        rows = db.execute_query(
            f"""SELECT SUM(COALESCE(sa.price_cents, s.price_cents)) as total_price
            FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
            JOIN scheduler.services s ON s.id = pairs.service_id AND s.active = TRUE
            LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
            params,
        )
        total = int(rows[0]["total_price"]) if rows and rows[0]["total_price"] else 0

    ids = servicos_sem_par(service_ids, pares)
    if not ids:
        return total or None
    if servicos is not None:
        por_id = {str(r["id"]): r for r in servicos}
        total += sum(int(por_id[i].get("price_cents") or 0) for i in ids if i in por_id)
        return total or None
    placeholders = ", ".join(["%s"] * len(ids))
    rows = db.execute_query(
        f"SELECT price_cents FROM scheduler.services WHERE id::text IN ({placeholders}) AND active = TRUE",
        tuple(ids),
    )
    total += sum(int(r.get("price_cents") or 0) for r in rows or [])
    return total or None


def _reais(centavos: int) -> str:
    return f"R$ {centavos / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct_legivel(pct: Percentual) -> str:
    """15 -> "15"; 12.50 -> "12,5". Zero a direita nao e informacao."""
    texto = format(Decimal(str(pct)).normalize(), "f")
    return texto.replace(".", ",")


def _rotulo(razao: Optional[str], qtd_areas: int) -> str:
    if razao == RAZAO_PRIMEIRA_SESSAO:
        return "primeira sessão"
    if razao in (RAZAO_FAIXA_2, RAZAO_FAIXA_3):
        return f"{qtd_areas} áreas"
    if razao == RAZAO_PERSONALIZADA:
        return "desconto especial"
    return ""


def texto_do_preco(original: Optional[int], final: Optional[int], pct: Optional[Percentual],
                   razao: Optional[str], qtd_areas: int) -> str:
    """A linha de valor da confirmacao por WhatsApp, a partir do que foi GRAVADO.

    O formato e o que o bot mandava (`~de~ → por (x% off - motivo)`): a clinica
    ja reconhece a mensagem, e a paciente ve o desconto em vez de so um numero.
    """
    if not original:
        return "Consultar"
    if not pct or final is None or final >= original:
        return _reais(final if final is not None else original)
    rotulo = _rotulo(razao, qtd_areas)
    sufixo = f" - {rotulo}" if rotulo else ""
    return f"~{_reais(original)}~ → {_reais(final)} ({_pct_legivel(pct)}% off{sufixo})"
