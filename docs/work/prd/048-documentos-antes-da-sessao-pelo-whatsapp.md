# PRD - 048 Termo e anamnese antes da sessão, pelo link no WhatsApp

> Gerado na fase **Research** em 17/11/2026. Use como input para a fase Spec.
> Pedido do André: "transferir parte do fluxo do check-in para o WhatsApp, sem
> o pagamento. Enviar um link para o paciente agendado como primeira vez, para
> que ele antecipe e preencha o termo. Não pensar no envio automático ainda;
> pensar no link e na divisão do fluxo de assinatura. Implementar direto em
> prod, é fluxo novo."

---

## 1. Objetivo

Quem tem sessão marcada e ainda não tem o documento vigente (termo de
consentimento + ficha de anamnese, PRDs 036 e 038) recebe pelo WhatsApp um
link para **conferir os dados, responder a ficha e assinar pelo próprio
celular**, em casa, antes do dia. No dia, o check-in no iPad encontra o
documento assinado e vai direto para confirmar e pagar.

O pagamento continua só no dia: a clínica não cobra antecipado.

---

## 2. Contexto

### 2.1 O que já existe e o que este PRD aproveita

| Peça | Onde | Estado |
|---|---|---|
| Passos de dados, anamnese (4 telas), preparação e assinatura | `checkin/src/steps/ConsentDataStep`, `AnamneseStep`, `ConsentStartStep`, `ConsentSignStep` | prontos, em prod |
| Rotas públicas `appointments/{id}/anamnesis`, `appointments/{id}/consent`, `consents/{id}` | `scheduler/src/functions/public_booking/checkin.py` | prontas; **não exigem `confirm`** antes, então não marcam chegada |
| Regra "precisa assinar" | `services/consentimento.precisa_assinar` | documento por paciente e versão; o iPad do dia já pula quando há vigente |
| Respostas gravadas antes de assinar (`FILLING`), retomada com `anamnesisPrefill`, reaproveitamento de `SIGNING` até 24 h | `consentimento.guarda_respostas`, `inicia` | prontos; o 038 §2.6 diz que foi desenhado "para deixar o backend pronto" para preencher em casa |
| Envio do sistema que não pausa o bot (PRD 034) | `services/envio_do_sistema.envia_texto` | pronto; origens fechadas em lista |
| Link de pagamento enviado pelo popover da agenda (PRD 029) | `frontend/.../EnviarLinkDePagamento.tsx`, `services/checkin.envia_link` | molde do botão e da rota |
| Domínio por clínica (`custom_domain`) e `link_de_autoatendimento` | `services/autoatendimento.py` | molde para montar a URL |

O fluxo remoto é, na prática, **o meio do check-in sem as pontas**: sem OTP
na entrada, sem confirmar chegada, sem pagamento.

### 2.2 Por que foi deixado de fora antes e o que mudou

O 036 (§9) e o 038 (§2.6) deixaram "preencher pelo celular" de fora por três
motivos. Cada um tem resposta hoje:

1. **"Link pedindo dado de saúde no WhatsApp parece golpe."** O link sai do
   número da clínica que a paciente já conhece, com o nome dela, a data da
   sessão e **no domínio da clínica** (`documentos.nobrelaser.com.br`, não
   `vercel.app`). A assinatura exige o código da ClickSign que chega no mesmo
   WhatsApp, e a mensagem avisa disso.
2. **"Exige domínio, app e token próprios."** App e telas já existem
   (`checkin/`). O domínio é um CNAME por clínica. O token é o mesmo
   mecanismo HMAC do OTP, com outro escopo e outro prazo.
3. **"No iPad a paciente já está identificada."** No celular ela é
   identificada pelo token do link (uma sessão, um prazo) e, para assinar,
   pelo código da ClickSign. O que o token do link libera sozinho é ler o
   próprio nome, o CPF mascarado e responder a ficha; nunca confirmar
   chegada nem pagar.

### 2.3 O que o iPad faz hoje e o que passa para o celular

```
Hoje (iPad):    telefone → OTP → sessão → dados → anamnese ×4 → preparar → assinar → confirmar → método → pagar → fim
Celular (048):  link ───────────────────▶ dados → anamnese ×4 → preparar → assinar → fim
iPad no dia:    telefone → OTP → sessão → (documento vigente: pula) → confirmar → método → pagar → fim
```

A divisão é limpa porque o documento é **por paciente**, não por check-in:
`precisa_assinar` já olha `patient_consents`, não o check-in. Nada do fluxo do
dia precisa saber que a assinatura veio pelo celular.

---

## 3. Proposta

### 3.1 O link

`https://documentos.{domínio da clínica}/{clinicId}/documentos/{token}`

- **Hospedagem:** o próprio app `checkin/` (projeto Vercel `checkin-prod`),
  com uma rota nova `/:clinicId/documentos/:token`. Sem app novo, sem
  duplicar telas no `booking-site/`.
