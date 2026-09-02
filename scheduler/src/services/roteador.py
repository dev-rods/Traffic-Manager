"""Que consulta a pergunta do cliente exige antes de qualquer resposta.

O agente decide sozinho quando chamar uma tool, e em 02/09/2026 decidiu que não
precisava: respondeu sobre um agendamento a partir do que ele mesmo dissera três
dias antes. O agendamento tinha sido cancelado no meio.

Aqui a decisão sai do modelo. Se a pergunta é sobre agenda, preço ou
disponibilidade, a consulta acontece antes de ele escrever a primeira palavra, e
o resultado entra no contexto como a única fonte válida.

A classificação é por padrão de texto, sem chamada de LLM: é barata, roda em
microssegundos e dá o mesmo resultado toda vez - o oposto do problema que ela
resolve. Os padrões saíram de 180 mensagens reais de clientes da Essência.
"""
import re
import unicodedata

AGENDAMENTO_PROPRIO = "AGENDAMENTO_PROPRIO"
PRECO = "PRECO"
DISPONIBILIDADE = "DISPONIBILIDADE"

# Cada padrão foi conferido contra as conversas reais. Ampliar sem esse
# lastro aumenta a latência de todas as respostas sem ganho conhecido.
PADROES = {
    AGENDAMENTO_PROPRIO: (
        r"\b(minha|meu|minhas|meus)\s+(sessao|sessoes|agendamento|agendamentos|horario|consulta)"
        r"|quando\s+(e|sera|vai ser)\s+(minha|meu|a minha|o meu)"
        r"|proxim[ao]\s+(sessao|agendamento|consulta|visita)"
        r"|est[aá]\s+confirmad"
        r"|confirma(r|)\s+(as\s+)?informacoes"
        r"|\b(remarcar|reagendar|cancelar)\b"
    ),
    PRECO: (
        r"\bquanto\s+(custa|fica|sai|e|esta|ficaria)"
        r"|\bvalor(es|)\b"
        r"|\bpreco(s|)\b"
        r"|tabela\s+de\s+preco"
    ),
    DISPONIBILIDADE: (
        r"\b(tem|teria|tem alguma|ha)\s+(horario|vaga|data|dia)"
        r"|quais\s+(as\s+)?(datas|horarios|dias)"
        r"|\bdisponi(vel|veis|bilidade)\b"
        r"|\b(agendar|marcar)\b"
        r"|que\s+dia"
    ),
}

TOOLS_POR_INTENCAO = {
    AGENDAMENTO_PROPRIO: ["lookup_appointments"],
    PRECO: ["list_services", "list_areas"],
    DISPONIBILIDADE: ["check_availability"],
}


def _normaliza(texto):
    plano = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in plano if not unicodedata.combining(c))


def intencoes(mensagem):
    """As intenções presentes na mensagem que exigem consulta ao banco.

    Conjunto vazio significa conversa comum - nenhuma pré-carga, nenhuma
    latência extra.
    """
    plano = _normaliza(mensagem)
    if not plano.strip():
        return set()
    return {nome for nome, padrao in PADROES.items() if re.search(padrao, plano)}


def tools_obrigatorias(intencoes_detectadas):
    """As tools que precisam ser consultadas antes de responder.

    Ordem estável para o contexto ficar reproduzível entre execuções.
    """
    tools = []
    for nome in sorted(intencoes_detectadas or []):
        for tool in TOOLS_POR_INTENCAO.get(nome, []):
            if tool not in tools:
                tools.append(tool)
    return tools
