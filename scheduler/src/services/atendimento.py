# -*- coding: utf-8 -*-
"""Quem atende esta conversa agora - e as duas perguntas que saem disso.

Hoje `session["state"]` carrega três coisas numa string: o passo do fluxo, o
resultado e QUEM responde. Aqui o "quem responde" ganha campo próprio, máquina
própria e um dono só. PRD 020 §3.2 a §3.5.

    BOT_ACTIVE ──(pessoa da clínica fala / handoff / pausa no painel)──▶ HUMAN_ACTIVE
        ▲                                                                   │
        │                                                     (human_until vence)
        │                                                                   ▼
        │                                                            HUMAN_EXPIRED
        │                                                                   │
        │                                            (fase 3: pendência -> HUMAN_PENDING)
        │                                                                   ▼
        └──────────────(cliente escreve, ou cooldown_until vence)──── COOLDOWN

E as duas perguntas, que hoje são uma só (`should_bot_reply`):

    pode_responder   reativo: alguém escreveu, o bot pode responder?
    pode_iniciar     proativo: ninguém escreveu, o bot pode falar primeiro?

A diferença é o COOLDOWN e a janela de silêncio: depois de um atendimento
humano o bot responde a quem escrever, mas não dispara nada por 24h; e de
madrugada ele não inicia conversa com ninguém, embora responda quem escrever.

Função pura, sem I/O, como `bot_policy`. O estado efetivo é DERIVADO dos
instantes gravados (`estado()`), nunca lido de um rótulo: o relógio não precisa
de cron para vencer um prazo.

Durante a fase 2 os campos legados (`state`, `attendant_active_until`,
`bot_pausado_por`, `handoff_reason`, `human_handoff_requested_at`) continuam
sendo ESCRITOS, como projeção, porque o painel os lê. Só este módulo os
escreve. Saem na fase 3, junto com os leitores.
"""
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from src.services.business_hours import em_silencio
from src.services.campanha import esta_viva as campanha_viva
from src.utils.phone import normalize_phone

CAMPO = "atendimento"

BOT_ACTIVE = "BOT_ACTIVE"
HUMAN_ACTIVE = "HUMAN_ACTIVE"
HUMAN_EXPIRED = "HUMAN_EXPIRED"   # transitório: só existe entre o vencimento e a avaliação
HUMAN_PENDING = "HUMAN_PENDING"   # fase 3: tarefa aberta, o bot não reassume
COOLDOWN = "COOLDOWN"

# Quanto tempo uma conversa entregue a uma pessoa fica com ela, contado da
# ÚLTIMA MENSAGEM DA CLÍNICA. Decisão do André em 06/09/2026 (24h) e em
# 05/10/2026 (só a clínica renova - mensagem do cliente não).
TTL_HUMANO = 24 * 60 * 60

# Depois que o atendimento humano vence, o bot responde mas não inicia.
COOLDOWN_PADRAO = 24 * 60 * 60

# Quem calou o bot. É o mesmo vocabulário de `bot_policy.PAUSA_*`, e os dois
# têm de concordar porque a projeção legada grava este valor em
# `bot_pausado_por`.
POR_ATENDENTE = "ATENDENTE"            # alguém da clínica respondeu, ou pausou no painel
POR_HANDOFF = "HANDOFF"                # o próprio bot pediu ajuda
POR_INSTABILIDADE = "INSTABILIDADE"    # o sistema falhou
POR_CONTATO_MANUAL = "CONTATO_MANUAL"  # "Já iniciada" no painel
POR_CHAT_ANTERIOR = "CHAT_ANTERIOR"    # já havia conversa antes de nós

# As que o bot pediu, não uma pessoa: o painel as mostra como "aguardando
# especialista", não como "atendente ativa".
ENTREGAS_DO_BOT = frozenset({POR_HANDOFF, POR_INSTABILIDADE})

# Decisão 9.1 do PRD 020 (André, 05/10/2026): NENHUMA pausa é permanente.
# `CONTATO_MANUAL` e `CHAT_ANTERIOR` vencem pelo mesmo TTL, contado da última
# mensagem conhecida (quem chama passa `ate`). Sessão legada sem prazo é
# tratada como vencida há muito: o bot volta a responder se a pessoa
# escrever, e a retomada automática não dispara para ela (idade máxima).

