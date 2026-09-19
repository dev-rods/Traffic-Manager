# -*- coding: utf-8 -*-
"""Os parâmetros iniciais do laser: três métodos, dois tipos de pele.

Transcrito dos dois materiais de consulta da clínica (`Documentos Laser/`,
19/09/2026): "Parâmetros iniciais para peles brancas e claras" (fototipos I-III)
e "Parâmetros iniciais para pele morena e pele negra" (IV-VI).

Cada método tem um formato de parâmetro DIFERENTE, e é por isso que a aplicação
não pode ser um campo de texto:

    SHR            Fluência (J) + Energia (kJ)
    SHR Stacking   Fluência (J) + Stacks + Passadas
    HR             Fluência (J) + Energia (kJ, fixa em 1,0)

Os rótulos ficam como os PDFs escrevem - `Fluência (J)`, `Energia (kJ)`. É o que
a profissional lê no material dela, e prontuário não é lugar de inventar unidade.


O mapa é tabela, e isso não é detalhe
-------------------------------------
Os nomes do protocolo NÃO são os do catálogo: `1/2 Braço` aqui é `Meio braço`,
`Orelhas` é `Orelha externa`, `Perianal/ânus` é `Região perianal`. Oito áreas
vendidas não têm protocolo e quatro do protocolo não são vendidas.

Em 16/09/2026 uma trava comparou nomes de área por aproximação e `Virilha Comp. +
ânus` ficou inalcançável: a paciente respondeu certo cinco vezes e a conversa caiu
para uma atendente. Lá o erro custou constrangimento. Aqui custaria sugerir a
fluência de OUTRA área num equipamento que queima pele.

Por isso `MAPA_DE_AREAS` é tabela explícita, revisada por quem aplica, e
`sugestao` devolve None quando não há linha - "sem parâmetro sugerido" é resposta
válida. Nunca aproximar, nunca cair no valor de outro método ou de outro tipo de
pele.


O que o software NÃO faz
------------------------
Avisa e não bloqueia. Os documentos são categóricos sobre HR em pele bronzeada
("nunca utilize") e sobre fototipo VI, e a tela mostra isso palavra por palavra.
Mas quem decide conduta é quem aplica: software que impede acaba contornado por
fora, e aí a sessão acontece sem registro nenhum - que é pior que a sessão
registrada com um aviso ignorado.

O bot não chega aqui. Nenhuma tool do agente expõe protocolo, parâmetro ou tipo
de pele.
"""
import logging
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

BRANCA, NEGRA = "BRANCA", "NEGRA"
SHR, SHR_STACKING, HR = "SHR", "SHR_STACKING", "HR"

# Os campos que cada método usa. Fonte única: o backend valida por aqui e
# `frontend/src/lib/protocolo.ts` espelha esta mesma tabela.
METODOS = {
    SHR: {
        "rotulo": "SHR",
        "campos": ("fluence_j", "energy_kj"),
        "movimento": "contínuo e levemente rápido",
    },
    SHR_STACKING: {
        "rotulo": "SHR Stacking",
        "campos": ("fluence_j", "stacks", "passes"),
        "movimento": "pontual (ponteira parada) ou arraste lento",
    },
    HR: {
        "rotulo": "HR",
        "campos": ("fluence_j", "energy_kj"),
        "movimento": "pontual, com a ponteira parada",
    },
}

# De onde veio cada linha. A tabela é referência clínica: quem ler daqui a um ano
# precisa distinguir o que está no material impresso do que foi decisão da
# clínica. Ver o anexo do PRD 012.
ORIGEM_PDF, ORIGEM_CLINICA = "PDF", "CLINICA"

# ─────────────────────────────────────────────────────────────────────────────
# As linhas. (skin_type, method, key, nome_no_documento, fluencia, energia,
# stacks, passadas, origem)
#
# Conferidas uma a uma contra os PDFs por test_protocolo_laser. Mexer aqui sem
# mexer lá quebra o teste de propósito: número de laser não se altera de
# passagem.
# ─────────────────────────────────────────────────────────────────────────────

