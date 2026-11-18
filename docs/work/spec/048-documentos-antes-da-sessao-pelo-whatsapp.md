# Spec - 048 Termo e anamnese antes da sessão, pelo link no WhatsApp

> Gerada em 17/11/2026 a partir de `prd/048-documentos-antes-da-sessao-pelo-whatsapp.md`.
> Decisões do André (PRD §5): app `checkin/` em modo remoto; domínios
> `documentos.nobrelaser.com.br` e `documentos.draclaradourado.com.br`; link
> fixo sem token, OTP ao abrir, token de escopo `documentos` de 2 h; botão
> para qualquer termo pendente; template editável; `consent_link_sent_at`;
> direto em prod.

---

## 1. O que muda, em uma frase

A paciente abre um link fixo da clínica no celular, entra com telefone e
código, e percorre dados → ficha → assinatura com os mesmos componentes do
iPad; a recepção manda esse link pelo popover da agenda. Confirmar chegada e
pagar continuam só no iPad.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/utils/booking_verification.py` | escopo no token: `SESSAO` (15 min, o de hoje) e `DOCUMENTOS` (2 h); `confirm_code(..., scope)`; `verify_token(..., scopes=...)` |
| `scheduler/src/functions/public_booking/confirm_otp.py` | lê `scope` do corpo e repassa |
| `scheduler/src/functions/public_booking/checkin.py` | `confirm`, `cobra`, `status`, `simula` só com `SESSAO`; `lista` e consentimento com os dois; `lista` devolve respostas gravadas quando o token é `DOCUMENTOS` |
| `scheduler/src/services/consentimento.py` | `resumo_para_o_ipad(..., com_respostas=False)` ganha `anamnesisAnswers`; **novo** `link_de_documentos(clinic)`; **novo** `envia_link_de_documentos(db, clinic_id, appointment_id, autor)` |
| `scheduler/src/services/envio_do_sistema.py` | origem `DOCUMENTOS` |
| `scheduler/src/services/template_service.py` | `LINK_DOCUMENTOS` em `DEFAULT_TEMPLATES` |
| `scheduler/src/functions/consent/router.py` | `POST appointments/{id}/link` (`agenda.escrever`) |
| `scheduler/src/functions/appointment/list.py` | `FILLING` no LATERAL de `consent_status`; `a.consent_link_sent_at` no SELECT |
| `scheduler/src/scripts/setup_database.py` | coluna `consent_link_sent_at TIMESTAMPTZ` em `appointments` (migration + CREATE TABLE) |
| `scheduler/tests/unit/test_booking_verification.py` | **novo** - escopo, prazo, token antigo de 4 partes |
| `scheduler/tests/unit/test_checkin.py` | handler recusa `DOCUMENTOS` em confirm/cobra; aceita nos demais; `anamnesisAnswers` |
| `scheduler/tests/unit/test_consentimento.py` | `envia_link_de_documentos`: pré-condições, mensagem, origem, `consent_link_sent_at` |
| `scheduler/tests/unit/test_consent_router.py` | rota nova pede `agenda.escrever`; 200/400/404 |
| `scheduler/tests/integration/048-documentos-antes-da-sessao.md` | **novo** - roteiro de prod |
| `checkin/src/router.tsx` | rota `/:clinicId/documentos` |
| `checkin/src/pages/DocumentosPage.tsx` (+ test) | **novo** - máquina de estados do modo remoto |
| `checkin/src/steps/WelcomeStep.tsx`, `NothingToDoStep.tsx` | **novos** - boas-vindas e "nada a fazer" |
| `checkin/src/steps/PhoneStep.tsx`, `CodeStep.tsx` | prop `teclado: 'keypad' \| 'nativo'` e `scope` |
| `checkin/src/steps/DoneStep.tsx` | sem auto-reset quando `remoto` |
| `checkin/src/services/checkin.service.ts`, `hooks/useCheckin.ts`, `types/index.ts` | `scope` no `confirmCode`; `anamnesisAnswers` no agendamento |
| `checkin/src/pages/NotFound.tsx` | sem mudança (a rota nova é antes do `*`) |
| `frontend/src/types/index.ts` | `ConsentStatus` ganha `FILLING`; `Appointment.consent_link_sent_at` |
| `frontend/src/utils/termo.ts` (+ test) | rótulos `FILLING` e `SIGNING` |
| `frontend/src/services/consents.service.ts`, `hooks/useConsents.ts` | `enviarLink` / `useEnviarLinkDosDocumentos` |
| `frontend/src/pages/agenda/components/EnviarLinkDosDocumentos.tsx` (+ test) | **novo** - botão, "enviado em", caixa de copiar |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` (+ test) | monta o botão quando pendente |
| `frontend/src/lib/linkDocumentosPadrao.ts` | **novo** - default e exemplo do template, espelho do backend |
| `frontend/src/pages/configuracoes/ConfiguracoesPage.tsx` | `TemplateField` de `LINK_DOCUMENTOS` |

