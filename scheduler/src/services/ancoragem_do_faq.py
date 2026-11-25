# -*- coding: utf-8 -*-
"""O FAQ como fonte: a fala do modelo só pode trazer fatos que estão no item.

Até 25/11/2026 o item do FAQ saía literal, em bolha própria, antes da fala
do modelo, e o modelo era proibido de resumir. Resultado (PRD 064, caso 1):
"quanto é a virilha?" recebia o texto inteiro dos três tipos de virilha
antes do "oi", sem ninguém ter perguntado a diferença. Agora o texto volta
ao modelo e ele responde só o que foi perguntado, com as palavras do item
(decisão P3 do André: tudo em modo fonte).

A rede: esta checagem de ancoragem. Deliberadamente permissiva, pega o que
custa caro - o modelo acrescentando prazo, quantidade, grau, percentual ou
produto que a clínica não escreveu. Não tenta julgar paráfrase. Falhou duas
vezes, o item vai literal (o comportamento antigo), e a promessa do PRD 020
("a clínica escreveu, vai como está") continua valendo no pior caso.
"""
import re
import unicodedata
from typing import Dict, List, Sequence, Set

# Número com o que vier colado: "7 dias", "-3°C", "30%", "8 a 12", "FPS 30".
_NUMERO = re.compile(r"-?\d+(?:[.,]\d+)?\s*(?:°c|ºc|%|dias?|semanas?|meses|mes|horas?|h|min|sessoes|sessao|anos?)?")
# Termos que mudam a conduta da paciente; um deles fora do item é invenção.
_TERMOS = re.compile(
    r"\b(isotretinoina|roacutan|antibiotico|anticoagulante|gestante|gravida|lactante|amamentand\w*|"
    r"peeling|acido|retinoico|cera|pinca|protetor|fps|bronze\w*|tatuagem|queloide|diabetes|"
    r"epilepsia|autoimune|silicone|cerave|cetaphil|cicaplast|bepantol|soprano|safira|alexandrite|diodo)\b"
)


def _plano(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[*_~`]", "", t)
    return re.sub(r"\s+", " ", t).strip()


# Horario (16:25, 16h30) e data (21/11, 03/12/2026) sao agenda: quem os
# confere e a proveniencia, com o respaldo de get_time_slots/check_availability.
_AGENDA = re.compile(r"(?<!\d)\d{1,2}[:h]\d{2}(?!\d)|(?<!\d)\d{1,2}h(?![a-z\d])|(?<!\d)\d{1,2}/\d{1,2}(?:/\d{2,4})?(?!\d)|dia \d{1,2}(?!\d)")


def _canonico(n: str) -> str:
    """'70,00' -> '70'; '70.50' -> '70.5'; '-3°c' -> '-3°c'. Virgula e ponto sao
    o mesmo separador aqui (R$ 70,00 no texto, R$ 70.00 na tool)."""
    m = re.match(r"(-?\d+)(?:[.,](\d+))?(.*)$", n)
    if not m:
        return n
    inteiro, fracao, resto = m.group(1), (m.group(2) or "").rstrip("0"), m.group(3)
    return f"{inteiro}{'.' + fracao if fracao else ''}{resto}"


def fatos(texto: str) -> Set[str]:
    t = _AGENDA.sub(" ", _plano(texto))
    achados = set()
    for m in _NUMERO.finditer(t):
        n = _canonico(re.sub(r"\s+", "", m.group(0)))
        if n.lstrip("-").replace(",", "").replace(".", "").isdigit() and len(n.lstrip("-")) <= 1 and not re.search(r"[a-z%]", n):
            # Dígito solto ("3 opções", "1 sessão"): contagem de conversa, não fato clínico.
            continue
        achados.add(n)
    for m in _TERMOS.finditer(t):
        achados.add(m.group(1))
    return achados


def _fatos_do_item(itens: Sequence[Dict]) -> Set[str]:
    base: Set[str] = set()
    for item in itens or []:
        base |= fatos(f"{item.get('question_label', '')} {item.get('answer', '')}")
    return base


def confere(fala_do_modelo: str, itens: Sequence[Dict], respaldo: str = "") -> List[str]:
    """Fatos da fala que não aparecem em nenhum item consultado nem no
    `respaldo` (o que as outras tools devolveram neste turno: horários,
    valores, duração). Vazio = ancorada. Números: basta o número aparecer na
    base (com ou sem a unidade)."""
    if not fala_do_modelo or not itens:
        return []
    base = _fatos_do_item(itens) | (fatos(respaldo) if respaldo else set())
    if respaldo:
        for n in re.findall(r"\d+(?:[.,]\d+)?", _plano(respaldo)):
            base.add(_canonico(n))
    base_numeros = {re.match(r"-?\d+(?:\.\d+)?", b).group(0) for b in base if re.match(r"-?\d", b)}
    faltam = []
    for f in sorted(fatos(fala_do_modelo)):
        if f in base:
            continue
        m = re.match(r"-?\d+(?:\.\d+)?", f)
        if m and m.group(0) in base_numeros:
            continue
        faltam.append(f)
    return faltam
