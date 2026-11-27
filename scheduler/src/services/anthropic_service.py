import json
import os
import random
import re
import time
import logging

import requests

from src.services.consumo import registra_chamada as registra_consumo

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"

# Duas contas, em ordem (PRD 068). A principal paga o uso normal; a reserva só
# entra quando a principal é RECUSADA - sem saldo, no teto de gasto, chave
# inválida ou expirada. Em 14/09/2026 a única conta ficou sem saldo e o bot
# calou sem ninguém saber; com a reserva, a paciente nem percebe, e o André
# recebe o aviso pelo alarme (sls/resources/alarmes/anthropic.yml).
PRINCIPAL = "principal"
RESERVA = "reserva"
VARIAVEIS_DAS_CONTAS = (
    (PRINCIPAL, "ANTHROPIC_API_KEY"),
    (RESERVA, "ANTHROPIC_API_KEY_RESERVA"),
)

# Depois de uma recusa, o contêiner vai direto à próxima conta por este tempo
# (decisão D4 do André: 24 h). A memória morre com o contêiner, então na
# prática cada contêiner novo tenta a principal uma vez; redeploy zera todos.
MEMORIA_DA_RECUSA = 24 * 3600
_recusada_ate = {}

# Recusa da conta, conferida em 27/11/2026 em platform.claude.com/docs/en/api/errors.
# Falha passageira (429 comum, 5xx, 529, rede) NÃO entra aqui: retenta-se na
# mesma conta. Passar para a reserva por isso só gastaria a outra conta.
STATUS_DE_RECUSA = {401, 402, 403}
CODIGOS_DE_RECUSA = {
    "enforced_spend_limit_reached",      # 429 do teto mensal: sem retry-after, falha até o mês virar
    "contract_spend_limit_reached",
    "linked_organization_spend_limit_reached",
    "linked_organization_billing_unavailable",
    "organization_on_hold",
}
# Falta de saldo e o limite de gasto definido pela organização chegam como 400
# `invalid_request_error`, sem código. O texto é o único sinal; se mudar, a
# chamada falha e o alarme de bot sem resposta avisa.
TEXTO_DE_RECUSA = re.compile(r"credit balance|spend limit|usage limit", re.IGNORECASE)

METRICA_RESERVA = "ChamadaPelaReserva"
METRICA_FALHA = "ChamadaFalhou"


def contas():
    """[(nome, chave)] na ordem de uso, só as configuradas."""
    return [
        (nome, os.environ.get(variavel))
        for nome, variavel in VARIAVEIS_DAS_CONTAS
        if os.environ.get(variavel)
    ]


def e_recusa_da_conta(status, corpo) -> bool:
    """A conta recusou o pedido (e outra conta pode atendê-lo)?"""
    erro = (corpo or {}).get("error") or {}
    codigo = (erro.get("details") or {}).get("error_code")
    if codigo in CODIGOS_DE_RECUSA or status in STATUS_DE_RECUSA:
        return True
    return (
        status == 400
        and erro.get("type") == "invalid_request_error"
        and bool(TEXTO_DE_RECUSA.search(erro.get("message") or ""))
    )


def _metrica(nome):
    """Uma unidade da métrica `nome`, no formato EMF do CloudWatch.

    A linha JSON no stdout vira métrica sozinha, sem filtro e sem permissão de
    IAM. Os alarmes do PRD 068 olham estas métricas. Nunca levanta: perder a
    métrica não pode custar a resposta da paciente.
    """
    try:
        print(json.dumps({
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [{
                    "Namespace": "ClinicScheduler/Anthropic",
                    "Dimensions": [["Stage"]],
                    "Metrics": [{"Name": nome, "Unit": "Count"}],
                }],
            },
            "Stage": os.environ.get("STAGE", "dev"),
            nome: 1,
        }), flush=True)
    except Exception as e:
        logger.error(f"[ContaAnthropic] Falha ao gravar a métrica {nome}: {e}")


