# -*- coding: utf-8 -*-
"""Quando o bot pode abrir conversa com um lead, e por que não pode.

Fonte única: o painel desenha o botão com o que sai daqui e o endpoint revalida
com a MESMA função no clique. Deixar o frontend decidir criaria a regra em dois
lugares, e a divergência entre eles é silenciosa - foi assim que um lead com
conversa desenvolvida no WhatsApp apareceu como "sem contato".

O disparo automático no cadastro foi removido em 05/09/2026. A razão não foi
técnica: não existe como saber por API que a atendente já falou com alguém que
nunca respondeu. O WhatsApp só expõe o número de quem está na agenda do
aparelho; o resto chega como LID sem telefone, e o z-api também não resolve
(testado: 4 de 27 LIDs, e os 4 já eram conhecidos). Sem esse dado, todo disparo
automático corre o risco de escrever para quem já está sendo atendido.

Quem sabe é a atendente. Por isso a decisão voltou para ela, com dois botões, e
o "Já iniciada" existe justamente para registrar o que a API não enxerga.
"""
from src.services.bot_policy import should_bot_reply

# Motivos, na ordem em que são conferidos. O painel mostra o texto ao lado do
# botão desabilitado: "indisponível" sem explicação vira chamado de suporte.
MOTIVOS = {
    "ORIGEM": "Só leads da landing page podem ser iniciados pelo bot.",
    "JA_RESPONDEU": "A pessoa já escreveu para a clínica.",
    "JA_CONTATADA": "Alguém já iniciou esta conversa.",
    "TEM_CONVERSA": "Já existe conversa com este número no WhatsApp.",
    "POLITICA": "O bot não está ativo para este número nesta clínica.",
    "SEM_TELEFONE": "Lead sem telefone.",
}

ORIGENS_PERMITIDAS = {"landing-page"}


def por_que_nao_pode(lead, clinic):
    """A chave do motivo, ou None quando o bot pode iniciar.

    A ordem importa para a mensagem: o motivo mais específico primeiro, senão
    todo lead de WhatsApp diria "política não permite", que é verdade e não
    ajuda.
    """
    lead = lead or {}

    # Clínica ausente recusa, e isto não é detalhe. `should_bot_reply` trata
    # política ausente como ALL de propósito - uma clínica lida antes da
    # migration não pode ficar sem RESPONDER. Mas INICIAR conversa é outra
    # coisa: a mensagem sai para uma pessoa real e não tem desfazer, então na
    # falta de contexto a resposta é não.
    if not clinic:
        return "POLITICA"

    if not lead.get("phone"):
        return "SEM_TELEFONE"

    if lead.get("source") not in ORIGENS_PERMITIDAS:
        return "ORIGEM"

    if lead.get("conversation_started_at"):
        return "JA_RESPONDEU"

    # Cobre os dois botões: o bot já enviou, ou a atendente marcou "Já iniciada".
    if lead.get("first_contact_at") or lead.get("first_contact_status"):
        return "JA_CONTATADA"

    # O espelho do z-api é confiável quando diz que HÁ conversa e cego quando
    # diz que não - ele não enxerga contato que nunca foi entregue. Na dúvida
    # não oferecemos o bot; o furo que sobra é o que o botão "Já iniciada" tapa.
    if lead.get("has_whatsapp_chat"):
        return "TEM_CONVERSA"

    # A política vale para o botão: em piloto, o bot só fala com quem está na
    # lista. Sem isto o clique enfileiraria um item que nunca sai, e a atendente
    # ficaria olhando um "na fila" que não anda.
    #
    # `bot_enabled=True` porque a origem landing-page ja foi conferida acima, e
    # e exatamente o que a politica LEADS_ONLY exige da conversa.
    if clinic.get("bot_paused") or not should_bot_reply(
        clinic, {"bot_enabled": True}, lead["phone"]
    ):
        return "POLITICA"

    return None


def pode_iniciar(lead, clinic):
    return por_que_nao_pode(lead, clinic) is None


def motivo_legivel(chave):
    return MOTIVOS.get(chave or "", "")


# De onde veio a certeza de que a conversa já começou. A ordem é de evidência
# mais forte para mais fraca, e todas menos HUMANO são apuradas por nós.
ORIGEM_RESPONDEU = "RESPONDEU"   # a pessoa escreveu para a clínica
ORIGEM_BOT = "BOT"               # o bot enviou (ou está na fila para enviar)
ORIGEM_HUMANO = "HUMANO"         # a atendente marcou à mão
ORIGEM_WHATSAPP = "WHATSAPP"     # existe conversa no espelho do z-api

ORIGENS_LEGIVEIS = {
    ORIGEM_RESPONDEU: "A pessoa já escreveu para a clínica.",
    ORIGEM_BOT: "O bot já iniciou esta conversa.",
    ORIGEM_HUMANO: "Marcado por uma atendente.",
    ORIGEM_WHATSAPP: "Já existe conversa com este número no WhatsApp.",
}


def origem_do_contato(lead):
    """Quem já iniciou a conversa, ou None se ninguém iniciou que a gente saiba.

    A tela mostrava "Já iniciada" desmarcado para lead que já tinha conversa no
    WhatsApp, e pedia um clique para registrar o que o sistema já sabia. Isso é
    trabalho manual para confirmar dado apurado - e pior, treina a atendente a
    clicar sem ler, justamente no botão cuja única razão de existir é o caso em
    que ela sabe algo que nós não sabemos.

    A intervenção humana fica só onde somos cegos: contato que a atendente fez e
    que nunca foi entregue não aparece em lugar nenhum (o WhatsApp só expõe o
    número de quem está salvo na agenda), e é exatamente para isso que o botão
    existe.
    """
    lead = lead or {}

    if lead.get("conversation_started_at"):
        return ORIGEM_RESPONDEU

    canal = lead.get("first_contact_channel")
    if canal == ORIGEM_HUMANO:
        return ORIGEM_HUMANO
    # Canal ausente com status preenchido é registro do disparo automático
    # antigo, que não gravava canal. Foi envio do bot.
    if canal == ORIGEM_BOT or lead.get("first_contact_status") or lead.get("first_contact_at"):
        return ORIGEM_BOT

    if lead.get("has_whatsapp_chat"):
        return ORIGEM_WHATSAPP

    return None


def origem_legivel(origem):
    return ORIGENS_LEGIVEIS.get(origem or "", "")


def pode_desmarcar(lead):
    """Dá para desfazer o "Já iniciada"?

    Só quando quem marcou foi uma pessoa. Se o BOT enviou, a mensagem está no
    WhatsApp de alguém e desmarcar seria mentira - pior, reabriria o botão para
    mandar uma segunda.
    """
    return (lead or {}).get("first_contact_channel") == "HUMANO"