Uma migration (idempotente). Nenhuma rota nova no CloudFormation: as três
rotas tocadas são coringas já existentes.

---

## 3. Servidor

### 3.1 `booking_verification.py`: escopo no token

```python
SESSAO = "sessao"          # o token de hoje: site, "Meus agendamentos", iPad
DOCUMENTOS = "documentos"  # PRD 048: só ficha e assinatura
TTL = {SESSAO: 15 * 60, DOCUMENTOS: 2 * 60 * 60}
```

- `confirm_code(clinic_id, phone, code, scope=SESSAO)`: valida o escopo
  (`ValueError` fora dos dois) e chama `_issue_token(clinic_id, phone, scope)`.
- `_issue_token`: payload `f"{clinic_id}|{phone}|{expires_at}|{scope}"`,
  assinatura sobre o payload inteiro, token de **5 partes**.
- `verify_token(clinic_id, phone, token, scopes=(SESSAO,))`: aceita token de
  4 partes (emitido antes do deploy) como `SESSAO`, e de 5 partes lendo o
  escopo. Devolve `False` se o escopo não está em `scopes`. Assinatura
  conferida sobre o payload do tamanho certo. Os quatro chamadores de hoje
  (`cancel_appointment`, `list_appointments`, `reschedule_appointment`,
  `checkin`) seguem sem passar `scopes` e, portanto, só aceitam `SESSAO`.

### 3.2 `confirm_otp.py`

`scope = body.get("scope") or SESSAO`; `ValueError` vira 400 "scope inválido".
Resposta inalterada (`token`).

### 3.3 `checkin.py`: quem aceita o quê

Depois de `phone`/`token`:

```python
SO_SESSAO = ("confirma", "cobra", "status", "simula")
escopos = (SESSAO,) if nome in SO_SESSAO else (SESSAO, DOCUMENTOS)
if not verify_token(clinic_id, phone, token, scopes=escopos):
    return _erro(401, "Sua sessão expirou. Confirme o código de novo.")
```

Para o 401 ficar igual nos dois casos (não revelar escopo). Em `lista`, passa
`com_respostas=(escopo do token == DOCUMENTOS)` para
`checkin.agendamentos_do_numero`, que repassa a `consentimento.resumo_para_o_ipad`.
Para saber o escopo, `verify_token` ganha uma irmã `escopo_do_token(token)`
que devolve a string sem validar (a validação já passou).

Docstring do módulo ganha a linha do escopo e a observação: "o token de
documentos nunca confirma chegada nem paga".

### 3.4 `consentimento.py`

- `resumo_para_o_ipad(db, clinic_id, appt, com_respostas=False)`: com
  `True` e `consentRequired`, acrescenta `anamnesisAnswers` = `answers` da
  linha `FILLING`/`SIGNING` da paciente (a função `_respostas_de(row)` já
  existe, linha ~836) ou `{}`. Sem `True`, não acrescenta a chave (o iPad
  continua recebendo o mesmo JSON de hoje).
