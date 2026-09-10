# -*- coding: utf-8 -*-
"""A campanha mensal de reagendamento da base já cadastrada.

Todo início de mês a clínica dispara, pelo painel, as datas de laser abertas
para quem está sem agendamento futuro. Deste disparo em diante o bot assume a
conversa e fecha o agendamento.

O modo NUNCA é inferido pelo modelo: é gravado no ato do disparo e lido daqui.
Modelo inferindo em que fluxo está pode trocar de fluxo no meio da conversa, e
o erro chega à paciente como "o bot me pediu o CPF de novo".

Por que a campanha VENCE, e por que isso não é detalhe:

A tabela de sessões está com TTL desabilitado - sessão gravada não expira
nunca. Se a elegibilidade viesse de uma marca permanente, cada campanha mensal
deixaria um rastro de pacientes que o bot atende para sempre, inclusive daqui a
seis meses num assunto qualquer, em modo LEAD, pedindo CPF de quem já é
cadastrada. Em poucos meses a trava LEADS_ONLY viraria decorativa - e sem
sintoma visível, porque o bot simplesmente responderia mais gente a cada mês.
Vencendo, a trava volta sozinha.

Função pura, sem I/O, como `bot_policy`: é a regra que muda a cada rodada da
campanha e precisa ser testável sem subir webhook.
"""
import time
from typing import Dict, List, Optional

MODO_REAGENDAMENTO = "REAGENDAMENTO"

# Decisão do André em 09/09/2026.
DURACAO_PADRAO_DIAS = 7
MAX_DATAS = 3


def abre(datas: List[str], dias: int = DURACAO_PADRAO_DIAS,
         agora: Optional[int] = None) -> Dict:
    """Monta a campanha que será gravada na sessão da paciente.

    `agora` injetável para o teste não depender do relógio.
    """
    if not datas:
        raise ValueError("campanha sem datas")

    agora = int(agora if agora is not None else time.time())
    return {
        "modo": MODO_REAGENDAMENTO,
        "expira_em": agora + dias * 86400,
        "datas": list(datas[:MAX_DATAS]),
    }


def esta_viva(session: Optional[Dict], agora: Optional[int] = None) -> bool:
    """Há campanha aberta e dentro do prazo nesta conversa?

    Falha fechada em toda dúvida - campanha ausente, malformada, sem prazo ou
    com prazo ilegível. O custo dos dois erros é assimétrico: não responder faz
    a atendente responder à mão, como já faz hoje; responder quando não devia
    solta o bot numa conversa que não é dele.
    """
    campanha = (session or {}).get("campanha")
    if not isinstance(campanha, dict):
        return False

    try:
        expira_em = int(campanha["expira_em"])
    except (KeyError, TypeError, ValueError):
        return False

    agora = int(agora if agora is not None else time.time())
    return expira_em > agora


def datas_da_campanha(session: Optional[Dict], agora: Optional[int] = None) -> List[str]:
    """As datas anunciadas, ou nada se a campanha morreu.

    Amarrado ao prazo de propósito: data de campanha vencida é data de um mês
    que já passou, e oferecê-la é pior do que não oferecer nada.
    """
    if not esta_viva(session, agora):
        return []
    datas = (session or {}).get("campanha", {}).get("datas")
    return list(datas) if isinstance(datas, list) else []