# O que o cron devolve ao avaliar um vencimento.
ACAO_PENDENTE = "pendente"
ACAO_AVALIAR_RETOMADA = "avaliar_retomada"

POLICY_ALL = "ALL"
POLICY_PILOT = "PILOT"
POLICY_LEADS_ONLY = "LEADS_ONLY"
POLICY_OFF = "OFF"


def _agora(agora: Optional[int]) -> int:
    return int(agora if agora is not None else time.time())


# ── Leitura ────────────────────────────────────────────────────────────────

def bloco(session: Optional[Dict]) -> Dict:
    """O bloco `atendimento` da sessão, migrado do legado se ainda não existir.

    Pura: devolve um dict novo, não grava. Sessão antiga migra quando é lida,
    e a que nunca mais for lida não importa - sem script em massa.
    """
    session = session or {}
    atual = session.get(CAMPO)
    if isinstance(atual, dict) and atual.get("handler"):
        return dict(atual)
    return migra_do_legado(session)


def migra_do_legado(session: Dict) -> Dict:
    """Traduz os campos antigos (`attendant_active_until`, `bot_pausado_por`)
    no bloco novo. Mesma regra de `bot_policy.esta_pausado` até aqui."""
    por = session.get("bot_pausado_por")
    ate = session.get("attendant_active_until")
    try:
        ate = int(ate) if ate else None
    except (TypeError, ValueError):
        ate = None

    if por in (POR_CONTATO_MANUAL, POR_CHAT_ANTERIOR) and not ate:
        # Sem data: venceu há muito (9.1). human_until=0 é "no passado".
        return _bloco(HUMAN_ACTIVE, por=por, human_until=0,
                      motivo=session.get("handoff_reason"))
    if ate:
        return _bloco(HUMAN_ACTIVE, por=por or POR_ATENDENTE, human_until=ate,
                      motivo=session.get("handoff_reason"),
                      entregue_em=session.get("human_handoff_requested_at"))
    return _bloco(BOT_ACTIVE)


def _bloco(handler, *, por=None, human_until=None, cooldown_until=None,
           motivo=None, entregue_em=None, versao=0, **extras) -> Dict:
    b = {
        "handler": handler,
        "pausado_por": por,
        "human_until": human_until,
        "cooldown_until": cooldown_until,
        "handoff_reason": motivo,
        "entregue_em": entregue_em,
        "pending_intent": None,
        "pending_task_id": None,
        "pending_since": None,
        "ultima_fala_cliente_em": None,
        "retomada_em": None,
        "alerta": None,
        "retomada_contexto": None,
        "versao": versao,
    }
    b.update(extras)
    return b


def estado(session: Optional[Dict], agora: Optional[int] = None) -> str:
    """O estado EFETIVO agora, derivado dos instantes. Nunca grava.

    `HUMAN_ACTIVE` com `human_until` vencido é `COOLDOWN` enquanto durar o
    cooldown, e `BOT_ACTIVE` depois. `HUMAN_EXPIRED` só aparece quando a
    avaliação da fase 3 precisar dele; aqui o vencimento cai direto em
    cooldown, porque sem pendência é isso que a máquina faz.
    """
    b = bloco(session)
    agora = _agora(agora)
    handler = b.get("handler")

    if handler == HUMAN_PENDING:
        return HUMAN_PENDING

    if handler == HUMAN_ACTIVE:
        ate = b.get("human_until")
        if ate is None or int(ate) > agora:
            return HUMAN_ACTIVE
        # Venceu. Com pendência, a conversa fica com uma pessoa (a tarefa):
        # o bot não reassume assunto em aberto (PRD 020 §3.6).
        if b.get("pending_intent") or b.get("pending_task_id"):
            return HUMAN_PENDING
        # Sem pendência, o cooldown conta do vencimento.
        if agora < int(ate) + COOLDOWN_PADRAO:
            return COOLDOWN
        return BOT_ACTIVE

    if handler == COOLDOWN:
        ate = b.get("cooldown_until")
        if ate and int(ate) > agora:
            return COOLDOWN
        return BOT_ACTIVE

    return BOT_ACTIVE


