# -*- coding: utf-8 -*-
"""Fecho social: quando a conversa já acabou e a pessoa só se despede de novo.

Em 24/11/2026 (Nobre): "Muito obrigada 😊" -> "Por nada! Até o dia 03/12 💛"
-> "Até 🙂" -> "Até lá! 💛". O agente não tinha como calar: resposta vazia
do modelo era tratada como falha (versão curta, depois handoff), e a guarda
de fecho social existia só na retomada automática (`retomada.py`).

Aqui a regra vira uma só, usada antes do modelo (fluxo normal), na retomada
pelo painel (`conversation_resume`) e na retomada automática (`retomada`):
a pessoa mandou só um fecho social, sem pergunta nem dado novo, e a última
fala do bot já era de encerramento. Nesse caso o bot cala (PRD 064, P4/P7).
"""
import re
import time
import unicodedata
from typing import Dict, Optional, Sequence

from src.services.roteador import SOCIAL

_SOCIAL = re.compile(SOCIAL)
# O que a regex do roteador nao cobre e aparece em despedida: "até" sozinho,
# "até lá", "até breve", "até já", beijos.
_SOCIAL_EXTRA = re.compile(r"^(muito |mt |mto |muitissimo )?(obrigad[ao]|brigad[ao]|obg|ate|ate la|ate breve|ate ja|ate amanha|beijos?|bjs|beijo)[\s!.,?]*$")

# A última fala do bot foi de encerramento: agradeceu, se despediu ou se
# colocou à disposição, e não deixou pergunta. "Até o dia 03/12" conta.
_ENCERRAMENTO = re.compile(
    r"(por nada|de nada|imagina|obrigad|at[eé]\b|at[eé] (l[aá]|mais|logo|breve|o dia)|"
    r"abra[cç]o|beij|qualquer d[uú]vida|[aà] disposi[cç][aã]o|te esperamos|"
    r"boa (sess[aã]o|semana|noite|tarde)|bom dia|tchau|fico feliz)",
    re.IGNORECASE,
)

# Dentro desta janela, uma despedida depois de outra é eco. Fora dela, a
# pessoa pode estar abrindo conversa de novo ("oi, boa tarde") e merece "oi".
JANELA_HORAS = 24


def _plano(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(c) != "Mn"
    ).strip()


def e_fecho_social(texto: str) -> bool:
    """Só saudação, agradecimento, confirmação curta ou despedida; nada mais.
    Emoji e pontuação não contam."""
    plano = re.sub(r"[^\w\s,;!?.]", "", _plano(texto))
    pedacos = [p.strip() for p in re.split(r"[,;]|\se\s", plano) if p.strip()]
    return bool(pedacos) and all(_SOCIAL.match(p) or _SOCIAL_EXTRA.match(p) for p in pedacos)


def tem_conteudo_novo(texto: str) -> bool:
    """Pergunta ou dado: "?" ou qualquer dígito. "Obrigada, e amanhã abre?"
    não é fecho; "até dia 3" também não."""
    t = texto or ""
    return "?" in t or bool(re.search(r"\d", t))


def _instante(evento: Dict) -> Optional[int]:
    sk = str(evento.get("sk") or "")
    m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", sk)
    if not m:
        return None
    try:
        return int(time.mktime(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) - time.timezone)
    except (ValueError, OverflowError):
        return None


def ultima_fala_do_bot_foi_fecho(eventos: Sequence[Dict], agora: Optional[int] = None,
                                 janela_horas: int = JANELA_HORAS) -> bool:
    """A última mensagem com texto da conversa, antes desta, é do bot, é de
    encerramento, não termina em pergunta e saiu dentro da janela."""
    agora = int(agora if agora is not None else time.time())
    for evento in reversed(eventos or []):
        texto = (evento.get("content") or "").strip()
        if not texto:
            continue
        if evento.get("direction") != "OUTBOUND":
            return False
        autor = str(((evento.get("metadata") or {}).get("autor") or "")).upper()
        if autor in ("HUMANO", "SISTEMA"):
            # Fala da recepção ou envio do sistema (confirmação, orientações):
            # não é o bot se despedindo.
            return False
        if texto.rstrip().endswith("?"):
            return False
        quando = _instante(evento)
        if quando is not None and agora - quando > janela_horas * 3600:
            return False
        return bool(_ENCERRAMENTO.search(texto))
    return False


def deve_calar(eventos: Sequence[Dict], texto: str, agora: Optional[int] = None) -> bool:
    """A pessoa só se despediu de novo e o bot já tinha encerrado: calar."""
    return (e_fecho_social(texto) and not tem_conteudo_novo(texto)
            and ultima_fala_do_bot_foi_fecho(eventos, agora))


# O que o modelo declara em `sem_consulta_necessaria(motivo=...)` quando a
# mensagem é só agradecimento ou despedida. Com isso, resposta vazia é
# legítima (ver conversation_agent), não falha.
_DESPEDIDA_DECLARADA = re.compile(r"despedid|agradec|encerr|tchau|obrigad|cumpriment", re.IGNORECASE)


def motivo_e_despedida(motivo: Optional[str]) -> bool:
    return bool(_DESPEDIDA_DECLARADA.search(_plano(motivo or "")))
