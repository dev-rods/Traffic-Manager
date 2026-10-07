# -*- coding: utf-8 -*-
"""Duas áreas que o cadastro vende juntas viram o combo - e o combo é mais barato.

Em 06/10/2026 a Aline pediu "virilha completa" e "perianal", em linhas
separadas. O cadastro tem as duas (R$ 175 e R$ 95) e tem "Virilha Completa +
ânus" (R$ 195). O bot somou as separadas: R$ 75 a mais na mesma sessão, e a
clínica corrigiu à mão duas horas depois. Decisão do André: quando as áreas
escolhidas formam um combo que existe, usa-se o combo.

Isso não é instrução para o modelo. Ele recebe a lista inteira de áreas e
escolhe; pedir que "prefira combos" é pedido, não garantia. A troca acontece na
tool, antes de preço, horário e agendamento, e o resultado diz ao modelo o que
foi trocado para ele confirmar com a pessoa pelo nome certo.

O que é combo vem do NOME no cadastro, não de uma tabela à parte: um nome com
"+" cujos dois lados são, cada um, exatamente outra área vendida. "Virilha
Completa + ânus" = "Virilha Completa" + "Perianal/ânus"; "Peitoral + abdômen" =
"Peitoral" + "Abdômen". "Costas total + ombros" NÃO é combo, porque "Costas
total" não existe sozinha; "Mão ou Pé + Dedos" também não. E só troca quando o
combo custa igual ou menos que a soma - combo mais caro que as partes seria a
clínica cobrando a mais, e isso não é decisão do bot.
"""
import re
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from src.services.confirmacao_de_areas import _alternativas


def _conjuntos(nome: str) -> List[frozenset]:
    """Os jeitos de dizer a área, cada um como conjunto de palavras."""
    return [frozenset(palavra for palavra, _ in alt) for alt in _alternativas(nome)]


def _lados(nome: str) -> Optional[Tuple[str, str]]:
    """'Virilha Completa + ânus' -> ('Virilha Completa', 'ânus'). Sem '+', None."""
    partes = [p.strip() for p in re.split(r"\s*\+\s*", nome or "") if p.strip()]
    if len(partes) != 2:
        return None
    return partes[0], partes[1]


def combos_do_catalogo(areas: Iterable[Dict]) -> Dict[str, List[str]]:
    """{id do combo: [ids das partes]} para as áreas cujo nome é soma de duas outras."""
    areas = [a for a in areas if a.get("name")]
    simples = [a for a in areas if _lados(a["name"]) is None]
    combos = {}
    for area in areas:
        lados = _lados(area["name"])
        if not lados:
            continue
        partes = []
        for lado in lados:
            alvo = frozenset(p for p, _ in sum(_alternativas(lado), []))
            candidatos = [
                s for s in simples
                if any(conj == alvo for conj in _conjuntos(s["name"]))
            ]
            if len(candidatos) != 1:
                partes = []
                break
            partes.append(str(candidatos[0]["id"]))
        if len(partes) == 2 and partes[0] != partes[1]:
            combos[str(area["id"])] = partes
    return combos


def aplica(pares: Sequence[Dict], areas: Iterable[Dict],
           preco_de: Callable[[str, str], Optional[int]]) -> Tuple[List[Dict], List[Dict]]:
    """Troca pares de partes pelo combo, quando o combo não custa mais.

    `preco_de(service_id, area_id)` devolve centavos ou None. Devolve
    (pares novos, trocas), onde cada troca é {"de": [nomes], "para": nome}.
    Pares de serviços diferentes não se combinam.
    """
    areas = list(areas)
    nome_de = {str(a.get("id")): a.get("name") for a in areas}
    combos = combos_do_catalogo(areas)
    if not combos or not pares:
        return list(pares or []), []

    restantes = [dict(p) for p in pares]
    trocas = []
    for combo_id, partes in combos.items():
        por_servico: Dict[str, List[int]] = {}
        for i, par in enumerate(restantes):
            if str(par.get("area_id")) in partes:
                por_servico.setdefault(str(par.get("service_id")), []).append(i)
        for service_id, indices in por_servico.items():
            ids = {str(restantes[i]["area_id"]) for i in indices}
            if ids != set(partes):
                continue
            precos = [preco_de(service_id, str(restantes[i]["area_id"])) for i in indices]
            preco_combo = preco_de(service_id, combo_id)
            if any(p is None for p in precos) or preco_combo is None:
                continue
            soma = sum(precos)
            if preco_combo > soma:
                continue
            trocas.append({
                "de": [nome_de.get(str(restantes[i]["area_id"]), "?") for i in indices],
                "para": nome_de.get(combo_id, "?"),
                "economia_cents": soma - preco_combo,
            })
            # O primeiro par vira o combo; os outros saem. A ordem dos demais
            # pares nao muda.
            primeiro = min(indices)
            restantes[primeiro]["area_id"] = combo_id
            restantes = [p for i, p in enumerate(restantes) if i == primeiro or i not in indices]
            break  # os indices mudaram; um combo por servico por chamada basta
    return restantes, trocas