- **Domínio:** `documentos.<custom_domain da clínica>` apontando para o
  projeto Vercel do check-in. Clínica sem domínio não tem link (mesma regra
  do PRD 046, `link_de_autoatendimento`).
- **Token:** o mesmo formato HMAC de `booking_verification._issue_token`
  (`BOOKING_VERIFICATION_SECRET`), com escopo próprio:
  `documentos|clinic_id|appointment_id|expires_at|hmac`. **Sem tabela**,
  sem estado. Validade: **até o fim do dia da sessão** (depois do dia, o
  iPad é o caminho). Reenviar gera outro token válido; o anterior continua
  valendo até expirar, o que é inofensivo porque o escopo é só este.
- **O que o token libera** nas sub-rotas do check-in (`checkin.py`):
  - `GET appointments/{id}/documentos`: nome, data e hora da sessão,
    `consentRequired`, `consentPrefill` (nome, CPF mascarado, nascimento,
    e-mail, menor/responsável) e `anamnesisPrefill`, como o iPad recebe.
  - `POST appointments/{id}/anamnesis`, `POST appointments/{id}/consent`,
    `GET consents/{id}`: os mesmos handlers, aceitando o token de documentos
    no lugar de `phone + token` de OTP.
  - **Recusa** `confirm`, `payments` e a lista de agendamentos. O token só
    serve ao `appointment_id` que carrega; o handler compara antes de tudo.
- **Pré-condições para emitir:** sessão `CONFIRMED`, data `>= hoje`,
  `precisa_assinar` verdadeiro, clínica pronta (`_clinica_pronta`: RT com
  registro e cidade), clínica com domínio.

### 3.2 O fluxo no celular

Rota `/:clinicId/documentos/:token` no `checkin/`, **modo remoto**:

1. **Boas-vindas**: "Olá, {nome}. Sua sessão é {dia} às {hora}. Antes,
   confira seus dados, responda a ficha e assine o termo. Leva uns 5
   minutos." Botão "Começar". Se o token expirou ou o documento já está
   vigente: tela "Tudo certo, nada a fazer" ou "Este link venceu, faça no
   dia na recepção".
2. `consent-data` → `anamnese` 1 a 4 → `consent-start` → `consent-sign`:
   **os mesmos componentes**, com o serviço recebendo o token de documentos.
3. **Fim**: "Documento assinado. No dia, é só confirmar e pagar na
   recepção." Sem passo de método, sem pagamento.

Diferenças do modo quiosque, todas por flag de modo (não por cópia):

- Sem `useIdleReset` (não é um tablet compartilhado); sem `Keypad`
  próprio, o teclado é o do celular (`TextField` já é usado nos campos do
  termo).
- Retomada: reabrir o link volta onde parou (`anamnesisPrefill` e o
  `SIGNING` reaproveitado já fazem isso no backend).
- Falha na assinatura (código não chega, ClickSign fora): "Tente de novo
  mais tarde ou faça no dia na recepção", sem botão de pular. A dispensa
  continua só pelo painel.
- Layout de celular: largura de 360 a 430 px, toques de 48 px; o widget da
  ClickSign em tela cheia como já é no iPad.

### 3.3 O envio, pelo painel (manual nesta fase)

No popover da agenda (`TermoDoAgendamento.tsx`), junto de "Dispensar" e
"Assinado em papel": **"Enviar link dos documentos"**, visível quando a
sessão é futura ou de hoje, o termo está pendente e a clínica tem domínio.
Mesmo molde de `EnviarLinkDePagamento`: botão, estado de envio, caixa de
copiar quando o envio falhar.

- Rota do painel: `POST clinics/{clinicId}/consents/appointments/{appointmentId}/link`
  no router de consentimento já existente (`functions/consent/router.py`),
  permissão `agenda.escrever`. Sem recurso novo no CloudFormation (a stack
  está perto do limite).
- Backend: emite o token, monta a URL, renderiza a mensagem e chama
  `envio_do_sistema.envia_texto(..., origem=DOCUMENTOS)`. **Origem nova**
  na lista fechada de `envio_do_sistema` (hoje `SITE_OTP`,
  `SITE_AGENDAMENTO`, `CHECKIN`); sem ela o envio levanta `ValueError`, e
  um envio fora dessa função pausaria o bot (PRD 034).
- Grava `appointments.consent_link_sent_at` (coluna nova, nula) para o
  popover mostrar "Link enviado em 17/11 às 14:20" e a recepção não reenviar
  sem querer. Reenviar é permitido.
