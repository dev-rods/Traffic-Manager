# Spec - 036 Termo de consentimento (TCLE) assinado no check-in

> Gerada na fase **Spec** em 03/11/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/036-termo-de-consentimento.md`

---

## 1. Resumo

Dois passos novos no app do iPad (`checkin/`), entre confirmar o agendamento
e escolher a forma de pagamento: `consent-data` (confirmar ou completar nome,
CPF, nascimento, celular e e-mail; escolher uso de imagem; responsável legal
se menor) e `consent-sign` (widget embedded da ClickSign). No backend, um
provedor de assinatura com a mesma forma do de pagamento (`SignatureProvider`
com ClickSign v3 e simulado), um serviço `consentimento.py` que é o único
lugar que decide "precisa assinar", quatro sub-rotas na coringa do check-in,
um webhook com HMAC e um bucket S3 privado para o PDF assinado. No painel,
estado e ações do termo no detalhe do agendamento, selo na agenda do dia, aba
na pasta de Documentos, e os campos de profissional responsável, cidade e
registro no conselho. Uma Lambda nova `Consentimento` (coringa) e uma
`UpdateProfessional` servem o painel.

Achados da pesquisa que mudam o plano do PRD:

- **Permissões.** `agenda.ler` / `agenda.escrever` existem no backend
  (`PERMISSOES_DO_STAFF`, `src/utils/acesso.py:55`) e é `require_acesso`
  quem as impõe. O painel não checa permissão no cliente, só `ehAdmin`. As
  ações do termo seguem o mesmo padrão do "Recebi em dinheiro": visíveis
  para quem abre o detalhe, recusadas no servidor.
- **Profissionais não têm endpoint de atualização.** Só `Create` e `List`.
  O registro no conselho exige `PUT clinics/{clinicId}/professionals/{id}`
  (Lambda nova, cerca de 6 recursos do CloudFormation). `responsible_professional_id`
  e `cidade` entram no `UpdateClinic` existente, sem rota nova.
- **O iframe da ClickSign não reinicia o contador de inatividade** do iPad
  (`useIdleReset` escuta `window`; toques dentro de um iframe de outra origem
  não chegam). O passo `consent-sign` usa o prazo de 5 min do pagamento.
- **Widget embedded no v3.** A lista de `auth` da API inclui
  `embedded_signature`. A documentação não diz se o widget exige esse valor
  ou se basta `whatsapp` + `handwritten`. O provedor envia os três requisitos
  de evidência e a primeira tarefa do E2E em dev é confirmar o que o sandbox
  aceita; se `embedded_signature` for recusado como combinação, cai para
  `whatsapp` + `handwritten`. A decisão fica registrada no doc de integração.
- **Webhook por HMAC do corpo**, não por token: header `Content-Hmac:
  sha256=<hex>` (a doc também cita `x-clicksign-signature`; o handler lê
  os dois). É diferente do Asaas, que compara um token fixo.
- **Download com validade de 5 min.** O PDF assinado vem por URL temporária
  no documento (`downloads`/`signed_file_url`); o serviço baixa na hora e
  grava no S3. O log de auditoria da ClickSign já vem como páginas finais
  do PDF assinado; o `.zip` (original + assinado) é guardado quando a API o
  oferecer, em `audit_s3_key`.
- **A ClickSign v3 não cancela envelope ativo** (sondado no sandbox em
  03/11): `DELETE` só em draft, `PATCH status` só `draft`/`running`. Um
  `SIGNING` abandonado morre pelo `deadline_at` (2 dias). E o vencimento, por
  padrão, FECHA o envelope sem assinatura (`deadline_partial_signature_action:
  closed`); o provedor manda `canceled`, para `closed` significar assinado.
  Detalhes em `scheduler/tests/integration/036-termo-de-consentimento.md`.
- **Runtime python3.8**: sem `match`, sem `X | Y` em tipos, sem
  `dict | dict`.
- **Stack em 466/500.** Consentimento (~6) + UpdateProfessional (~6) +
  rota do webhook (~4) ≈ 482. Conferido no deploy de dev em 04/11: **482**
  (`aws cloudformation list-stack-resources --stack-name clinic-scheduler-infra-dev --query "length(StackResourceSummaries)"`;
  o `describe-stack-resources` para em 100).

Desvios da implementação (04/11/2026), todos registrados no código:

- A lista do painel é `GET consents/patients/{patientId}` (não `?patientId=`):
  a coringa `{proxy+}` exige pelo menos um segmento.
- Os campos numéricos da tela de dados do iPad usam o teclado do iPad
  (`TextField` com `inputMode`), não o `Keypad`: são cinco a dez campos numa
  tela só, e nome e e-mail já exigem o teclado.
- `appointment/list.py` manda `consent_enabled` também por linha, para o selo
  da agenda receber só o agendamento.
- O widget recebe o `id` do signatário (`signerId`); se o embedded pedir outra
  chave, muda-se só `_para_tela`. A confirmar no E2E, junto com
  `embedded_signature` e o nome real do evento do webhook v3 (doc de
  integração, "Pendências a confirmar").

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/src/providers/signature_provider.py` | Interface `SignatureProvider`, tipos `Signatario`, `TermoCriado`, exceções `AssinaturaIndisponivel`, `ErroDoProvedor`, `provedor_ativo()`, `termo_de_teste()` |
| `scheduler/src/providers/clicksign_provider.py` | API v3 (JSON:API): envelope → documento via modelo → signatário → requisitos → ativar; consulta; download; cancela |
| `scheduler/src/providers/simulated_signature_provider.py` | Só dev sem chave: ids falsos, `simula` fecha, PDF de teste gerado localmente |
| `scheduler/src/services/consentimento.py` | Regra do gatilho, snapshots, criação, status com reserva do webhook, aplicação de evento, dispensa, papel, URLs assinadas |
| `scheduler/src/services/documentos_s3.py` | `grava(chave, bytes) -> sha256`, `url_assinada(chave, segundos=300)`; único ponto que fala com o bucket privado |
| `scheduler/src/functions/public_booking/clicksign_webhook.py` | `POST public/clicksign/webhook`: HMAC, parse, `consentimento.aplica_evento` |
| `scheduler/src/functions/consent/router.py` | Lambda `Consentimento`, coringa `clinics/{clinicId}/consents/{proxy+}` |
| `scheduler/src/functions/professional/update.py` | `PUT clinics/{clinicId}/professionals/{professionalId}`: `name`, `role`, `registro_conselho`, `active` |
| `scheduler/sls/functions/consent/interface.yml` | Lambda `Consentimento` + IAM `s3:GetObject` no bucket privado |
| `scheduler/sls/resources/s3/documentos-bucket.yml` | Bucket privado `${resourcePrefix}-documentos` |
| `scheduler/tests/unit/test_consentimento.py` | Serviço com `Db` falso e `Provedor` falso (mesmo molde de `test_checkin.py`) |
| `scheduler/tests/unit/test_clicksign_provider.py` | Montagem dos payloads JSON:API e leitura das respostas, com `requests` mockado |
| `scheduler/tests/unit/test_clicksign_webhook.py` | HMAC certo/errado/ausente, segredo vazio, corpo inválido, evento repetido, rota no router e no yml |
| `scheduler/tests/unit/test_consent_router.py` | Rotas do painel: permissão, clínica errada, dispensa, papel, URLs |
| `scheduler/tests/integration/036-termo-de-consentimento.md` | Roteiro E2E em dev (sandbox) e casos curl |
| `scheduler/tests/postman/036-termo-de-consentimento.postman_requests.json` | Requests públicas, webhook e painel |
| `checkin/src/steps/ConsentDataStep.tsx` | Confirmar/completar dados, uso de imagem, responsável |
| `checkin/src/steps/ConsentSignStep.tsx` | Widget embedded ou botão de simulação; polling do status |
| `checkin/src/lib/clicksignWidget.ts` | Carrega o script oficial uma vez e monta/desmonta o widget; sem `any` |
| `checkin/src/components/ui/TextField.tsx` | Campo de texto grande para nome e e-mail (teclado do iPad), 64 px de altura |
| `frontend/src/services/consents.service.ts` | HTTP do painel: lista por paciente, dispensar, papel, URLs |
| `frontend/src/hooks/useConsents.ts` | TanStack: `useConsentsDoPaciente`, `useDispensarTermo`, `useRegistrarPapel`, `useUrlDoTermo` |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` | Linha "Termo" no detalhe + botões Dispensar / Assinado em papel |
| `frontend/src/pages/agenda/components/TermoPendenteBadge.tsx` | Selo "Termo pendente", mesmo molde de `ConfirmacaoBadge` |
| `frontend/src/pages/documentos/components/TermoDeConsentimento.tsx` | Aba com as versões, PDF e zip por URL assinada |
| `frontend/src/pages/configuracoes/components/ResponsavelTecnica.tsx` | Select da responsável, cidade e registro por profissional |
| Testes Vitest ao lado de cada componente novo (`*.test.tsx`) | Ver §6 |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/scripts/setup_database.py` | Bloco PRD 036 em `SQL_STATEMENTS` (§6) e colunas nos `CREATE TABLE` de `clinics`, `professionals`, `appointments` |
| `scheduler/src/services/checkin.py` | `agendamentos_do_numero` ganha `consentRequired` e `consentPrefill` por item (via `consentimento.resumo_para_o_ipad`); `confirma` devolve também `consentRequired` |
| `scheduler/src/functions/public_booking/checkin.py` | Três entradas em `ROTAS` (`consent`, `consent_status`, `consent_simula`) e os ramos no `handler`; mapeia `AssinaturaIndisponivel` → 503 e `ConsentimentoInvalido` → 400 |
| `scheduler/src/functions/public_booking/router.py` | Import e rota `("POST", "public/clicksign/webhook")` |
| `scheduler/sls/functions/public_booking/interface.yml` | Evento http do webhook (sem cors) e IAM `s3:PutObject`/`s3:GetObject` no bucket privado |
| `scheduler/sls/functions/professional/interface.yml` | Lambda `UpdateProfessional` |
| `scheduler/src/functions/professional/list.py` | SELECT já é `*`; nada a fazer além de conferir que `registro_conselho` sai na resposta |
| `scheduler/src/functions/clinic/update.py` | `ALLOWED_FIELDS` += `responsible_professional_id`, `cidade`; validação: a profissional é da clínica e está ativa |
| `scheduler/src/functions/public_booking/bootstrap.py` | Nada: a clínica do iPad continua vindo do bootstrap; o termo não precisa dela no cliente |
| `scheduler/src/functions/appointment/list.py` | SELECT ganha `consent_waived_at`, `consent_waived_reason` e LATERAL `consent_status` (ver §6) para o selo e o detalhe |
| `scheduler/serverless.yml` | `custom.clicksignBaseUrl` por stage; env `CLICKSIGN_API_KEY`, `CLICKSIGN_WEBHOOK_SECRET`, `CLICKSIGN_TCLE_TEMPLATE_KEY`, `TCLE_VERSION`, `CLICKSIGN_BASE_URL`, `DOCUMENTOS_BUCKET`; resource do bucket |
| `scheduler/requirements.txt` | Nada novo: `requests` e `boto3` já estão lá (conferir) |
| `checkin/src/pages/CheckinPage.tsx` | Estados `consent-data` e `consent-sign`; `next()` passa pelo termo antes de `method`; idle de 5 min no `consent-sign` |
| `checkin/src/steps/AppointmentStep.tsx` | `onConfirmed(appointment, payerCpfKnown, consentRequired)` |
| `checkin/src/services/checkin.service.ts` | `startConsent`, `consent`, `simulateConsent` |
| `checkin/src/hooks/useCheckin.ts` | `useStartConsent`, `useConsentStatus` (polling 3 s), `useSimulateConsent` |
| `checkin/src/types/index.ts` | `CheckinAppointment.consentRequired`, `ConsentPrefill`, `Consent`, `ConsentStartPayload` |
| `checkin/src/pages/CheckinPage.test.tsx` | Fluxo com termo (simulado) e sem termo |
| `checkin/CLAUDE.md` | Parágrafo sobre o termo e o modo simulado |
| `frontend/src/types/index.ts` | `Appointment` += `consent_status`, `consent_waived_at`, `consent_waived_reason`; `Clinic`/`UpdateClinicPayload` += `responsible_professional_id`, `cidade`; `PatientConsent`, `ConsentWaiveReason` |
| `frontend/src/services/professionals.service.ts` | `Professional.registro_conselho`; `update(clinicId, id, payload)` |
| `frontend/src/hooks/useProfessionals.ts` | `useUpdateProfessional` |
| `frontend/src/pages/agenda/components/PagamentoDoAgendamento.tsx` | Renderiza `<TermoDoAgendamento>` acima da linha "Pagamento" |
| `frontend/src/pages/agenda/components/AgendaDoDia.tsx`, `WeekGrid.tsx` | `<TermoPendenteBadge>` ao lado de `ConfirmacaoBadge` |
| `frontend/src/pages/documentos/DocumentosPage.tsx` | `nav` vira abas de verdade (`?doc=historico|termo`), segunda aba `TermoDeConsentimento` |
| `frontend/src/pages/configuracoes/ConfiguracoesPage.tsx` | Seção "Responsável técnica e termo" com `ResponsavelTecnica` |
| `docs/work/prd/036-termo-de-consentimento.md` | Status: Spec gerada; corrigir §7 (permissões no servidor, rota de profissional) |
| `docs/work/prd/014-ficha-de-anamnese.md` | Fora desta entrega; fica para o PR seguinte |

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação

