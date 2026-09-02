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
"""


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
