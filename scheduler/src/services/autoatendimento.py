# -*- coding: utf-8 -*-
"""Onde a pessoa resolve o proprio agendamento sem falar com ninguem.

"Meus agendamentos" vive na Home do booking-site. Com dominio proprio da
clinica a raiz JA e a clinica; sem dominio, nao ha link: o bot volta a
cancelar e remarcar pela conversa (decisao do Andre em 27/10/2026). O dominio
Vercel padrao fica de fora de proposito; se um dia servir, e uma env var aqui,
num lugar so.
"""
from typing import Optional


def link_de_autoatendimento(clinic: Optional[dict]) -> Optional[str]:
    dominio = ((clinic or {}).get("custom_domain") or "").strip()
    if not dominio:
        return None
    dominio = dominio.replace("https://", "").replace("http://", "").rstrip("/")
    return f"https://{dominio}/"
