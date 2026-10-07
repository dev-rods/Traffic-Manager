# -*- coding: utf-8 -*-
"""Quantos dias a pessoa terá de vida no dia da sessão.

A conta é em DIAS de propósito, e a data de referência é a da sessão, não a de
hoje. As duas escolhas são do André, e as duas evitam o mesmo erro: quem faz 18
anos entre a conversa e a sessão é maior de idade na cadeira, e quem completa 18
no dia seguinte à sessão ainda é menor quando o laser liga. "Tem 17" não
responde isso; "faltam 12 dias" responde.

Idade em anos também sai daqui, e sai da MESMA conta - não de uma segunda
fórmula. Duas contas de idade divergindo em silêncio é o defeito que mais custou
nesta base.

Nunca peça ao modelo para calcular isto. Ele erra data, e erra com convicção:
ver o bloco CALENDÁRIO, que existe porque ele se enrolava com dia da semana.
"""
import logging
import re
from datetime import date, datetime

logger = logging.getLogger(__name__)

MAIORIDADE_EM_ANOS = 18


def para_data(valor):
    """A data em `valor`, ou None. Aceita o que a conversa produz.

    `date` e `datetime` passam direto - o banco devolve `date`, e convertê-lo
    para texto só para reconverter aqui é ida e volta que só cria bug.
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = (valor or "").strip() if isinstance(valor, str) else ""
    if not texto:
        return None

    iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", texto)
    if iso:
        ano, mes, dia = (int(g) for g in iso.groups())
    else:
        # 05/11/2008 e 5-11-2008: a pessoa escreve como quiser.
        br = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", texto)
        if not br:
            return None
        dia, mes, ano = (int(g) for g in br.groups())

    try:
        return date(ano, mes, dia)
    except ValueError:
        # 30/02 e 31/04 chegam de digitação errada. Data impossível não é data.
        return None


def em_dias(nascimento, na_data):
    """Dias vividos na data de referência. None se faltar alguma das datas.

    Negativo quer dizer nascimento depois da referência - e não é sempre erro:
    a data pode ter sido digitada trocada. Quem decide o que fazer é o chamador.
    """
    inicio, fim = para_data(nascimento), para_data(na_data)
    if not inicio or not fim:
        return None
    return (fim - inicio).days


def em_anos(nascimento, na_data):
    """Anos completos na data de referência. None se faltar alguma das datas.

    Aniversário no dia conta como completo: quem faz 18 no dia da sessão já é
    maior de idade quando chega.
    """
    inicio, fim = para_data(nascimento), para_data(na_data)
    if not inicio or not fim:
        return None
    anos = fim.year - inicio.year
    if (fim.month, fim.day) < (inicio.month, inicio.day):
        anos -= 1
    return anos


def e_menor_de_idade(nascimento, na_data):
    """Menor de 18 na data da sessão? None quando não dá para saber.

    None NÃO é "não". Sem data de nascimento ninguém sabe a idade, e tratar
    desconhecido como adulto é exatamente o silêncio que esta regra existe para
    quebrar - quem chama precisa distinguir os dois casos.
    """
    anos = em_anos(nascimento, na_data)
    if anos is None:
        return None
    return anos < MAIORIDADE_EM_ANOS


def dias_para_a_maioridade(nascimento, na_data):
    """Quantos dias faltam para os 18, contados da data da sessão.

    Zero ou negativo quer dizer que já é maior. Serve para a atendente saber se
    o caso é de esperar uma semana ou de pedir autorização de verdade.
    """
    inicio, fim = para_data(nascimento), para_data(na_data)
    if not inicio or not fim:
        return None
    try:
        maioridade = inicio.replace(year=inicio.year + MAIORIDADE_EM_ANOS)
    except ValueError:
        # Nasceu em 29/02: a maioridade cai em 01/03 do ano não bissexto.
        maioridade = date(inicio.year + MAIORIDADE_EM_ANOS, 3, 1)
    return (maioridade - fim).days
