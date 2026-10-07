# -*- coding: utf-8 -*-
"""Quem já é paciente não ouve o valor ao confirmar - só se perguntar.

Decisão do André (06/10/2026, PRD 020 fase 2): o roteiro de lead mostra o
valor no passo 3 e repete no resumo do passo 5, porque para quem nunca veio o
preço é parte da decisão. Para quem está marcando a segunda sessão em diante
o valor é conhecido, e repeti-lo a cada confirmação soa a cobrança. A campanha
já fazia isso (prompt_da_campanha, regra 3); aqui vale para qualquer paciente
recorrente, em qualquer fluxo.

Três peças, no mesmo desenho do passo de cadastro (identificacao_de_paciente):

  1. `e_recorrente`     quem é: já tem sessão feita ou agendamento marcado
  2. `sem_valor_no_roteiro`  o prompt perde o "mostre o valor" - RETIRADO, não
                         contradito
  3. `anuncia_valor` / `pediu_valor`  a trava de saída: valor na resposta sem
                         ela ter perguntado manda reescrever uma vez

`calculate_discount` continua sendo chamada antes de agendar: o preço gravado
tem de estar certo mesmo sem ser anunciado.
"""
import re
import unicodedata
from typing import Dict, Optional, Sequence

from src.services.roteador import PRECO, intencoes

_CABECALHO = chr(0x2550) * 3
_SECAO = "COMO CONDUZIR A CONVERSA"

# Como a pessoa pede o valor, além do que o roteador já reconhece como PRECO.
_PEDE_VALOR = re.compile(
    r"\b(valor|valores|preco|precos|quanto (custa|fica|sai|e|vai ficar|ficaria)|"
    r"tabela|desconto|promocao|parcel|pagamento)\b"
)

# Como uma resposta anuncia valor.
_ANUNCIA = re.compile(
    r"r\$\s*\d|\d+\s*%\s*(de\s+)?desconto|\bdesconto de\b|\bvalor (total|final|da sessao)\b|"
    r"\btotal:?\s*r?\$?\s*\d"
)

BLOCO_DO_PROMPT = (
    "\n" + _CABECALHO + " PACIENTE RECORRENTE " + _CABECALHO + "\n"
    "Esta pessoa já é paciente: já fez sessão ou já tem sessão marcada. Ela sabe\n"
    "quanto custa.\n"
    "1. NÃO anuncie valor, total nem desconto ao confirmar áreas, data ou\n"
    "   agendamento. Resuma só áreas, data e horário.\n"
    "2. Se ELA perguntar o valor, responda normalmente, com calculate_discount.\n"
    "3. Continue chamando calculate_discount antes de book_appointment: o preço\n"
    "   gravado precisa estar certo, mesmo sem ser dito.\n"
)


def _plano(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    ).lower()


def e_recorrente(paciente: Optional[Dict]) -> bool:
    """Já fez sessão, ou já tem uma marcada. A primeira vez é a que vê o valor."""
    p = paciente or {}
    if not p.get("encontrado"):
        return False
    return int(p.get("sessoes_feitas") or 0) > 0 or bool(p.get("agendamento_futuro"))


def pediu_valor(turnos: Sequence[Dict]) -> bool:
    """Em algum turno DELA nesta conversa, a pessoa perguntou o valor?"""
    for turno in turnos or []:
        if turno.get("role") != "user":
            continue
        texto = turno.get("content") or ""
        if PRECO in intencoes(texto) or _PEDE_VALOR.search(_plano(texto)):
            return True
    return False


def anuncia_valor(texto: str) -> Optional[str]:
    """O trecho em que a resposta anuncia valor ou desconto, ou None."""
    m = _ANUNCIA.search(_plano(texto))
    return m.group(0) if m else None


def sem_valor_no_roteiro(prompt: str) -> str:
    """O roteiro de lead sem o 'mostre o valor' - para quem já é paciente.

    Troca, dentro da seção COMO CONDUZIR A CONVERSA, as linhas que mandam
    mostrar ou resumir o valor. Tolerante a template editado: sem a seção ou
    sem as linhas, o prompt volta como veio, e o bloco e a trava seguem valendo.
    """
    if not prompt:
        return prompt
    marca = re.search(
        re.escape(_CABECALHO) + r"\s*" + re.escape(_SECAO) + r"\s*" + re.escape(_CABECALHO),
        prompt,
    )
    if not marca:
        return prompt + BLOCO_DO_PROMPT
    fim = prompt.find(_CABECALHO, marca.end())
    if fim == -1:
        fim = len(prompt)
    secao = prompt[marca.start():fim]

    linhas = []
    for linha in secao.split("\n"):
        plana = _plano(linha)
        if "mostre o valor" in plana:
            linha = re.sub(
                r"(?i)e mostre o valor\.?",
                "(o preço gravado precisa estar certo). NÃO mostre o valor: "
                "esta pessoa já é paciente e só ouve valor se perguntar.",
                linha,
            )
        elif "valor total" in plana and "resuma" in plana:
            linha = re.sub(r"(?i),?\s*hor[aá]rio e valor total", " e horário. SEM valor", linha)
        linhas.append(linha)
    secao = "\n".join(linhas)
    return prompt[:marca.start()] + secao + prompt[fim:] + BLOCO_DO_PROMPT
