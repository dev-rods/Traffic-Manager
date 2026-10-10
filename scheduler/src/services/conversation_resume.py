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


# Folga entre o instante da entrega a pessoa e a mensagem do bot que a
# anunciou ("ja chamei uma especialista"): sao gravados no mesmo turno, com
# segundos de diferenca, em qualquer ordem.
_FOLGA_DO_AVISO = 120


def _foi_de_pessoa_da_clinica(evento):
    """OUTBOUND digitado no celular (metadata.autor = HUMANO desde a fase 3;
    antes, SENT sem providerMessageId). Ver conversation_agent."""
    if evento.get("direction") != "OUTBOUND":
        return False
    if (evento.get("metadata") or {}).get("autor") == "HUMANO":
        return True
    return evento.get("status") == "SENT" and not evento.get("providerMessageId")


def ha_pergunta_em_aberto(eventos, entregue_em=None):
    """A última fala HUMANA da conversa é da pessoa?

    Se for, ninguém respondeu - é o caso de retomar. Eventos sem texto (webhooks
    de status de entrega) não são fala e não contam.

    `entregue_em`: o instante em que o bot entregou a conversa a uma pessoa
    (bloco `atendimento`). A mensagem do bot gravada junto da entrega ("já
    chamei uma especialista...") é aviso, não resposta: a pergunta da pessoa
    continua em aberto atrás dela. Sem `entregue_em` vale a regra antiga (a
    última fala com texto decide).

    Espera os eventos em ordem cronológica, do mais antigo para o mais recente.
    """
    from src.services.retomada import _instante

    for evento in reversed(eventos or []):
        if not (evento.get("content") or "").strip():
            continue
        if evento.get("direction") == "INBOUND":
            return True
        if _foi_de_pessoa_da_clinica(evento):
            return False
        if entregue_em:
            quando = _instante(evento)
            if quando is not None and quando >= int(entregue_em) - _FOLGA_DO_AVISO:
                continue  # o aviso de handoff do bot; a pergunta esta atras dele
        return False
    return False


def responder_se_ficou_em_aberto(clinic_id, phone, entregue_em=None):
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

    if not ha_pergunta_em_aberto(eventos, entregue_em):
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

    # Ninguem escreveu agora: e o bot falando primeiro, entao passa pela
    # pergunta proativa. Antes nao conferia nem `bot_paused` nem politica.
    from src.services import atendimento
    from src.services.session_store import carrega_sessao

    sessao = carrega_sessao(clinic_id, phone)
    if not atendimento.pode_iniciar(rows[0], sessao, phone):
        logger.info(
            f"[Retomada] {phone}: porta fechada "
            f"(handler={atendimento.estado(sessao)}), nao respondo"
        )
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