def esta_com_pessoa(session: Optional[Dict], agora: Optional[int] = None) -> bool:
    """A conversa está com uma pessoa (ativa ou com tarefa aberta)? É o
    `esta_pausado` de antes, com nome que diz o que afirma."""
    return estado(session, agora) in (HUMAN_ACTIVE, HUMAN_PENDING)


def aguarda_especialista(session: Optional[Dict], agora: Optional[int] = None) -> bool:
    """O BOT entregou (handoff ou instabilidade) e ninguém assumiu ainda."""
    if not esta_com_pessoa(session, agora):
        return False
    return bloco(session).get("pausado_por") in ENTREGAS_DO_BOT


# ── As duas perguntas ──────────────────────────────────────────────────────

def _politica_permite(clinic: Dict, session: Dict, phone: str) -> bool:
    """A política da clínica (ALL, PILOT, LEADS_ONLY, OFF) cobre esta conversa?

    Política ausente equivale a ALL: uma clínica lida antes da migration não
    pode ficar sem bot. OFF e valor inesperado falham fechado.
    """
    policy = clinic.get("bot_autoreply_policy") or POLICY_ALL
    if policy == POLICY_ALL:
        return True
    if policy == POLICY_PILOT:
        piloto = {normalize_phone(p) for p in (clinic.get("bot_pilot_phones") or [])}
        return normalize_phone(phone) in piloto
    if policy == POLICY_LEADS_ONLY:
        # Dois caminhos para a mesma política: lead da landing page que escreveu
        # (`bot_enabled`) ou paciente para quem NÓS escrevemos (campanha viva).
        return bool(session.get("bot_enabled")) or campanha_viva(session)
    return False


def pode_responder(clinic: Optional[Dict], session: Optional[Dict], phone: str,
                   agora: Optional[int] = None) -> bool:
    """Alguém escreveu. O bot pode responder?

    Ordem: a clínica desligou o bot -> não; a conversa está com uma pessoa ->
    não; a política não cobre -> não. Cooldown e horário NÃO entram: quem
    escreveu está do outro lado esperando.
    """
    clinic = clinic or {}
    session = session or {}
    if clinic.get("bot_paused"):
        return False
    if esta_com_pessoa(session, agora):
        return False
    return _politica_permite(clinic, session, phone)


def pode_iniciar(clinic: Optional[Dict], session: Optional[Dict], phone: str,
                 agora: Optional[int] = None, *, transacional: bool = False) -> bool:
    """Ninguém escreveu. O bot pode falar primeiro?

    Tudo de `pode_responder`, mais: em COOLDOWN não inicia, e na janela de
    silêncio não inicia. `transacional=True` pula SÓ o cooldown, e tem dois
    chamadores: o lembrete de 24h da sessão marcada (a sessão existe e a
    pessoa precisa saber) e a retomada por vencimento (ela É a transição que
    abre o cooldown; barrá-la pelo cooldown seria circular). Um terceiro
    chamador é sinal de que a mensagem não é nenhuma das duas coisas. A janela
    de silêncio vale SEMPRE, inclusive para eles.
    """
    agora = _agora(agora)
    if not pode_responder(clinic, session, phone, agora):
        return False
    if not transacional and estado(session, agora) == COOLDOWN:
        return False
    instante = datetime.fromtimestamp(agora, tz=timezone.utc)
    if em_silencio(clinic, instante):
        return False
    return True


# ── Transições ─────────────────────────────────────────────────────────────
#
# Cada uma devolve a sessão mutada. `versao` é a lida do banco; quem grava usa
# `session_store.grava_atendimento`, condicionado à versão lida, porque duas
# Lambdas escrevem a mesma sessão (webhook assíncrono e, na fase 3, o cron de
# vencimento) e um put cego faria COOLDOWN sobrescrever HUMAN_ACTIVE calado.

def _comete(session: Dict, b: Dict) -> Dict:
    # `versao` NAO sobe aqui. Ela conta escritas no banco, nao transicoes em
    # memoria: quem sobe e `grava_atendimento`, na escrita condicional. Subir
    # por transicao quebrava qualquer cadeia (alerta + encerra, contexto +
    # retomada): a segunda transicao esperava uma versao que o banco nunca
    # teve, e o cron descartou toda retomada em prod em 08/10/2026.
    b["versao"] = int(b.get("versao") or 0)
    session[CAMPO] = b
    _projeta_no_legado(session, b)
    return session


