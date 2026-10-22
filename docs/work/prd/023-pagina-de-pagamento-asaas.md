# PRD — 023 Pagamento no balcão e no site (Asaas)

> Gerado na fase **Research** em 12/10/2026; revisado no mesmo dia com a
> definição do André dos dois momentos de pagamento. Use como input para a
> fase Spec.

---

## 1. Objetivo

Receber o pagamento da sessão por **Pix, boleto, cartão de crédito ou débito**,
pelo **Asaas**, com o dinheiro na conta da clínica e o agendamento marcado como
pago sem ninguém conferir extrato. Dois momentos, nesta ordem de prioridade:

1. **No dia, no balcão (fluxo principal).** A paciente agendou pelo WhatsApp
   e chega na clínica. Num tablet na recepção ela digita o **CPF ou o
   telefone**, vê o agendamento de hoje, **confirma as áreas e o valor**,
   escolhe como pagar, e:
   - **Pix:** o tablet mostra o QR Code e a tela vira "pago" quando o Asaas
     confirmar;
   - **cartão (crédito ou débito):** o link de pagamento vai pelo WhatsApp do
     número cadastrado da paciente; ela paga no celular, na página do Asaas.
   - **Boleto fica fora por enquanto** (decisão do André, 12/10/2026): no
     balcão a pessoa sairia sem pagar. Volta a ser avaliado no fluxo 2.
2. **No site, na hora de agendar** (`agendar.draclaradourado.com.br`). Menos
   comum; entra depois que o balcão estiver rodando e será lapidado à parte.

---

## 2. Contexto

### O que já existe
- `patients` tem `cpf`, `phone`, `name`, `custom_discount_pct`; o bot pede e
  grava o CPF no cadastro (PRD 020 fase 1).
- `appointments` tem `final_price_cents`, `original_price_cents`,
  `discount_pct`, `is_first_visit`; as áreas de cada serviço do agendamento
  ficam em `appointment_service_areas`. O valor é recalculado pelo motor de
  preço e desconto que o bot e o site já usam.
- `booking-site`: Vite + React, multi-tenant por `clinic_id`, domínio próprio
  por clínica (PRD 021). É o lugar natural da tela do tablet: mesmo domínio,
  mesmo visual, sem login de usuário.
- Backend: Lambda `PublicBooking` com roteador por rota (9 rotas); stack em
  435/500 recursos (cada rota ≈ 2 a 3, cada Lambda ≈ 7 a 8). `Send` manda
  texto por WhatsApp dado `clinicId` + `phone` + `message`.
- Nada de pagamento em banco, painel, site ou bot. O FAQ `PAYMENT_METHODS`
  responde "como paga" em texto.
- Segredos por clínica são colunas texto (`zapi_instance_token`); o `infra/`
  cifra credenciais com Fernet, o `scheduler/` ainda não cifra nada.

### O que o Asaas oferece (docs.asaas.com, 12/10/2026)

| meio | como | observação |
|---|---|---|
| Pix | `POST /v3/payments` com `billingType=PIX`; `GET /v3/payments/{id}/pixQrCode` devolve a imagem (base64) e o copia-e-cola | QR na nossa tela |
| Boleto | `billingType=BOLETO`; resposta traz `bankSlipUrl` (PDF), `invoiceUrl` e a linha digitável (`GET /v3/payments/{id}/identificationField`) | código de barras na nossa tela |
| Cartão de crédito | `billingType=CREDIT_CARD` **com os dados do cartão** no corpo (`creditCard`, `creditCardHolderInfo`, `remoteIp` do pagador), ou a pessoa paga na `invoiceUrl` | tokenização em produção só com liberação do gerente de conta |
| Cartão de débito | **não existe via API**: só na `invoiceUrl` (cobrança `CREDIT_CARD` ou `UNDEFINED`) | é por isso que cartão vai como link |
| Confirmação | **só por webhook** (`PAYMENT_CONFIRMED`, `PAYMENT_RECEIVED`, `PAYMENT_OVERDUE`, `PAYMENT_REFUNDED`, `PAYMENT_DELETED`); "ao menos uma vez"; só HTTP 200 conta; 15 falhas seguidas pausam a fila | |
| Webhook | criado pela API com `authToken` obrigatório (desde 02/2026), chega no header `asaas-access-token`; um por conta Asaas | |
| Sandbox | `https://api-sandbox.asaas.com/v3`, conta separada | |
| Taxas padrão | Pix R$ 1,99; boleto R$ 1,99; débito R$ 0,35 + 1,89%; crédito à vista R$ 0,49 + 2,99% | negociável |

