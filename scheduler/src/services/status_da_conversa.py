# -*- coding: utf-8 -*-
"""Em que pé está a conversa de cada lead: quem atende e se ela existe.

Duas fontes, de propósito, porque elas respondem coisas diferentes:

  ConversationSessions (DynamoDB)  quem está conduzindo agora - bot ou gente
  whatsapp_chats (espelho z-api)   existe conversa no WhatsApp, e quando foi

Nada disso é denormalizado numa coluna do lead. Esta conversa toda começou com
`conversation_started_at` mostrando "sem contato" para quem tinha conversa: um
campo copiado que divergiu da realidade e ninguém percebeu. Ler da fonte na hora
da listagem custa um batch_get por página e não pode divergir.
"""
import logging
import time

from src.utils.phone import variantes_do_numero

logger = logging.getLogger(__name__)

# O que a tela mostra. Ordem de precedência: quem está atendendo agora importa
# mais do que o histórico.
HUMANO = "HUMANO"        # atendente assumiu, o bot está calado
AGUARDA_HUMANO = "AGUARDA_HUMANO"  # o bot pediu ajuda e ninguém assumiu ainda
BOT = "BOT"              # o bot está conduzindo
SEM_CONVERSA = "SEM_CONVERSA"

ESTADOS_DE_ESPERA = {"HUMAN_HANDOFF"}
ESTADOS_DE_ATENDENTE = {"HUMAN_ATTENDANT_ACTIVE"}

MAX_POR_LOTE = 100  # limite do BatchGetItem do DynamoDB


def status_de_uma_sessao(sessao, agora=None):
    """Traduz a sessão crua no rótulo da tela."""
    if not sessao:
        return SEM_CONVERSA

    agora = agora or int(time.time())
    estado = str(sessao.get("state") or "")

    # `attendant_active_until` é a marca que o webhook grava quando a atendente
    # responde pelo celular. Vence sozinha em 24h, então o passado não pode
    # deixar a conversa marcada como humana para sempre.
    ate = sessao.get("attendant_active_until")
    try:
        atendente_ativo = int(ate or 0) > agora
    except (TypeError, ValueError):
        atendente_ativo = False

    if atendente_ativo or estado in ESTADOS_DE_ATENDENTE:
        return HUMANO
    if estado in ESTADOS_DE_ESPERA:
        return AGUARDA_HUMANO
    return BOT


def sessoes_por_telefone(tabela, clinic_id, telefones):
    """Uma leitura em lote para a página inteira, não uma por linha."""
    encontradas = {}
    unicos = [t for t in dict.fromkeys(telefones) if t]
    if not tabela or not unicos:
        return encontradas

    for inicio in range(0, len(unicos), MAX_POR_LOTE):
        fatia = unicos[inicio:inicio + MAX_POR_LOTE]
        chaves = [{"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{t}"} for t in fatia]
        try:
            resposta = tabela.meta.client.batch_get_item(
                RequestItems={tabela.name: {"Keys": chaves}}
            )
            for item in resposta.get("Responses", {}).get(tabela.name, []):
                telefone = str(item.get("sk", "")).replace("PHONE#", "")
                encontradas[telefone] = item.get("session") or {}
        except Exception as e:
            # Falha aqui não pode derrubar a listagem: o painel mostra os leads
            # sem o status, que é o comportamento de antes desta feature.
            logger.error(f"[StatusConversa] batch_get falhou para {clinic_id}: {e}")
    return encontradas


def conversas_da_clinica(db, clinic_id):
    """O espelho do z-api indexado por TODA variante do telefone.

    Indexar pelas variantes resolve o nono dígito na leitura: o z-api guarda
    `554797053940` e o lead tem `5547997053940`.
    """
    por_variante = {}
    linhas = db.execute_query(
        "SELECT phone, name, last_message_at, unread_count "
        "FROM scheduler.whatsapp_chats WHERE clinic_id = %s",
        (clinic_id,),
    )
    for linha in linhas:
        for variante in variantes_do_numero(linha["phone"]):
            por_variante[variante] = linha
    return por_variante


def enriquece(leads, sessoes, conversas):
    """Devolve os leads com `conversation_status` e `has_whatsapp_chat`.

    Não sobrescreve `conversation_started_at`: "respondeu" continua sendo a
    pessoa tendo escrito para nós. A lista de chats do z-api não diz quem falou,
    então usá-la para "respondeu" inflaria a taxa de conversão com conversas em
    que só a clínica falou.
    """
    enriquecidos = []
    for lead in leads:
        lead = dict(lead)
        telefone = lead.get("phone") or ""

        chat = None
        for variante in variantes_do_numero(telefone):
            chat = conversas.get(variante)
            if chat:
                break

        lead["has_whatsapp_chat"] = bool(chat)
        lead["whatsapp_last_message_at"] = chat["last_message_at"] if chat else None

        sessao = sessoes.get(telefone)
        if not sessao:
            for variante in variantes_do_numero(telefone):
                sessao = sessoes.get(variante)
                if sessao:
                    break

        status = status_de_uma_sessao(sessao)
        # Sem sessão mas com conversa no WhatsApp é atendimento humano puro: a
        # atendente respondeu pelo celular e o webhook nunca viu. Chamar isso de
        # "sem conversa" é o defeito que trouxe esta feature.
        if status == SEM_CONVERSA and chat:
            status = HUMANO
        lead["conversation_status"] = status
        enriquecidos.append(lead)
    return enriquecidos
