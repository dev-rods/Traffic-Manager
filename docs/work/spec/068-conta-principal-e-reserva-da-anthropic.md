# Spec - 068 Conta principal e conta reserva da Anthropic

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/068-conta-principal-e-reserva-da-anthropic.md`

---

## 1. Resumo

`AnthropicService` passa a ter uma lista ordenada de contas, a principal e a
reserva, e só passa para a seguinte quando a conta anterior é **recusada**.
Falha passageira continua retentada na mesma conta.

O aviso não usa filtro de métrica nem permissão de IAM. Cada evento grava uma
linha no formato EMF do CloudWatch (Embedded Metric Format), uma linha JSON no
stdout que o CloudWatch transforma em métrica sozinho. Dois alarmes sobre
essas métricas publicam num tópico SNS com o e-mail do André.

Os eventos são:
- chamada atendida pela reserva;
- chamada que falhou de vez.

---

## 2. Erros da API (conferidos em 27/11/2026 na documentação)

A documentação está em `platform.claude.com/docs/en/api/errors`, e a lista de
`ErrorDetails` em `/api/$shared`.

| Resposta | Classe | Ação |
|---|---|---|
| 401 `authentication_error` (chave inválida, revogada ou **expirada**) | recusa da conta | próxima conta |
| 402 `billing_error` | recusa da conta | próxima conta |
| 403 `permission_error` | recusa da conta | próxima conta |
| qualquer status com `error.details.error_code` em `enforced_spend_limit_reached`, `contract_spend_limit_reached`, `linked_organization_spend_limit_reached`, `linked_organization_billing_unavailable`, `organization_on_hold` | recusa da conta | próxima conta. O 429 de teto mensal vem sem `retry-after` e falha até o mês virar, então retentar só atrasa a paciente |
| 400 `invalid_request_error` cuja mensagem fala de saldo ou de limite de gasto (`credit balance`, `spend limit`, `usage limit`, sem diferenciar maiúsculas) | recusa da conta | próxima conta. A documentação diz que o 400 também vale para o limite de gasto definido pela organização, mas não dá código para isso nem para falta de saldo. O texto é o único sinal. Se ele mudar, a chamada falha e cai no alarme de falha |
| 429 sem esses códigos, 5xx, 529, timeout, rede | passageira | retentativa na mesma conta, como hoje |
| outro 4xx | pedido | `AnthropicError`, sem tentar a próxima conta |

---

## 3. Arquivos

| Arquivo | Tipo | Alteração |
|---|---|---|
| `scheduler/src/services/anthropic_service.py` | modificar | contas, classificação, memória da recusa, EMF |
| `scheduler/src/services/consumo.py` | modificar | `registra_chamada(..., conta=None)` acrescenta `conta=` à linha |
| `scheduler/serverless.yml` | modificar | env `ANTHROPIC_API_KEY_RESERVA` (`${ssm:..., ''}`) e o recurso novo |
| `scheduler/sls/resources/alarmes/anthropic.yml` | criar | `AWS::SNS::Topic`, `AWS::SNS::Subscription` (email, `${ssm:/${stage}/ALERTA_EMAIL}`), 2 `AWS::CloudWatch::Alarm` |
| `scheduler/tests/unit/test_anthropic_reserva.py` | criar | casos da seção 6 |
| `scheduler/tests/unit/test_anthropic_retentativa.py` | conferir | continua verde sem mudança |
| `scheduler/tests/evaluation/eval_fluxo_agente.py` | modificar | lê também `/prod/ANTHROPIC_API_KEY_RESERVA` |
| SSM `/{dev,prod}/ALERTA_EMAIL` | criar | e-mail do André (String) |

O serviço de consentimento usa IAM por função, mas o EMF não precisa de IAM.

---

## 4. `anthropic_service.py`

```python
PRINCIPAL, RESERVA = "principal", "reserva"
MEMORIA_DA_RECUSA = 24 * 3600          # D4
CODIGOS_DE_RECUSA = {...}              # tabela da seção 2
_recusada_ate = {}                     # conta -> epoch; vive no contêiner

def contas():
    """[(nome, chave)] na ordem de uso, só as configuradas."""

def e_recusa_da_conta(status, corpo) -> bool:
    """Seção 2. Função pura, testada por vetores."""

