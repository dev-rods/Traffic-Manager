# -*- coding: utf-8 -*-
"""O endereço de uma clínica não pode aparecer no texto de outra.

Em 09/11/2026 uma lead da Nobre Laser (São José dos Campos) recebeu, na
mensagem que fecha o agendamento, o endereço da Essência (Rua Augusta, em São
Paulo). A causa não foi código: o `AI_SYSTEM_PROMPT` da Nobre em produção era
uma cópia byte a byte do da Essência, e o bloco "AO FECHAR O AGENDAMENTO"
trazia o endereço **escrito à mão**, não por variável. O mesmo prompt tinha
`{{clinic_address}}` no topo, com o endereço certo - o modelo obedeceu à
instrução literal, que é mais específica.

Copiar o prompt de uma clínica para a próxima é o caminho natural de cadastro,
e vai acontecer de novo. O que não pode acontecer de novo é o texto copiado
carregar o endereço de quem foi copiado sem ninguém perceber.

Esta é a regra, em um lugar só: `endereco_alheio` responde se um texto carrega
o endereço de OUTRA clínica. Usada na escrita do template (recusa) e pelo
script que corrige o que já está gravado.
"""
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# "Rua Augusta, 2709" -> ("rua augusta", "2709"). O que identifica um endereço
# sem depender do resto (bairro, conjunto, cidade) é logradouro + número: é o
# par que sobrevive à reescrita do texto por quem copiou.
TIPOS = r"(?:rua|r\.|avenida|av\.?|alameda|al\.|travessa|tv\.|praca|pca\.|rodovia|rod\.|estrada|largo)"
_NUCLEO = re.compile(rf"\b{TIPOS}\s+([^,;\n]{{3,80}}?)\s*,?\s*(?:n[o°º]?\.?\s*)?(\d{{1,6}})\b")


def normaliza(texto):
    plano = unicodedata.normalize("NFKD", (texto or "").lower())
    sem_acento = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento)


def nucleo(endereco):
    """(logradouro, numero) do endereço, ou None se não houver o par."""
    m = _NUCLEO.search(normaliza(endereco))
    if not m:
        return None
    return m.group(1).strip(), m.group(2)


def menciona(conteudo, endereco):
    """O texto cita este endereço, mesmo reescrito ou quebrado em linhas?"""
    n = nucleo(endereco)
    if not n:
        return False
    logradouro, numero = n
    # Entre logradouro e número pode haver vírgula, quebra de linha ou nada -
    # foi assim que o bloco copiado escreveu ("Rua Augusta, 2709").
    padrao = re.escape(logradouro) + r"[\s,;.\-]{0,10}" + re.escape(numero) + r"\b"
    return re.search(padrao, normaliza(conteudo)) is not None


def endereco_alheio(conteudo, clinic_id, enderecos):
    """A primeira clínica, que não esta, cujo endereço aparece no texto.

    `enderecos` é um dict {clinic_id: address}. Devolve (clinic_id, endereco)
    ou None. Clínica sem endereço cadastrado não acusa nada: não há o que
    comparar, e inventar suspeita aqui pararia cadastro legítimo.
    """
    for outra, endereco in sorted((enderecos or {}).items()):
        if outra == clinic_id or not (endereco or "").strip():
            continue
        if menciona(conteudo, endereco):
            return outra, endereco
    return None


def enderecos_das_clinicas(db):
    """{clinic_id: address} de todas as clínicas. Falha alto: quem chama está
    decidindo se grava, e decidir sem a lista é decidir no escuro."""
    linhas = db.execute_query(
        "SELECT clinic_id, address FROM scheduler.clinics WHERE address IS NOT NULL", ())
    return {l["clinic_id"]: l["address"] for l in linhas}


MENSAGEM = ("O texto cita o endereco de outra clinica ({dona}: {endereco}). "
            "Use a variavel {{clinic_address}}, que renderiza o endereco desta "
            "clinica, e deixe as referencias de localizacao no FAQ.")


def recusa_endereco_alheio(db, clinic_id, conteudo):
    """A mensagem de recusa, ou None se o texto está limpo.

    Falha aberta de propósito: se a consulta das clínicas cair, o cadastro do
    template não para. Esta função protege contra descuido, não contra ataque,
    e barrar toda escrita de template porque o banco piscou é pior do que a
    cópia que ela evita - que, além disso, o script de auditoria pega depois.
    """
    try:
        enderecos = enderecos_das_clinicas(db)
    except Exception as e:  # pragma: no cover - caminho de indisponibilidade
        logger.error(f"[EnderecoAlheio] Nao foi possivel conferir {clinic_id}: {e}")
        return None
    alheio = endereco_alheio(conteudo, clinic_id, enderecos)
    if not alheio:
        return None
    return MENSAGEM.format(dona=alheio[0], endereco=alheio[1])
