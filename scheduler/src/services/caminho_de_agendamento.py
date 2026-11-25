# -*- coding: utf-8 -*-
"""Link ou conversa: decidido ANTES do modelo, nunca na última tool.

Até 25/11/2026 a regra "quem já é paciente agenda pelo site primeiro" (PRD
046) vivia em dois lugares que não conversavam: um bloco de prompt que só as
skills de paciente recebiam, e uma recusa na tool de agendar que olhava
"tem cadastro". Uma paciente com cadastro e nenhuma sessão feita caiu na
skill de lead (sem o bloco), foi conduzida até "Confirmo?", e só então a
tool devolveu `primeiro_o_link`: cinco mensagens de trabalho dela trocadas
por "faça pelo site" (PRD 064, caso 2).

Agora a decisão é uma função, com três saídas, tomada no início do turno:

- CONVERSA: lead sem cadastro, clínica sem domínio, link do bot já enviado
  (7 dias), lembrete vivo (tem regras próprias) ou mensagem que não pede
  para agendar. Fluxo de sempre.
- LINK_PRIMEIRO: paciente com cadastro, primeiro pedido de agendar neste
  atendimento, link ainda não enviado PELO BOT. A resposta é só o link, sem
  oferta de marcar por aqui (decisões P1/P2 do André em 25/11). O link da
  campanha e do lembrete não contam, de propósito.
- CONVERSA_POR_INSISTENCIA: ela pediu de novo depois do link, ou disse que
  não consegue / prefere aqui. O bot agenda até o fim e nunca manda link no
  fechamento.

A tool não recusa mais nada: `ai_tools._recusa_sem_o_link` virou asserção
(log `[Caminho] VIOLAÇÃO`) para o eval medir.
"""
import logging
import re
import unicodedata
from typing import Dict, Optional

from src.services import autoatendimento, lembrete

logger = logging.getLogger(__name__)

CONVERSA = "conversa"
LINK_PRIMEIRO = "link_primeiro"
CONVERSA_POR_INSISTENCIA = "conversa_por_insistencia"

# Em LINK_PRIMEIRO o bot nao chama o modelo: a resposta e um texto fixo com o
# link (template LINK_PRIMEIRO, por clinica). No eval de 25/11 o modelo, com o
# bloco no prompt, ainda assim perguntou as areas ou pediu esclarecimento - o
# roteiro de areas do prompt do banco vence qualquer bloco colado no fim.
# Determinismo onde a regra e de negocio.
TEMPLATE_DO_LINK = "LINK_PRIMEIRO"
TEXTO_PADRAO_DO_LINK = (
    "Oi{{nome}}! O agendamento é pelo nosso site: {{link}} 😊\n"
    "Qualquer dúvida, é só me chamar por aqui."
)


def mensagem_do_link(template_service, clinic_id: str, link: str, nome: Optional[str]) -> str:
    """O texto fixo de LINK_PRIMEIRO. `nome` e o primeiro nome, ou vazio."""
    primeiro = (nome or "").strip().split(" ")[0] if nome else ""
    variaveis = {"link": link, "nome": f", {primeiro}" if primeiro else ""}
    try:
        texto = template_service.get_and_render(clinic_id, TEMPLATE_DO_LINK, variaveis) if template_service else ""
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Caminho] template {TEMPLATE_DO_LINK} falhou ({e}); texto padrao")
        texto = ""
    if not texto or not texto.strip() or not autoatendimento.link_citado(texto, link):
        # Template vazio, ausente ou sem o link (um template errado no banco
        # nao pode mandar a pessoa para lugar nenhum): texto padrao.
        texto = TEXTO_PADRAO_DO_LINK
        for k, v in variaveis.items():
            texto = texto.replace("{{" + k + "}}", v)
    return texto


_PEDE_AGENDAR = re.compile(
    r"\b(agendar|agenda|agendamento|marcar|marca|marcacao|horarios?|vagas?|datas?|"
    r"dia \d{1,2}|remarcar|reagendar|encaixe|disponibilidade|disponivel|proxima sessao|"
    r"fazer (a )?sessao|quero fazer|gostaria de fazer)\b"
)
_CANCELA = re.compile(r"\b(cancelar|cancela|desmarcar|desmarca|nao vou (poder )?ir)\b")
_INSISTE = re.compile(
    r"(nao consigo|nao consegui|nao abre|nao abriu|nao carrega|nao funciona|deu erro|"
    r"prefiro (por |resolver )?aqui|por aqui mesmo|pode marcar|marca (pra|para) mim|me marca|"
    r"faz (pra|para) mim|agenda (pra|para) mim|nao quero (pelo|o|no) (site|link)|"
    r"sem (o )?link|pelo (whatsapp|zap)|aqui pelo)"
)


def _plano(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(c) != "Mn"
    ).strip()


def pede_agendar(texto: str) -> bool:
    t = _plano(texto)
    return bool(_PEDE_AGENDAR.search(t)) and not _CANCELA.search(t)


def insiste_na_conversa(texto: str) -> bool:
    return bool(_INSISTE.search(_plano(texto)))


def decide(clinic: Optional[Dict], paciente: Optional[Dict], session: Optional[Dict],
           texto: str, link: Optional[str], agora: Optional[int] = None) -> str:
    """Grava o contador de pedidos na sessão quando LINK_PRIMEIRO."""
    paciente = paciente or {}
    session = session if session is not None else {}
    if not link or not paciente.get("encontrado"):
        return CONVERSA
    if lembrete.esta_vivo(session, agora):
        # O lembrete tem o próprio roteiro (cancelar aqui, remarcar por
        # ?meus=1, confirmar presença). Não misturar.
        return CONVERSA
    if autoatendimento.link_ja_foi(session, agora):
        return CONVERSA
    if insiste_na_conversa(texto):
        return CONVERSA_POR_INSISTENCIA
    if not pede_agendar(texto):
        return CONVERSA
    if autoatendimento.pedidos_de_agendar(session) >= 1:
        return CONVERSA_POR_INSISTENCIA
    autoatendimento.registra_pedido_de_agendar(session, agora)
    return LINK_PRIMEIRO


def bloco(caminho: str, link: Optional[str]) -> str:
    """O que vai para o system prompt. CONVERSA: nada (fluxo de sempre)."""
    if caminho == CONVERSA_POR_INSISTENCIA:
        return (
            "\n═══ AGENDAMENTO: NA CONVERSA ═══\n"
            "Ela já recebeu o link do site e pediu de novo por aqui (ou disse que\n"
            "não consegue pelo site). Conduza o agendamento até o fim nesta\n"
            "conversa, como sempre: áreas, data, horário, confirmação. Nunca mande\n"
            "o link de novo, nem no fechamento.\n"
        )
    return ""


def garante_o_link(texto: str, caminho: str, link: Optional[str]) -> str:
    """Em LINK_PRIMEIRO a mensagem precisa levar o link; se o modelo esqueceu,
    ele é anexado. Determinismo em volta do modelo."""
    if caminho != LINK_PRIMEIRO or not link or autoatendimento.link_citado(texto, link):
        return texto
    return f"{texto}\n\n{link}" if texto else f"O agendamento é por aqui: {link}"
