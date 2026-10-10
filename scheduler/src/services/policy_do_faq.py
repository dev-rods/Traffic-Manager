# -*- coding: utf-8 -*-
"""O FAQ da clínica entregue palavra por palavra (PRD 020 §4.3, fase 5).

Decisão do André (10/10/2026): se a clínica teve o trabalho de escrever a
resposta, ela vai como está. Não há item "redigível" e item "literal", não há
coluna nem seletor: todo item é literal.

O modelo só ESCOLHE o item, numa lista fechada (`enum` dos `question_key`
ativos da clínica); o texto do item vai à pessoa como mensagem própria no
WhatsApp, byte a byte. O que o modelo tiver a dizer sobre o resto da pergunta
vai em outra mensagem, nunca na mesma. Se o modelo repetir o item na fala
dele, a fala é descartada: a bolha literal basta.

Nenhum item respondendo é handoff `faq_sem_resposta`; mais de dois itens no
mesmo turno é pergunta confusa e também vai a pessoa. O desempate nunca é do
modelo.
"""
import logging
import re
import unicodedata
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

NOME_DA_TOOL = "get_faq_answer"
MAX_ITENS_POR_TURNO = 2

# A partir desta fração de frases do item presentes na fala do modelo, a fala
# é repetição do item e é descartada. Metade: uma frase copiada numa resposta
# de duas é repetição; uma frase em seis é citação, e passa.
FRACAO_QUE_E_REPETICAO = 0.5
_MIN_PALAVRAS_DA_FRASE = 5


def itens(db, clinic_id: str) -> List[Dict]:
    """Os itens ativos do FAQ da clínica, na ordem do painel. Nunca levanta:
    sem itens a tool não existe e o modelo não tem como responder dúvida -
    que é o certo quando a clínica não escreveu nada."""
    if db is None:
        return []
    try:
        linhas = db.execute_query(
            """
            SELECT question_key, question_label, answer
            FROM scheduler.faq_items
            WHERE clinic_id = %s AND active = true
            ORDER BY display_order, question_key
            """,
            (clinic_id,),
        )
    except Exception as e:
        logger.error(f"[FAQ] não li o FAQ de {clinic_id}: {e}")
        return []
    saida = []
    for l in linhas or []:
        chave = str(l.get("question_key") or "").strip()
        if chave and l.get("answer"):
            saida.append({
                "question_key": chave,
                "question_label": str(l.get("question_label") or chave),
                "answer": str(l["answer"]),
            })
    return saida


def definicao_da_tool(lista: Sequence[Dict]) -> Optional[Dict]:
    """A tool `get_faq_answer` com `enum` fechado, no formato OpenAI que
    `get_tool_definitions` converte. Sem itens, None: a tool não existe."""
    lista = list(lista or [])
    if not lista:
        return None
    catalogo = "\n".join(f"- {i['question_key']}: {i['question_label']}" for i in lista)
    return {
        "type": "function",
        "function": {
            "name": NOME_DA_TOOL,
            "description": (
                "Answer a patient question with the clinic's own FAQ text. Choose the ONE "
                "item that answers the question; the item's text is sent to the patient "
                "automatically, word for word, as its own message - you must NOT repeat, "
                "summarize or paraphrase it in your reply. If no item answers the question, "
                "do NOT call this tool: say you will confirm with the team and call "
                "request_human_handoff. Items available:\n" + catalogo
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question_key": {
                        "type": "string",
                        "enum": [i["question_key"] for i in lista],
                        "description": "The key of the FAQ item that answers the question.",
                    },
                },
                "required": ["question_key"],
            },
        },
    }


def por_chave(lista: Sequence[Dict], chave: str) -> Optional[Dict]:
    for i in lista or []:
        if i.get("question_key") == chave:
            return i
    return None


def _plano(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[*_~`]", "", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _frases(texto: str) -> List[str]:
    partes = re.split(r"[.!?\n]+", texto or "")
    return [p.strip() for p in partes if len(p.split()) >= _MIN_PALAVRAS_DA_FRASE]


def repete_o_item(fala_do_modelo: str, answer: str) -> bool:
    """A fala do modelo repete o item (inteiro ou em boa parte)? Comparação
    sem acento, sem pontuação, sem negrito do WhatsApp."""
    fala = _plano(fala_do_modelo)
    if not fala:
        return False
    frases = [_plano(f) for f in _frases(answer)]
    frases = [f for f in frases if f]
    if not frases:
        return _plano(answer) in fala
    repetidas = sum(1 for f in frases if f in fala)
    return repetidas / len(frases) >= FRACAO_QUE_E_REPETICAO


def fala_sem_o_item(fala_do_modelo: str, entregues: Sequence[Dict], phone: str = "") -> str:
    """A fala do modelo, ou vazio se ela repete algum item entregue."""
    for item in entregues or []:
        if repete_o_item(fala_do_modelo, item.get("answer", "")):
            logger.warning(
                f"[FAQ] {phone}: o modelo repetiu o item {item.get('question_key')}; "
                f"descartei | {fala_do_modelo[:120]!r}"
            )
            return ""
    return fala_do_modelo