def _projeta_no_legado(session: Dict, b: Dict) -> None:
    """Os campos antigos, escritos a partir do bloco - nunca à mão. O painel
    ainda os lê (fase 2); somem na fase 3 junto com os leitores."""
    if b["handler"] in (HUMAN_ACTIVE, HUMAN_PENDING):
        por = b.get("pausado_por") or POR_ATENDENTE
        session["state"] = "HUMAN_HANDOFF" if por in ENTREGAS_DO_BOT else "HUMAN_ATTENDANT_ACTIVE"
        session["bot_pausado_por"] = por
        if b.get("human_until") is not None:
            session["attendant_active_until"] = int(b["human_until"])
        else:
            session.pop("attendant_active_until", None)
        if b.get("handoff_reason"):
            session["handoff_reason"] = b["handoff_reason"]
        if b.get("entregue_em"):
            session["human_handoff_requested_at"] = int(b["entregue_em"])
    else:
        for campo in ("attendant_active_until", "bot_pausado_por", "handoff_reason",
                      "human_handoff_requested_at", "_previous_state_before_attendant"):
            session.pop(campo, None)
        if session.get("state") in ("HUMAN_HANDOFF", "HUMAN_ATTENDANT_ACTIVE"):
            session["state"] = ""


def entrega_a_humano(session: Optional[Dict], *, por: str, motivo: Optional[str] = None,
                     agora: Optional[int] = None, ate: Optional[int] = None,
                     pending_intent: Optional[str] = None) -> Dict:
    """A conversa passa a uma pessoa. `ate=None` com `por` permanente
    (CONTATO_MANUAL, CHAT_ANTERIOR) não vence; qualquer outro vence em TTL.

    Já entregue: renova o prazo e mantém o motivo original, a menos que venha
    um novo - o primeiro motivo é o que a fila precisa ver.
    """
    session = session if session is not None else {}
    agora = _agora(agora)
    b = bloco(session)

    if ate is None:
        ate = agora + TTL_HUMANO

    if estado(session, agora) == HUMAN_ACTIVE:
        b["human_until"] = ate if ate is not None else b.get("human_until")
        if motivo:
            b["handoff_reason"] = motivo
        if pending_intent:
            b["pending_intent"] = pending_intent
            b["pending_since"] = b.get("pending_since") or agora
        return _comete(session, b)

    novo = _bloco(
        HUMAN_ACTIVE, por=por, human_until=ate, motivo=motivo, entregue_em=agora,
        versao=b.get("versao", 0),
        ultima_fala_cliente_em=b.get("ultima_fala_cliente_em"),
        pending_intent=pending_intent, pending_since=agora if pending_intent else None,
    )
    return _comete(session, novo)


def renova_por_mensagem_da_clinica(session: Optional[Dict], agora: Optional[int] = None) -> Dict:
    """Alguém da clínica falou: o prazo humano conta de novo. Se a conversa
    não estava com pessoa, passa a estar (por ATENDENTE)."""
    session = session if session is not None else {}
    agora = _agora(agora)
    if estado(session, agora) != HUMAN_ACTIVE:
        return entrega_a_humano(session, por=POR_ATENDENTE, agora=agora)
    b = bloco(session)
    b["human_until"] = agora + TTL_HUMANO
    return _comete(session, b)


def registra_fala_do_cliente(session: Optional[Dict], agora: Optional[int] = None) -> Dict:
    """O cliente escreveu. NÃO renova o prazo humano - só marca quando foi,
    para a retomada (fase 3) saber se ficou pergunta sem resposta. Em
    COOLDOWN, a conversa volta ao bot: ele vai responder."""
    session = session if session is not None else {}
    agora = _agora(agora)
    b = bloco(session)
    b["ultima_fala_cliente_em"] = agora
    if estado(session, agora) == COOLDOWN:
        b = _bloco(BOT_ACTIVE, versao=b.get("versao", 0), ultima_fala_cliente_em=agora)
    elif estado(session, agora) == BOT_ACTIVE and b.get("handler") != BOT_ACTIVE:
        # Prazos vencidos de um atendimento antigo: materializa o BOT_ACTIVE.
        b = _bloco(BOT_ACTIVE, versao=b.get("versao", 0), ultima_fala_cliente_em=agora)
    return _comete(session, b)


