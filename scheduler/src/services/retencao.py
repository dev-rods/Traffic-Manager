# -*- coding: utf-8 -*-
"""Quanto tempo conversa vive. PRD 022, decisões do André em 12/10/2026.

Duas retenções, num lugar só:

  MEMORIA_DO_BOT       30 dias. A sessão PHONE# vence (atributo `ttl` do
                       DynamoDB) e o agente não lê histórico mais velho que
                       isso, nem da sessão nem dos eventos. Quem volta depois
                       de 30 dias de silêncio é conversa nova.
  HISTORICO_DO_PAINEL  60 dias. Os eventos de mensagem (aba Conversas, chat de
                       cada número) vencem.

O que NÃO vence: o vínculo LID# (identidade; sem ele a resposta da atendente
pelo celular fica sem dono) e, dentro da sessão, as marcas de identidade
(`bot_enabled`, `lead_id`) quando a sessão vencida ainda está no banco - o
DynamoDB apaga com atraso de até 48 h, e nesse intervalo o agente descarta a
conversa mas mantém quem a pessoa é. `bot_enabled` é rederivado da tabela
`leads` pelo webhook quando some de vez.

Pura, sem I/O. Todo escritor de sessão e de evento passa por aqui: o teste
`test_retencao` confere por AST que nenhum `put_item` de PHONE# esquece o `ttl`.
"""
import calendar
import time
from typing import Optional

DIA = 86400
MEMORIA_DO_BOT = 30 * DIA
HISTORICO_DO_PAINEL = 60 * DIA

# O que sobrevive quando a conversa venceu mas o item ainda não foi apagado.
CAMPOS_DE_IDENTIDADE = frozenset({"bot_enabled", "lead_id"})

_ISO = "%Y-%m-%dT%H:%M:%SZ"


def ttl_da_sessao(agora: Optional[int] = None) -> int:
    return int(agora if agora is not None else time.time()) + MEMORIA_DO_BOT


def ttl_do_evento(criado_em: Optional[int] = None) -> int:
    return int(criado_em if criado_em is not None else time.time()) + HISTORICO_DO_PAINEL


def inicio_da_memoria(agora: Optional[int] = None) -> int:
    """O instante mais antigo que o agente ainda lê."""
    return int(agora if agora is not None else time.time()) - MEMORIA_DO_BOT


def iso(epoch: int) -> str:
    return time.strftime(_ISO, time.gmtime(int(epoch)))


def sessao_vencida(updated_at_iso: Optional[str], agora: Optional[int] = None) -> bool:
    """A sessão está parada há mais de MEMORIA_DO_BOT? Sem `updatedAt` (sessão
    nova, ou item antigo sem o campo) não está vencida: na dúvida, lembrar."""
    if not updated_at_iso:
        return False
    try:
        escrita = calendar.timegm(time.strptime(str(updated_at_iso)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OverflowError):
        return False
    return escrita < inicio_da_memoria(agora)


def so_identidade(session: dict) -> dict:
    """A sessão sem a conversa: o que uma pessoa é, não o que ela disse."""
    return {k: v for k, v in (session or {}).items() if k in CAMPOS_DE_IDENTIDADE}
