# -*- coding: utf-8 -*-
"""A lista numerada que a paciente vê, e o número que ela responde.

Com mais de 3 opções o WhatsApp não tem botões, e `_build_outgoing` manda a
lista como texto numerado ("1. Virilha Cavada"). A numeração nasce na hora de
enviar: o modelo nunca a vê - no histórico fica a fala dele e o tool_result
com ids e rótulos, sem número nenhum. Quando a pessoa responde "1", que é o
que qualquer pessoa faz diante de uma lista numerada, o modelo não tem como
ligar o dígito à opção e trata a resposta como incompreensível.

Em 16/10/2026 isso custou uma lead vinda do site (quatro respostas corretas,
duas vezes "o que você quer fazer?", seis horas em silêncio). Em 13/10 outra
só se salvou porque digitou o rótulo inteiro.

Determinismo em volta, modelo no meio: a lista enviada fica na sessão e o
dígito vira o rótulo ANTES de o modelo ler. É o mesmo que o botão faz com
até 3 opções - o toque volta como o texto do rótulo.
"""
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CAMPO = "conversa"
CHAVE = "opcoes_numeradas"

# "1", "1.", "1)", "1 -", "opção 1", "a 1", "número 2"
_DIGITO = re.compile(
    r"^\s*(?:(?:op[cç][aã]o|n[uú]mero|a|o)\s+)?(\d{1,2})\s*[.)\-]?\s*$",
    re.IGNORECASE,
)


def guarda(session: Dict, options: List[Dict[str, str]]) -> None:
    """A lista que acabou de sair numerada. Substitui a anterior: só a última
    mensagem do bot está na tela com números."""
    bloco = dict(session.get(CAMPO) or {})
    bloco[CHAVE] = [
        {"id": str(o.get("id", "")), "label": str(o.get("label", ""))} for o in options
    ]
    session[CAMPO] = bloco


def limpa(session: Dict) -> None:
    """O bot falou de novo sem lista numerada: um dígito agora não aponta
    para nada."""
    if not session or CHAVE not in (session.get(CAMPO) or {}):
        return
    bloco = dict(session.get(CAMPO) or {})
    bloco.pop(CHAVE, None)
    session[CAMPO] = bloco


def pendentes(session: Optional[Dict]) -> List[Dict[str, str]]:
    return list(((session or {}).get(CAMPO) or {}).get(CHAVE) or [])


def resolve(session: Optional[Dict], texto: str) -> Optional[Dict[str, str]]:
    """A opção que o número aponta, ou None se não há lista ou o texto não
    é um número dentro dela. Fora do intervalo também é None: "5" numa lista
    de 4 é a pessoa falando de outra coisa, e o modelo que decida."""
    opcoes = pendentes(session)
    if not opcoes:
        return None
    m = _DIGITO.match(texto or "")
    if not m:
        return None
    n = int(m.group(1))
    if not 1 <= n <= len(opcoes):
        return None
    return opcoes[n - 1]


def numerada(options: List[Dict[str, str]]) -> str:
    """O texto que vai para a paciente - a MESMA numeração que `resolve` lê."""
    return "\n".join(f"{i + 1}. {opt['label']}" for i, opt in enumerate(options))