def _shr(pele, chave, nome, fluencia, energia, origem=ORIGEM_PDF):
    return (pele, SHR, chave, nome, fluencia, energia, None, None, origem)


def _stack(pele, chave, nome, fluencia, stacks=3, passadas=2, origem=ORIGEM_PDF):
    return (pele, SHR_STACKING, chave, nome, fluencia, None, stacks, passadas, origem)


def _hr(pele, chave, nome, fluencia, origem=ORIGEM_PDF):
    # A energia do HR é fixa em 1,0 do início ao fim do tratamento.
    return (pele, HR, chave, nome, fluencia, 1.0, None, None, origem)


PROTOCOLO = (
    # ── SHR ──────────────────────────────────────────────────────────────────
    _shr(BRANCA, "linha_alba", "Linha alba", 7, 5),
    _shr(BRANCA, "axilas", "Axilas", 7, 8),
    _shr(BRANCA, "meio_braco", "Meio braço", 7, 8),
    _shr(BRANCA, "lombar", "Lombar", 7, 8),
    _shr(BRANCA, "gluteos", "Glúteos", 8, 14),
    _shr(BRANCA, "coxas", "Coxas", 8, 14),
    _shr(BRANCA, "meia_perna", "Meia perna", 8, 14),
    _shr(BRANCA, "virilha_simples", "Virilha simples", 7, 5),
    _shr(BRANCA, "virilha_cavada", "Virilha cavada", 7, 5),
    _shr(BRANCA, "virilha_completa", "Virilha completa", 7, 6),
    _shr(BRANCA, "interno_virilha", "Interno da virilha (lábios)", 6, 3),
    _shr(BRANCA, "peitoral", "Peitoral", 7, 8),
    _shr(BRANCA, "abdomen", "Abdômen", 7, 8),
    _shr(BRANCA, "costas", "Costas", 7, 8),
    _shr(BRANCA, "ombros", "Ombros", 7, 8),

    _shr(NEGRA, "linha_alba", "Linha alba", 5, 4),
    _shr(NEGRA, "axilas", "Axilas", 5, 7),
    _shr(NEGRA, "meio_braco", "Meio braço", 5, 7),
    _shr(NEGRA, "lombar", "Lombar", 5, 7),
    _shr(NEGRA, "gluteos", "Glúteos", 7, 12),
    _shr(NEGRA, "coxas", "Coxas", 7, 12),
    _shr(NEGRA, "meia_perna", "Meia perna", 7, 12),
    _shr(NEGRA, "virilha_simples", "Virilha simples", 5, 4),
    _shr(NEGRA, "virilha_cavada", "Virilha cavada", 5, 4),
    _shr(NEGRA, "virilha_completa", "Virilha completa", 5, 5),
    _shr(NEGRA, "interno_virilha", "Interno da virilha (lábios)", 4, 2.5),
    _shr(NEGRA, "peitoral", "Peitoral", 5, 7),
    _shr(NEGRA, "abdomen", "Abdômen", 5, 7),
    _shr(NEGRA, "costas", "Costas", 5, 7),
    _shr(NEGRA, "ombros", "Ombros", 5, 7),

    # Meio glúteo: dado pelo André em 19/09/2026, não está nos PDFs. Mesma
    # fluência do glúteo inteiro, metade da energia - a energia escala com a
    # área tratada.
    #
    # SÓ pele branca, de propósito. O 8 J é o valor da branca; na negra o glúteo
    # inteiro é 7 J, e copiar 8 para lá sugeriria ACIMA do protocolo dela, que é
    # a direção que queima. Na pele negra a tela dirá "sem parâmetro sugerido"
    # até alguém de dentro da clínica dar o número.
    _shr(BRANCA, "meio_gluteo", "Meio glúteo", 8, 7, ORIGEM_CLINICA),

    # ── SHR Stacking ─────────────────────────────────────────────────────────
    _stack(BRANCA, "buco", "Buço", 6),
    _stack(BRANCA, "mento_queixo", "Mento ou queixo", 6),
    _stack(BRANCA, "rosto_completo", "Rosto completo", 6),
    _stack(BRANCA, "pescoco", "Pescoço", 6),
    _stack(BRANCA, "areola", "Aréola", 6),
    _stack(BRANCA, "mao_pe_dedos", "Mão ou pé e dedos", 6),
    _stack(BRANCA, "regiao_perianal", "Região perianal", 6),
    _stack(BRANCA, "interno_virilha", "Interno da virilha (reforço)", 6),
    _stack(BRANCA, "costeleta", "Costeleta", 6),
    _stack(BRANCA, "barba_contorno", "Contorno ou desenho da barba", 6),
    _stack(BRANCA, "barba_completa", "Barba completa", 5),
    _stack(BRANCA, "nuca", "Nuca", 5),
    _stack(BRANCA, "orelha_externa", "Orelha externa", 5),

    _stack(NEGRA, "buco", "Buço", 5),
    _stack(NEGRA, "mento_queixo", "Mento ou queixo", 5),
    _stack(NEGRA, "rosto_completo", "Rosto completo", 5),
    _stack(NEGRA, "pescoco", "Pescoço", 5),
    _stack(NEGRA, "areola", "Aréola", 5),
    _stack(NEGRA, "mao_pe_dedos", "Mão ou pé e dedos", 5),
    _stack(NEGRA, "regiao_perianal", "Região perianal", 5),
    _stack(NEGRA, "interno_virilha", "Interno da virilha (reforço)", 4),
    _stack(NEGRA, "costeleta", "Costeleta", 5),
    _stack(NEGRA, "barba_contorno", "Contorno ou desenho da barba", 5),
    _stack(NEGRA, "barba_completa", "Barba completa", 4),
    _stack(NEGRA, "nuca", "Nuca", 4),
    _stack(NEGRA, "orelha_externa", "Orelha externa", 4),

    # Glabela e nariz: dados pelo André em 19/09/2026, fora dos PDFs. Ponteira
    # pontual, 2 stacks (todas as linhas dos documentos são 3).
    #
    # Veio UM valor só, e todas as demais linhas diferem entre branca e negra.
    # Semeado 4 para as duas: nas áreas de Stacking a branca vai de 5 a 6, então
    # 4 erra para o lado seguro nela. Se a negra tiver de ser menor, alguém da
    # clínica precisa dar o número.
    _stack(BRANCA, "glabela", "Glabela (entre as sobrancelhas)", 4, stacks=2,
           origem=ORIGEM_CLINICA),
    _stack(NEGRA, "glabela", "Glabela (entre as sobrancelhas)", 4, stacks=2,
           origem=ORIGEM_CLINICA),
    _stack(BRANCA, "nariz", "Nariz", 4, stacks=2, origem=ORIGEM_CLINICA),
    _stack(NEGRA, "nariz", "Nariz", 4, stacks=2, origem=ORIGEM_CLINICA),

    # ── HR ───────────────────────────────────────────────────────────────────
    _hr(BRANCA, "buco", "Buço", 17),
    _hr(BRANCA, "mento_queixo", "Mento ou queixo", 17),
    _hr(BRANCA, "areola", "Aréola", 17),
    _hr(BRANCA, "costeleta", "Costeleta", 17),
    _hr(BRANCA, "barba_contorno", "Contorno ou desenho da barba", 15),
    _hr(BRANCA, "interno_virilha", "Interno da virilha (reforço)", 15),
    _hr(BRANCA, "axilas", "Axila", 17),
    _hr(BRANCA, "joelho", "Joelho", 15),
    _hr(BRANCA, "cotovelo", "Cotovelo", 17),

    _hr(NEGRA, "buco", "Buço", 14),
    _hr(NEGRA, "mento_queixo", "Mento ou queixo", 14),
    _hr(NEGRA, "areola", "Aréola", 14),
    _hr(NEGRA, "costeleta", "Costeleta", 14),
    _hr(NEGRA, "barba_contorno", "Contorno ou desenho da barba", 12),
    _hr(NEGRA, "interno_virilha", "Interno da virilha (reforço)", 12),
    _hr(NEGRA, "axilas", "Axila", 14),
    _hr(NEGRA, "joelho", "Joelho", 12),
    _hr(NEGRA, "cotovelo", "Cotovelo", 14),
)

