# -*- coding: utf-8 -*-
"""Normalizacao de CPF e data de nascimento do cadastro do paciente.

Os dois chegam de tres lugares - o bot pelo WhatsApp, o painel, e a importacao
de historico - e cada um escreve de um jeito. Guardar como veio faria a busca
por CPF depender de a pessoa ter digitado com ponto ou sem.

Nao validamos digito verificador de proposito. A clinica precisa do CPF para
nota e cadastro; recusar um CPF que a paciente ditou errado no WhatsApp
travaria o agendamento por um dado que a recepcao corrige depois. Formato
obviamente invalido e recusado; o resto entra.
"""
import re
from datetime import datetime

TAMANHO_CPF = 11


def normaliza_cpf(valor):
    """Só os dígitos, ou None. `''` também vira None: string vazia num campo
    opcional passaria em checagem de preenchimento e esconderia o vazio."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    if not digitos:
        return None
    return digitos if len(digitos) == TAMANHO_CPF else False  # False = invalido


def normaliza_data_nascimento(valor):
    """Aceita `YYYY-MM-DD` e `DD/MM/YYYY`, devolve ISO ou None.

    O painel manda ISO (input type=date) e o WhatsApp manda o que a pessoa
    escreveu. `False` sinaliza formato que nao da para interpretar - diferente
    de None, que e "nao informado".
    """
    texto = str(valor or "").strip()
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d.%m.%Y"):
        try:
            d = datetime.strptime(texto, formato).date()
        except ValueError:
            continue
        # Data futura ou de mais de 120 anos atras e erro de digitacao, nao
        # nascimento. Deixar passar polui o cadastro em silencio.
        hoje = datetime.now().date()
        if d > hoje or (hoje.year - d.year) > 120:
            return False
        return d.isoformat()
    return False
