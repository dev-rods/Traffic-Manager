# -*- coding: utf-8 -*-
"""Em que pe esta a conversa de cada lead: as regras, sem I/O (PRD 057).

Nao confundir com `status_da_conversa`, que diz QUEM conduz a conversa agora
(bot ou pessoa) e e calculado na hora da listagem. O estagio diz EM QUE PE a
conversa esta e e um retrato noturno gravado no lead pela ClassificaLeads.

A precedencia esta em `decide`, e a ordem e a regra:
fato da agenda > NAO_E_LEAD > MANUAL > veredito do modelo > regras de conversa.
Um fato (agendou) vence inclusive uma correcao manual, porque agendar nao e
julgamento. E a unica excecao a "MANUAL trava tudo".

Fato que nao fecha a porta: CANCELOU e FALTOU ficam para tras quando o lead
escreve DEPOIS do horario daquele agendamento. Quem cancelou e perguntou
"consigo remarcar?" e AGUARDANDO_NOS, nao um cancelamento parado. AGENDOU nao
tem essa saida: com sessao marcada, a conversa nao e problema do CRM.

Qual fato (PRD 054): o agendamento mais recente que NAO e remarcacao decide.
Remarcacao e CANCELLED com `rescheduled_to_id`, e fica de fora antes de olhar.
Quem faltou e remarcou e AGENDOU; quem remarcou tres vezes nao vira CANCELOU.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

SEM_CONVERSA = "SEM_CONVERSA"
INICIADA_SEM_RESPOSTA = "INICIADA_SEM_RESPOSTA"
EM_ANDAMENTO = "EM_ANDAMENTO"
AGUARDANDO_NOS = "AGUARDANDO_NOS"
SUMIU = "SUMIU"
NAO_AGENDOU = "NAO_AGENDOU"
CANCELOU = "CANCELOU"
FALTOU = "FALTOU"
AGENDOU = "AGENDOU"
NAO_E_LEAD = "NAO_E_LEAD"

REGRA = "REGRA"
MODELO = "MODELO"
MANUAL = "MANUAL"
HISTORICO = "HISTORICO"

ESTAGIOS = (SEM_CONVERSA, INICIADA_SEM_RESPOSTA, EM_ANDAMENTO, AGUARDANDO_NOS, SUMIU,
            NAO_AGENDOU, CANCELOU, FALTOU, AGENDOU, NAO_E_LEAD)
FONTES = (REGRA, MODELO, MANUAL, HISTORICO)

# A ordem dos chips e a ordem de trabalho: quem precisa de acao primeiro.
ORDEM_DA_FILA = (AGUARDANDO_NOS, SUMIU, INICIADA_SEM_RESPOSTA, SEM_CONVERSA, EM_ANDAMENTO,
                 NAO_AGENDOU, CANCELOU, FALTOU, AGENDOU)

ESTAGIOS_DA_AGENDA = frozenset({AGENDOU, CANCELOU, FALTOU})
# O que a atendente pode escolher no popover. Fato da agenda nao se edita.
ESTAGIOS_EDITAVEIS = frozenset(ESTAGIOS) - ESTAGIOS_DA_AGENDA

# O MessageEvents guarda 60 dias (PRD 022). Conversa mais antiga que isso so
# existe no espelho do z-api, sem texto: o estagio vai sem motivo e marcado
# HISTORICO para a tela nao fingir que leu a conversa.
DIAS_DE_RETENCAO_DOS_EVENTOS = 60

LEAD = "LEAD"
NOS = "NOS"

_PELO_STATUS = {"CONFIRMED": AGENDOU, "NO_SHOW": FALTOU, "CANCELLED": CANCELOU}


@dataclass(frozen=True)
class Sinais:
    stage: Optional[str]
    stage_source: Optional[str]
    stage_updated_at: Optional[datetime]
    first_contact_at: Optional[datetime]
    ultima_mensagem_de: Optional[str]        # LEAD | NOS | None
    ultima_mensagem_em: Optional[datetime]
    lead_ja_falou: bool
    tem_transcricao: bool                    # veio do MessageEvents
    chat_espelho_em: Optional[datetime]      # whatsapp_chats.last_message_at
    chat_espelho_nao_lidas: int
    # status do agendamento mais recente SEM rescheduled_to_id (PRD 054):
    # CONFIRMED | CANCELLED | NO_SHOW | None
    ultimo_agendamento: Optional[str]
    # data e hora desse agendamento, em UTC. E o marco para "o lead falou depois".
    ultimo_agendamento_em: Optional[datetime] = None


@dataclass(frozen=True)
class Decisao:
    stage: str
    source: str
    reason: Optional[str] = None


def _parado_ha(mais_que_dias: int, quando: Optional[datetime], agora: datetime) -> bool:
    return quando is not None and (agora - quando) > timedelta(days=mais_que_dias)


def _mensagem_nova_depois_do_veredito(s: Sinais) -> bool:
    """O lead falou DEPOIS de o modelo decidir? Entao o veredito caiu."""
    return (s.ultima_mensagem_de == LEAD and s.ultima_mensagem_em is not None
            and s.stage_updated_at is not None and s.ultima_mensagem_em > s.stage_updated_at)


def _lead_falou_depois(s: Sinais, marco: Optional[datetime]) -> bool:
    return (s.ultima_mensagem_de == LEAD and s.ultima_mensagem_em is not None
            and marco is not None and s.ultima_mensagem_em > marco)


def _pela_agenda(s: Sinais) -> Optional[Decisao]:
    stage = _PELO_STATUS.get(s.ultimo_agendamento or "")
    if not stage:
        return None
    if stage in (CANCELOU, FALTOU) and _lead_falou_depois(s, s.ultimo_agendamento_em):
        # Cancelou ou faltou e voltou a escrever: a conversa manda de novo.
        return None
    return Decisao(stage, REGRA)


def _pela_conversa(s: Sinais, agora: datetime, dias_parado: int) -> Decisao:
    if s.tem_transcricao and s.ultima_mensagem_de:
        if not s.lead_ja_falou:
            # So nos falamos. Depois de N dias nao e mais "iniciada": sumiu.
            if _parado_ha(dias_parado, s.ultima_mensagem_em, agora):
                return Decisao(SUMIU, REGRA)
            return Decisao(INICIADA_SEM_RESPOSTA, REGRA)
        if s.ultima_mensagem_de == LEAD:
            return Decisao(AGUARDANDO_NOS, REGRA)
        if _parado_ha(dias_parado, s.ultima_mensagem_em, agora):
            return Decisao(SUMIU, REGRA)
        return Decisao(EM_ANDAMENTO, REGRA)

    if s.chat_espelho_em is not None:
        # So o espelho: existe conversa, sem direcao nem texto.
        fonte = HISTORICO if _parado_ha(DIAS_DE_RETENCAO_DOS_EVENTOS, s.chat_espelho_em, agora) else REGRA
        if s.chat_espelho_nao_lidas > 0:
            return Decisao(AGUARDANDO_NOS, fonte)
        if _parado_ha(dias_parado, s.chat_espelho_em, agora):
            return Decisao(SUMIU, fonte)
        return Decisao(EM_ANDAMENTO, fonte)

    if s.first_contact_at is not None:
        if _parado_ha(dias_parado, s.first_contact_at, agora):
            return Decisao(SUMIU, REGRA)
        return Decisao(INICIADA_SEM_RESPOSTA, REGRA)
    return Decisao(SEM_CONVERSA, REGRA)


def decide(sinais: Sinais, agora: datetime, dias_parado: int = 7) -> Decisao:
    fato = _pela_agenda(sinais)
    if fato:
        return fato

    if sinais.stage_source == MANUAL and sinais.stage:
        # Decisao manual sai sem motivo de proposito: o repo mantem o que esta
        # gravado. Motivo novo so chega por outra correcao manual.
        return Decisao(sinais.stage, MANUAL)

    if sinais.stage in (NAO_E_LEAD, NAO_AGENDOU) and sinais.stage_source == MODELO:
        if not _mensagem_nova_depois_do_veredito(sinais):
            return Decisao(sinais.stage, MODELO)

    return _pela_conversa(sinais, agora, dias_parado)
