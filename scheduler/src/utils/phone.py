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
