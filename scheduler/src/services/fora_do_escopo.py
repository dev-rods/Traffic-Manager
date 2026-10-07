# -*- coding: utf-8 -*-
"""Pergunta sobre procedimento que o bot não atende.

A Essência não vende só depilação a laser: vende preenchimento, toxina
botulínica, bioestimulador. O bot atende UM desses - o laser - e a decisão do
André em 04/10/2026 é que qualquer informação sobre os outros vai para uma
especialista. Não é timidez de produto: preço de injetável depende de avaliação
presencial, de quantos mililitros, da indicação. Nada disso cabe num catálogo
de áreas com preço por região.

Hoje isso funciona POR ACIDENTE, e só às vezes. "Vocês fazem botox?" não casa
nada no FAQ, a tool devolve vazio com a instrução de chamar a especialista, e a
resposta sai certa. Mas o acidente desmonta de duas formas:

1. a clínica cadastra um item de FAQ sobre botox - e o bot passa a responder
   sobre botox, que é justamente o que não pode;
2. a pergunta carrega palavra de laser. "Quanto custa a toxina botulínica por
   sessão?" casa "sessão" e "custa" com itens de depilação, a busca devolve o
   item de laser acima do piso, e o bot responde preço de laser para quem
   perguntou de botox. Esse é o erro caro: a pessoa chega na clínica com um
   número na cabeça que nunca foi dela.

Por isso a guarda é determinística e roda ANTES do agente, não depois: a
pergunta nem chega ao modelo. O prompt também ganhou a instrução, como segunda
rede para o que a lista não nomeia (ver conversation_agent), mas quem decide os
casos nomeados é esta lista. O repo inteiro é feito assim - [areas_ambiguas],
[menor_de_idade], [proveniencia] - e pelo mesmo motivo: instrução o modelo
contorna.
"""
import logging
import re
import unicodedata
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# O piso, igual para toda clínica. Estes procedimentos não entram no fluxo do
# bot em lugar nenhum: ele agenda sessão de laser por área, com preço de
# tabela, e nada aqui tem isso.
#
# Para ACRESCENTAR termos de uma clínica existe a coluna
# `bot_procedimentos_fora_do_escopo`. Esta lista é só somada, nunca substituída:
# o dia em que o bot passar a atender um destes, o termo sai DAQUI - de um
# lugar, no código, com teste - e não de uma linha de banco que ninguém releu.
PROCEDIMENTOS = (
    # Injetáveis
    ("toxina_botulinica", r"\btoxinas?\b|\bbotox\b|\bbotulinica\b|\bbotulinico\b|\bdysport\b|\bxeomin\b"),
    ("preenchimento", r"\bpreenchimento\b|\bpreencher\b|\back?ido hialuronico\b|\bhialuronico\b"),
    ("bioestimulador", r"\bbioestimulador(es)?\b|\bsculptra\b|\bradiesse\b|\bellanse\b"),
    ("fios_de_sustentacao", r"\bfios? de (sustentacao|pdo)\b|\bfios? russos?\b"),
    ("enzimas", r"\benzimas?\b|\bintradermoterapia\b|\bmesoterapia\b"),
    ("skinbooster", r"\bskin ?booster\b"),
    # Estética facial e corporal que não é laser
    ("limpeza_de_pele", r"\blimpeza de pele\b"),
    ("peeling", r"\bpeeling\b"),
    ("microagulhamento", r"\bmicroagulhamento\b|\bmicro ?needling\b"),
    ("criolipolise", r"\bcriolipolise\b|\bcoolsculpt\w*\b"),
    ("massagem", r"\bmassagem\b|\bdrenagem\b|\bmassoterapia\b"),
    ("micropigmentacao", r"\bmicropigmentacao\b|\bdesign de (sobrancelha|cilios)\b|\bextensao de cilios\b"),
    ("ultraformer", r"\bultraformer\b|\bhifu\b|\bultrassom microfocado\b"),
    ("lavieen", r"\blavieen\b|\blaser lavieen\b"),
)

