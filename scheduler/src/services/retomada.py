# -*- coding: utf-8 -*-
"""Quando o atendimento humano vence, o bot avalia se ficou pergunta sem
resposta - e responde uma vez, sem depender de clique. PRD 020 §3.7.

Hoje o bot só responde o que ficou em aberto quando alguém clica "Retomar
bot" no painel. É essa dependência que acaba aqui. Mas a assimetria do erro
desenha a avaliação: silêncio se corrige (a pessoa insiste, a fila mostra),
mensagem fora de contexto não. Por isso ela FALHA FECHADA e o modelo não
decide - classifica.

    1. guardas determinísticas, nesta ordem; qualquer uma falha -> cala
       a. a última fala da conversa é do cliente
       b. não é fecho social ("ok", "obrigada", "boa noite")
       c. idade da fala <= idade máxima da clínica (72h por padrão)
       d. nenhum efeito no banco DEPOIS dela: agendamento criado, remarcado ou
          cancelado após a mensagem é evidência de que alguém resolveu por
          telefone ou no balcão
       e. nenhuma retomada já enviada para esta pendência
       f. pode_iniciar() - janela de silêncio, bot_paused, política
    2. LLM classifica, com saída fechada: {pendente: sim|nao, o_que: "..."}
       "nao" ou saída inválida -> cala
    3. LLM responde, com o atraso reconhecido e datas relativas reperguntadas

Idade máxima tem de ser MAIOR que o TTL humano (24h): no vencimento a
pendência tem pelo menos 24h, e um limite de 24h nunca passaria.
"""
import json
import logging
import re
import time
from typing import Dict, Optional, Sequence, Tuple

from src.services import atendimento
from src.services.roteador import SOCIAL

logger = logging.getLogger(__name__)

IDADE_MAXIMA_PADRAO_HORAS = 72

# Quantos eventos do MessageEvents a avaliação lê. As guardas só precisam da
# última fala; o classificador e o agente recebem a janela para não repetir o
# que já foi dito (mesmo valor de conversation_resume).
EVENTOS_PARA_CONTEXTO = 20

# Motivos de "calar", para o log e para a fila do painel saberem por quê.
ULTIMA_FALA_NAO_E_DO_CLIENTE = "ultima_fala_nao_e_do_cliente"
FECHO_SOCIAL = "fecho_social"
PENDENCIA_VELHA = "pendencia_velha"
RESOLVIDO_FORA = "resolvido_fora"
JA_RETOMADO = "ja_retomado"
PORTA_FECHADA = "porta_fechada"
MODELO_DISSE_NAO = "modelo_disse_nao"

_SOCIAL = re.compile(SOCIAL)

PROMPT_DO_CLASSIFICADOR = (
    "Você lê o fim de uma conversa de WhatsApp entre uma clínica de depilação a "
    "laser e uma pessoa. A última mensagem é da pessoa e ficou sem resposta há "
    "mais de um dia. Decida se ela ESPERA uma resposta: uma pergunta, um pedido, "
    "uma escolha de horário ou de área. Agradecimento, confirmação ('ok', "
    "'combinado'), despedida ou comentário sem pergunta NÃO esperam resposta.\n"
    "Responda SOMENTE com JSON: {\"pendente\": true|false, \"o_que\": \"<em uma frase, "
    "o que ela espera; vazio se nada>\"}. Datas relativas que ela usou ('amanhã', "
    "'sábado') já não valem: não as resolva, só descreva o pedido."
)


def _instante(evento: Dict) -> Optional[int]:
    """Epoch do evento, a partir do sk 'MSG#2026-10-06T15:11:12Z#...'."""
    sk = str(evento.get("sk") or "")
    m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", sk)
    if not m:
        return None
    try:
        return int(time.mktime(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) - time.timezone)
    except (ValueError, OverflowError):
        return None


def ultima_fala(eventos: Sequence[Dict]) -> Optional[Dict]:
    """O último evento com texto, ou None."""
    for evento in reversed(eventos or []):
        if (evento.get("content") or "").strip():
            return evento
    return None


def e_fecho_social(texto: str) -> bool:
    plano = _plano(texto)
    pedacos = [p.strip() for p in re.split(r"[,;]|\se\s", plano) if p.strip()]
    return bool(pedacos) and all(_SOCIAL.match(p) for p in pedacos)


def _plano(texto: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(c) != "Mn"
    ).strip()


def pode_retomar(session: Dict, eventos: Sequence[Dict], efeitos_depois: int,
                 clinic: Dict, phone: str, agora: Optional[int] = None) -> Tuple[bool, str]:
    """As guardas determinísticas, na ordem. (True, "") quando todas passam.

    `efeitos_depois` é a contagem de agendamentos da pessoa criados ou
    alterados após a última fala dela - quem consulta é o chamador, porque
    aqui não há banco.
    """
    agora = atendimento._agora(agora)
    fala = ultima_fala(eventos)
    if not fala or fala.get("direction") != "INBOUND":
        return False, ULTIMA_FALA_NAO_E_DO_CLIENTE
    if e_fecho_social(fala.get("content") or ""):
        return False, FECHO_SOCIAL

    quando = _instante(fala)
    limite_h = int((clinic or {}).get("idade_maxima_da_pendencia_horas") or IDADE_MAXIMA_PADRAO_HORAS)
    if quando is None or agora - quando > limite_h * 3600:
        return False, PENDENCIA_VELHA
    if efeitos_depois > 0:
        return False, RESOLVIDO_FORA
    if atendimento.bloco(session).get("retomada_em"):
        return False, JA_RETOMADO
    # No instante do vencimento a sessão já lê como COOLDOWN, e o cooldown
    # existe justamente para o bot não iniciar nada DEPOIS da retomada. A
    # retomada é a transição; por isso ela ignora o cooldown (transacional),
    # mas não a janela de silêncio, o bot_paused nem a política.
    if not atendimento.pode_iniciar(clinic, session, phone, agora, transacional=True):
        return False, PORTA_FECHADA
    return True, ""


def classifica(anthropic, eventos: Sequence[Dict]) -> Dict:
    """{pendente, o_que}. Falha fechada: erro ou JSON inválido é não pendente."""
    linhas = []
    for e in (eventos or [])[-12:]:
        texto = (e.get("content") or "").strip()
        if not texto:
            continue
        quem = "PESSOA" if e.get("direction") == "INBOUND" else "CLÍNICA"
        linhas.append(f"{quem}: {texto[:300]}")
    try:
        resposta = anthropic.create_message(
            system=PROMPT_DO_CLASSIFICADOR,
            messages=[{"role": "user", "content": "\n".join(linhas) or "(vazio)"}],
            max_tokens=120,
        )
        texto = "".join(b.get("text", "") for b in resposta.get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", texto, flags=re.S)
        dados = json.loads(m.group(0)) if m else {}
        return {"pendente": bool(dados.get("pendente")), "o_que": str(dados.get("o_que") or "")[:200]}
    except Exception as e:
        logger.error(f"[Retomada] classificador falhou: {e}")
        return {"pendente": False, "o_que": ""}


def bloco_de_contexto(horas: int, o_que: str) -> str:
    """O que o agente recebe junto com o gatilho de retomada."""
    return (
        "═══ RETOMADA ═══\n"
        f"A última mensagem desta pessoa ficou sem resposta há {horas}h. Reconheça o\n"
        "atraso em uma frase curta. Se ela mencionou data relativa (\"amanhã\",\n"
        "\"sábado\", \"semana que vem\"), NÃO a resolva: pergunte a data de novo.\n"
        f"O que ela perguntou: {o_que or 'ver a última mensagem dela'}.\n"
    )
