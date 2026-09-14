# -*- coding: utf-8 -*-
"""Área cujo nome não diz sozinho o que a paciente quer.

Duas regiões têm nome popular que cobre mais de uma área vendida, e a paciente
costuma usar o nome popular achando que está sendo específica:

  "barriga" / "abdômen"  -> pode ser a região inteira OU só a linha alba, a
                            faixa vertical no meio da barriga.
  "virilha"              -> pode ser só a virilha OU a virilha com a região do
                            ânus (perianal). Vale inclusive para "virilha
                            completa": muita gente chama de completa a que
                            inclui o períneo.

Errar aqui não aparece na conversa - aparece na sala, com a sessão marcada com
duração e preço de outra área. Por isso a desambiguação não é sugestão de
prompt: é trava de tool, no mesmo lugar e pelo mesmo motivo que
[confirmacao_de_areas] - o modelo já provou que instrução ele contorna.

Regra, decidida pelo André em 13/09/2026:

  Área com nome ambíguo só entra em horário, preço ou agendamento depois que o
  termo alternativo (linha alba / ânus) apareceu na conversa e a paciente falou
  depois disso.

Como em confirmacao_de_areas, não se julga se ela disse "sim" ou "não" - o que
se garante é que a pergunta foi feita antes de marcar.
"""
import re
from typing import Dict, Iterable, List, Sequence

from src.services.confirmacao_de_areas import _normaliza

# `gatilho` casa contra o NOME da área escolhida; `alternativa` é o termo que
# precisa ter sido dito na conversa para a escolha valer.
AMBIGUIDADES = (
    {
        "id": "linha_alba",
        "gatilho": r"\bbarriga\b|\babdome\b|\babdomen\b|\babdominal\b",
        "alternativa": r"\blinha alba\b",
        "pergunta": (
            "Quando você fala em barriga/abdômen, é a *região toda* ou a "
            "*linha alba* (a faixa vertical no centro da barriga)?"
        ),
    },
    {
        "id": "virilha_com_anus",
        "gatilho": r"\bvirilha\b",
        "alternativa": r"\banus\b|\bperianal\b|\bperineo\b",
        "pergunta": (
            "Na virilha, você quer incluir também a região do *ânus "
            "(perianal)*, ou apenas a virilha?"
        ),
    },
)


def _casa(padrao: str, texto: str) -> bool:
    return re.search(padrao, _normaliza(texto)) is not None


def _termo_conversado(padrao: str, turnos: Sequence[Dict]) -> bool:
    """O termo alternativo já foi dito E a paciente falou depois?

    Mesma leitura de confirmacao_de_areas: proposta do bot só conta depois que
    ela respondeu; dito por ela conta na hora.
    """
    for i, turno in enumerate(turnos or []):
        if not _casa(padrao, turno.get("content") or ""):
            continue
        if turno.get("role") == "user":
            return True
        if any(t.get("role") == "user" for t in turnos[i + 1:]):
            return True
    return False


def pendencias(
    pares: Sequence[Dict],
    areas_da_clinica: Iterable[Dict],
    turnos: Sequence[Dict],
) -> List[Dict]:
    """As desambiguações que faltam para os pares escolhidos.

    Lista vazia significa que pode seguir. Cada item traz o nome da área e a
    pergunta que precisa ser feita a ela.
    """
    por_id = {str(a.get("id")): (a.get("name") or "") for a in areas_da_clinica or []}
    pendentes, ja_vistas = [], set()

    for par in pares or []:
        nome = por_id.get(str(par.get("area_id") or ""), "")
        if not nome:
            continue
        for ambiguidade in AMBIGUIDADES:
            if ambiguidade["id"] in ja_vistas:
                continue
            if not _casa(ambiguidade["gatilho"], nome):
                continue
            # O próprio nome já resolve: "Virilha Completa com Ânus" não é
            # ambígua, a escolha dela já diz o que quer.
            if _casa(ambiguidade["alternativa"], nome):
                continue
            if _termo_conversado(ambiguidade["alternativa"], turnos):
                continue
            ja_vistas.add(ambiguidade["id"])
            pendentes.append({
                "id": ambiguidade["id"],
                "area": nome,
                "pergunta": ambiguidade["pergunta"],
            })
    return pendentes


def perguntas(pendentes: Sequence[Dict]) -> List[str]:
    """Só o texto das perguntas - o que o fluxo determinístico precisa enviar."""
    return [p["pergunta"] for p in pendentes or []]


def recado_de_recusa(pendentes: Sequence[Dict]) -> Dict:
    """O que a tool devolve ao modelo quando falta desambiguar.

    Instrutivo de propósito, como em confirmacao_de_areas: o modelo lê e precisa
    saber o próximo passo, senão repete a chamada igual.
    """
    areas = ", ".join(p["area"] for p in pendentes) or "as áreas"
    lista = "\n".join(f"- {p['pergunta']}" for p in pendentes)
    return {
        "error": "areas_ambiguas",
        "areas_a_confirmar": [p["area"] for p in pendentes],
        "o_que_fazer": (
            f"Antes de seguir com {areas}, você precisa desfazer uma ambiguidade "
            f"com a paciente. Pergunte a ela, com estas palavras ou equivalentes:\n"
            f"{lista}\n"
            f"Faça a pergunta e ESPERE a resposta dela. Só depois chame esta tool "
            f"de novo. Não escolha por ela e não suponha pela área mais comum."
        ),
    }
