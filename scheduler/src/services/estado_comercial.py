# -*- coding: utf-8 -*-
"""Estado comercial da pessoa: derivado de `appointments`, nunca gravado.

PRD 020 §3.1. Um campo `commercial_status` seria cache de algo que o banco já
sabe, e cache de estado comercial envelhece em silêncio: a pessoa faz a sessão
e o campo não muda até alguém rodar um job. Aqui o estado é calculado a cada
mensagem, a partir do que `identificacao_de_paciente.identificar` já traz na
sua única consulta (sessões feitas, última sessão, agendamento futuro). Não
há segunda consulta.

    NEW_LEAD         sem cadastro ou sem agendamento algum
    FIRST_BOOKING    tem agendamento futuro, zero sessões feitas
    ACTIVE_CUSTOMER  >= 1 sessão feita e tem agendamento futuro
    NO_NEXT_BOOKING  >= 1 sessão feita, sem agendamento futuro

"Sessão feita" = CONFIRMED com data passada (a régua dos PRDs 016/017); NO_SHOW
e CANCELLED não contam. Havia uma "janela de retorno" dividindo o último
estado em dois; o André a retirou em 09/10/2026: a distinção não mudava a
resposta, e quem está no ciclo é chamada pela campanha.

O estado muda o que o bot DEIXA de fazer (cadastro, valor, apresentação da
clínica), nunca o que ele assume pela pessoa: as áreas são sempre perguntadas
e confirmadas, em todo estado.

O bloco QUEM É entra no turno da pessoa, não no system prompt (o prefixo
cacheado não pode mudar por mensagem), e é retirado do histórico antes de
gravar: é cache de requisição, não estado.
"""
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

NEW_LEAD = "NEW_LEAD"
FIRST_BOOKING = "FIRST_BOOKING"
ACTIVE_CUSTOMER = "ACTIVE_CUSTOMER"
NO_NEXT_BOOKING = "NO_NEXT_BOOKING"

ESTADOS = (NEW_LEAD, FIRST_BOOKING, ACTIVE_CUSTOMER, NO_NEXT_BOOKING)

CABECALHO = "═══ QUEM É ═══"

LEGIVEL = {
    NEW_LEAD: "ainda não é paciente (nenhuma sessão feita, nada marcado)",
    FIRST_BOOKING: "vai fazer a primeira sessão (tem horário marcado, nenhuma feita)",
    ACTIVE_CUSTOMER: "paciente (já fez sessão e tem a próxima marcada)",
    NO_NEXT_BOOKING: "paciente (já fez sessão, sem próxima marcada)",
}


def deriva(sessoes_feitas: int, tem_futuro: bool) -> str:
    """Pura. A tabela do PRD §3.1, nesta ordem."""
    feitas = int(sessoes_feitas or 0)
    if feitas <= 0:
        return FIRST_BOOKING if tem_futuro else NEW_LEAD
    return ACTIVE_CUSTOMER if tem_futuro else NO_NEXT_BOOKING


def do_paciente(paciente: Optional[Dict]) -> str:
    """O estado a partir do dict de `identificar`. Sem cadastro, NEW_LEAD."""
    p = paciente or {}
    if not p.get("encontrado"):
        return NEW_LEAD
    return deriva(p.get("sessoes_feitas") or 0, bool(p.get("agendamento_futuro")))


def bloco(paciente: Optional[Dict], estado: str) -> str:
    """O bloco QUEM É, para o turno da pessoa. Diz o que o banco sabe e o
    que isso muda na conduta; o modelo não deduz o estado, lê."""
    p = paciente or {}
    linhas = [CABECALHO, f"Estado: {estado} - {LEGIVEL.get(estado, estado)}."]
    if p.get("encontrado"):
        if p.get("nome"):
            linhas.append(f"Nome no cadastro: {p['nome']}.")
        linhas.append(f"Sessões feitas: {int(p.get('sessoes_feitas') or 0)}.")
        if p.get("ultima_sessao"):
            linhas.append(f"Última sessão: {str(p['ultima_sessao'])[:10]}.")
        futuro = p.get("agendamento_futuro")
        if isinstance(futuro, dict) and futuro.get("data"):
            linhas.append(f"Próximo horário marcado: {futuro.get('data')} às {futuro.get('hora', '?')}.")
        linhas.append(
            "Cadastro completo: sim. Não peça nome, nascimento, CPF nem e-mail."
            if p.get("cadastro_completo") else
            "Cadastro incompleto: o que faltar é pedido só na hora de agendar."
        )
    elif p.get("ambiguo"):
        linhas.append("Este telefone está em mais de um cadastro; pergunte o nome completo antes de agendar.")
    else:
        linhas.append("Sem cadastro neste telefone.")
    if estado in (ACTIVE_CUSTOMER, NO_NEXT_BOOKING):
        linhas.append("Já conhece a clínica: não apresente a clínica de novo nem repita o valor sem ela perguntar.")
        linhas.append("As áreas desta sessão você pergunta e confirma com ela, como sempre: o que ela fez antes não diz o que quer agora.")
    linhas.append("Vale só para esta mensagem; a cada mensagem este bloco é refeito.")
    return "\n".join(linhas)


_BLOCO = re.compile(re.escape(CABECALHO) + r"\n.*?(?=\n═══ |\Z)", re.DOTALL)


def sem_bloco(history: List[Dict]) -> List[Dict]:
    """O histórico sem os blocos QUEM É, para gravar. O estado de ontem no
    histórico de hoje é exatamente o cache envelhecido que o PRD proíbe."""
    limpo = []
    for turno in history or []:
        conteudo = turno.get("content")
        if turno.get("role") == "user" and isinstance(conteudo, str) and CABECALHO in conteudo:
            novo = _BLOCO.sub("", conteudo).replace("\n\n\n", "\n\n").lstrip("\n")
            turno = {**turno, "content": novo}
        limpo.append(turno)
    return limpo
