# -*- coding: utf-8 -*-
"""As orientações de preparo e de pós-sessão que estão no FAQ da clínica.

Fechar o agendamento e não dizer como se preparar é o erro que só aparece no
dia: a paciente chega com a pele bronzeada, ou depilada com cera na véspera, e a
sessão não pode ser feita. O horário vira buraco na agenda.

A clínica já escreve isso - está no FAQ, que ela mantém. O que faltava era o bot
entregar sem depender de a paciente perguntar. Regra, decidida pelo André em
13/09/2026: todo agendamento concluído termina com as orientações pré e
pós-procedimento do FAQ, com prioridade para as de preparo antes da sessão.

O filtro é por palavra no texto do FAQ, e roda em Python de propósito: o banco
não tem `unaccent` garantido, e a base de uma clínica são dezenas de itens, não
milhares. Nunca inventa orientação - clínica sem FAQ de preparo não recebe nada.
"""
import logging
import re
import unicodedata
from typing import Dict, List

logger = logging.getLogger(__name__)

# Ordenado: preparo primeiro, porque é o que muda a conduta da paciente ANTES
# da sessão - e é o que o André pediu para vir em destaque.
PREPARO = (
    r"prepar|antes da sessao|antes do procedimento|pre sessao|pre procedimento|"
    r"vespera|bronze|sol\b|cera|lamina|raspar|depilar|barbear|"
    r"nao pode fazer|contraindic"
)
POS = (
    r"\bpos\b|depois da sessao|depois do procedimento|apos a sessao|"
    r"apos o procedimento|cuidado|recomenda|orienta"
)


def _normaliza(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", (texto or "").lower())
    sem_acento = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sem_acento)


def busca(db, clinic_id: str) -> List[Dict]:
    """Os itens de FAQ que são orientação de preparo ou de pós-procedimento.

    Preparo vem antes; dentro de cada grupo, a ordem é a que a clínica definiu.
    """
    try:
        linhas = db.execute_query(
            """
            SELECT question_label, answer
            FROM scheduler.faq_items
            WHERE clinic_id = %s AND active = true
            ORDER BY display_order
            """,
            (clinic_id,),
        ) or []
    except Exception as e:
        # Sem as orientações o agendamento continua válido. Derrubar a
        # confirmação por causa de uma consulta ao FAQ seria trocar o essencial
        # pelo complemento.
        logger.error(f"[OrientacoesFAQ] Falha ao ler o FAQ de {clinic_id}: {e}")
        return []

    de_preparo, de_pos = [], []
    for linha in linhas:
        texto = _normaliza(f"{linha.get('question_label') or ''} {linha.get('answer') or ''}")
        item = {
            "pergunta": linha.get("question_label") or "",
            "resposta": linha.get("answer") or "",
            "tipo": "preparo",
        }
        if re.search(PREPARO, texto):
            de_preparo.append(item)
        elif re.search(POS, texto):
            de_pos.append(dict(item, tipo="pos"))
    return de_preparo + de_pos


def como_texto(itens: List[Dict]) -> str:
    """As orientações prontas para ir na mensagem do fluxo determinístico."""
    return "\n\n".join(
        f"*{i['pergunta']}*\n{i['resposta']}".strip() for i in itens or []
    )