1. **Banco.** Bloco 036 em `setup_database.py`; `CREATE TABLE` atualizados. Rodar em dev.
2. **Provedor.** `signature_provider.py`, `simulated_signature_provider.py`, `clicksign_provider.py` + `test_clicksign_provider.py`. Rodar uma criação real no sandbox por script (`python -c`) e anotar no doc de integração quais `auth` o widget aceitou.
3. **S3.** `documentos-bucket.yml`, `documentos_s3.py`, env e IAM. Deploy dev só do stack para o bucket nascer.
4. **Serviço + rotas públicas.** `consentimento.py`, mudanças em `checkin.py` (serviço e handler), webhook, router, yml + `test_consentimento.py`, `test_clicksign_webhook.py`, ajustes em `test_checkin.py`. Deploy dev. Cadastrar o webhook na conta sandbox apontando para `/dev/public/clicksign/webhook`, gravar `/dev/CLICKSIGN_WEBHOOK_SECRET`, redeploy.
5. **iPad.** Tipos, service, hooks, `clicksignWidget.ts`, `TextField`, os dois passos, `CheckinPage` + testes. `npm run build`, `lint`, `test`. Deploy `checkin-dev`. E2E no sandbox: token no WhatsApp, manuscrita, webhook, PDF no S3.
6. **Painel, backend.** `consent/router.py`, `professional/update.py`, `clinic/update.py`, `appointment/list.py`, ymls + `test_consent_router.py`. Deploy dev. Conferir a contagem de recursos.
7. **Painel, frontend.** Tipos, services, hooks, componentes, abas, configurações + testes. `npm run build` e `lint`.
8. **Docs.** Integração, Postman, `checkin/CLAUDE.md`, status do PRD, `TASKS_LOG.md`.
9. **Prod.** Migrations em prod; `/prod/CLICKSIGN_TCLE_TEMPLATE_KEY` e `/prod/TCLE_VERSION` gravados; `serverless deploy --stage prod`; cadastrar o webhook na conta de produção, gravar `/prod/CLICKSIGN_WEBHOOK_SECRET`, redeploy; `checkin-prod` pela CLI; painel pela Vercel no merge. Cadastrar responsável, registro e cidade nas clínicas antes de ligar.

