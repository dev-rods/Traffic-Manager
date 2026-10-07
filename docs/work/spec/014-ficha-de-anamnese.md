# Spec - 014 Ficha de anamnese digital

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/014-ficha-de-anamnese.md`

---

## 1. Resumo

Um **app web público novo** (`anamnese/`) onde a paciente preenche a ficha no
celular e é levada direto à assinatura no ZapSign. O disparo é um **clique
manual na agenda** do painel. O resultado, PDF assinado mais trilha de
auditoria, entra na **pasta de Documentos** criada pelo PRD 012.

Toca quatro superfícies: banco (migrations), `scheduler/` (7 Lambdas e 3
serviços), `frontend/` (agenda e pasta de documentos) e um app novo.

---

## 2. Decisões de desenho desta spec

### As perguntas são definidas UMA vez, em Python

`src/services/anamnese/formulario_v02.py` é a fonte única. O app web recebe as
perguntas pelo endpoint de abertura e **renderiza a partir do payload**; a
geração do PDF lê do mesmo módulo.

Definir 60 perguntas em Python e de novo em TypeScript é garantir que um dia
divirjam - e o que diverge aqui é documento com peso legal. É a mesma lição de
`feedback-fonte-unica-de-verdade`.

Em código e não em tabela porque é documento jurídico: precisa de revisão por
diff, histórico no git e teste. Tabela convida edição silenciosa.

### O PDF é nosso, gerado com `fpdf2`

O ZapSign aceita template com campos posicionais. Descartado: as respostas têm
**texto livre de tamanho variável** ("quais medicamentos?"), que estoura campo
de posição fixa. E precisamos conseguir regerar o documento sem depender do
provedor.

`fpdf2` é Python puro, e o empacotamento usa `dockerizePip: false` - dependência
com binário nativo dá problema aqui.

### O envio é direto, sem passar pela fila

`outbound-queue` existe para mensagem iniciada pelo bot, com retry e cadência. O
disparo da ficha é manual: a profissional está olhando a tela e precisa ver o
erro na hora. Fila aqui só esconderia a falha.

---

## 3. Migrations

Em `src/scripts/setup_database.py`, lista `MIGRATIONS`, **todas idempotentes**.
Atualizar também os `CREATE TABLE` correspondentes na lista `TABLES`.

```sql
-- Identificacao juridica da clinica
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS cnpj VARCHAR(18);
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS razao_social VARCHAR(255);
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS responsible_professional_id UUID
    REFERENCES scheduler.professionals(id);

-- Registro no conselho da profissional
ALTER TABLE scheduler.professionals ADD COLUMN IF NOT EXISTS registro_conselho VARCHAR(40);
```

```sql
CREATE TABLE IF NOT EXISTS scheduler.anamnesis_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
    patient_id UUID NOT NULL REFERENCES scheduler.patients(id),
    appointment_id UUID REFERENCES scheduler.appointments(id),
    form_version VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ENVIADA',
    answers JSONB,
    declared_phototype VARCHAR(3),
    rt_snapshot JSONB,
    sent_by_name VARCHAR(255),
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ,
    signed_at TIMESTAMPTZ,
    provider VARCHAR(20),
    provider_document_id VARCHAR(120),
    pdf_s3_key TEXT,
    pdf_sha256 CHAR(64),
    audit_s3_key TEXT,
    signer_name VARCHAR(255),
    signer_cpf VARCHAR(14),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (status IN ('ENVIADA','PREENCHIDA','ASSINADA','EXPIRADA','CANCELADA')),
    CHECK (declared_phototype IS NULL
           OR declared_phototype IN ('I','II','III','IV','V','VI'))
);