### Decisões de arquitetura

**Cartão é link, não formulário.** Débito não existe pela API, e crédito pela
API faria o número do cartão atravessar nossa Lambda (escopo PCI, `remoteIp`
do pagador, logs). A `invoiceUrl` do Asaas resolve os dois: a paciente abre no
próprio celular, digita o cartão lá, e a confirmação chega pelo mesmo webhook
do Pix e do boleto. Nada de cartão passa por nós. É exatamente o que o André
descreveu para o balcão.

**O tablet é uma tela do `booking-site`, em modo balcão.** Rota
`/:clinicId/balcao` (ou `/balcao` no domínio próprio). Sem login de usuário,
mas protegida por **código de balcão** da clínica (6 dígitos, no painel),
digitado uma vez e guardado no tablet por 12 h. Sem o código, a rota não
responde. (Alternativa: login de STAFF no tablet, que exigiria conta por
recepcionista e login toda manhã.) O que o CPF ou o telefone expõe é só o
agendamento **de hoje** daquela paciente, nesta clínica: nome, áreas e
valor. Nada de histórico, outros dias, nem o telefone em si (a tela mostra o
número mascarado ao enviar o link).

**Confirmar áreas muda o valor, e a cobrança acompanha.** A ordem é fixa:
(1) a tela manda as áreas; (2) o backend recalcula duração e preço pelo motor
que o bot e a recepção já usam, com o desconto da paciente, e **grava** no
agendamento; (3) só então a cobrança é criada no Asaas, a partir do valor
gravado. A tela nunca manda valor. Se as áreas mudarem **depois** de existir
uma cobrança (a paciente voltou e tirou uma área), a cobrança anterior é
cancelada no Asaas e outra é criada com o valor novo, na mesma operação do
nosso lado; o QR ou o link antigos deixam de valer. Invariante: nunca existe
cobrança aberta com valor diferente do `final_price_cents` do agendamento.

**A conta Asaas é da clínica.** Ela cria, gera a chave de API e cola no
painel. Sem split, sem subconta, sem repasse. Vale para a Essência e para a
próxima clínica sem código novo.

**Uma cobrança por agendamento, vida curta.** Pix e cartão vencem no fim do
dia. Trocar de meio, ou mudar as áreas, cancela a cobrança anterior no Asaas
e cria outra: nunca duas abertas para o mesmo agendamento.

**Pago é estado do pagamento, não do agendamento.** `appointments.status`
continua CONFIRMED/CANCELLED/NO_SHOW. `payments.status` diz se pagou. O
painel mostra os dois.

---

## 3. Escopo

### Dentro do escopo (fluxo 1, balcão)
- **Configuração da clínica, no painel:** chave de API do Asaas (cifrada,
  só escrita), ambiente (`sandbox`/`producao`), meios habilitados, dias de
  vencimento do boleto, código de balcão. "Testar conexão" e "Registrar
  webhook" (criamos o webhook no Asaas pela API, com `authToken` nosso).
- **Banco:** `scheduler.payments` (cobrança por linha: `appointment_id`,
  `patient_id`, `amount_cents`, `billing_type`, `status`, `asaas_payment_id`,
  `external_reference`, `invoice_url`, `bank_slip_url`, `pix_payload`,
  `pix_qr_base64`, `linha_digitavel`, `due_date`, `paid_at`,
  `cancelled_at`, `ultimo_evento`, `raw_webhook`); `patients.asaas_customer_id`;
  colunas Asaas em `clinics`.
