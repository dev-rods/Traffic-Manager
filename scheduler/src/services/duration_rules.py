"""Duração da sessão calculada pela quantidade de áreas.

Antes a duração era a soma das durações cadastradas em `service_areas`, o que
produzia números irreais: seis áreas de 10 minutos viravam uma sessão de 60,
quando na prática o atendimento leva 35. O laser é aplicado em sequência e boa
parte do tempo é de preparo, que não se repete a cada área.

As faixas são editáveis por clínica em `scheduler.duration_rules`, no mesmo
formato de `discount_rules` — inclusive as fronteiras, não só os minutos.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Padrão da Essência, usado quando a clínica não tem regra própria cadastrada.
DEFAULT_DURATION_RULES = {
    "base_duration_minutes": 15,     # 1 área, e piso de qualquer atendimento
    "tier_2_min_areas": 2,
    "tier_2_max_areas": 3,
    "tier_2_duration_minutes": 20,
    "tier_3_min_areas": 4,
    "tier_3_max_areas": 6,
    "tier_3_duration_minutes": 35,
    "tier_4_min_areas": 7,           # sem máximo: é a última faixa
    "tier_4_duration_minutes": 45,
    "is_active": True,
}


def duration_for_areas(area_count: int, rules: Optional[Dict]) -> int:
    """Minutos de sessão para uma quantidade de áreas.

    Percorre as faixas da maior para a menor e devolve a primeira cuja abertura
    já foi alcançada. Ler de cima para baixo faz a configuração com lacuna cair
    na faixa anterior em vez de escorregar para a base: subestimar a duração
    criaria conflito de horário na agenda, que é o pior dos dois erros.

    `rules` ausente, vazio ou inativo cai no padrão do código — clínica sem
    configuração continua agendando.
    """
    if not rules or not rules.get("is_active", True):
        rules = DEFAULT_DURATION_RULES

    def valor(chave):
        v = rules.get(chave)
        return DEFAULT_DURATION_RULES[chave] if v is None else v

    base = int(valor("base_duration_minutes"))
    if area_count <= 1:
        return base

    faixas = (
        (int(valor("tier_4_min_areas")), int(valor("tier_4_duration_minutes"))),
        (int(valor("tier_3_min_areas")), int(valor("tier_3_duration_minutes"))),
        (int(valor("tier_2_min_areas")), int(valor("tier_2_duration_minutes"))),
    )
    for minimo, minutos in faixas:
        if area_count >= minimo:
            return minutos

    return base


def get_duration_rules(db, clinic_id: str) -> Dict:
    """Regras da clínica, ou o padrão do código se não houver nenhuma.

    Nunca levanta: uma falha ao ler a configuração não pode impedir agendamento.
    """
    try:
        rows = db.execute_query(
            "SELECT * FROM scheduler.duration_rules WHERE clinic_id = %s AND is_active = TRUE",
            (clinic_id,),
        )
        if rows:
            return rows[0]
    except Exception as e:
        logger.warning(f"[DurationRules] Falha ao ler regras de {clinic_id}, usando padrão: {e}")
    return DEFAULT_DURATION_RULES
