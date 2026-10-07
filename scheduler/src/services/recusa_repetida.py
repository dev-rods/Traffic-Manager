# -*- coding: utf-8 -*-
"""Uma trava que recusa a mesma coisa duas vezes não está protegendo, está presa.

As travas de área devolvem ao modelo um recado instrutivo: "pergunte a ela e
chame esta tool de novo". Isso está certo quando a pergunta pode mudar o
resultado - a paciente ainda não tinha nomeado a área, ela nomeia, a tool passa.

Está errado quando a resposta dela não muda nada. Em 16/09/2026 a área chamava-se
"Virilha Comp. + ânus" no cadastro e a trava comparava a string inteira: nenhuma
frase humana a liberaria. O modelo obedeceu ao recado cinco vezes, a paciente
respondeu certo cinco vezes, e a conversa só terminou porque o próprio modelo
desistiu e pediu uma atendente, uma hora e meia depois.

Regra, decidida pelo André em 16/09/2026:

  A MESMA recusa, sobre as MESMAS áreas, duas vezes na mesma conversa, é defeito
  nosso - não paciente indecisa. Para de perguntar e entrega a uma pessoa.

Duas, e não três: a primeira recusa é a trava trabalhando, e a pergunta que ela
gera é legítima. Se a resposta da paciente não destravou, perguntar de novo é
pedir que ela conserte um bug que está do nosso lado.

O contador vive na sessão porque o laço atravessa turnos: cada pergunta é uma
mensagem nova, e um contador de uma rodada só veria a primeira recusa.
"""
import logging

logger = logging.getLogger(__name__)

# Os erros das travas de área, e onde cada um lista o que barrou.
RECUSAS_DE_AREA = {
    "areas_nao_confirmadas": "areas_barradas",
    "areas_ambiguas": "areas_a_confirmar",
}

LIMITE = 2

CAMPO = "recusas_de_area"


def assinatura(resultado):
    """O que esta recusa barrou, como chave estável - ou None se não é recusa.

    A chave é o erro mais as áreas ordenadas: recusar "Virilha" e depois
    "Perianal" são tentativas diferentes do modelo procurando saída, e contá-las
    juntas entregaria a conversa cedo demais.
    """
    if not isinstance(resultado, dict):
        return None
    campo = RECUSAS_DE_AREA.get(resultado.get("error"))
    if not campo:
        return None
    return "{}:{}".format(
        resultado["error"], "|".join(sorted(str(a) for a in resultado.get(campo) or []))
    )


def registra(contador, resultado):
    """Soma esta recusa ao contador da conversa e diz quantas vezes já houve.

    Devolve 0 quando o resultado não é recusa de área. `contador` é o dicionário
    guardado na sessão, alterado no lugar.
    """
    chave = assinatura(resultado)
    if not chave:
        return 0
    vezes = int(contador.get(chave, 0)) + 1
    contador[chave] = vezes
    return vezes


def e_laco(contador, resultado, phone=""):
    """Esta recusa fecha um laço? Registra e decide, num lugar só.

    Quem chama só precisa saber se para ou segue - por isso o log de ERROR sai
    daqui e não do agente: laço de trava é defeito de catálogo ou de regra, e
    precisa aparecer no alarme sem depender de quem lembrou de logar.
    """
    vezes = registra(contador, resultado)
    if vezes < LIMITE:
        return False
    logger.error(
        f"[LacoDeRecusa] {phone}: a trava recusou {assinatura(resultado)} "
        f"{vezes}x nesta conversa. Perguntar de novo não vai destravar - "
        f"conferir o NOME dessas áreas no cadastro. Conversa entregue a uma pessoa."
    )
    return True