def retoma_pelo_painel(session: Optional[Dict]) -> Dict:
    """"Retomar bot": limpa tudo, de qualquer estado, e a conversa volta ao
    bot sem cooldown - quem clicou decidiu que ele pode falar."""
    session = session if session is not None else {}
    b = bloco(session)
    return _comete(session, _bloco(BOT_ACTIVE, versao=b.get("versao", 0),
                                   ultima_fala_cliente_em=b.get("ultima_fala_cliente_em")))


def avalia_vencimento(session: Optional[Dict], agora: Optional[int] = None):
    """O cron encontrou `human_until` vencido. Devolve (session, ação).

    Com pendência (intenção que o bot não atendeu ou tarefa aberta), a
    conversa vai para HUMAN_PENDING e fica lá até alguém fechar a tarefa ou
    clicar "Retomar bot". Sem pendência, devolve ACAO_AVALIAR_RETOMADA: quem
    chama roda as guardas de `retomada` e então encerra em cooldown.
    """
    session = session if session is not None else {}
    agora = _agora(agora)
    b = bloco(session)
    if b.get("pending_intent") or b.get("pending_task_id"):
        b["handler"] = HUMAN_PENDING
        return _comete(session, b), ACAO_PENDENTE
    return session, ACAO_AVALIAR_RETOMADA


def vincula_tarefa(session: Optional[Dict], tarefa_id: str) -> Dict:
    session = session if session is not None else {}
    b = bloco(session)
    b["pending_task_id"] = str(tarefa_id)
    return _comete(session, b)


def fecha_pendencia(session: Optional[Dict], agora: Optional[int] = None) -> Dict:
    """Tarefa fechada no painel: HUMAN_PENDING -> COOLDOWN, pendência limpa."""
    session = session if session is not None else {}
    agora = _agora(agora)
    b = bloco(session)
    novo = _bloco(COOLDOWN, cooldown_until=agora + COOLDOWN_PADRAO, versao=b.get("versao", 0),
                  ultima_fala_cliente_em=b.get("ultima_fala_cliente_em"),
                  retomada_em=b.get("retomada_em"))
    return _comete(session, novo)


def marca_retomada(session: Optional[Dict], agora: Optional[int] = None) -> Dict:
    """Uma retomada por pendência: quem já foi retomado não é de novo."""
    session = session if session is not None else {}
    b = bloco(session)
    b["retomada_em"] = _agora(agora)
    return _comete(session, b)


def marca_alerta(session: Optional[Dict], motivo: str) -> Dict:
    """A última fala era do cliente e o bot decidiu calar: a fila precisa ver."""
    session = session if session is not None else {}
    b = bloco(session)
    b["alerta"] = motivo
    return _comete(session, b)


def poe_contexto_de_retomada(session: Optional[Dict], texto: str) -> Dict:
    session = session if session is not None else {}
    b = bloco(session)
    b["retomada_contexto"] = texto
    return _comete(session, b)


def limpa_contexto_de_retomada(session: Optional[Dict]) -> Dict:
    session = session if session is not None else {}
    b = bloco(session)
    if b.get("retomada_contexto"):
        b["retomada_contexto"] = None
        return _comete(session, b)
    return session


def encerra_atendimento_humano(session: Optional[Dict], agora: Optional[int] = None) -> Dict:
    """O atendimento humano acabou (prazo vencido e avaliado): COOLDOWN
    explícito, contado de agora. Usado pela avaliação de vencimento (fase 3)."""
    session = session if session is not None else {}
    agora = _agora(agora)
    b = bloco(session)
    novo = _bloco(COOLDOWN, cooldown_until=agora + COOLDOWN_PADRAO, versao=b.get("versao", 0),
                  ultima_fala_cliente_em=b.get("ultima_fala_cliente_em"),
                  retomada_em=b.get("retomada_em"), alerta=b.get("alerta"))
    return _comete(session, novo)