Até o passo 4 o backend já recusa o pagamento de quem não assinou? **Não.** O backend não bloqueia `cobra` pelo termo; o bloqueio é do fluxo do iPad (decisão 4 do PRD: a recepção segue pelo painel). Isso mantém o painel e o link de cobrança funcionando sem termo.

---

## 6. Detalhes por arquivo

### `scheduler/src/scripts/setup_database.py` (modificar)

Bloco `-- PRD 036` ao final de `SQL_STATEMENTS`:

```sql
ALTER TABLE scheduler.professionals ADD COLUMN IF NOT EXISTS registro_conselho VARCHAR(60);
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS responsible_professional_id UUID REFERENCES scheduler.professionals(id);
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS cidade VARCHAR(120);

ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS consent_waived_at TIMESTAMPTZ;
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS consent_waived_by VARCHAR(120);
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS consent_waived_reason VARCHAR(20);
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS consent_waived_note VARCHAR(200);

CREATE TABLE IF NOT EXISTS scheduler.patient_guardians (
    patient_id UUID PRIMARY KEY REFERENCES scheduler.patients(id),
    name VARCHAR(255) NOT NULL,
    cpf VARCHAR(11) NOT NULL,
    birth_date DATE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scheduler.patient_consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
    patient_id UUID NOT NULL REFERENCES scheduler.patients(id),
    appointment_id UUID REFERENCES scheduler.appointments(id),
    term_version VARCHAR(20) NOT NULL,
    status VARCHAR(12) NOT NULL CHECK (status IN ('SIGNING','SIGNED','CANCELLED','EXPIRED','PAPER')),
    signer_kind VARCHAR(10) NOT NULL CHECK (signer_kind IN ('PATIENT','GUARDIAN')),
    signer_name VARCHAR(255), signer_cpf VARCHAR(11), signer_birth_date DATE,
    signer_phone VARCHAR(20), signer_email VARCHAR(255),
    patient_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    image_authorized BOOLEAN,
    responsible_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    provider VARCHAR(20), provider_envelope_id VARCHAR(80),
    provider_document_id VARCHAR(80), provider_signer_id VARCHAR(80),
    pdf_s3_key VARCHAR(300), pdf_sha256 CHAR(64), audit_s3_key VARCHAR(300),
    signed_at TIMESTAMPTZ,
    paper_signed_at DATE, paper_registered_by VARCHAR(120),
    created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_consents_vigente
    ON scheduler.patient_consents (clinic_id, patient_id, term_version)
    WHERE status IN ('SIGNED','PAPER');
CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_consents_assinando
    ON scheduler.patient_consents (clinic_id, patient_id) WHERE status = 'SIGNING';
CREATE INDEX IF NOT EXISTS idx_patient_consents_provider_doc
    ON scheduler.patient_consents (provider_document_id);

CREATE TABLE IF NOT EXISTS scheduler.consent_webhook_events (
    event_id VARCHAR(120) PRIMARY KEY,
    provider VARCHAR(20) NOT NULL,
    event VARCHAR(60) NOT NULL,
    provider_document_id VARCHAR(80),
    payload JSONB,
    received_at TIMESTAMPTZ DEFAULT NOW()
);
```

- Mesmas colunas nos `CREATE TABLE` da lista (`clinics`, `professionals`, `appointments`), com comentário "PRD 036".
- `consent_waived_reason` sem CHECK no banco: o enum (`SEM_CELULAR`, `RECUSOU`, `SISTEMA_FORA`, `OUTRO`) é validado no serviço, para não exigir migration ao acrescentar motivo.
- `patient_guardians` com `cpf` em 11 dígitos normalizados (`normaliza_cpf`), ao contrário de `patients.cpf` (14, formato livre). Comentar.

### `scheduler/src/providers/signature_provider.py` (criar)

```python
class AssinaturaIndisponivel(Exception): ...   # 503
class ErroDoProvedor(Exception): ...           # 502

@dataclass
class Signatario:
    nome: str; cpf: str; nascimento: date; telefone: str; email: str

@dataclass
class TermoCriado:
    envelope_id: str; document_id: str; signer_id: str

class SignatureProvider:
    nome = ""
    pode_simular = False
    widget_endpoint = ""   # "https://sandbox.clicksign.com" | "https://app.clicksign.com" | "" (simulado)

    def cria_termo(self, template_key, filename, dados: Dict[str, str],
                   signatario: Signatario, referencia: str, prazo: datetime) -> TermoCriado
    def consulta(self, envelope_id) -> str          # "SIGNING" | "SIGNED" | "CANCELLED" | "EXPIRED"
    def baixa_pdf(self, envelope_id, document_id) -> bytes
    def baixa_zip(self, envelope_id, document_id) -> Optional[bytes]
    def cancela(self, envelope_id) -> None
    def simula(self, envelope_id) -> None           # só pode_simular

def termo_de_teste(provider_nome) -> bool   # simulado, ou clicksign com "sandbox" na base URL

def provedor_ativo() -> SignatureProvider:
    if os.environ.get("CLICKSIGN_API_KEY"): return ClicksignProvider(api_key, base_url=os.environ.get("CLICKSIGN_BASE_URL") or "https://sandbox.clicksign.com")
    if os.environ.get("STAGE") == "dev": return SimulatedSignatureProvider()
    raise AssinaturaIndisponivel("Nenhum provedor de assinatura configurado")
```

