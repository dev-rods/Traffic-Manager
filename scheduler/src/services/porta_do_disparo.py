# -*- coding: utf-8 -*-
"""A porta de quem fala PRIMEIRO com o bot na frente: o disparo em lote e o
lembrete de sessao. Um lugar so, para os dois recusarem e destravarem igual.

Estados que o disparo com bot DESTRAVA em vez de recusar. Sao os mesmos que
o botao "Retomar bot" limpa: quem marcou "o bot conduz" na tela decidiu que
ele pode falar com esta pessoa, e a pausa de 24h que uma resposta pelo
celular deixa nao e motivo para o disparo falhar (19/10/2026: um envio da
Essencia voltou "atendimento_humano" e a tela so disse "Falhou").

Bot da clinica pausado e janela de silencio continuam recusando: um e
decisao da clinica inteira, o outro e horario.
"""
from datetime import datetime, timezone
from typing import Optional

from src.services import atendimento
from src.services.business_hours import em_silencio

MOTIVOS_QUE_O_DISPARO_DESTRAVA = frozenset({"atendimento_humano", "cooldown"})


def motivo_para_nao_iniciar(clinic, sessao, agora: int) -> Optional[str]:
    """Por que o bot NAO pode assumir esta conversa agora; None se pode.

    Olha so o ESTADO da conversa. A politica da clinica (ALL, PILOT,
    LEADS_ONLY) fica de fora de proposito: quem decide que o bot assume este
    disparo e o operador, na tela, e e o proprio disparo que abre a campanha
    que a politica exigiria. Consulta-la aqui recusou 89 pacientes da Essencia
    em 15/10/2026 com o motivo generico "politica" - em LEADS_ONLY, nenhuma
    sessao nova tem campanha viva ANTES de a campanha ser aberta.
    """
    if (clinic or {}).get("bot_paused"):
        return "bot_da_clinica_pausado"
    if atendimento.esta_com_pessoa(sessao, agora):
        return "atendimento_humano"
    if atendimento.estado(sessao, agora) == atendimento.COOLDOWN:
        return "cooldown"
    if em_silencio(clinic, datetime.fromtimestamp(agora, tz=timezone.utc)):
        return "janela_de_silencio"
    return None
