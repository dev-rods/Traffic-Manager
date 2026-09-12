# -*- coding: utf-8 -*-
"""O prompt de uma conversa de campanha nao carrega o roteiro de lead.

Em 11/09/2026 a Camila, paciente cadastrada, recebeu isto do bot:

    "Perfeito! Para finalizar o cadastro, me envia:
     Nome completo:
     Data de nascimento:
     CPF:
     E-mail:"

E o valor da sessao, que ela nao tinha perguntado.

O bloco de campanha ESTAVA no prompt, com "NUNCA peca nome, CPF" e "NAO anuncie
preco" - conferido depois, reconstruindo o prompt com a sessao real de producao.
O modelo passou por cima. E passou porque o prompt base traz um roteiro
numerado, longo e com TEXTO PRONTO, e a mensagem enviada era palavra por palavra
o passo 6 desse roteiro.

Entre um roteiro especifico e uma negacao curta colada no fim, o modelo segue o
roteiro. A licao que se repetiu o dia inteiro: instrucao e pedido, nao garantia.

Entao aqui o roteiro de lead e RETIRADO, nao contradito. O que nao esta no
prompt nao pode ser reproduzido.

As demais secoes ficam - tom de escrita, proveniencia dos fatos, FAQ, objecao,
endereco, transferencia. Sao as mesmas regras nos dois fluxos, e duplica-las
criaria duas fontes para a mesma verdade.
"""
import re
import unicodedata

# As secoes do template sao delimitadas por cabecalhos de caixa dupla.
_CABECALHO = chr(0x2550) * 3

# Roteiro de lead: comeca em boas-vindas, mostra preco no passo 3 e pede
# cadastro no passo 6. Nada disso vale para quem ja e paciente.
SECAO_DO_FLUXO = "COMO CONDUZIR A CONVERSA"
# Gatilho __INICIAR_CONVERSA__, exclusivo do lead da landing page.
SECOES_REMOVIDAS = ("ABERTURA DE CONVERSA",)

FLUXO_DA_CAMPANHA = (
    "1. AREAS\n"
    "   Pergunte quais areas ela quer tratar DESTA VEZ. Sempre pergunte, mesmo\n"
    "   que ela ja seja cliente antiga.\n"
    "\n"
    "2. DATA E HORARIO\n"
    "   Com as areas confirmadas por ela, ofereca as datas da campanha e confirme\n"
    "   os horarios com check_availability e get_time_slots.\n"
    "   Se ela pedir um dia fora da campanha, diga que naquele dia nao ha agenda\n"
    "   e ofereca os que existem.\n"
    "\n"
    "3. CONFIRMACAO\n"
    "   Resuma em uma mensagem curta: areas, data e horario. SEM valor.\n"
    "   Pergunte \"Confirmo?\"\n"
    "\n"
    "4. AGENDAMENTO\n"
    "   Depois do sim dela, chame calculate_discount (o preco gravado precisa\n"
    "   estar certo) e em seguida book_appointment. NAO peca dados de cadastro:\n"
    "   ela ja e cadastrada e o nome dela esta no seu contexto.\n"
    "\n"
    "5. ENCERRAMENTO\n"
    "   Chame get_pre_session_instructions e envie as orientacoes completas,\n"
    "   junto com o endereco.\n"
)


def _limite_da_secao(prompt, titulo):
    """(inicio, fim) da secao, ou None. O fim e o proximo cabecalho."""
    marca = re.search(
        re.escape(_CABECALHO) + r"\s*" + re.escape(titulo) + r"\s*" + re.escape(_CABECALHO),
        prompt,
    )
    if not marca:
        return None
    seguinte = prompt.find(_CABECALHO, marca.end())
    return marca.start(), (seguinte if seguinte != -1 else len(prompt))


def adapta(prompt):
    """Devolve o prompt sem o roteiro de lead, com o da campanha no lugar.

    Tolerante a template editado pela clinica: secao que nao existe e ignorada
    em silencio - o bloco de campanha e a trava de saida seguem valendo.
    """
    if not prompt:
        return prompt

    for titulo in SECOES_REMOVIDAS:
        limite = _limite_da_secao(prompt, titulo)
        if limite:
            prompt = prompt[:limite[0]] + prompt[limite[1]:]

    limite = _limite_da_secao(prompt, SECAO_DO_FLUXO)
    if limite:
        novo = (
            "\n" + _CABECALHO + " COMO CONDUZIR A CONVERSA (CAMPANHA) " + _CABECALHO
            + "\n" + FLUXO_DA_CAMPANHA + "\n"
        )
        prompt = prompt[:limite[0]] + novo + prompt[limite[1]:]
    return prompt


# -- Trava de saida --------------------------------------------------------
#
# Retirar do prompt reduz a chance; so a trava garante. Mesmo desenho da
# proveniencia: confere a mensagem PRONTA, antes de virar WhatsApp.

_PEDIDOS_DE_CADASTRO = (
    "cpf",
    "nome completo",
    "data de nascimento",
    "data de nasc",
)


def _sem_acento(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    ).lower()


def pede_cadastro(texto):
    """Os termos de cadastro que a mensagem cita, se citar algum.

    Numa conversa de campanha nao ha motivo legitimo para o bot escrever "CPF"
    ou "nome completo": a paciente esta cadastrada e o nome dela vai no
    contexto do prompt.
    """
    plano = _sem_acento(texto)
    return [termo for termo in _PEDIDOS_DE_CADASTRO if termo in plano]
