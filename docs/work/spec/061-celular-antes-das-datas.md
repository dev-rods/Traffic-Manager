# Spec - 061 Site identifica a pessoa antes do preço e das datas

> Gerado na fase **Spec** em 23/11/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/061-celular-antes-das-datas.md`

---

## 1. Resumo

Backend (`scheduler`): a cotação pública passa a dizer se o celular é de um
paciente (`cadastro.conhecido`); a confirmação do código devolve o primeiro
nome e os campos que faltam; nasce a rota `POST /public/clinics/{clinicId}/cadastro`
(com token) que cria ou completa o paciente sem agendamento, pelo mesmo
preenchimento que a criação usa; o token de sessão passa a durar 30 minutos.
Site (`booking-site`): a máquina de etapas muda para
`cart -> areas -> phone -> (verify -> identity | register -> verify) -> schedule -> success`;
a etapa `customer` deixa de existir; o par celular+token verificado fica em
`sessionStorage` e é compartilhado com o "Meus agendamentos".

Ordem de deploy: backend primeiro (campos aditivos e rota nova não quebram o
site atual), site depois.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/src/services/cadastro_pelo_site.py` | `completa_paciente(db, clinic_id, phone, nome, cpf, birth_date, email)`: o preenchimento hoje dentro de `AppointmentService._get_or_create_patient`, extraído para a criação e a rota de cadastro usarem o mesmo código; `conflito_de_cpf(db, clinic_id, cpf, proprio_id)` |
| `scheduler/src/functions/public_booking/cadastro.py` | Handler de `POST /public/clinics/{clinicId}/cadastro` |
| `scheduler/tests/unit/test_cadastro_sem_agendamento.py` | Rota nova: token obrigatório, campos validados, `CPF_EM_USO`, COALESCE, resposta sem dados sensíveis |
| `scheduler/tests/unit/test_confirm_otp_devolve_paciente.py` | `paciente` só no escopo sessão, só depois do código válido, só primeiro nome |
| `booking-site/src/components/PhoneStep.tsx` (+ `.test.tsx`) | Etapa do celular |
| `booking-site/src/components/IdentityConfirm.tsx` (+ `.test.tsx`) | "Olá, {nome}, é você?" com os campos que faltam |
| `booking-site/src/utils/sessaoVerificada.ts` (+ `.test.ts`) | Guarda e leitura do par celular+token em `sessionStorage` |
| `scheduler/tests/integration/061-celular-antes-das-datas.md` | Roteiro de validação em dev |
| `scheduler/tests/postman/061-celular-antes-das-datas.postman_requests.json` | Requests das rotas tocadas |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/services/carrinho.py` | `cadastro_para_o_site` devolve `conhecido` |
| `scheduler/src/functions/public_booking/quote.py` | docstring; nada mais (o campo vem de `cadastro_para_o_site`) |
| `scheduler/src/functions/public_booking/confirm_otp.py` | devolve `paciente` quando `scope == SESSAO` |
| `scheduler/src/functions/public_booking/create_appointment.py` | usa `cadastro_pelo_site.conflito_de_cpf`; docstring |
| `scheduler/src/services/appointment_service.py` | `_get_or_create_patient` delega a `cadastro_pelo_site.completa_paciente` |
| `scheduler/src/functions/public_booking/router.py` | rota nova |
| `scheduler/sls/functions/public_booking/interface.yml` | rota nova |
| `scheduler/src/utils/booking_verification.py` | `TOKEN_TTL_SECONDS = 30 * 60` |
| `scheduler/tests/unit/test_carrinho_do_site.py`, `test_cadastro_pelo_site.py`, `test_booking_verification.py` | `conhecido`; TTL |
| `booking-site/src/types/index.ts` | `WizardStep`, `CadastroDoSite.conhecido`, `PacienteVerificado`, `CadastroPayload` |
| `booking-site/src/services/booking.service.ts` | `confirmOtp` devolve `{ token, paciente }`; `cadastro()` |
| `booking-site/src/hooks/useBooking.ts` | `useConfirmOtp` novo retorno; `useCadastro` |
| `booking-site/src/components/CustomerInfoForm.tsx` | modo `semCelular` (cadastro completo, sem o campo de celular) |
| `booking-site/src/components/OtpCodeForm.tsx` | `onVerified(token, paciente)` |
| `booking-site/src/components/MyAppointmentsModal.tsx` | lê e grava `sessaoVerificada` |
| `booking-site/src/components/CartSummary.tsx` | mostra nome e celular confirmados em `schedule` |
| `booking-site/src/pages/Booking.tsx` | nova máquina de etapas |
| `booking-site/src/pages/Booking.test.tsx`, `MyAppointmentsModal.test.tsx`, `CustomerInfoForm.test.tsx` | novos cenários |
| `booking-site/CLAUDE.md` | fluxo novo |
| `docs/work/prd/061-...md`, `TASKS_LOG.md` | status |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. `cadastro_pelo_site.py` + `appointment_service` delegando (suite verde sem mudança de comportamento).
2. `carrinho.cadastro_para_o_site` com `conhecido`; testes.
3. `confirm_otp` com `paciente`; testes.
4. Rota `cadastro` (handler, router, interface.yml); testes.
5. TTL 30 min; teste.
6. Deploy dev do backend; Postman das três rotas.
7. Site: tipos, service, hooks, `sessaoVerificada`.
8. `PhoneStep`, `IdentityConfirm`, `CustomerInfoForm` modo sem celular, `OtpCodeForm`.
9. `Booking.tsx` nova máquina; `CartSummary`; `MyAppointmentsModal`.
10. Testes do site; lint; build.
11. Roteiro em dev com o celular do André; prod com autorização.

---

## 6. Detalhes por arquivo

### `scheduler/src/services/cadastro_pelo_site.py` (criar)

- `completa_paciente(db, clinic_id, phone, nome=None, cpf=None, birth_date=None, email=None) -> dict`:
  o corpo atual de `AppointmentService._get_or_create_patient`, sem mudança
  de regra: casa pelas variantes do número (`formas_do_numero`), exato
  vence, ativo vence apagado; preenche só o que está vazio (`COALESCE`);
  restaura apagado; insere quando não existe. `_completa_algo` vem junto.
- `conflito_de_cpf(db, clinic_id, cpf, proprio_id) -> bool`: a consulta que
  hoje está inline em `create_appointment.py` ("CPF de outro paciente").
- Docstring: existe para a criação e o cadastro sem agendamento gravarem
  pelo mesmo código (ver `feedback_fonte_unica_de_verdade`).

### `scheduler/src/services/appointment_service.py` (modificar)

- `_get_or_create_patient` vira `return completa_paciente(self.db, clinic_id, phone, full_name, cpf, birth_date, email)`.
  Nome e assinatura ficam, para bot, painel e testes não mudarem.

### `scheduler/src/services/carrinho.py` (modificar)

- `cadastro_para_o_site(paciente)` devolve `{"conhecido": paciente is not None, "completo": ..., "faltam": [...]}`.
  Sem telefone a cotação continua devolvendo `cadastro: null`. Com telefone
  desconhecido: `conhecido: false, faltam: ["cpf", "birth_date", "email"]`.
  Docstring: `conhecido` é do mesmo tamanho do que `faltam` já revela.

### `scheduler/src/functions/public_booking/confirm_otp.py` (modificar)

- Depois de `token = confirm_code(...)`, se `scope == SESSAO`:
  `paciente = carrinho.paciente_do_telefone(db, clinic_id, normalize_phone(phone))`
  e a resposta ganha `"paciente": {"nome": primeiro_nome(paciente["name"]), "faltam": cadastro_para_o_site(paciente)["faltam"]}`
  ou `"paciente": null` quando não há ficha. Só o PRIMEIRO nome (o site
  pergunta "é você?"; o sobrenome não ajuda e é dado a menos exposto).
- Escopo `documentos` não devolve `paciente`.
- Docstring: o nome só sai depois do código; antes dele a API nunca o devolve.

### `scheduler/src/functions/public_booking/cadastro.py` (criar)

- `POST /public/clinics/{clinicId}/cadastro`, body:
  `{ "phone", "token", "fullName"?, "cpf"?, "birthDate"?, "email"? }`.
- `require_booking_intake_api_key`; `is_valid_phone`; `verify_token(clinic_id, phone, token)` senão 401 `MENSAGEM_TOKEN` (a mesma da criação).
- Normaliza CPF, nascimento e e-mail com as mesmas funções de
  `create_appointment` (`normaliza_cpf`, `cpf_valido`, `normaliza_data_nascimento`, `normaliza_email`); inválido: 400 com `campo`.
- `paciente = paciente_do_telefone(...)`; `faltam` pela mesma régua da
  criação: o que falta e não veio -> 400 `CADASTRO_INCOMPLETO` com `faltam`.
  Para celular desconhecido `fullName` é obrigatório (400 sem ele).
- `conflito_de_cpf` -> 409 `CPF_EM_USO`.
- `completa_paciente(...)`; resposta 200
  `{"status": "SUCCESS", "paciente": {"nome": primeiro_nome, "faltam": []}}`.
  Não devolve id, CPF, nascimento nem e-mail.
- Log `[PublicBooking][cadastro] {clinic} tel=***{4} novo=True|False completou=[...]`.
- Idempotente: chamar de novo com os mesmos dados não altera nada (COALESCE).

### `scheduler/src/functions/public_booking/router.py` e `sls/functions/public_booking/interface.yml` (modificar)

- `("POST", "public/clinics/{clinicId}/cadastro"): cadastro.handler` e o
  `http` correspondente, ao lado de `quote`. Conferir o total de recursos do
  stack no deploy de dev (prod em 418/500).

### `scheduler/src/utils/booking_verification.py` (modificar)

- `TOKEN_TTL_SECONDS = 30 * 60` com o motivo: o token agora cobre a escolha
  de data. `DOCUMENTOS` não muda.

### Testes do backend

- `test_carrinho_do_site.py`: `conhecido` True/False/null.
- `test_confirm_otp_devolve_paciente.py`: código válido devolve `paciente`
  com primeiro nome e `faltam`; celular sem ficha devolve `null`; escopo
  `documentos` não devolve; código inválido não devolve nada.
- `test_cadastro_sem_agendamento.py`: sem token 401; token de outro celular
  401; celular novo sem `fullName` 400; faltando campo 400 `CADASTRO_INCOMPLETO`;
  CPF de outro 409; cria ficha nova; completa só o vazio de ficha existente;
  resposta não traz CPF/e-mail.
- `test_cadastro_pelo_site.py`: a criação continua gravando igual (prova que
  a extração não mudou comportamento).
- `test_booking_verification.py`: TTL de sessão 1800.

### `booking-site/src/types/index.ts` (modificar)

- `WizardStep = 'cart' | 'areas' | 'phone' | 'verify' | 'identity' | 'register' | 'schedule' | 'success'`.
- `CadastroDoSite.conhecido?: boolean` (opcional: backend antigo não manda).
- `PacienteVerificado = { nome: string; faltam: CampoDoCadastro[] } | null`.
- `CadastroPayload = { phone; token; fullName?; cpf?; birthDate?; email? }`.
- `CreateAppointmentPayload` continua com `cpf/birthDate/email` opcionais
  (compatibilidade); o site novo não os manda, porque o cadastro já foi feito.

### `booking-site/src/services/booking.service.ts` e `hooks/useBooking.ts` (modificar)

- `confirmOtp` devolve `{ token, paciente }`; `cadastro(clinicId, payload)`.
- `useConfirmOtp` repassa o objeto; `useCadastro(clinicId)` mutation.
- `useQuote` sem mudança.

### `booking-site/src/utils/sessaoVerificada.ts` (criar)

- `guarda({ phone, token, expiraEm })`, `le(): {...} | null` (descarta se
  vencido), `limpa()`. `sessionStorage`, chave `booking:verificada`; todo
  acesso em try/catch (navegação privada). `expiraEm = Date.now() + 29 min`
  (um minuto de folga sobre o backend).

### `booking-site/src/components/PhoneStep.tsx` (criar)

- Campo de celular (`formatPhoneInput`, `isValidPhone`), `onPhoneChange`
  para a cotação, texto "Já é paciente? Seu desconto aparece aqui.",
  botão "Continuar" habilitado só com número válido e cotação com celular
  carregada (`aguardando` enquanto `quote.isFetching`).
- `onContinue(phone, conhecido)`.

### `booking-site/src/components/IdentityConfirm.tsx` (criar)

- Props: `nome`, `faltam`, `onConfirm(dados)`, `onNotMe()`, `submitting`.
- "Olá, {nome}, é você?"; "Sou eu" e "Não sou eu". Com `faltam` não vazio,
  "Sou eu" abre `CadastroFields` só com esses campos e o botão vira
  "Continuar"; o nome não é editável.

### `booking-site/src/components/CustomerInfoForm.tsx` (modificar)

- Prop `semCelular?: boolean`: esconde o campo de celular, o schema não o
  exige, e `camposFaltantes` recebe os três campos (cadastro completo).
  Reaproveita o componente em vez de criar um formulário irmão.

### `booking-site/src/components/OtpCodeForm.tsx` (modificar)

- `onVerified(token, paciente)`; o modal de "Meus agendamentos" ignora o
  segundo argumento.

### `booking-site/src/pages/Booking.tsx` (modificar)

- Estado: `phone`, `verified` (de `sessaoVerificada.le()` na montagem),
  `paciente`, `ramo: 'paciente' | 'novo'`, `dadosDeCadastro`.
- `areas` -> "Continuar" -> `phone`.
- `phone`: `onContinue(phone, conhecido)`. Se `verified` vale para esse
  celular, pula o código: `conhecido` -> `identity` (precisa do `paciente`:
  chamar `cadastro` só com `phone`+`token` devolve `nome` e `faltam` sem
  gravar nada; a rota é idempotente) ou `register`. Senão: `conhecido` ->
  `verify`; não conhecido -> `register`.
- `verify` (ramo paciente): `onVerified` guarda o token, grava
  `sessaoVerificada`, guarda `paciente`, vai para `identity`.
- `identity`: "Sou eu" sem faltantes -> `schedule`; com faltantes ->
  `useCadastro` com `phone`, `token` e os campos, depois `schedule`.
  "Não sou eu" -> limpa `phone`, `paciente`, `quotePhone`, volta a `phone`.
- `register`: formulário completo -> guarda `dadosDeCadastro` -> `verify`.
- `verify` (ramo novo): `onVerified` -> `useCadastro` com `dadosDeCadastro`
  + token -> `schedule`. Erro 409 `CPF_EM_USO` volta a `register` com a
  mensagem no CPF.
- `schedule`: botão "Confirmar agendamento" -> `createAppointment` com
  `{ ...cartPayload, phone, fullName: nome, date, time, token }`. `fullName`
  vem do `paciente.nome` (ramo paciente) ou do formulário (ramo novo).
  Tratamento de 409 (`SAME_MONTH`, `OTHER_MONTH`, horário ocupado) como
  hoje, com os diálogos renderizados nesta etapa.
  401 -> `setStep('verify')` com `pendingPayload`; `onVerified` repete a criação.
- `goBack`: `phone -> areas`; `verify -> phone | register`; `identity -> phone`;
  `register -> phone`; `schedule -> identity | register`.
- `quotePhone` passa a ser setado em `phone` e nunca limpo até "Não sou eu".
- `CartSummary` recebe `customer={{ nome, phone }}` em `schedule`.
- `success`: sem mudança.

### `booking-site/src/components/MyAppointmentsModal.tsx` (modificar)

- Na abertura, se `sessaoVerificada.le()` tem o mesmo celular, vai direto
  para a lista com aquele token; ao verificar pelo modal, grava a sessão.

### Testes do site

- `Booking.test.tsx`: paciente com desconto (preço muda ao digitar o
  celular; código; "Olá, Ana, é você?"; sem campos; schedule; cria sem
  novo código); paciente com cadastro incompleto (campos em `identity`;
  `cadastro` chamado; schedule); novo (register; código; `cadastro` chamado
  antes de schedule); "Não sou eu" volta ao celular; 401 na criação pede
  código e conclui; token guardado pula o código.
- `PhoneStep.test.tsx`, `IdentityConfirm.test.tsx`, `sessaoVerificada.test.ts`.
- `MyAppointmentsModal.test.tsx`: com sessão guardada não mostra `OtpCodeForm`.
- `CustomerInfoForm.test.tsx`: modo `semCelular`.

### `scheduler/tests/integration/061-celular-antes-das-datas.md` (criar)

- Casos: quote com celular conhecido (`conhecido: true`, preço pessoal, sem
  nome); confirm devolve `paciente`; cadastro sem token 401; cadastro cria
  ficha; abandono deixa ficha sem agendamento; TTL 30 min; roteiro no
  navegador em dev (Premium dev) com o celular do André: (a) marcar
  `custom_discount_pct` no cadastro dele e ver o preço cair ao digitar;
  (b) número novo fictício NÃO pode ser usado (dev envia WhatsApp de
  verdade): usar o próprio celular com a ficha apagada antes.

---

## 7. Convenções a respeitar

- Nada de nome, CPF ou e-mail na API antes do código confirmado; só o
  primeiro nome depois dele.
- Fonte única: criação e cadastro gravam pelo mesmo `completa_paciente`.
- Telefones fictícios não passam por rota que envia WhatsApp em dev.
- Site: estados loading/error/empty/success em cada etapa; named exports;
  zero `any`; `npm run lint` e `npm run build` limpos antes do push.
- Logs do backend sem telefone completo (`tel=***1234`).
