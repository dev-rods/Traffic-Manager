# PRD — 023 Página de pagamento (Asaas)

> Gerado na fase **Research** em 12/10/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Uma página pública de pagamento, no mesmo molde do `booking-site`
(`agendar.draclaradourado.com.br`), onde a paciente da Essência paga a sessão
por **Pix, boleto, cartão de crédito ou débito**, com o dinheiro caindo na
conta da clínica e o agendamento marcado como pago sem ninguém conferir
extrato. Provedor: **Asaas**.

A página serve dois caminhos: o fim do agendamento online ("Agendamento
confirmado, pague agora") e um link avulso que a atendente ou o bot mandam
pelo WhatsApp.

---

## 2. Contexto

### O que já existe
- `booking-site`: Vite + React, multi-tenant por `clinic_id` no path, domínio
  próprio por clínica (PRD 021), wizard `cart → areas → professional →
  schedule → customer → success`. Fala com o backend por `x-api-key` pública.
- Backend: Lambda única `PublicBooking` com roteador por `event.resource` (9
  rotas `public/*`). Stack em 435/500 recursos (dev e prod); cada rota nova
  custa 2 a 3 recursos, cada Lambda nova 7 a 8.
- `appointments` já tem `original_price_cents`, `final_price_cents`,
  `discount_pct`, `is_first_visit`. Não há nada de pagamento no banco, no
  painel, no site nem no bot. O FAQ `PAYMENT_METHODS` responde "como paga"
  em texto.
- Segredos por clínica hoje: `zapi_instance_token` em coluna texto. O
  `infra/` guarda credenciais do Google Ads com Fernet; o `scheduler/` ainda
  não cifra nada.

### O que o Asaas oferece (docs.asaas.com, lido em 12/10/2026)

| meio | como | observação |
|---|---|---|
| Pix | `POST /v3/payments` com `billingType=PIX`; `GET /v3/payments/{id}/pixQrCode` devolve QR (base64) e copia-e-cola | dá para render na nossa página |
| Boleto | `billingType=BOLETO`; resposta traz `bankSlipUrl` (PDF) e `invoiceUrl` | linha digitável e PDF |
| Cartão de crédito | `billingType=CREDIT_CARD` **com** os dados do cartão no corpo (`creditCard`, `creditCardHolderInfo`, `remoteIp` do pagador) | o número do cartão passa pela nossa Lambda; tokenização (`/v3/creditCard/tokenizeCreditCard`) só em produção com liberação do gerente de conta |
| Cartão de débito | **não existe via API**: a pessoa paga na página do próprio Asaas (`invoiceUrl` de uma cobrança `CREDIT_CARD` ou `UNDEFINED`) | única forma de aceitar débito |
| Checkout hospedado (`POST /v3/checkouts`) | página do Asaas com `callback.successUrl`; suporta só `PIX` e `CREDIT_CARD` | sem boleto |
| Confirmação | **só por webhook** (`PAYMENT_CONFIRMED`, `PAYMENT_RECEIVED`, `PAYMENT_OVERDUE`, `PAYMENT_REFUNDED`, `PAYMENT_DELETED`); entrega "ao menos uma vez"; só HTTP 200 conta; 15 falhas seguidas pausam a fila | redirect de navegador não é confirmação financeira |
| Webhook | criado pela API com `authToken` obrigatório desde 02/2026; chega no header `asaas-access-token` | um webhook por conta Asaas |
| Sandbox | `https://api-sandbox.asaas.com/v3`, conta separada | tokenização liberada no sandbox |
| Taxas padrão | Pix R$ 1,99; boleto R$ 1,99; débito R$ 0,35 + 1,89%; crédito à vista R$ 0,49 + 2,99% | negociável por conta |

### Decisão de arquitetura: onde o cartão é digitado

Três caminhos, e a diferença é quem toca no número do cartão:

1. **Tudo na nossa página** (cartão pela API): melhor UX, mas o cartão
   atravessa nossa Lambda (escopo PCI maior, logs, `remoteIp` do pagador a
   capturar) e débito não existe por esse caminho de qualquer jeito.
2. **Checkout hospedado do Asaas**: zero cartão em nossas mãos, mas sem
   boleto e sem débito explícito.
3. **Híbrido (recomendado):** nossa página escolhe o meio e trata **Pix e
   boleto em casa** (QR, copia-e-cola, PDF, status ao vivo); para **crédito e
   débito** abre a `invoiceUrl` da cobrança no Asaas, onde a pessoa digita o
   cartão. Nenhum dado de cartão passa por nós, débito funciona, boleto
   funciona, e a confirmação de todos os quatro chega pelo mesmo webhook.
   Cartão dentro da nossa página fica como fase opcional, depois que o Asaas
   liberar tokenização em produção.

### Decisão de produto: pagar confirma ou pagar é depois?

- **Pagar depois (recomendado para começar):** o agendamento continua sendo
  confirmado como hoje; o pagamento é uma cobrança ligada a ele, com prazo.
  A tela de sucesso ganha "Pagar agora"; o WhatsApp de confirmação ganha o
  link. A clínica vê no painel quem pagou. Nada de reserva de horário por
  minutos, nada de expirar agendamento.
- **Pagar para confirmar:** horário reservado por N minutos até o webhook
  chegar; exige expiração de reserva, Pix com `minutesToExpire`, tratamento
  de boleto (que leva dias) e um estado novo de agendamento. Fica para uma
  fase posterior, se a clínica quiser.

### Decisão: de quem é a conta Asaas

O dinheiro cai na **conta Asaas da própria clínica**. Ela cria a conta, gera
a chave de API e cola no painel. Nós não intermediamos valores, não há split
nem subconta. Vale para a Essência e para qualquer clínica futura sem código
novo. (Subcontas white-label do Asaas existem e ficariam para um modelo de
plataforma, fora deste PRD.)

---

## 3. Escopo

### Dentro do escopo
- **Configuração por clínica, no painel:** chave de API do Asaas (cifrada),
  ambiente (`sandbox`/`producao`), meios habilitados, dias de vencimento do
  boleto, texto do "Pagar agora". Botão "Testar conexão" e "Registrar
  webhook" (cria o webhook no Asaas pela API, com `authToken` nosso).
- **Tabela `scheduler.payments`:** uma cobrança por linha, ligada ao
  agendamento (ou avulsa), com `asaas_payment_id`, `billing_type`, `status`,
  `amount_cents`, `invoice_url`, `bank_slip_url`, `pix_payload`, `due_date`,
  `paid_at`, `external_reference` (= nosso id), `raw` do último webhook.
  `patients.asaas_customer_id` para não recriar cliente no Asaas.
- **Serviço `asaas_client`:** cliente HTTP fino (customers, payments,
  pixQrCode, webhooks, refund), com dublagem para testes; nunca loga corpo
  de resposta inteiro.
- **Endpoints públicos (no roteador `PublicBooking`):**
  - `POST /public/clinics/{clinicId}/payments` cria a cobrança de um
    agendamento (`appointmentId` + `billingType`); valor vem do
    `final_price_cents` do agendamento, nunca do cliente.
  - `GET /public/clinics/{clinicId}/payments/{paymentId}` status + dados
    para a tela (QR, copia-e-cola, PDF, `invoiceUrl`).
  - `POST /public/webhooks/asaas/{clinicId}` recebe eventos; valida
    `asaas-access-token` contra o token da clínica; idempotente por
    `(asaas_payment_id, event)`; responde 200 em menos de 1 s e processa o
    resto na mesma Lambda (um `UPDATE`); sem `x-api-key`.
- **Página de pagamento no `booking-site`:** rota `/:clinicId/pagar/:paymentId`
  (também sob domínio próprio). Escolha do meio; Pix com QR e copia-e-cola e
  status ao vivo (polling de 3 s até `RECEIVED`/`CONFIRMED`); boleto com
  linha digitável, PDF e vencimento; crédito e débito com botão que abre a
  `invoiceUrl`; tela "Pagamento confirmado" com o resumo do agendamento.
- **Integração com o agendamento online:** a tela de sucesso do wizard ganha
  "Pagar agora"; o template `BOOKED` do WhatsApp ganha o link quando a
  clínica tem Asaas configurado.
- **Painel:** status de pagamento na agenda e na ficha do agendamento;
  "Enviar link de pagamento" pelo WhatsApp (usa o `Send` existente).
- **Lembrete de boleto/Pix vencendo:** fora. Boleto vencido vira
  `PAYMENT_OVERDUE` e a atendente vê no painel.

### Fora do escopo
- Cartão digitado na nossa página (tokenização): fase posterior, depende de
  liberação do Asaas.
- Pagar para confirmar (reserva de horário).
- Split, subcontas, antecipação, assinatura/recorrência.
- Estorno pelo painel (o Asaas faz pelo próprio painel; a gente só reflete
  `PAYMENT_REFUNDED`).
- Nota fiscal.
- Pagamento pelo bot de WhatsApp (tool `gerar_link_de_pagamento`): PRD
  próprio depois que a página existir; o bot já responde "como paga" pelo FAQ.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/scripts/setup_database.py` | modificar | tabela `payments`; colunas em `clinics` (`asaas_api_key_enc`, `asaas_environment`, `asaas_webhook_token`, `asaas_billing_types`, `boleto_due_days`, `asaas_webhook_id`); `patients.asaas_customer_id` |
| `scheduler/src/utils/cifra.py` | criar | Fernet com chave em SSM `/${stage}/FERNET_KEY` (mesmo padrão do `infra/`) |
| `scheduler/src/services/asaas_client.py` | criar | HTTP para o Asaas (sandbox/prod pela config da clínica) |
| `scheduler/src/services/pagamentos.py` | criar | regras: criar cobrança do agendamento, aplicar webhook, status derivado |
| `scheduler/src/functions/public_booking/create_payment.py`, `get_payment.py`, `asaas_webhook.py` | criar | handlers |
| `scheduler/src/functions/public_booking/router.py` + `sls/functions/public_booking/interface.yml` | modificar | 3 rotas novas (≈ 8 recursos no stack) |
| `scheduler/src/functions/clinic/update.py`, `get.py` | modificar | campos Asaas (chave só de escrita; leitura devolve "configurada: sim/não" e os 4 últimos dígitos) |
| `scheduler/src/functions/clinic/asaas_setup.py` | criar | "Testar conexão" e "Registrar webhook" (uma rota nova no router de clínica, se houver; senão 1 Lambda) |
| `scheduler/src/functions/public_booking/create_appointment.py` | modificar | se a clínica tem Asaas, devolve `paymentUrl` e inclui no WhatsApp |
| `scheduler/src/services/template_service.py` | modificar | `BOOKED` com `{{payment_url}}` opcional |
| `booking-site/src/pages/Pay.tsx`, `router.tsx`, `services/payment.service.ts`, `types` | criar/modificar | a página |
| `booking-site/src/pages/Booking.tsx` | modificar | "Pagar agora" no sucesso |
| `frontend/src/pages/configuracoes/...` | modificar | seção "Pagamentos (Asaas)" |
| `frontend/src/pages/agenda/...` | modificar | status e botão "Enviar link" |
| `scheduler/tests/unit/test_pagamentos.py`, `test_asaas_webhook.py`, `booking-site/src/pages/Pay.test.tsx` | criar | |

---

## 5. Dependências e riscos

- **Do lado do Asaas (quem faz: a clínica, com a gente junto):**
  1. Conta PJ da Essência aprovada (KYC do Asaas).
  2. Meios de recebimento habilitados na conta: Pix (chave Pix na conta
     Asaas), boleto, cartão de crédito e débito (cartão passa por análise do
     Asaas; débito vem junto com a habilitação de cartão na fatura).
  3. Chave de API gerada em *Integrações → Chaves de API* e colada no painel.
  4. Webhook registrado (nós fazemos pela API, com nosso `authToken`),
     eventos de cobrança ligados, fila ativa.
  5. Uma **conta sandbox** separada para dev (chave própria).
- **Do nosso lado:** `FERNET_KEY` em SSM (dev e prod); 3 rotas no stack
  (435 → ~443 de 500); domínio da página = o mesmo do `booking-site`.
- **Riscos:**
  - *Webhook sem 200 por 15 vezes pausa a fila* e nenhum pagamento mais
    confirma até alguém reativar. O handler tem que responder 200 mesmo com
    erro interno (loga e grava o evento cru para reprocessar), e um alarme
    conta `[AsaasWebhook] erro`.
  - *Entrega duplicada*: idempotência por `(asaas_payment_id, event)`.
  - *Chave de API vazando*: cifrada em repouso, nunca devolvida pela API,
    nunca logada; a `x-api-key` pública do site não dá acesso a ela.
  - *Valor manipulado pelo cliente*: o endpoint público nunca aceita valor;
    lê do agendamento.
  - *Débito só na página do Asaas*: a pessoa sai do nosso domínio. A tela
    avisa e, ao voltar, o status já reflete o webhook.
  - *Boleto leva até 3 dias úteis*: status `PENDING` até lá; o painel mostra
    "aguardando compensação".
  - *Reembolso e cancelamento*: cancelar agendamento pago não estorna sozinho
    (decisão da clínica); o painel mostra "pago, cancelado" para ela agir.

---

## 6. Critérios de aceite

- [ ] Na Essência em sandbox: agendar pelo site, clicar "Pagar agora", pagar
      por Pix (QR do sandbox), e ver a tela virar "Pagamento confirmado" sem
      recarregar; o agendamento aparece pago no painel.
- [ ] Boleto: PDF e linha digitável na página; `PAYMENT_RECEIVED` simulado
      no sandbox marca pago.
- [ ] Crédito e débito: botão abre a fatura do Asaas; ao pagar, webhook
      marca pago e a página, ao voltar, mostra confirmado.
- [ ] Webhook com token errado → 401 e nada gravado; evento repetido → 200 e
      nada muda; evento de cobrança desconhecida → 200 e log.
- [ ] Chave de API não aparece em nenhuma resposta nem log.
- [ ] Link de pagamento sai no WhatsApp de confirmação só quando a clínica
      tem Asaas configurado; sem Asaas, nada muda no fluxo de hoje.
- [ ] Clínica sem Asaas: página `/pagar` responde "pagamento indisponível".

---

## 7. Fases propostas

| fase | entrega | depende de |
|---|---|---|
| 0 | contas Asaas (sandbox nossa, produção da Essência), `FERNET_KEY`, decisões abaixo | André / clínica |
| 1 | backend: tabela, cifra, `asaas_client` (com gravações do sandbox como fixtures), `pagamentos`, 3 endpoints, webhook, testes | 0 |
| 2 | `booking-site`: página `/pagar`, serviço, testes; deploy Vercel | 1 em dev |
| 3 | integração: "Pagar agora" no sucesso, link no `BOOKED`, painel (config Asaas, status na agenda, "Enviar link") | 2 |
| 4 | opcional: cartão dentro da página com tokenização; pagar para confirmar | liberação do Asaas / decisão |

---

## 8. Decisões pedidas ao André

1. Híbrido (Pix e boleto em casa; crédito e débito na fatura do Asaas) para começar? Ou esperar a tokenização e fazer cartão em casa desde o início?
2. Pagar depois (recomendado) ou pagar para confirmar?
3. Vencimento do boleto e do Pix: proposta 3 dias para boleto, Pix sem vencimento curto (a cobrança segue aberta até a data da sessão).
4. Conta Asaas da clínica (recomendado) ou nossa com repasse?
5. Pagamento parcial/sinal (ex.: 30% para reservar) entra agora ou nunca?

---

## 9. Referências

- Asaas: [Criar nova cobrança](https://docs.asaas.com/reference/criar-nova-cobranca), [Pix](https://docs.asaas.com/docs/cobrancas-via-pix), [Boleto](https://docs.asaas.com/docs/cobrancas-via-boleto), [Cartão de crédito](https://docs.asaas.com/docs/cobrancas-via-cartao-de-credito), [Checkout](https://docs.asaas.com/docs/introdu%C3%A7%C3%A3o-1), [Webhooks](https://docs.asaas.com/docs/sobre-os-webhooks), [Eventos de cobrança](https://docs.asaas.com/docs/payment-events), [Fila pausada](https://docs.asaas.com/docs/webhooks-queue-paused), [Token obrigatório](https://docs.asaas.com/changelog/obrigatoriedade-e-auto-geração-de-tokens-para-webhooks), [Preços](https://www.asaas.com/precos-e-taxas).
- PRD 009 (booking-site), PRD 021 (domínio próprio), PRD 020 §4.3 (FAQ `PAYMENT_METHODS`).

---

## Status (preencher após conclusão)

- [ ] Pendente (aguardando as decisões da §8)
- [ ] Spec gerada: `spec/023-pagina-de-pagamento-asaas.md`
- [ ] Implementado em:
- [ ] Registrado em `TASKS_LOG.md`