class RecusaDaConta(AnthropicError): ...
```

- `AnthropicService.__init__`: `self.contas = contas()`. Sem nenhuma chave,
  mantém o warning de hoje.
- `create_message`:
  - O payload é montado uma vez.
  - A ordem é: as contas não recusadas, na ordem da lista, seguidas das
    recusadas. Assim a principal recusada ainda é tentada se a reserva também
    estiver fora, e nenhuma conta é descartada de vez.
  - Para cada conta, `_envia(nome, chave, payload)` faz o laço de
    retentativa de hoje, com a classificação da seção 2 antes do ramo de
    429/5xx.
    - **Recusa:** `_recusada_ate[nome] = agora + MEMORIA_DA_RECUSA`, log
      WARNING `[ContaAnthropic] Recusa da conta {nome}: {status}
      {type}/{error_code}`, e segue para a próxima conta.
    - **Sucesso:** se a conta estava marcada como recusada, desmarca e loga
      INFO `[ContaAnthropic] Conta {nome} voltou`. Se a conta não é a
      primeira da lista, grava a métrica `ChamadaPelaReserva`.
    - Chama `registra_consumo(corpo, model, conta=nome)` e devolve o corpo.
  - Se todas forem recusadas, ou se uma falhar de outro jeito, grava a métrica
    `ChamadaFalhou`, loga ERROR e relança o `AnthropicError`. O tratamento de
    quem chama não muda.
- `_metrica(nome)`: faz `print(json.dumps(...))` no formato EMF, com
  namespace `ClinicScheduler/Anthropic`, dimensão `Stage` (env `STAGE`) e
  unidade `Count`, valor 1. Dentro de `try`, porque falhar a métrica não pode
  derrubar o atendimento.
- A chave nunca aparece em log nem em exceção.

---

## 5. Alarmes (`sls/resources/alarmes/anthropic.yml`)

| Recurso | Configuração |
|---|---|
| `AlertaAnthropicTopic` | `TopicName: ${resourcePrefix}-alerta-anthropic` |
| `AlertaAnthropicEmail` | `Protocol: email`, `Endpoint: ${ssm:/${stage}/ALERTA_EMAIL}` |
| `ReservaEmUsoAlarm` | métrica `ChamadaPelaReserva`, `Sum >= 1` em 1 período de 3600 s, `TreatMissingData: notBreaching`, `AlarmActions` e `OKActions` no tópico |
| `BotSemRespostaAlarm` | métrica `ChamadaFalhou`, `Sum >= 1` em 1 período de 300 s, `notBreaching`, `AlarmActions` e `OKActions` no tópico |

- **Descrição do alarme da reserva, que vai no e-mail:** "A conta principal
  da Anthropic recusou chamadas e a reserva está pagando. Confira saldo,
  limite e chave da principal no Console. Para voltar na hora depois de
  recarregar, faça redeploy do scheduler. OK = uma hora sem uso da reserva
  (volta da principal ou só falta de conversa)."
- **Descrição do alarme de bot sem resposta:** "Chamada à Anthropic falhou
  de vez: o bot calou e a conversa foi para uma pessoa. Se for recusa das
  duas contas, recarregue a principal. Se for instabilidade da Anthropic, as
  pessoas na fila precisam de resposta manual."
- **Recursos:** 4 novos por stage. Prod vai de 430 para cerca de 434 de 500.

---

## 6. Testes (`test_anthropic_reserva.py`)

1. **Vetores de `e_recusa_da_conta`:**
   - 401, 402 e 403 são recusa.
   - 429 com `enforced_spend_limit_reached` é recusa; 429 sem código não é.
   - 400 com "Your credit balance is too low..." é recusa; 400 com limite
     de gasto é recusa.
   - 400 de pedido mal formado ("messages: field required") não é recusa.
   - 500 e 529 não são recusa.
2. Principal recusa com 401 e reserva atende: 2 posts, segunda com a chave
   da reserva, métrica `ChamadaPelaReserva` gravada, consumo com
   `conta=reserva`.
3. Memória: depois da recusa, a próxima chamada vai direto à reserva, com um
   post só. Avançando o relógio 24 h, volta a tentar a principal.
4. Principal volta: com a memória vencida e a principal atendendo, sai o log
   "voltou" e nenhuma métrica.
5. 429 sem código e 500 são retentados na principal, sem tocar a reserva.
6. 400 de pedido não vai à reserva: `AnthropicError` e métrica `ChamadaFalhou`.
7. Sem reserva, a principal recusada dá `AnthropicError` com um post só,
   igual a hoje.
8. As duas recusadas: `AnthropicError` e `ChamadaFalhou`.
9. A chave não aparece no texto da exceção nem nos logs capturados.
10. A linha EMF é JSON válido, com `_aws.CloudWatchMetrics` e
    `Stage`.

---

## 7. Verificação

1. Pytest do scheduler inteiro.
2. **Local, contra a API real, sem WhatsApp:** principal com uma chave
   inventada e reserva com a chave nova de prod. Deve sair 401, depois
   resposta pela reserva. Também, uma chamada com a chave antiga para
   registrar o texto real do erro de saldo, se ela estiver sem saldo.
3. SSM `ALERTA_EMAIL` em dev e prod; deploy dev; confirmar que a assinatura
   SNS ficou pendente e que o André clicou no e-mail.
4. **Alarme de ponta a ponta em dev:** uma Lambda de dev é invocada com a
   principal inválida só nessa função, numa rota que não envia WhatsApp. Se
   não houver rota assim, publica-se a métrica EMF por `put-metric-data` com
   o mesmo namespace e dimensão. Conferir o e-mail de ALARM e depois o de OK.
5. Deploy prod e uma chamada real atendida pela principal (`conta=principal`
   no `[Consumo]`).
