"""Quem enviou a mensagem que saiu do número da clínica.

O z-api entrega toda mensagem com fromMe=true e status=SENT, venha ela do bot
ou do celular da atendente. Distinguir pelo status não funciona - foi o que
deixou o bot responder por cima de um atendimento humano em 01/09/2026.

O identificador é factual: ao enviar, o bot guarda no MessageEvents o id que o
provider devolveu. Id conhecido é eco do próprio bot; id desconhecido foi
digitado no celular.

Confirmado nos dados de produção: das 2.246 mensagens OUTBOUND com status SENT
da Essência, 2.194 têm providerMessageId (todas do bot) e 52 não têm - e essas
52 são justamente mensagens humanas de abril e maio ("Gi, pode ser às 08:15?").
A ausência do id já é, por si só, o sinal de que alguém digitou.

Três autores possíveis para o que sai do número da clínica (PRD 034):
BOT (o agente), HUMANO (celular da atendente) e SISTEMA (OTP e confirmação do
site, link de cobrança do check-in - `metadata.origem`). A regra mora aqui e
só aqui: já houve três cópias dela (agente, retomada, painel), e cópia diverge
em silêncio.
"""

HUMANO = "HUMANO"
SISTEMA = "SISTEMA"
BOT = "BOT"


def foi_enviada_pelo_bot(eventos, provider_message_id):
    """O id veio de uma mensagem que o próprio bot enviou?

    Sem id não dá para afirmar que foi o bot, e a resposta é False: calar o bot
    à toa é um erro barato perto de deixá-lo atropelar um atendimento humano.
    """
    if not provider_message_id:
        return False
    return any(
        (evento or {}).get("providerMessageId") == provider_message_id
        for evento in (eventos or [])
    )


def _metadata(evento):
    meta = (evento or {}).get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def origem_do_sistema(evento):
    """`metadata.origem` de um OUTBOUND que o sistema mandou (site, check-in),
    ou None. Ver `envio_do_sistema.ORIGENS`."""
    if (evento or {}).get("direction") != "OUTBOUND":
        return None
    return _metadata(evento).get("origem") or None


def foi_de_pessoa_da_clinica(evento):
    """OUTBOUND digitado no celular, não enviado pelo bot nem pelo sistema.

    O webhook marca `metadata.autor = HUMANO` desde a fase 3 do PRD 020. Antes
    disso o sinal era a ausência de providerMessageId num SENT: o bot sempre
    guarda o id que o provider devolve. Envio do sistema com origem nunca é
    pessoa, mesmo que o id tenha faltado.
    """
    evento = evento or {}
    if evento.get("direction") != "OUTBOUND":
        return False
    if origem_do_sistema(evento):
        return False
    if _metadata(evento).get("autor") == HUMANO:
        return True
    return evento.get("status") == "SENT" and not evento.get("providerMessageId")


def autor_da_mensagem(evento):
    """HUMANO, SISTEMA ou BOT para um OUTBOUND; None para o resto."""
    if (evento or {}).get("direction") != "OUTBOUND":
        return None
    if origem_do_sistema(evento):
        return SISTEMA
    if foi_de_pessoa_da_clinica(evento):
        return HUMANO
    return BOT
