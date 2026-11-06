# Spec - 038 Ficha de anamnese no check-in, compilada no modelo do termo

> Gerado na fase **Spec** em 05/11/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/038-ficha-de-anamnese-no-checkin.md` (decisões 1 a 12 fechadas)
- **Modelo já validado:** `docs/work/assets/038-modelo-compilado/` (gerador + `.docx`; sandbox `1d2b35f6`, 68 variáveis, PDF de 8 páginas)

---

## 1. Resumo

O documento assinado no check-in passa a ser o **modelo compilado** (TCLE de
produção + ficha de anamnese V03), versão `2026-12`. No iPad entram **4 telas
de anamnese** entre a tela de dados e a assinatura; cada "Continuar" grava as
respostas no backend (registro `FILLING`), e o último cria o envelope como
hoje. O backend ganha um catálogo das perguntas (`anamnese.py`), que é a
única fonte das chaves, das telas, das variáveis do modelo e da lista de
alertas; o iPad e o painel leem esse catálogo pela API. O painel mostra as
respostas e os alertas no popover e na aba de Documentos, com "Pedir nova
assinatura". **Nenhuma Lambda, rota de infraestrutura ou documento novo na
ClickSign**: o pipeline do 036 com mais variáveis. Stacks em 482/500; a
mudança não acrescenta recurso ao CloudFormation.

Invariantes que a implementação preserva:

- `consentimento.precisa_assinar` continua o único dono do gatilho.
- Respostas e PDF nunca divergem: o PDF é gerado das respostas gravadas.
- Fototipo declarado nunca escreve `patients.skin_type`.
- Nenhuma tool do bot lê `patient_consents`.
- Dado de saúde só sai pela rota do painel com `prontuario.ler`.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/src/services/anamnese.py` | Catálogo das perguntas (chave, tela, texto, tipo, condicional, alerta), validação por tela e completa, variáveis do modelo, alertas |
| `scheduler/tests/unit/test_anamnese.py` | Catálogo íntegro, validação, variáveis, alertas |
| `checkin/src/steps/AnamneseStep.tsx` | As 4 telas, dirigidas pelo catálogo que vem do `bootstrap` |
| `checkin/src/components/ui/SimNao.tsx` | Par de botões grandes "Sim"/"Não", sem default, acessível |
| `frontend/src/pages/documentos/components/RespostasDaAnamnese.tsx` | Respostas por seção + alertas + nota do fototipo |
| `frontend/src/pages/agenda/components/AlertasDaAnamnese.tsx` | Lista vermelha de alertas, usada no popover |
| `scheduler/tests/integration/038-ficha-de-anamnese-no-checkin.md` | Roteiro E2E, curls, achados |
| `scheduler/tests/postman/038-ficha-de-anamnese-no-checkin.postman_requests.json` | Requests novas |
| `scheduler/tests/mocks/public_booking/checkin_anamnesis_save.json` | Payload da gravação parcial |

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/scripts/setup_database.py` | `answers JSONB`, status `FILLING`/`REVOKED` no CHECK, índice "em andamento" cobre `FILLING` |
| `scheduler/src/services/consentimento.py` | `FILLING`, `guarda_respostas`, `inicia` exige ficha completa, snapshot e `_mesmos_dados` com respostas, variáveis da ficha, `renova`, `para_o_painel` com `answers`/`alertas`, `resumo_para_o_ipad` com `anamnesisPrefill` |
| `scheduler/src/services/checkin.py` | Nada além do spread já existente (o `resumo` cresce sozinho) |
| `scheduler/src/functions/public_booking/checkin.py` | Rota `PUT appointments/{id}/anamnesis`; `bootstrap` devolve o catálogo |
| `scheduler/src/functions/consent/router.py` | `POST {id}/renew`; `GET patients/{id}` já devolve o que `para_o_painel` montar |
| `scheduler/src/functions/appointment/list.py` | LATERAL trata `FILLING` como pendente (já cai no `ELSE 'SIGNING'`); comentário |
| `scheduler/src/providers/*` | Sem mudança de interface. `clicksign_provider` só recebe mais `dados` |
| `scheduler/serverless.yml` | Nada (mesmas env vars). Versão e modelo novos entram pelo SSM |
| `scheduler/tests/unit/test_consentimento.py`, `test_checkin.py`, `test_consent_router.py`, `test_rotas_abertas_ao_staff.py` | Casos novos (seção 6) |
| `checkin/src/types/index.ts` | `AnamneseCatalogo`, `AnamneseRespostas`, `anamnesisPrefill`, `anamnese` no bootstrap |
| `checkin/src/services/checkin.service.ts`, `hooks/useCheckin.ts` | `saveAnamnesis`, `useSaveAnamnesis`; `startConsent` inalterado |
| `checkin/src/steps/ConsentDataStep.tsx` | Deixa de chamar `startConsent`: valida e devolve o `ConsentStartPayload` por `onContinue` |
| `checkin/src/pages/CheckinPage.tsx` | Estados `anamnese` (com `tela` e `respostas`) e `consent-start`; `LONG_IDLE_STEPS` += anamnese |
| `checkin/src/pages/CheckinPage.test.tsx` | Fluxo com as 4 telas, condicionais, prefill, erro de validação |
| `checkin/CLAUDE.md` | Parágrafo da anamnese |
| `frontend/src/types/index.ts` | `PatientConsent` += `answers`, `alertas`, `revoked_at`; `ConsentStatus` += `FILLING`, `REVOKED` |
| `frontend/src/services/consents.service.ts`, `hooks/useConsents.ts` | `renovar`, `useRenovarTermo` |
| `frontend/src/utils/termo.ts` | `situacaoDoTermo` entende `FILLING` como pendente; rótulos "Documento" |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` | Rótulo "Documento (termo + anamnese)", alertas abaixo, "Pedir nova assinatura" |
| `frontend/src/pages/agenda/components/TermoPendenteBadge.tsx` | Texto **DOCS**, título "Termo e anamnese pendentes" |
| `frontend/src/pages/documentos/DocumentosPage.tsx`, `components/TermoDeConsentimento.tsx` | Aba "Termo e anamnese"; respostas, alertas, renovar |
| `frontend/src/pages/configuracoes/components/ResponsavelTecnica.tsx` | Texto cita "termo e anamnese" e a versão vigente |
| testes do frontend correspondentes | Casos novos |
| `docs/work/prd/038-...md`, `TASKS_LOG.md` | Status ao final |

## 4. Arquivos a remover

Nenhum. O gerador do 036 (`docs/work/assets/036-tcle/`) fica como histórico
da versão `2026-11`.

---

## 5. Ordem de implementação

1. `anamnese.py` + `test_anamnese.py` (catálogo é a base de tudo).
2. Migrations em `setup_database.py` (idempotentes), rodar em dev.
3. `consentimento.py`: `FILLING`, `guarda_respostas`, `inicia` com respostas, `renova`, painel. Testes.
4. Rotas: `checkin.py` (`PUT anamnesis`, catálogo no `bootstrap`), `consent/router.py` (`renew`). Testes.
5. Deploy dev do scheduler. Modelo compilado criado no sandbox pela API (reusar o script do 036); `/dev/CLICKSIGN_TCLE_TEMPLATE_KEY` e `/dev/TCLE_VERSION=2026-12`; redeploy.
6. iPad: tipos, serviço, `SimNao`, `AnamneseStep`, `ConsentDataStep` sem API, `CheckinPage`. Testes, build, deploy `checkin-dev`.
7. Painel: tipos, serviço, `RespostasDaAnamnese`, `AlertasDaAnamnese`, popover, aba, selo DOCS, configurações. Testes, build.
8. E2E em dev com assinatura real do documento compilado (seção 8), doc de integração, Postman, mocks, status do PRD, TASKS_LOG.
9. Prod, só com confirmação: migrations, deploy, modelo na conta de produção, SSM, `checkin-prod`.

---

## 6. Detalhes por arquivo

### `scheduler/src/services/anamnese.py` (criar)

- `VERSAO_DA_FICHA = "03"` (só informativo; a versão que governa é `TCLE_VERSION`).
- `PERGUNTAS`: tupla de `Pergunta` (NamedTuple) na ordem do PDF:
  `chave`, `tela` (1 a 4), `secao` (título da seção da ficha), `texto`,
  `tipo` (`SIM_NAO` | `TEXTO` | `FOTOTIPO`), `condicional_de` (chave da
  pergunta Sim/Não que a habilita, ou `None`), `rotulo` (o "Se sim, quais?"),
  `obrigatoria` (bool; `queixa_principal` sim, `observacoes` não, condicionais
  sim quando habilitadas), `alerta` (bool).
  Chaves exatamente as do gerador do modelo (`gera_modelo.js`), 51 no total:
  `queixa_principal`; `gestante`, `amamentando`, `hormonal`, `hormonal_quais`,
  `doenca_pele`, `doenca_pele_quais`, `doenca_pele_controlada`, `autoimune`,
  `autoimune_qual`, `imunossupressao`, `epilepsia`, `cancer`, `cancer_detalhe`,
  `diabetes`, `diabetes_controlada`, `alergia`, `alergia_quais`; `medicamento`,
  `medicamento_quais`, `isotretinoina`, `isotretinoina_ultima_dose`,
  `fotossensibilizante`, `fotossensibilizante_quais`, `minoxidil`,
  `minoxidil_qual`; `tatuagem`, `peeling_30d`, `cera_30d`, `foliculite`,
  `herpes_area`, `silicone`, `procedimentos_30d`, `procedimentos_30d_quais`,
  `queloide`, `acidos`, `acidos_quais`, `lesao_ativa`, `lesao_ativa_quais`;
  `atividade_fisica`, `atividade_fisica_detalhe`, `fuma`, `alcool`,
  `acompanhamento_medico`, `acompanhamento_medico_quais`; `laser_antes`,
  `laser_antes_reacao`, `laser_antes_sessoes`; `observacoes`; `fototipo`.
  Telas: 1 = seções 1 e 2; 2 = seção 3; 3 = seção 4; 4 = seções 5, 6, 7 e
  fototipo. `doenca_pele_controlada` e `diabetes_controlada` são `SIM_NAO`
  condicionais (de `doenca_pele` e `diabetes`). `isotretinoina_ultima_dose` é
  `TEXTO` com validação de data `dd/mm/aaaa` (aceita parcial `mm/aaaa`).
- `ALERTAS`: chaves com `alerta=True`: `gestante`, `amamentando`,
  `isotretinoina`, `fotossensibilizante`, `herpes_area`, `lesao_ativa`,
  `tatuagem`, `peeling_30d`, `cera_30d`, `cancer`, `imunossupressao`,
  `queloide`, `epilepsia`; mais a regra composta `diabetes` = Sim **e**
  `diabetes_controlada` = Não (rótulo "Diabetes não controlada").
- `catalogo() -> dict`: o que vai para o iPad e o painel:
  `{"version": "03", "screens": [{"n": 1, "questions": [{key, text, type,
  conditionalOf, label, required, section}]}]}`. Sem a flag `alerta` (o iPad
  não precisa; o painel recebe os alertas prontos).
- `valida_tela(n, respostas) -> dict`: normaliza as respostas da tela `n`
  (`bool` para Sim/Não; `str` aparada, até 300 caracteres; fototipo em
  `I..VI`), exige as obrigatórias habilitadas, descarta condicionais cujo pai
  é Não. Levanta `AnamneseInvalida(mensagem, campo)`.
- `valida_completa(respostas) -> dict`: `valida_tela` para 1..4 e exige que
  todas as Sim/Não existam. É o que `inicia` chama.
- `variaveis(respostas) -> Dict[str, str]`: uma por chave: `"Sim"`/`"Não"`
  para Sim/Não, texto ou `"-"`, fototipo `"III"`. Sempre as 51 chaves.
- `alertas(respostas) -> List[Dict]`: `[{"key": "gestante", "label":
  "Gestante"}, ...]` na ordem do catálogo, só os disparados.
- Teste de integridade: `test_anamnese.py` lê `gera_modelo.js` com regex e
  afirma que o conjunto de chaves da ficha no modelo é igual ao de `PERGUNTAS`
  (mesma lógica do teste que confere as 17 do 036, se existir; senão criar).

### `scheduler/src/scripts/setup_database.py` (modificar)

Migrations (lista `MIGRATIONS`, idempotentes) e `CREATE TABLE` em sincronia:

```sql
ALTER TABLE scheduler.patient_consents ADD COLUMN IF NOT EXISTS answers JSONB;
ALTER TABLE scheduler.patient_consents ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;
ALTER TABLE scheduler.patient_consents ADD COLUMN IF NOT EXISTS revoked_by VARCHAR(120);
ALTER TABLE scheduler.patient_consents DROP CONSTRAINT IF EXISTS patient_consents_status_check;
ALTER TABLE scheduler.patient_consents ADD CONSTRAINT patient_consents_status_check
  CHECK (status IN ('FILLING','SIGNING','SIGNED','CANCELLED','EXPIRED','PAPER','REVOKED'));
DROP INDEX IF EXISTS scheduler.uq_patient_consents_assinando;
CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_consents_em_andamento
  ON scheduler.patient_consents (clinic_id, patient_id) WHERE status IN ('FILLING','SIGNING');
```

`answers` fica `NULL` nas linhas da versão `2026-11`. `REVOKED` é o
"pedir nova assinatura": sai do índice de vigente, então `vigente()` volta
`None` e o check-in pede de novo. O nome do constraint deve ser conferido em
dev (`\d scheduler.patient_consents`) antes do `DROP`.

### `scheduler/src/services/consentimento.py` (modificar)

- Constantes: `RESPONDENDO = "FILLING"`, `REVOGADO = "REVOKED"`.
  `NOME_DO_PDF` fica; o PDF continua `tcle-assinado.pdf` (histórico).
- `_signing_da_paciente` → `_em_andamento(db, clinic_id, patient_id)`:
  `status IN ('FILLING','SIGNING')`.
- **`guarda_respostas(db, clinic_id, phone, appointment_id, tela, respostas)
  -> dict`** (rota `PUT anamnesis`): valida sessão/agendamento como `inicia`
  (`_agendamento_do_numero`, já existe); `anamnese.valida_tela`; se houver
  linha `FILLING`, `UPDATE answers = answers || %s`; senão `INSERT` com
  `status='FILLING'`, `term_version=versao()`, `signer_kind` provisório
  `PATIENT`, `answers`. Se houver `SIGNING` (envelope aberto), descarta-o
  primeiro com `_descarta_signing(..., "nova resposta")` e cria `FILLING`:
  mudar resposta depois de abrir o envelope invalida o envelope. Devolve
  `{"anamnesis": {"screen": n, "answered": [chaves], "complete": bool}}`.
- **`inicia`**: antes do provedor, carrega a linha `FILLING` da paciente
  (`_em_andamento`); sem ela ou com `anamnese.valida_completa` falhando →
  `ConsentimentoInvalido("Responda a ficha de anamnese antes de assinar.")`.
  O reaproveitamento de `SIGNING` continua, com `_mesmos_dados` comparando
  também `snapshot["respostas"] == respostas`. Na criação: a linha `FILLING`
  vira a linha `SIGNING` por `UPDATE ... WHERE id = %s AND status = 'FILLING'`
  (em vez de `INSERT`), preenchendo os campos do signatário, snapshot
  (`+ "respostas"`), `image_authorized`, provedor e ids. Se o `UPDATE` não
  afetar linha (corrida), cancela o envelope e devolve o existente, como hoje
  no `IntegrityError`.
- `_dados_do_modelo` += `anamnese.variaveis(respostas)` (merge; as 17 chaves
  do termo têm precedência, nenhuma colide).
- **`renova(db, clinic_id, consent_id, autor)`** (painel): linha `SIGNED` ou
  `PAPER` → `status='REVOKED', revoked_at=NOW(), revoked_by=autor`. Devolve
  `para_o_painel`. 404 se não vigente.
- `para_o_painel(row)` += `answers` (dict ou `None`), `alertas`
  (`anamnese.alertas(answers)` ou `[]`), `revoked_at`, `revoked_by`,
  `has_anamnesis: answers is not None`.
- `resumo_para_o_ipad` += `anamnesisPrefill`: `answers` da linha `FILLING`
  (ou `SIGNING` reaproveitável) da paciente, ou `None`. Assim "Recomeçar" e
  queda de rede voltam com o que já foi respondido.
- `lista_do_paciente` continua; a linha `FILLING` aparece como pendente.
- `dispensa`, `registra_papel`, webhook: sem mudança. `_fecha` idem.

### `scheduler/src/functions/public_booking/checkin.py` (modificar)

- `ROTAS` += `("PUT", r"^appointments/({UUID})/anamnesis$", "anamnesis")`,
  incluída em `CONSENTIMENTO` (exige provedor e versão como as outras).
  Body: `{phone, token, screen: 1..4, answers: {chave: valor}}`. Resposta
  200 `{"status": "SUCCESS", "anamnesis": {...}}`. Erros: 400 com `campo`
  (`{"status": "ERROR", "message", "field"}`) para o iPad marcar o campo.
- `bootstrap` += `"anamnesis": anamnese.catalogo()` quando `versao()` estiver
  configurada, senão `null`. O iPad não precisa carregar o catálogo em outra
  chamada.

### `scheduler/src/functions/consent/router.py` (modificar)

- `POST {UUID}/renew` → `consentimento.renova`, permissão `agenda.escrever`,
  autor como em `waive`. 200 com `{"status": "SUCCESS", "consent": {...}}`.
- `GET patients/{id}` não muda de assinatura; `para_o_painel` já traz
  `answers` e `alertas`. Permissão continua `prontuario.ler`
  (`test_rotas_abertas_ao_staff` inalterado).

### `scheduler/src/functions/appointment/list.py` (modificar)

- Só comentário: `FILLING` cai no `ELSE 'SIGNING'` da LATERAL, ou seja,
  pendente. `REVOKED` não entra no `IN ('SIGNED','PAPER')`, então a paciente
  volta a aparecer como pendente. Nenhuma query muda.

### `checkin/src/types/index.ts` (modificar)

```ts
export type AnamneseTipo = 'SIM_NAO' | 'TEXTO' | 'FOTOTIPO'
export interface AnamnesePergunta { key: string; text: string; type: AnamneseTipo;
  conditionalOf: string | null; label: string | null; required: boolean; section: string }
export interface AnamneseTela { n: number; questions: AnamnesePergunta[] }
export interface AnamneseCatalogo { version: string; screens: AnamneseTela[] }
export type AnamneseRespostas = Record<string, boolean | string>
// BootstrapResponse += anamnesis: AnamneseCatalogo | null
// CheckinAppointment += anamnesisPrefill: AnamneseRespostas | null
```

### `checkin/src/services/checkin.service.ts` e `hooks/useCheckin.ts` (modificar)

- `saveAnamnesis(clinicId, s, appointmentId, screen, answers)` → `PUT
  .../appointments/{id}/anamnesis`. Hook `useSaveAnamnesis(clinicId, session)`
  (mutation). `startConsent` inalterado.

### `checkin/src/components/ui/SimNao.tsx` (criar)

- Dois botões de 64px lado a lado, `role="radiogroup"` com `aria-label` =
  pergunta, selecionado em destaque, nenhum selecionado por padrão. Erro
  abaixo quando obrigatório e vazio.

### `checkin/src/steps/AnamneseStep.tsx` (criar)

- Props: `clinicId`, `session`, `appointment`, `catalogo`, `tela` (1..4),
  `respostas`, `onChange(respostas)`, `onBack`, `onNext(respostas)` (chamado
  depois do `PUT` com sucesso), `onFinish(respostas)` na tela 4.
- Renderiza as perguntas da tela: `SIM_NAO` → `SimNao`; `TEXTO` → `TextField`
  (teclado do iPad, `maxLength` 300) só quando `conditionalOf` está `true`;
  `FOTOTIPO` → seis cartões com o texto de cada opção, um selecionável.
- Cabeçalho "Ficha de anamnese", progresso "Tela 2 de 4", botões "Voltar" e
  "Continuar" (64px). Validação local espelha a do backend (obrigatórias,
  condicionais); o erro do backend (`field`) também aponta o campo.
- Ao "Continuar": `useSaveAnamnesis.mutate({screen, answers da tela})`;
  sucesso → `onNext`. Na tela 4 → `onFinish`.

### `checkin/src/steps/ConsentDataStep.tsx` (modificar)

- Remove `useStartConsent`. `onStarted` vira `onContinue(payload:
  ConsentStartPayload)`. Validação e layout iguais. Botão "Continuar para a
  ficha de anamnese".

### `checkin/src/pages/CheckinPage.tsx` (modificar)

- Estados: `consent-data` (igual) → `anamnese` (`{ tela, respostas,
  consentPayload } & Paying`) → `consent-start` (chama `useStartConsent` com
  o `consentPayload`, mostra spinner "Preparando o documento…", erro com
  "Tentar de novo") → `consent-sign` (igual).
- `respostas` iniciais = `appointment.anamnesisPrefill ?? {}`.
- `LONG_IDLE_STEPS` += `anamnese` (5 min; é leitura e toques lentos).
- `reset` continua limpando as queries de consent.

### `checkin/src/pages/CheckinPage.test.tsx` (modificar)

- Fluxo completo: dados → 4 telas (uma condicional aparece ao marcar Sim,
  some ao marcar Não) → `startConsent` chamado com o payload dos dados →
  assinatura (simulada) → pagamento.
- `PUT` chamado uma vez por tela com só as chaves da tela.
- Prefill: `anamnesisPrefill` preenche e a tela 1 abre já respondida.
- Erro 400 com `field` marca o campo e não avança.
- Sem catálogo no bootstrap (versão desligada) o fluxo é o de hoje.

### `frontend/` (modificar)

- `types`: `PatientConsent` += `answers: Record<string, boolean | string> |
  null`, `alertas: {key, label}[]`, `has_anamnesis`, `revoked_at`,
  `revoked_by`; `ConsentStatus` += `'FILLING' | 'REVOKED'`.
- `consents.service.renovar(clinicId, consentId)`; `useRenovarTermo`
  invalida `consents` do paciente e `appointments`.
- `utils/termo.ts`: `FILLING` → pendente, label "Respondendo a ficha";
  rótulos passam a falar "documento".
- `AlertasDaAnamnese` (`alertas: {key,label}[]`): lista `text-red-700`, ícone
  de atenção, "Alertas da anamnese" como título pequeno; vazio → nada.
- `TermoDoAgendamento`: título "Termo e anamnese"; abaixo do estado, `<AlertasDaAnamnese
  alertas={vigente?.alertas ?? []}>`; ação "Pedir nova assinatura" (confirm
  inline, sem modal) quando vigente.
- `RespostasDaAnamnese` (`consent: PatientConsent`): alertas no topo; uma
  seção por `section` do catálogo (o painel recebe `answers` por chave e
  precisa dos textos: a aba usa um mapa estático `ANAMNESE_PERGUNTAS` em
  `frontend/src/utils/anamnese.ts`, gerado a partir do catálogo do backend
  e conferido por teste contra o JSON `tests/mocks/.../anamnesis_catalog.json`
  versionado no repo); Sim/Não com `Sim` em destaque; textos; fototipo com a
  nota "autodeclarado; o tipo de pele do prontuário é o da profissional".
- `TermoDeConsentimento` (aba): título "Termo e anamnese"; para cada
  documento, o bloco atual + `RespostasDaAnamnese` quando `has_anamnesis`;
  botão "Pedir nova assinatura" no vigente.
- `TermoPendenteBadge`: texto `DOCS`; título "Termo e anamnese pendentes".
- `DocumentosPage`: rótulo da aba "Termo e anamnese" (id `termo` mantido para
  não quebrar links).
- `ResponsavelTecnica`: texto menciona "termo e anamnese"; mostra `term_version`
  vigente vinda de `consent_enabled`/versão (já exposta em `ListConsentsResponse`;
  se não, acrescentar `term_version` ali).
- Testes: `AlertasDaAnamnese.test`, `RespostasDaAnamnese.test`,
  `TermoDoAgendamento.test` (+alertas, +renovar), `TermoDeConsentimento.test`
  (+respostas), `TermoPendenteBadge.test` (DOCS), `termo.test` (FILLING).

### `scheduler/tests/unit/test_consentimento.py` (modificar)

- Fake `Db`: `UPDATE ... answers = answers || %s`, `INSERT ... 'FILLING'`,
  `UPDATE ... WHERE id = %s AND status = 'FILLING'` (vira SIGNING),
  `status IN ('FILLING','SIGNING')`, `status = 'REVOKED'`.
- Casos: `guarda_respostas` cria `FILLING` e acumula por tela; tela inválida
  400 com campo; `inicia` sem ficha completa falha; `inicia` com ficha
  completa vira SIGNING na mesma linha e as variáveis do modelo trazem
  `gestante: "Não"` etc.; mudar resposta com SIGNING aberto descarta o
  envelope; `_mesmos_dados` com respostas iguais reaproveita, diferentes não;
  `renova` marca REVOKED e `precisa_assinar` volta a ser `True`; `para_o_painel`
  traz `alertas` certos (incluindo diabetes composto) e `answers`.

### `scheduler/tests/integration/038-ficha-de-anamnese-no-checkin.md` (criar)

- Estado em dev, achados (modelo compilado no sandbox, 68 variáveis, 8
  páginas), roteiro E2E (seção 8), curls das rotas novas, pendências.

---

## 7. Convenções a respeitar

- Logging `[Consentimento]`, `[Anamnese]`, `[ClicksignWebhook]` como no 036.
- Secrets e versão só no SSM: `/${stage}/TCLE_VERSION`,
  `/${stage}/CLICKSIGN_TCLE_TEMPLATE_KEY`. Nada de chave em código ou doc.
- Migrations idempotentes; `CREATE TABLE` em sincronia.
- Dado de paciente real nunca em teste, commit, PR ou doc (nome fictício).
- Frontend: named exports, 4 estados, zero `any`, TanStack Query, lint zero
  warnings. iPad: alvos ≥ 64px, nada abre fora da página.
- Deploys: dev e prod nunca em paralelo; scheduler sempre de árvore que
  contém `origin/main`; `checkin-*` pela CLI com o id do projeto.

---

## 8. Roteiro E2E (dev)

1. Modelo compilado criado no sandbox (já existe: `1d2b35f6`); gravar
   `/dev/CLICKSIGN_TCLE_TEMPLATE_KEY` = esse id e `/dev/TCLE_VERSION=2026-12`;
   deploy dev.
2. Paciente de teste sem documento na versão `2026-12`: o check-in pede dados
   → 4 telas → "Preparando o documento…" → widget com o PDF de 8 páginas.
3. Assinar de verdade (token no WhatsApp + manuscrita). Conferir: webhook
   `document_closed`/`auto_close` → SIGNED, PDF no S3 com as respostas, aba
   "Termo e anamnese" com respostas e alertas, popover com alertas.
4. "Pedir nova assinatura" no painel → próximo check-in pede de novo e o
   prefill vem vazio (REVOKED não é FILLING).
5. "Recomeçar" no meio da tela 3 → novo check-in abre a tela 1 já respondida.
6. Alterar uma resposta depois de ter aberto o widget → envelope antigo
   cancelado, novo criado.

---

## Status

- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
