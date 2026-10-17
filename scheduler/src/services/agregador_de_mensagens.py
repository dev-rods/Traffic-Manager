# -*- coding: utf-8 -*-
"""Junta a rajada de mensagens da pessoa num turno só.

Quem escreve no WhatsApp não escreve parágrafo: manda "oi", "queria agendar",
"pra semana que vem" em três balões. O bot respondia cada um separado - e o
roteador classificava cada pedaço isolado, então "queria agendar" ia para a
consulta de agenda sem saber que a data vinha na mensagem seguinte.

Medido nas 70 conversas reais da Essência (MessageEvents, 90 dias): com uma
janela de 68s a partir da primeira mensagem, 49% dos turnos têm 2+ mensagens.
A curva satura ali - 90s só acrescenta 0,6 ponto.

A janela é FIXA e não reinicia. Reiniciar a cada mensagem nova parece melhor e
não é: a mediana de intervalo entre mensagens reais é 38s, então quase metade
das mensagens seguintes empurraria o relógio de novo. Simulado no mesmo
histórico, uma janela de 30s com reinício dava p90 de 56s e pior caso de 140s.
Fixa, a espera é limitada por construção: ninguém espera mais que a janela.

O `versao` é um contador atômico. Serve para duas coisas que se parecem e não
são a mesma: drenar sem perder mensagem que chegou no meio, e descobrir depois
que chegou mensagem nova enquanto o agente pensava.
"""
import logging
import time
from decimal import Decimal

logger = logging.getLogger(__name__)

# Segundos de espera antes de o bot começar a pensar. Fica aqui como último
# recurso: o valor real vem da clínica, para mudar sem deploy.
JANELA_PADRAO_SEGUNDOS = 68

# Teto de mensagens guardadas. A maior rajada do histórico tem 15; o corte
# existe para um item de sessão não crescer sem limite se alguém colar um
# romance em 40 balões.
MAX_MENSAGENS = 40

TTL_DO_BUFFER = 900  # 15 min: muito além de qualquer janela, some sozinho


def _chave(clinic_id, phone):
    return {"pk": f"CLINIC#{clinic_id}", "sk": f"BUFFER#{phone}"}


def enfileira(table, clinic_id, phone, mensagem, janela_segundos):
    """Guarda a mensagem e diz se é ela quem abre a janela.

    Devolve `(versao, momento_de_processar, abriu_a_janela)`.

    `abriu_a_janela` é True só para a primeira mensagem do turno - é ela que
    agenda o processamento. As seguintes entram no mesmo balde e não agendam
    nada, senão teríamos uma execução por mensagem, que é o problema original.

    `momento_de_processar` é gravado com `if_not_exists`: a janela é da primeira
    mensagem e as seguintes não a empurram.
    """
    agora = int(time.time())
    resposta = table.update_item(
        Key=_chave(clinic_id, phone),
        UpdateExpression=(
            "SET mensagens = list_append(if_not_exists(mensagens, :vazio), :nova), "
            "processar_em = if_not_exists(processar_em, :quando), "
            "#ttl = :ttl "
            "ADD versao :um"
        ),
        ExpressionAttributeNames={"#ttl": "ttl"},
        ExpressionAttributeValues={
            ":vazio": [],
            ":nova": [mensagem],
            ":quando": agora + int(janela_segundos),
            ":ttl": agora + TTL_DO_BUFFER,
            ":um": 1,
        },
        ReturnValues="ALL_NEW",
    )
    item = resposta["Attributes"]
    mensagens = item.get("mensagens") or []
    return (
        int(item.get("versao") or 0),
        int(item.get("processar_em") or agora),
        len(mensagens) == 1,
    )


