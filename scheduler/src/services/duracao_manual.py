# -*- coding: utf-8 -*-
"""A duração que uma pessoa fixou para UM agendamento.

[duration_rules] diz que a duração é derivada, nunca informada, e a razão é boa:
em 02/09/2026 o agente pediu horários para uma sessão de 4 minutos, porque nada
impedia ele de informar o número. Desde então `create_appointment` recebe
`total_duration_minutes` do chamador e joga fora.

Este módulo abre UMA exceção a isso, e a exceção tem dono: a recepção, num
agendamento específico, pelo painel. O caso é o que o cálculo não sabe - a
paciente que sempre demora mais, a sessão que vai acumular duas coisas, o dia em
que a sala precisa de folga.

O que NÃO muda, e é o desenho inteiro:

  - A regra da clínica (`scheduler.duration_rules`) não é tocada. O override vale
    para um agendamento e morre com ele.
  - O bot continua sem poder opinar. Ele não chega aqui: `manual_duration_minutes`
    só entra pelos handlers HTTP de criar e editar, e nenhuma tool do agente
    expõe esse campo. `total_duration_minutes` que ele passa segue ignorado.

Decisões do André em 16/09/2026:

  - O manual NÃO passa por piso, teto nem passo. Escapar da regra é o ponto: um
    teto de 50 impediria exatamente a sessão longa que motivou o pedido. Só há
    faixa de sanidade, para um dedo errado não zerar nem estourar a agenda.
  - Trocar as áreas de um agendamento DESCARTA o override. Ele foi decidido para
    outro conjunto de áreas; mudou a área, mudou a premissa. Ver
    `update_appointment_services`.

Por isso este módulo não importa [duration_rules]: a independência é o ponto, e
o import só criaria a tentação de "clampar só um pouquinho".
"""
import logging

logger = logging.getLogger(__name__)

# Faixa de sanidade, não regra de negócio. Larga de propósito: apertar aqui é
# recriar o teto que o override existe para furar.
MINIMO = 5
MAXIMO = 480


class DuracaoInvalida(ValueError):
    """Valor que a atendente digitou e não dá para aceitar.

    ValueError de propósito: os handlers HTTP transformam em 400, não em 500 -
    dedo errado no formulário não é falha do servidor.
    """


def valida(valor):
    """Os minutos como inteiro, ou None quando não há override.

    Campo vazio e `null` explícito são a mesma intenção - "sem override" - e por
    isso viram None os dois. Quem distingue "não mexer" de "limpar" é o handler,
    olhando se a chave veio no corpo; aqui já chegou a decisão.
    """
    if valor is None or valor == "":
        return None

    try:
        # int(str) recusa "3.5" e "abc", que é o que se quer: minuto quebrado
        # não existe na agenda, e texto não é duração.
        minutos = int(str(valor).strip())
    except (TypeError, ValueError):
        raise DuracaoInvalida(
            f"Duração inválida: {valor!r}. Informe um número inteiro de minutos."
        )

    if not MINIMO <= minutos <= MAXIMO:
        raise DuracaoInvalida(
            f"A duração precisa estar entre {MINIMO} e {MAXIMO} minutos "
            f"(recebido: {minutos})."
        )
    return minutos


def efetiva(calculada, manual):
    """A duração que vale: a manual quando existe, a calculada quando não.

    Única resposta para essa pergunta em todo o sistema. Se cada caminho de
    escrita decidisse sozinho, voltaria a existir mais de uma verdade sobre
    quanto tempo a sala fica ocupada - que é exatamente o que [duration_rules]
    foi criado para acabar.

    `0` conta como ausência de override, coerente com MINIMO=5: um zero vindo de
    payload malformado zeraria a sessão na agenda, e o silêncio disso é pior que
    a duração errada.
    """
    if manual:
        return int(manual)
    return int(calculada or 0)