# Compilado uma vez: este módulo roda em toda mensagem recebida.
_COMPILADOS = tuple((nome, re.compile(padrao)) for nome, padrao in PROCEDIMENTOS)

# O que a paciente recebe. Promete pessoa e não promete prazo - a clínica
# responde quando responde, e dar hora aqui seria inventar.
#
# Não nomeia o procedimento de volta ("sobre botox, vou passar..."): o nome que
# a guarda casou é o nosso, não o dela, e repeti-lo errado numa mensagem de
# "não sei responder" é a pior combinação possível.
TEXTO = (
    "Esse procedimento é com uma das nossas especialistas - ela te explica "
    "certinho e já te passa os valores. Vou te colocar em contato agora 😊"
)

# A instrução que vai no prompt, para o que a lista não nomeia. Fica aqui, ao
# lado da lista, porque as duas dizem a MESMA regra: separá-las é como a
# divergência começa.
INSTRUCAO_DO_PROMPT = (
    "\n═══ SÓ DEPILAÇÃO A LASER ═══\n"
    "1. A clínica faz outros procedimentos (preenchimento, toxina botulínica,\n"
    "   bioestimulador, estética facial). Você atende APENAS depilação a laser.\n"
    "2. Qualquer pergunta sobre outro procedimento - o que é, se faz, preço,\n"
    "   quantas sessões, se pode combinar com o laser - você NÃO responde e NÃO\n"
    "   consulta o FAQ. Chame request_human_handoff com\n"
    "   reason=\"procedimento_fora_do_escopo\" e diga que uma especialista vai\n"
    "   explicar e passar os valores.\n"
    "3. Isso vale mesmo que o FAQ tenha algo parecido e mesmo que você ache que\n"
    "   sabe. Preço de injetável depende de avaliação presencial: número vindo\n"
    "   de você é número errado na cabeça da paciente.\n"
    "4. Também não agende: você só agenda sessão de depilação a laser.\n"
)


def _normaliza(texto: str) -> str:
    """Minúsculas, sem acento. A paciente escreve "botulinica" e "botulínica"."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )
    return sem_acento.lower()


def _extras(clinic: Optional[Dict]) -> List[tuple]:
    """Os termos que esta clínica acrescentou, já compilados.

    Termo com regex inválida é ignorado com log, não derruba a mensagem: a
    coluna é editada por gente, e uma clínica digitando "(" ali não pode calar o
    bot para todas as pacientes dela.
    """
    termos = (clinic or {}).get("bot_procedimentos_fora_do_escopo") or []
    compilados = []
    for termo in termos:
        texto = _normaliza(str(termo)).strip()
        if not texto:
            continue
        try:
            # O termo da clínica é texto, não regex: escapamos e envolvemos em
            # fronteira de palavra. Quem preenche a coluna é a recepção, e
            # pedir regex a ela seria pedir o bug.
            compilados.append((f"clinica:{texto}", re.compile(rf"\b{re.escape(texto)}\b")))
        except re.error as e:
            logger.warning(f"[ForaDoEscopo] termo inválido {termo!r}: {e}")
    return compilados


def detecta(texto: str, clinic: Optional[Dict] = None) -> Optional[str]:
    """O procedimento fora do escopo citado na mensagem, ou None.

    Devolve o NOME interno (ex. "toxina_botulinica") para ir ao log e ao painel.
    Primeiro que casa ganha: a mensagem citar dois não muda nada, porque a ação
    é a mesma.
    """
    if not texto:
        return None
    limpo = _normaliza(texto)
    for nome, padrao in tuple(_COMPILADOS) + tuple(_extras(clinic)):
        if padrao.search(limpo):
            return nome
    return None


def termos_da_clinica(clinic: Optional[Dict]) -> Sequence[str]:
    """Os termos extras configurados, para a tela de configuração mostrar."""
    return (clinic or {}).get("bot_procedimentos_fora_do_escopo") or []