def drena(table, clinic_id, phone, tentativas=3):
    """Tira tudo do balde de uma vez, sem perder o que chegou no meio.

    A remoção é condicionada à versão lida. Se uma mensagem entrou entre a
    leitura e a remoção, a condição falha e a gente lê de novo - senão aquela
    mensagem ficaria órfã: ela não abriu janela nenhuma (o balde existia), então
    não há outra execução agendada para buscá-la.

    Devolve `(mensagens, versao)`; `([], 0)` se não havia nada.
    """
    for tentativa in range(tentativas):
        item = (table.get_item(Key=_chave(clinic_id, phone)).get("Item")) or {}
        mensagens = item.get("mensagens") or []
        if not mensagens:
            return [], 0

        versao = int(item.get("versao") or 0)
        try:
            table.delete_item(
                Key=_chave(clinic_id, phone),
                ConditionExpression="versao = :v",
                ExpressionAttributeValues={":v": versao},
            )
            return [_limpa(m) for m in mensagens[:MAX_MENSAGENS]], versao
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            logger.info(
                f"[Agregador] mensagem entrou durante a drenagem de {phone}, "
                f"relendo (tentativa {tentativa + 1}/{tentativas})"
            )

    logger.error(f"[Agregador] não consegui drenar {phone} em {tentativas} tentativas")
    return [], 0


def edita(table, clinic_id, phone, message_id, content, tentativas=3):
    """A pessoa editou uma mensagem que ainda está no balde: troca o texto.

    Devolve True se trocou. False se a mensagem não está mais no balde - já foi
    drenada e respondida, ou nunca passou por aqui - e aí quem chama decide o
    que fazer com a correção.

    Em 10/10/2026 uma paciente escreveu "virilha completa + perianal", editou
    15s depois para "... + axilas", e o webhook jogou a edição fora como
    duplicata. A janela de 68s ainda estava aberta: bastava trocar o texto no
    balde e o bot leria a versão certa. Condicionado à versão, pelo mesmo
    motivo de `drena`: uma mensagem que entra no meio não pode se perder.
    """
    for tentativa in range(tentativas):
        item = (table.get_item(Key=_chave(clinic_id, phone)).get("Item")) or {}
        mensagens = item.get("mensagens") or []
        indice = next(
            (i for i, m in enumerate(mensagens) if (m or {}).get("message_id") == message_id),
            None,
        )
        if indice is None:
            return False
        versao = int(item.get("versao") or 0)
        try:
            table.update_item(
                Key=_chave(clinic_id, phone),
                UpdateExpression=f"SET mensagens[{indice}].content = :c ADD versao :um",
                ConditionExpression="versao = :v",
                ExpressionAttributeValues={":c": content, ":v": versao, ":um": 1},
            )
            logger.info(f"[Agregador] edição de {phone} aplicada no balde (msg {message_id})")
            return True
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            logger.info(
                f"[Agregador] balde de {phone} mudou durante a edição, "
                f"relendo (tentativa {tentativa + 1}/{tentativas})"
            )
    logger.error(f"[Agregador] não consegui aplicar a edição de {phone} em {tentativas} tentativas")
    return False


def chegou_mensagem_nova(table, clinic_id, phone):
    """Alguém escreveu depois de a gente ter drenado?

    Chamado antes de ENVIAR a resposta. O agente leva de 6 a 12s e nesse tempo a
    pessoa pode ter completado o raciocínio dela - responder ao que ela disse
    pela metade é o mesmo defeito que a janela existe para resolver, só que mais
    tarde. Quem chegou depois abriu uma janela nova e já tem processamento
    agendado, então descartar aqui não perde ninguém.
    """
    item = (table.get_item(Key=_chave(clinic_id, phone)).get("Item")) or {}
    return bool(item.get("mensagens"))


def _limpa(mensagem):
    """DynamoDB devolve número como Decimal; o resto do código espera int."""
    return {
        chave: int(valor) if isinstance(valor, Decimal) else valor
        for chave, valor in (mensagem or {}).items()
    }


def junta_conteudo(mensagens):
    """As várias falas viram o turno único que o agente lê.

    Uma por linha, na ordem em que chegaram. Sem numerar e sem rótulo: é uma
    pessoa falando, e o modelo lê melhor a fala do que um relatório dela.
    Vazias saem - áudio e imagem chegam sem conteúdo e virariam linha em branco.
    """
    partes = [(m.get("content") or "").strip() for m in mensagens or []]
    return "\n".join(p for p in partes if p)