- **Mensagem como template editável por clínica** (`LINK_DOCUMENTOS` em
  `template_service.DEFAULT_TEMPLATES`), ao contrário do link de pagamento,
  que é fixo em Python. Padrão:

  > Olá, {{nome}}! Sua sessão na {{clinic_name}} é {{dia}} às {{hora}}.
  > Para agilizar o atendimento, confira seus dados, responda a ficha de
  > saúde e assine o termo de consentimento pelo link: {{link}}
  > Leva uns 5 minutos. Na hora de assinar, um código de confirmação chega
  > neste WhatsApp.

### 3.4 Quem recebe

O botão aparece para **qualquer sessão com termo pendente**, não só
`is_first_visit`. Motivo: a regra do documento é "sem vigente na versão
atual" (decisão 3 do 036), e isso inclui pacientes antigas sem termo digital
nem papel registrado. Na prática a recepção vai usar nas primeiras vezes, que
é o pedido; e o envio automático (fase 2) pode filtrar por `is_first_visit`
se o André preferir.

### 3.5 Painel: estados que passam a existir fora do iPad

- `consent_status` da listagem da agenda (`functions/appointment/list.py`)
  passa a considerar `FILLING` (hoje invisível: ficha pela metade aparece
  como "Pendente").
- Rótulos em `utils/termo.ts`: `FILLING` → "Preenchendo pelo link",
  `SIGNING` → "Assinando" (sai o "no iPad"). O selo `DOCS` segue igual.
- "Pedir nova assinatura" continua funcionando: se a profissional pedir
  nova, o link pode ser enviado de novo.

---

## 4. Escopo

### Dentro

- Token de documentos (emissão e validação), com testes.
- Sub-rota `GET appointments/{id}/documentos` e aceitação do token nas três
  sub-rotas existentes; recusa explícita em `confirm`, `payments` e listagem.
- Rota `/:clinicId/documentos/:token` no `checkin/` em modo remoto, com
  boas-vindas, fim, expirado e já-vigente.
- Rota do painel para enviar, origem `DOCUMENTOS`, template
  `LINK_DOCUMENTOS`, coluna `consent_link_sent_at` (migration idempotente),
  botão no popover com "enviado em".
- `FILLING` visível na agenda e rótulos novos.
- Domínios `documentos.nobrelaser.com.br` e `documentos.draclaradourado.com.br`
  no projeto `checkin-prod` da Vercel (DNS é do André).
- Doc de integração `scheduler/tests/integration/048-documentos-antes-da-sessao.md`.

### Fora

- **Envio automático** (gatilho por tempo antes da sessão). Fase 2, PRD
  próprio; a rota e o template deste PRD são o que ele vai chamar.
- Pagamento antecipado. Não existe na clínica.
- Confirmar presença pelo link. É outro assunto (lembrete de 24 h, PRD 027).
- Triagem por sessão (seção 8 da ficha), como no 038.
- Mudar texto do termo ou da ficha, versão, modelo da ClickSign.
- Conta ClickSign por clínica (segue global por stage).
- Bot responder dúvidas sobre o link. Se a paciente perguntar, o bot cai no
  atendimento normal; o que ele diz sobre isso é prompt no banco, não código.

---

## 5. Decisões a confirmar

| # | Pergunta | Recomendação | Alternativa |
|---|---|---|---|
| 1 | Onde o link abre | **App `checkin/` em modo remoto** | Rotas no `booking-site/` (duplicaria 6 telas; o site é "não tocar") |
| 2 | Domínio | **`documentos.<domínio da clínica>`** antes do primeiro envio real | `checkin-prod.vercel.app` como provisório; alimenta o "parece golpe" |
| 3 | Autenticação | **Token do link (escopo documentos, até o dia da sessão) + código da ClickSign para assinar** | Pedir OTP ao abrir o link: um passo a mais e o token de 15 min não cobre 4 telas + assinatura |
| 4 | Para quem | **Qualquer termo pendente** (botão manual) | Só `is_first_visit` |
| 5 | Mensagem | **Template editável** (`LINK_DOCUMENTOS`) | Fixa em Python, como o link de pagamento |
| 6 | Registro do envio | **`consent_link_sent_at` na sessão** | Só no `message-events` (a recepção não enxerga) |
| 7 | Deploy | **Direto em prod**, com E2E no celular do André antes do primeiro envio a paciente | Dev primeiro |

---

