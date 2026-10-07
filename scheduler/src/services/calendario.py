# -*- coding: utf-8 -*-
"""O calendário do agente: que dia é hoje e o que a pessoa quis dizer com
"amanhã", "semana que vem", "sexta".

O modelo não tem relógio. Nada no prompt nem nas tools dizia a data atual, e a
consequência apareceu em produção em 04/09/2026: a pessoa pediu "gostaria de
agendar para amanhã", o agente consultou a agenda corretamente e respondeu
"não consigo calcular amanhã automaticamente - pode escolher a data na lista?".
Ele não estava confuso; ele não tinha a entrada.

A resolução é feita aqui, no código, e não pelo modelo, por dois motivos:

1. É aritmética de calendário com fuso - determinística por natureza. Pedir ao
   modelo que some um dia é aceitar erro numa classe de problema que não tem
   por que ter erro.
2. O resultado entra como fato consultado. Uma data que o modelo deduzisse
   sozinha seria barrada pelo verificador de proveniência, e o bot calaria -
   trocaríamos uma falha visível por uma pior.

O conjunto de expressões é fechado de propósito. Tentar cobrir toda forma de
falar de data com regex é o caminho para casar com o que não é data: "segunda"
é dia da semana e também é "segunda sessão".
"""
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

# A clínica, as pacientes e a agenda estão todas em horário de Brasília. A
# Lambda roda em UTC: sem o deslocamento, das 21h à meia-noite BRT o "hoje" do
# agente já seria o dia seguinte e "amanhã" cairia dois dias à frente.
FUSO_BRT = timezone(timedelta(hours=-3))

DIAS_DA_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]

_DIA_POR_NOME = {
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sabado": 5, "domingo": 6,
}

# "segunda" e "terca" tambem sao numerais ordinais. Sem esta guarda, "na segunda
# sessao" viraria uma data e o agente responderia sobre agenda quando a pessoa
# falava de tratamento.
_NAO_E_DIA_DEPOIS = r"(?!\s+(?:sessao|sessoes|vez|vezes|opcao|opcoes|area|areas|etapa|parte))"

_MARCADOR_DE_DIA = re.compile(
    r"\b(?:n[ao]\s+|nessa\s+|nesta\s+|essa\s+|esta\s+|proxim[ao]\s+)?"
    r"(segunda|terca|quarta|quinta|sexta|sabado|domingo)"
    + _NAO_E_DIA_DEPOIS
    + r"(?:\s*-?\s*feira)?"
    r"(?:\s+que\s+vem|\s+proxim[ao])?\b"
)

_DAQUI_A = re.compile(r"\bdaqui\s+a\s+(\d{1,2})\s+dias?\b")
_DIA_DO_MES = re.compile(r"\bdia\s+(\d{1,2})\b(?!\s*[/-])")


def _sem_acento(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    ).lower()


def hoje_brt():
    """A data corrente no fuso da clínica."""
    return datetime.now(FUSO_BRT).date()


def rotulo(d):
    """`quinta-feira, 04/09/2026` - como a data aparece para o modelo."""
    return f"{DIAS_DA_SEMANA[d.weekday()]}, {d.strftime('%d/%m/%Y')}"


def _proximo_dia_da_semana(hoje, alvo):
    """A próxima ocorrência do dia da semana, sempre à frente.

    Nunca devolve hoje: quem diz "quinta" numa quinta-feira à tarde está
    marcando a semana que vem, não daqui a cinco minutos.
    """
    delta = (alvo - hoje.weekday()) % 7
    return hoje + timedelta(days=delta or 7)


def _semana_que_vem(hoje):
    segunda = hoje + timedelta(days=7 - hoje.weekday())
    return [segunda + timedelta(days=i) for i in range(7)]


def _fim_de_semana(hoje):
    sabado = _proximo_dia_da_semana(hoje, 5)
    return [sabado, sabado + timedelta(days=1)]


def _dia_do_mes(hoje, dia):
    """Dia N do mês corrente; se já passou, do mês seguinte."""
    if dia < 1 or dia > 31:
        return []
    for mes_a_frente in (0, 1, 2):
        ano, mes = hoje.year, hoje.month + mes_a_frente
        ano, mes = ano + (mes - 1) // 12, (mes - 1) % 12 + 1
        try:
            candidato = date(ano, mes, dia)
        except ValueError:
            continue  # dia 31 num mês de 30
        if candidato >= hoje:
            return [candidato]
    return []


def referencias(texto, hoje=None):
    """As datas que a mensagem menciona por referência, não por número.

    Devolve uma lista de `(expressao, [datas])` na ordem em que foram
    reconhecidas. Mensagem sem referência relativa devolve lista vazia - o
    normal, e por isso o bloco de calendário não polui todo turno.
    """
    hoje = hoje or hoje_brt()
    t = _sem_acento(texto)
    if not t.strip():
        return []

    achadas = []
    vistas = set()

    def registra(expressao, datas):
        datas = [d for d in datas if d]
        if datas and expressao not in vistas:
            vistas.add(expressao)
            achadas.append((expressao, datas))

    # Ordem importa: "depois de amanha" contem "amanha".
    if "depois de amanha" in t:
        registra("depois de amanhã", [hoje + timedelta(days=2)])
    elif "amanha" in t:
        registra("amanhã", [hoje + timedelta(days=1)])

    if re.search(r"\bhoje\b", t):
        registra("hoje", [hoje])

    if re.search(r"\b(?:semana que vem|proxima semana|semana proxima)\b", t):
        registra("semana que vem", _semana_que_vem(hoje))

    if re.search(r"\b(?:fim|final)\s+de\s+semana\b", t):
        registra("fim de semana", _fim_de_semana(hoje))

    m = _DAQUI_A.search(t)
    if m:
        dias = int(m.group(1))
        if 1 <= dias <= 60:
            registra(f"daqui a {dias} dias", [hoje + timedelta(days=dias)])

    for m in _DIA_DO_MES.finditer(t):
        registra(f"dia {int(m.group(1))}", _dia_do_mes(hoje, int(m.group(1))))

    # "fim de semana" ja consumiu "semana"; o marcador de dia roda por ultimo
    # para nao competir com as expressoes mais especificas acima.
    for m in _MARCADOR_DE_DIA.finditer(t):
        nome = m.group(1)
        registra(nome, [_proximo_dia_da_semana(hoje, _DIA_POR_NOME[nome])])

    return achadas


def bloco_de_contexto(texto, hoje=None):
    """O texto que vai para o modelo, e as datas ISO que ele pode citar.

    Devolve `(bloco, datas_iso)`. As datas voltam separadas porque entram no
    respaldo de proveniência: sem isso, dizer "amanhã (05/09) não temos vaga"
    seria uma data sem origem e a resposta seria bloqueada.

    O bloco sempre traz HOJE, mesmo sem referência reconhecida - é a âncora que
    faltava, e custa uma linha.
    """
    hoje = hoje or hoje_brt()
    achadas = referencias(texto, hoje)

    linhas = [f"HOJE é {rotulo(hoje)}."]
    for expressao, datas in achadas:
        if len(datas) == 1:
            linhas.append(f'"{expressao}" = {rotulo(datas[0])}')
        else:
            linhas.append(
                f'"{expressao}" = de {rotulo(datas[0])} a {rotulo(datas[-1])}'
            )

    datas_iso = [hoje.isoformat()]
    for _, datas in achadas:
        datas_iso.extend(d.isoformat() for d in datas)

    return "\n".join(linhas), sorted(set(datas_iso))