- `referencia` vai em `metadata` do documento e no `name` do envelope (`TCLE {referencia}`), para localizar no painel da ClickSign.

### `scheduler/src/providers/clicksign_provider.py` (criar)

- `requests` com timeout 20 s, headers `Authorization: Bearer {api_key}`, `Content-Type: application/vnd.api+json`, `Accept: application/vnd.api+json`. `_chama(metodo, caminho, payload=None)`: levanta `ErroDoProvedor` com status e a primeira mensagem de `errors[]` em qualquer 4xx/5xx; 429 idem (limite 20 req/10 s no sandbox).
- `widget_endpoint = base_url` (sem `/api/v3`).
- `cria_termo`, em sequência (cada chamada é um `POST` JSON:API `{"data": {"type": ..., "attributes": {...}}}`):
  1. `POST /api/v3/envelopes`: `name`, `locale: "pt-BR"`, `auto_close: true`, `remind_interval: null`, `deadline_at: prazo` (RFC 3339), `block_after_refusal: true`.
  2. `POST /api/v3/envelopes/{id}/documents`: `filename`, `template: {"key": template_key, "data": dados}`, `metadata: {"referencia": referencia}`.
  3. `POST /api/v3/envelopes/{id}/signers`: `name`, `email`, `phone_number` (DDD + número, 10 ou 11 dígitos, sem 55), `has_documentation: true`, `documentation` (CPF `000.000.000-00`), `birthday` (`YYYY-MM-DD`), `communicate_events: {"signature_request": "none", "signature_reminder": "none", "document_signed": "email"}` (a cópia assinada vai por e-mail; convite e lembrete não, porque a assinatura é no iPad). Conferir no sandbox os nomes aceitos em `communicate_events`; se `none` for recusado, omitir a chave.
  4. `POST /api/v3/envelopes/{id}/requirements` três vezes: `{"action": "agree", "role": "sign"}`, `{"action": "provide_evidence", "auth": "whatsapp"}`, `{"action": "provide_evidence", "auth": "handwritten"}`; e, se a constante `REQUISITOS_DE_EVIDENCIA` incluir, `embedded_signature` (ver §1). Cada um com `relationships.document` e `relationships.signer`.
  5. `PATCH /api/v3/envelopes/{id}`: `{"status": "running"}`.
  - Falha em qualquer passo depois do 1: tenta `cancela(envelope_id)` e relança `ErroDoProvedor`. Nunca deixa envelope `running` sem registro nosso.
- `consulta`: `GET /api/v3/envelopes/{id}` → `attributes.status`: `running` → `SIGNING`, `closed` → `SIGNED`, `canceled` → `CANCELLED`; `deadline` vencido com `running` → `EXPIRED`.
- `baixa_pdf`: `GET /api/v3/envelopes/{id}/documents/{doc}` → `attributes.downloads` (`signed_file_url` ou `signed`); segundo `GET` na URL (válida 5 min) → bytes. `baixa_zip` idem com `ziped_file_url`/`zip`, devolve `None` se ausente.
- `cancela`: `PATCH /api/v3/envelopes/{id}` `{"status": "canceled"}`; 4xx por já fechado é ignorado.
- `pode_simular = "sandbox" in base_url`; `simula` não existe na API: no sandbox, a simulação é assinar de verdade pelo widget. Logo `pode_simular = False` para a ClickSign; só o simulado simula. (Diferente do Asaas, que tem `/sandbox/.../confirm`.)
- Nomes de chave da resposta (`signed_file_url` x `downloads.signed`) lidos com fallback, porque a doc v3 e v1 divergem; o teste do provedor cobre os dois.

### `scheduler/src/providers/simulated_signature_provider.py` (criar)

- `nome = "simulado"`, `pode_simular = True`, `widget_endpoint = ""`.
- Estado em memória por processo (dict); `cria_termo` devolve ids `sim-{uuid}`; `consulta` devolve `SIGNING` até `simula`; `baixa_pdf` devolve um PDF mínimo gerado em Python puro (cabeçalho `%PDF-1.4`, uma página com o texto "TCLE DE TESTE - {referencia}"), `baixa_zip` → `None`.
- Fora de dev, `provedor_ativo` nunca o instancia; o construtor levanta `AssinaturaIndisponivel` se `STAGE != "dev"`, como segurança dupla.

### `scheduler/src/services/documentos_s3.py` (criar)

```python
BUCKET = os.environ.get("DOCUMENTOS_BUCKET", "")
def chave_do_termo(clinic_id, patient_id, consent_id, nome) -> str   # clinics/{c}/patients/{p}/consents/{id}/{nome}
def grava(chave, conteudo: bytes, content_type) -> str              # put_object com ServerSideEncryption AES256; devolve sha256 hex
def url_assinada(chave, segundos=300) -> str                        # generate_presigned_url get_object
```

- `boto3.client("s3")` criado uma vez por módulo. Sem bucket configurado, `grava` levanta `RuntimeError("DOCUMENTOS_BUCKET não configurado")`.

### `scheduler/src/services/consentimento.py` (criar)

Constantes e regras:

```python
VERSAO = os.environ.get("TCLE_VERSION", "")
TEMPLATE_KEY = os.environ.get("CLICKSIGN_TCLE_TEMPLATE_KEY", "")
MOTIVOS_DE_DISPENSA = ("SEM_CELULAR", "RECUSOU", "SISTEMA_FORA", "OUTRO")
REAPROVEITA_SIGNING_ATE = timedelta(hours=24)
PRAZO_DO_ENVELOPE = timedelta(days=2)

class ConsentimentoInvalido(Exception): ...   # 400 para o iPad
```

Funções:

