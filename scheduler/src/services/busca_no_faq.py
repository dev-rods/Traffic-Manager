# -*- coding: utf-8 -*-
"""Achar a resposta certa no FAQ da clínica.

O caso que motivou este módulo, em 23/09/2026: uma paciente perguntou se podia
fazer a sessão menstruada. O FAQ da Essência tem um item chamado exatamente
"Posso fazer menstruada?". O bot perguntou certo à tool, a busca não entregou,
e ele chamou uma especialista - para uma pergunta que a própria clínica já
tinha respondido por escrito.

A busca antiga fazia duas tentativas:

1. a frase inteira como `ILIKE %pergunta%`, que só casa se a pessoa repetir o
   título do item palavra por palavra;
2. um fallback que quebrava em palavras, juntava com OR, ordenava por
   `display_order` e cortava em 3.

O segundo é que falhava, e falhava sempre do mesmo jeito: "pode", "fazer" e
"sessão" casam com quase todo item do FAQ, então vencia quem estava mais no
topo da lista - não quem era mais relevante. Medido no FAQ real: 13 dos 19
itens casavam, e "Posso fazer menstruada?" ficava em 6º.

Aqui a ordenação é por RELEVÂNCIA, e ela vem de três ideias simples:

- **palavra rara vale mais que palavra comum.** "menstruada" aparece em 1 item;
  "sessão" aparece em 12. Quem casa a primeira está falando do assunto; quem
  casa a segunda só está falando português.
- **casar no título vale mais que casar na resposta.** O título é a pergunta
  que a clínica escreveu; a resposta é texto corrido, onde uma palavra pode
  aparecer de passagem.
- **um piso.** Casar só palavra comum não é resposta. Abaixo do piso a tool
  devolve vazio, e vazio faz o bot chamar a especialista - que é o certo
  quando a clínica realmente não escreveu sobre aquilo.

O FAQ de uma clínica tem dezenas de itens, não milhares: ranquear em memória é
mais simples e mais previsível que montar isso em SQL, e deixa a regra testável
sem banco.
"""
import math
import re
import unicodedata
from typing import Dict, List, Sequence

# Palavras que não distinguem um item de FAQ de outro. Sem esta lista,
# "Posso fazer?" casaria com metade do FAQ - e casaria com força, porque são
# justamente as palavras que mais se repetem.
VAZIAS = frozenset("""
a as o os um uma uns umas de do da dos das em no na nos nas por para pra pelo
pela com sem sobre ao aos e ou mas que se qual quais quando onde como quanto
quantos quantas eu voce vc me meu minha meus minhas seu sua tem ter tenho
posso pode podem poderia consigo consegue fazer faz faco fazendo ser e esta
estao estou muito mais menos ja nao sim tambem so entao assim isso isto essa
esse aquilo la ali aqui preciso precisa precisam
""".split())

# ANTES/DEPOIS/DURANTE ficaram DE FORA da lista de propósito.
#
# Parecem palavras de ligação, mas aqui são o que distingue uma pergunta da
# outra: "posso pegar sol depois?" e "pode fazer com sol?" são itens diferentes
# do FAQ, e a única palavra que os separa é justamente essa. Marcá-las como
# vazias fazia a busca devolver o item errado - visto no teste, com o FAQ real.

# Um título casado vale por três ocorrências na resposta. O título é a pergunta
# que a clínica escreveu; a resposta é texto corrido.
PESO_DO_TITULO = 3.0

# Abaixo disto não é resposta, é coincidência de vocabulário. Calibrado contra
# o FAQ real da Essência: ver test_busca_no_faq.
PISO = 1.0

# Quantos itens voltam para o modelo. Mais que isso vira um despejo e convida o
# bot a costurar pedaços de respostas diferentes.
QUANTOS = 3


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _singular(palavra: str) -> str:
    """Plural e singular viram a mesma coisa.

    A paciente pergunta "quantas sessoes" e a clínica escreveu "sessões".
    Sem isto, `sessoes` e `sessao` são palavras diferentes e a pergunta erra o
    item - visto no teste, com o FAQ real.

    Português tem plural irregular demais para resolver de forma geral; estas
    três regras cobrem o que aparece num FAQ de clínica.
    """
    if len(palavra) > 4 and palavra.endswith("oes"):
        return palavra[:-3] + "ao"      # sessoes -> sessao
    if len(palavra) > 4 and palavra.endswith("aes"):
        return palavra[:-3] + "ao"      # maes -> mao
    if len(palavra) > 3 and palavra.endswith("s"):
        return palavra[:-1]             # pelos -> pelo
    return palavra


def termos(texto: str) -> List[str]:
    """As palavras que importam numa frase, já normalizadas.

    Sem acento porque a paciente escreve "sessao" e a clínica escreveu
    "sessão"; sem pontuação porque "menstruada?" e "menstruada" são a mesma
    palavra, e o `ILIKE '%menstruada?%'` da versão antiga não sabia disso; no
    singular porque "sessoes" e "sessão" são o mesmo assunto.
    """
    limpo = _sem_acento((texto or "").lower())
    palavras = re.findall(r"[a-z0-9]+", limpo)
    return [
        _singular(p) for p in palavras
        if len(p) >= 3 and p not in VAZIAS and _singular(p) not in VAZIAS
    ]


def _peso_dos_termos(itens: Sequence[Dict]) -> Dict[str, float]:
    """Quanto vale cada palavra, dado este FAQ.

    Uma palavra que aparece em quase todos os itens não ajuda a escolher entre
    eles. É a ideia do IDF, no tamanho do problema que temos aqui.
    """
    total = max(len(itens), 1)
    em_quantos: Dict[str, int] = {}
    for item in itens:
        vistos = set(termos(item.get("question_label", "")))
        vistos |= set(termos(item.get("answer", "")))
        for t in vistos:
            em_quantos[t] = em_quantos.get(t, 0) + 1
    return {
        t: math.log((total + 1) / (n + 1)) + 0.1
        for t, n in em_quantos.items()
    }


def pontua(pergunta: str, item: Dict, pesos: Dict[str, float]) -> float:
    """O quanto este item do FAQ responde a esta pergunta."""
    procurados = set(termos(pergunta))
    if not procurados:
        return 0.0

    no_titulo = set(termos(item.get("question_label", "")))
    na_resposta = set(termos(item.get("answer", "")))

    total = 0.0
    for t in procurados:
        peso = pesos.get(t, 1.0)
        if t in no_titulo:
            total += peso * PESO_DO_TITULO
        elif t in na_resposta:
            total += peso
    return total


def busca(pergunta: str, itens: Sequence[Dict], quantos: int = QUANTOS) -> List[Dict]:
    """Os itens do FAQ que respondem à pergunta, do mais ao menos relevante.

    Lista vazia quando nada passa do piso. Vazio aqui é uma resposta: faz o bot
    dizer que vai confirmar com a especialista, em vez de despejar três itens
    que não têm a ver e deixar a paciente repetir a pergunta.
    """
    if not pergunta or not itens:
        return []

    pesos = _peso_dos_termos(itens)

    marcados = []
    for item in itens:
        p = pontua(pergunta, item, pesos)
        if p >= PISO:
            marcados.append((p, item))

    # Empate desempata por `display_order`: com a mesma relevância, a ordem que
    # a clínica escolheu é o melhor critério que sobra.
    marcados.sort(key=lambda par: (-par[0], par[1].get("display_order") or 0))
    return [item for _, item in marcados[:quantos]]
