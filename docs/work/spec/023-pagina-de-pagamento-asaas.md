# Spec — 023 Pagamento no balcão (Asaas)

> Gerado na fase **Spec** em 12/10/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/023-pagina-de-pagamento-asaas.md` (decisões da §8 fechadas)

---

## 1. Resumo

Três PRs, nesta ordem. **Fase 1, backend:** migrations, cifra da chave,
cliente do Asaas, regras de pagamento, cinco rotas públicas no roteador
existente, webhook, templates de WhatsApp, configuração do Asaas e código de
balcão no painel (API). **Fase 2, tablet:** a tela de balcão no
`booking-site`. **Fase 3, painel:** pagamento na agenda, "Enviar link",
alarme, piloto na Essência.

Invariantes que o código garante, não a instrução:
1. Valor nunca vem da tela: `pagamentos.cria_cobranca` lê `final_price_cents`
   do agendamento e confere com o `valorVisto` que a tela mandou (409 se diferiu).
2. Nunca duas cobranças abertas para o mesmo agendamento: `UNIQUE` parcial em
   `payments(appointment_id) WHERE status IN ('PENDING')` + cancelamento no
   Asaas antes de criar outra.
3. Webhook sempre responde 200 e é idempotente por `(asaas_payment_id, evento)`.
4. A chave de API do Asaas só existe cifrada no banco e em memória na Lambda.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/src/utils/cifra.py` | `cifra(texto) -> str`, `decifra(texto) -> str` com Fernet; chave em SSM `/${stage}/FERNET_KEY` (lida uma vez por container). Mesmo desenho de `infra/src/utils/encryption.py`, sem gerar chave sozinho: sem chave, levanta |
| `scheduler/src/services/asaas_client.py` | `AsaasClient(api_key, ambiente)`; métodos `cria_cliente`, `cria_cobranca`, `qr_do_pix`, `cancela_cobranca`, `consulta_cobranca`, `cria_webhook`, `lista_webhooks`; base `https://api-sandbox.asaas.com/v3` ou `https://api.asaas.com/v3`; header `access_token`; timeout 10 s; `AsaasError(status, codigo, mensagem)`; loga método, caminho, status e `id` da cobrança, nunca o corpo |
| `scheduler/src/services/pagamentos.py` | regras (ver §6) |
| `scheduler/src/services/balcao.py` | código de balcão: `gera()`, `hash()`, `confere(clinic, codigo)`, `emite_sessao(clinic_id)` / `valida_sessao(token)` (HMAC com `FERNET_KEY`, 12 h) |
| `scheduler/src/functions/public_booking/balcao_identificar.py` | `POST public/clinics/{clinicId}/balcao/identificar` |
| `scheduler/src/functions/public_booking/balcao_areas.py` | `PUT public/clinics/{clinicId}/balcao/appointments/{appointmentId}/areas` |
| `scheduler/src/functions/public_booking/balcao_pagamento.py` | `POST public/clinics/{clinicId}/balcao/appointments/{appointmentId}/payments` e `GET public/clinics/{clinicId}/balcao/payments/{paymentId}` |
| `scheduler/src/functions/public_booking/asaas_webhook.py` | `POST public/webhooks/asaas/{clinicId}` |
| `scheduler/src/functions/clinic/asaas_setup.py` | `POST clinics/{clinicId}/asaas/testar` e `POST clinics/{clinicId}/asaas/webhook` (1 Lambda nova com 2 rotas, ou rotas no `UpdateClinic` se o stack apertar) |
| `scheduler/tests/unit/dublagem_asaas.py` | `AsaasFalso` com roteiro (respostas gravadas do sandbox em `tests/unit/asaas_fixtures/*.json`) |
| `scheduler/tests/unit/test_pagamentos.py`, `test_asaas_webhook.py`, `test_balcao.py`, `test_cifra.py` | ver §7 |
| `booking-site/src/pages/Balcao.tsx` | a tela (fase 2) |
| `booking-site/src/components/balcao/*` | `CodigoDeBalcao`, `TecladoNumerico`, `ResumoDoDia`, `EscolhaDoMeio`, `PixNaTela`, `LinkEnviado`, `Confirmado` |
| `booking-site/src/services/balcao.service.ts`, `hooks/useBalcao.ts` | |
| `booking-site/src/pages/Balcao.test.tsx` | |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/scripts/setup_database.py` | `TABLES`: `scheduler.payments`; `MIGRATIONS`: colunas em `clinics` e `patients`, índices, `UNIQUE` parcial, CHECK de status |
| `scheduler/src/functions/public_booking/router.py` | 5 rotas novas |
| `scheduler/sls/functions/public_booking/interface.yml` | 5 `http` events; `iamRoleStatements` + `ssm:GetParameter` em `/${stage}/FERNET_KEY`; `lambda:InvokeFunction` no `Send` (ou chamar o provider direto, ver §6) |
| `scheduler/sls/functions/clinic/interface.yml` | `AsaasSetup` |
| `scheduler/serverless.yml` | `FERNET_KEY` **não** vai em env (lida do SSM em runtime, cifrada em repouso); `BOOKING_SITE_URL` já existe? Se não, criar (base do link de cartão não precisa: o link é a `invoiceUrl` do Asaas) |
| `scheduler/src/functions/clinic/update.py` | aceita `asaas_api_key` (cifra antes de gravar; vazio = remove), `asaas_environment`, `asaas_billing_types`, `codigo_de_balcao` (hash); nunca devolve a chave |
| `scheduler/src/functions/clinic/get.py` | remove `asaas_api_key_enc` e `codigo_de_balcao_hash` da resposta; adiciona `asaas_configurado: bool`, `asaas_chave_final: "...1234"`, `asaas_webhook_id` |
| `scheduler/src/services/template_service.py` | `PAYMENT_LINK`, `PAYMENT_CONFIRMED` (ver §6) |
| `scheduler/src/functions/appointment/list.py` | `LEFT JOIN LATERAL` na última cobrança: `payment_status`, `payment_billing_type`, `paid_at` (fase 3) |
| `scheduler/src/functions/appointment/update.py` ou novo `appointment/enviar_link.py` | "Enviar link de pagamento" (fase 3) reutiliza `pagamentos.cria_cobranca(..., meio="CARTAO")` |
| `booking-site/src/router.tsx` | rota `balcao` nas duas árvores |
| `frontend/src/pages/configuracoes/ConfiguracoesPage.tsx`, `types`, `services/clinic.service.ts` | seção "Pagamentos (Asaas)" e "Código de balcão" (fase 1, parte do painel) |
| `frontend/src/pages/agenda/*` | coluna e badge de pagamento; botão "Enviar link" (fase 3) |
| `CLAUDE.md` | tabela `payments` na lista do Postgres; segredo `FERNET_KEY` |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

**Fase 0 (André):** conta sandbox do Asaas; chave de API do sandbox; `FERNET_KEY`
em SSM dev e prod (`python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`);
`cryptography` no `requirements.txt` do scheduler (conferir se já está na layer).

**Fase 1, backend (um PR, commits nesta ordem):**
1. Migrations + `cifra.py` + `test_cifra`.
2. `asaas_client.py` + `dublagem_asaas` + fixtures gravadas à mão do sandbox
   (criar cliente, criar cobrança Pix, QR, cancelar, cobrança cartão).
3. `pagamentos.py` + `test_pagamentos` (puro, com `AsaasFalso` e `db` dublado).
4. `balcao.py` + `balcao_identificar` + `balcao_areas` + `test_balcao`.
5. `balcao_pagamento` (criar e consultar) + envio do link pelo provider.
6. `asaas_webhook` + `test_asaas_webhook`.
7. `clinic/update`, `clinic/get`, `asaas_setup`; painel: seção Asaas e código.
8. Rotas, `interface.yml`, deploy dev; registrar webhook do sandbox apontando
   para dev; teste manual: criar cobrança Pix pelo endpoint, pagar no sandbox,
   ver `PAYMENT_RECEIVED` chegar.

**Fase 2, tablet (um PR):** tela completa com `AsaasFalso` no Vitest; Vercel
preview; teste no tablet real em dev.

**Fase 3, painel e piloto (um PR):** agenda, "Enviar link", alarme; conta de
produção da Essência; piloto só com Pix na primeira semana; cartão depois.

---

## 6. Detalhes por arquivo

### `setup_database.py`

```sql
CREATE TABLE IF NOT EXISTS scheduler.payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
    appointment_id UUID REFERENCES scheduler.appointments(id),
    patient_id UUID REFERENCES scheduler.patients(id),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    billing_type VARCHAR(10) NOT NULL CHECK (billing_type IN ('PIX', 'CARTAO')),
    -- PENDING | PAID | CANCELLED | OVERDUE | REFUNDED
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING',
    origem VARCHAR(10) NOT NULL DEFAULT 'BALCAO',  -- BALCAO | PAINEL | SITE
    asaas_payment_id VARCHAR(40) UNIQUE,
    asaas_customer_id VARCHAR(40),
    invoice_url TEXT,
    pix_payload TEXT,
    pix_qr_base64 TEXT,
    due_date DATE NOT NULL,
    paid_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    ultimo_evento VARCHAR(40),
    raw_webhook JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_payments_appointment ON scheduler.payments(appointment_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_uma_aberta
    ON scheduler.payments(appointment_id) WHERE status = 'PENDING';
CREATE TABLE IF NOT EXISTS scheduler.payment_events (
    id BIGSERIAL PRIMARY KEY,
    asaas_payment_id VARCHAR(40) NOT NULL,
    evento VARCHAR(40) NOT NULL,
    asaas_event_id VARCHAR(60),
    recebido_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw JSONB,
    UNIQUE(asaas_payment_id, evento, asaas_event_id)
);
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS asaas_api_key_enc TEXT;
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS asaas_environment VARCHAR(10) NOT NULL DEFAULT 'sandbox';
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS asaas_billing_types TEXT[] NOT NULL DEFAULT '{PIX,CARTAO}';
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS asaas_webhook_id VARCHAR(60);
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS asaas_webhook_token_enc TEXT;
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS codigo_de_balcao_hash TEXT;
ALTER TABLE scheduler.patients ADD COLUMN IF NOT EXISTS asaas_customer_id VARCHAR(40);
CREATE UNIQUE INDEX IF NOT EXISTS uq_patients_clinic_cpf
    ON scheduler.patients(clinic_id, cpf) WHERE cpf IS NOT NULL AND deleted_at IS NULL;
```
Antes da migration em prod: `SELECT clinic_id, cpf, count(*) FROM scheduler.patients WHERE cpf IS NOT NULL AND deleted_at IS NULL GROUP BY 1,2 HAVING count(*) > 1` (tem que voltar vazio; se não, o André decide qual cadastro fica).

### `services/pagamentos.py` (puro, recebe `db`, `asaas`, `provider`, `agora`)

- `agendamento_de_hoje(db, clinic_id, cpf=None, phone=None) -> dict | None`:
  normaliza (`normaliza_cpf`, `normalize_phone` + `variantes_do_numero`);
  `SELECT` do agendamento `CONFIRMED` com `appointment_date = hoje` no fuso da
  clínica (`_fuso_da_clinica` do `AppointmentService`), com serviços, áreas
  (`appointment_service_areas`), `final_price_cents`, e a cobrança aberta se
  houver. Dois agendamentos no mesmo dia: devolve o mais próximo do horário.
- `atualiza_areas(db, appointment_id, pares) -> dict`: chama
  `AppointmentService.update_appointment_services` (o mesmo caminho da
  recepção; recalcula duração e `final_price_cents`, mantém o desconto da
  paciente); se existe cobrança `PENDING`, chama `cancela_cobranca` antes
  (a troca de áreas invalida a cobrança). Devolve o agendamento recalculado.
- `cria_cobranca(db, asaas, clinic, appointment, meio, valor_visto, origem) -> dict`:
  1. `appointment.final_price_cents != valor_visto` → `ValorMudou` (409).
  2. cobrança `PENDING` existente com mesmo meio e mesmo valor → devolve ela
     (idempotente: a tela pode repetir o clique).
  3. `PENDING` com meio ou valor diferente → `cancela_cobranca`.
  4. cliente no Asaas: `patients.asaas_customer_id` ou `asaas.cria_cliente(nome, cpf, telefone)`; grava o id.
  5. `asaas.cria_cobranca(customer, billingType='PIX' | 'CREDIT_CARD', value=reais, dueDate=hoje no fuso da clínica, externalReference=payment.id, description="Sessão {data} - {clínica}")`.
     - Pix: `asaas.qr_do_pix(id)` → `pix_payload`, `pix_qr_base64`.
     - Cartão: só `invoice_url`; `provider.send_text(phone, template PAYMENT_LINK)`; o retorno traz `telefone_mascarado`.
  6. `INSERT payments` (status `PENDING`, `due_date` = hoje). Transação: o
     INSERT falhou → cancela no Asaas (compensação), levanta.
- `cancela_cobranca(db, asaas, payment)`: `asaas.cancela_cobranca(id)` (DELETE
  `/v3/payments/{id}`; 404 lá é sucesso aqui), `status=CANCELLED`.
- `aplica_webhook(db, clinic, corpo) -> str`: lê `event`, `payment.id`,
  `payment.status`, `payment.externalReference`; grava em `payment_events`
  (`ON CONFLICT DO NOTHING`; se já existia, devolve `"repetido"`); mapeia
  `PAYMENT_RECEIVED`/`PAYMENT_CONFIRMED` → `PAID` (`paid_at`), `PAYMENT_OVERDUE`
  → `OVERDUE`, `PAYMENT_DELETED` → `CANCELLED`, `PAYMENT_REFUNDED` → `REFUNDED`;
  cobrança desconhecida → `"desconhecida"` e log; depois de `PAID`, manda
  `PAYMENT_CONFIRMED` por WhatsApp (uma vez: só na transição).
- `status_para_a_tela(payment) -> dict`: `status`, `billing_type`,
  `amount_cents`, `pix_payload`, `pix_qr_base64`, `telefone_mascarado`,
  `paid_at`.

### `services/balcao.py`
- `gera() -> str` 6 dígitos (`secrets`); `hash(codigo)` = `hashlib.sha256(codigo + clinic_id)`; `confere(clinic_row, codigo)` em tempo constante.
- `emite_sessao(clinic_id, agora)` → token `base64(clinic_id|exp|hmac)` com 12 h; `valida_sessao(token, clinic_id, agora)`.
- Tentativas: 5 erros em 10 min por `clinic_id` bloqueiam por 15 min (contador na tabela `booking-otp-codes` do DynamoDB, que já tem TTL; sem tabela nova).

### Handlers públicos (`public_booking/balcao_*.py`)
- Todos exigem `x-api-key` pública (como os demais) **e** o header
  `x-balcao-token` válido, exceto `identificar` quando vem com `codigo`
  (é ele que emite o token). 401 sem token; 403 token de outra clínica.
- `identificar`: body `{codigo?, cpf?, phone?}`; com `codigo` → `{token}`;
  com `token` + `cpf|phone` → `{appointment, payment?}` ou 404 `SEM_SESSAO_HOJE`
  / 404 `NAO_ENCONTRADA`. Nunca devolve o telefone: só `telefone_mascarado`.
- `areas`: body `{serviceAreaPairs}` → `{appointment}` recalculado.
- `pagamento` POST: `{billingType, valorVisto}` → `{payment}`; 409 `VALOR_MUDOU`
  com o agendamento atual no corpo; 422 se a clínica não tem Asaas ou o meio
  não está habilitado. GET: `{payment}`.
- Clínica sem `asaas_api_key_enc` → 422 `PAGAMENTO_INDISPONIVEL` em todas as
  rotas de pagamento (a tela mostra a mensagem).

### `public_booking/asaas_webhook.py`
- Sem `x-api-key`. Lê `asaas-access-token`; compara com
  `decifra(clinic.asaas_webhook_token_enc)` em tempo constante; diferente →
  401 (e **esse** 401 é intencional: token errado não é "falha nossa").
- Com token certo: `try: pagamentos.aplica_webhook(...) except Exception: log
  [AsaasWebhook] erro + grava o corpo cru em payment_events com evento
  'ERRO_PROCESSAMENTO'`; **sempre** `return 200 {"received": true}`.
- Processamento síncrono: é um UPDATE e, no máximo, um envio de WhatsApp;
  cabe nos 30 s. Se o envio do WhatsApp falhar, não falha o webhook.

### `clinic/asaas_setup.py` (painel, `require_api_key`)
- `testar`: `GET /v3/myAccount` com a chave da clínica; devolve nome da conta e ambiente.
- `webhook`: gera `authToken` (`secrets.token_urlsafe(32)`), cifra e grava;
  `POST /v3/webhooks` com `url = {API_BASE}/public/webhooks/asaas/{clinic_id}`,
  `events = [PAYMENT_RECEIVED, PAYMENT_CONFIRMED, PAYMENT_OVERDUE, PAYMENT_DELETED, PAYMENT_REFUNDED]`,
  `sendType = SEQUENTIALLY`, `enabled = true`; grava `asaas_webhook_id`.
  Se já existe `asaas_webhook_id`, `PUT` em vez de `POST`.

### Envio de WhatsApp
`pagamentos` recebe um `provider` (`get_provider(clinic)`, o mesmo do `Send`)
e chama `send_text`. Não invoca a Lambda `Send`: o balcão não passa pela porta
de atendimento (é a clínica falando com quem está na frente dela), e o
`Send` existe para a atendente. O envio é rastreado no `MessageTracker` como
OUTBOUND com `metadata.origem = "balcao"`.

### `template_service.py`
```
PAYMENT_LINK: "Oi, {{patient_name}}! Aqui está o link para pagar sua sessão de hoje ({{amount}}): {{invoice_url}}\nVocê pode pagar no crédito ou no débito. Qualquer dúvida, é só chamar 😊"
PAYMENT_CONFIRMED: "Pagamento confirmado, {{patient_name}}! {{amount}} recebido. Obrigada 💛"
```

### `booking-site` (fase 2)
- Rota `balcao` nas duas árvores do `router.tsx`. Layout próprio
  (`BalcaoLayout`): sem cabeçalho do site, fonte grande, botões de 64 px,
  teclado numérico na tela (o tablet não tem teclado), sem `localStorage`
  além do token de balcão (12 h) e do `clinicId`.
- Máquina de estados: `codigo → identificar → resumo → meio → (pix | link) →
  confirmado`. `confirmado` volta para `identificar` em 20 s ou no toque.
  Inatividade de 90 s em qualquer tela volta para `identificar` (a próxima
  paciente não pode ver a anterior).
- `pix`: QR (`<img src="data:image/png;base64,...">`) + copia-e-cola +
  polling `GET payments/{id}` a cada 3 s; `PAID` → `confirmado`.
- `link`: "Enviamos o link para (11) 9****-1234. Pague pelo celular."; polling
  igual; botão "Reenviar" (chama POST de novo; idempotente).
- Mudar áreas depois de `pix`/`link`: volta ao `resumo`, e o próximo POST
  cancela e recria (a tela mostra "o valor mudou, gerando novo QR").
- Erros: 422 `PAGAMENTO_INDISPONIVEL` → "Pagamento pelo tablet indisponível;
  chame a recepção"; 409 → recarrega o resumo.

### Painel (fases 1 e 3)
- Configurações → "Pagamentos (Asaas)": chave (campo senha; mostra
  "configurada, final 1234"), ambiente, meios, "Testar conexão", "Registrar
  webhook" (mostra o id). "Código de balcão": "Gerar novo" mostra o código uma
  vez (não é mais recuperável; só regerar).
- Agenda do dia: badge `pago` / `aguardando` / `vencido` / `sem cobrança`;
  ficha: cobrança atual e "Enviar link de pagamento".

---

## 7. Testes

- `test_cifra`: ida e volta; sem chave levanta; valor cifrado não contém o texto.
- `test_pagamentos` (com `AsaasFalso` e `db` dublado como `TabelaFalsa`):
  valor diferente → 409; mesma cobrança repetida → mesma linha; troca de meio
  cancela a anterior; troca de áreas cancela; INSERT falho cancela no Asaas;
  Pix traz QR; cartão manda o template no telefone certo e devolve mascarado;
  `aplica_webhook`: cada evento → status; repetido → "repetido" sem segundo
  WhatsApp; desconhecida → "desconhecida"; `PAID` manda `PAYMENT_CONFIRMED`
  uma vez.
- `test_balcao`: código certo/errado; 5 erros bloqueiam; token de outra
  clínica → 403; token vencido → 401; `agendamento_de_hoje` por CPF com
  máscara, por telefone com variantes do nono dígito, sem sessão hoje, dois
  no mesmo dia.
- `test_asaas_webhook`: token errado → 401; certo com exceção interna → 200 e
  evento `ERRO_PROCESSAMENTO`; corpo de cada evento real do sandbox (fixtures).
- `test_nomes_resolvem` e `test_retencao` já cobrem o que é genérico.
- `Balcao.test.tsx`: cada transição, o polling virando `PAID`, inatividade,
  mudança de áreas invalidando o QR.
- Fixtures: respostas reais do sandbox (criar cliente, cobrança Pix, QR,
  cobrança cartão, DELETE, os cinco eventos de webhook), com ids trocados.

---

## 8. Custo de recursos no stack

5 rotas × (Resource + Method + OPTIONS) ≈ 15, menos o que compartilha
`public/clinics/{clinicId}` já existente; `AsaasSetup` ≈ 8. Estimativa:
435 → ~455 de 500. Se passar de 470, `asaas_setup` vira duas rotas na
`UpdateClinic` em vez de Lambda nova.
