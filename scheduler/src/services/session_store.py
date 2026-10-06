"""Marca conversas como elegíveis para resposta automática do bot.

A sessão é gravada aninhada: o item do DynamoDB tem {"pk", "sk", "session": {...}},
e `_load_session` devolve o conteúdo de `session`. Um `SET bot_enabled` na raiz do
item seria invisível para quem lê a sessão — com a política LEADS_ONLY o bot
ficaria mudo para todo mundo, silenciosamente. Por isso a marca entra dentro de
`session`.

Lê, mescla e grava em vez de usar UpdateExpression com caminho aninhado: o
`session` pode ainda não existir, e a leitura extra é irrelevante no volume aqui
(uma abordagem a cada 10 minutos).
"""
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def mark_conversation_eligible(table, clinic_id: str, phone: str,
                               lead_id: Optional[str] = None) -> bool:
    """Marca a conversa como elegível, preservando o histórico já gravado.

    Devolve True se gravou. Nunca levanta: falhar aqui não pode derrubar o envio
    que já aconteceu.
    """
    pk, sk = f"CLINIC#{clinic_id}", f"PHONE#{phone}"
    try:
        item = table.get_item(Key={"pk": pk, "sk": sk}).get("Item") or {}
        session = item.get("session") or {}

        session["bot_enabled"] = True
        if lead_id:
            session["lead_id"] = str(lead_id)

        table.put_item(
            Item={
                "pk": pk,
                "sk": sk,
                "session": session,
                "clinicId": clinic_id,
                "phone": phone,
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()))),
            }
        )
        logger.info(f"[SessionStore] Conversa {phone} marcada como elegível")
        return True
    except Exception as e:
        logger.error(f"[SessionStore] Falha ao marcar {phone} como elegível: {e}")
        return False


def abre_campanha(table, clinic_id: str, phone: str, campanha: dict) -> bool:
    """Grava a campanha de reagendamento na sessão da paciente.

    Chamada pelo disparo em massa, DEPOIS de a mensagem sair. Campanha aberta
    sem mensagem entregue deixa o bot esperando resposta de algo que ninguém
    recebeu.

    Dentro de `session`, nunca na raiz - a raiz é invisível para quem lê a
    sessão, e o bot ficaria mudo em silêncio (ver o docstring do módulo).

    Devolve True se gravou. Nunca levanta: falhar aqui não pode derrubar o envio
    que já aconteceu. Quem chama reporta o resultado para a tela.
    """
    pk, sk = f"CLINIC#{clinic_id}", f"PHONE#{phone}"
    try:
        item = table.get_item(Key={"pk": pk, "sk": sk}).get("Item") or {}
        session = item.get("session") or {}
        session["campanha"] = campanha

        # A campanha COMECA uma conversa. Quem ja falou com o bot antes tem
        # historico guardado, e sem limpar aqui o agente leria a conversa velha
        # e a continuaria - o bloco de campanha diz "acabamos de te escrever" e
        # o historico diz outra coisa, e quem decide na pratica e o historico.
        #
        # Encontrado no piloto de 09/09/2026: o numero de teste tinha 36 turnos
        # de 04/09 parados na sessao. Sem TTL na tabela, esse historico fica
        # para sempre - o mes que vem teria a conversa deste mes por baixo.
        session["agent_history"] = []
        session.pop("state", None)
        session.pop("respaldo_anterior", None)
        session.pop("efeito_na_ultima_rodada", None)

        table.put_item(
            Item={
                "pk": pk,
                "sk": sk,
                "session": session,
                "clinicId": clinic_id,
                "phone": phone,
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()))),
            }
        )
        logger.info(f"[SessionStore] Campanha aberta para {phone}")
        return True
    except Exception as e:
        logger.error(f"[SessionStore] Falha ao abrir campanha para {phone}: {e}")
        return False


def carrega_sessao(clinic_id: str, phone: str, table=None) -> dict:
    """A sessao como esta, ou vazia. Nunca levanta."""
    import os

    import boto3

    try:
        table = table or boto3.resource("dynamodb").Table(
            os.environ["CONVERSATION_SESSIONS_TABLE"]
        )
        item = table.get_item(
            Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"}
        ).get("Item") or {}
        return dict(item.get("session") or {})
    except Exception as e:
        logger.error(f"[SessionStore] Falha ao ler sessao de {phone}: {e}")
        return {}


# Os campos antigos que `atendimento` projeta. Gravados junto com o bloco, e
# so por aqui: o painel os le ate a fase 3.
_PROJECAO_LEGADA = (
    "state", "attendant_active_until", "bot_pausado_por", "handoff_reason",
    "human_handoff_requested_at",
)