CREATE INDEX IF NOT EXISTS idx_anamnesis_paciente
    ON scheduler.anamnesis_forms (patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_anamnesis_agendamento
    ON scheduler.anamnesis_forms (appointment_id);
```

```sql
CREATE TABLE IF NOT EXISTS scheduler.anamnesis_access_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID NOT NULL REFERENCES scheduler.anamnesis_forms(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    opened_at TIMESTAMPTZ,
    used_at TIMESTAMPTZ,
    attempts SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**`token_hash`, nunca o token cru.** Vazamento do banco não pode virar acesso a
prontuário. SHA-256 do token; a consulta é pelo hash.

```sql
CREATE TABLE IF NOT EXISTS scheduler.anamnesis_form_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID NOT NULL REFERENCES scheduler.anamnesis_forms(id) ON DELETE CASCADE,
    event VARCHAR(30) NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_anamnesis_eventos ON scheduler.anamnesis_form_events (form_id, created_at);
```

### Dados da Essência

Na mesma migration, idempotente:

```sql
UPDATE scheduler.professionals
   SET registro_conselho = 'CRBM-SP 44657', role = COALESCE(role, 'Biomédica Esteta')
 WHERE clinic_id = '<essencia>' AND name ILIKE 'Clara Santos Dourado'
   AND registro_conselho IS NULL;
```

**Confirmar antes se a Clara já existe em `professionals`.** Se não existir,
inserir. CNPJ e razão social da Essência ainda não foram informados e ficam
pendentes - o PDF não pode ir a paciente real sem eles.

---

## 4. Arquivos a criar - backend

| Arquivo | Descrição |
|---|---|
| `src/services/anamnese/__init__.py` | - |
| `src/services/anamnese/formulario_v02.py` | **Fonte única** das seções 1 a 11 |
| `src/services/anamnese/alertas.py` | Quais respostas viram alerta |
| `src/services/anamnese/pdf.py` | Monta o PDF com `fpdf2` |
| `src/services/anamnese/tokens.py` | Gera, hasheia, valida, conta tentativas |
| `src/services/anamnese/service.py` | Orquestra: cria, envia, recebe, conclui |
| `src/services/assinatura/__init__.py` | - |
| `src/services/assinatura/base.py` | ABC do provedor |
| `src/services/assinatura/zapsign.py` | Implementação |
| `src/services/assinatura/factory.py` | `get_provider()` |
| `src/functions/anamnesis/enviar.py` | Painel: cria a ficha e dispara |
| `src/functions/anamnesis/listar.py` | Painel: fichas de uma paciente |
| `src/functions/anamnesis/pendentes.py` | Painel: selo na agenda do dia |
| `src/functions/anamnesis/arquivo.py` | Painel: URL assinada do PDF |
| `src/functions/anamnesis/abrir.py` | **Público:** valida token e nascimento |
| `src/functions/anamnesis/enviar_respostas.py` | **Público:** grava e cria a assinatura |
| `src/functions/anamnesis/webhook.py` | **Público:** conclusão do ZapSign |
| `sls/functions/anamnesis/interface.yml` | As 7 funções |
| `sls/resources/documents-bucket.yml` | Bucket S3 privado |

### Estrutura de `formulario_v02.py`

```python
VERSAO = "02"

@dataclass(frozen=True)
class Pergunta:
    id: str
    secao: int
    texto: str
    tipo: str          # sim_nao | texto | texto_longo | data | escolha_unica
    detalhe_se: str = None   # pergunta de follow-up quando a resposta for SIM
    opcoes: tuple = ()
    alerta: bool = False     # um SIM aqui aparece para a profissional
    obrigatoria: bool = True
```

`alerta` mora aqui, junto da pergunta, para a lista de sinais vermelhos ser
derivada da definição e não de uma segunda lista que envelhece à parte.

`para_a_tela()` devolve o payload que o app renderiza. `valida(respostas)`
recusa resposta de pergunta inexistente e obrigatória faltando.

---

## 5. Contratos de API

### Painel (autenticado, `x-api-key`)

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/clinics/{clinicId}/patients/{patientId}/anamnesis` | Cria e dispara. Body: `{appointmentId?, sentByName}` |
| `GET` | `/clinics/{clinicId}/patients/{patientId}/anamnesis` | Fichas da paciente |
| `GET` | `/clinics/{clinicId}/anamnesis/pending?date=YYYY-MM-DD` | Selo na agenda |
| `GET` | `/clinics/{clinicId}/anamnesis/{formId}/file?tipo=pdf\|trilha` | URL assinada, 5 min |

### Público (token, **sem api key**)

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/public/anamnesis/{token}/open` | Body `{birthDate}`. Devolve clínica, RT e perguntas |
| `POST` | `/public/anamnesis/{token}/submit` | Body `{answers, declaredPhototype}`. Devolve `{signUrl}` |
| `POST` | `/public/anamnesis/webhook` | Conclusão do ZapSign |

**Regras do endpoint público**, todas testáveis:

- Token inexistente, expirado ou já usado: **404 genérico**, sempre a mesma
  mensagem. Distinguir "não existe" de "expirou" entrega informação a quem
  sonda.
- `birthDate` errado incrementa `attempts`; a partir de 5, o token morre.
- Resposta de `open` **nunca** traz CPF, telefone, e-mail ou histórico. Só
  primeiro nome da paciente, marca da clínica, RT e as perguntas.
- `submit` é idempotente por token: repetir devolve a mesma `signUrl`.

---

## 6. App novo `anamnese/`

Vite + React + TypeScript, mesma stack do `frontend/`, **projeto Vercel
separado**. Sem qualquer tag de analytics ou pixel.

```
anamnese/
  src/
    App.tsx                 // 3 passos: abrir -> preencher -> redirecionar
    pages/AberturaPage.tsx  // data de nascimento
    pages/FormularioPage.tsx
    components/Pergunta.tsx // renderiza por `tipo`
    components/Secao.tsx
    services/anamnese.ts
    types.ts
  vercel.json
```

**Uma pergunta por vez não; seção por vez sim.** Quatro páginas de papel viram 9
passos curtos com barra de progresso. Rolagem infinita num formulário médico faz
a paciente desistir no meio; 60 telas também.

Salvar rascunho em `localStorage` por token, para quem perde o sinal não começar
de novo.

---

## 7. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `src/scripts/setup_database.py` | Migrations da seção 3 |
| `serverless.yml` | `- ${file(sls/functions/anamnesis/interface.yml)}`; recurso do bucket; env `ZAPSIGN_API_TOKEN`, `ANAMNESE_BASE_URL`, `DOCUMENTS_BUCKET` |
| `sls/resources/` | Incluir `documents-bucket.yml` |
| `src/functions/clinic/create.py`, `update.py` | Aceitar `cnpj`, `razao_social`, `responsible_professional_id` |
| `src/functions/professional/create.py`, `update.py` | Aceitar `registro_conselho` |
| `requirements.txt` | `fpdf2==2.7.9` |
| `frontend/src/services/anamnesis.service.ts` | **criar** |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | Botão **Enviar ficha** e estado da ficha |
| `frontend/src/pages/agenda/components/WeekGrid.tsx` | Selo de pendência |
| `frontend/src/pages/documentos/DocumentosPage.tsx` | Aba **Ficha de anamnese** |
| `frontend/src/pages/documentos/components/FichaDeAnamnese.tsx` | **criar** |
| `frontend/src/types/` | Tipos novos |

**SSM:** criar `/${stage}/ZAPSIGN_API_TOKEN` **antes** do deploy. Secret é
resolvido em tempo de deploy; sem o parâmetro, o deploy falha.

---

## 8. Ordem de implementação

**0. Liberar espaço no CloudFormation.** A stack está em **440/500**, com 74
lambdas - **~5,9 recursos por função**. As 7 funções novas custam ~41 e levam a
~481, deixando 19 de folga. Muito apertado, e descobrir isso no deploy final é
o pior momento possível.

Executar antes a remoção dos log groups já mapeada no PRD 013 (74 recursos,
levando a stack a ~366). É a dança de dois deploys com `DeletionPolicy: Retain`.

Sem esse passo, o risco é terminar a feature e não conseguir subir.

1. Migrations; rodar em dev; conferir a Clara.
2. `formulario_v02.py` + teste de transcrição.
3. `alertas.py`, `tokens.py`.
4. Bucket S3 e `assinatura/` (ZapSign), testado isolado.
5. `pdf.py`, conferido contra o PDF original.
6. Lambdas do painel (`enviar`, `listar`, `pendentes`, `arquivo`).
7. Lambdas públicas (`abrir`, `enviar_respostas`, `webhook`).
8. App `anamnese/`, contra o backend de dev.
9. Frontend: agenda e pasta de documentos.
10. Ponta a ponta em dev, com telefone de teste.
11. Migration e deploy em prod; documentação e Postman.

---

## 9. Testes obrigatórios

Cada regra da seção 6 do PRD vira teste, porque são as que machucam alguém:

| Arquivo | O que trava |
|---|---|
| `test_formulario_v02.py` | Transcrição fiel; valores conferidos à mão contra o PDF |
| `test_alertas_da_anamnese.py` | Cada `alerta=True` aparece; nada é bloqueado automaticamente |
| `test_fototipo_nao_vira_skin_type.py` | **Nenhum** caminho escreve `patients.skin_type` |
| `test_respostas_gravam_antes_de_assinar.py` | ZapSign falhando ainda deixa `PREENCHIDA` |
| `test_token_de_anamnese.py` | Expirado, usado, nascimento errado, limite de tentativas |
| `test_abrir_nao_vaza_dado.py` | O payload de `open` não traz CPF, telefone nem e-mail |
| `test_ficha_nao_sobrescreve_cadastro.py` | Só preenche campo vazio; divergência é reportada |
| `test_menor_vai_ao_responsavel.py` | Menor manda ao responsável e ele é o signatário |
| `test_bot_nao_ve_anamnese.py` | Nenhuma tool do agente alcança estas tabelas |
| `anamnese/src/**/*.test.tsx` | Renderização por `tipo`, follow-up no SIM, rascunho |

`test_bot_nao_ve_anamnese.py` segue o molde do `test_bot_nao_ve_prontuario.py`
que já existe.

**Conferir cada teste contra o código anterior** e registrar quantos falham sem
a mudança. Teste que passa nos dois lados não protege nada.

---

## 10. Pontos em aberto

1. **Autenticação do webhook do ZapSign.** Confirmar na documentação se é HMAC
   ou segredo na URL. Enquanto não souber, **não** aceitar webhook sem
   verificação.
2. **Redirecionamento do signatário.** A spec depende de o ZapSign devolver a
   paciente ao final sem segundo link. Confirmar antes do passo 4.
3. **CNPJ e razão social** das três clínicas.
4. **Aceite da Clara** em constar identificada em toda ficha.
5. **Retenção.** Por quanto tempo a ficha fica guardada, e o que acontece se a
   paciente pedir exclusão pela LGPD. Prontuário costuma ter prazo legal próprio
   que se sobrepõe ao pedido de exclusão; confirmar com o advogado.

Os itens 1 e 2 travam o passo 4. Os demais travam só a ida a produção.
