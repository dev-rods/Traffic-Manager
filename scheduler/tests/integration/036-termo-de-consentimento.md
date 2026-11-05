# 036 - Termo de consentimento (TCLE) assinado no check-in

Roteiro E2E em dev (ClickSign sandbox) e casos curl. Spec:
`docs/work/spec/036-termo-de-consentimento.md`. Postman:
`tests/postman/036-termo-de-consentimento.postman_requests.json`.

## O que está no ar em dev (04/11/2026)

- Stack `clinic-scheduler-infra-dev` em **482/500** recursos (eram 466).
- Bucket privado `clinic-scheduler-infra-dev-documentos` (criptografia AES256,
  versionado, `Retain`).
- Rotas novas: `POST public/clicksign/webhook`, coringa
  `clinics/{clinicId}/consents/{proxy+}` (Lambda `Consentimento`),
  `PUT clinics/{clinicId}/professionals/{professionalId}` (`UpdateProfessional`)
  e as sub-rotas `consent`, `consents/{id}`, `consents/{id}/simulate` na
  coringa do check-in.
- SSM em dev: `CLICKSIGN_API_KEY` (sandbox), `CLICKSIGN_TCLE_TEMPLATE_KEY`,
  `TCLE_VERSION`. **Falta** `/dev/CLICKSIGN_WEBHOOK_SECRET` (ver "Antes do
  E2E").

## Achados no sandbox da ClickSign (03/11/2026)

Conferidos com o provedor real (`src/providers/clicksign_provider.py`) contra
`sandbox.clicksign.com`, modelo `ecd991c8-3d71-40f2-ac7c-1cae7aac4810`:

| Ponto | Resultado |
|---|---|
| Criar modelo pela API (`POST /api/v3/templates`) | OK com `content_base64` em data URI; o atributo `color` é recusado (400), omitir |
| Conta sem "e-mail do usuário da API" (Configurações → API) | Toda chamada responde 403 `forbidden`. A conta de produção precisa do mesmo ajuste |
| Sequência envelope → documento do modelo → signatário → requisitos → ativar | Aceita de ponta a ponta. Envelope `a8bd5667-...` criado como prova e deixado vencer |
| Requisitos `agree/sign` + `provide_evidence` `whatsapp` + `handwritten` | Aceitos. Se o widget embedded exigir `embedded_signature`, acrescentar em `REQUISITOS_DE_EVIDENCIA` (pendente: conferir no E2E, com o widget) |
| `communicate_events` `{signature_request: none, signature_reminder: none, document_signed: email}` | Aceito e devolvido igual no signatário |
| Cancelar envelope ativo | **Não existe no v3.** `PATCH status` só aceita `draft`/`running`; `DELETE` só em `draft` (403 fora disso). Abandono morre pelo `deadline_at` (2 dias) |
| Vencimento sem assinatura | O padrão é `deadline_partial_signature_action: closed`, que FECHA o envelope sem assinatura. O provedor manda `canceled` (aceito; `cancel`/`cancelled`/`void` são recusados) para `closed` significar assinado |
| Arquivos do documento | `data.links.files.original` (docx) antes de assinar; o assinado deve aparecer em `links.files.signed`, URL válida por ~5 min (`X-Amz-Expires=299`). A confirmar com o primeiro envelope assinado |
| Limite de requisições | 20 req / 10 s no sandbox. Criar um termo gasta 6 chamadas |

## Achados do E2E de 04-05/11/2026 (widget)

Reproduzido num Chromium headless (`playwright`), carregando o script
embedded com o `id` do signatário e `origin` do iPad, igual ao
`ConsentSignStep`:

| Ponto | Resultado |
|---|---|
| Chave do widget | É o `id` do signatário (v3), como o backend devolve em `signerId` |
| `whatsapp` + `handwritten` (decisão 2 do PRD) | **Funciona.** O widget renderiza o termo com os dados, "0/1 Assinaturas" e o botão "Assinar"; os passos são `federal_data, agree, handwritten, whatsapp` |
| `embedded_signature` | A doc "Assinatura Incorporada" manda criá-lo, mas o widget quebra com "ERRO 500" dentro do iframe logo após `/steps` (`federal_data, agree, embedded_signature`), e a API recusa ativar o envelope se ele vier junto de outra evidência (422 "assinatura incorporada e adicional"). Descartado |
| "Imagem do termo quebrada" no 1º teste no iPad | O documento gerado do modelo é processado DEPOIS de criado: `modified` muda ~9 s após `created` (medido duas vezes). O iPad abriu o widget antes. `cria_termo` agora espera o documento processado (até 20 s, `ESPERA_DOCUMENTO_S`) antes de devolver o termo |
| Erro 500 na tela "Assine o termo" no 2º teste | Era o `embedded_signature` acima; o nosso backend respondeu 200 em tudo (conferido com token forjado em dev) |
| Envelopes de sonda | `1992f6aa` (1º do iPad, funciona), `880c9a30` e `20044ee4` (embedded, quebram), `beca0835`/termo atual (API, funciona). Todos vencem sozinhos em até 2 dias |

Como repetir a sondagem: `scratchpad/sonda_widget.py <signerId>` e
`e2e_termo.py` desta sessão (cria o termo pela API com token forjado a
partir de `BOOKING_VERIFICATION_SECRET` e abre o widget headless).

## Pendências a confirmar no E2E (o código já lê os dois jeitos)

3. **Formato do webhook v3.** `aplica_evento` lê `event.name` (ou `event.type`,
   ou `event` string) e procura `document.key|id` e `envelope.key|id` em
   qualquer nível do payload. Nomes aceitos como "fechado": `auto_close`,
   `close`, `closed`, `document_closed`, `envelope_closed`, `envelope.closed`,
   `document.closed`. Conferir o nome real no primeiro evento (log
   `[ClicksignWebhook] <event_id>: <resultado>`) e, se vier outro, acrescentar
   em `EVENTOS_FECHADO`.
4. **`links.files.signed`** de verdade no documento assinado.

## Antes do E2E (uma vez, pelo André)

1. Na conta sandbox da ClickSign, cadastrar o webhook apontando para
   `https://<api-dev>/dev/public/clicksign/webhook` e copiar o segredo (HMAC).
2. `MSYS_NO_PATHCONV=1 aws ssm put-parameter --name /dev/CLICKSIGN_WEBHOOK_SECRET --type SecureString --value "<segredo>" --profile dev-andre`
3. `cd scheduler && npx serverless deploy --stage dev --aws-profile dev-andre`
   (o segredo entra como variável de ambiente no deploy).
4. Publicar o iPad: `cd checkin && npx vercel deploy --prod --yes --scope team_ZLFt6HlpGbYXZsEloIbOVq96`
   (projeto `checkin-dev`).
5. No painel de dev, em Configurações → "Responsável técnica e termo":
   escolher a profissional, preencher o registro no conselho e a cidade.

## Roteiro E2E

1. **iPad em dev, paciente sem termo**: celular → código → confirmar →
   tela "Termo de consentimento" (dados pré-preenchidos, CPF mascarado) →
   "Continuar para a assinatura" → widget carrega (confere pendências 1 e 2)
   → código no WhatsApp → assinatura manuscrita → o iPad segue sozinho para o
   pagamento (polling) → no banco `patient_consents.status = SIGNED`,
   `pdf_s3_key` e `pdf_sha256` preenchidos → painel, Documentos → aba "Termo de
   consentimento" → "Abrir PDF" abre o assinado com o log de auditoria.
2. **Webhook**: no CloudWatch da `PublicBooking`, o evento chegou
   (`[ClicksignWebhook] ...: SIGNED` ou `ignorado: já SIGNED` se o polling
   fechou antes). Em `consent_webhook_events` há uma linha.
3. **Mesmo número de novo**: confirmar → vai direto ao pagamento (não pede).
4. **Menor de idade**: paciente com nascimento < 18 na data da sessão → bloco
   "Responsável legal" obrigatório → o widget carrega para o responsável (nome e
   celular dele) → `signer_kind = GUARDIAN`, `patient_guardians` preenchida.
5. **Dispensa**: outra paciente sem termo; no painel, popover do agendamento →
   "Dispensar nesta sessão" (motivo) → selo "TERMO" some; no iPad, confirmar
   não pede o termo; criar outro agendamento para ela → pede de novo.
6. **Papel**: "Assinado em papel" com data → aba do termo mostra "EM PAPEL",
   "Abrir PDF" desabilitado; iPad não pede.
7. **Webhook com HMAC errado** → 401; repetido com o mesmo corpo → 200
   `repetido`.
8. **Abandono**: começar o termo e sair; voltar em menos de 24 h → o mesmo
   envelope é reaproveitado (um só na ClickSign); vencido (2 dias) → o status
   vira `EXPIRED` e um novo é criado na próxima tentativa.
9. **Clínica sem responsável**: limpar o select nas Configurações → o iPad
   mostra "A clínica ainda não configurou o termo. Chame a recepção.", sem
   botão de pular.

## Casos curl

```bash
cd scheduler && source .env
API=https://<api-dev>/dev
CLINIC=<clinic_id>

# Painel: termos da paciente
curl -s -H "x-api-key: $API_KEY" "$API/clinics/$CLINIC/consents/patients/<patientId>"

# Painel: dispensar nesta sessão
curl -s -X POST -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"reason":"SEM_CELULAR"}' "$API/clinics/$CLINIC/consents/appointments/<appointmentId>/waive"

# Painel: assinado em papel
curl -s -X POST -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"signedAt":"2026-11-01"}' "$API/clinics/$CLINIC/consents/patients/<patientId>/paper"

# Painel: URL do PDF (5 min)
curl -s -H "x-api-key: $API_KEY" "$API/clinics/$CLINIC/consents/<consentId>/pdf-url"

# Admin: responsável técnica e cidade; registro da profissional
curl -s -X PUT -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"responsible_professional_id":"<professionalId>","cidade":"São Paulo"}' "$API/clinics/$CLINIC"
curl -s -X PUT -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"registro_conselho":"CRBM 12345"}' "$API/clinics/$CLINIC/professionals/<professionalId>"

# iPad (chave do booking + token do código de WhatsApp)
curl -s -X POST -H "x-api-key: $BOOKING_API_KEY" -H "Content-Type: application/json" \
  -d '{"phone":"5511999990000","token":"<token>","fullName":"Ana Souza","cpf":null,"birthDate":"1990-05-10","email":"ana@exemplo.com","imageAuthorized":true,"guardian":null}' \
  "$API/public/clinics/$CLINIC/checkin/appointments/<appointmentId>/consent"
curl -s -H "x-api-key: $BOOKING_API_KEY" "$API/public/clinics/$CLINIC/checkin/consents/<consentId>?phone=5511999990000&token=<token>"

# Webhook: HMAC do corpo cru
BODY='{"event":{"name":"auto_close","occurred_at":"2026-11-04T15:00:00Z"},"document":{"key":"<doc>"}}'
HMAC=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$CLICKSIGN_WEBHOOK_SECRET" | awk '{print $2}')
curl -s -X POST -H "Content-Type: application/json" -H "Content-Hmac: sha256=$HMAC" -d "$BODY" "$API/public/clicksign/webhook"
```

## Testes automatizados

- `tests/unit/test_consentimento.py` (36): gatilho, prefill, criação,
  menor/responsável, cadastro só em campo vazio, reaproveitamento e corrida,
  fechamento com S3, webhook, painel.
- `tests/unit/test_clicksign_provider.py` (25): payloads JSON:API, rollback,
  status, downloads, cancelamento.
- `tests/unit/test_clicksign_webhook.py` (13): HMAC, base64, corpo inválido,
  500 para reenvio, rota e variáveis de ambiente.
- `tests/unit/test_consent_router.py` (17): permissão por rota, corpo,
  `UpdateProfessional`, validação do `UpdateClinic`.
- `checkin`: 7 casos em `CheckinPage.test.tsx`; painel: `TermoDoAgendamento`,
  `TermoPendenteBadge`, `TermoDeConsentimento`, `ResponsavelTecnica`,
  `DocumentosPage`.
