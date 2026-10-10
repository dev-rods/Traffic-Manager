# -*- coding: utf-8 -*-
"""Fase 6 (PRD 020 §4.1): perguntar antes de desistir, e desistir depois de duas.

Quando o modelo não consegue saber o que a pessoa quer ("quero marcar aquele
negócio"), ele chama `pedir_esclarecimento` com as intenções plausíveis. A
pergunta é TEXTO FIXO com botões; o modelo escolhe as opções, não redige a
pergunta. Um contador na sessão sobe a cada pergunta e zera quando uma
intenção se resolve (tool com efeito, ou item do FAQ entregue). Na terceira
ambiguidade seguida a conversa vai a uma pessoa com `incompreensao`.

Sem o contador uma pessoa confusa entra em laço; o repositório já tem a
cicatriz disso em `recusas_de_area`. E se o modelo pedir handoff por
`incompreensao` antes de esgotar as tentativas, o código converte o pedido na
pergunta: perguntar é mais barato que ocupar a recepção com o que uma
pergunta resolveria.

Medido em prod em 10/10/2026: zero handoffs por incompreensao em 30 dias. A
fase entra como proteção, não como correção de dor atual.
"""
import logging
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

MAX_TENTATIVAS = 2
CAMPO = "conversa"
CHAVE = "tentativas_de_desambiguacao"

NOME_DA_TOOL = "pedir_esclarecimento"

# As intenções que o modelo pode oferecer. Rótulo <= 24 caracteres (botão do
# WhatsApp). A pessoa toca e o texto do botão volta como mensagem dela.
OPCOES = {
    "agendar": "Agendar uma sessão",
    "remarcar": "Remarcar",
    "cancelar": "Cancelar",
    "duvida": "Tirar uma dúvida",
}
PADRAO = ("agendar", "remarcar", "duvida")
MAX_OPCOES = 3  # botões inline do WhatsApp

TEXTO = "Só para eu te ajudar certinho: o que você quer fazer? 😊"

# O que a pessoa recebe quando as tentativas acabam.
TEXTO_DE_ESGOTAMENTO = "Vou chamar uma especialista para te ajudar, só um instante 😊"


def tentativas(session: Optional[Dict]) -> int:
    return int(((session or {}).get(CAMPO) or {}).get(CHAVE) or 0)


def registra_tentativa(session: Dict) -> int:
    bloco = dict(session.get(CAMPO) or {})
    bloco[CHAVE] = tentativas(session) + 1
    session[CAMPO] = bloco
    return bloco[CHAVE]


def zera(session: Optional[Dict]) -> None:
    if not session or not (session.get(CAMPO) or {}).get(CHAVE):
        return
    bloco = dict(session.get(CAMPO) or {})
    bloco[CHAVE] = 0
    session[CAMPO] = bloco


def esgotou(session: Optional[Dict]) -> bool:
    return tentativas(session) >= MAX_TENTATIVAS


def opcoes(candidatas: Optional[Sequence[str]]) -> List[Dict[str, str]]:
    """As opções válidas entre as pedidas, na ordem de OPCOES, até MAX_OPCOES.
    Nenhuma válida: o padrão (agendar, remarcar, dúvida)."""
    pedidas = [c for c in (candidatas or []) if c in OPCOES]
    escolhidas = [c for c in OPCOES if c in pedidas] or list(PADRAO)
    return [{"id": c, "label": OPCOES[c]} for c in escolhidas[:MAX_OPCOES]]


def pergunta(candidatas: Optional[Sequence[str]]) -> Dict:
    """O que o agente trata como `present_options`: texto fixo + botões."""
    return {"presented": True, "esclarecimento": True, "message": TEXTO, "options": opcoes(candidatas)}


def pede(session: Dict, candidatas: Optional[Sequence[str]], phone: str = "") -> Dict:
    """Registra a tentativa e devolve a pergunta - ou, se já foram
    MAX_TENTATIVAS, o handoff por incompreensão. Quem chama é o executor."""
    from src.services.bot_policy import MOTIVO_INCOMPREENSAO

    if esgotou(session):
        logger.info(f"[Desambiguacao] {phone}: {tentativas(session)} tentativas; pessoa")
        return {"esclarecimento": False, "handoff_requested": True, "reason": MOTIVO_INCOMPREENSAO,
                "instruction": "The conversation is being transferred to a person. Reply with nothing."}
    n = registra_tentativa(session)
    logger.info(f"[Desambiguacao] {phone}: tentativa {n}/{MAX_TENTATIVAS} ({[o['id'] for o in opcoes(candidatas)]})")
    r = pergunta(candidatas)
    r["instruction"] = (
        "The clarification question is being sent to the patient as buttons, with a fixed text. "
        "Do NOT write the question yourself; reply with nothing."
    )
    return r


def definicao_da_tool() -> Dict:
    return {
        "type": "function",
        "function": {
            "name": NOME_DA_TOOL,
            "description": (
                "Call this when you cannot tell what the patient wants (schedule, reschedule, cancel or "
                "ask something) and the message gives you no way to find out. A fixed clarification "
                "question is sent with buttons for the options you list; you do not write it. Do not "
                "call request_human_handoff for not understanding - this tool decides when to give up."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidatas": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(OPCOES)},
                        "description": "Up to 3 plausible intents to offer as buttons.",
                    },
                },
                "required": ["candidatas"],
            },
        },
    }