class AnthropicService:

    def __init__(self):
        self.contas = contas()
        if not self.contas:
            logger.warning("[AnthropicService] ANTHROPIC_API_KEY not set")

    def create_message(
        self,
        system,
        messages,
        tools=None,
        model=DEFAULT_MODEL,
        temperature=None,
        max_tokens=1024,
        tool_choice=None,
    ):
        """
        Call Anthropic Messages API with optional tool use.

        Returns the parsed JSON response dict.
        Retries up to 5 times on 429/5xx with exponential backoff (3s base),
        always on the same account. Only a refusal of the account (see
        `e_recusa_da_conta`) moves the call to the next one (PRD 068).

        `temperature` só entra no payload quando o chamador informa um valor.
        Enviá-lo sempre quebrava o modelo atual, que responde
        400 "`temperature` is deprecated for this model."
        """
        # O system vai como bloco com cache_control, nao como string solta.
        #
        # A ordem de render e tools -> system -> messages, entao um breakpoint no
        # ultimo bloco de system cobre tools + system: os ~17k chars de prompt
        # mais as definicoes das 15 tools, que sao identicos em toda requisicao.
        # O agent loop faz de 2 a 4 chamadas por mensagem e reenviava esse
        # prefixo inteiro a preco cheio em cada uma.
        #
        # Leitura de cache custa ~0,1x; a escrita custa 1,25x e se paga na
        # segunda chamada - ou seja, ja na primeira mensagem que use uma tool.
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }] if system else system,
            "messages": messages,
        }

        if temperature is not None:
            payload["temperature"] = temperature

        if tools:
            payload["tools"] = tools

        # Obriga o modelo a chamar uma tool específica nesta rodada. Usado quando
        # a pergunta é sobre agenda: deixar a escolha com ele fez o bot listar
        # horários inventados com tools=0, mesmo com o prompt mandando consultar.
        if tool_choice:
            payload["tool_choice"] = tool_choice

        ordem = sorted(self.contas, key=lambda c: _recusada_ate.get(c[0], 0) > time.time())
        ultimo_erro = AnthropicError("Anthropic API key not configured")
        for nome, chave in ordem:
            try:
                corpo = self._envia(nome, chave, payload, model)
            except RecusaDaConta as recusa:
                _recusada_ate[nome] = time.time() + MEMORIA_DA_RECUSA
                logger.warning(f"[ContaAnthropic] Recusa da conta {nome}: {recusa.resumo}")
                ultimo_erro = recusa
                continue
            except AnthropicError:
                _metrica(METRICA_FALHA)
                raise
            if _recusada_ate.pop(nome, None):
                logger.info(f"[ContaAnthropic] Conta {nome} voltou a atender")
            if nome != self.contas[0][0]:
                logger.warning(f"[ContaAnthropic] Chamada atendida pela conta {nome}")
                _metrica(METRICA_RESERVA)
            return corpo

        _metrica(METRICA_FALHA)
        logger.error(f"[ContaAnthropic] Nenhuma conta atendeu: {ultimo_erro}")
        raise ultimo_erro

    def _envia(self, nome, chave, payload, model):
        """Uma conta, com a retentativa de falha passageira de sempre."""
        headers = {
            "x-api-key": chave,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        max_retries = 5

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    ANTHROPIC_API_URL, headers=headers, json=payload, timeout=25
                )

                # Antes do ramo de 429: o 429 do teto mensal é recusa da conta,
                # não limite de taxa - retentá-lo só atrasa a paciente.
                if response.status_code != 200 and e_recusa_da_conta(
                        response.status_code, _corpo(response)):
                    raise RecusaDaConta(nome, response.status_code, _corpo(response))

                if response.status_code == 200:
                    corpo = response.json()
                    # O `usage` vem em toda resposta e era descartado aqui. Ver
                    # consumo.py: sem esta linha, "o que gastou os créditos?"
                    # não tem resposta nos logs.
                    registra_consumo(corpo, model, conta=nome)
                    return corpo

                if response.status_code == 429 or response.status_code >= 500:
                    # Honor Retry-After when the API provides it (429 / 503).
                    # Otherwise use decorrelated jitter: random in [base, prev*3]
                    # capped at 60s. With many parallel Lambdas hitting the same
                    # rate limit, jitter desynchronizes retries instead of
                    # creating retry waves that all hit 429 again.
                    retry_after = response.headers.get("retry-after")
                    if retry_after:
                        try:
                            wait_time = min(float(retry_after), 60.0)
                        except ValueError:
                            wait_time = min(2.0 * (3 ** attempt), 60.0)
                    else:
                        base = 2.0
                        wait_time = min(random.uniform(base, base * (3 ** (attempt + 1))), 60.0)
                    logger.warning(
                        f"[AnthropicService] API error (status {response.status_code}), "
                        f"retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue

                logger.error(
                    f"[AnthropicService] API error {response.status_code}: {response.text[:500]}"
                )
                raise AnthropicError(
                    f"Anthropic API error {response.status_code}: {response.text[:200]}"
                )

            # Timeout e conexão derrubada são a mesma classe de problema: falha
            # transitória de rede, que uma segunda tentativa resolve. Só o
            # timeout era retentado; ConnectionError caía no ramo genérico
            # abaixo e estourava de primeira, e a pessoa recebia "estou com
            # dificuldades" por um reset que ia passar sozinho.
            #
            # Apareceu no eval: 130 de 300 chamadas seguidas morreram com
            # ConnectionResetError. Em produção o volume é menor, mas o caminho
            # é o mesmo - e ali quem paga é a paciente esperando resposta.
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError) as e:
                wait_time = min(random.uniform(2.0, 2.0 * (3 ** (attempt + 1))), 60.0)
                logger.warning(
                    f"[AnthropicService] Falha de rede ({type(e).__name__}), "
                    f"retentando em {wait_time:.1f}s "
                    f"(tentativa {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
            except AnthropicError:
                raise
            except requests.exceptions.RequestException as e:
                logger.error(f"[AnthropicService] Request exception: {e}")
                raise AnthropicError(f"Anthropic request failed: {e}")

        raise AnthropicError(
            f"Anthropic API failed after {max_retries} retries"
        )


class AnthropicError(Exception):
    pass


class RecusaDaConta(AnthropicError):
    """A conta recusou o pedido; outra conta pode atendê-lo. Nunca leva a chave."""

    def __init__(self, conta, status, corpo):
        erro = (corpo or {}).get("error") or {}
        codigo = (erro.get("details") or {}).get("error_code")
        self.conta = conta
        self.status = status
        self.resumo = (
            f"{status} {erro.get('type')}"
            + (f"/{codigo}" if codigo else "")
            + f": {(erro.get('message') or '')[:160]}"
        )
        super().__init__(f"Anthropic API error {status} (conta {conta}): {self.resumo}")


def _corpo(response):
    try:
        return response.json()
    except ValueError:
        return {}
