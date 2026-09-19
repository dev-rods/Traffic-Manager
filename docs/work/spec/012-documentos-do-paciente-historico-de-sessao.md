# Spec — 012 Documentos do paciente: histórico por sessão

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/012-documentos-do-paciente-historico-de-sessao.md`
- **Anexo obrigatório:** `prd/012-anexo-mapa-areas-protocolo.md` — os valores e o
  mapa. Nenhum número desta feature sai da cabeça de quem implementa.

---

## 1. Resumo

Uma pasta de Documentos por paciente, abrindo direto no **histórico por sessão**.
Cada registro tem data, profissional, observações e N **aplicações** — uma por
área, com método e parâmetros. Escolhido o método, os parâmetros vêm do protocolo
da clínica conforme o tipo de pele da paciente, e seguem editáveis.

Seis tabelas no banco (duas colunas novas + quatro tabelas), seis Lambdas, uma
página nova e um atalho na Agenda. A trilha de auditoria guarda o estado completo
a cada escrita.

**O bot não participa de nada disto.** Nenhuma tool lê ou escreve estas tabelas,
nem o `skin_type`.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/services/protocolo_laser.py` | Os 3 métodos, os campos de cada um, e a busca do parâmetro sugerido |
| `scheduler/src/services/historico_de_sessao.py` | Montar registro do agendamento, validar aplicações, gravar a trilha |
| `scheduler/src/functions/patient_record/create.py` | `POST` registro |
| `scheduler/src/functions/patient_record/list.py` | `GET` registros do paciente |
| `scheduler/src/functions/patient_record/update.py` | `PUT` registro |
| `scheduler/src/functions/patient_record/delete.py` | `DELETE` (soft) |
| `scheduler/src/functions/patient_record/history.py` | `GET` trilha de um registro |
| `scheduler/src/functions/patient_record/protocol.py` | `GET` protocolo + mapa, para a tela sugerir sem ida e volta por linha |
| `scheduler/sls/functions/patient_record.yml` | Interface das 6 Lambdas |
| `frontend/src/pages/documentos/DocumentosPage.tsx` | A pasta, abrindo no histórico |
| `frontend/src/pages/documentos/components/HistoricoDeSessao.tsx` | A lista |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx` | Criar/editar |
| `frontend/src/pages/documentos/components/AplicacoesField.tsx` | A tabela de aplicações |
| `frontend/src/pages/documentos/components/ParametrosDoMetodo.tsx` | Os campos que mudam por método |
| `frontend/src/pages/documentos/components/AvisosDoProtocolo.tsx` | Os avisos, palavra por palavra do documento |
| `frontend/src/pages/documentos/components/HistoricoDeEdicoes.tsx` | O painel do selo "editado" |
| `frontend/src/services/sessionRecords.service.ts` | HTTP |
| `frontend/src/hooks/useSessionRecords.ts` | Queries e mutations |
| `frontend/src/hooks/useProtocoloLaser.ts` | Protocolo + mapa, cacheado |
| `frontend/src/lib/protocolo.ts` | Espelho do cálculo da sugestão, para a tela não piscar |
| `scheduler/tests/unit/test_protocolo_laser.py` | Os valores, conferidos contra o anexo |
| `scheduler/tests/unit/test_mapa_de_areas.py` | O mapa cobre o catálogo real |
| `scheduler/tests/unit/test_historico_de_sessao.py` | Montagem e validação |
| `scheduler/tests/unit/test_trilha_de_auditoria.py` | Fiação: nada se perde |
| `scheduler/tests/unit/test_bot_nao_ve_prontuario.py` | Superfície de tools |
| `frontend/src/pages/documentos/components/*.test.tsx` | Comportamento das telas |
| `scheduler/tests/integration/historico-de-sessao.md` | Casos via curl |
| `scheduler/tests/postman/historico-de-sessao.postman_requests.json` | Requests |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/scripts/setup_database.py` | 2 colunas, 4 tabelas, índices e o seed do protocolo + mapa |
| `scheduler/src/functions/appointment/list.py` | Filtro `patientId` |
| `scheduler/src/functions/patient/update.py` | Aceitar `skinType` |
| `scheduler/src/functions/patient/list.py` | Devolver `skin_type` |
| `scheduler/serverless.yml` | Incluir `patient_record.yml` |
| `frontend/src/router.tsx` | Rota `pacientes/:patientId/documentos` |
| `frontend/src/pages/pacientes/components/PatientsTable.tsx` | Botão Documentos |
| `frontend/src/pages/pacientes/components/CadastroFields.tsx` | Campo Tipo de pele |
| `frontend/src/pages/agenda/components/*` (popover) | Atalho `Registrar sessão` |
| `frontend/src/types/index.ts` | Tipos novos |

---

## 4. Ordem de implementação

Backend inteiro antes do frontend, e o protocolo antes de tudo — é dele que o
resto depende.

1. **Migrations + seed** (`setup_database.py`)
2. **`protocolo_laser.py` + `test_protocolo_laser.py` + `test_mapa_de_areas.py`**
3. **`historico_de_sessao.py` + testes**
4. **Handlers + `patient_record.yml` + `serverless.yml`**
5. **`appointment/list.py` (`patientId`), `patient/update.py` e `list.py` (`skinType`)**
6. **`test_bot_nao_ve_prontuario.py`**
7. **Migration em prod + `serverless deploy --stage prod`** — obrigatoriamente antes de 8
8. **Frontend:** types → hooks/services → `ParametrosDoMetodo` → `AplicacoesField` → modal → página → botão → atalho na Agenda
9. **Docs de teste**

---

## 5. Detalhes por arquivo

### `scheduler/src/scripts/setup_database.py`

**Colunas novas**

```python
# O tipo de pele decide qual dos dois protocolos alimenta a sugestao de
# parametro. Marcado SO pela profissional, no painel: o bot nunca escreve
# aqui e nenhuma tool dele expoe este campo. Ver protocolo_laser.
"ALTER TABLE scheduler.patients ADD COLUMN IF NOT EXISTS skin_type VARCHAR(10)",
"""ALTER TABLE scheduler.patients DROP CONSTRAINT IF EXISTS patients_skin_type_check""",
"""ALTER TABLE scheduler.patients ADD CONSTRAINT patients_skin_type_check
   CHECK (skin_type IS NULL OR skin_type IN ('BRANCA','NEGRA'))""",
```

**Tabelas novas** — nesta ordem (FK):

`laser_protocol_parameters`
```sql
id UUID PK, skin_type VARCHAR(10) NOT NULL, method VARCHAR(20) NOT NULL,
protocol_area_key VARCHAR(60) NOT NULL, protocol_area_name VARCHAR(120) NOT NULL,
fluence_j NUMERIC(5,2) NOT NULL, energy_kj NUMERIC(5,2),
stacks SMALLINT, passes SMALLINT,
source VARCHAR(20) NOT NULL DEFAULT 'PDF',
UNIQUE (skin_type, method, protocol_area_key)
```
Sem `clinic_id` (decisão do André). `source` distingue `PDF` de `CLINICA` — as
linhas `glabela` e `nariz` não vêm dos documentos, e uma referência clínica tem
de dizer de onde cada número veio.

`area_protocol_map`
```sql
id UUID PK, area_id UUID NOT NULL REFERENCES scheduler.areas(id) ON DELETE CASCADE,
protocol_area_key VARCHAR(60) NOT NULL, display_order SMALLINT NOT NULL DEFAULT 0,
UNIQUE (area_id, protocol_area_key)
```
Uma área pode ter **duas** linhas (composta). Área sem linha = sem sugestão.

`patient_session_records`
```sql
id UUID PK, clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
patient_id UUID NOT NULL REFERENCES scheduler.patients(id),
appointment_id UUID REFERENCES scheduler.appointments(id),
professional_id UUID REFERENCES scheduler.professionals(id),
session_date DATE NOT NULL,
tanned_skin BOOLEAN NOT NULL DEFAULT FALSE,
skin_type_snapshot VARCHAR(10),
notes TEXT,
created_by_user_id UUID,
deleted_at TIMESTAMPTZ,
version INTEGER NOT NULL DEFAULT 1,
created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
```

`patient_session_applications`
```sql
id UUID PK,
record_id UUID NOT NULL REFERENCES scheduler.patient_session_records(id) ON DELETE CASCADE,
area_id UUID REFERENCES scheduler.areas(id),
area_name VARCHAR(160) NOT NULL,
protocol_area_key VARCHAR(60),
method VARCHAR(20),
fluence_j NUMERIC(5,2), energy_kj NUMERIC(5,2),
stacks SMALLINT, passes SMALLINT,
display_order SMALLINT NOT NULL DEFAULT 0
```

`patient_session_record_audit`
```sql
id UUID PK, record_id UUID NOT NULL, clinic_id VARCHAR(100) NOT NULL,
action VARCHAR(10) NOT NULL, snapshot JSONB NOT NULL,
changed_by_name VARCHAR(255), changed_at TIMESTAMPTZ DEFAULT NOW()
```
**Sem FK em `record_id`, de propósito:** a trilha tem de sobreviver ao registro.

**Índices**
```sql
idx_session_records_patient ON (patient_id, session_date DESC) WHERE deleted_at IS NULL
idx_session_applications_record ON (record_id)
idx_session_applications_area ON (area_id)   -- "qual fluencia usei nesta area"
idx_session_audit_record ON (record_id, changed_at)
idx_area_protocol_map_area ON (area_id)
```

**Seeds** — idempotentes (`ON CONFLICT DO NOTHING`), valores do anexo §5 e mapa
do anexo §1–3. O mapa casa a área **pelo nome exato** do catálogo, dentro de
cada clínica:
```sql
INSERT INTO scheduler.area_protocol_map (area_id, protocol_area_key, display_order)
SELECT a.id, m.key, m.ord
FROM (VALUES ('Axilas','axilas',0), ...) AS m(area_name, key, ord)
JOIN scheduler.areas a ON a.name = m.area_name
ON CONFLICT DO NOTHING
```
Casa por nome **exato** aqui e só aqui, porque é seed conferido contra o
catálogo real. O teste `test_mapa_de_areas` é o que impede a divergência
silenciosa quando alguém renomear uma área — ele falha, como o de 16/09.

### `scheduler/src/services/protocolo_laser.py` — **criar**

Cabeçalho registrando: os 3 métodos, de onde vieram os valores, e por que o mapa
é tabela e não casamento de nome (citar o defeito de 16/09/2026).

```python
METODOS = {
    "SHR":          {"campos": ("fluence_j", "energy_kj")},
    "SHR_STACKING": {"campos": ("fluence_j", "stacks", "passes")},
    "HR":           {"campos": ("fluence_j", "energy_kj")},
}

def campos_do_metodo(metodo) -> tuple
    """Quais parâmetros este método usa. Fonte única - a tela espelha."""

def sugestao(db, protocol_area_key, metodo, skin_type) -> dict | None
    """O parâmetro inicial, ou None quando não há linha.

    None é resultado válido e significa "sem parâmetro sugerido". Nunca
    aproximar, nunca cair num valor de outra área: sugerir a fluência errada
    num equipamento que queima pele é pior do que não sugerir nada.
    """

def metodos_disponiveis(db, protocol_area_key) -> list
    """Os métodos que o protocolo tem para esta área.

    Um só -> a tela já deixa escolhido. Mais de um (Buço tem Stacking e HR) ->
    fica em branco: escolher por ela seria decidir conduta clínica.
    """

def avisos(metodo, skin_type, bronzeada) -> list[str]
    """Os avisos do documento, palavra por palavra. Ver anexo §6.

    HR + bronzeada nao e sugerido: o documento diz "nunca utilize", e isso e
    categorico. Mas nao BLOQUEIA - a decisao e de quem aplica, e o software
    que impede conduta acaba sendo contornado por fora, sem registro.
    """
```

`sugestao` **nunca** aplica fallback entre tipos de pele ou métodos.

### `scheduler/src/services/historico_de_sessao.py` — **criar**

```python
def aplicacoes_do_agendamento(db, appointment_id, skin_type) -> list[dict]
    """As aplicações que o registro nasce tendo.

    Le as areas do agendamento em appointment_service_areas, expande cada uma
    pelo area_protocol_map (a composta vira DUAS) e busca a sugestao. Area sem
    mapa entra com area_name preenchido e parametros vazios.
    """

def valida_aplicacoes(aplicacoes) -> list[dict]
    """Normaliza e recusa o que nao faz sentido.

    - `area_name` obrigatorio (e o que sobrevive ao catalogo)
    - metodo, se informado, tem de estar em METODOS
    - so os campos do metodo sao gravados: mandar `stacks` num SHR e sinal de
      tela desatualizada, e gravar isso poluiria a consulta depois
    - fluencia/energia > 0 quando presentes
    """

def grava_trilha(db, record_id, clinic_id, action, estado, por) -> None
    """Um append por escrita, com o estado COMPLETO depois da mudanca.

    Snapshot e nao diff: diff parece economico e depois nao reconstitui nada
    sozinho. O registro e pequeno e escrito uma vez por sessao.
    """
```

### Handlers `scheduler/src/functions/patient_record/`

Rotas, todas sob a clínica:

| Método | Rota |
|---|---|
| POST | `/clinics/{clinicId}/patients/{patientId}/session-records` |
| GET | `/clinics/{clinicId}/patients/{patientId}/session-records` |
| PUT | `/clinics/{clinicId}/session-records/{recordId}` |
| DELETE | `/clinics/{clinicId}/session-records/{recordId}` |
| GET | `/clinics/{clinicId}/session-records/{recordId}/history` |
| GET | `/clinics/{clinicId}/laser-protocol` |

- `create`: aceita `appointmentId` (traz as aplicações prontas) ou `sessionDate`
  avulsa. Grava `skin_type_snapshot` com o tipo de pele **no momento**.
- `update`: lock otimista por `version`, como em `appointments`. Substitui as
  aplicações inteiras (delete + insert), que é o que a tela manda.
- `delete`: soft (`deleted_at`), trilha com `action='DELETE'`.
- `protocol`: devolve as 78 linhas + o mapa da clínica num payload só. Cacheado
  no frontend — sem isto a tela faria uma chamada por linha de aplicação.
- Todos: `ValueError` → 400.

### `scheduler/src/functions/appointment/list.py`

Aceitar `patientId` como query param e acrescentar `AND a.patient_id = %s::uuid`.
O `GET` de registros devolve junto os agendamentos do paciente **sem** registro,
que é o que a tela oferece em "de qual sessão?".

### `scheduler/src/functions/patient/update.py` e `list.py`

`skinType` entra no `ALLOWED_FIELDS` do update (mapeando para `skin_type`) e no
`SELECT` da listagem. **Só isso** — nenhum outro caminho escreve o campo.

### `frontend/src/pages/documentos/components/ParametrosDoMetodo.tsx` — **criar**

Os campos mudam com o método, espelhando `METODOS`:

```
SHR            [ Fluência (J) ]  [ Energia (kJ) ]
SHR Stacking   [ Fluência (J) ]  [ Stacks ▾ ]  [ Passadas ]
HR             [ Fluência (J) ]  [ Energia (kJ) ]
```

Rótulos **exatamente** como os PDFs escrevem. Stacks como seletor de 2 a 5, com
as bolinhas do documento (`●●●`) ao lado do número — é assim que ela lê o
material.

Trocar o método **repõe** a sugestão e limpa os campos que o método novo não
usa.

### `frontend/src/pages/documentos/components/AplicacoesField.tsx` — **criar**

Uma linha por aplicação: área, método, parâmetros, remover. `+ Adicionar área`
com combo do catálogo e texto livre.

**Os três métodos estão sempre disponíveis, em qualquer área.** O protocolo diz
qual COMEÇAR, não qual é permitido - corrigido em 19/09/2026, depois de o André
não conseguir escolher Stacking numa axila (que no material só tem SHR e HR). O
que não tem sugestão aparece marcado na lista, e escolhê-lo deixa os campos
vazios para ela informar o que usou.

Área que o protocolo não conhece **continua editável**, com método e parâmetros.
Antes ela não mostrava campo nenhum, e a profissional simplesmente não conseguia
registrar o que tinha feito.

Nenhuma opção fica `disabled` - nem o HR em pele bronzeada. O aviso é o que o
documento manda mostrar; impedir seria conduta, e conduta é de quem aplica.

### `frontend/src/pages/documentos/DocumentosPage.tsx` — **criar**

Abre no histórico. Seletor de documento no topo, hoje com um item; o termo de
consentimento **não aparece** (não prometemos data que não temos).

4 estados tratados. O vazio oferece o agendamento sem registro, com botão.

### Atalho na Agenda

`Registrar sessão` no popover do agendamento abre o `RegistroDeSessaoModal` já
com aquele agendamento escolhido. É o caminho do caso comum — ela acabou de
atender e o paciente está na tela.

---

## 6. Convenções a respeitar

- Migrations idempotentes; `CREATE TABLE` e `MIGRATIONS` em sincronia.
- **Fonte única:** `METODOS` e os campos de cada método existem em
  `protocolo_laser.py`; `frontend/src/lib/protocolo.ts` espelha **com comentário
  dizendo que espelha**, como `duracao.ts` já faz.
- Snapshot de nome (`area_name`) e de valores: o passado não se reescreve.
- Frontend: named exports, zero `any`, TanStack Query, 4 estados, grid 4pt e os
  princípios Impeccable de `frontend/CLAUDE.md`.
- Logging com prefixo `[Prontuario]`.
- **Backend e migration antes do frontend.**

---

## 7. Testes que precisam existir

Além dos óbvios:

- **`test_protocolo_laser`**: cada uma das 78 linhas conferida contra o anexo.
  Axilas SHR = 7/8 na branca e 5/7 na negra. `sugestao` devolve `None` para
  combinação inexistente, e **não** cai em outro tipo de pele nem outro método.
- **`test_mapa_de_areas`**: o mapa é conferido contra o catálogo real de
  `tests/unit/catalogo_real.py`. Toda área ou tem linha, ou está numa lista
  explícita de "sem protocolo". Renomear área no painel acende vermelho aqui.
  *É o teste que a lição de 16/09/2026 comprou.*
- **`test_historico_de_sessao`**: `Virilha Completa + ânus` gera **duas**
  aplicações, com métodos diferentes; área sem mapa entra sem parâmetro;
  `valida_aplicacoes` recusa `stacks` num SHR.
- **`test_trilha_de_auditoria`**: editar preserva o estado anterior; excluir
  mantém a trilha; a trilha sobrevive ao registro.
- **`test_bot_nao_ve_prontuario`**: nenhuma tool em `ai_tools.py` cita as tabelas
  novas nem `skin_type`, e o prompt do agente também não. Fiação, não intenção.

---

## 8. O que esta spec deliberadamente não faz

- Não toca em `ai_tools.py`, `conversation_agent.py` nem no prompt.
- Não bloqueia método por regra clínica — avisa, e a decisão fica com quem
  aplica.
- Não resolve a autenticação por usuário. `created_by_user_id` nasce nullable e
  vazia. **A autoria é declarada, não provada**, e isso está no PRD como decisão
  consciente do André, não como esquecimento.
- Não edita protocolos pelo painel. A tabela é semeada por migration.
