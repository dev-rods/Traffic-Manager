# -*- coding: utf-8 -*-
"""Uma área só vale se foi dita em voz alta na conversa.

Em 11/09/2026, no piloto da campanha, o bot foi perguntado "quais horários para
24/09?" e respondeu com horários. No fim fechou "Costas total + ombros, Lombar e
Axilas", R$ 445,00 por R$ 400,50, a um "sim" de agendar. A paciente nunca citou
área nenhuma, e o bot nunca perguntou: ele chamou `list_areas`, recebeu a lista
inteira e escolheu três.

O prompt já mandava confirmar as áreas. Não adiantou - e essa é a lição: com
modelo, instrução é pedido, não garantia. O que garante é a tool recusar.

Regra, decidida pelo André em 11/09/2026:

  Uma área só pode entrar em horário, preço ou agendamento se o NOME dela já
  apareceu na conversa, e a paciente falou depois disso.

Isso cobre os dois caminhos e força o terceiro:
  - a paciente nomeou ("quero axilas")           -> vale na hora
  - o bot propôs e ela respondeu                 -> vale
  - o bot achou no histórico e calou             -> NÃO vale, porque achar não é
    perguntar. Para liberar, ele precisa dizer os nomes a ela e esperar resposta.

Não julga se a resposta foi "sim" ou "não" - isso é interpretação, e é
justamente o que não se pode terceirizar para quem errou. A trava garante o
mínimo verificável: ninguém é agendado numa área que nunca foi conversada.
"""
import re
import unicodedata
from typing import Dict, Iterable, List, Sequence, Tuple


def _normaliza(texto: str) -> str:
    """Sem acento, sem caixa, sem pontuação - 'Buço' e 'buco' são a mesma área."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def _aparece(nome: str, texto: str) -> bool:
    """O nome da área aparece no texto?

    Compara por palavras inteiras para 'Axilas' não casar dentro de outra
    palavra, e aceita o nome inteiro em sequência - 'Costas total + ombros'
    vira 'costas total ombros'.
    """
    alvo = _normaliza(nome)
    if not alvo:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(alvo)}(?![a-z0-9])", texto) is not None


def areas_conversadas(turnos: Sequence[Dict], areas_da_clinica: Iterable[Dict]) -> set:
    """Os ids das áreas que já foram ditas E respondidas nesta conversa.

    `turnos` é a conversa em ordem, cada item {"role": "user"|"assistant",
    "content": "..."}. Só conta a área cujo nome aparece num turno seguido de
    pelo menos uma fala da paciente - ou dito por ela mesma.
    """
    liberadas = set()
    for i, turno in enumerate(turnos):
        texto = _normaliza(turno.get("content") or "")
        if not texto:
            continue

        dita_pela_paciente = turno.get("role") == "user"
        # Proposta do bot só vale depois que a paciente falou de novo.
        respondida = any(t.get("role") == "user" for t in turnos[i + 1:])
        if not (dita_pela_paciente or respondida):
            continue

        for area in areas_da_clinica:
            if _aparece(area.get("name") or "", texto):
                liberadas.add(str(area.get("id")))
    return liberadas


def separa(pares: Sequence[Dict], liberadas: set) -> Tuple[List[Dict], List[str]]:
    """Divide os pares entre os que podem ser usados e os ids barrados."""
    ok, barrados = [], []
    for par in pares or []:
        area_id = str(par.get("area_id") or "")
        if area_id in liberadas:
            ok.append(par)
        else:
            barrados.append(area_id)
    return ok, barrados


def recado_de_recusa(nomes_barrados: Sequence[str]) -> Dict:
    """O que a tool devolve ao modelo quando ele tenta usar área não conversada.

    Texto instrutivo de propósito: o modelo lê isto e precisa saber o que fazer
    em seguida, senão ele tenta de novo igual ou desiste no meio da conversa.
    """
    lista = ", ".join(nomes_barrados) if nomes_barrados else "as áreas"
    return {
        "error": "areas_nao_confirmadas",
        "areas_barradas": list(nomes_barrados),
        "o_que_fazer": (
            f"Você tentou usar {lista}, mas a paciente não confirmou essas áreas "
            f"nesta conversa. Pergunte a ela quais áreas quer tratar - se você as "
            f"encontrou no histórico dela, diga os nomes e pergunte se confirma "
            f"que são essas. Só depois da resposta dela chame esta tool de novo. "
            f"NUNCA escolha áreas por conta própria."
        ),
    }