- `vigente(db, clinic_id, patient_id) -> Optional[Dict]`: termo `SIGNED`/`PAPER` com `term_version = VERSAO`.
- `precisa_assinar(db, clinic_id, appt_row) -> bool`: `VERSAO` vazia → `False` (prod sem configuração não pede); `appt.consent_waived_at` → `False`; `vigente(...)` → `False`; senão `True`.
- `resumo_para_o_ipad(db, clinic_id, appt_row) -> Dict`: `{"consentRequired": bool, "consentPrefill": {...} | None}`. Prefill: `name`, `cpf` (mascarado `***.***.***-12`, e `cpfKnown`), `birthDate`, `phone` (o do agendamento), `email`, `isMinor` (`e_menor_de_idade(birth_date, appointment_date)`; `None` vira `False` e o iPad decide pela data digitada), `guardian` (de `patient_guardians`, CPF mascarado) e `clinicReady` (responsável e cidade cadastradas). Chamado por `checkin.agendamentos_do_numero` para cada item e por `checkin.confirma`.
- `inicia(db, provider, clinic_id, phone, appointment_id, dados: Dict) -> Dict`:
  1. `appt = checkin._do_numero(db, clinic_id, phone, appointment_id)` (posse, mesmo guard do pagamento).
  2. `precisa_assinar` falso → devolve o vigente/dispensa como `{"consent": {"status": "NOT_REQUIRED"}}`; o iPad segue.
  3. Clínica: `SELECT c.name, c.display_name, c.cidade, p.name, p.role, p.registro_conselho FROM clinics c LEFT JOIN professionals p ON p.id = c.responsible_professional_id AND p.active`. Sem responsável, sem registro ou sem cidade → `ConsentimentoInvalido("A clínica ainda não cadastrou a profissional responsável. Chame a recepção.")`.
  4. Valida `dados`: `fullName` com dois nomes; `cpf` por `normaliza_cpf` + `cpf_valido`; `birthDate` ISO, no passado; `email` com `@` e `.`; `imageAuthorized` booleano obrigatório. `menor = e_menor_de_idade(birthDate, appt.appointment_date)`; se menor, `guardian` obrigatório com os mesmos campos mais `phone` (normalizado por `normalize_phone`), e o CPF do responsável diferente do da menor.
  5. Reaproveita `SIGNING` da mesma paciente com `created_at` dentro de 24 h e mesmo `signer_kind` e `term_version`: devolve o existente sem chamar o provedor. Mais velho: `provider.cancela`, `status = EXPIRED`, segue.
  6. Grava cadastro **só em campo vazio**: `patients.name` (se vazio ou só um nome), `cpf`, `birth_date`, `email`; `patient_guardians` por upsert (`ON CONFLICT (patient_id) DO UPDATE`), porque o responsável não é cadastro, é anexo do termo.
  7. Monta `template.data` com as 18 variáveis do modelo (`docs/work/assets/036-tcle/gera_modelo.js`): datas `dd/mm/aaaa`, CPF `000.000.000-00`, `autoriza_imagem` "Autorizo" / "Não autorizo", `menor_nome`/`responsavel_*` vazios se maior, `signatario_*` = responsável se menor, senão paciente, `data` = hoje no fuso da clínica (`relogio`), `cidade`, `clinica_nome` = `display_name or name`.
  8. `provider.cria_termo(TEMPLATE_KEY, f"TCLE-{VERSAO}-{patient_id[:8]}.docx", dados, signatario, referencia=f"{clinic_id}/{appointment_id}", prazo=agora + 2 dias)`.
  9. `INSERT patient_consents (... status 'SIGNING' ...)`. `IntegrityError` no índice `uq_patient_consents_assinando` (corrida de dois toques) → `provider.cancela` do recém-criado e devolve o existente.
  10. Devolve `{"consent": _para_tela(row, provider)}`.
- `_para_tela(row, provider) -> Dict`: `id, status, signerId, widgetEndpoint (provider.widget_endpoint), test (termo_de_teste), canSimulate (provider.pode_simular), signedAt`.
- `status(db, provider, clinic_id, phone, consent_id) -> Dict`: posse (`appointment_id` do termo pertence ao número, via `_do_numero`); se `SIGNING`, `provider.consulta`; `SIGNED` → `_fecha(db, provider, row)`; `CANCELLED`/`EXPIRED` → grava. Devolve `_para_tela`.
- `_fecha(db, provider, row)`: idempotente (`WHERE status = 'SIGNING'`); baixa PDF, `grava` no S3, sha256, zip se houver; `UPDATE ... status 'SIGNED', signed_at = NOW(), pdf_s3_key, pdf_sha256, audit_s3_key`. Se o download falhar, loga e **não** marca `SIGNED`; o próximo polling ou webhook tenta de novo.
- `aplica_evento(db, provider, evento: Dict, event_id: str) -> str`: `SELECT 1 FROM consent_webhook_events WHERE event_id` → `"repetido"`. Lê `event.name` e o(s) `document.key` / `envelope.key` do payload (formato varia; função `_ids_do_evento` tolerante). Nome em `("auto_close", "close", "document_closed", "envelope_closed")` → localiza por `provider_document_id` ou `provider_envelope_id`, `_fecha`; `("cancel", "deadline")` → `CANCELLED`/`EXPIRED`. Outros → `"ignorado"`. Depois, `INSERT consent_webhook_events ... ON CONFLICT DO NOTHING` (depois de processar, como o Asaas). `event_id` = `event.name + ":" + document_key + ":" + occurred_at` quando o payload não trouxer id próprio.
- `simula(db, provider, clinic_id, phone, consent_id)`: `provider.pode_simular` falso → `ConsentimentoInvalido`; `provider.simula(envelope_id)`; `status(...)`.
- Painel: `lista_do_paciente(db, clinic_id, patient_id)`, `dispensa(db, clinic_id, appointment_id, motivo, nota, autor)` (valida motivo, `UPDATE appointments SET consent_waived_* WHERE clinic_id AND id`), `registra_papel(db, clinic_id, patient_id, data: date, autor)` (`INSERT ... status 'PAPER', term_version VERSAO, paper_signed_at, paper_registered_by, signer_kind 'PATIENT'`; `IntegrityError` → já vigente, devolve o existente), `url_do_pdf(db, clinic_id, consent_id)` / `url_do_zip(...)` (404 se não houver chave; URL de 300 s).
- Logs `[Consentimento] ...` com `clinic`, `consent`, `provider`.

### `scheduler/src/services/checkin.py` (modificar)

- `agendamentos_do_numero`: para cada `row`, `item.update(consentimento.resumo_para_o_ipad(db, clinic_id, row))`.
- `confirma`: na resposta, `**consentimento.resumo_para_o_ipad(db, clinic_id, appt)`.
- Nada muda em `cobra`: o backend não bloqueia pagamento por termo (§5).

### `scheduler/src/functions/public_booking/checkin.py` (modificar)

```python
("POST", re.compile(rf"^appointments/({UUID})/consent$"), "consent"),
("GET",  re.compile(rf"^consents/({UUID})$"),             "consent_status"),
("POST", re.compile(rf"^consents/({UUID})/simulate$"),    "consent_simula"),
```

- Ramos: `consent` → 201 `{"status": "SUCCESS", **consentimento.inicia(db, provedor_de_assinatura, clinic_id, phone, id, body)}`; `consent_status` → 200; `consent_simula` → 200.
- O provedor de assinatura é criado só nesses ramos (`from src.providers.signature_provider import provedor_ativo as provedor_de_assinatura`), para não exigir chave da ClickSign em `lista`/`confirma`.
- Exceções: `ConsentimentoInvalido` → 400; `AssinaturaIndisponivel` → 503 "Assinatura indisponível no momento. Chame a recepção."; `ErroDoProvedor` (assinatura) → 502.

### `scheduler/src/functions/public_booking/clicksign_webhook.py` (criar)