# ─────────────────────────────────────────────────────────────────────────────
# Do nome da área no catálogo para a chave do protocolo.
#
# Revisado pelo André em 19/09/2026. Uma área pode abrir em DUAS linhas: a
# composta `Virilha Completa + ânus` é virilha (SHR) e perianal (Stacking), que é
# o que a profissional de fato aplica.
#
# Área que não está aqui não é erro: é "sem parâmetro sugerido".
# ─────────────────────────────────────────────────────────────────────────────
MAPA_DE_AREAS = {
    "Linha alba": ("linha_alba",),
    "Axilas": ("axilas",),
    "1/2 Braço": ("meio_braco",),
    "Braço Completo": ("meio_braco",),
    "Lombar": ("lombar",),
    "Glúteo": ("gluteos",),
    "1/2 Glúteo": ("meio_gluteo",),
    "Coxas": ("coxas",),
    "1/2 Coxa": ("coxas",),
    "1/2 Perna": ("meia_perna",),
    "Perna Completa": ("meia_perna",),
    "Pernas Completas": ("meia_perna",),
    "Virilha Simples": ("virilha_simples",),
    "Virilha Cavada": ("virilha_cavada",),
    "Virilha Completa": ("virilha_completa",),
    "1/2 Virilha": ("interno_virilha",),
    "Perianal/ânus": ("regiao_perianal",),
    "Peitoral": ("peitoral",),
    "Abdômen": ("abdomen",),
    "Ombros": ("ombros",),
    "Buço": ("buco",),
    "Mento/Queixo": ("mento_queixo",),
    "Rosto Completo": ("rosto_completo",),
    "Pescoço": ("pescoco",),
    "Aréola": ("areola",),
    "Mão ou Pé + Dedos": ("mao_pe_dedos",),
    "Costeleta": ("costeleta",),
    "Barba contorno": ("barba_contorno",),
    "Nuca": ("nuca",),
    "Orelhas": ("orelha_externa",),
    "Glabela (entre as sobrancelhas)": ("glabela",),
    "Nariz": ("nariz",),

    # Compostas: abrem em duas aplicações, na ordem em que ela aplica.
    "Virilha Completa + ânus": ("virilha_completa", "regiao_perianal"),
    "Costas total + ombros": ("costas", "ombros"),
    "Peitoral + abdômen": ("peitoral", "abdomen"),
    "Barba Comp. + Pescoço": ("barba_completa", "pescoco"),
}

