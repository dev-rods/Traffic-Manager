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
DURACAO = "DURACAO"

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
    # "Quanto tempo dura?" não casava com nada, e o agente respondia de memória.
    # A pergunta é comum e a resposta é derivada: tem que passar por tool.
    DURACAO: (
        r"quanto\s+tempo"
        r"|\bdura(cao|)\b"
        r"|\bdemora\b"
        r"|\bleva\s+quanto"
        r"|\bduram\b"
        r"|quantos?\s+minutos"
    ),
    DISPONIBILIDADE: (
        r"\b(tem|teria|tem alguma|ha)\s+(horario|vaga|data|dia)"
        r"|quais\s+(as\s+)?(datas|horarios|dias)"
        r"|\bdisponi(vel|veis|bilidade)\b"
        r"|\b(agendar|marcar)\b"
        r"|que\s+dia"
    ),
}

# Só entram aqui tools que respondem sem argumento. check_availability e
# calculate_duration dependem das áreas que a pessoa escolheu, que só existem na
# conversa - pré-carregá-las com argumento vazio devolveria o piso de 15 minutos
# como se fosse a duração real, que é mentira com cara de dado consultado.
TOOLS_POR_INTENCAO = {
    AGENDAMENTO_PROPRIO: ["lookup_appointments"],
    PRECO: ["list_services", "list_areas"],
    DISPONIBILIDADE: ["list_areas"],
    DURACAO: ["list_areas"],
}


# A lista do que NÃO exige consulta. É o inverso do desenho anterior, e de
# propósito: classificar todo assunto factual é uma lista infinita - "E horários
# à tarde?" não casava com nada e o bot inventou dez horários. Classificar
# conversa fiada é uma lista curta e estável, e errar para o lado de consultar
# custa uma chamada de tool, não uma paciente na porta em dia que não existe.
SOCIAL = (
    r"^(oi|ola|opa|eae|e ai|bom dia|boa tarde|boa noite|tudo bem|tudo bom|"
    r"sim|nao|ok|okay|blz|beleza|certo|claro|perfeito|otimo|show|fechado|"
    r"isso|isso mesmo|exato|combinado|entendi|entendido|uhum|aham|"
    r"obrigad[ao]|vlw|valeu|brigad[ao]|de nada|imagina|"
    r"tchau|ate mais|ate logo|abraco|bjs|bjos|falou)"
    r"[\s!.,?]*$"
)

# Respostas de cadastro: nome, data, CPF, e-mail. A pessoa está entregando um
# dado, não perguntando nada - forçar tool aqui faria o agente consultar a
# agenda no meio do preenchimento do formulário.
#
# O nome é reconhecido pelas MAIÚSCULAS no texto original, não pelo texto
# normalizado: "André Felipe" é nome, "quero agendar" não é, e sem essa
# distinção qualquer frase minúscula de até 60 letras passava por cadastro.
# Nome em minúscula cai no lado de consultar, que custa uma tool e não uma
# alucinação.
_DATA_CPF_OU_EMAIL = re.compile(r"^[\d\s./\-]{1,20}$|^\S+@\S+\.\S+$")
_NOME_PROPRIO = re.compile(r"^(?:[A-ZÀ-Þ][a-zà-ÿ'\-]+\s*){1,4}$")


def _normaliza(texto):
    plano = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in plano if not unicodedata.combining(c))


def exige_consulta(mensagem):
    """A mensagem precisa que o agente consulte antes de responder?

    Verdadeiro por padrão. Só é falso para saudação, agradecimento, confirmação
    social e entrega de dado de cadastro - o resto do mundo pode envolver fato,
    e fato vem de tool.
    """
    original = (mensagem or "").strip()
    plano = _normaliza(original).strip()
    if not plano:
        return False
    # "oi, tudo bem?" são duas expressões sociais emendadas: a mensagem só é
    # conversa fiada se TODOS os pedaços forem.
    pedacos = [p.strip() for p in re.split(r"[,;]|\se\s", plano) if p.strip()]
    if pedacos and all(re.match(SOCIAL, p) for p in pedacos):
        return False
    # Pergunta é sempre consulta, mesmo curta ("e amanhã?").
    if "?" in plano:
        return True
    if _DATA_CPF_OU_EMAIL.match(plano) or _NOME_PROPRIO.match(original):
        return False
    return True


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
