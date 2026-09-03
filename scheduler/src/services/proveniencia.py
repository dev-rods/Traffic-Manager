"""De onde veio cada afirmação da resposta.

O prompt já proíbe afirmar preço, data, horário ou status sem consultar - com
todas as letras, no limite da ênfase. Em 02/09/2026 o bot afirmou que um
agendamento cancelado estava confirmado mesmo assim: ele releu a própria
mensagem de 29/08, quando aquilo ainda era verdade. Não foi alucinação, foi
memória desatualizada, e nenhuma instrução cobre isso de forma confiável.

Este módulo é a camada determinística em volta do modelo: extrai da resposta os
fatos que não podem ser inventados e confere cada um contra o que as tools
devolveram naquela execução. Barato, reproduzível, e não flutua entre chamadas.
"""
import re
import unicodedata
from datetime import date

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11,
    "dezembro": 12,
}

# Só afirmações contam. "Está confirmada?" é pergunta; "Está confirmada!" é fato.
STATUS = {
    "confirmado": ("confirmada", "confirmado"),
    "cancelado": ("cancelada", "cancelado"),
    "reagendado": ("reagendada", "reagendado"),
}

_DATA_NUMERICA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_DATA_EXTENSO = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?\b", re.IGNORECASE
)
_HORA = re.compile(r"\b(\d{1,2})\s*(?:h|:)\s*(\d{2})?\b")
# "35 minutos", "35 min". Duração era o único fato sensível sem extrator, e
# por isso uma duração inventada passava pelo verificador como se fosse ok.
_DURACAO = re.compile(r"\b(\d{1,3})\s*(?:min\b|minutos?\b)", re.IGNORECASE)
_DINHEIRO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{2}))?", re.IGNORECASE)


def _sem_acento(texto):
    return "".join(
        c for c in unicodedata.normalize("NFKD", (texto or "").lower())
        if not unicodedata.combining(c)
    )


def _data(dia, mes, ano, ano_padrao):
    try:
        dia, mes = int(dia), int(mes)
        ano = int(ano) if ano else ano_padrao
        if ano < 100:
            ano += 2000
        if not (1 <= mes <= 12 and 1 <= dia <= 31):
            return None
        return f"{ano:04d}-{mes:02d}-{dia:02d}"
    except (TypeError, ValueError):
        return None


def fatos_sensiveis(texto, ano=None):
    """Os fatos de banco afirmados neste texto, normalizados.

    Datas viram YYYY-MM-DD, horários HH:MM, dinheiro R$0.00, durações
    'duracao:35' e status 'status:confirmado'. A normalização é o que permite comparar "23/09" da
    resposta com "2026-09-23" da tool.

    Perguntas não entram: quem pergunta não está afirmando nada.
    """
    texto = texto or ""
    ano = ano or date.today().year
    achados = set()

    for trecho in _frases_afirmativas(texto):
        plano = _sem_acento(trecho)

        for dia, mes, ano_txt in _DATA_NUMERICA.findall(trecho):
            d = _data(dia, mes, ano_txt, ano)
            if d:
                achados.add(d)

        for dia, mes_txt, ano_txt in _DATA_EXTENSO.findall(trecho):
            mes = MESES.get(_sem_acento(mes_txt))
            if mes:
                d = _data(dia, mes, ano_txt, ano)
                if d:
                    achados.add(d)

        for hora, minuto in _HORA.findall(trecho):
            h = int(hora)
            if 0 <= h <= 23:
                achados.add(f"{h:02d}:{int(minuto or 0):02d}")

        for minutos in _DURACAO.findall(trecho):
            achados.add(f"duracao:{int(minutos)}")

        for inteiro, centavos in _DINHEIRO.findall(trecho):
            valor = float(inteiro.replace(".", "")) + int(centavos or 0) / 100
            achados.add(f"R${valor:.2f}")

        for chave, palavras in STATUS.items():
            if any(p in plano for p in palavras):
                achados.add(f"status:{chave}")

    return achados


def _frases_afirmativas(texto):
    """Separa o texto em frases, descartando as interrogativas.

    "Qual horário prefere?" não afirma horário nenhum - cobrar origem dela
    faria o guardrail disparar em conversa normal.
    """
    for frase in re.split(r"(?<=[.!?\n])\s*", texto or ""):
        if frase.strip() and not frase.rstrip().endswith("?"):
            yield frase


def _valores_das_tools(resultado, encontrados, chave_pai=None):
    """Percorre o resultado da tool em qualquer profundidade.

    Os retornos chegam embrulhados de formas diferentes por tool; procurar por
    caminho fixo deixaria passar valor legítimo e o guardrail barraria resposta
    correta.

    Escalar solto dentro de lista herda a chave de quem o contém. Sem isso,
    `available_slots: ["18:00", "18:15"]` ficava invisível - os horários não
    tinham chave própria e nunca chegavam ao extrator, então o bot listava os
    horários que a tool devolveu e era acusado de tê-los inventado.
    """
    if isinstance(resultado, dict):
        for chave, valor in resultado.items():
            if isinstance(valor, (dict, list)):
                _valores_das_tools(valor, encontrados, chave)
            else:
                _valor_simples(chave, valor, encontrados)
    elif isinstance(resultado, list):
        for item in resultado:
            if isinstance(item, (dict, list)):
                _valores_das_tools(item, encontrados, chave_pai)
            else:
                _valor_simples(chave_pai or "", item, encontrados)


def _valor_simples(chave, valor, encontrados):
    if valor is None:
        return
    texto = str(valor)
    chave_plana = _sem_acento(chave)

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        encontrados.add(texto)
    elif re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", texto):
        h, m = texto.split(":")[:2]
        encontrados.add(f"{int(h):02d}:{int(m):02d}")
    elif "cents" in chave_plana and str(valor).isdigit():
        encontrados.add(f"R${int(valor) / 100:.2f}")
    elif chave_plana.endswith("price") and str(valor).replace(".", "").isdigit():
        encontrados.add(f"R${float(valor):.2f}")
    elif "duration" in chave_plana and str(valor).isdigit():
        encontrados.add(f"duracao:{int(valor)}")
    elif chave_plana == "status":
        mapa = {"CONFIRMED": "confirmado", "CANCELLED": "cancelado",
                "RESCHEDULED": "reagendado"}
        rotulo = mapa.get(texto.upper())
        if rotulo:
            encontrados.add(f"status:{rotulo}")
    elif isinstance(valor, str):
        # Datas e horas também aparecem no meio de textos que a tool devolve.
        for d, m, a in _DATA_NUMERICA.findall(texto):
            achado = _data(d, m, a, date.today().year)
            if achado:
                encontrados.add(achado)


def fatos_sem_origem(resposta, resultados_de_tools, ano=None):
    """Os fatos afirmados na resposta que nenhuma tool respaldou.

    Conjunto vazio significa que tudo que a resposta afirma tem origem. Qualquer
    item devolvido é uma afirmação que o modelo produziu sozinho.
    """
    afirmados = fatos_sensiveis(resposta, ano=ano)
    if not afirmados:
        return set()

    respaldados = set()
    for resultado in resultados_de_tools or []:
        _valores_das_tools(resultado, respaldados)

    return afirmados - respaldados