- **novo** `link_de_documentos(clinic) -> Optional[str]`: a partir de
  `autoatendimento.link_de_autoatendimento(clinic)`; se `None`, `None`;
  senão `https://documentos.{domínio}/{clinic_id}/documentos`. O domínio é
  o `custom_domain` sem `agendar.`? **Não**: `custom_domain` hoje é
  `agendar.nobrelaser.com.br`. Regra: trocar o primeiro rótulo por
  `documentos` (`agendar.X` → `documentos.X`). Se o domínio não começar com
  `agendar.`, prefixar `documentos.`. Teste cobre os dois.
- **novo** `envia_link_de_documentos(db, clinic_id, appointment_id, autor)`:
  1. carrega a sessão com paciente e clínica (mesma consulta de
     `checkin.envia_link`); `NaoEncontrado` se não existe.
  2. pré-condições, cada uma `ConsentimentoInvalido` com mensagem curta:
     `status != CONFIRMED`; `appointment_date < hoje` (fuso da clínica,
     `relogio.agora_na_clinica`); `not precisa_assinar(...)` ("já tem termo
     vigente ou foi dispensado"); `not _clinica_pronta(...)` ("cadastre a
     responsável técnica e a cidade"); `link_de_documentos(clinica) is None`
     ("clínica sem domínio"); telefone vazio.
  3. renderiza `LINK_DOCUMENTOS` com `TemplateService().get_and_render(clinic_id,
     "LINK_DOCUMENTOS", variaveis)`, `variaveis` =
     `lembrete_da_agenda.variaveis_do_template(appt, clinica)` + `{"link": url}`
     (reaproveita `nome`, `clinic_name`, `dia`, `hora`).
  4. `envio_do_sistema.envia_texto(clinica, phone, texto, DOCUMENTOS)`.
  5. se `success`: `UPDATE appointments SET consent_link_sent_at = NOW()`.
  6. devolve `{"link": url, "sent": bool, "consent_link_sent_at": iso|None}`.
  Log: `[Documentos] link {clinic_id} {appointment_id} tel=***1234 enviado=True por {autor}`.

### 3.5 `envio_do_sistema.py`

`DOCUMENTOS = "DOCUMENTOS"`; entra em `ORIGENS`. Docstring: uma linha.

### 3.6 `template_service.py`

```python
"LINK_DOCUMENTOS": (
    "Olá, {{nome}}! Sua sessão na {{clinic_name}} é {{dia}} às {{hora}}. "
    "Para agilizar o atendimento, confira seus dados, responda a ficha de saúde "
    "e assine o termo de consentimento pelo link: {{link}}\n"
    "Leva uns 5 minutos. Você entra com este número de WhatsApp e um código que "
    "chega aqui; na hora de assinar, chega outro código."
),
```

### 3.7 `consent/router.py`

`LINK = re.compile(r"^appointments/{}/link$".format(UUID))`. POST, `agenda.escrever`,
sem corpo obrigatório. Chama `consentimento.envia_link_de_documentos(PostgresService(),
clinic_id, id, _autor(identidade))`. 200 com `para_o_staff(identidade,
{"status": "SUCCESS", **resultado})`. `ConsentimentoInvalido` → 400 com a
mensagem; `NaoEncontrado` → 404. Docstring do módulo ganha a linha da rota.

### 3.8 `appointment/list.py`

LATERAL de `consent_status`:

```sql
SELECT CASE WHEN pc.status IN ('SIGNED', 'PAPER') THEN pc.status ELSE pc.status END AS consent_status
FROM scheduler.patient_consents pc
WHERE pc.clinic_id = a.clinic_id AND pc.patient_id = a.patient_id
  AND pc.term_version = %s AND pc.status IN ('SIGNED', 'PAPER', 'SIGNING', 'FILLING')
ORDER BY CASE pc.status WHEN 'SIGNED' THEN 0 WHEN 'PAPER' THEN 0 WHEN 'SIGNING' THEN 1 ELSE 2 END
LIMIT 1
```

(o `CASE` externo passa a devolver o status literal; `FILLING` e `SIGNING`
saem como estão). `a.consent_link_sent_at` entra no SELECT ao lado de
`a.consent_waived_at`. `patient/list.py` (PRD 047) **não muda**: lá
`FILLING` continua contando como "sem termo", que é o correto.

### 3.9 `setup_database.py`

- `MIGRATIONS`: `"ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS consent_link_sent_at TIMESTAMPTZ"`,
  logo após as `consent_waived_*` (linha ~1268), com comentário "PRD 048".
- `TABLES`: a coluna no `CREATE TABLE appointments`, ao lado de
  `consent_waived_note` (linha ~196).

---

## 4. App `checkin/`: modo remoto

### 4.1 Rota

```ts
{ path: '/:clinicId/documentos', element: <DocumentosPage /> },
{ path: '/:clinicId', element: <CheckinPage /> },
```

Comentário: "Pelo celular, antes da sessão (PRD 048): mesmos passos de
documento, sem chegada nem pagamento."

### 4.2 `DocumentosPage.tsx`

Mesma arquitetura do `CheckinPage` (`useReducer`, união de estados), sem
`useIdleReset`, sem o botão "Recomeçar" no header (há "Trocar número" no
código e "Voltar" nas telas).

```ts
type State =
  | { step: 'phone' }
  | { step: 'code'; phone: string; devCode: string | null }
  | { step: 'loading'; session: Session }                       // GET appointments
  | { step: 'nothing'; firstName: string | null }               // nenhuma pendente
  | ({ step: 'welcome' } & Doc)
  | ({ step: 'consent-data' } & Doc)
  | ({ step: 'anamnese'; tela: number; respostas: AnamneseRespostas; dados: ConsentStartPayload } & Doc)
  | ({ step: 'consent-start'; dados: ConsentStartPayload } & Doc)
  | ({ step: 'consent-sign'; consent: Consent } & Doc)
  | { step: 'done'; firstName: string | null }
interface Doc { session: Session; appointment: CheckinAppointment }
```

Transições:

- `code` → `onVerified(token)` → `loading`. `useAppointments` com a sessão;
  escolhe `appointments.find(a => a.consentRequired)`; achou → `welcome`;
  não achou → `nothing` (primeiro nome do primeiro agendamento, se houver).
  Erro 401 em qualquer chamada → `phone` com aviso "Sua sessão venceu, entre
  de novo" (o progresso está no servidor).
- `welcome` → `consent-data`.
- `consent-data` → `anamnese` tela 1 com `respostas: appointment.anamnesisAnswers ?? {}`
  (**aqui difere do iPad**, que começa em branco: no celular a pessoa pode ter
  parado no meio), ou `consent-start` sem catálogo.
- `anamnese` → mesmas regras do `CheckinPage` (voltar/avançar; última →
  `consent-start`).
- `consent-start` → `SIGNING` → `consent-sign`; qualquer outro status →
  `done` (já assinado por outro caminho).
- `consent-sign` → `onSigned` → `done`. `onRestart` → `phone`.
- `done`: `DoneStep` com `firstName` e mensagem "Documento assinado. No dia,
  é só confirmar e pagar na recepção.", `onFinish` desligado (sem auto-reset,
  prop `remoto`).