# Áreas do catálogo que conscientemente NÃO têm protocolo. Existir nesta lista é
# diferente de ter sido esquecida - test_mapa_de_areas exige que toda área do
# catálogo esteja no mapa OU aqui.
SEM_PROTOCOLO = frozenset()

# Os avisos, palavra por palavra dos documentos.
AVISO_BRONZEADA = (
    "Pele bronzeada: reduza a fluência. No SHR Stacking, reduza também os "
    "stacks e/ou as passadas. Nunca utilize o método HR, independentemente do "
    "fototipo."
)
AVISO_HR_PELE_NEGRA = (
    "Utilize somente nas tonalidades mais claras de pele negra, fototipos IV e "
    "V, após avaliação criteriosa. Não utilize o método HR no fototipo VI."
)
AVISO_HR_GERAL = (
    "É um método mais agressivo, mais eficiente e mais dolorido, com maior "
    "risco de queimaduras."
)


def _indice():
    return {(p[0], p[1], p[2]): p for p in PROTOCOLO}


_POR_CHAVE = _indice()


def campos_do_metodo(metodo: str) -> tuple:
    """Quais parâmetros este método usa.

    Fonte única: o handler valida por aqui e a tela desenha por aqui. Método
    desconhecido devolve vazio, e quem chama trata - levantar deixaria a tela
    sem desenhar nada por causa de um valor velho no payload.
    """
    return METODOS.get(metodo, {}).get("campos", ())


