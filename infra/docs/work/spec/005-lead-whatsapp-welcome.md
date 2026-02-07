# SPEC-005: WhatsApp Welcome Message on Lead Creation

**PRD:** [005-lead-whatsapp-welcome](../prd/005-lead-whatsapp-welcome.md)
**Status:** Ready for Implementation
**Created:** 2026-02-07

---

## Resumo das Mudancas

Adicionar envio automatico de mensagem de boas-vindas via WhatsApp quando um lead e criado com `clinicId`. Usa invocacao Lambda-to-Lambda do `CreateLead` (infra) para o `SendMessage` (scheduler).

---

## Ordem de Implementacao

1. Modificar `sls/functions/leads/interface.yml` (IAM permissions + env var)
2. Modificar `src/functions/leads/create.py` (logica de envio WhatsApp)
3. Criar `tests/mocks/leads/create_with_whatsapp.json` (mock para teste)

---

## Arquivos a Modificar

### 1. `sls/functions/leads/interface.yml`

**Alteracoes no CreateLead:**

Adicionar environment variable:
```yaml
environment:
  SCHEDULER_SEND_FUNCTION: clinic-scheduler-infra-${self:custom.stage}-SendMessage
```

Adicionar IAM statements:
```yaml
# Invocar SendMessage do scheduler
- Effect: Allow
  Action:
    - lambda:InvokeFunction
  Resource: arn:aws:lambda:${self:provider.region}:${self:custom.accountId}:function:clinic-scheduler-infra-${self:custom.stage}-SendMessage

# Buscar SCHEDULER_API_KEY no SSM
- Effect: Allow
  Action:
    - ssm:GetParameter
  Resource: arn:aws:ssm:${self:provider.region}:${self:custom.accountId}:parameter/${self:custom.stage}/SCHEDULER_API_KEY

# Atualizar lead com campos de whatsapp
- Effect: Allow
  Action:
    - dynamodb:UpdateItem
  Resource: !GetAtt LeadsTable.Arn
```

### 2. `src/functions/leads/create.py`

**Alteracoes:**

Adicionar imports: `boto3.client('lambda')`, `boto3.client('ssm')`

Adicionar variaveis globais (cached):
```python
lambda_client = boto3.client("lambda")
ssm_client = boto3.client("ssm")
_scheduler_api_key_cache = None
```

Adicionar funcoes helper:

**`_get_scheduler_api_key()`** — Busca e cacheia o SCHEDULER_API_KEY do SSM:
```python
def _get_scheduler_api_key() -> str:
    global _scheduler_api_key_cache
    if _scheduler_api_key_cache:
        return _scheduler_api_key_cache
    stage = os.environ.get("STAGE", "dev")
    response = ssm_client.get_parameter(Name=f"/{stage}/SCHEDULER_API_KEY", WithDecryption=True)
    _scheduler_api_key_cache = response["Parameter"]["Value"]
    return _scheduler_api_key_cache
```

**`_send_whatsapp_welcome()`** — Constroi evento e invoca SendMessage:
```python
def _send_whatsapp_welcome(phone: str, name: str, clinic_id: str) -> dict:
    api_key = _get_scheduler_api_key()
    message = f"Ola {name}! Obrigado pelo seu interesse. Em breve entraremos em contato!"

    payload = {
        "httpMethod": "POST",
        "path": "/send",
        "headers": {"Content-Type": "application/json", "x-api-key": api_key},
        "body": json.dumps({
            "clinicId": clinic_id,
            "phone": phone,
            "type": "text",
            "content": message
        })
    }

    function_name = os.environ.get("SCHEDULER_SEND_FUNCTION")
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode()
    )

    result = json.loads(response["Payload"].read().decode())
    return result
```

**Alteracao no handler:** Apos `put_item`, adicionar bloco de envio WhatsApp:
```python
# Enviar WhatsApp welcome (best-effort)
clinic_id = body.get("clinicId")
if clinic_id and body.get("phone"):
    try:
        result = _send_whatsapp_welcome(body["phone"], body["name"], clinic_id)
        result_body = json.loads(result.get("body", "{}"))

        whatsapp_fields = {
            "clinicId": clinic_id,
            "whatsappStatus": "SENT" if result.get("statusCode") == 200 else "FAILED",
            "whatsappSentAt": datetime.utcnow().isoformat(),
        }
        if result_body.get("messageId"):
            whatsapp_fields["whatsappMessageId"] = result_body["messageId"]
        if result.get("statusCode") != 200:
            whatsapp_fields["whatsappError"] = result_body.get("error", result_body.get("message", "Unknown error"))

        # Update lead with whatsapp fields
        leads_table.update_item(
            Key={"leadId": lead_id},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in whatsapp_fields),
            ExpressionAttributeNames={f"#{k}": k for k in whatsapp_fields},
            ExpressionAttributeValues={f":{k}": v for k, v in whatsapp_fields.items()},
        )

        lead_item.update(whatsapp_fields)
    except Exception as e:
        logger.error(f"Falha ao enviar WhatsApp welcome para lead {lead_id}: {str(e)}")
        lead_item["whatsappStatus"] = "FAILED"
        lead_item["whatsappError"] = str(e)
```

---

## Arquivos a Criar

### 3. `tests/mocks/leads/create_with_whatsapp.json`

```json
{
  "httpMethod": "POST",
  "path": "/leads",
  "headers": {
    "Content-Type": "application/json",
    "x-api-key": "test-api-key"
  },
  "body": "{\"clientId\": \"empresarodsteste-bd5f23\", \"name\": \"Maria Silva\", \"phone\": \"5511999999999\", \"email\": \"maria@example.com\", \"location\": \"Sao Paulo\", \"clinicId\": \"laser-beauty-sp-abc123\"}",
  "requestContext": {
    "stage": "dev",
    "requestId": "test-request-id"
  }
}
```

---

## Endpoints Resultantes

Nenhum endpoint novo. O endpoint existente `POST /leads` ganha campo opcional `clinicId` no body e campos de tracking na resposta.

### Novo campo no body do POST /leads

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `clinicId` | String | Nao | ID da clinica no scheduler para envio de WhatsApp |

### Novos campos na resposta (quando clinicId informado)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `whatsappStatus` | String | `SENT` ou `FAILED` |
| `whatsappMessageId` | String | ID da mensagem (quando SENT) |
| `whatsappSentAt` | String | ISO timestamp do envio |
| `whatsappError` | String | Erro (quando FAILED) |

---

## Checklist de Implementacao

- [ ] Atualizar `sls/functions/leads/interface.yml` com IAM permissions e env var
- [ ] Atualizar `src/functions/leads/create.py` com logica de WhatsApp
- [ ] Criar `tests/mocks/leads/create_with_whatsapp.json`
- [ ] Testar endpoint com curl
- [ ] Criar documentacao de integracao
- [ ] Criar Postman collection