Layout: `max-w-md` em todas as etapas (celular), `consent-sign` com a mesma
classe `h-dvh overflow-hidden` do iPad. Header igual ao do iPad sem o botão
"Recomeçar".

### 4.3 Passos reaproveitados

- `PhoneStep`/`CodeStep`: prop `teclado?: 'keypad' | 'nativo'` (default
  `'keypad'`). Com `'nativo'`, em vez de `<Keypad>` renderizam um `<input
  inputMode="numeric" autoComplete="one-time-code">` (no `CodeStep`, o
  `one-time-code` deixa o iOS sugerir o código do WhatsApp). O `StepHeader`
  do `PhoneStep` em modo remoto diz "Digite o WhatsApp em que você recebeu o
  link". `CodeStep` ganha prop `scope?: 'sessao' | 'documentos'` repassada a
  `useConfirmCode`.
- `AnamneseStep`, `ConsentDataStep`, `ConsentStartStep`, `ConsentSignStep`:
  **sem mudança** (já recebem `session`, `appointment` e callbacks). Conferir
  que `ConsentSignStep` não depende de largura mínima do iPad; o widget da
  ClickSign é responsivo.
- `DoneStep`: prop `remoto?: boolean` desliga o timer de 15 s e o botão
  "Concluir" vira "Pode fechar esta página".