```python
def _assinatura(event) -> str:  # Content-Hmac ou x-clicksign-signature, case-insensitive; aceita "sha256=<hex>" ou só "<hex>"
def handler(event, context):
    segredo = os.environ.get("CLICKSIGN_WEBHOOK_SECRET", "")
    corpo = event.get("body") or ""           # cru; se isBase64Encoded, decodifica antes
    esperado = hmac.new(segredo.encode(), corpo.encode("utf-8"), hashlib.sha256).hexdigest()
    if not segredo or not hmac.compare_digest(_assinatura(event), esperado): return http_response(401, ...)
    try: evento = json.loads(corpo)
    except ValueError: return http_response(400, ...)
    try:
        resultado = consentimento.aplica_evento(PostgresService(), provedor_de_assinatura(), evento, event_id=_event_id(evento))
        return http_response(200, {"status": "SUCCESS", "result": resultado})
    except Exception: logger.exception(...); return http_response(500, ...)   # ClickSign reenvia
```

- O HMAC é sobre o **corpo cru** como string; nunca re-serializar o JSON.

### `scheduler/src/functions/public_booking/router.py` e `sls/functions/public_booking/interface.yml` (modificar)

- Rota `("POST", "public/clicksign/webhook"): clicksign_webhook.handler`.
- Evento `http: path: public/clicksign/webhook, method: post` sem `cors` (servidor a servidor).
- IAM: `s3:PutObject`, `s3:GetObject` em `arn:aws:s3:::${self:custom.resourcePrefix}-documentos/clinics/*`.
- `TestRota` em `test_checkin.py` ganha a rota nova; o mesmo teste nasce em `test_clicksign_webhook.py`.

### `scheduler/sls/resources/s3/documentos-bucket.yml` (criar)

```yaml
Resources:
  DocumentosBucket:
    Type: AWS::S3::Bucket
    DeletionPolicy: Retain
    Properties:
      BucketName: ${self:custom.resourcePrefix}-documentos
      PublicAccessBlockConfiguration: {BlockPublicAcls: true, BlockPublicPolicy: true, IgnorePublicAcls: true, RestrictPublicBuckets: true}
      BucketEncryption: {ServerSideEncryptionConfiguration: [{ServerSideEncryptionByDefault: {SSEAlgorithm: AES256}}]}
      VersioningConfiguration: {Status: Enabled}
```

- Sem `BucketPolicy`, sem CORS (o painel só recebe URLs assinadas para `GET`). `DeletionPolicy: Retain`: termo assinado não some com o stack.

### `scheduler/serverless.yml` (modificar)

```yaml
custom:
  clicksignBaseUrl:
    dev: https://sandbox.clicksign.com
    prod: https://app.clicksign.com
provider.environment:
  CLICKSIGN_API_KEY: ${ssm:/${self:custom.stage}/CLICKSIGN_API_KEY, ''}
  CLICKSIGN_WEBHOOK_SECRET: ${ssm:/${self:custom.stage}/CLICKSIGN_WEBHOOK_SECRET, ''}
  CLICKSIGN_TCLE_TEMPLATE_KEY: ${ssm:/${self:custom.stage}/CLICKSIGN_TCLE_TEMPLATE_KEY, ''}
  TCLE_VERSION: ${ssm:/${self:custom.stage}/TCLE_VERSION, ''}
  CLICKSIGN_BASE_URL: ${self:custom.clicksignBaseUrl.${self:custom.stage}}
  DOCUMENTOS_BUCKET: ${self:custom.resourcePrefix}-documentos
resources:
  - ${file(sls/resources/s3/documentos-bucket.yml)}
```

### `scheduler/src/functions/consent/router.py` + `sls/functions/consent/interface.yml` (criar)

- Molde: `src/functions/caixa/router.py`. Regexes: `POR_PACIENTE = ^$` com `?patientId=`, `DISPENSA = ^appointments/(UUID)/waive$`, `PAPEL = ^patients/(UUID)/paper$`, `PDF = ^(UUID)/pdf-url$`, `ZIP = ^(UUID)/zip-url$`.
- Auth: `GET` lista, `pdf-url`, `zip-url` → `require_acesso(event, "prontuario.ler")` (é documento da paciente, como o histórico); `waive` e `paper` → `require_acesso(event, "agenda.escrever")`. Admin passa por `require_acesso` como hoje (chave mestra).
- `waive`: body `{reason, note?}`; `autor = identidade.nome` (ou "admin"); 200 `{appointment: {...consent_waived_*}}`; motivo inválido → 400.
- `paper`: body `{signedAt: "YYYY-MM-DD"}`; data futura → 400; 201 `{consent}`.
- `pdf-url` / `zip-url`: 200 `{url, expiresInSeconds: 300}`; sem arquivo → 404.
- Respostas de staff passam por `para_o_staff(identidade, ...)` como o caixa, por consistência (não há valor monetário aqui).
- yml: `Consentimento`, handler `src.functions.consent.router.handler`, evento `clinics/{clinicId}/consents/{proxy+}` `any` `cors: true`, IAM `s3:GetObject` no bucket privado (presign exige a permissão na role que assina).

### `scheduler/src/functions/professional/update.py` + `interface.yml` (criar / modificar)

- `PUT clinics/{clinicId}/professionals/{professionalId}`, `require_api_key` (admin, como o create). `ALLOWED_FIELDS = ("name", "role", "registro_conselho", "active")`; `UPDATE ... WHERE id AND clinic_id RETURNING *`; 404 se não achou.
- `UpdateProfessional` no yml, `cors: true`.

### `scheduler/src/functions/clinic/update.py` (modificar)

- `ALLOWED_FIELDS` += `"responsible_professional_id"`, `"cidade"`. Validação: `responsible_professional_id` nulo ou UUID de profissional ativo **desta** clínica (`SELECT 1 FROM professionals WHERE id AND clinic_id AND active`), senão 400. `cidade` até 120 caracteres, `strip`.

### `scheduler/src/functions/appointment/list.py` (modificar)

- SELECT += `a.consent_waived_at, a.consent_waived_reason, a.consent_waived_by` e

```sql
LEFT JOIN LATERAL (
  SELECT CASE WHEN pc.status IN ('SIGNED','PAPER') THEN pc.status ELSE 'SIGNING' END AS consent_status
    FROM scheduler.patient_consents pc
   WHERE pc.clinic_id = a.clinic_id AND pc.patient_id = a.patient_id
     AND pc.term_version = %(versao)s AND pc.status IN ('SIGNED','PAPER','SIGNING')
   ORDER BY CASE pc.status WHEN 'SIGNED' THEN 0 WHEN 'PAPER' THEN 0 ELSE 1 END LIMIT 1) ct ON TRUE
```

- `consent_status`: `SIGNED | PAPER | SIGNING | NULL` (`NULL` = pendente). O painel deriva "Termo pendente" = `consent_status` nulo ou `SIGNING`, `consent_waived_at` nulo, `status = CONFIRMED`, e `TCLE_VERSION` configurada (o backend manda `consent_enabled: bool` no topo da resposta da lista, igual a `bool(VERSAO)`).

### `checkin/src/types/index.ts` (modificar)