## 6. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/utils/booking_verification.py` | modificar | `issue_documents_token` / `verify_documents_token` (escopo, appointment, prazo) |
| `scheduler/src/functions/public_booking/checkin.py` | modificar | aceitar o token de documentos; sub-rota `appointments/{id}/documentos`; recusa em confirm/payments/lista |
| `scheduler/src/services/consentimento.py` | modificar | `resumo_para_o_link` (prefill + anamnesisPrefill para uma sessão); `link_de_documentos(clinic, appointment)` |
| `scheduler/src/services/envio_do_sistema.py` | modificar | origem `DOCUMENTOS` |
| `scheduler/src/services/template_service.py` | modificar | `LINK_DOCUMENTOS` nos defaults |
| `scheduler/src/functions/consent/router.py` | modificar | `POST .../consents/appointments/{appointmentId}/link` |
| `scheduler/src/functions/appointment/list.py` | modificar | `FILLING` no `consent_status`; `consent_link_sent_at` |
| `scheduler/src/scripts/setup_database.py` | modificar | `ALTER TABLE appointments ADD COLUMN IF NOT EXISTS consent_link_sent_at` (+ CREATE TABLE) |
| `scheduler/tests/unit/test_documents_token.py`, `test_checkin_documentos.py` | criar | token, escopo, recusas, prefill |
| `checkin/src/router.tsx`, `pages/DocumentosPage.tsx` (+ test) | criar/modificar | rota e máquina de estados do modo remoto |
| `checkin/src/steps/*` | modificar | flag de modo (sem idle reset, teclado nativo, textos de fim) |
| `checkin/src/services/checkin.service.ts`, `types/index.ts` | modificar | chamadas com token de documentos |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` (+ test), `EnviarLinkDosDocumentos.tsx` | criar/modificar | botão, estado, "enviado em", copiar |
| `frontend/src/services/consents.service.ts`, `hooks/useConsents.ts`, `types/index.ts`, `utils/termo.ts` | modificar | rota, hook, rótulos |
| `frontend/src/lib/*templates*` | modificar | `LINK_DOCUMENTOS` na tela de templates |
| `scheduler/tests/integration/048-documentos-antes-da-sessao.md` | criar | roteiro |

---

## 7. Dependências e riscos

- **Widget da ClickSign no celular.** Hoje só rodou no iPad. Antes do
  primeiro envio real: assinar de verdade no celular do André (1 crédito),
  em Safari iOS e Chrome Android. Se o widget não servir no celular, o
  caminho de volta é a ClickSign enviar o próprio link de assinatura
  (`communicate_events.signature_request` por WhatsApp) e o nosso fluxo parar
  no "preparar".
- **Prazo do envelope é 2 dias** (`PRAZO_DO_ENVELOPE`). Link enviado com 7
  dias de antecedência e paciente que para em "assinar" deixa um envelope
  vencer; reabrir cria outro (o `SIGNING` velho é descartado). Custo zero,
  porque a ClickSign cobra por documento finalizado.
- **Link encaminhado a terceiro** expõe nome, CPF mascarado, nascimento e
  e-mail que a própria paciente informou. Mitigação: prazo curto, escopo
  único, assinatura só com código no WhatsApp dela. Se o André quiser
  fechar mais, a decisão 3 tem a alternativa com OTP.
- **Direto em prod**: um deploy do `scheduler/` (prod, nunca em paralelo
  com dev), `checkin-prod` pela CLI da Vercel, painel pela Vercel no merge.
  Nenhuma rota nova no CloudFormation. Migration idempotente.
- **DNS** dos dois subdomínios é do André; sem ele, o botão não aparece
  (clínica "sem link").
- **Bot**: o envio passa por `envia_texto`, então o eco é reconhecido e o
  bot não pausa. Se a paciente responder "não consegui", a conversa segue
  normal; o bot não conhece o fluxo.

---

## 8. Critérios de aceite

- [ ] Link emitido só para sessão confirmada, futura ou de hoje, com termo pendente, clínica pronta e com domínio.
- [ ] Token de documentos abre a página com o nome e a data da sessão; expira no fim do dia da sessão; não serve para `confirm`, `payments` nem para outra sessão.
- [ ] Dados → anamnese (4 telas) → assinar funciona no celular, com retomada ao reabrir o link.
- [ ] Documento assinado pelo link aparece na agenda como assinado; no dia, o iPad pula os passos e vai de confirmar para pagar.
- [ ] Mensagem sai pelo número da clínica, não pausa o bot, e usa o template editável.
- [ ] Popover mostra "Link enviado em"; reenvio permitido.
- [ ] `FILLING` aparece na agenda como "Preenchendo pelo link".
- [ ] Link vencido ou documento já vigente mostram tela própria, sem erro genérico.
- [ ] pytest e Vitest dos pontos acima; `npm run build` e `npm run lint` nos três apps.

---

## 9. Referências

- PRD 026 (check-in e OTP), 029 (link de pagamento), 034 (envios do sistema), 036 (termo), 038 (anamnese), 046 (link como primeiro caminho), 047 (papel por paciente)
- `checkin/CLAUDE.md`, `scheduler/src/utils/booking_verification.py`, `scheduler/src/services/consentimento.py`

---

## Status

- [x] Pendente
- [ ] Spec gerada: `spec/048-documentos-antes-da-sessao-pelo-whatsapp.md`
- [ ] Implementado em prod: (data)
- [ ] Registrado em `TASKS_LOG.md`