- **novo** `WelcomeStep`: nome, dia/hora da sessão (`appointment.date`,
  `startTime`, formatados com os utilitários de `utils/format`), três
  linhas do que vai acontecer, botão "Começar".
- **novo** `NothingToDoStep`: "Tudo certo, {nome}. Não há nada para
  preencher agora. No dia da sessão, é só chegar e fazer o check-in."

### 4.4 Serviço, hook e tipos

- `checkinService.confirmCode(clinicId, phone, code, scope = 'sessao')` envia
  `{ phone, code, scope }`.
- `useConfirmCode(clinicId, scope = 'sessao')`.
- `CheckinAppointment.anamnesisAnswers?: AnamneseRespostas` (opcional: o
  iPad não recebe).

### 4.5 Testes (`DocumentosPage.test.tsx`)

Mesmo molde do `CheckinPage.test.tsx` (mock de `checkinService`):

1. telefone → código → sem pendente → "nada a fazer".
2. telefone → código → pendente → boas-vindas → dados → anamnese com
   respostas pré-carregadas → preparar → assinar (SIGNING) → assinado → fim;
   `confirmCode` chamado com `scope: 'documentos'`; `confirm` e `pay` nunca
   chamados.
3. 401 no meio volta ao telefone com o aviso.
4. `CheckinPage.test.tsx`: um caso novo confirmando que `confirmCode` segue
   sem `scope` (ou com `'sessao'`).

---

## 5. Painel

### 5.1 Tipos e rótulos

- `ConsentStatus = 'SIGNED' | 'PAPER' | 'SIGNING' | 'FILLING'`;
  `Appointment.consent_link_sent_at: string | null`.
- `situacaoDoTermo`: `FILLING` → `{ label: 'Preenchendo pelo link', tom:
  'atencao', pendente: true }`; `SIGNING` → `'Assinando'` (sai "no iPad").
  `semTermo` não muda (`FILLING` continua "sem termo").
- `MOTIVO_DA_DISPENSA.RECUSOU` continua "Recusou assinar no iPad" (é a
  dispensa do dia).

### 5.2 Serviço e hook

```ts
enviarLinkDosDocumentos: (clinicId, appointmentId) =>
  api.post<{ link: string; sent: boolean; consent_link_sent_at: string | null }>(
    `/clinics/${clinicId}/consents/appointments/${appointmentId}/link`).then(r => r.data)
```

`useEnviarLinkDosDocumentos()` no molde de `useEnviarLink` (invalida
`appointmentKeys.lists()`).

### 5.3 `EnviarLinkDosDocumentos.tsx`

Props: `appointmentId`, `linkEnviadoEm: string | null`. Comportamento igual
ao `EnviarLinkDePagamento` sem o ramo do CPF:

- botão "Enviar link dos documentos" (ou "Reenviar link dos documentos"
  quando `linkEnviadoEm`), largura total, mesmo estilo;
- abaixo, em `text-xs text-gray-500`, "Link enviado em 17/11 às 14:20"
  quando houver (formatar com o utilitário de data já usado no popover);
- `sent: false` → caixa âmbar com o link para copiar (texto: "O WhatsApp
  não enviou. Copie o link e mande para a paciente.");
- erro 400 → toast com a mensagem do backend.

### 5.4 `TermoDoAgendamento.tsx`

Dentro do bloco `situacao.pendente`, acima dos dois botões de hoje:
`<EnviarLinkDosDocumentos appointmentId={a.id} linkEnviadoEm={a.consent_link_sent_at} />`,
renderizado só quando `a.appointment_date >= hoje` (o mesmo cálculo de data
local usado em `situacaoDoTermo`/agenda) e `a.patient_id`. A decisão de
"clínica sem domínio" fica no servidor (400 com mensagem); o painel não
conhece o domínio.

Teste: botão aparece para pendente futuro; não aparece para sessão passada
nem para assinado; sucesso mostra "enviado em"; `sent:false` mostra o link.

### 5.5 Template na tela de configurações

`frontend/src/lib/linkDocumentosPadrao.ts` com `LINK_DOCUMENTOS_PADRAO`
(cópia byte a byte do backend) e `EXEMPLO_DO_LINK` (`nome`, `clinic_name`,
`dia`, `hora`, `link: 'https://documentos.suaclinica.com.br/sua-clinica/documentos'`).
Em `ConfiguracoesPage`, um `TemplateField templateKey="LINK_DOCUMENTOS"`
logo abaixo do de `LEMBRETE_SESSAO`, label "Link dos documentos (termo e
ficha)", help "Enviado pela agenda para quem ainda não assinou. Variáveis:
{{nome}}, {{clinic_name}}, {{dia}}, {{hora}}, {{link}}".

