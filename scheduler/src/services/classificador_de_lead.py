# -*- coding: utf-8 -*-
"""Duas perguntas ao modelo sobre a conversa de um lead (PRD 057).

Triagem: "isto e um lead?" - so para quem chegou pelo WhatsApp, cedo (3
mensagens do contato). Fornecedor, cobranca e conversa pessoal saem do funil.

Desfecho: "por que nao agendou?" - so para quem parou ha N dias e chegou a
falar. Devolve NAO_AGENDOU com motivo curto, ou AINDA_ABERTO quando nao ha
decisao na conversa.

O modelo so SUGERE. A atendente corrige no painel e a correcao trava (MANUAL).
Resposta que nao e JSON ou classe fora do enum e descartada e conta no teto;
o lead nao e marcado como tentado e volta na noite seguinte.
"""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

from src.services import estagio_do_lead as estagio
from src.services.transcricao import LEAD, Mensagem

logger = logging.getLogger(__name__)

MODELO_DO_CLASSIFICADOR = "claude-haiku-4-5-20251001"
TRIAGEM_MINIMO_DE_MENSAGENS_DO_LEAD = 3
MAX_CHAMADAS_PADRAO = 200
TAMANHO_DO_MOTIVO = 120

CLASSES_DA_TRIAGEM = frozenset({"LEAD", "NAO_E_LEAD"})
CLASSES_DO_DESFECHO = frozenset({"NAO_AGENDOU", "AINDA_ABERTO"})

_SYSTEM_TRIAGEM = (
    "Voce le conversas de WhatsApp de uma clinica de depilacao a laser chamada {nome}. "
    "Decida se o contato e um LEAD (pessoa interessada em tratamento, agendamento, preco, "
    "duvida de paciente ou ex-paciente) ou NAO_E_LEAD (fornecedor, proposta comercial, "
    "cobranca, conversa pessoal, spam, engano). Na duvida, LEAD. "
    'Responda SOMENTE um JSON: {{"classe": "LEAD" | "NAO_E_LEAD", "motivo": "<ate 8 palavras>"}}.'
)
_SYSTEM_DESFECHO = (
    "Voce le conversas de WhatsApp de uma clinica de depilacao a laser chamada {nome}. "
    "A pessoa parou de responder e nao agendou. Decida: NAO_AGENDOU quando a conversa mostra "
    "uma razao ou uma recusa (achou caro, mora longe, so pesquisando, vai pensar, fora do "
    "horario, contraindicacao, fechou em outro lugar), ou AINDA_ABERTO quando nao ha decisao "
    "visivel (a clinica nao respondeu, a pessoa so sumiu). "
    'Responda SOMENTE um JSON: {{"classe": "NAO_AGENDOU" | "AINDA_ABERTO", "motivo": "<ate 8 palavras>"}}.'
)


@dataclass(frozen=True)
class Veredito:
    classe: str
    motivo: str


class TetoAtingido(Exception):
    """A execucao ja fez o maximo de chamadas; o resto fica para a proxima noite."""


def interpreta(texto: str, classes_validas: Iterable[str]) -> Optional[Veredito]:
    """Extrai {"classe","motivo"} do texto. Qualquer coisa fora do enum e descartada."""
    achado = re.search(r"\{.*?\}", texto or "", flags=re.S)
    if not achado:
        return None
    try:
        dados = json.loads(achado.group(0))
    except ValueError:
        return None
    if not isinstance(dados, dict):
        return None
    classe = dados.get("classe")
    if classe not in set(classes_validas):
        return None
    motivo = " ".join(str(dados.get("motivo") or "").split())[:TAMANHO_DO_MOTIVO]
    return Veredito(classe, motivo)


def precisa_de_triagem(lead: dict, mensagens: List[Mensagem]) -> bool:
    if (lead.get("source") or "whatsapp") != "whatsapp":
        return False
    if lead.get("triagem_feita_em"):
        return False
    return sum(1 for m in mensagens if m.de == LEAD) >= TRIAGEM_MINIMO_DE_MENSAGENS_DO_LEAD


def precisa_de_desfecho(lead: dict, decisao: estagio.Decisao, mensagens: List[Mensagem],
                        agora: datetime, dias_parado: int) -> bool:
    if decisao.stage not in (estagio.SUMIU, estagio.INICIADA_SEM_RESPOSTA):
        return False
    if not any(m.de == LEAD for m in mensagens):
        return False
    ultima = mensagens[-1].em if mensagens else None
    if ultima is None or (agora - ultima) <= timedelta(days=dias_parado):
        return False
    tentado = lead.get("desfecho_tentado_em")
    return tentado is None or tentado < ultima


def _transcricao_em_texto(mensagens: List[Mensagem]) -> str:
    rotulo = {LEAD: "CONTATO", "NOS": "CLINICA"}
    return "\n".join("[{:%d/%m %H:%M}] {}: {}".format(m.em, rotulo.get(m.de, m.de), m.texto.strip())
                     for m in mensagens)


class Classificador:
    def __init__(self, anthropic=None, max_chamadas: int = MAX_CHAMADAS_PADRAO):
        if anthropic is None:
            from src.services.anthropic_service import AnthropicService
            anthropic = AnthropicService()
        self.anthropic = anthropic
        self.max_chamadas = max_chamadas
        self.chamadas = 0

    def _pergunta(self, system: str, mensagens: List[Mensagem], clinic: dict, classes) -> Optional[Veredito]:
        if self.chamadas >= self.max_chamadas:
            raise TetoAtingido("{} chamadas nesta execucao".format(self.max_chamadas))
        self.chamadas += 1
        nome = clinic.get("display_name") or clinic.get("name") or "a clinica"
        try:
            corpo = self.anthropic.create_message(
                system=system.format(nome=nome),
                messages=[{"role": "user", "content": _transcricao_em_texto(mensagens)}],
                model=MODELO_DO_CLASSIFICADOR,
                temperature=0,
                max_tokens=120,
            )
        except Exception as e:
            logger.error("[Classificador] chamada falhou: {}".format(e))
            return None
        texto = "".join(b.get("text", "") for b in (corpo or {}).get("content", []) if b.get("type") == "text")
        veredito = interpreta(texto, classes)
        if veredito is None:
            logger.warning("[Classificador] resposta descartada: {!r}".format(texto[:200]))
        return veredito

    def triagem(self, mensagens: List[Mensagem], clinic: dict) -> Optional[Veredito]:
        return self._pergunta(_SYSTEM_TRIAGEM, mensagens, clinic, CLASSES_DA_TRIAGEM)

    def desfecho(self, mensagens: List[Mensagem], clinic: dict) -> Optional[Veredito]:
        return self._pergunta(_SYSTEM_DESFECHO, mensagens, clinic, CLASSES_DO_DESFECHO)
