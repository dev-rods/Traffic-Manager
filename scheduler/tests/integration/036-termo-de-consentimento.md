# 036 - Termo de consentimento (TCLE) assinado no check-in

Roteiro E2E em dev (ClickSign sandbox) e casos curl. Spec:
`docs/work/spec/036-termo-de-consentimento.md`.

## Achados no sandbox da ClickSign (03/11/2026)

Conferidos com o provedor real (`src/providers/clicksign_provider.py`) contra
`sandbox.clicksign.com`, modelo `ecd991c8-3d71-40f2-ac7c-1cae7aac4810`:

| Ponto | Resultado |
|---|---|
| Criar modelo pela API (`POST /api/v3/templates`) | OK com `content_base64` em data URI; o atributo `color` é recusado (400), omitir |
| Conta sem "e-mail do usuário da API" (Configurações → API) | Toda chamada responde 403 `forbidden`. A conta de produção precisa do mesmo ajuste |
| Sequência envelope → documento do modelo → signatário → requisitos → ativar | Aceita de ponta a ponta. Envelope `a8bd5667-...` criado como prova e deixado vencer |
| Requisitos `agree/sign` + `provide_evidence` `whatsapp` + `handwritten` | Aceitos. Se o widget embedded exigir `embedded_signature`, acrescentar em `REQUISITOS_DE_EVIDENCIA` (pendente: conferir no passo 5, com o widget) |
| `communicate_events` `{signature_request: none, signature_reminder: none, document_signed: email}` | Aceito e devolvido igual no signatário |
| Cancelar envelope ativo | **Não existe no v3.** `PATCH status` só aceita `draft`/`running`; `DELETE` só em `draft` (403 fora disso). Abandono morre pelo `deadline_at` |
| Vencimento sem assinatura | O padrão é `deadline_partial_signature_action: closed`, que FECHA o envelope sem assinatura. O provedor manda `canceled` (aceito; `cancel`/`cancelled`/`void` são recusados) para `closed` significar assinado |
| Arquivos do documento | `data.links.files.original` (docx) antes de assinar; o assinado deve aparecer em `links.files.signed`, URL válida por ~5 min (`X-Amz-Expires=299`). A confirmar com o primeiro envelope assinado |
| Limite de requisições | 20 req / 10 s no sandbox. Criar um termo gasta 6 chamadas |

## Roteiro E2E (a executar no passo 5)

1. Conferir quais `auth` o widget aceita (ver tabela acima) e ajustar `REQUISITOS_DE_EVIDENCIA`.
2. iPad em dev, paciente sem termo: dados → widget → token no WhatsApp → assinatura na tela → webhook → `GET consents/{id}` = `SIGNED` → PDF no S3 com hash.
3. Mesmo número de novo: não pede o termo.
4. Menor de idade: responsável assina.
5. Dispensa pelo painel; na sessão seguinte pede de novo.
6. Assinado em papel pelo painel.
7. Webhook com HMAC errado → 401; repetido → 200 `repetido`.
8. `curl` de cada rota com `source .env`.
