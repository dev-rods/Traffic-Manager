# -*- coding: utf-8 -*-
"""Onde a pessoa resolve o proprio agendamento sem falar com ninguem.

"Meus agendamentos" vive na Home do booking-site. Com dominio proprio da
clinica a raiz JA e a clinica; sem dominio, nao ha link: o bot volta a
cancelar e remarcar pela conversa (decisao do Andre em 27/10/2026). O dominio
Vercel padrao fica de fora de proposito; se um dia servir, e uma env var aqui,
num lugar so.
"""
import time
from typing import Dict, Optional


def link_de_autoatendimento(clinic: Optional[dict]) -> Optional[str]:
    dominio = ((clinic or {}).get("custom_domain") or "").strip()
    if not dominio:
        return None
    dominio = dominio.replace("https://", "").replace("http://", "").rstrip("/")
    return f"https://{dominio}/"


# -- O link como primeiro caminho (PRD 046) ----------------------------------
#
# Para quem ja e paciente, em clinica com dominio, o site e a PRIMEIRA
# tentativa: o bot manda o link antes de qualquer area ou data, e so agenda na
# conversa depois de o link ter saido (decisao do Andre em 10/11/2026). O que
# conta e o bot ter mandado - o texto do disparo e a mensagem da recepcao nao
# contam, de proposito: nesses casos a decisao pede reforco.

CAMPO_LINK_ENVIADO = "link_enviado_em"
# Mesmo prazo da campanha (campanha.DURACAO_PADRAO_DIAS). Sem prazo, quem
# recebeu o link em agosto agendaria na conversa de primeira em novembro.
VALIDADE_DIAS = 7


def link_de_agendamento(clinic: Optional[dict]) -> Optional[str]:
    """O link que o bot manda a quem ja e paciente. E o mesmo site do
    autoatendimento; o nome diz o papel."""
    return link_de_autoatendimento(clinic)


def _dominio(link: str) -> str:
    return (link or "").replace("https://", "").replace("http://", "").rstrip("/").lower()


def link_citado(texto: Optional[str], link: Optional[str]) -> bool:
    """O texto traz o link? Compara pelo dominio: o modelo escreve
    `agendar.x.com.br/agendar` tanto quanto a raiz."""
    d = _dominio(link or "")
    return bool(d) and d in (texto or "").lower()


def marca_link_enviado(session: Optional[Dict], agora: Optional[int] = None) -> Dict:
    s = session if session is not None else {}
    s[CAMPO_LINK_ENVIADO] = int(agora if agora is not None else time.time())
    return s


def link_ja_foi(session: Optional[Dict], agora: Optional[int] = None) -> bool:
    """O bot ja mandou o link nesta conversa, dentro do prazo? Falha fechada:
    campo ausente ou ilegivel e "ainda nao foi"."""
    try:
        quando = int((session or {})[CAMPO_LINK_ENVIADO])
    except (KeyError, TypeError, ValueError):
        return False
    agora = int(agora if agora is not None else time.time())
    return agora - quando < VALIDADE_DIAS * 86400