```ts
export interface ConsentPrefill {
  name: string | null; cpfMasked: string | null; cpfKnown: boolean
  birthDate: string | null; phone: string; email: string | null
  isMinor: boolean; clinicReady: boolean
  guardian: { name: string; cpfMasked: string; birthDate: string; phone: string; email: string } | null
}
export interface Consent {
  id: string; status: 'NOT_REQUIRED' | 'SIGNING' | 'SIGNED' | 'CANCELLED' | 'EXPIRED'
  signerId: string | null; widgetEndpoint: string; test: boolean; canSimulate: boolean; signedAt: string | null
}
export interface ConsentStartPayload {
  fullName: string; cpf: string | null; birthDate: string; email: string; imageAuthorized: boolean
  guardian: { name: string; cpf: string; birthDate: string; phone: string; email: string } | null
}
// CheckinAppointment += consentRequired: boolean; consentPrefill: ConsentPrefill | null
```

- `cpf: null` no payload significa "manter o CPF já conhecido" (o iPad mostra mascarado e não pede de novo).

### `checkin/src/services/checkin.service.ts` e `hooks/useCheckin.ts` (modificar)

```ts
startConsent: (clinicId, s, appointmentId, payload) => api.post<{ consent: Consent }>(`${base}/checkin/appointments/${appointmentId}/consent`, { ...s, ...payload }).then(r => r.data.consent)
consent:      (clinicId, s, consentId) => api.get<{ consent: Consent }>(`${base}/checkin/consents/${consentId}`, { params: s }).then(r => r.data.consent)
simulateConsent: (clinicId, s, consentId) => api.post<{ consent: Consent }>(`${base}/checkin/consents/${consentId}/simulate`, s).then(r => r.data.consent)
```

- `checkinKeys.consent(clinicId, consentId)`; `useConsentStatus` com `refetchInterval: data && data.status !== 'SIGNING' ? false : 3000`, `refetchIntervalInBackground: true`, `gcTime: 0`. `reset` da página remove `['checkin', 'consent']`.

### `checkin/src/lib/clicksignWidget.ts` (criar)

```ts
const SCRIPT = 'https://cdn-public-library.clicksign.com/embedded/embedded.min-2.1.0.js'
interface ClicksignWidget { endpoint: string; origin: string; mount(id: string): void; unmount(): void; on(ev: 'loaded' | 'signed' | 'resized', cb: (e: { data?: { height?: number } }) => void): void }
declare global { interface Window { Clicksign?: new (signerId: string) => ClicksignWidget } }
export function loadClicksign(): Promise<void>          // injeta o script uma vez; rejeita em 15 s
export function mountClicksign(signerId, endpoint, containerId, onSigned, onResized): () => void   // devolve o unmount
```

- `widget.origin = window.origin` (não `*`). Se o script falhar (sem rede, bloqueio), `ConsentSignStep` mostra erro com "Tentar de novo" e "Chamar a recepção".

### `checkin/src/steps/ConsentDataStep.tsx` (criar)

- Props: `{ appointment, onStarted(consent: Consent), onBack }` + `clinicId`, `session`.
- Layout em uma coluna, alvos de 64 px. Campos: nome completo (`TextField`, pré-preenchido, obrigatório com dois nomes), CPF (`Keypad` só quando `!cpfKnown`; quando conhecido, mostra mascarado e um botão "Não é meu CPF" que abre o teclado), nascimento (`Keypad` 8 dígitos `ddmmaaaa`, pré-preenchido quando conhecido), e-mail (`TextField` tipo email, obrigatório), uso de imagem (dois botões grandes "Autorizo" / "Não autorizo", obrigatório). Se `isMinor` ou a data digitada der menor de 18 na data da sessão: bloco "Responsável legal" com os mesmos campos mais celular (`Keypad` 11 dígitos), pré-preenchido do `guardian`.
- Validação local espelha a do servidor (`isValidCpf`, e-mail, data); erro do servidor (`400`) aparece em `ErrorMessage`.
- Se `!clinicReady`: tela "A clínica ainda não configurou o termo. Chame a recepção." com "Voltar ao início". Nunca um botão de pular.
- Botão "Continuar para a assinatura" → `useStartConsent.mutate` → `onStarted(consent)`. `status === 'NOT_REQUIRED'` → `onStarted` igualmente; a página decide.

### `checkin/src/steps/ConsentSignStep.tsx` (criar)

- Props: `{ clinicId, session, consent, onSigned(consent), onBack }`.
- `consent.canSimulate` (simulado): bloco "Ambiente de teste" com botão "Simular assinatura (teste)" → `useSimulateConsent` → `onSigned`. Sem widget.
- Senão: `<div id="clicksign-widget">` com `min-height: 70vh`; `mountClicksign` no `useEffect`, `unmount` no cleanup; `resized` ajusta a altura. Texto acima: "Leia o termo, digite o código que chegou no seu WhatsApp e assine na tela."
- `useConsentStatus` polling; `useEffect` chama `onSigned` quando `SIGNED` (o evento `signed` do widget só força um `refetch`). `CANCELLED`/`EXPIRED` → erro com "Chamar a recepção" e "Voltar ao início".
- Selo "TESTE" quando `consent.test` (sandbox), como o pagamento.

### `checkin/src/pages/CheckinPage.tsx` (modificar)

```ts
| ({ step: 'consent-data' } & Paying)
| ({ step: 'consent-sign'; consent: Consent } & Paying)
```

- `next(paying, payment)` ganha uma verificação antes do bloco de pagamento: `if (appointment.consentRequired && !paying.consentDone) return { step: 'consent-data', ...paying }`. `Paying` += `consentDone: boolean` (false ao confirmar). `ConsentDataStep.onStarted`: `NOT_REQUIRED`/`SIGNED` → `go(next({...paying, consentDone: true}, appointment.payment))`; `SIGNING` → `consent-sign`. `ConsentSignStep.onSigned` → `go(next({...paying, consentDone: true}, appointment.payment))`.
- Idle: `state.step === 'payment' || state.step === 'consent-sign' ? IDLE_PAYMENT_MS : IDLE_MS`.
- `reset` remove também `['checkin', 'consent']`.
- Agendamento já pago com termo pendente: `alreadyPaid` continua indo para `done` (pagamento pago não é bloqueado); o termo fica para a recepção. Comentar.

### `checkin/src/pages/CheckinPage.test.tsx` (modificar)

Casos novos (simulado): `consentRequired: true` com prefill completo → passa por "Continuar para a assinatura" → "Simular assinatura (teste)" → chega em Pix; `consentRequired: false` → fluxo atual intacto; menor de idade exige responsável (botão desabilitado até preencher); `clinicReady: false` mostra "Chame a recepção" e não mostra Pix; `startConsent` 400 mostra a mensagem do servidor.

### `frontend/` (criar / modificar)