- **Serviço `asaas_client`:** HTTP fino (customers, payments, pixQrCode,
  identificationField, delete, webhooks), ambiente pela config da clínica,
  dublagem para testes, nunca loga corpo inteiro.
- **Serviço `pagamentos`:** regras: achar o agendamento de hoje por CPF,
  criar cobrança a partir do `final_price_cents`, trocar de meio, aplicar
  webhook (idempotente por `(asaas_payment_id, evento)`), status derivado.
- **Endpoints públicos (no roteador `PublicBooking`):**
  - `POST /public/clinics/{clinicId}/balcao/identificar` — código de balcão
    + CPF **ou telefone** → agendamento de hoje (nome, serviços, áreas, valor,
    status de pagamento). 404 sem agendamento hoje; 401 sem código.
  - `PUT /public/clinics/{clinicId}/balcao/appointments/{id}/areas` — confirma
    ou ajusta áreas; devolve valor recalculado.
  - `POST /public/clinics/{clinicId}/balcao/appointments/{id}/payments` —
    `billingType` (`PIX` | `CARTAO`) → cria (ou troca) a cobrança a partir do
    valor gravado; Pix devolve QR e copia-e-cola; cartão manda o link pelo
    WhatsApp e devolve "enviado para (11) 9****-1234". Rejeita com 409 se o
    valor gravado mudou desde a tela (a tela reconfirma e tenta de novo).
  - `GET /public/clinics/{clinicId}/balcao/payments/{paymentId}` — status
    para a tela (polling de 3 s).
  - `POST /public/webhooks/asaas/{clinicId}` — eventos do Asaas; valida
    `asaas-access-token`; responde 200 sempre; sem `x-api-key`.
- **Tela do balcão no `booking-site`:** código de balcão (uma vez) → CPF ou
  telefone → "Olá, Fulana: hoje às 14:00, Axilas + Virilha, R$ 166,50" com
  as áreas editáveis e o valor recalculado a cada mudança → "Como você quer
  pagar?" (Pix ou cartão) → tela do meio escolhido → "Pagamento confirmado,
  obrigada!" e volta ao início sozinha em 20 s. Tudo grande, para dedo, sem
  teclado físico.
- **WhatsApp:** mensagens fixas (template `PAYMENT_LINK`, `PAYMENT_CONFIRMED`)
  pelo `Send` existente, no número da paciente.
- **Painel:** coluna "pagamento" na agenda do dia (aberto / pago / vencido /
  sem cobrança); na ficha do agendamento, a cobrança e o botão "Enviar link de
  pagamento" (mesmo serviço do balcão, para quem esqueceu o celular ou pagou
  depois).
- **Alarme:** `[AsaasWebhook] erro` no CloudWatch, porque 15 falhas pausam a
  fila do Asaas e nada mais confirma.

### Fluxo 2 (site, na hora de agendar) — depois
- Tela de sucesso do wizard ganha "Pagar agora"; template `BOOKED` ganha o
  link; mesma página de pagamento, sem código de balcão, protegida por
  token da cobrança. Reaproveita `payments`, `asaas_client`, webhook e a tela
  de Pix/boleto. PRD próprio ou revisão deste, quando o balcão estiver
  estável.

### Fora do escopo
- Cartão digitado na nossa tela (tokenização): depende do Asaas liberar;
  avaliar depois do balcão rodar.
