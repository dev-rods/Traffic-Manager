import re


# DDDs em uso no Brasil: 11 a 99, menos os que a Anatel nunca atribuiu.
_DDDS_INVALIDOS = {"20", "23", "25", "26", "29", "30", "36", "39", "40", "50",
                   "52", "56", "57", "58", "59", "60", "70", "72", "76", "78",
                   "80", "90"}


def _ddd_valido(ddd: str) -> bool:
    return len(ddd) == 2 and "11" <= ddd <= "99" and ddd not in _DDDS_INVALIDOS


def _parece_brasileiro(digits: str) -> bool:
    """Dígitos SEM o 55: DDD válido e celular (9 dígitos começando por 9) ou
    fixo (8 dígitos). É esta a régua que decide se ganha o `55`.

    Antes qualquer coisa que não começasse por 55 ganhava o prefixo, e o número
    holandês `31617223202` virou `5531617223202` no cadastro da Isadora
    (01/11/2026). `31` é DDD válido, mas `617223202` não é celular brasileiro
    (não começa por 9) nem fixo (tem 9 dígitos).
    """
    if len(digits) == 11:
        return _ddd_valido(digits[:2]) and digits[2] == "9"
    if len(digits) == 10:
        return _ddd_valido(digits[:2])
    return False


def _e_brasileiro_com_ddi(digits: str) -> bool:
    return digits.startswith("55") and len(digits) in (12, 13)


def normalize_phone(phone: str) -> str:
    """
    Normaliza telefone para o formato do z-api: só dígitos, com o código do
    país. Brasileiro vira `55DDDNNNNNNNNN`; os outros ficam como vieram.

    Aceita: +55 (11) 99999-0000, 5511999990000, 11999990000, 011999990000,
    +31 6 1722 3202 (-> 31617223202), 31617223202 (idem).

    Devolve UM valor só: é a chave de identidade de lead e paciente. Para
    comparar com tolerância ao nono dígito, ver `variantes_do_numero`.
    """
    bruto = (phone or "").strip()
    digits = re.sub(r"\D", "", bruto)

    # Com `+` a pessoa já escreveu o código do país: não se mexe.
    if bruto.startswith("+"):
        return digits

    if digits.startswith("0") and _parece_brasileiro(digits[1:]):
        digits = digits[1:]

    if _e_brasileiro_com_ddi(digits):
        return digits

    if _parece_brasileiro(digits):
        return "55" + digits

    return digits


def format_phone_display(phone: str) -> str:
    """
    Formata telefone para exibição: (DD) NNNNN-NNNN. Número de fora do Brasil
    sai como `+N...`.
    """
    digits = normalize_phone(phone)

    if _e_brasileiro_com_ddi(digits):
        local = digits[2:]
        if len(local) == 11:
            return f"({local[:2]}) {local[2:7]}-{local[7:]}"
        return f"({local[:2]}) {local[2:6]}-{local[6:]}"

    return f"+{digits}" if digits else phone


def is_valid_br_phone(phone: str) -> bool:
    """
    Valida se é um telefone brasileiro válido.
    Aceita celular (11 dígitos com DDD) ou fixo (10 dígitos com DDD).
    """
    digits = re.sub(r'\D', '', phone or "")

    if digits.startswith('55') and len(digits) in (12, 13):
        digits = digits[2:]
    if digits.startswith('0'):
        digits = digits[1:]

    return _parece_brasileiro(digits)


def is_valid_phone(phone: str) -> bool:
    """Brasileiro válido, ou internacional escrito com `+` e 8 a 15 dígitos
    (E.164). Sem o `+`, 10 ou 11 dígitos é lido como brasileiro: o site manda
    o `+` sempre que a pessoa o digita."""
    bruto = (phone or "").strip()
    digits = re.sub(r"\D", "", bruto)
    if bruto.startswith("+") and not digits.startswith("55"):
        return 8 <= len(digits) <= 15
    return is_valid_br_phone(bruto)


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

    Só mexe em celular brasileiro (8 ou 9 dígitos após o DDD) e só fora da
    faixa 11-28, onde a ausência do nono dígito é real. Em São Paulo, tirar o 9
    produziria um número de outra pessoa. Número de outro país tem uma forma só.
    """
    if not (phone or "").strip():
        return set()
    digits = normalize_phone(phone)
    if not digits:
        return set()
    if not _e_brasileiro_com_ddi(digits):
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


def formas_do_numero(phone: str) -> list:
    """`variantes_do_numero` como lista ordenada, para `phone = ANY(%s)` no SQL.

    Toda leitura de paciente por telefone deve usar isto. A criação do
    agendamento casava exato enquanto a cotação casava por variantes, e a
    Paula (DDD 35, gravada sem o 9) ganhou um segundo cadastro pelo site em
    21/10/2026.
    """
    return sorted(variantes_do_numero(phone))