- **`types/index.ts`**: `Appointment` += `consent_status: 'SIGNED' | 'PAPER' | 'SIGNING' | null`, `consent_waived_at`, `consent_waived_reason`, `consent_waived_by`; `Clinic`/`UpdateClinicPayload` += `responsible_professional_id: string | null`, `cidade: string | null`; `PatientConsent { id, term_version, status, signer_kind, signer_name, signed_at, paper_signed_at, paper_registered_by, has_pdf, has_zip, created_at }`; `ConsentWaiveReason`.
- **`services/consents.service.ts`** + **`hooks/useConsents.ts`**: molde `caixa.service.ts`/`useCaixa.ts`; mutações invalidam `appointmentKeys.lists()` e `consentKeys.all`. `useUrlDoTermo` é mutação (a URL expira): `onSuccess: window.open(url, '_blank', 'noopener')`.
- **`TermoDoAgendamento.tsx`**: linha "Termo" com `situacaoDoTermo(a)`: "Assinado em dd/mm" (`SIGNED`), "Em papel" (`PAPER`), "Assinando" (`SIGNING`), "Dispensado por X (motivo)" (`consent_waived_at`), "Pendente". Quando pendente e `CONFIRMED`: botões "Dispensar nesta sessão" (abre `Modal` com `select` de motivo e nota quando OUTRO) e "Assinado em papel" (`Modal` com `input type=date`). Toasts como em `PagamentoDoAgendamento`. Só renderiza quando `consent_enabled` (vem na lista).
- **`TermoPendenteBadge.tsx`**: `({ appointment, compacto })`, retorna `null` se não pendente; texto "TERMO" amber nos mesmos estilos do `ConfirmacaoBadge`. Em `AgendaDoDia.tsx` (L197) e `WeekGrid.tsx` (L179).
- **`DocumentosPage.tsx`**: `const doc = searchParams.get('doc') ?? 'historico'`; `nav` com dois botões-aba (`role="tab"`, `aria-selected`); segunda aba renderiza `TermoDeConsentimento patientId`. Manter `?agendamento=` ao trocar de aba.
- **`TermoDeConsentimento.tsx`**: `useConsentsDoPaciente`; 4 estados; tabela versão / situação / signatário / data / registrado por; botões "Abrir PDF" e "Baixar zip" (desabilitado sem arquivo). Vazio: "Nenhum termo assinado. A paciente assina no check-in."
- **`ResponsavelTecnica.tsx`** em Configurações: `select` da profissional ativa (`useProfessionals`), campo cidade (salvos com o resto do formulário via `set`), e uma lista das profissionais com campo "Registro no conselho" por linha e botão "Salvar" por linha (`useUpdateProfessional`). Aviso amarelo quando responsável, registro ou cidade faltam: "Sem isso o termo não é gerado no check-in."
- **`professionals.service.ts`** / **`useProfessionals.ts`**: `registro_conselho: string | null` no tipo; `update`; `useUpdateProfessional` invalida `professionalKeys.all`.
- Testes: `TermoDoAgendamento.test.tsx` (cada situação, dispensar chama o service com motivo), `TermoPendenteBadge.test.tsx`, `TermoDeConsentimento.test.tsx` (4 estados), `ResponsavelTecnica.test.tsx` (aviso quando falta), `DocumentosPage.test.tsx` (troca de aba).

### `scheduler/tests/unit/test_consentimento.py` (criar)

`Db` falso com dicts `clinicas`, `profissionais`, `pacientes`, `responsaveis`, `agendamentos`, `termos`, `eventos`; `execute_*` por substring do SQL, `AssertionError` em SQL desconhecido; `IntegrityError` nos dois índices parciais. `Provedor(SignatureProvider)` grava `criados`, `cancelados`, `status` controlável, `pdf = b"%PDF-teste"`. `documentos_s3.grava` e `url_assinada` com `mock.patch`.

Casos: sem termo pede; termo `SIGNED` da versão vigente não pede; `SIGNED` de versão antiga pede; `PAPER` vigente não pede; dispensa na sessão não pede e a próxima sessão pede; `TCLE_VERSION` vazia nunca pede; clínica sem responsável → `ConsentimentoInvalido`; menor sem responsável → inválido; menor com responsável → `signer_kind GUARDIAN` e `signatario_*` do responsável; cadastro só preenche campo vazio (nome de uma palavra é vazio, nome com dois não é sobrescrito); `SIGNING` de 1 h é reaproveitado sem chamar o provedor; `SIGNING` de 30 h é cancelado e expirado; falha no `INSERT` por corrida cancela o envelope novo; `status` com provedor `SIGNED` baixa, grava, marca; download falho não marca; `aplica_evento` repetido devolve `repetido` e não grava duas vezes; evento de cancel marca `CANCELLED`; `registra_papel` duas vezes devolve o mesmo; `dispensa` com motivo inválido falha.

### `scheduler/tests/integration/036-termo-de-consentimento.md` (criar)

Roteiro: (1) conferir `auth` aceitos pelo widget no sandbox e registrar; (2) iPad em dev com paciente sem termo: dados → widget → token no WhatsApp → manuscrita → webhook → `GET consents/{id}` `SIGNED` → PDF no S3 e hash; (3) mesmo número de novo não pede; (4) menor; (5) dispensa pelo painel e volta a pedir na sessão seguinte; (6) papel; (7) webhook com HMAC errado 401, repetido 200 `repetido`; (8) `curl` de cada rota com `source .env`.

---

## 7. Convenções a respeitar

- Migrations idempotentes e coluna também no `CREATE TABLE`; a lista chama-se `SQL_STATEMENTS`. Rodar `python -m src.scripts.setup_database` com o `.env` do stage certo.
- Regra do gatilho **só** em `consentimento.precisa_assinar`; `appointment/list.py` expõe estado, não decide. Antes do PR: `grep -rn "patient_consents" scheduler/src` e justificar cada leitura fora do serviço.
- Escrita no cadastro só em campo vazio, como `_guarda_cpf_no_cadastro`. Snapshot é o que foi ao documento; `patients` é o cadastro.
- Provedor nunca recebe `db`; serviço nunca chama `requests`. Mesma separação do pagamento.
- O bot não importa `consentimento` nem lê as tabelas novas (`grep -rn "patient_consents\|patient_guardians" scheduler/src/services/skills scheduler/src/services/ai_tools.py` vazio).
- Python 3.8: `Optional[...]`, `Dict[...]`, sem walrus em compreensões complicadas, sem `str.removeprefix`.
- Logging `[Consentimento] ...`, `[ClicksignProvider] ...`, `[ClicksignWebhook] ...`; nunca logar token, CPF completo ou corpo do webhook inteiro (só `event.name` e chaves).
- Segredos só por SSM (`/{stage}/CLICKSIGN_*`, `/{stage}/TCLE_VERSION`); nada em código, docs ou Postman.
- Frontend e checkin: 4 estados, named exports, zero `any`, alvos ≥ 64 px no iPad, `npm run build` e `npm run lint` antes do push (a Vercel roda o build).
- Testes de comportamento com `Db` falso (`test_checkin.py` é o molde); nada de `assertIn` no fonte.
- Deploys de dev e prod nunca em paralelo; conferir estado real depois do deploy (rota responde, webhook cadastrado, bucket existe, contagem do stack).