- Pagar para confirmar (reserva de horário), sinal, parcial.
- Split, subcontas, antecipação, assinatura.
- Estorno pelo painel (feito no Asaas; refletimos `PAYMENT_REFUNDED`).
- Nota fiscal; maquininha física; TEF.
- Pagamento pelo bot (tool `gerar_link_de_pagamento`): PRD próprio depois.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/scripts/setup_database.py` | modificar | `payments`; `clinics.asaas_*`, `clinics.codigo_de_balcao_hash`; `patients.asaas_customer_id` |
| `scheduler/src/utils/cifra.py` | criar | Fernet com chave em SSM `/${stage}/FERNET_KEY` |
| `scheduler/src/services/asaas_client.py` | criar | HTTP para o Asaas |
| `scheduler/src/services/pagamentos.py` | criar | regras do pagamento e do balcão |
| `scheduler/src/functions/public_booking/balcao_*.py`, `asaas_webhook.py` | criar | 5 handlers |
| `scheduler/src/functions/public_booking/router.py`, `sls/functions/public_booking/interface.yml` | modificar | 5 rotas (≈ 12 recursos; stack 435 → ~447) |
| `scheduler/src/functions/clinic/update.py`, `get.py`, `asaas_setup.py` | modificar/criar | campos Asaas, código de balcão, testar/registrar |
| `scheduler/src/functions/appointment/...` | modificar | status de pagamento na listagem da agenda; "enviar link" |
| `scheduler/src/services/template_service.py` | modificar | `PAYMENT_LINK`, `PAYMENT_CONFIRMED` |
| `booking-site/src/pages/Balcao.tsx` (+ componentes), `router.tsx`, `services/balcao.service.ts`, `types` | criar/modificar | a tela do tablet |
| `frontend/src/pages/configuracoes/...`, `frontend/src/pages/agenda/...` | modificar | config e status |
| testes: `test_pagamentos.py`, `test_asaas_webhook.py`, `test_balcao.py`, `Balcao.test.tsx` | criar | |

---

## 5. Dependências e riscos

- **Do lado do Asaas (a clínica, com a gente junto):**
  1. Conta PJ da Essência aprovada (KYC).
  2. Pix (chave Pix na conta), boleto e cartão habilitados; cartão passa por
     análise do Asaas; débito vem com cartão na fatura.
  3. Chave de API gerada em *Integrações → Chaves de API* e colada no painel.
  4. Webhook registrado por nós pela API; eventos de cobrança ligados; fila
     ativa.
  5. Conta **sandbox** separada para dev.
- **Do nosso lado:** `FERNET_KEY` em SSM (dev e prod); um tablet com
  navegador e Wi-Fi na recepção; o `booking-site` publicado no domínio da
  clínica (já está).
- **Riscos:**
  - *Fila do webhook pausa após 15 falhas*: handler responde 200 sempre
    (grava o evento cru e loga); alarme.
  - *Entrega duplicada*: idempotência por `(asaas_payment_id, evento)`.
  - *Paciente sem CPF*: o telefone é a alternativa na própria tela (é a
    identidade que o bot usa). Nem CPF nem telefone conhecidos: "chame a
    recepção". Não cadastramos pelo tablet.
  - *Duas pacientes com o mesmo CPF* não existe por clínica: `UNIQUE` parcial
    em `(clinic_id, cpf)` onde `cpf IS NOT NULL` entra na migration (hoje
    não há constraint; conferir duplicatas em prod antes).
  - *Tablet exposto*: código de balcão, só agendamento de hoje por CPF, sem
    dados além de nome/áreas/valor; sessão do tablet expira em 12 h.
  - *Valor manipulado*: endpoints nunca aceitam valor; leem do agendamento
    depois da confirmação das áreas.
  - *Cancelar agendamento pago* não estorna sozinho: painel mostra "pago e
    cancelado" para a clínica agir no Asaas.
  - *Chave de API*: cifrada, nunca devolvida, nunca logada.

---

## 6. Critérios de aceite (fluxo 1, sandbox da Essência em dev)

- [ ] Tablet: código de balcão errado não entra; certo, pede CPF.
- [ ] CPF ou telefone de paciente com sessão hoje mostra nome, áreas e valor
      corretos; sem sessão hoje, mensagem clara; desconhecido, "chame a
      recepção".
- [ ] Tirar uma área recalcula o valor e grava no agendamento; o painel
      reflete.
- [ ] Pix: QR na tela; `PAYMENT_RECEIVED` do sandbox vira "pago" na tela em
      até 5 s sem recarregar; agendamento pago no painel.
- [ ] Mudar as áreas depois de gerar o QR cancela a cobrança no Asaas, cria
      outra com o valor novo e a tela mostra o QR novo.
- [ ] Cartão: link chega no WhatsApp; pagar na fatura do Asaas marca pago e
      a tela do tablet mostra "confirmado".
- [ ] Trocar de meio cancela a cobrança anterior no Asaas.
- [ ] Webhook: token errado → 401 e nada gravado; repetido → 200 sem efeito;
      cobrança desconhecida → 200 e log.
- [ ] Chave de API ausente de respostas e logs.
- [ ] Clínica sem Asaas: tela do balcão diz "pagamento indisponível"; nada
      muda no resto.

---

## 7. Fases propostas

| fase | entrega | depende de |
|---|---|---|
| 0 | contas Asaas (sandbox nossa, produção da Essência), `FERNET_KEY`, tablet, decisões da §8 | André / clínica |
| 1 | backend: migrations, cifra, `asaas_client` (fixtures gravadas do sandbox), `pagamentos`, 5 rotas, webhook, templates, testes; config Asaas no painel | 0 |
| 2 | `booking-site`: tela do balcão completa, testes, Vercel | 1 em dev |
| 3 | painel: pagamento na agenda e "Enviar link"; alarme; piloto na Essência com Pix primeiro, depois cartão | 2 |
| 4 | fluxo 2 (site na hora de agendar) | 3 estável |
| 5 | opcional: cartão na nossa tela com tokenização | liberação do Asaas |

---

## 8. Decisões

Tomadas pelo André em 12/10/2026:
- **Paciente sem CPF:** o tablet aceita telefone.
- **Boleto:** fora do balcão por enquanto; reavaliar no fluxo 2.
- **Áreas mudam o valor e a cobrança acompanha:** recalcular, gravar, só
  então cobrar; mudança posterior cancela e recria a cobrança.

- **Proteção do tablet:** código de balcão de 6 dígitos no painel, guardado
  no tablet por 12 h.
- **Vencimento:** Pix e link de cartão vencem às 23:59 do dia da sessão, no
  fuso da clínica.
- **Troca de áreas no balcão:** a paciente mexe sozinha.

Nenhuma pendente. Spec: `spec/023-pagina-de-pagamento-asaas.md`.

---

## 9. Referências

- Asaas: [Criar nova cobrança](https://docs.asaas.com/reference/criar-nova-cobranca), [Pix](https://docs.asaas.com/docs/cobrancas-via-pix), [Boleto](https://docs.asaas.com/docs/cobrancas-via-boleto), [Cartão de crédito](https://docs.asaas.com/docs/cobrancas-via-cartao-de-credito), [Checkout](https://docs.asaas.com/docs/introdu%C3%A7%C3%A3o-1), [Webhooks](https://docs.asaas.com/docs/sobre-os-webhooks), [Eventos de cobrança](https://docs.asaas.com/docs/payment-events), [Fila pausada](https://docs.asaas.com/docs/webhooks-queue-paused), [Token obrigatório](https://docs.asaas.com/changelog/obrigatoriedade-e-auto-geração-de-tokens-para-webhooks), [Preços](https://www.asaas.com/precos-e-taxas).
- PRD 009 (booking-site), PRD 021 (domínio próprio), PRD 020 fase 1 (cadastro com CPF) e §4.3 (FAQ `PAYMENT_METHODS`).

---

## Status (preencher após conclusão)

- [ ] Pendente (aguardando as decisões da §8)
- [ ] Spec gerada: `spec/023-pagina-de-pagamento-asaas.md`
- [ ] Implementado em:
- [ ] Registrado em `TASKS_LOG.md`
