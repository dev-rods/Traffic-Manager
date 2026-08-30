"""Retomada de conversa quando alguém ativa o bot no painel.

Ativar o bot só liberava a resposta automática para a próxima mensagem. Quem já
tinha escrito e ficado sem resposta continuava sem resposta: o bot esperava a
pessoa insistir. Aqui ele olha como a conversa parou e, se a última fala foi da
pessoa, responde o que ficou pendente.

O contrário também importa: se a conversa terminou com o bot ou o atendente
falando, ativar não pode gerar mensagem do nada. Por isso a decisão é do guard
determinístico, e não do modelo - chamar o LLM para ele concluir que não há nada
a dizer custa caro e ainda arrisca uma mensagem indevida.
"""
import logging

logger = logging.getLogger(__name__)

# Mensagem sintética que explica ao agente por que ele está falando sem ninguém
# ter escrito agora. O AI_SYSTEM_PROMPT tem uma seção ensinando a reconhecê-la.
GATILHO_RETOMADA = "__RETOMAR_CONVERSA__"

# Janela lida do MessageEvents. O guard só precisa da última fala, mas o agente
# recebe a janela inteira para responder sem repetir o que já foi dito.
EVENTOS_PARA_CONTEXTO = 20


def ha_pergunta_em_aberto(eventos):
    """A última fala da conversa é da pessoa?

    Se for, ninguém respondeu - é o caso de retomar. Eventos sem texto (webhooks
    de status de entrega) não são fala e não contam.

    Espera os eventos em ordem cronológica, do mais antigo para o mais recente.
    """
    for evento in reversed(eventos or []):
        if not (evento.get("content") or "").strip():
            continue
        return evento.get("direction") == "INBOUND"
    return False


def responder_se_ficou_em_aberto(clinic_id, phone):
    """Responde a pergunta pendente da conversa. Devolve True se falou.

    Roda fora do request do painel: o agente leva de 3 a 15 segundos e o API
    Gateway corta em 29, o que mostraria erro na tela depois de a mensagem já
    ter saído.
    """
    from src.providers.whatsapp_provider import get_provider
    from src.services.agent_runner import falar
    from src.services.db.postgres import PostgresService
    from src.services.message_tracker import MessageTracker

    tracker = MessageTracker()
    eventos = tracker.get_conversation_messages(clinic_id, phone, limit=EVENTOS_PARA_CONTEXTO)

    if not ha_pergunta_em_aberto(eventos):
        logger.info(f"[Retomada] Nada pendente com {phone}: bot ativado sem responder")
        return False

    db = PostgresService()
    rows = db.execute_query(
        "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
        (clinic_id,),
    )
    if not rows:
        logger.error(f"[Retomada] Clínica {clinic_id} não encontrada")
        return False

    enviou, quantas = falar(
        clinic_id, phone, GATILHO_RETOMADA,
        db=db, provider=get_provider(rows[0]), tracker=tracker,
        metadata={"kind": "resume"},
    )

    if enviou:
        logger.info(f"[Retomada] Respondi o que estava em aberto com {phone} ({quantas} msg)")
    else:
        logger.error(f"[Retomada] Falhei ao responder {phone}")
    return enviou
