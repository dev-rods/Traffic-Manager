# -*- coding: utf-8 -*-
"""Aviso imediato quando a política cala o bot (PRD 064, decisão P5).

Nobre em `LEADS_ONLY`: quem escreve por conta própria espera alguém da
clínica apertar "Retomar bot". Em 24/11/2026 uma lead esperou 44 minutos por
"quanto é a virilha?"; em 30 dias foram 1.768 mensagens sem resposta
automática. O André decidiu manter a política e mandar, na hora, um aviso
caloroso de que uma especialista vai responder.

O aviso NÃO é atendimento do bot: sai como envio do sistema (origem
AVISO_DE_ESPERA), não muda o `handler`, e a retomada o ignora ao decidir se
há pergunta em aberto. Uma vez por conversa a cada 24 h.
"""
import logging
import time
from typing import Dict, Optional

from src.services import atendimento
from src.services.envio_do_sistema import AVISO_DE_ESPERA, envia_texto

logger = logging.getLogger(__name__)

CAMPO = "aviso_de_espera_em"
INTERVALO_HORAS = 24
TEMPLATE = "AVISO_DE_ESPERA"


def deve_enviar(clinic: Optional[Dict], session: Optional[Dict], phone: str, *,
                silenciado: bool = False, agora: Optional[int] = None) -> bool:
    """Só quando a ÚNICA porta fechada é a política da clínica, e não houve
    aviso nas últimas 24 h."""
    if atendimento.motivo_da_recusa(clinic, session, phone, agora, silenciado=silenciado) != atendimento.RECUSA_POLITICA:
        return False
    agora = int(agora if agora is not None else time.time())
    try:
        ultimo = int((session or {}).get(CAMPO) or 0)
    except (TypeError, ValueError):
        ultimo = 0
    return agora - ultimo >= INTERVALO_HORAS * 3600


def texto(template_service, clinic: Dict) -> str:
    nome = clinic.get("display_name") or clinic.get("name") or "clínica"
    return template_service.get_and_render(clinic["clinic_id"], TEMPLATE, {"clinic_display_name": nome})


def envia(clinic: Dict, phone: str, template_service, session: Dict, *, tracker=None,
          agora: Optional[int] = None) -> bool:
    """Manda o aviso e marca a hora na sessão (em memória; quem persiste é o
    chamador, via `grava_atendimento(..., extras={CAMPO: ...})`)."""
    try:
        result = envia_texto(clinic, phone, texto(template_service, clinic), AVISO_DE_ESPERA, tracker=tracker)
        enviado = bool(getattr(result, "success", False))
    except Exception as e:  # noqa: BLE001
        logger.error(f"[AvisoDeEspera] {phone}: falha ao enviar: {e}")
        enviado = False
    if enviado:
        session[CAMPO] = int(agora if agora is not None else time.time())
        logger.info(f"[AvisoDeEspera] {phone}: aviso enviado (politica cala o bot)")
    return enviado
