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

16/09/2026 - a trava recusou uma área que a paciente nomeou certo
------------------------------------------------------------------
Ela pediu "Virilha completa + Ânus". A área chama-se "Virilha Comp. + ânus" no
cadastro, e a comparação era com a string INTEIRA do nome: "virilha comp anus"
não é subsequência de "virilha completa anus", porque depois de "comp" vem
"leta". A área era inalcançável - nenhuma frase humana a liberaria, nunca.

O bot perguntou cinco vezes, ela respondeu certo cinco vezes, e a conversa
terminou uma hora e meia depois com o modelo pedindo uma atendente, que teve de
pedir desculpa por um defeito nosso.

Duas lições, e a segunda é a que dói:

  - Comparar com o nome do cadastro é comparar com uma string que uma atendente
    digitou num formulário. Ela abrevia, usa barra, põe ponto. Quem tem de ser
    entendida é a paciente, então o casamento é por PALAVRAS da área, não pela
    string. Ver `_aparece`.

  - Uma trava que recusa o mesmo duas vezes não está protegendo, está presa, e
    insistir cobra o preço da paciente. Ver [recusa_repetida].

E o defeito era invisível: nada quebrou, nada logou ERROR, a trava funcionou
exatamente como escrita. O que faltava era conferi-la contra o catálogo REAL -
que é o que [tests/unit/test_catalogo_real_e_alcancavel] passou a fazer.

06/10/2026 - a mesma classe de defeito, agora na fração
-------------------------------------------------------
A área chama-se "1/2 Perna". A paciente disse "meia perna" - e o próprio bot
tinha perguntado "perna completa ou meia perna?". A trava exigia as palavras
"1", "2" e "perna"; "meia" não é "1" nem "2". Recusou duas vezes, o laço de
recusa entregou a conversa a uma pessoa, e a atendente fechou à mão.

O teste de alcançabilidade não pegou porque a frase dele para "1/2 Perna" era
"1/2 perna" - circular: ninguém escreve fração no WhatsApp. Agora "1/2" no
cadastro aceita "meia", "meio" e "metade", e "½" digitado vira "1/2". Ver
`_alternativas` e `_normaliza`.

No mesmo dia, mais duas conversas caíram pelo mesmo motivo com outras
palavras: "virilha completa e peri anal" não liberava "Virilha Completa +
ânus" (peri anal não é ânus), e "costas, ombro, peitoral e abdômen" não
liberava "Costas total + ombros" (faltou "total", e "ombro" não é "ombros") -
três recusas, mesmo depois de o bot listar as áreas e ela dizer "sim".

A regra que fecha a classe inteira, e não uma palavra por vez:

  - sinônimo: "ânus" aceita "anal" e "perianal";
  - plural: "ombro" casa "ombros" - EXCETO quando o plural é o que distingue
    duas áreas ("Perna Completa" x "Pernas Completas"), aí é exato;
  - qualificador ("total", "completa", "comp.", "simples") é dispensável
    quando nenhuma outra área do catálogo fica com as mesmas palavras sem ele.
    "Costas total + ombros" vira alcançável por "costas e ombros"; "Virilha
    Completa" NÃO vira alcançável por "virilha", porque "Virilha Simples"
    também viraria.

