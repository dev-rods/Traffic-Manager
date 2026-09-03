"""Quanto tempo dura uma sessão. Única autoridade sobre isso.

Antes havia quatro respostas diferentes para a mesma pergunta: as faixas por
quantidade de áreas, a soma das durações cadastradas por área, o `SUM` do
fallback de reagendamento e o número que o próprio agente inventava. Em
02/09/2026 o agente pediu horários para uma sessão de *4 minutos* e nada barrou.

Agora a resposta é uma só, e é derivada, nunca informada:

    soma das durações das áreas → arredonda para cima ao passo → aplica piso e teto

Arredonda para CIMA de propósito. Subestimar a duração agenda duas pessoas em
cima da mesma janela; superestimar só desperdiça um vão. Entre os dois erros, o
segundo é o barato.

O agente não opina sobre duração: as tools recebem quais áreas a pessoa
escolheu, que é o que ele de fato sabe, e a duração sai daqui.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Padrão da Essência, usado quando a clínica não tem regra própria cadastrada.
DEFAULT_DURATION_RULES = {
    "floor_minutes": 15,     # nenhuma sessão é mais curta que isto
    "ceiling_minutes": 50,   # nenhuma sessão é mais longa que isto
    "step_minutes": 5,       # toda duração é múltiplo disto
    "is_active": True,
}


def arredonda_para_passo(minutos: int, passo: int) -> int:
    """O menor múltiplo de `passo` que não é menor que `minutos`.

    Passo inválido devolve o valor intacto: uma configuração ruim não pode
    zerar a duração de um agendamento.
    """
    if passo <= 0:
        return int(minutos)
    return -(-int(minutos) // int(passo)) * int(passo)


def duracao_da_sessao(soma_minutos, rules: Optional[Dict] = None) -> int:
    """A duração final, a partir da soma bruta das áreas.

    Arredonda antes de aplicar piso e teto: assim os limites saem exatos, e não
    empurrados para o próximo múltiplo. Piso e teto configurados fora do passo
    são respeitados como estão - quem escreveu 47 no painel quis 47.
    """
    if not rules or not rules.get("is_active", True):
        rules = DEFAULT_DURATION_RULES

    def valor(chave):
        v = rules.get(chave)
        return DEFAULT_DURATION_RULES[chave] if v is None else int(v)

    piso, teto, passo = valor("floor_minutes"), valor("ceiling_minutes"), valor("step_minutes")

    # Piso acima do teto é configuração impossível: o piso vence, porque uma
    # sessão curta demais quebra o atendimento e uma longa demais só ocupa agenda.
    if piso > teto:
        logger.warning(f"[DurationRules] piso {piso} > teto {teto}; usando o piso")
        teto = piso

    bruto = max(int(soma_minutos or 0), 0)
    return max(piso, min(teto, arredonda_para_passo(bruto, passo)))


def soma_das_areas(db, service_area_pairs: List[Dict]) -> int:
    """Soma bruta das durações das áreas escolhidas, antes de qualquer limite.

    Usa a duração específica da área quando existe e cai na do serviço quando
    não - o mesmo COALESCE que a listagem de áreas expõe como
    `effective_duration_minutes`, para a tela e a agenda não discordarem.

    Par que não casar com nenhuma linha simplesmente não soma: é área removida
    do catálogo, e derrubar o agendamento por isso seria pior.
    """
    pares = [p for p in (service_area_pairs or []) if p.get("service_id") and p.get("area_id")]
    if not pares:
        return 0

    valores = ", ".join(["(%s::uuid, %s::uuid)"] * len(pares))
    params: tuple = ()
    for p in pares:
        params += (p["service_id"], p["area_id"])

    rows = db.execute_query(
        f"""SELECT COALESCE(SUM(COALESCE(sa.duration_minutes, s.duration_minutes)), 0) AS total
        FROM (VALUES {valores}) AS pares(service_id, area_id)
        JOIN scheduler.services s ON s.id = pares.service_id AND s.active = TRUE
        LEFT JOIN scheduler.service_areas sa
               ON sa.service_id = pares.service_id
              AND sa.area_id = pares.area_id
              AND sa.active = TRUE""",
        params,
    )
    return int(rows[0]["total"]) if rows and rows[0]["total"] else 0


def calcula_duracao(db, clinic_id: str, service_area_pairs: List[Dict]) -> int:
    """A duração de uma sessão para as áreas escolhidas. Ponto de entrada único.

    Todo caminho de agendamento - chat, painel, criação, reagendamento - passa
    por aqui. Sem áreas, devolve o piso: é o caso do serviço sem área detalhada,
    que continua ocupando o mínimo de agenda.
    """
    rules = get_duration_rules(db, clinic_id)
    return duracao_da_sessao(soma_das_areas(db, service_area_pairs), rules)


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
