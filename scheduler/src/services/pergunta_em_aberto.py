# -*- coding: utf-8 -*-
"""Na retomada, a última pergunta da pessoa vem primeiro (PRD 064, frente 5).

Nobre, 24/11/2026: "Quanto é a depilação na virilha?" ficou 44 minutos sem
resposta (política LEADS_ONLY); a recepção retomou o bot e ele foi direto
para a etapa de áreas, sem dizer o preço nem que o preço depende do tipo. O
prompt do banco já mandava "responda exatamente o que ela perguntou por
último", mas o roteiro de áreas, no meio do mesmo prompt, venceu.

Aqui a pergunta em aberto é extraída pelo código e entra em dois lugares: no
turno do gatilho (o que ela perguntou, literal) e no FIM do system prompt
(último vence). E uma trava confere se a resposta falou do assunto; se não,
uma reescrita.
"""
import re
import unicodedata
from typing import Dict, Optional, Sequence

from src.services import fecho_social

_INTERROGATIVAS = re.compile(
    r"^(quanto|quantos|quantas|qual|quais|quando|onde|como|tem |teria|voces|vcs|posso|pode|"
    r"consigo|preciso saber|queria saber|gostaria de saber|e possivel|da pra|da para|funciona|doi|"
    r"atende|aceita|fazem|faz )"
)
_STOP = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos", "um", "uma",
    "e", "ou", "que", "com", "sem", "por", "para", "pra", "se", "ja", "nao", "sim", "voce", "voces",
    "vcs", "eu", "me", "meu", "minha", "esse", "essa", "isso", "ele", "ela", "ola", "oi", "bom", "boa",
    "dia", "tarde", "noite", "obrigada", "obrigado", "tudo", "bem", "quanto", "qual", "quais", "quando",
    "onde", "como", "tem", "posso", "pode", "fica", "custa", "sai", "valor", "preco", "mais", "muito",
}
_RAIZ = 5


def _plano(texto: str) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9?\s]", " ", t)).strip()


def e_pergunta(texto: str) -> bool:
    t = _plano(texto)
    if not t or fecho_social.e_fecho_social(texto):
        return False
    return "?" in t or bool(_INTERROGATIVAS.match(t))


def ultima_pergunta(eventos: Sequence[Dict]) -> Optional[str]:
    """A última fala da pessoa que é pergunta, se ninguém respondeu depois."""
    for evento in reversed(eventos or []):
        texto = (evento.get("content") or "").strip()
        if not texto:
            continue
        if evento.get("direction") != "INBOUND":
            # Alguém (bot, recepção, sistema) falou depois: nada em aberto aqui.
            return None
        if e_pergunta(texto):
            return texto
        # Fala da pessoa sem pergunta ("ok", "axilas e virilha"): segue olhando
        # para trás, a pergunta pode ter sido a mensagem anterior.
    return None


def _termos(texto: str):
    return {p[:_RAIZ] for p in _plano(texto).replace("?", " ").split() if len(p) >= 4 and p not in _STOP}


# Perguntar horario e ouvir "qual data?" e o mesmo assunto: o horario depende
# da data. Sem isto a trava mandava reescrever uma resposta certa (25/11/2026).
_AGENDA = re.compile(r"horari|hora\b|datas?\b|dias?\b|agenda|vaga|disponi")


def respondeu(resposta: str, pergunta: str) -> bool:
    """A resposta toca no assunto da pergunta? Raízes de palavras em comum, ou
    número/valor quando a pergunta era de preço/quantidade. Permissivo de
    propósito: a trava existe para pegar o modelo mudando de assunto, não
    para julgar qualidade."""
    if not pergunta:
        return True
    r = _plano(resposta)
    if not r:
        return False
    comuns = _termos(resposta) & _termos(pergunta)
    if comuns:
        return True
    p = _plano(pergunta)
    if re.search(r"quanto|valor|preco|custa|sai por", p) and re.search(r"\d|r\$|depende", r):
        return True
    if re.search(r"quando|data|dia|horario|hora", p) and re.search(r"\d|segunda|terca|quarta|quinta|sexta|sabado", r):
        return True
    if _AGENDA.search(p) and _AGENDA.search(r):
        return True
    return False


# O modelo, corrigido com "PARE", as vezes responde A CORRECAO em vez de a
# pessoa: "peco desculpas, vou reformular." saiu numa mensagem real do eval de
# 25/11. Fala de bastidor nao chega a paciente.
_META = re.compile(
    r"^\s*((pe[cç]o desculpas|desculpe|desculpa|perd[aã]o)[,.!]?\s*)?(vou reformular|reformulando|"
    r"deixa eu reformular|corrigindo|vou corrigir|me corrigindo)[.:!]?\s*",
    re.IGNORECASE,
)


def limpa_meta(texto: str) -> str:
    """Tira a fala de bastidor do inicio da resposta."""
    if not texto:
        return texto
    limpo = _META.sub("", texto, count=1).lstrip()
    if limpo != texto and limpo:
        return limpo[0].upper() + limpo[1:]
    return texto


def bloco_do_turno(pergunta: Optional[str]) -> str:
    if not pergunta:
        return ""
    return (
        "═══ PERGUNTA EM ABERTO ═══\n"
        f"A pessoa perguntou e ninguém respondeu: \"{pergunta.strip()[:200]}\"\n"
        "Responda ISSO primeiro, na primeira frase depois da saudação. Só depois\n"
        "conduza para a próxima etapa.\n\n"
    )


def bloco_do_system() -> str:
    """Vai no FIM do system prompt da retomada: o último bloco vence o roteiro
    de etapas que está no meio do prompt do banco."""
    return (
        "\n═══ RETOMADA: A PERGUNTA VEM PRIMEIRO ═══\n"
        "Esta é uma retomada: a pessoa escreveu antes e ficou sem resposta. A\n"
        "PERGUNTA EM ABERTO do turno é a prioridade absoluta: responda-a na\n"
        "primeira frase depois da saudação, mesmo que a etapa do roteiro peça\n"
        "outra coisa (áreas, datas). Se a resposta depende de algo (ex.: preço\n"
        "depende do tipo de virilha), diga isso e pergunte o que falta. Nunca\n"
        "comece pela etapa de áreas deixando a pergunta dela para depois.\n"
    )
