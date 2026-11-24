# 062 - Assinatura libera o pagamento na hora: testes de integração

PRD: `docs/work/prd/062-assinatura-libera-pagamento-na-hora.md`. Sem rota
nova: muda o que o `POST /public/clicksign/webhook` e o
`GET public/clinics/{c}/checkin/consents/{id}` fazem com o termo.

## Antes (prod, 18/11/2026)

| Termo | `sign` | `auto_close` | SIGNED (PDF baixado) | Espera |
|---|---|---|---|---|
| 6f54189e | 01:59:52 | 02:00:02 | 02:00:17 | 25 s |
| 6d0871a1 | 10:25:57 | 10:26:04 | 10:26:21 | 24 s |
| a7b6dd3e | 12:06:36 | 12:06:44 | 12:07:03 | 27 s |
| 5a269a89 | 12:57:13 | 12:57:23 | 12:57:43 | 30 s |

## Casos

| # | Caso | Esperado |
|---|---|---|
| 1 | `sign` com o termo SIGNING | 200; termo SIGNED com `signed_at = NOW()`; PDF arquivado se já existir, senão `"SIGNED: PDF pendente"` |
| 2 | `auto_close` com o termo SIGNED sem PDF | 200 `"SIGNED: PDF pendente"` se o PDF ainda não existir |
| 3 | `document_closed` com o termo SIGNED sem PDF e PDF pronto | 200 `SIGNED`; `pdf_s3_key`/`pdf_sha256` gravados; `signed_at` não muda |
| 4 | `document_closed` com o PDF ainda indisponível | 500, evento NÃO gravado em `consent_webhook_events`; o reenvio da ClickSign processa |
| 5 | `sign` com o termo CANCELLED/EXPIRED | 200 `"ignorado: já CANCELLED"` |
| 6 | Polling do iPad com envelope `closed` e sem PDF | `status: SIGNED` na resposta |

## Resultado em dev (24/11/2026, layer 218)

Webhooks assinados com o HMAC de `/dev/CLICKSIGN_WEBHOOK_SECRET`, contra
linhas reais de `scheduler.patient_consents` do sandbox (restauradas depois):

- **Caso 1**: termo `f4435afd` (envelope de sandbox vencido) posto em SIGNING;
  `sign` respondeu `200 SIGNED` em 2,9 s (cold start + download), linha SIGNED.
  O sandbox serve `links.files.signed` também para envelope vencido, então o
  PDF baixou e o caso 4 não se reproduz aqui (coberto no unitário
  `test_document_closed_sem_pdf_falha_para_a_clicksign_reenviar`).
- **Caso 3**: termo `dc54dd49` (assinado de verdade no sandbox) com
  `pdf_s3_key` apagado; `document_closed` respondeu `200 SIGNED` em 0,7 s,
  `pdf_sha256` voltou igual ao original (`b00fd7d7…`), `signed_at` mantido.

Unitários: `tests/unit/test_consentimento.py` (TestStatus, TestWebhook) e
`tests/unit/test_clicksign_webhook.py`.

## Curl (dev)

```bash
API=https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev
SECRET=$(MSYS_NO_PATHCONV=1 aws ssm get-parameter --name /dev/CLICKSIGN_WEBHOOK_SECRET \
  --with-decryption --query Parameter.Value --output text --profile traffic-manager)
BODY='{"event":{"name":"sign","occurred_at":"2026-11-24T12:00:00Z"},"document":{"key":"<documentId>"},"envelope":{"key":"<envelopeId>"}}'
HMAC=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')
curl -s -X POST -H "Content-Type: application/json" -H "Content-Hmac: sha256=$HMAC" \
  -d "$BODY" "$API/public/clicksign/webhook"
```
