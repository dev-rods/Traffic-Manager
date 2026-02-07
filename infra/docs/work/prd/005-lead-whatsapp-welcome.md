# PRD-005: WhatsApp Welcome Message on Lead Creation

**Status:** Implemented
**Created:** 2026-02-07
**Author:** Claude

---

## 1. Problema / Objetivo

Quando um novo lead e criado via `POST /leads`, queremos enviar automaticamente uma mensagem de boas-vindas pelo WhatsApp para o telefone do lead. Isso permite um contato imediato e automatizado com o lead, aumentando a taxa de conversao.

### Requisitos

1. Ao criar um lead com `clinicId` no body, enviar mensagem de boas-vindas via WhatsApp
2. Utilizar invocacao Lambda-to-Lambda (infra `CreateLead` → scheduler `SendMessage`)
3. O envio de WhatsApp e best-effort: falhas nunca devem impedir a criacao do lead
4. Registrar status do envio no item do lead no DynamoDB (`whatsappStatus`, `whatsappMessageId`, `whatsappSentAt`, `whatsappError`)
5. `clinicId` e um campo opcional no body do POST /leads (`clientId` != `clinicId`)

---

## 2. Solucao Proposta

### 2.1 Fluxo

1. Lead e criado normalmente no DynamoDB (fluxo existente)
2. Se `clinicId` estiver presente no body E `phone` estiver preenchido:
   a. Obter `SCHEDULER_API_KEY` do SSM (com cache)
   b. Construir evento API Gateway para o Lambda `SendMessage` do scheduler
   c. Invocar Lambda `clinic-scheduler-infra-{stage}-SendMessage` de forma sincrona
   d. Atualizar item do lead no DynamoDB com campos de tracking do WhatsApp
3. Retornar resposta ao cliente com dados do lead + status do WhatsApp

### 2.2 Campos Novos no Lead (DynamoDB)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `clinicId` | String | ID da clinica no scheduler (opcional) |
| `whatsappStatus` | String | `SENT`, `FAILED`, ou `SKIPPED` |
| `whatsappMessageId` | String | ID da mensagem retornado pelo scheduler |
| `whatsappSentAt` | String | ISO timestamp do envio |
| `whatsappError` | String | Mensagem de erro em caso de falha |

### 2.3 Template da Mensagem

```
Ola {name}! Obrigado pelo seu interesse. Em breve entraremos em contato!
```

### 2.4 Arquitetura

```
POST /leads (infra)
  └─ CreateLead handler
       ├─ put_item (DynamoDB) — lead salvo
       ├─ _get_scheduler_api_key() — SSM cached
       ├─ _send_whatsapp_welcome() — Lambda invoke
       │    └─ clinic-scheduler-infra-{stage}-SendMessage
       └─ update_item (DynamoDB) — whatsapp fields
```

---

## 3. Arquivos Afetados

### Arquivos Modificados
- `src/functions/leads/create.py` — Adicionar logica de envio WhatsApp
- `sls/functions/leads/interface.yml` — Adicionar IAM permissions (lambda:InvokeFunction, ssm:GetParameter, dynamodb:UpdateItem)

### Arquivos Novos
- `tests/mocks/leads/create_with_whatsapp.json` — Mock para teste local

### Arquivos Removidos
- Nenhum

---

## 4. Dependencias

- boto3 Lambda client (ja disponivel)
- boto3 SSM client (ja disponivel)
- Scheduler project deployado com funcao `SendMessage` ativa
- SSM parameter `/${stage}/SCHEDULER_API_KEY` configurado

---

## 5. Consideracoes

### Best-Effort
- Falhas no envio de WhatsApp nunca devem impedir a criacao do lead
- Todo o bloco de envio e encapsulado em try/except
- Falhas sao logadas e registradas no campo `whatsappError`

### Performance
- SSM parameter e cached em variavel global (warm Lambda)
- Invocacao Lambda sincrona adiciona latencia (~1-3s) mas e aceitavel para criacao de lead

### Seguranca
- `SCHEDULER_API_KEY` e obtida via SSM (nunca hardcoded)
- IAM role do CreateLead precisa de permissao para invocar Lambda do scheduler

---

## Historico

| Data | Status | Notas |
|------|--------|-------|
| 2026-02-07 | Draft | PRD criado |
| 2026-02-07 | Spec Generated | Spec criada em docs/work/spec/005-lead-whatsapp-welcome.md |
| 2026-02-07 | Implemented | Codigo implementado |