def metodos_disponiveis(protocol_area_key: str) -> List[str]:
    """Os métodos que o protocolo tem para esta área, na ordem de METODOS.

    Um só significa que a tela pode deixar escolhido. Mais de um - `Buço` tem
    Stacking e HR - fica em branco: escolher por ela seria decidir conduta.
    """
    return [m for m in METODOS
            if any(p[1] == m and p[2] == protocol_area_key for p in PROTOCOLO)]


def sugestao(protocol_area_key: str, metodo: str, skin_type: str) -> Optional[Dict]:
    """O parâmetro inicial desta área, neste método, nesta pele.

    None quando não há linha, e None é resposta VÁLIDA - a tela diz "sem
    parâmetro sugerido" e a profissional digita.

    Nunca há fallback: não cai em outro tipo de pele, não cai em outro método,
    não aproxima o nome. Sugerir a fluência de outra área é o erro que este
    módulo inteiro existe para não cometer.
    """
    linha = _POR_CHAVE.get((skin_type, metodo, protocol_area_key))
    if not linha:
        return None
    _, _, _, nome, fluencia, energia, stacks, passadas, origem = linha
    return {
        "protocol_area_key": protocol_area_key,
        "protocol_area_name": nome,
        "method": metodo,
        "fluence_j": fluencia,
        "energy_kj": energia,
        "stacks": stacks,
        "passes": passadas,
        "source": origem,
    }


def chaves_da_area(area_name: str) -> Sequence[str]:
    """As chaves de protocolo de uma área do catálogo. Vazio = sem sugestão."""
    return MAPA_DE_AREAS.get(area_name, ())


def avisos(metodo: Optional[str], skin_type: Optional[str],
           bronzeada: bool = False) -> List[str]:
    """Os avisos que a tela mostra, palavra por palavra do documento."""
    saida = []
    if bronzeada:
        saida.append(AVISO_BRONZEADA)
    if metodo == HR:
        saida.append(AVISO_HR_GERAL)
        if skin_type == NEGRA:
            saida.append(AVISO_HR_PELE_NEGRA)
    return saida


def hr_desaconselhado(skin_type: Optional[str], bronzeada: bool) -> bool:
    """O documento é categórico contra o HR neste caso?

    Só em pele bronzeada: "nunca utilize o método HR, independentemente do
    fototipo". A tela tira o HR das sugestões, mas NÃO impede - quem decide
    conduta é quem aplica, e software que impede é contornado por fora.
    """
    return bool(bronzeada)


def tabela_para_a_tela() -> List[Dict]:
    """O protocolo inteiro num payload, para a tela sugerir sem ida e volta.

    São 79 linhas e elas quase nunca mudam: uma chamada cacheada evita uma
    consulta por linha de aplicação enquanto ela digita.
    """
    return [
        {
            "skin_type": p[0], "method": p[1], "protocol_area_key": p[2],
            "protocol_area_name": p[3], "fluence_j": p[4], "energy_kj": p[5],
            "stacks": p[6], "passes": p[7], "source": p[8],
        }
        for p in PROTOCOLO
    ]
