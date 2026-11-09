# -*- coding: utf-8 -*-
"""A mensagem pede uma data sem oferecer nenhuma?

Em 09/11/2026, numa lead da Nobre Laser, o bot fechou o valor e escreveu "Agora
me diz: qual data fica melhor pra você?" sem ter chamado `check_availability` -
os logs do turno mostram só `list_areas` e `calculate_discount`. A Nobre atende
em cerca de uma data por mês: a pergunta aberta convida a pessoa a escolher um
dia que não existe. Em 19/10/2026 o mesmo aconteceu na Essência, e a resposta
dela foi "Já te respondi".

O prompt manda chamar a tool, com todas as letras. A `proveniencia` barra data
AFIRMADA sem respaldo - mas "qual data fica melhor?" não afirma nada, e passa.
Este módulo é o mesmo verificador visto do lado da PERGUNTA.

O que salva a pergunta legítima é a ordem das duas condições: "Nossas próximas
datas são 21, 22, 27 e 28 de outubro. Qual dia fica melhor?" casa com os
padrões abaixo e está CORRETA. Ela oferece datas, e por isso não é o caso.
"""
import logging
import re
import unicodedata

from src.services.proveniencia import fatos_de_agenda, fatos_sensiveis

logger = logging.getLogger(__name__)

# Conferidos contra as duas conversas reais e contra os casos legítimos da mesma
# varredura de produção. Ampliar sem esse lastro barra mensagem boa.
PEDE_ESCOLHA = re.compile(
    r"qual\s+(?:a\s+|seria\s+a\s+|e\s+a\s+)?(?:melhor\s+)?(?:data|dia)"
    r"|(?:data|dia)\s+(?:fica|seria|e)\s+melhor"
    r"|que\s+dia\s+(?:fica|seria|voce|vc|te|melhor|prefere)"
    r"|quando\s+(?:voce|vc)?\s*(?:fica|seria|prefere|poderia|pode|consegue)"
)

# Decisão §7.3 do PRD: oferecer ver as datas antes de consultar custa um turno,
# mas não inventa dia nenhum. Só é medido.
OFERECE_VER = re.compile(
    r"quer\s+(?:que\s+eu\s+)?(?:ver|veja|te\s+mostre|mostrar)[^?]{0,40}(?:datas|dias|agenda|horarios)"
    r"|posso\s+(?:ver|consultar|checar)[^?]{0,40}(?:datas|dias|agenda|horarios)"
)


def _normaliza(texto):
    plano = unicodedata.normalize("NFKD", (texto or "").lower())
    sem_acento = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento)


def oferece_nenhuma_data(texto):
    """O texto não traz data nem horário nenhum.

    Usa o extrator da `proveniencia` de propósito: é quem já decide no projeto
    o que conta como data e o que conta como horário. Duas réguas para a mesma
    pergunta divergiriam em silêncio.
    """
    try:
        return not fatos_de_agenda(fatos_sensiveis(texto))
    except Exception as e:  # pragma: no cover - o extrator não deve cair
        logger.error(f"[PerguntaDeData] Falha ao ler os fatos do texto: {e}")
        # Falha aberta: na dúvida a mensagem segue. Calar o bot por um erro
        # deste módulo é pior do que a pergunta que ele evita.
        return False


def pede_data_sem_consulta(texto):
    """A mensagem pede que a pessoa escolha uma data, sem oferecer nenhuma."""
    if not (texto or "").strip():
        return False
    if not oferece_nenhuma_data(texto):
        return False
    return PEDE_ESCOLHA.search(_normaliza(texto)) is not None


def oferece_ver_as_datas(texto):
    """A variante branda: "quer ver as datas disponíveis?" antes de consultar.

    Não bloqueia nada (PRD §7.3). Existe para o log medir quanto ela acontece.
    """
    if not (texto or "").strip():
        return False
    return OFERECE_VER.search(_normaliza(texto)) is not None