---

## 6. Ordem de implementação

1. **Servidor, token**: `booking_verification` + `confirm_otp` + testes.
   Deploy nenhum ainda.
2. **Servidor, check-in**: escopos em `checkin.py`, `anamnesisAnswers`,
   testes em `test_checkin.py`.
3. **Servidor, envio**: origem, template, `link_de_documentos`,
   `envia_link_de_documentos`, rota no router, migration, `FILLING` na
   agenda; testes. `pytest scheduler/tests/unit` verde.
4. **Deploy prod do scheduler** (`cd scheduler && serverless deploy --stage
   prod --aws-profile dev-andre`; nunca em paralelo com dev). Rodar
   `setup_database.py` em prod para a coluna. Conferir no painel que a
   agenda ainda lista (campo novo nulo).
5. **App checkin**: passos, página, rota, serviço, testes; `npm run build`
   e `npm run lint`. Deploy `checkin-prod` pela CLI da Vercel (login
   interativo é do André). Conferir `https://documentos.draclaradourado.com.br/clinicaessenciaestetica-9668a4/documentos`
   abre a tela de telefone e `/clinicaessenciaestetica-9668a4` segue o iPad.
6. **Painel**: tipos, rótulos, serviço, hook, componente, popover, template;
   Vitest; `npm run build` e `npm run lint`. Merge → Vercel.
7. **E2E em prod** (roteiro em §8), antes de qualquer envio a paciente.

---

## 7. Convenções

- Logs com prefixo `[Documentos]` no serviço e `[Checkin]` no handler.
- Permissão `agenda.escrever` no servidor; painel só esconde o botão.
- Nenhum nome real de paciente em teste, commit, PR ou doc.
- Migration idempotente (`ADD COLUMN IF NOT EXISTS`) e `CREATE TABLE` em
  sincronia.
- Texto do template igual no backend e no `linkDocumentosPadrao.ts`; teste
  do painel confere a presença de `{{link}}`.
- Nada de `any`; exports nomeados; 4 estados nas views que carregam dados
  (`loading` da página remota cobre o GET).

---

## 8. Roteiro de prod (`scheduler/tests/integration/048-documentos-antes-da-sessao.md`)

1. Sessão futura de uma paciente de teste (telefone do André) na Essência,
   sem termo vigente. Popover → "Enviar link dos documentos" → mensagem chega
   pelo número da clínica; popover mostra "enviado em"; `message-events` tem
   `metadata.origem = DOCUMENTOS`; o bot **não** pausou (conferir sessão).
2. Abrir o link no celular: telefone → código → boas-vindas → dados → 4
   telas → preparar → widget da ClickSign (código no WhatsApp, manuscrita) →
   "Documento assinado". Safari iOS e Chrome Android. **1 crédito.**
3. Agenda: sessão sai de "Pendente" para "Assinado"; PDF na pasta da
   paciente.
4. iPad: check-in da mesma sessão pula termo e ficha, vai de confirmar para
   pagar.
5. Negativos: link aberto por outro número → "nada a fazer"; token de
   documentos em `confirm` (curl) → 401; sessão passada → botão ausente;
   clínica sem domínio (clínica de dev) → 400 com mensagem.
6. Retomada: parar na tela 2 da ficha, fechar, reabrir, entrar de novo →
   respostas da tela 1 já marcadas.
