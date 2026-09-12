import re


def normalize_phone(phone: str) -> str:
    """
    Normaliza telefone para formato z-api: 55DDDNNNNNNNNN (apenas dígitos).
    Aceita formatos: +55 (11) 99999-0000, 5511999990000, 11999990000, etc.
    """
    digits = re.sub(r'\D', '', phone)

    # Se começa com 0, remover (ex: 011999990000)
    if digits.startswith('0'):
        digits = digits[1:]

    # Se não começa com 55, adicionar código do país
    if not digits.startswith('55'):
        digits = '55' + digits

    return digits


def format_phone_display(phone: str) -> str:
    """
    Formata telefone para exibição: (DD) NNNNN-NNNN
    Espera formato normalizado: 55DDDNNNNNNNNN
    """
    digits = normalize_phone(phone)

    # Remover código do país (55)
    if digits.startswith('55'):
        digits = digits[2:]

    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    elif len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    else:
        return phone


def is_valid_br_phone(phone: str) -> bool:
    """
    Valida se é um telefone brasileiro válido.
    Aceita celular (11 dígitos com DDD) ou fixo (10 dígitos com DDD).
    """
    digits = re.sub(r'\D', '', phone)

    if digits.startswith('55'):
        digits = digits[2:]
    if digits.startswith('0'):
        digits = digits[1:]

    # Celular: 2 dígitos DDD + 9 dígitos (começando com 9)
    if len(digits) == 11 and digits[2] == '9':
        return True

    # Fixo: 2 dígitos DDD + 8 dígitos
    if len(digits) == 10:
        return True

    return False


# DDDs onde o nono digito e obrigatorio desde sempre: Sao Paulo (11-19) e Rio
# mais Espirito Santo (21-28). Fora dessa faixa a portabilidade foi mais tarde e
# o WhatsApp guarda muito numero antigo sem o 9.
DDDS_COM_NONO_DIGITO = {str(d) for d in range(11, 29)}


def variantes_do_numero(phone: str) -> set:
    """O mesmo celular escrito com e sem o nono dígito.

    O WhatsApp guarda `554797053940` e o formulário da landing page gravou
    `5547997053940` - 12 dígitos contra 13, mesma pessoa. Casando exato, o lead
    nunca encontra a própria conversa: em 05/09/2026 a "Julia Dalçóquio"
    aparecia como sem contato tendo conversa desenvolvida no WhatsApp.

    Não é normalização: `normalize_phone` tem que continuar devolvendo UM valor,
    senão a chave de identidade do lead vira ambígua. Isto é para COMPARAR.

    Só mexe em celular (8 ou 9 dígitos após o DDD) e só fora da faixa 11-28,
    onde a ausência do nono dígito é real. Em São Paulo, tirar o 9 produziria um
    número de outra pessoa.
    """
    if not (phone or "").strip():
        return set()
    digits = normalize_phone(phone)
    # `normalize_phone("")` devolve "55": entrada vazia nao vira pais.
    if digits in ("", "55"):
        return set()
    if len(digits) < 12:
        return {digits}

    ddd, resto = digits[2:4], digits[4:]
    variantes = {digits}
    if ddd in DDDS_COM_NONO_DIGITO:
        return variantes

    if len(resto) == 9 and resto.startswith("9"):
        variantes.add("55" + ddd + resto[1:])
    elif len(resto) == 8:
        variantes.add("55" + ddd + "9" + resto)

    return variantes


def mesmo_numero(a: str, b: str) -> bool:
    """Os dois telefones são a mesma pessoa, tolerando o nono dígito."""
    return bool(variantes_do_numero(a) & variantes_do_numero(b))
