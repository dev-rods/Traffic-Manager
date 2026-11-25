# -*- coding: utf-8 -*-
"""Saudação pelo relógio da clínica, não pelo eco da pessoa.

"Olá, boa noite" mandado às 21h e respondido às 8h da manhã seguinte (bot
calado pela política até alguém retomar) saía como "Olá, boa noite". O
modelo copia a saudação porque é o que está no histórico; ele não tem
relógio. O bloco CALENDÁRIO ganha a hora e o período, o prompt manda
cumprimentar pelo AGORA, e esta trava corrige o que escapar (PRD 064).
"""
import re
from datetime import datetime
from typing import Optional

MANHA, TARDE, NOITE = "manhã", "tarde", "noite"

_SAUDACAO_POR_PERIODO = {MANHA: "Bom dia", TARDE: "Boa tarde", NOITE: "Boa noite"}
_PERIODO_POR_SAUDACAO = {"bom dia": MANHA, "boa tarde": TARDE, "boa noite": NOITE}
_SAUDACAO = re.compile(r"\b(bom dia|boa tarde|boa noite)\b", re.IGNORECASE)


def periodo(agora_local: datetime) -> str:
    h = agora_local.hour
    if h < 12:
        return MANHA
    if h < 18:
        return TARDE
    return NOITE


def saudacao_do_periodo(p: Optional[str]) -> str:
    return _SAUDACAO_POR_PERIODO.get(p or "", "Olá")


def linha_do_calendario(agora_local: datetime) -> str:
    """A linha que entra no bloco CALENDÁRIO: 'Agora: 08:12, manhã.'"""
    return f"Agora: {agora_local.strftime('%H:%M')}, {periodo(agora_local)}."


def corrige(texto: str, periodo_atual: Optional[str]) -> str:
    """Troca 'bom dia/boa tarde/boa noite' de período errado pela saudação do
    período atual (ou 'Olá' sem período). Preserva o resto, inclusive a
    inicial maiúscula/minúscula do que estava lá."""
    if not texto:
        return texto

    def _troca(m):
        achada = m.group(1)
        if _PERIODO_POR_SAUDACAO.get(achada.lower()) == periodo_atual:
            return achada
        nova = saudacao_do_periodo(periodo_atual)
        return nova if achada[0].isupper() else nova.lower()

    return _SAUDACAO.sub(_troca, texto)


def saudacao_errada(texto: str, periodo_atual: Optional[str]) -> bool:
    return corrige(texto, periodo_atual) != (texto or "")