As duas últimas dependem do catálogo inteiro, e é por isso que a decisão
mora em `_formas`, que o recebe. Ver [tests/unit/test_catalogo_real_e_alcancavel].
"""
import re
import unicodedata
from typing import Dict, Iterable, List, Sequence, Tuple


def _normaliza(texto: str) -> str:
    """Sem acento, sem caixa, sem pontuação - 'Buço' e 'buco' são a mesma área."""
    # "½" sumiria na limpeza (não é letra nem dígito) e "½ perna" viraria só
    # "perna". Vira a fração escrita, que é como o cadastro a grafa.
    texto = (texto or "").replace("\u00bd", " 1/2 ")
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


# Palavras que ligam, não identificam. Exigi-las barraria quem escreveu
# "costas total E ombros" onde o cadastro diz "+".
CONECTORES = frozenset({
    "e", "ou", "de", "da", "do", "das", "dos", "com", "a", "o", "as", "os",
})


def _sem_glosa(nome: str) -> str:
    """Tira o parêntese explicativo: 'Glabela (entre as sobrancelhas)' é 'Glabela'.

    A glosa existe para a atendente entender o cadastro, não para a paciente
    repetir. Exigi-la tornaria a área inalcançável.
    """
    return re.sub(r"\([^)]*\)", " ", nome or "")


def _tokens(trecho: str) -> List[Tuple[str, bool]]:
    """As palavras que identificam a área, cada uma com a marca de abreviação.

    Abreviada é a palavra que vinha seguida de ponto no cadastro - o 'Comp.' de
    'Virilha Comp. + ânus'. Só essas casam por começo de palavra, e é por isso
    que 'Lombar' continua não casando dentro de 'lombardia': 'Lombar' não é
    abreviação de nada, o cadastro não põe ponto nela.
    """
    saida = []
    for palavra, ponto in re.findall(r"([^\W_]+)(\.?)", trecho, flags=re.UNICODE):
        plano = _normaliza(palavra)
        if not plano or plano in CONECTORES:
            continue
        saida.append((plano, bool(ponto)))
    return saida


# Como a fração do cadastro é dita. "1/2 Perna" é "meia perna"; "1/2 Braço" é
# "meio braço"; e há quem diga "metade da perna". A paciente nunca digita "1/2".
_FRACAO = [("1", False), ("2", False)]
_FRACAO_FALADA = ("meia", "meio", "metade")


def _alternativas(nome: str) -> List[List[Tuple[str, bool]]]:
    """Os jeitos de nomear a área. 'Perianal/ânus' aceita qualquer um dos dois.

    A barra separa sinônimos no cadastro ('Mento/Queixo'), mas também escreve
    fração ('1/2 Braço'). Por isso só separa quando os dois lados são palavra.

    Fração vira palavra: '1/2 Perna' aceita '1/2 perna', 'meia perna', 'meio
    perna' e 'metade da perna'. Desde 06/10/2026, quando 'meia perna' foi
    recusada duas vezes e a conversa caiu para uma pessoa.
    """
    partes = re.split(
        r"(?<=[^\W\d_])\s*/\s*(?=[^\W\d_])|\s+ou\s+",
        _sem_glosa(nome),
        flags=re.UNICODE,
    )
    saida = []
    for tokens in (_tokens(p) for p in partes):
        if not tokens:
            continue
        saida.append(tokens)
        if tokens[:2] == _FRACAO:
            resto = tokens[2:]
            saida.extend([(palavra, False)] + resto for palavra in _FRACAO_FALADA)
    return saida


# Palavras que distinguem versões da mesma área. Dispensáveis quando não há
# versão vizinha para confundir; obrigatórias quando há.
QUALIFICADORES = frozenset({
    "total", "completa", "completo", "completas", "completos", "comp",
    "simples", "inteira", "inteiro",
})

# O que a paciente escreve no lugar da palavra do cadastro.
SINONIMOS = {
    "anus": frozenset({"anal", "perianal"}),
    "perianal": frozenset({"anal", "anus"}),
}


def _raiz(palavra: str) -> str:
    """'ombros' e 'ombro' são a mesma coisa. 'mas' não vira 'ma'."""
    return palavra[:-1] if len(palavra) > 3 and palavra.endswith("s") else palavra


def _chave(tokens) -> frozenset:
    return frozenset(_raiz(alvo) for alvo, _ in tokens)


def _casa_palavra(palavra: str, alvo: str, abreviado: bool, exato: bool) -> bool:
    if abreviado:
        return palavra.startswith(alvo)
    if palavra == alvo or palavra in SINONIMOS.get(alvo, ()):
        return True
    return (not exato) and _raiz(palavra) == _raiz(alvo)


def _formas(nome: str, catalogo=None) -> List[Tuple[List[Tuple[str, bool]], bool]]:
    """Os jeitos aceitos de dizer a área: (tokens, exato).

    Sem catálogo, só as formas completas, exatas - é o comportamento seguro.
    Com catálogo, duas tolerâncias que só valem quando NÃO confundem com outra
    área: plural solto (exato=False) e qualificador dispensado.
    """
    completas = _alternativas(nome)
    if catalogo is None:
        return [(t, True) for t in completas]

    chaves_das_outras = set()
    for outro in catalogo:
        if outro == nome:
            continue
        for t in _alternativas(outro):
            chaves_das_outras.add(_chave(t))
            sem = [x for x in t if x[0] not in QUALIFICADORES]
            if sem and len(sem) < len(t):
                chaves_das_outras.add(_chave(sem))

    def tolerante(chave):
        # Uma forma so pode ser frouxa se nenhuma outra area a CONTEM. "Coxas"
        # esta dentro de "1/2 Coxa" e "Perna Completa" dentro de "Pernas
        # Completas": frouxa, "1/2 coxa" liberaria as duas. Ai e exata.
        return not any(chave <= outra for outra in chaves_das_outras)

    formas = []
    for t in completas:
        formas.append((t, not tolerante(_chave(t))))
        sem = [x for x in t if x[0] not in QUALIFICADORES]
        if sem and len(sem) < len(t) and tolerante(_chave(sem)):
            formas.append((sem, False))
    return formas


def _aparece(nome: str, texto: str, formas=None) -> bool:
    """A área foi nomeada neste texto?

    Casa por palavras, não pela string inteira do cadastro. Até 16/09/2026 era
    pela string inteira, e o resultado foi o defeito descrito no cabeçalho:
    'Virilha Comp. + ânus' ficou inalcançável, porque ninguém escreve 'Comp.'
    no WhatsApp. A paciente escreveu 'Virilha completa + Ânus', a tool recusou
    cinco vezes seguidas, e a conversa caiu para uma atendente que teve de pedir
    desculpa por um defeito nosso.

    Exige TODAS as palavras da área. Por isso 'virilha completa' sozinho NÃO
    libera 'Virilha Comp. + ânus' - falta o 'ânus'. Frouxo o bastante para a
    paciente ser entendida, apertado o bastante para não liberar a área vizinha.
    """
    palavras = re.findall(r"[a-z0-9]+", texto or "")
    if not palavras:
        return False
    for alternativa, exato in (formas if formas is not None else _formas(nome)):
        if all(
            any(_casa_palavra(p, alvo, abreviado, exato) for p in palavras)
            for alvo, abreviado in alternativa
        ):
            return True
    return False


def areas_conversadas(turnos: Sequence[Dict], areas_da_clinica: Iterable[Dict]) -> set:
    """Os ids das áreas que já foram ditas E respondidas nesta conversa.

    `turnos` é a conversa em ordem, cada item {"role": "user"|"assistant",
    "content": "..."}. Só conta a área cujo nome aparece num turno seguido de
    pelo menos uma fala da paciente - ou dito por ela mesma.
    """
    areas = list(areas_da_clinica)
    catalogo = [a.get("name") or "" for a in areas]
    formas_por_area = {a.get("id"): _formas(a.get("name") or "", catalogo) for a in areas}

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

        for area in areas:
            if _aparece(area.get("name") or "", texto, formas_por_area[area.get("id")]):
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
