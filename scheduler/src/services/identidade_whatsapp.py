"""De quem é a conversa que o webhook acabou de receber.

O z-api identifica o outro lado de três jeitos diferentes no mesmo campo
`phone`, e a diferença decide se a mensagem vira atendimento ou é descartada:

    cliente escreve       phone=5511970522647          fromMe=false
    bot responde (API)    phone=5511970522647          fromMe=true  status=SENT
    atendente no celular  phone=176209673617532@lid    fromMe=true  status=RECEIVED
    grupo                 phone=120363...-group
    self-chat             phone == connectedPhone

A terceira linha é a que nos custou caro: quando a mensagem sai do aparelho, o
z-api põe o LID (identidade interna do WhatsApp) no lugar do número. O guard que
barra grupos e broadcasts levava essa mensagem junto, e por isso o bot nunca
soube que havia gente atendendo - respondeu por cima cinco vezes em 01/09/2026.

O LID é resolvido pelo vínculo que as próprias mensagens da conversa fornecem:
elas trazem `chatLid` ao lado do número real.
"""
from src.utils.phone import normalize_phone


def chat_lid(body):
    """O identificador da conversa, quando o payload traz um."""
    lid = (body.get("chatLid") or "").strip()
    return lid or None


def telefone_da_conversa(body, telefone_do_lid=None):
    """O telefone real do outro lado, ou None se a mensagem deve ser ignorada.

    `telefone_do_lid` é o número já vinculado ao chatLid desta conversa, quando
    conhecido. Sem ele, uma mensagem que chega identificada só por LID continua
    sendo descartada - é o comportamento antigo, e é o lado seguro.
    """
    phone = (body.get("phone") or "").strip()

    if body.get("isGroup") or phone.endswith("-group") or phone.endswith("-broadcast"):
        return None

    if "@" in phone:
        # Identidade não-PSTN. Só seguimos se soubermos de quem é a conversa.
        return telefone_do_lid

    conectado = (body.get("connectedPhone") or "").strip()
    if conectado and normalize_phone(phone) == normalize_phone(conectado):
        return None  # o número falando com ele mesmo

    return phone or None


def deve_vincular_lid(body):
    """Esta mensagem ensina a quem pertence um LID?

    Só as que trazem número real e chatLid ao mesmo tempo - as demais não
    acrescentam nada ao vínculo.
    """
    phone = (body.get("phone") or "").strip()
    return bool(chat_lid(body)) and "@" not in phone and bool(phone)