def grava_atendimento(table, clinic_id: str, phone: str, session: dict,
                      extras: Optional[dict] = None) -> bool:
    """Grava SO o bloco `atendimento` (e sua projecao), condicionado a versao.

    Duas Lambdas escrevem a mesma sessao - o webhook assincrono e, na fase 3,
    o cron de vencimento. Um put da sessao inteira faria COOLDOWN sobrescrever
    HUMAN_ACTIVE em silencio. Aqui a escrita exige que a versao no banco seja
    a anterior a transicao (`versao - 1`); conflito e relido uma vez e a
    transicao e reaplicada pelo chamador... que hoje nao existe: em conflito
    o log diz, e a proxima mensagem reavalia do zero.

    `extras`: outros campos de primeiro nivel da sessao que a mesma acao
    muda (ex.: "Retomar bot" tambem grava bot_enabled). Devolve True se gravou.
    """
    from src.services.atendimento import CAMPO

    bloco = session.get(CAMPO) or {}
    versao = int(bloco.get("versao") or 0)
    pk, sk = f"CLINIC#{clinic_id}", f"PHONE#{phone}"

    nomes = {"#s": "session", "#a": CAMPO}
    valores = {":a": bloco, ":v": versao - 1,
               ":u": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    sets = ["#s.#a = :a", "updatedAt = :u", "clinicId = :c", "phone = :p"]
    valores[":c"], valores[":p"] = clinic_id, phone
    removes = []
    i = 0
    for campo in _PROJECAO_LEGADA + tuple((extras or {}).keys()):
        i += 1
        nomes[f"#f{i}"] = campo
        if campo in (extras or {}):
            valores[f":f{i}"] = extras[campo]
            sets.append(f"#s.#f{i} = :f{i}")
        elif campo in session:
            valores[f":f{i}"] = session[campo]
            sets.append(f"#s.#f{i} = :f{i}")
        else:
            removes.append(f"#s.#f{i}")

    expressao = "SET " + ", ".join(sets)
    if removes:
        expressao += " REMOVE " + ", ".join(removes)

    # Sem `session` no item (sessao nova) o caminho aninhado falha: cria o
    # item inteiro. A condicao de versao so vale quando ja ha bloco.
    try:
        item = table.get_item(Key={"pk": pk, "sk": sk}).get("Item") or {}
        if not item.get("session"):
            table.put_item(Item={
                "pk": pk, "sk": sk, "session": session, "clinicId": clinic_id,
                "phone": phone, "updatedAt": valores[":u"],
            })
            return True

        condicao = (
            "attribute_not_exists(#s.#a) OR attribute_not_exists(#s.#a.versao) "
            "OR #s.#a.versao = :v"
        )
        table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression=expressao,
            ConditionExpression=condicao,
            ExpressionAttributeNames=nomes,
            ExpressionAttributeValues=valores,
        )
        return True
    except Exception as e:
        nome = type(e).__name__
        if "ConditionalCheckFailed" in nome or "ConditionalCheckFailed" in str(e):
            logger.error(
                f"[SessionStore] Conflito de versao ao gravar atendimento de {phone} "
                f"(esperava {versao - 1}); transicao descartada"
            )
        else:
            logger.error(f"[SessionStore] Falha ao gravar atendimento de {phone}: {e}")
        return False


def vincula_lid(table, clinic_id: str, chat_lid: str, phone: str) -> None:
    """Guarda a quem pertence um LID do WhatsApp.

    Quando a atendente responde pelo celular, o z-api manda o LID no lugar do
    número e a mensagem não teria dono. As mensagens normais da mesma conversa
    trazem os dois campos juntos - é delas que o vínculo sai.

    Vive na tabela de sessões com sk=LID#..., ao lado de PHONE#...: mesma
    partição da clínica, sem tabela nova.
    """
    try:
        table.put_item(Item={
            "pk": f"CLINIC#{clinic_id}",
            "sk": f"LID#{chat_lid}",
            "phone": phone,
            "clinicId": clinic_id,
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
    except Exception as e:
        logger.warning(f"[SessionStore] Não consegui vincular {chat_lid} a {phone}: {e}")


def telefone_do_lid(table, clinic_id: str, chat_lid: str) -> Optional[str]:
    """O telefone vinculado a um LID, se já tivermos visto a conversa."""
    try:
        item = table.get_item(
            Key={"pk": f"CLINIC#{clinic_id}", "sk": f"LID#{chat_lid}"}
        ).get("Item") or {}
        return item.get("phone") or None
    except Exception as e:
        logger.warning(f"[SessionStore] Não consegui resolver o LID {chat_lid}: {e}")
        return None
