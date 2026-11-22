# CRM de leads - Plano de implementação (Spec 057)

> **Para agentes:** executar tarefa por tarefa com `executing-plans` (ou um subagente por tarefa). Passos usam `- [ ]`. PRD de origem: `docs/work/prd/057-crm-de-leads.md`.

**Objetivo:** cada lead ganha um estágio (regra, modelo ou atendente), e a página `/crm` filtra por estágio e origem, corrige e dispara mensagem em lote para o grupo filtrado.

**Arquitetura:** estágio gravado em `scheduler.leads` e recalculado por uma Lambda diária (`ClassificaLeads`) que lê a última mensagem de cada lead no MessageEvents, aplica regras puras e chama o modelo só para triagem (WhatsApp novo) e desfecho (parado há N dias). Toda mudança vira linha em `lead_stage_events` (append-only, ninguém lê ainda). Correção manual grava `MANUAL` e trava a regra; fato da agenda vence tudo.

**Stack:** Python 3.13 (Lambda, unittest), Postgres (Supabase), DynamoDB (MessageEvents, sessões), Anthropic API via `AnthropicService`, React 19 + TS + TanStack Query v5 + Vitest.

## Restrições globais

- Branch `feat/057-crm-de-leads`, PR para `main`. Nunca commit em main. Sem co-author do agente no commit.
- Hífen `-`, nunca travessão.
- Migrations idempotentes (`ADD COLUMN IF NOT EXISTS`, `DO $$ IF NOT EXISTS`), e o `CREATE TABLE` da lista `TABLES` atualizado junto.
- Backend: logs com `[traceId: ...]`; segredos só via env/SSM; testes em `scheduler/tests/unit/` com `unittest`, rodados por `cd scheduler && python -m unittest tests.unit.<modulo> -v`; a suíte inteira com `python -m pytest tests/unit -q` antes de cada commit. Runtime python3.8 (ver revisões).
- Frontend: named exports, zero `any`, 4 estados, query keys por factory, nunca service direto no componente, `npm run lint` com zero warnings, design conforme `frontend/CLAUDE.md`.
- Modelo do classificador: `claude-haiku-4-5-20251001`, temperatura 0, `max_tokens` 120.
- Nomes dos estágios (fechados): `SEM_CONVERSA`, `INICIADA_SEM_RESPOSTA`, `EM_ANDAMENTO`, `AGUARDANDO_NOS`, `SUMIU`, `NAO_AGENDOU`, `CANCELOU`, `FALTOU`, `AGENDOU`, `NAO_E_LEAD`. Fontes: `REGRA`, `MODELO`, `MANUAL`, `HISTORICO`.

## Revisões de 21/11/2026 (main de hoje; vencem o texto das tarefas onde conflitam)

Escrita em 24/10 como Spec 026 e guardada. Reaberta em 21/11 sobre a main (90 PRs depois). O que muda, por tarefa:

| Tarefa | Antes | Agora |
|---|---|---|
| T1 | lista `MIGRATIONS` | `setup_database.py` tem uma lista só, `SQL_STATEMENTS`; os statements vão ao fim dela, depois do bloco da PRD 039 (`contatos_silenciados`). O `CREATE TABLE` de `leads` e `clinics` na mesma lista ganha as colunas. |
| T2 | `Sinais.agendamentos: tuple[status]` + `tem_agendamento_futuro_confirmado`; FALTOU vence CONFIRMED | **PRD 054:** `Sinais.ultimo_agendamento: Optional[str]` = status do agendamento mais recente (data e hora) **sem** `rescheduled_to_id` (remarcação fica de fora). `CONFIRMED` → AGENDOU, `NO_SHOW` → FALTOU, `CANCELLED` → CANCELOU, `None` → segue para as regras de conversa. Testes da classe `TestFatosDaAgenda` reescritos nesse formato. |
| T3 | `tabela.query(...)` direto, com o `try/except TypeError` | Usar `MessageTracker.get_conversation_messages(clinic_id, variante, limit)` por variante (já existe, lê `MSG#` em ordem cronológica e devolve `direction`, `content`, `created_at`); a tabela falsa do teste dubla o tracker, não o boto3. Timestamp é `createdAt`/`created_at` (ISO `...Z`). |
| T4 | `AnthropicService.create_message(system, messages, model, temperature, max_tokens)` | Assinatura confirmada: `create_message(system, messages, tools=None, model=DEFAULT_MODEL, temperature=None, max_tokens=1024, tool_choice=None)`, devolve o JSON cru e lança `AnthropicError`. Padrão de parse igual ao de `retomada.classifica`. Runtime da Lambda é **python3.8**: `typing.List/Optional`, nada de `list[str]` nem `X | None`. |
| T6 | `_agendamentos_por_variante` lia todo status | SQL com `AND a.rescheduled_to_id IS NULL`, `JOIN patients p ... AND p.deleted_at IS NULL`, `ORDER BY a.appointment_date DESC, a.start_time DESC`; `_sinais` pega o primeiro entre as variantes do telefone. IAM da função: `dynamodb:Query` na `message-events` (via tracker) e logs. Nova função conta no `LIMITE_DE_FUNCOES` (104; 86 hoje). Depois do deploy, `aws logs put-retention-policy` de 90 dias no log group novo. |
| T7 | `require_acesso(event, "crm.ler")` em `list.py` | Mantido. `ListLeads` tem IAM próprio (BatchGetItem nas sessões): não mexer. A chave mestra entra como ADMIN. |
| T8 | rota `patch` com `cors: true` | **Sem `cors:`** (PRD 055: `TestSemCors` proíbe; a API entra pelo rewrite da Vercel). |
| T10 | modal aceita `Destinatario`; resultados por `patientId` | `useSendBatchMessages`/`BatchMessageResult` indexam por `id` do destinatário (renomear `patientId` → `id` no hook, no modal e nos testes; `SendMessagePayload.patient_id` continua indo no `metadata` por compatibilidade). |
| T10b (nova) | - | **PRD 039 vence:** `POST /send` com `campanha` recusa contato silenciado (`silencio.esta_silenciado`) com 409 `motivo: "silenciado"`, antes das demais recusas. `MOTIVOS`/`descreveFalha` em `useMessages.ts` ganham o rótulo "Contato silenciado". Teste unitário no handler. |
| T11 | `router.tsx`, `lib/permissoes.ts`, `AppLayout` | Confirmados. `ROTAS_DO_STAFF` ganha `'/crm'`. Botão "Disparar mensagem" só para `ehAdmin` (`POST /send` é ADMIN). Sem componente Popover genérico: o `PopoverDeEstagio` inline da tarefa fica. `Lead` em `types/index.ts` ganha também `bot_silenciado?: boolean`, que o backend já manda. |
| T2 (22/11) | INICIADA_SEM_RESPOSTA sem prazo; CANCELOU/FALTOU absolutos | `Sinais.ultimo_agendamento_em: Optional[datetime]` (horário do agendamento em UTC, `_quando` no job pelo fuso da clínica). `_pela_agenda` devolve `None` para CANCELOU/FALTOU quando a última mensagem é do lead e posterior a esse horário. `_pela_conversa`: só nós falamos há mais de N dias → SUMIU (transcrição e `first_contact_at`). Testes novos em `TestEstagiosDeConversa` e `TestFatosDaAgenda`. |
| T4 (22/11) | `precisa_de_desfecho` para SUMIU e INICIADA_SEM_RESPOSTA | SUMIU e AGUARDANDO_NOS (INICIADA nunca tem fala do lead). `_SYSTEM_DESFECHO` cita "encerrou com um agradecimento sem pedir horário" como razão de NAO_AGENDOU. |
| T12 | prod no mesmo fluxo | **Até dev, por autorização do André em 21/11** (criar contatos e eventos em dev, usar o contato dele no +5511970522647). Prod só depois do merge, com autorização. Roteiro em `scheduler/tests/integration/057-crm-de-leads.md`. |

## Duas adaptações em relação ao PRD (decididas ao planejar)

1. **`dias_parado` e `ultima_mensagem_de` ficam gravados pelo job** (colunas `ultima_mensagem_em`, `ultima_mensagem_de` em `leads`) em vez de calculados na listagem. Motivo: a listagem só tem o espelho do z-api, sem direção; calcular na hora exigiria uma query no DynamoDB por lead a cada página. São o mesmo retrato noturno do estágio, com a mesma defasagem, documentado no código.
2. **Disparo em lote não muda o backend.** O fluxo atual já faz uma chamada `POST /send` por destinatário com `phone`; `patient_id` só serve de chave no cliente. O modal passa a aceitar qualquer destinatário com `id`, `name`, `phone`. O item 8.3 do PRD fica atendido no cliente.

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `scheduler/src/scripts/setup_database.py` | migrations e `CREATE TABLE` |
| `scheduler/src/services/estagio_do_lead.py` | constantes e regras puras: `decide(sinais, agora) -> Decisao` |
| `scheduler/src/services/transcricao.py` | leitura do MessageEvents: última mensagem e transcrição |
| `scheduler/src/services/classificador_de_lead.py` | triagem e desfecho via modelo, teto de chamadas |
| `scheduler/src/services/estagio_repo.py` | escrita: `grava_estagio`, `marca_triagem`, `marca_desfecho_tentado` |
| `scheduler/src/functions/lead/classifica_estagios.py` | Lambda do job, `dryRun` |
| `scheduler/src/functions/lead/atualiza_estagio.py` | `PATCH .../leads/{leadId}/stage` |
| `scheduler/src/functions/lead/list.py`, `src/services/lead_service.py` | filtros `stage`, `source`, totais por estágio |
| `scheduler/src/utils/acesso.py` | permissões `crm.ler`, `crm.escrever` |
| `scheduler/sls/functions/lead/interface.yml` | `ClassificaLeads`, `AtualizaEstagioDoLead`, IAM |
| `frontend/src/types/index.ts` | `LeadStage`, `StageSource`, campos novos |
| `frontend/src/services/leads.service.ts` | params novos, `patchStage` |
| `frontend/src/hooks/useLeads.ts` | `useCorrigeEstagio` |
| `frontend/src/lib/permissoes.ts`, `router.tsx`, `layouts/AppLayout.tsx` | rota `/crm` |
| `frontend/src/pages/pacientes/components/BatchMessageModal.tsx` | aceita destinatário genérico |
| `frontend/src/pages/crm/*` | `CrmPage`, `ChipsDeEstagio`, `EstagioBadge`, `PopoverDeEstagio`, `estagios.ts` |

---

## Tarefa 1: Migrations

**Arquivos:** modificar `scheduler/src/scripts/setup_database.py`.

**Produz:** colunas `leads.stage`, `stage_reason`, `stage_source`, `stage_updated_at`, `triagem_feita_em`, `desfecho_tentado_em`, `ultima_mensagem_em`, `ultima_mensagem_de`; tabela `scheduler.lead_stage_events`; `clinics.crm_dias_parado`.

- [ ] **Passo 1: adicionar ao fim da lista `SQL_STATEMENTS`** (depois do bloco da PRD 039, `contatos_silenciados`):

```python
    # -- CRM de leads (PRD 057) ----------------------------------------------
    #
    # O estagio e um RETRATO noturno gravado no lead, recalculado pela Lambda
    # ClassificaLeads. Nao confundir com `conversation_status`, que a listagem
    # calcula na hora e diz QUEM conduz a conversa agora; o estagio diz EM QUE
    # PE a conversa esta. `ultima_mensagem_*` sao parte do mesmo retrato.
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS stage VARCHAR(32)",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS stage_reason VARCHAR(120)",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS stage_source VARCHAR(16)",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS stage_updated_at TIMESTAMPTZ",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS triagem_feita_em TIMESTAMPTZ",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS desfecho_tentado_em TIMESTAMPTZ",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS ultima_mensagem_em TIMESTAMPTZ",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS ultima_mensagem_de VARCHAR(4)",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_leads_stage') THEN
            ALTER TABLE scheduler.leads ADD CONSTRAINT chk_leads_stage CHECK (stage IS NULL OR stage IN (
                'SEM_CONVERSA','INICIADA_SEM_RESPOSTA','EM_ANDAMENTO','AGUARDANDO_NOS','SUMIU',
                'NAO_AGENDOU','CANCELOU','FALTOU','AGENDOU','NAO_E_LEAD'));
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_leads_stage_source') THEN
            ALTER TABLE scheduler.leads ADD CONSTRAINT chk_leads_stage_source CHECK (
                stage_source IS NULL OR stage_source IN ('REGRA','MODELO','MANUAL','HISTORICO'));
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_leads_ultima_mensagem_de') THEN
            ALTER TABLE scheduler.leads ADD CONSTRAINT chk_leads_ultima_mensagem_de CHECK (
                ultima_mensagem_de IS NULL OR ultima_mensagem_de IN ('LEAD','NOS'));
        END IF;
    END $$
    """,
    "CREATE INDEX IF NOT EXISTS idx_leads_clinic_stage ON scheduler.leads(clinic_id, stage)",

    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS crm_dias_parado INTEGER NOT NULL DEFAULT 7",

    # Append-only. Nenhum endpoint le daqui nesta entrega: existe para que o
    # funil e a taxa de erro do classificador tenham historico desde o dia 1.
    """
    CREATE TABLE IF NOT EXISTS scheduler.lead_stage_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
        lead_id UUID NOT NULL REFERENCES scheduler.leads(id),
        de VARCHAR(32),
        para VARCHAR(32) NOT NULL,
        fonte VARCHAR(16) NOT NULL,
        motivo VARCHAR(120),
        usuario_id UUID,
        criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_lead_stage_events_lead ON scheduler.lead_stage_events(lead_id, criado_em)",
```

- [ ] **Passo 2: atualizar o `CREATE TABLE IF NOT EXISTS scheduler.leads` em `TABLES`**, acrescentando antes de `metadata JSONB`:

```sql
        stage VARCHAR(32),
        stage_reason VARCHAR(120),
        stage_source VARCHAR(16),
        stage_updated_at TIMESTAMPTZ,
        triagem_feita_em TIMESTAMPTZ,
        desfecho_tentado_em TIMESTAMPTZ,
        ultima_mensagem_em TIMESTAMPTZ,
        ultima_mensagem_de VARCHAR(4),
```

E no `CREATE TABLE ... scheduler.clinics` da lista `TABLES`, acrescentar `crm_dias_parado INTEGER NOT NULL DEFAULT 7,` junto das outras colunas de configuração do bot.

- [ ] **Passo 3: rodar em dev** (dev e prod são bancos distintos; `MSYS_NO_PATHCONV=1` no Git Bash):

```bash
cd scheduler && export MSYS_NO_PATHCONV=1
get(){ aws ssm get-parameter --name "$1" --with-decryption --profile dev-andre --region us-east-1 --query 'Parameter.Value' --output text; }
export RDS_HOST=$(get /dev/SUPABASE_DB_HOST) RDS_PORT=$(get /dev/SUPABASE_DB_PORT) RDS_DATABASE=$(get /dev/SUPABASE_DB_NAME) RDS_USERNAME=$(get /dev/SUPABASE_DB_USER) RDS_PASSWORD=$(get /dev/SUPABASE_DB_PASSWORD)
python -m src.scripts.setup_database && python -m src.scripts.setup_database
```

Esperado: as duas execuções terminam sem erro (idempotência).

- [ ] **Passo 4: commit**

```bash
git add scheduler/src/scripts/setup_database.py
git commit -m "feat(crm): colunas de estagio em leads, lead_stage_events e crm_dias_parado"
```

---

## Tarefa 2: Regras de estágio (puro)

**Arquivos:** criar `scheduler/src/services/estagio_do_lead.py`; testar em `scheduler/tests/unit/test_estagio_do_lead.py`.

**Produz:**

```python
# constantes
SEM_CONVERSA, INICIADA_SEM_RESPOSTA, EM_ANDAMENTO, AGUARDANDO_NOS, SUMIU, \
NAO_AGENDOU, CANCELOU, FALTOU, AGENDOU, NAO_E_LEAD  # str
REGRA, MODELO, MANUAL, HISTORICO  # str
ESTAGIOS: tuple[str, ...]            # os 10
ESTAGIOS_EDITAVEIS: frozenset[str]   # os 7 que o PATCH aceita
ESTAGIOS_DA_AGENDA: frozenset[str]   # AGENDOU, CANCELOU, FALTOU
ORDEM_DA_FILA: tuple[str, ...]       # ordem dos chips

@dataclass(frozen=True)
class Sinais:
    stage: Optional[str]; stage_source: Optional[str]; stage_updated_at: Optional[datetime]
    first_contact_at: Optional[datetime]
    ultima_mensagem_de: Optional[str]      # 'LEAD' | 'NOS' | None
    ultima_mensagem_em: Optional[datetime]
    lead_ja_falou: bool
    tem_transcricao: bool                  # veio do MessageEvents
    chat_espelho_em: Optional[datetime]    # whatsapp_chats.last_message_at
    chat_espelho_nao_lidas: int
    ultimo_agendamento: Optional[str]      # status do mais recente sem rescheduled_to_id: CONFIRMED | CANCELLED | NO_SHOW | None

@dataclass(frozen=True)
class Decisao:
    stage: str; source: str; reason: Optional[str] = None

def decide(sinais: Sinais, agora: datetime, dias_parado: int = 7) -> Decisao
```

- [ ] **Passo 1: escrever os testes**

```python
# -*- coding: utf-8 -*-
"""Uma linha por estagio da secao 5 do PRD 057, mais os conflitos de precedencia."""
import unittest
from datetime import datetime, timedelta, timezone

from src.services import estagio_do_lead as e

AGORA = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
D = lambda dias: AGORA - timedelta(days=dias)


def sinais(**kw):
    base = dict(stage=None, stage_source=None, stage_updated_at=None, first_contact_at=None,
                ultima_mensagem_de=None, ultima_mensagem_em=None, lead_ja_falou=False,
                tem_transcricao=False, chat_espelho_em=None, chat_espelho_nao_lidas=0,
                ultimo_agendamento=None)
    base.update(kw)
    return e.Sinais(**base)


class TestEstagiosDeConversa(unittest.TestCase):
    def test_sem_nada_e_sem_conversa(self):
        self.assertEqual(e.decide(sinais(), AGORA), e.Decisao(e.SEM_CONVERSA, e.REGRA))

    def test_so_nos_falamos(self):
        s = sinais(ultima_mensagem_de="NOS", ultima_mensagem_em=D(1), tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.INICIADA_SEM_RESPOSTA)

    def test_first_contact_sem_evento_e_iniciada(self):
        s = sinais(first_contact_at=D(2))
        self.assertEqual(e.decide(s, AGORA).stage, e.INICIADA_SEM_RESPOSTA)

    def test_ultima_e_do_lead(self):
        s = sinais(ultima_mensagem_de="LEAD", ultima_mensagem_em=D(10), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_nossa_recente_depois_de_ele_falar_e_em_andamento(self):
        s = sinais(ultima_mensagem_de="NOS", ultima_mensagem_em=D(3), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.EM_ANDAMENTO)

    def test_nossa_antiga_depois_de_ele_falar_e_sumiu(self):
        s = sinais(ultima_mensagem_de="NOS", ultima_mensagem_em=D(8), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.SUMIU)

    def test_dias_parado_vem_da_clinica(self):
        s = sinais(ultima_mensagem_de="NOS", ultima_mensagem_em=D(8), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA, dias_parado=10).stage, e.EM_ANDAMENTO)


class TestFallbackDoEspelho(unittest.TestCase):
    def test_nao_lidas_e_aguardando_nos(self):
        s = sinais(chat_espelho_em=D(1), chat_espelho_nao_lidas=2)
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.AGUARDANDO_NOS, e.REGRA))

    def test_recente_lido_e_em_andamento(self):
        s = sinais(chat_espelho_em=D(2))
        self.assertEqual(e.decide(s, AGORA).stage, e.EM_ANDAMENTO)

    def test_antigo_dentro_de_60_dias_e_sumiu_por_regra(self):
        s = sinais(chat_espelho_em=D(20))
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.SUMIU, e.REGRA))

    def test_mais_de_60_dias_e_historico(self):
        s = sinais(chat_espelho_em=D(90))
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.SUMIU, e.HISTORICO))


class TestFatosDaAgenda(unittest.TestCase):
    def test_confirmado_e_agendou(self):
        self.assertEqual(e.decide(sinais(ultimo_agendamento="CONFIRMED"), AGORA).stage, e.AGENDOU)

    def test_ultimo_cancelado_e_cancelou(self):
        self.assertEqual(e.decide(sinais(ultimo_agendamento="CANCELLED"), AGORA).stage, e.CANCELOU)

    def test_ultimo_e_falta(self):
        # PRD 054: faltou e nao remarcou. Se tivesse remarcado, o NO_SHOW teria
        # rescheduled_to_id e ficaria de fora; o mais recente seria o CONFIRMED.
        self.assertEqual(e.decide(sinais(ultimo_agendamento="NO_SHOW"), AGORA).stage, e.FALTOU)

    def test_sem_agendamento_segue_para_a_conversa(self):
        self.assertEqual(e.decide(sinais(ultimo_agendamento=None), AGORA).stage, e.SEM_CONVERSA)

    def test_agendou_vence_manual(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MANUAL, stage_updated_at=D(1), ultimo_agendamento="CONFIRMED")
        self.assertEqual(e.decide(s, AGORA).stage, e.AGENDOU)

    def test_agendou_vence_nao_e_lead(self):
        s = sinais(stage=e.NAO_E_LEAD, stage_source=e.MODELO, stage_updated_at=D(1), ultimo_agendamento="CONFIRMED")
        self.assertEqual(e.decide(s, AGORA).stage, e.AGENDOU)


class TestJulgamentos(unittest.TestCase):
    def test_manual_trava_a_regra(self):
        s = sinais(stage=e.EM_ANDAMENTO, stage_source=e.MANUAL, stage_updated_at=D(1),
                   ultima_mensagem_de="NOS", ultima_mensagem_em=D(20), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.EM_ANDAMENTO, e.MANUAL))

    def test_manual_preserva_o_motivo(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MANUAL, stage_updated_at=D(1))
        d = e.decide(s, AGORA)
        self.assertEqual((d.stage, d.source), (e.NAO_AGENDOU, e.MANUAL))

    def test_nao_agendou_do_modelo_fica_sem_mensagem_nova(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="NOS", ultima_mensagem_em=D(10), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.NAO_AGENDOU)

    def test_mensagem_nova_do_lead_derruba_nao_agendou_do_modelo(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="LEAD", ultima_mensagem_em=D(1), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_nao_e_lead_do_modelo_fica(self):
        s = sinais(stage=e.NAO_E_LEAD, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="LEAD", ultima_mensagem_em=D(10), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.NAO_E_LEAD)

    def test_mensagem_nova_derruba_nao_e_lead_do_modelo(self):
        s = sinais(stage=e.NAO_E_LEAD, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="LEAD", ultima_mensagem_em=D(1), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)


class TestConstantes(unittest.TestCase):
    def test_editaveis_nao_incluem_agenda(self):
        self.assertFalse(e.ESTAGIOS_EDITAVEIS & e.ESTAGIOS_DA_AGENDA)

    def test_ordem_da_fila_cobre_os_nove_visiveis(self):
        self.assertEqual(len(e.ORDEM_DA_FILA), 9)
        self.assertNotIn(e.NAO_E_LEAD, e.ORDEM_DA_FILA)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `cd scheduler && python -m unittest tests.unit.test_estagio_do_lead -v`
Esperado: `ModuleNotFoundError: src.services.estagio_do_lead`.

- [ ] **Passo 3: implementar**

```python
# -*- coding: utf-8 -*-
"""Em que pe esta a conversa de cada lead: as regras, sem I/O.

Nao confundir com `status_da_conversa`, que diz QUEM conduz a conversa agora
(bot ou pessoa) e e calculado na hora da listagem. O estagio diz EM QUE PE a
conversa esta e e um retrato noturno gravado no lead (PRD 057).

A precedencia esta em `decide`, e a ordem e a regra:
fato da agenda > NAO_E_LEAD > MANUAL > veredito do modelo > regras de conversa.
Um fato (agendou) vence inclusive uma correcao manual, porque agendar nao e
julgamento. E a unica excecao a "MANUAL trava tudo".
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

SEM_CONVERSA = "SEM_CONVERSA"
INICIADA_SEM_RESPOSTA = "INICIADA_SEM_RESPOSTA"
EM_ANDAMENTO = "EM_ANDAMENTO"
AGUARDANDO_NOS = "AGUARDANDO_NOS"
SUMIU = "SUMIU"
NAO_AGENDOU = "NAO_AGENDOU"
CANCELOU = "CANCELOU"
FALTOU = "FALTOU"
AGENDOU = "AGENDOU"
NAO_E_LEAD = "NAO_E_LEAD"

REGRA = "REGRA"
MODELO = "MODELO"
MANUAL = "MANUAL"
HISTORICO = "HISTORICO"

ESTAGIOS = (SEM_CONVERSA, INICIADA_SEM_RESPOSTA, EM_ANDAMENTO, AGUARDANDO_NOS, SUMIU,
            NAO_AGENDOU, CANCELOU, FALTOU, AGENDOU, NAO_E_LEAD)
FONTES = (REGRA, MODELO, MANUAL, HISTORICO)

# A ordem dos chips e a ordem de trabalho: quem precisa de acao primeiro.
ORDEM_DA_FILA = (AGUARDANDO_NOS, SUMIU, INICIADA_SEM_RESPOSTA, SEM_CONVERSA, EM_ANDAMENTO,
                 NAO_AGENDOU, CANCELOU, FALTOU, AGENDOU)

ESTAGIOS_DA_AGENDA = frozenset({AGENDOU, CANCELOU, FALTOU})
# O que a atendente pode escolher no popover. Fato da agenda nao se edita.
ESTAGIOS_EDITAVEIS = frozenset(ESTAGIOS) - ESTAGIOS_DA_AGENDA

# O MessageEvents guarda 60 dias (PRD 022). Conversa mais antiga que isso so
# existe no espelho do z-api, sem texto: o estagio vai sem motivo e marcado
# HISTORICO para a tela nao fingir que leu a conversa.
DIAS_DE_RETENCAO_DOS_EVENTOS = 60


@dataclass(frozen=True)
class Sinais:
    stage: Optional[str]
    stage_source: Optional[str]
    stage_updated_at: Optional[datetime]
    first_contact_at: Optional[datetime]
    ultima_mensagem_de: Optional[str]        # "LEAD" | "NOS" | None
    ultima_mensagem_em: Optional[datetime]
    lead_ja_falou: bool
    tem_transcricao: bool
    chat_espelho_em: Optional[datetime]
    chat_espelho_nao_lidas: int
    ultimo_agendamento: Optional[str]


@dataclass(frozen=True)
class Decisao:
    stage: str
    source: str
    reason: Optional[str] = None


def _parado_ha(mais_que_dias: int, quando: Optional[datetime], agora: datetime) -> bool:
    return quando is not None and (agora - quando) > timedelta(days=mais_que_dias)


def _mensagem_nova_depois_do_veredito(s: Sinais) -> bool:
    """O lead falou DEPOIS de o modelo decidir? Entao o veredito caiu."""
    return (s.ultima_mensagem_de == "LEAD" and s.ultima_mensagem_em is not None
            and s.stage_updated_at is not None and s.ultima_mensagem_em > s.stage_updated_at)


# PRD 054: o agendamento mais recente que NAO e remarcacao decide. Quem faltou
# e remarcou e AGENDOU; quem remarcou tres vezes nao vira CANCELOU.
_PELO_STATUS = {"CONFIRMED": AGENDOU, "NO_SHOW": FALTOU, "CANCELLED": CANCELOU}


def _pela_agenda(s: Sinais) -> Optional[Decisao]:
    stage = _PELO_STATUS.get(s.ultimo_agendamento or "")
    return Decisao(stage, REGRA) if stage else None


def _pela_conversa(s: Sinais, agora: datetime, dias_parado: int) -> Decisao:
    if s.tem_transcricao and s.ultima_mensagem_de:
        if not s.lead_ja_falou:
            return Decisao(INICIADA_SEM_RESPOSTA, REGRA)
        if s.ultima_mensagem_de == "LEAD":
            return Decisao(AGUARDANDO_NOS, REGRA)
        if _parado_ha(dias_parado, s.ultima_mensagem_em, agora):
            return Decisao(SUMIU, REGRA)
        return Decisao(EM_ANDAMENTO, REGRA)

    if s.chat_espelho_em is not None:
        # So o espelho: existe conversa, sem direcao nem texto.
        fonte = HISTORICO if _parado_ha(DIAS_DE_RETENCAO_DOS_EVENTOS, s.chat_espelho_em, agora) else REGRA
        if s.chat_espelho_nao_lidas > 0:
            return Decisao(AGUARDANDO_NOS, fonte)
        if _parado_ha(dias_parado, s.chat_espelho_em, agora):
            return Decisao(SUMIU, fonte)
        return Decisao(EM_ANDAMENTO, fonte)

    if s.first_contact_at is not None:
        return Decisao(INICIADA_SEM_RESPOSTA, REGRA)
    return Decisao(SEM_CONVERSA, REGRA)


def decide(sinais: Sinais, agora: datetime, dias_parado: int = 7) -> Decisao:
    fato = _pela_agenda(sinais)
    if fato:
        return fato

    if sinais.stage_source == MANUAL and sinais.stage:
        return Decisao(sinais.stage, MANUAL)

    if sinais.stage in (NAO_E_LEAD, NAO_AGENDOU) and sinais.stage_source == MODELO:
        if not _mensagem_nova_depois_do_veredito(sinais):
            return Decisao(sinais.stage, MODELO)

    return _pela_conversa(sinais, agora, dias_parado)
```

Atenção ao teste `test_manual_preserva_o_motivo`: quem chama (`estagio_repo.grava_estagio`) só grava se `stage` ou `reason` mudou, e quando a decisão é `MANUAL` o repo mantém `stage_reason` atual. O `Decisao` manual sai com `reason=None` de propósito; ver Tarefa 5.

- [ ] **Passo 4: rodar e ver passar**

Run: `cd scheduler && python -m unittest tests.unit.test_estagio_do_lead -v`
Esperado: todos `ok`.

- [ ] **Passo 5: commit**

```bash
git add scheduler/src/services/estagio_do_lead.py scheduler/tests/unit/test_estagio_do_lead.py
git commit -m "feat(crm): regras puras de estagio do lead"
```

---

## Tarefa 3: Leitura da transcrição no MessageEvents

**Arquivos:** criar `scheduler/src/services/transcricao.py`; testar em `scheduler/tests/unit/test_transcricao.py`.

**Consome:** formato do MessageEvents: `pk = CLINIC#{clinic_id}#PHONE#{phone}`, `sk = MSG#{iso}#{id}` para mensagens e `STATUS#...` para status; `direction` em `INBOUND`/`OUTBOUND`; `content`; `createdAt` ISO `YYYY-MM-DDTHH:MM:SSZ`. `src.utils.phone.variantes_do_numero(phone) -> set[str]`.

**Produz:**

```python
@dataclass(frozen=True)
class Mensagem: de: str  # "LEAD" | "NOS"
                em: datetime; texto: str

def ultimas_mensagens(tabela, clinic_id: str, phone: str, limite: int = 40) -> list[Mensagem]
    # cronologica (antiga -> nova), unindo variantes do numero

def resumo(mensagens: list[Mensagem]) -> dict
    # {"ultima_de": "LEAD"|"NOS"|None, "ultima_em": datetime|None, "lead_ja_falou": bool}
```

- [ ] **Passo 1: testes com tabela falsa**

```python
# -*- coding: utf-8 -*-
"""A transcricao vem do MessageEvents, unindo as variantes do numero.

A tabela falsa devolve o que o DynamoDB devolveria para cada pk; o teste confere
a uniao, a ordem e a traducao de direcao para LEAD/NOS. STATUS_UPDATE fica fora.
"""
import os
import unittest
from datetime import datetime, timezone

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import transcricao as t

CLINIC = "clinicaessenciaestetica-9668a4"


class TabelaFalsa:
    def __init__(self, por_pk):
        self.por_pk = por_pk
        self.chamadas = []

    def query(self, **kw):
        self.chamadas.append(kw)
        pk = kw["ExpressionAttributeValues"][":pk"]
        itens = sorted(self.por_pk.get(pk, []), key=lambda i: i["sk"], reverse=True)
        return {"Items": itens[: kw.get("Limit", 50)]}


def msg(iso, direction, content, tipo="MSG"):
    return {"sk": f"{tipo}#{iso}#x", "direction": direction, "content": content, "createdAt": iso}


class TestUltimasMensagens(unittest.TestCase):
    def test_une_variantes_e_ordena_cronologicamente(self):
        tabela = TabelaFalsa({
            f"CLINIC#{CLINIC}#PHONE#5547997053940": [msg("2026-10-20T10:00:00Z", "OUTBOUND", "Oi")],
            f"CLINIC#{CLINIC}#PHONE#554797053940": [msg("2026-10-21T10:00:00Z", "INBOUND", "Quanto custa?")],
        })
        ms = t.ultimas_mensagens(tabela, CLINIC, "5547997053940")
        self.assertEqual([(m.de, m.texto) for m in ms], [("NOS", "Oi"), ("LEAD", "Quanto custa?")])
        self.assertEqual(ms[1].em, datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc))

    def test_ignora_status_update(self):
        tabela = TabelaFalsa({f"CLINIC#{CLINIC}#PHONE#5511999990000": [
            msg("2026-10-20T10:00:00Z", "OUTBOUND", "Oi"),
            msg("2026-10-20T10:00:05Z", "STATUS_UPDATE", "", tipo="STATUS"),
        ]})
        ms = t.ultimas_mensagens(tabela, CLINIC, "5511999990000")
        self.assertEqual(len(ms), 1)

    def test_respeita_o_limite_no_total(self):
        itens = [msg(f"2026-10-{d:02d}T10:00:00Z", "INBOUND", str(d)) for d in range(1, 29)]
        tabela = TabelaFalsa({f"CLINIC#{CLINIC}#PHONE#5511999990000": itens})
        self.assertEqual(len(t.ultimas_mensagens(tabela, CLINIC, "5511999990000", limite=10)), 10)

    def test_sem_eventos_devolve_vazio(self):
        self.assertEqual(t.ultimas_mensagens(TabelaFalsa({}), CLINIC, "5511999990000"), [])


class TestResumo(unittest.TestCase):
    def test_vazio(self):
        self.assertEqual(t.resumo([]), {"ultima_de": None, "ultima_em": None, "lead_ja_falou": False})

    def test_so_nos(self):
        ms = [t.Mensagem("NOS", datetime(2026, 10, 1, tzinfo=timezone.utc), "Oi")]
        self.assertEqual(t.resumo(ms)["lead_ja_falou"], False)
        self.assertEqual(t.resumo(ms)["ultima_de"], "NOS")

    def test_lead_falou_antes_e_nos_por_ultimo(self):
        ms = [t.Mensagem("LEAD", datetime(2026, 10, 1, tzinfo=timezone.utc), "Oi"),
              t.Mensagem("NOS", datetime(2026, 10, 2, tzinfo=timezone.utc), "Ola")]
        r = t.resumo(ms)
        self.assertEqual((r["ultima_de"], r["lead_ja_falou"]), ("NOS", True))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `cd scheduler && python -m unittest tests.unit.test_transcricao -v`
Esperado: `ModuleNotFoundError`.

- [ ] **Passo 3: implementar**

```python
# -*- coding: utf-8 -*-
"""A conversa de um lead, lida do MessageEvents.

E a unica fonte que tem DIRECAO e TEXTO: o espelho do z-api so diz que existe
conversa. Inclui o que a atendente manda pelo celular (chega como fromMe, autor
HUMANO). Retencao de 60 dias (PRD 022): conversa mais antiga nao esta aqui.

Uma query por variante do numero (com e sem o nono digito), unidas e ordenadas.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from boto3.dynamodb.conditions import Key

from src.utils.phone import variantes_do_numero

logger = logging.getLogger(__name__)

NOS = "NOS"
LEAD = "LEAD"
_DIRECAO = {"OUTBOUND": NOS, "INBOUND": LEAD}


@dataclass(frozen=True)
class Mensagem:
    de: str
    em: datetime
    texto: str


def _quando(item) -> Optional[datetime]:
    bruto = item.get("createdAt") or ""
    try:
        return datetime.strptime(bruto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def ultimas_mensagens(tabela, clinic_id: str, phone: str, limite: int = 40) -> List[Mensagem]:
    """As ultimas `limite` mensagens, da mais antiga para a mais nova."""
    encontradas: List[Mensagem] = []
    for variante in sorted(variantes_do_numero(phone)):
        pk = f"CLINIC#{clinic_id}#PHONE#{variante}"
        try:
            resposta = tabela.query(
                KeyConditionExpression=Key("pk").eq(pk) & Key("sk").begins_with("MSG#"),
                ExpressionAttributeValues={":pk": pk},
                ScanIndexForward=False,
                Limit=limite,
            )
        except TypeError:
            # boto3 nao aceita ExpressionAttributeValues junto de Key(): a tabela
            # falsa dos testes precisa do pk, o boto3 nao. Tenta sem.
            resposta = tabela.query(
                KeyConditionExpression=Key("pk").eq(pk) & Key("sk").begins_with("MSG#"),
                ScanIndexForward=False,
                Limit=limite,
            )
        except Exception as e:
            logger.error(f"[Transcricao] query falhou para {pk}: {e}")
            continue
        for item in resposta.get("Items", []):
            de = _DIRECAO.get(item.get("direction"))
            em = _quando(item)
            if de and em:
                encontradas.append(Mensagem(de, em, str(item.get("content") or "")))
    encontradas.sort(key=lambda m: m.em)
    return encontradas[-limite:]


def resumo(mensagens: List[Mensagem]) -> dict:
    if not mensagens:
        return {"ultima_de": None, "ultima_em": None, "lead_ja_falou": False}
    ultima = mensagens[-1]
    return {"ultima_de": ultima.de, "ultima_em": ultima.em,
            "lead_ja_falou": any(m.de == LEAD for m in mensagens)}
```

**Nota de implementação:** o `boto3` real recusa `ExpressionAttributeValues` sem placeholder na expressão. Em vez do `try/except TypeError`, faça a tabela falsa do teste ler o pk da `KeyConditionExpression` (`kw["KeyConditionExpression"]._values[0]._values[1]`) e chame o boto3 só com `KeyConditionExpression`, `ScanIndexForward`, `Limit`. Ajuste o teste para isso e remova o `except TypeError`. O código acima mostra a intenção; o commit deve ter uma única forma de chamada.

- [ ] **Passo 4: rodar e ver passar**

Run: `cd scheduler && python -m unittest tests.unit.test_transcricao -v`

- [ ] **Passo 5: commit**

```bash
git add scheduler/src/services/transcricao.py scheduler/tests/unit/test_transcricao.py
git commit -m "feat(crm): leitura da transcricao do lead no MessageEvents"
```

---

## Tarefa 4: Classificador (triagem e desfecho)

**Arquivos:** criar `scheduler/src/services/classificador_de_lead.py`; testar em `scheduler/tests/unit/test_classificador_de_lead.py`.

**Consome:** `AnthropicService.create_message(system, messages, model=..., temperature=..., max_tokens=...)` devolve o corpo da API (`{"content": [{"type": "text", "text": "..."}]}`), lança `AnthropicError`. `transcricao.Mensagem`.

**Produz:**

```python
MODELO_DO_CLASSIFICADOR = "claude-haiku-4-5-20251001"
TRIAGEM_MINIMO_DE_MENSAGENS_DO_LEAD = 3

@dataclass(frozen=True)
class Veredito: classe: str; motivo: str

class TetoAtingido(Exception): ...

class Classificador:
    def __init__(self, anthropic=None, max_chamadas: int = 200)
    chamadas: int
    def triagem(self, mensagens, clinic) -> Optional[Veredito]   # LEAD | NAO_E_LEAD
    def desfecho(self, mensagens, clinic) -> Optional[Veredito]  # NAO_AGENDOU | AINDA_ABERTO

def precisa_de_triagem(lead, mensagens) -> bool
def precisa_de_desfecho(lead, decisao, mensagens, agora, dias_parado) -> bool
def interpreta(texto: str, classes_validas) -> Optional[Veredito]
```

- [ ] **Passo 1: testes**

```python
# -*- coding: utf-8 -*-
"""O classificador le a transcricao e devolve classe + motivo curto, ou nada.

Sem chamar o modelo: o cliente e injetado e devolve o que o teste manda.
"""
import unittest
from datetime import datetime, timedelta, timezone

from src.services import classificador_de_lead as c
from src.services import estagio_do_lead as e
from src.services.transcricao import Mensagem

AGORA = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
CLINIC = {"clinic_id": "x", "name": "Clinica Teste", "display_name": "Clinica Teste"}


class AnthropicFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def create_message(self, **kw):
        self.chamadas.append(kw)
        return {"content": [{"type": "text", "text": self.respostas.pop(0)}]}


def conversa(n_lead=3):
    ms = [Mensagem("NOS", AGORA - timedelta(days=10), "Ola! Como posso ajudar?")]
    for i in range(n_lead):
        ms.append(Mensagem("LEAD", AGORA - timedelta(days=9, hours=i), f"msg {i}"))
    return ms


class TestInterpreta(unittest.TestCase):
    def test_json_valido(self):
        v = c.interpreta('{"classe": "NAO_E_LEAD", "motivo": "fornecedor de insumos"}', {"LEAD", "NAO_E_LEAD"})
        self.assertEqual(v, c.Veredito("NAO_E_LEAD", "fornecedor de insumos"))

    def test_json_dentro_de_texto(self):
        v = c.interpreta('Claro: {"classe":"LEAD","motivo":"quer agendar"} fim', {"LEAD", "NAO_E_LEAD"})
        self.assertEqual(v.classe, "LEAD")

    def test_classe_fora_do_enum_descarta(self):
        self.assertIsNone(c.interpreta('{"classe": "TALVEZ", "motivo": "x"}', {"LEAD", "NAO_E_LEAD"}))

    def test_nao_json_descarta(self):
        self.assertIsNone(c.interpreta("nao sei", {"LEAD"}))

    def test_motivo_truncado_e_sem_quebra(self):
        v = c.interpreta('{"classe": "LEAD", "motivo": "' + "a\\nb" * 80 + '"}', {"LEAD"})
        self.assertLessEqual(len(v.motivo), 120)
        self.assertNotIn("\n", v.motivo)


class TestTriagem(unittest.TestCase):
    def test_lead_de_site_nunca_passa(self):
        lead = {"source": "landing-page", "triagem_feita_em": None}
        self.assertFalse(c.precisa_de_triagem(lead, conversa(5)))

    def test_whatsapp_com_poucas_mensagens_espera(self):
        lead = {"source": "whatsapp", "triagem_feita_em": None}
        self.assertFalse(c.precisa_de_triagem(lead, conversa(2)))

    def test_whatsapp_com_tres_mensagens_passa(self):
        lead = {"source": "whatsapp", "triagem_feita_em": None}
        self.assertTrue(c.precisa_de_triagem(lead, conversa(3)))

    def test_ja_triado_nao_repete(self):
        lead = {"source": "whatsapp", "triagem_feita_em": AGORA}
        self.assertFalse(c.precisa_de_triagem(lead, conversa(5)))

    def test_chama_o_modelo_e_devolve_veredito(self):
        falso = AnthropicFalso(['{"classe":"NAO_E_LEAD","motivo":"proposta comercial"}'])
        v = c.Classificador(falso).triagem(conversa(), CLINIC)
        self.assertEqual(v.classe, "NAO_E_LEAD")
        self.assertEqual(falso.chamadas[0]["model"], c.MODELO_DO_CLASSIFICADOR)
        self.assertEqual(falso.chamadas[0]["temperature"], 0)


class TestDesfecho(unittest.TestCase):
    def test_so_para_sumiu_ou_iniciada_parados(self):
        lead = {"desfecho_tentado_em": None}
        parado = e.Decisao(e.SUMIU, e.REGRA)
        self.assertTrue(c.precisa_de_desfecho(lead, parado, conversa(), AGORA, 7))
        self.assertFalse(c.precisa_de_desfecho(lead, e.Decisao(e.EM_ANDAMENTO, e.REGRA), conversa(), AGORA, 7))

    def test_exige_que_o_lead_tenha_falado(self):
        lead = {"desfecho_tentado_em": None}
        so_nos = [Mensagem("NOS", AGORA - timedelta(days=10), "Oi")]
        self.assertFalse(c.precisa_de_desfecho(lead, e.Decisao(e.INICIADA_SEM_RESPOSTA, e.REGRA), so_nos, AGORA, 7))

    def test_ja_tentado_depois_da_ultima_mensagem_nao_repete(self):
        lead = {"desfecho_tentado_em": AGORA - timedelta(days=1)}
        self.assertFalse(c.precisa_de_desfecho(lead, e.Decisao(e.SUMIU, e.REGRA), conversa(), AGORA, 7))

    def test_tentado_antes_de_mensagem_nova_repete(self):
        lead = {"desfecho_tentado_em": AGORA - timedelta(days=30)}
        self.assertTrue(c.precisa_de_desfecho(lead, e.Decisao(e.SUMIU, e.REGRA), conversa(), AGORA, 7))

    def test_ainda_aberto_e_veredito_valido(self):
        falso = AnthropicFalso(['{"classe":"AINDA_ABERTO","motivo":"sem decisao"}'])
        self.assertEqual(c.Classificador(falso).desfecho(conversa(), CLINIC).classe, "AINDA_ABERTO")


class TestTeto(unittest.TestCase):
    def test_estoura_no_limite(self):
        falso = AnthropicFalso(['{"classe":"LEAD","motivo":"x"}'] * 3)
        cl = c.Classificador(falso, max_chamadas=2)
        cl.triagem(conversa(), CLINIC)
        cl.triagem(conversa(), CLINIC)
        with self.assertRaises(c.TetoAtingido):
            cl.triagem(conversa(), CLINIC)
        self.assertEqual(cl.chamadas, 2)

    def test_resposta_invalida_devolve_none_e_conta(self):
        cl = c.Classificador(AnthropicFalso(["???"]))
        self.assertIsNone(cl.triagem(conversa(), CLINIC))
        self.assertEqual(cl.chamadas, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `cd scheduler && python -m unittest tests.unit.test_classificador_de_lead -v`

- [ ] **Passo 3: implementar**

```python
# -*- coding: utf-8 -*-
"""Duas perguntas ao modelo sobre a conversa de um lead (PRD 057).

Triagem: "isto e um lead?" - so para quem chegou pelo WhatsApp, cedo (3
mensagens do contato). Fornecedor, cobranca e conversa pessoal saem do funil.

Desfecho: "por que nao agendou?" - so para quem parou ha N dias e chegou a
falar. Devolve NAO_AGENDOU com motivo curto, ou AINDA_ABERTO quando nao ha
decisao na conversa.

O modelo so SUGERE. A atendente corrige no painel e a correcao trava (MANUAL).
"""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

from src.services import estagio_do_lead as estagio
from src.services.transcricao import LEAD, Mensagem

logger = logging.getLogger(__name__)

MODELO_DO_CLASSIFICADOR = "claude-haiku-4-5-20251001"
TRIAGEM_MINIMO_DE_MENSAGENS_DO_LEAD = 3
MAX_CHAMADAS_PADRAO = 200
TAMANHO_DO_MOTIVO = 120

CLASSES_DA_TRIAGEM = frozenset({"LEAD", "NAO_E_LEAD"})
CLASSES_DO_DESFECHO = frozenset({"NAO_AGENDOU", "AINDA_ABERTO"})

_SYSTEM_TRIAGEM = (
    "Voce le conversas de WhatsApp de uma clinica de depilacao a laser chamada {nome}. "
    "Decida se o contato e um LEAD (pessoa interessada em tratamento, agendamento, preco, duvida de paciente) "
    "ou NAO_E_LEAD (fornecedor, proposta comercial, cobranca, conversa pessoal, spam, engano). "
    'Responda SOMENTE um JSON: {{"classe": "LEAD" | "NAO_E_LEAD", "motivo": "<ate 8 palavras>"}}.'
)
_SYSTEM_DESFECHO = (
    "Voce le conversas de WhatsApp de uma clinica de depilacao a laser chamada {nome}. "
    "A pessoa parou de responder e nao agendou. Decida: NAO_AGENDOU quando a conversa mostra uma razao "
    "ou uma recusa (achou caro, mora longe, so pesquisando, vai pensar, fora do horario, contraindicacao), "
    "ou AINDA_ABERTO quando nao ha decisao visivel (a clinica nao respondeu, a pessoa so sumiu). "
    'Responda SOMENTE um JSON: {{"classe": "NAO_AGENDOU" | "AINDA_ABERTO", "motivo": "<ate 8 palavras>"}}.'
)


@dataclass(frozen=True)
class Veredito:
    classe: str
    motivo: str


class TetoAtingido(Exception):
    """A execucao ja fez o maximo de chamadas; o resto fica para a proxima noite."""


def interpreta(texto: str, classes_validas: Iterable[str]) -> Optional[Veredito]:
    """Extrai {"classe","motivo"} do texto. Qualquer coisa fora do enum e descartada."""
    achado = re.search(r"\{.*?\}", texto or "", flags=re.S)
    if not achado:
        return None
    try:
        dados = json.loads(achado.group(0))
    except ValueError:
        return None
    classe = dados.get("classe")
    if classe not in set(classes_validas):
        return None
    motivo = " ".join(str(dados.get("motivo") or "").split())[:TAMANHO_DO_MOTIVO]
    return Veredito(classe, motivo)


def precisa_de_triagem(lead: dict, mensagens: List[Mensagem]) -> bool:
    if (lead.get("source") or "whatsapp") != "whatsapp":
        return False
    if lead.get("triagem_feita_em"):
        return False
    return sum(1 for m in mensagens if m.de == LEAD) >= TRIAGEM_MINIMO_DE_MENSAGENS_DO_LEAD


def precisa_de_desfecho(lead: dict, decisao: estagio.Decisao, mensagens: List[Mensagem],
                        agora: datetime, dias_parado: int) -> bool:
    if decisao.stage not in (estagio.SUMIU, estagio.INICIADA_SEM_RESPOSTA):
        return False
    if not any(m.de == LEAD for m in mensagens):
        return False
    ultima = mensagens[-1].em if mensagens else None
    if ultima is None or (agora - ultima) <= timedelta(days=dias_parado):
        return False
    tentado = lead.get("desfecho_tentado_em")
    return tentado is None or tentado < ultima


def _transcricao_em_texto(mensagens: List[Mensagem]) -> str:
    rotulo = {LEAD: "CONTATO", "NOS": "CLINICA"}
    return "\n".join(f"[{m.em:%d/%m %H:%M}] {rotulo[m.de]}: {m.texto.strip()}" for m in mensagens)


class Classificador:
    def __init__(self, anthropic=None, max_chamadas: int = MAX_CHAMADAS_PADRAO):
        if anthropic is None:
            from src.services.anthropic_service import AnthropicService
            anthropic = AnthropicService()
        self.anthropic = anthropic
        self.max_chamadas = max_chamadas
        self.chamadas = 0

    def _pergunta(self, system: str, mensagens: List[Mensagem], clinic: dict, classes) -> Optional[Veredito]:
        if self.chamadas >= self.max_chamadas:
            raise TetoAtingido(f"{self.max_chamadas} chamadas nesta execucao")
        self.chamadas += 1
        nome = clinic.get("display_name") or clinic.get("name") or "a clinica"
        try:
            corpo = self.anthropic.create_message(
                system=system.format(nome=nome),
                messages=[{"role": "user", "content": _transcricao_em_texto(mensagens)}],
                model=MODELO_DO_CLASSIFICADOR,
                temperature=0,
                max_tokens=120,
            )
        except Exception as e:
            logger.error(f"[Classificador] chamada falhou: {e}")
            return None
        texto = "".join(b.get("text", "") for b in (corpo or {}).get("content", []) if b.get("type") == "text")
        veredito = interpreta(texto, classes)
        if veredito is None:
            logger.warning(f"[Classificador] resposta descartada: {texto[:200]!r}")
        return veredito

    def triagem(self, mensagens: List[Mensagem], clinic: dict) -> Optional[Veredito]:
        return self._pergunta(_SYSTEM_TRIAGEM, mensagens, clinic, CLASSES_DA_TRIAGEM)

    def desfecho(self, mensagens: List[Mensagem], clinic: dict) -> Optional[Veredito]:
        return self._pergunta(_SYSTEM_DESFECHO, mensagens, clinic, CLASSES_DO_DESFECHO)
```

Confira a assinatura de `AnthropicService.create_message` antes de commitar: ela aceita `system` como string e monta o bloco com cache por conta própria.

- [ ] **Passo 4: rodar e ver passar**

Run: `cd scheduler && python -m unittest tests.unit.test_classificador_de_lead -v`

- [ ] **Passo 5: commit**

```bash
git add scheduler/src/services/classificador_de_lead.py scheduler/tests/unit/test_classificador_de_lead.py
git commit -m "feat(crm): classificador de triagem e desfecho com teto de chamadas"
```

---

## Tarefa 5: Escrita do estágio e do log de eventos

**Arquivos:** criar `scheduler/src/services/estagio_repo.py`; testar em `scheduler/tests/unit/test_estagio_repo.py`.

**Consome:** `PostgresService.execute_write(sql, params) -> int`, `execute_query`. `estagio_do_lead.Decisao`.

**Produz:**

```python
def grava_estagio(db, lead: dict, decisao: Decisao, usuario_id: Optional[str] = None,
                  ultima_em: Optional[datetime] = None, ultima_de: Optional[str] = None) -> bool
    # True se gravou (stage ou reason mudou). Sempre atualiza ultima_mensagem_* quando informados.
def registra_tentativa(db, lead: dict, motivo: str) -> None   # evento para=stage atual
def marca_triagem(db, lead_id: str) -> None
def marca_desfecho_tentado(db, lead_id: str) -> None
```

- [ ] **Passo 1: testes com banco falso**

```python
# -*- coding: utf-8 -*-
"""Escrita do estagio: so grava quando muda, e toda mudanca vira evento."""
import unittest
from datetime import datetime, timezone

from src.services import estagio_do_lead as e
from src.services import estagio_repo as repo

AGORA = datetime(2026, 10, 24, tzinfo=timezone.utc)


class BancoFalso:
    def __init__(self):
        self.escritas = []

    def execute_write(self, sql, params=None):
        self.escritas.append((" ".join(sql.split()), params))
        return 1


def lead(**kw):
    base = {"id": "11111111-1111-1111-1111-111111111111", "clinic_id": "c1",
            "stage": None, "stage_source": None, "stage_reason": None}
    base.update(kw)
    return base


class TestGravaEstagio(unittest.TestCase):
    def test_mudanca_grava_lead_e_evento(self):
        db = BancoFalso()
        ok = repo.grava_estagio(db, lead(), e.Decisao(e.SEM_CONVERSA, e.REGRA), ultima_em=None, ultima_de=None)
        self.assertTrue(ok)
        sqls = [s for s, _ in db.escritas]
        self.assertTrue(any("UPDATE scheduler.leads" in s for s in sqls))
        self.assertTrue(any("INSERT INTO scheduler.lead_stage_events" in s for s in sqls))

    def test_igual_nao_grava_evento_mas_atualiza_ultima_mensagem(self):
        db = BancoFalso()
        ok = repo.grava_estagio(db, lead(stage=e.SUMIU, stage_source=e.REGRA),
                                e.Decisao(e.SUMIU, e.REGRA), ultima_em=AGORA, ultima_de="NOS")
        self.assertFalse(ok)
        sqls = [s for s, _ in db.escritas]
        self.assertFalse(any("lead_stage_events" in s for s in sqls))
        self.assertTrue(any("ultima_mensagem_em" in s for s in sqls))

    def test_manual_preserva_motivo_existente(self):
        db = BancoFalso()
        l = lead(stage=e.NAO_AGENDOU, stage_source=e.MANUAL, stage_reason="achou caro")
        ok = repo.grava_estagio(db, l, e.Decisao(e.NAO_AGENDOU, e.MANUAL))
        self.assertFalse(ok)

    def test_motivo_novo_com_mesmo_estagio_grava(self):
        db = BancoFalso()
        l = lead(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_reason="vai pensar")
        ok = repo.grava_estagio(db, l, e.Decisao(e.NAO_AGENDOU, e.MODELO, "achou caro"))
        self.assertTrue(ok)

    def test_manual_leva_usuario_no_evento(self):
        db = BancoFalso()
        repo.grava_estagio(db, lead(), e.Decisao(e.NAO_E_LEAD, e.MANUAL, "fornecedor"), usuario_id="u1")
        evento = [p for s, p in db.escritas if "lead_stage_events" in s][0]
        self.assertIn("u1", evento)


class TestMarcas(unittest.TestCase):
    def test_tentativa_gera_evento_sem_mudar_estagio(self):
        db = BancoFalso()
        repo.registra_tentativa(db, lead(stage=e.SUMIU), "ainda_aberto")
        s, p = db.escritas[0]
        self.assertIn("lead_stage_events", s)
        self.assertIn("ainda_aberto", p)

    def test_marcas_de_tempo(self):
        db = BancoFalso()
        repo.marca_triagem(db, "id1"); repo.marca_desfecho_tentado(db, "id1")
        self.assertIn("triagem_feita_em", db.escritas[0][0])
        self.assertIn("desfecho_tentado_em", db.escritas[1][0])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: rodar e ver falhar**, depois **Passo 3: implementar**

```python
# -*- coding: utf-8 -*-
"""Grava o estagio no lead e a transicao no log. Um lugar so para as duas
escritas, porque esquecer o evento e silencioso."""
import logging
from datetime import datetime
from typing import Optional

from src.services.estagio_do_lead import Decisao, MANUAL

logger = logging.getLogger(__name__)


def _evento(db, lead: dict, para: str, fonte: str, motivo: Optional[str], usuario_id: Optional[str]):
    db.execute_write(
        """
        INSERT INTO scheduler.lead_stage_events (clinic_id, lead_id, de, para, fonte, motivo, usuario_id)
        VALUES (%s, %s::uuid, %s, %s, %s, %s, %s::uuid)
        """,
        (lead["clinic_id"], str(lead["id"]), lead.get("stage"), para, fonte, motivo, usuario_id),
    )


def grava_estagio(db, lead: dict, decisao: Decisao, usuario_id: Optional[str] = None,
                  ultima_em: Optional[datetime] = None, ultima_de: Optional[str] = None) -> bool:
    # Decisao MANUAL vinda da regra (mantem o que esta) nao traz motivo: o que
    # ja esta gravado fica. Um motivo novo so chega por correcao manual (PATCH).
    motivo = decisao.reason if decisao.reason is not None else (
        lead.get("stage_reason") if decisao.source == MANUAL or decisao.stage == lead.get("stage") else None)
    mudou = decisao.stage != lead.get("stage") or (motivo or None) != (lead.get("stage_reason") or None)

    if mudou:
        db.execute_write(
            """
            UPDATE scheduler.leads
               SET stage = %s, stage_reason = %s, stage_source = %s, stage_updated_at = NOW(),
                   ultima_mensagem_em = %s, ultima_mensagem_de = %s, updated_at = NOW()
             WHERE id = %s::uuid
            """,
            (decisao.stage, motivo, decisao.source, ultima_em, ultima_de, str(lead["id"])),
        )
        _evento(db, lead, decisao.stage, decisao.source, motivo, usuario_id)
        return True

    db.execute_write(
        "UPDATE scheduler.leads SET ultima_mensagem_em = %s, ultima_mensagem_de = %s WHERE id = %s::uuid",
        (ultima_em, ultima_de, str(lead["id"])),
    )
    return False


def registra_tentativa(db, lead: dict, motivo: str) -> None:
    """Desfecho que voltou AINDA_ABERTO: nada muda no lead, mas fica o rastro."""
    _evento(db, lead, lead.get("stage") or "", "MODELO", motivo, None)


def marca_triagem(db, lead_id: str) -> None:
    db.execute_write("UPDATE scheduler.leads SET triagem_feita_em = NOW() WHERE id = %s::uuid", (lead_id,))


def marca_desfecho_tentado(db, lead_id: str) -> None:
    db.execute_write("UPDATE scheduler.leads SET desfecho_tentado_em = NOW() WHERE id = %s::uuid", (lead_id,))
```

- [ ] **Passo 4: rodar e ver passar**; **Passo 5: commit** `feat(crm): gravacao de estagio e log de transicoes`.

---

## Tarefa 6: Lambda `ClassificaLeads`

**Arquivos:** criar `scheduler/src/functions/lead/classifica_estagios.py`; modificar `scheduler/sls/functions/lead/interface.yml`; testar em `scheduler/tests/unit/test_classifica_estagios.py`.

**Consome:** Tarefas 2 a 5; `status_da_conversa.conversas_da_clinica(db, clinic_id)` (espelho por variante); `variantes_do_numero`.

**Produz:** `handler(event, context)` com `event = {"clinicId"?: str, "dryRun"?: bool}` devolvendo `{"traceId", "clinics", "por_clinica": {clinic_id: {"leads", "mudaram", "por_estagio", "chamadas_modelo", "descartes", "erro"}}}`. Função pura testável: `processa_clinica(db, tabela_eventos, clinic, classificador, agora, dry_run) -> dict`.

- [ ] **Passo 1: testes**

```python
# -*- coding: utf-8 -*-
"""O job: regras + modelo por lead, grava so quando muda, dryRun nao escreve,
uma clinica com erro nao bloqueia a proxima."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "t")

from src.functions.lead import classifica_estagios as job
from src.services import estagio_do_lead as e

AGORA = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
CLINIC = {"clinic_id": "c1", "name": "Essencia", "crm_dias_parado": 7, "active": True}


class BancoFalso:
    def __init__(self, leads, agendamentos=(), chats=()):
        self.leads, self.agendamentos, self.chats = leads, list(agendamentos), list(chats)
        self.escritas = []

    def execute_query(self, sql, params=None):
        s = " ".join(sql.split())
        if "FROM scheduler.leads" in s:
            return self.leads
        if "FROM scheduler.appointments" in s:
            return self.agendamentos
        if "FROM scheduler.whatsapp_chats" in s:
            return self.chats
        return []

    def execute_write(self, sql, params=None):
        self.escritas.append((" ".join(sql.split()), params))
        return 1


def lead(**kw):
    base = {"id": "11111111-1111-1111-1111-111111111111", "clinic_id": "c1", "phone": "5511999990000",
            "source": "landing-page", "stage": None, "stage_source": None, "stage_reason": None,
            "stage_updated_at": None, "first_contact_at": None, "triagem_feita_em": None,
            "desfecho_tentado_em": None}
    base.update(kw)
    return base


class ClassificadorFalso:
    chamadas = 0
    def triagem(self, *_): return None
    def desfecho(self, *_): return None


class TestProcessaClinica(unittest.TestCase):
    def test_lead_sem_nada_vira_sem_conversa_e_grava(self):
        db = BancoFalso([lead()])
        with mock.patch.object(job, "ultimas_mensagens", return_value=[]):
            r = job.processa_clinica(db, None, CLINIC, ClassificadorFalso(), AGORA, dry_run=False)
        self.assertEqual(r["por_estagio"], {e.SEM_CONVERSA: 1})
        self.assertEqual(r["mudaram"], 1)
        self.assertTrue(any("UPDATE scheduler.leads" in s for s, _ in db.escritas))

    def test_dry_run_nao_escreve(self):
        db = BancoFalso([lead()])
        with mock.patch.object(job, "ultimas_mensagens", return_value=[]):
            r = job.processa_clinica(db, None, CLINIC, ClassificadorFalso(), AGORA, dry_run=True)
        self.assertEqual(r["por_estagio"], {e.SEM_CONVERSA: 1})
        self.assertEqual(db.escritas, [])

    def test_agendamento_do_paciente_com_mesmo_telefone_conta(self):
        db = BancoFalso([lead()], agendamentos=[{"phone": "5511999990000", "status": "CONFIRMED", "appointment_date": AGORA.date() + timedelta(days=3)}])
        with mock.patch.object(job, "ultimas_mensagens", return_value=[]):
            r = job.processa_clinica(db, None, CLINIC, ClassificadorFalso(), AGORA, dry_run=True)
        self.assertEqual(r["por_estagio"], {e.AGENDOU: 1})

    def test_variante_do_telefone_casa_no_espelho(self):
        db = BancoFalso([lead(phone="5547997053940")], chats=[{"phone": "554797053940", "name": "x", "last_message_at": AGORA - timedelta(days=2), "unread_count": 1}])
        with mock.patch.object(job, "ultimas_mensagens", return_value=[]):
            r = job.processa_clinica(db, None, CLINIC, ClassificadorFalso(), AGORA, dry_run=True)
        self.assertEqual(r["por_estagio"], {e.AGUARDANDO_NOS: 1})

    def test_triagem_nao_e_lead_grava_com_fonte_modelo(self):
        from src.services.classificador_de_lead import Veredito
        from src.services.transcricao import Mensagem
        ms = [Mensagem("LEAD", AGORA - timedelta(days=1, hours=h), "venda de insumos") for h in (3, 2, 1)]
        class Cl(ClassificadorFalso):
            def triagem(self, *_): return Veredito("NAO_E_LEAD", "fornecedor")
        db = BancoFalso([lead(source="whatsapp")])
        with mock.patch.object(job, "ultimas_mensagens", return_value=ms):
            r = job.processa_clinica(db, None, CLINIC, Cl(), AGORA, dry_run=False)
        self.assertEqual(r["por_estagio"], {e.NAO_E_LEAD: 1})
        upd = [p for s, p in db.escritas if "UPDATE scheduler.leads SET stage" in s][0]
        self.assertEqual(upd[2], e.MODELO)

    def test_desfecho_ainda_aberto_registra_tentativa_e_nao_muda(self):
        from src.services.classificador_de_lead import Veredito
        from src.services.transcricao import Mensagem
        ms = [Mensagem("LEAD", AGORA - timedelta(days=12), "oi"), Mensagem("NOS", AGORA - timedelta(days=11), "ola")]
        class Cl(ClassificadorFalso):
            def desfecho(self, *_): return Veredito("AINDA_ABERTO", "sem decisao")
        db = BancoFalso([lead()])
        with mock.patch.object(job, "ultimas_mensagens", return_value=ms):
            r = job.processa_clinica(db, None, CLINIC, Cl(), AGORA, dry_run=False)
        self.assertEqual(r["por_estagio"], {e.SUMIU: 1})
        self.assertTrue(any("lead_stage_events" in s and "ainda_aberto" in (p or ()) for s, p in db.escritas))
        self.assertTrue(any("desfecho_tentado_em" in s for s, _ in db.escritas))


class TestHandler(unittest.TestCase):
    def test_clinica_com_erro_nao_bloqueia_a_proxima(self):
        clinicas = [dict(CLINIC, clinic_id="c1"), dict(CLINIC, clinic_id="c2")]
        resultados = iter([RuntimeError("boom"), {"leads": 0, "mudaram": 0, "por_estagio": {}, "chamadas_modelo": 0, "descartes": 0}])
        def processa(*a, **k):
            r = next(resultados)
            if isinstance(r, Exception): raise r
            return r
        with mock.patch.object(job, "_clinicas", return_value=clinicas), \
             mock.patch.object(job, "processa_clinica", side_effect=processa), \
             mock.patch.object(job, "PostgresService"), mock.patch.object(job, "_tabela_de_eventos"), \
             mock.patch.object(job, "Classificador"):
            r = job.handler({"dryRun": True}, None)
        self.assertEqual(r["clinics"], 2)
        self.assertIn("erro", r["por_clinica"]["c1"])
        self.assertNotIn("erro", r["por_clinica"]["c2"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: rodar e ver falhar**; **Passo 3: implementar**

```python
# -*- coding: utf-8 -*-
"""Recalcula o estagio de todos os leads (PRD 057). Diario, 7h BRT.

Para cada lead: le a transcricao no MessageEvents, cruza com agenda e espelho
do z-api, aplica `estagio_do_lead.decide`, e so entao pergunta ao modelo o que a
regra nao sabe (triagem de WhatsApp novo; desfecho de quem parou). Grava so o
que mudou. `{"dryRun": true}` calcula e devolve a distribuicao sem escrever.
"""
import logging
import os
import uuid
from collections import Counter
from datetime import datetime, timezone

from src.services import estagio_do_lead as estagio
from src.services import estagio_repo as repo
from src.services.classificador_de_lead import Classificador, TetoAtingido, precisa_de_desfecho, precisa_de_triagem
from src.services.db.postgres import PostgresService
from src.services.status_da_conversa import conversas_da_clinica
from src.services.transcricao import resumo, ultimas_mensagens
from src.utils.phone import variantes_do_numero

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_tabela = None


def _tabela_de_eventos():
    global _tabela
    if _tabela is None:
        import boto3
        _tabela = boto3.resource("dynamodb").Table(os.environ["MESSAGE_EVENTS_TABLE"])
    return _tabela


def _clinicas(db, clinic_id=None):
    if clinic_id:
        return db.execute_query("SELECT * FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,))
    return db.execute_query("SELECT * FROM scheduler.clinics WHERE active = TRUE")


def _agendamentos_por_variante(db, clinic_id, hoje):
    """Agendamentos da clinica que NAO sao remarcacao (PRD 054), do mais recente
    para o mais antigo, indexados por variante do telefone do paciente."""
    linhas = db.execute_query(
        """
        SELECT p.phone, a.status, a.appointment_date, a.start_time
          FROM scheduler.appointments a
          JOIN scheduler.patients p ON p.id = a.patient_id
         WHERE a.clinic_id = %s
           AND a.rescheduled_to_id IS NULL
           AND p.deleted_at IS NULL
         ORDER BY a.appointment_date DESC, a.start_time DESC
        """,
        (clinic_id,),
    )
    por_tel = {}
    for l in linhas:
        for v in variantes_do_numero(l["phone"] or ""):
            por_tel.setdefault(v, []).append(l)
    return por_tel


def _sinais(lead, mensagens, chat, agendamentos, hoje):
    r = resumo(mensagens)
    # ja vem ordenado do mais recente para o mais antigo
    mais_recente = max(agendamentos, key=lambda a: (a["appointment_date"], a.get("start_time") or ""), default=None)
    ultimo = mais_recente["status"] if mais_recente else None
    return estagio.Sinais(
        stage=lead.get("stage"), stage_source=lead.get("stage_source"), stage_updated_at=lead.get("stage_updated_at"),
        first_contact_at=lead.get("first_contact_at"),
        ultima_mensagem_de=r["ultima_de"], ultima_mensagem_em=r["ultima_em"], lead_ja_falou=r["lead_ja_falou"],
        tem_transcricao=bool(mensagens),
        chat_espelho_em=(chat or {}).get("last_message_at"), chat_espelho_nao_lidas=int((chat or {}).get("unread_count") or 0),
        ultimo_agendamento=ultimo,
    )


def processa_clinica(db, tabela_eventos, clinic, classificador, agora, dry_run):
    clinic_id = clinic["clinic_id"]
    dias = int(clinic.get("crm_dias_parado") or 7)
    hoje = agora.date()
    leads = db.execute_query("SELECT * FROM scheduler.leads WHERE clinic_id = %s", (clinic_id,))
    chats = conversas_da_clinica(db, clinic_id)
    agenda = _agendamentos_por_variante(db, clinic_id, hoje)

    por_estagio, mudaram, descartes = Counter(), 0, 0
    for lead in leads:
        telefone = lead.get("phone") or ""
        mensagens = ultimas_mensagens(tabela_eventos, clinic_id, telefone)
        chat = next((chats.get(v) for v in variantes_do_numero(telefone) if chats.get(v)), None)
        ags = [a for v in variantes_do_numero(telefone) for a in agenda.get(v, [])]
        decisao = estagio.decide(_sinais(lead, mensagens, chat, ags, hoje), agora, dias)
        r = resumo(mensagens)

        try:
            if decisao.stage not in estagio.ESTAGIOS_DA_AGENDA and decisao.source != estagio.MANUAL:
                if precisa_de_triagem(lead, mensagens):
                    v = classificador.triagem(mensagens, clinic)
                    if v is None:
                        descartes += 1
                    else:
                        if not dry_run:
                            repo.marca_triagem(db, str(lead["id"]))
                        if v.classe == "NAO_E_LEAD":
                            decisao = estagio.Decisao(estagio.NAO_E_LEAD, estagio.MODELO, v.motivo)
                if decisao.stage != estagio.NAO_E_LEAD and precisa_de_desfecho(lead, decisao, mensagens, agora, dias):
                    v = classificador.desfecho(mensagens, clinic)
                    if v is None:
                        descartes += 1
                    else:
                        if not dry_run:
                            repo.marca_desfecho_tentado(db, str(lead["id"]))
                        if v.classe == "NAO_AGENDOU":
                            decisao = estagio.Decisao(estagio.NAO_AGENDOU, estagio.MODELO, v.motivo)
                        elif not dry_run:
                            repo.registra_tentativa(db, dict(lead, stage=decisao.stage), "ainda_aberto")
        except TetoAtingido as t:
            logger.warning(f"[ClassificaLeads] {clinic_id}: teto do modelo atingido ({t}); o resto fica para amanha")
            classificador = _SemModelo()

        por_estagio[decisao.stage] += 1
        if not dry_run and repo.grava_estagio(db, lead, decisao, ultima_em=r["ultima_em"], ultima_de=r["ultima_de"]):
            mudaram += 1
        elif dry_run and (decisao.stage != lead.get("stage") or (decisao.reason or None) != (lead.get("stage_reason") or None)):
            mudaram += 1

    return {"leads": len(leads), "mudaram": mudaram, "por_estagio": dict(por_estagio),
            "chamadas_modelo": getattr(classificador, "chamadas", 0), "descartes": descartes}


class _SemModelo:
    """Depois do teto, as regras continuam e o modelo cala."""
    chamadas = 0
    def triagem(self, *_): return None
    def desfecho(self, *_): return None


def handler(event, context):
    trace_id = str(uuid.uuid4())
    event = event or {}
    dry_run = bool(event.get("dryRun"))
    agora = datetime.now(timezone.utc)
    logger.info(f"[traceId: {trace_id}] ClassificaLeads inicio" + (" (dryRun)" if dry_run else ""))

    db = PostgresService()
    tabela = _tabela_de_eventos()
    max_chamadas = int(os.environ.get("CRM_MAX_CHAMADAS_MODELO", "200"))
    saida = {"traceId": trace_id, "dryRun": dry_run, "clinics": 0, "por_clinica": {}}

    for clinic in _clinicas(db, event.get("clinicId")):
        cid = clinic["clinic_id"]
        saida["clinics"] += 1
        try:
            saida["por_clinica"][cid] = processa_clinica(db, tabela, clinic, Classificador(max_chamadas=max_chamadas), agora, dry_run)
            logger.info(f"[traceId: {trace_id}] {cid}: {saida['por_clinica'][cid]}")
        except Exception as e:
            logger.error(f"[traceId: {trace_id}] {cid} falhou: {e}")
            saida["por_clinica"][cid] = {"erro": str(e)}
    return saida
```

- [ ] **Passo 4: interface serverless**, acrescentar ao fim de `scheduler/sls/functions/lead/interface.yml`:

```yaml
ClassificaLeads:
  handler: src.functions.lead.classifica_estagios.handler
  memorySize: 1024
  timeout: 300
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ClassificaLeads-lambdaRole
  iamRoleStatements:
    # Transcricao de cada lead: uma Query por variante do telefone.
    - Effect: Allow
      Action:
        - dynamodb:Query
      Resource:
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-message-events"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    # 7h BRT (10h UTC): uma hora depois do SyncWhatsAppChats, para o espelho
    # do z-api estar do dia. Diario porque a fila e semanal; mais que isso so
    # gastaria chamadas de modelo sem ninguem olhar.
    - schedule:
        rate: cron(0 10 * * ? *)
        enabled: true
```

- [ ] **Passo 5: rodar os testes**, `cd scheduler && python -m unittest tests.unit.test_classifica_estagios -v`, e **commit** `feat(crm): Lambda ClassificaLeads com dryRun`.

---

## Tarefa 7: Permissões e listagem com filtros de estágio

**Arquivos:** modificar `scheduler/src/utils/acesso.py`, `scheduler/src/services/lead_service.py`, `scheduler/src/functions/lead/list.py`; testar em `scheduler/tests/unit/test_lead_service_filtros.py`.

**Produz:**

- `PERMISSOES_DO_STAFF` ganha `"crm.ler"` e `"crm.escrever"`.
- `LeadService._filtros(..., stages: Optional[List[str]] = None, sources: Optional[List[str]] = None)`; `list_leads` e `contar_leads` aceitam `stages`/`sources`; novo `contar_por_estagio(clinic_id, start_date, end_date, sources, exclude_sources) -> Dict[str, int]`; `list_leads` aceita `ordenar_por: str = "created_at"` com valor `"dias_parado"` (ORDER BY `ultima_mensagem_em ASC NULLS LAST`).
- `list.py`: lê `stage`, `source`, `orderBy`; usa `require_acesso(event, "crm.ler")` no lugar de `require_api_key` (a chave mestra continua passando como ADMIN); devolve `totals.por_estagio`.

- [ ] **Passo 1: testes do `_filtros`**

```python
# -*- coding: utf-8 -*-
"""Os filtros de estagio e origem entram no MESMO where da listagem e da contagem."""
import unittest
from unittest import mock

from src.services.lead_service import LeadService


class TestFiltros(unittest.TestCase):
    def setUp(self):
        self.svc = LeadService(mock.MagicMock())

    def test_stages_multiplos(self):
        where, params = self.svc._filtros("c1", stages=["SUMIU", "AGUARDANDO_NOS"])
        self.assertIn("stage IN (%s, %s)", where)
        self.assertEqual(params[-2:], ["SUMIU", "AGUARDANDO_NOS"])

    def test_sources_multiplas(self):
        where, params = self.svc._filtros("c1", sources=["landing-page", "whatsapp"])
        self.assertIn("COALESCE(source, '') IN (%s, %s)", where)

    def test_stage_desconhecido_e_ignorado(self):
        where, _ = self.svc._filtros("c1", stages=["INVENTADO"])
        self.assertNotIn("stage IN", where)

    def test_contar_por_estagio_nao_filtra_por_estagio(self):
        db = mock.MagicMock()
        db.execute_query.return_value = [{"stage": "SUMIU", "n": 3}, {"stage": None, "n": 1}]
        r = LeadService(db).contar_por_estagio("c1", sources=["whatsapp"])
        sql = db.execute_query.call_args[0][0]
        self.assertIn("GROUP BY stage", sql)
        self.assertNotIn("stage IN", sql)
        self.assertEqual(r, {"SUMIU": 3, "SEM_ESTAGIO": 1})

    def test_ordenar_por_dias_parado(self):
        db = mock.MagicMock(); db.execute_query.return_value = []
        LeadService(db).list_leads("c1", ordenar_por="dias_parado")
        self.assertIn("ORDER BY ultima_mensagem_em ASC NULLS LAST", db.execute_query.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: implementar em `lead_service.py`**

Em `_filtros`, acrescentar parâmetros e condições:

```python
        if sources:
            marcadores = ", ".join(["%s"] * len(sources))
            conditions.append(f"COALESCE(source, '') IN ({marcadores})")
            params.extend(sources)
        validos = [s for s in (stages or []) if s in ESTAGIOS]
        if validos:
            marcadores = ", ".join(["%s"] * len(validos))
            conditions.append(f"stage IN ({marcadores})")
            params.extend(validos)
```

com `from src.services.estagio_do_lead import ESTAGIOS` no topo. `list_leads` e `contar_leads` repassam `stages`/`sources`. Novo método:

```python
    def contar_por_estagio(self, clinic_id, start_date=None, end_date=None,
                           sources=None, exclude_sources=None) -> Dict[str, int]:
        """Contagem por estagio do conjunto filtrado por origem e periodo. Sem o
        filtro de estagio de proposito: e o numero de cada chip, e os chips
        precisam mostrar o todo enquanto um deles esta selecionado."""
        where, params = self._filtros(clinic_id, start_date, end_date, None, exclude_sources, None, sources)
        linhas = self.db.execute_query(
            f"SELECT stage, COUNT(*) AS n FROM scheduler.leads WHERE {where} GROUP BY stage",
            tuple(params))
        return {(l["stage"] or "SEM_ESTAGIO"): int(l["n"]) for l in linhas}
```

Em `list_leads`, parâmetro `ordenar_por="created_at"`:

```python
        ordem = ("ORDER BY ultima_mensagem_em ASC NULLS LAST, created_at DESC, id DESC"
                 if ordenar_por == "dias_parado" else "ORDER BY created_at DESC, id DESC")
```

- [ ] **Passo 3: `list.py`**

Trocar `require_api_key` por `from src.utils.acesso import require_acesso` e `identidade, error_response = require_acesso(event, "crm.ler")`. Ler params:

```python
        stages = [s.strip() for s in (extract_query_param(event, "stage") or "").split(",") if s.strip()]
        sources = [s.strip() for s in (extract_query_param(event, "source") or "").split(",") if s.strip()]
        ordenar_por = extract_query_param(event, "orderBy") or "created_at"
```

Passar a `list_leads(..., stages=stages, sources=sources, ordenar_por=ordenar_por)` e a `contar_leads(..., sources=sources)`. Dentro do `try` dos totais: `totais["por_estagio"] = lead_service.contar_por_estagio(clinic_id, start_date, end_date, sources, exclude_sources)`. Acrescentar em cada lead serializado `dias_parado`:

```python
        agora = datetime.now(timezone.utc)
        for l in leads:
            em = l.get("ultima_mensagem_em")
            l["dias_parado"] = (agora - em).days if em else None
```

- [ ] **Passo 4: `acesso.py`**, adicionar a `PERMISSOES_DO_STAFF`: `"crm.ler", "crm.escrever",` com comentário "fila de leads: a recepcao trabalha nela toda semana (PRD 057)".

- [ ] **Passo 5: rodar** `python -m unittest tests.unit.test_lead_service_filtros tests.unit.test_acesso_por_papel -v` (o segundo já existe; conferir que não quebrou) e **commit** `feat(crm): filtros de estagio e origem na listagem de leads`.

---

## Tarefa 8: `PATCH /clinics/{clinicId}/leads/{leadId}/stage`

**Arquivos:** criar `scheduler/src/functions/lead/atualiza_estagio.py`; modificar `scheduler/sls/functions/lead/interface.yml`; testar em `scheduler/tests/unit/test_atualiza_estagio.py`.

- [ ] **Passo 1: testes**

```python
# -*- coding: utf-8 -*-
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.lead import atualiza_estagio as h
from src.utils.acesso import Identidade, STAFF


def evento(body, lead_id="11111111-1111-1111-1111-111111111111"):
    return {"pathParameters": {"clinicId": "c1", "leadId": lead_id}, "headers": {"x-api-key": "k"},
            "body": json.dumps(body)}


class TestPatch(unittest.TestCase):
    def setUp(self):
        self.ident = Identidade(papel=STAFF, user_id="u1", clinic_id="c1")
        self.db = mock.MagicMock()
        self.db.execute_query.return_value = [{"id": "11111111-1111-1111-1111-111111111111", "clinic_id": "c1",
                                               "stage": "SUMIU", "stage_source": "REGRA", "stage_reason": None}]

    def chama(self, body):
        with mock.patch.object(h, "require_acesso", return_value=(self.ident, None)), \
             mock.patch.object(h, "PostgresService", return_value=self.db):
            return h.handler(evento(body), None)

    def test_grava_manual_com_usuario(self):
        r = self.chama({"stage": "NAO_AGENDOU", "reason": "achou caro"})
        self.assertEqual(r["statusCode"], 200)
        escritas = [c.args for c in self.db.execute_write.call_args_list]
        self.assertTrue(any("lead_stage_events" in a[0] and "u1" in a[1] for a in escritas))
        corpo = json.loads(r["body"])
        self.assertEqual(corpo["lead"]["stage_source"], "MANUAL")

    def test_recusa_fato_da_agenda(self):
        r = self.chama({"stage": "AGENDOU"})
        self.assertEqual(r["statusCode"], 400)
        self.assertIn("agenda", json.loads(r["body"])["message"])

    def test_recusa_estagio_desconhecido(self):
        self.assertEqual(self.chama({"stage": "X"})["statusCode"], 400)

    def test_404_sem_lead(self):
        self.db.execute_query.return_value = []
        self.assertEqual(self.chama({"stage": "SUMIU"})["statusCode"], 404)

    def test_403_sem_permissao(self):
        with mock.patch.object(h, "require_acesso", return_value=(None, {"statusCode": 403, "body": "{}"})):
            self.assertEqual(h.handler(evento({"stage": "SUMIU"}), None)["statusCode"], 403)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: implementar**

```python
# -*- coding: utf-8 -*-
"""A atendente corrige o estagio que o modelo (ou a regra) errou.

PATCH /clinics/{clinicId}/leads/{leadId}/stage  {"stage": "...", "reason": "..."}

Grava MANUAL: a regra noturna nao sobrescreve mais, so um fato da agenda
(agendou) ou outra correcao. Fato da agenda nao se edita aqui - vem da agenda.
"""
import logging

from src.services import estagio_repo as repo
from src.services.db.postgres import PostgresService
from src.services.estagio_do_lead import Decisao, ESTAGIOS, ESTAGIOS_DA_AGENDA, ESTAGIOS_EDITAVEIS, MANUAL
from src.utils.acesso import require_acesso
from src.utils.http import extract_path_param, http_response, parse_body

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    try:
        identidade, erro = require_acesso(event, "crm.escrever")
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        lead_id = extract_path_param(event, "leadId")
        body = parse_body(event) or {}
        stage = body.get("stage")
        reason = (body.get("reason") or "").strip()[:120] or None

        if stage in ESTAGIOS_DA_AGENDA:
            return http_response(400, {"status": "ERROR", "message": "Este estagio vem da agenda e nao pode ser editado."})
        if stage not in ESTAGIOS_EDITAVEIS:
            return http_response(400, {"status": "ERROR", "message": f"stage invalido; aceitos: {sorted(ESTAGIOS_EDITAVEIS)}"})

        db = PostgresService()
        leads = db.execute_query(
            "SELECT * FROM scheduler.leads WHERE id = %s::uuid AND clinic_id = %s", (lead_id, clinic_id))
        if not leads:
            return http_response(404, {"status": "ERROR", "message": "Lead nao encontrado"})
        lead = leads[0]

        repo.grava_estagio(db, lead, Decisao(stage, MANUAL, reason), usuario_id=identidade.user_id,
                           ultima_em=lead.get("ultima_mensagem_em"), ultima_de=lead.get("ultima_mensagem_de"))
        atualizado = dict(lead, stage=stage, stage_source=MANUAL, stage_reason=reason)
        logger.info(f"[AtualizaEstagio] {lead_id} -> {stage} por {identidade.user_id or 'admin'}")
        return http_response(200, {"status": "SUCCESS", "lead": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in atualizado.items()}})
    except Exception as e:
        logger.error(f"Erro ao atualizar estagio: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
```

- [ ] **Passo 3: interface**

```yaml
AtualizaEstagioDoLead:
  handler: src.functions.lead.atualiza_estagio.handler
  memorySize: 512
  timeout: 30
  events:
    - http:
        path: clinics/{clinicId}/leads/{leadId}/stage
        method: patch
        cors: true
```

- [ ] **Passo 4: rodar** e **commit** `feat(crm): PATCH de correcao manual do estagio`.

---

## Tarefa 9: Tipos, service e hooks no frontend

**Arquivos:** modificar `frontend/src/types/index.ts`, `frontend/src/services/leads.service.ts`, `frontend/src/hooks/useLeads.ts`; criar `frontend/src/pages/crm/estagios.ts`; testar em `frontend/src/services/leads.service.test.ts` (existente) e `frontend/src/pages/crm/estagios.test.ts`.

- [ ] **Passo 1: tipos** (em `types/index.ts`, antes de `export interface Lead`):

```ts
export type LeadStage =
  | 'SEM_CONVERSA' | 'INICIADA_SEM_RESPOSTA' | 'EM_ANDAMENTO' | 'AGUARDANDO_NOS' | 'SUMIU'
  | 'NAO_AGENDOU' | 'CANCELOU' | 'FALTOU' | 'AGENDOU' | 'NAO_E_LEAD'
export type StageSource = 'REGRA' | 'MODELO' | 'MANUAL' | 'HISTORICO'
```

E em `Lead`, acrescentar:

```ts
  /** Retrato noturno do job ClassificaLeads (PRD 057). null = ainda nao processado. */
  stage: LeadStage | null
  stage_reason: string | null
  stage_source: StageSource | null
  stage_updated_at: string | null
  ultima_mensagem_em: string | null
  ultima_mensagem_de: 'LEAD' | 'NOS' | null
  /** Dias desde a ultima mensagem, calculado no servidor na listagem. */
  dias_parado: number | null
```

- [ ] **Passo 2: service**

```ts
export interface LeadTotals {
  total: number
  convertidos: number
  nao_convertidos: number
  /** Contagem por estagio do conjunto filtrado por origem e periodo (nao por estagio). */
  por_estagio?: Record<string, number>
}

export interface LeadListParams {
  startDate?: string
  endDate?: string
  booked?: boolean
  excludeSource?: string
  /** Estagios separados por virgula. */
  stage?: string
  /** Origens separadas por virgula. */
  source?: string
  orderBy?: 'created_at' | 'dias_parado'
  limit?: number
  offset?: number
}
```

e no objeto `leadsService`:

```ts
  patchStage(clinicId: string, leadId: string, payload: { stage: LeadStage; reason?: string }) {
    return api
      .patch<{ status: string; lead: Lead }>(`/clinics/${clinicId}/leads/${leadId}/stage`, payload)
      .then((r) => r.data)
  },
```

Teste a acrescentar em `leads.service.test.ts`:

```ts
  it('patchStage bate na rota certa com o payload', async () => {
    mockedApi.patch.mockResolvedValue({ data: { status: 'SUCCESS', lead: {} } })
    await leadsService.patchStage(CLINIC_ID, 'lead-1', { stage: 'NAO_AGENDOU', reason: 'achou caro' })
    expect(mockedApi.patch).toHaveBeenCalledWith(`/clinics/${CLINIC_ID}/leads/lead-1/stage`, { stage: 'NAO_AGENDOU', reason: 'achou caro' })
  })
```

(Seguir o mesmo mock de `api` que o arquivo já usa.)

- [ ] **Passo 3: hook**

```ts
export function useCorrigeEstagio() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ leadId, stage, reason }: { leadId: string; stage: LeadStage; reason?: string }) =>
      leadsService.patchStage(clinicId!, leadId, { stage, reason }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: leadKeys.all }),
  })
}
```

- [ ] **Passo 4: `pages/crm/estagios.ts`**, a fonte única de rótulos e ordem na tela:

```ts
import type { LeadStage, StageSource } from '@/types'

export interface EstagioInfo {
  label: string
  descricao: string
  variant: 'success' | 'warning' | 'danger' | 'neutral' | 'info'
}

export const ESTAGIOS: Record<LeadStage, EstagioInfo> = {
  AGUARDANDO_NOS: { label: 'Aguardando nós', descricao: 'A última mensagem é do lead.', variant: 'danger' },
  SUMIU: { label: 'Sumiu', descricao: 'Respondeu, nós respondemos, e parou.', variant: 'warning' },
  INICIADA_SEM_RESPOSTA: { label: 'Sem resposta', descricao: 'Só nós falamos.', variant: 'warning' },
  SEM_CONVERSA: { label: 'Sem conversa', descricao: 'Ninguém falou ainda.', variant: 'neutral' },
  EM_ANDAMENTO: { label: 'Em andamento', descricao: 'Conversa viva, sem decisão.', variant: 'info' },
  NAO_AGENDOU: { label: 'Não agendou', descricao: 'Decidiu não agendar.', variant: 'neutral' },
  CANCELOU: { label: 'Cancelou', descricao: 'Agendou e cancelou tudo.', variant: 'warning' },
  FALTOU: { label: 'Faltou', descricao: 'Agendou e não compareceu.', variant: 'danger' },
  AGENDOU: { label: 'Agendou', descricao: 'Tem agendamento confirmado.', variant: 'success' },
  NAO_E_LEAD: { label: 'Não é lead', descricao: 'Fornecedor, pessoal, spam.', variant: 'neutral' },
}

/** Ordem de trabalho da fila. Espelha ORDEM_DA_FILA do backend. */
export const ORDEM_DA_FILA: LeadStage[] = [
  'AGUARDANDO_NOS', 'SUMIU', 'INICIADA_SEM_RESPOSTA', 'SEM_CONVERSA', 'EM_ANDAMENTO',
  'NAO_AGENDOU', 'CANCELOU', 'FALTOU', 'AGENDOU',
]

/** O que a atendente pode escolher. Fato da agenda nao se edita. */
export const ESTAGIOS_EDITAVEIS: LeadStage[] = [
  'AGUARDANDO_NOS', 'SUMIU', 'INICIADA_SEM_RESPOSTA', 'SEM_CONVERSA', 'EM_ANDAMENTO', 'NAO_AGENDOU', 'NAO_E_LEAD',
]

export const FONTE_LABEL: Record<StageSource, string> = {
  REGRA: 'Pelas mensagens',
  MODELO: 'Sugerido pelo modelo',
  MANUAL: 'Corrigido pela equipe',
  HISTORICO: 'Conversa antiga, sem transcrição',
}

export const ORIGENS = [
  { value: 'landing-page', label: 'Site' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'harmonizacao', label: 'Harmonização' },
] as const
```

Teste `estagios.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { ESTAGIOS, ESTAGIOS_EDITAVEIS, ORDEM_DA_FILA } from './estagios'

describe('estagios', () => {
  it('a fila tem 9 e nao inclui NAO_E_LEAD', () => {
    expect(ORDEM_DA_FILA).toHaveLength(9)
    expect(ORDEM_DA_FILA).not.toContain('NAO_E_LEAD')
  })
  it('editaveis nao incluem fato da agenda', () => {
    for (const s of ['AGENDOU', 'CANCELOU', 'FALTOU']) expect(ESTAGIOS_EDITAVEIS).not.toContain(s)
  })
  it('todo estagio tem rotulo', () => {
    expect(Object.keys(ESTAGIOS)).toHaveLength(10)
  })
})
```

- [ ] **Passo 5: rodar** `cd frontend && npm run test -- leads.service estagios && npm run lint` e **commit** `feat(crm): tipos, service e hook de estagio no painel`.

---

## Tarefa 10: Modal de disparo aceita qualquer destinatário

**Arquivos:** modificar `frontend/src/pages/pacientes/components/BatchMessageModal.tsx`; teste em `frontend/src/pages/pacientes/components/BatchMessageModal.test.tsx` (criar se não existir).

- [ ] **Passo 1:** trocar o tipo da prop:

```ts
/** O minimo que o disparo precisa. Pacientes e leads servem. */
export interface Destinatario {
  id: string
  name: string | null
  phone: string
}

interface BatchMessageModalProps {
  open: boolean
  patients: Destinatario[]
  availableDates: string[]
  clinicTemplate?: string | null
  onClose: () => void
  onDone: () => void
}
```

`PatientWithStats` é estruturalmente compatível; `PacientesPage` não muda. Onde o componente lê campos além de `id`, `name`, `phone` (conferir o JSX da lista de destinatários), restringir a esses três.

- [ ] **Passo 2: teste**

```tsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BatchMessageModal } from './BatchMessageModal'

vi.mock('@/hooks/useMessages', () => ({
  useSendBatchMessages: () => ({ send: vi.fn(), results: [], isSending: false, isCheckingDelivery: false, progress: { sent: 0, total: 0 }, reset: vi.fn() }),
}))

describe('BatchMessageModal com destinatarios genericos', () => {
  it('lista um lead sem campos de paciente', () => {
    render(<BatchMessageModal open patients={[{ id: 'l1', name: 'Maria', phone: '5511999990000' }]} availableDates={['2026-11-06']} onClose={vi.fn()} onDone={vi.fn()} />)
    expect(screen.getByText('Maria')).toBeInTheDocument()
  })
})
```

- [ ] **Passo 3: rodar** `npm run test -- BatchMessageModal && npm run build` e **commit** `refactor(disparo): modal aceita destinatario generico`.

---

## Tarefa 11: Página `/crm`

**Arquivos:** criar `frontend/src/pages/crm/CrmPage.tsx`, `ChipsDeEstagio.tsx`, `EstagioBadge.tsx`, `PopoverDeEstagio.tsx`, `CrmPage.test.tsx`; modificar `frontend/src/router.tsx`, `frontend/src/layouts/AppLayout.tsx`, `frontend/src/lib/permissoes.ts`.

**Consome:** `useLeads(params)`, `useCorrigeEstagio()`, `useClinic()`, `useAvailabilityRules()` e o `useMemo` de `availableDates` como em `PacientesPage` (copiar a lógica, não o componente), `BatchMessageModal`, `Badge`, `Button`, `EmptyState`, `ErrorState`, `SkeletonTable`, `Pagination`, `formatPhone`.

- [ ] **Passo 1: `EstagioBadge.tsx`**

```tsx
import { Badge } from '@/components/ui/Badge'
import type { Lead } from '@/types'
import { ESTAGIOS, FONTE_LABEL } from './estagios'

interface EstagioBadgeProps {
  lead: Lead
  onClick?: () => void
}

/** Badge do estagio com o motivo e a fonte. Clicavel quando `onClick` existe. */
export function EstagioBadge({ lead, onClick }: EstagioBadgeProps) {
  if (!lead.stage) return <Badge variant="neutral">Processando</Badge>
  const info = ESTAGIOS[lead.stage]
  const fonte = lead.stage_source ? FONTE_LABEL[lead.stage_source] : ''
  const icone = lead.stage_source === 'MODELO' ? '◆' : lead.stage_source === 'MANUAL' ? '✎' : lead.stage_source === 'HISTORICO' ? '◷' : ''
  const conteudo = (
    <span className="inline-flex items-center gap-1.5">
      <Badge variant={info.variant}>{info.label}</Badge>
      {icone && <span aria-label={fonte} title={fonte} className="text-xs text-gray-400">{icone}</span>}
    </span>
  )
  return (
    <div className="flex flex-col gap-0.5">
      {onClick ? (
        <button type="button" onClick={onClick} className="text-left cursor-pointer rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500" aria-label={`Corrigir estágio de ${lead.name ?? lead.phone}`}>
          {conteudo}
        </button>
      ) : conteudo}
      {lead.stage_reason && <span className="text-xs text-gray-500">{lead.stage_reason}</span>}
    </div>
  )
}
```

- [ ] **Passo 2: `ChipsDeEstagio.tsx`**

```tsx
import type { LeadStage } from '@/types'
import { ESTAGIOS, ORDEM_DA_FILA } from './estagios'

interface ChipsDeEstagioProps {
  contagem: Record<string, number>
  selecionados: LeadStage[]
  onToggle: (stage: LeadStage) => void
  mostrarMais: boolean
  onMostrarMais: () => void
}

/** Um chip por estagio com a contagem. Multi-selecao. "Mais" revela Nao e lead. */
export function ChipsDeEstagio({ contagem, selecionados, onToggle, mostrarMais, onMostrarMais }: ChipsDeEstagioProps) {
  const lista: LeadStage[] = mostrarMais ? [...ORDEM_DA_FILA, 'NAO_E_LEAD'] : ORDEM_DA_FILA
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por estágio">
      {lista.map((stage) => {
        const ativo = selecionados.includes(stage)
        return (
          <button
            key={stage}
            type="button"
            aria-pressed={ativo}
            onClick={() => onToggle(stage)}
            title={ESTAGIOS[stage].descricao}
            className={[
              'inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm transition-colors cursor-pointer min-h-11',
              ativo ? 'bg-brand-500 text-white' : 'bg-gray-50 text-gray-700 hover:bg-gray-100',
            ].join(' ')}
          >
            {ESTAGIOS[stage].label}
            <span className={ativo ? 'text-white/80' : 'text-gray-400'}>{contagem[stage] ?? 0}</span>
          </button>
        )
      })}
      {!mostrarMais && (
        <button type="button" onClick={onMostrarMais} className="text-sm text-gray-500 underline-offset-2 hover:underline cursor-pointer min-h-11 px-2">
          mais
        </button>
      )}
    </div>
  )
}
```

- [ ] **Passo 3: `PopoverDeEstagio.tsx`** (inline, sem modal; usa `useCorrigeEstagio`)

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useCorrigeEstagio } from '@/hooks/useLeads'
import type { Lead, LeadStage } from '@/types'
import { ESTAGIOS, ESTAGIOS_EDITAVEIS } from './estagios'

interface PopoverDeEstagioProps {
  lead: Lead
  onFechar: () => void
}

export function PopoverDeEstagio({ lead, onFechar }: PopoverDeEstagioProps) {
  const [stage, setStage] = useState<LeadStage>(lead.stage && ESTAGIOS_EDITAVEIS.includes(lead.stage) ? lead.stage : 'EM_ANDAMENTO')
  const [reason, setReason] = useState(lead.stage_reason ?? '')
  const corrige = useCorrigeEstagio()

  const salvar = () => {
    corrige.mutate({ leadId: lead.id, stage, reason: reason.trim() || undefined }, { onSuccess: onFechar })
  }

  return (
    <div role="dialog" aria-label="Corrigir estágio" className="absolute z-20 mt-2 w-72 rounded-xl border border-gray-200 bg-white p-4 shadow-lg flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-gray-600">Estágio</span>
        <select value={stage} onChange={(e) => setStage(e.target.value as LeadStage)} className="rounded-md border border-gray-200 px-2 py-2 min-h-11">
          {ESTAGIOS_EDITAVEIS.map((s) => <option key={s} value={s}>{ESTAGIOS[s].label}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-gray-600">Motivo (opcional)</span>
        <input value={reason} maxLength={120} onChange={(e) => setReason(e.target.value)} placeholder="ex.: achou caro" className="rounded-md border border-gray-200 px-2 py-2 min-h-11" />
      </label>
      {corrige.isError && <p className="text-sm text-red-600">Não foi possível salvar. Tente de novo.</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onFechar}>Cancelar</Button>
        <Button size="sm" loading={corrige.isPending} onClick={salvar}>Salvar</Button>
      </div>
    </div>
  )
}
```

- [ ] **Passo 4: `CrmPage.tsx`**

```tsx
import { useMemo, useState } from 'react'
import { useLeads } from '@/hooks/useLeads'
import { useClinic } from '@/hooks/useClinic'
import { useAvailabilityRules } from '@/hooks/useAvailability'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Pagination } from '@/components/ui/Pagination'
import { formatPhone } from '@/utils/formatPhone'
import { BatchMessageModal, type Destinatario } from '@/pages/pacientes/components/BatchMessageModal'
import type { Lead, LeadStage } from '@/types'
import { ChipsDeEstagio } from './ChipsDeEstagio'
import { EstagioBadge } from './EstagioBadge'
import { PopoverDeEstagio } from './PopoverDeEstagio'
import { ORIGENS } from './estagios'

const POR_PAGINA_PADRAO = 25

export function CrmPage() {
  const [estagios, setEstagios] = useState<LeadStage[]>([])
  const [origens, setOrigens] = useState<string[]>([])
  const [mostrarMais, setMostrarMais] = useState(false)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(POR_PAGINA_PADRAO)
  const [selecionados, setSelecionados] = useState<Set<string>>(new Set())
  const [editando, setEditando] = useState<string | null>(null)
  const [disparoAberto, setDisparoAberto] = useState(false)

  const params = {
    stage: estagios.length ? estagios.join(',') : undefined,
    source: origens.length ? origens.join(',') : undefined,
    orderBy: 'dias_parado' as const,
    limit: perPage,
    offset: (page - 1) * perPage,
  }
  const { data, isLoading, isError, error, refetch } = useLeads(params)

  const { data: clinic } = useClinic()
  const { data: rulesData } = useAvailabilityRules()
  // Mesma regra de PacientesPage: proximas datas com regra ativa, limitadas por max_future_dates.
  const availableDates = useMemo(() => proximasDatas(rulesData, clinic?.max_future_dates), [rulesData, clinic])

  const leads = data?.leads ?? []
  const total = data?.total ?? 0
  const contagem = data?.totals.por_estagio ?? {}

  const toggleEstagio = (s: LeadStage) => {
    setPage(1)
    setEstagios((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]))
  }
  const toggleOrigem = (o: string) => {
    setPage(1)
    setOrigens((prev) => (prev.includes(o) ? prev.filter((x) => x !== o) : [...prev, o]))
  }
  const toggleLead = (id: string) => setSelecionados((prev) => {
    const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n
  })
  const selecionarPagina = () => setSelecionados(new Set(leads.map((l) => l.id)))
  const destinatarios: Destinatario[] = leads.filter((l) => selecionados.has(l.id)).map((l) => ({ id: l.id, name: l.name, phone: l.phone }))

  if (isLoading) return <div className="p-6"><SkeletonTable rows={8} /></div>
  if (isError) {
    return <div className="p-6"><ErrorState message={error instanceof Error ? error.message : 'Erro ao carregar o CRM.'} onRetry={() => refetch()} /></div>
  }

  return (
    <div className="p-6 flex flex-col gap-6 max-w-[1400px]">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">CRM</h1>
        <p className="text-sm text-gray-500">A fila da semana: quem precisa de resposta, quem sumiu, quem vale reativar.</p>
      </header>

      <ChipsDeEstagio contagem={contagem} selecionados={estagios} onToggle={toggleEstagio} mostrarMais={mostrarMais} onMostrarMais={() => setMostrarMais(true)} />

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filtrar por origem">
        <span className="text-xs uppercase tracking-wide text-gray-400">Origem</span>
        {ORIGENS.map((o) => (
          <button key={o.value} type="button" aria-pressed={origens.includes(o.value)} onClick={() => toggleOrigem(o.value)}
            className={['rounded-md px-3 py-1.5 text-sm cursor-pointer min-h-11', origens.includes(o.value) ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'].join(' ')}>
            {o.label}
          </button>
        ))}
      </div>

      {selecionados.size > 0 && (
        <div className="flex items-center justify-between rounded-xl bg-brand-50 px-4 py-3 text-sm">
          <span className="text-brand-800">{selecionados.size} selecionado{selecionados.size > 1 ? 's' : ''}</span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => setSelecionados(new Set())}>Limpar</Button>
            <Button size="sm" onClick={() => setDisparoAberto(true)}>Disparar mensagem</Button>
          </div>
        </div>
      )}

      {leads.length === 0 ? (
        <EmptyState title="Nada aqui" description={estagios.length || origens.length ? 'Nenhum lead com esse filtro. Tire um chip para ampliar.' : 'Os estágios aparecem depois da primeira rodada do classificador (todo dia às 7h).'} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                <th className="px-4 py-3"><button type="button" onClick={selecionarPagina} className="underline-offset-2 hover:underline cursor-pointer">Todos</button></th>
                <th className="px-3 py-3">Contato</th>
                <th className="px-3 py-3">Origem</th>
                <th className="px-3 py-3">Estágio</th>
                <th className="px-3 py-3">Última mensagem</th>
                <th className="px-3 py-3">Parado há</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {leads.map((lead: Lead) => (
                <tr key={lead.id} className="hover:bg-gray-50/50">
                  <td className="px-4 py-3">
                    <input type="checkbox" aria-label={`Selecionar ${lead.name ?? lead.phone}`} checked={selecionados.has(lead.id)} onChange={() => toggleLead(lead.id)} className="h-4 w-4" />
                  </td>
                  <td className="px-3 py-3">
                    <p className="font-medium text-gray-800">{lead.name || 'Sem nome'}</p>
                    <p className="text-gray-500">{formatPhone(lead.phone)}</p>
                  </td>
                  <td className="px-3 py-3"><Badge variant="neutral">{ORIGENS.find((o) => o.value === lead.source)?.label ?? lead.source}</Badge></td>
                  <td className="px-3 py-3 relative">
                    <EstagioBadge lead={lead} onClick={lead.stage && ['AGENDOU', 'CANCELOU', 'FALTOU'].includes(lead.stage) ? undefined : () => setEditando(lead.id)} />
                    {editando === lead.id && <PopoverDeEstagio lead={lead} onFechar={() => setEditando(null)} />}
                  </td>
                  <td className="px-3 py-3 text-gray-600 whitespace-nowrap">
                    {lead.ultima_mensagem_em ? `${new Date(lead.ultima_mensagem_em).toLocaleDateString('pt-BR')} · ${lead.ultima_mensagem_de === 'LEAD' ? 'do lead' : 'nossa'}` : '-'}
                  </td>
                  <td className="px-3 py-3 text-gray-700 whitespace-nowrap">{lead.dias_parado == null ? '-' : `${lead.dias_parado} d`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={page} perPage={perPage} total={total} onPageChange={setPage} onPerPageChange={(n) => { setPerPage(n); setPage(1) }} />
        </div>
      )}

      {disparoAberto && (
        <BatchMessageModal open patients={destinatarios} availableDates={availableDates} clinicTemplate={clinic?.batch_message_template}
          onClose={() => setDisparoAberto(false)} onDone={() => setSelecionados(new Set())} />
      )}
    </div>
  )
}
```

`proximasDatas(rulesData, maxFutureDates)` é a lógica do `useMemo` de `PacientesPage` extraída para `frontend/src/utils/proximasDatas.ts` e usada nos dois lugares (um padrão repetido 2 vezes vira util, conforme o checklist do `frontend/CLAUDE.md`). Os nomes `useClinic` e `useAvailabilityRules` são os que `PacientesPage` já importa; confirmar os caminhos ao implementar.

- [ ] **Passo 5: rota, menu, permissão**

`router.tsx`: `import { CrmPage } from '@/pages/crm/CrmPage'` e `{ path: 'crm', element: <CrmPage /> }` logo após `leads`.
`AppLayout.tsx`: no grupo WhatsApp, `{ to: '/crm', label: 'CRM' }` depois de Leads; adicionar ícone em `ICONS` (reaproveitar o de Leads se não houver outro).
`lib/permissoes.ts`: `ROTAS_DO_STAFF` ganha `'/crm'`, com comentário "fila semanal da recepcao (PRD 057); o backend abriu crm.ler e crm.escrever".
`lib/permissoes.test.ts`: `it('STAFF ve /crm', () => expect(podeVer({ papel: 'STAFF', permissoes: { see_prices: false, see_patient_list: true } }, '/crm')).toBe(true))`.

- [ ] **Passo 6: `CrmPage.test.tsx`**

```tsx
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { CrmPage } from './CrmPage'
import type { Lead } from '@/types'

const mockUseLeads = vi.fn()
const mockMutate = vi.fn()
vi.mock('@/hooks/useLeads', () => ({
  useLeads: (...a: unknown[]) => mockUseLeads(...a),
  useCorrigeEstagio: () => ({ mutate: mockMutate, isPending: false, isError: false }),
}))
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ clinicId: 'c1' }) }))
vi.mock('@/hooks/useClinic', () => ({ useClinic: () => ({ data: { max_future_dates: 5, batch_message_template: null } }) }))
vi.mock('@/hooks/useAvailability', () => ({ useAvailabilityRules: () => ({ data: [] }) }))
vi.mock('@/pages/pacientes/components/BatchMessageModal', () => ({
  BatchMessageModal: ({ patients }: { patients: { id: string }[] }) => <div data-testid="modal">{patients.length} destinatarios</div>,
}))

const lead = (over: Partial<Lead>): Lead => ({
  id: 'l1', clinic_id: 'c1', phone: '5511999990000', name: 'Maria', booked: false, source: 'landing-page',
  first_appointment_id: null, first_appointment_value: null, raw_message: null, first_contact_status: null,
  first_contact_at: null, conversation_started_at: null, conversation_status: null, has_whatsapp_chat: null,
  whatsapp_last_message_at: null, first_contact_channel: null, can_start_bot: null, bot_block_reason: null,
  bot_block_message: null, can_unmark_contact: null, contact_started: null, contact_started_source: null,
  contact_started_message: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
  stage: 'SUMIU', stage_reason: null, stage_source: 'REGRA', stage_updated_at: null,
  ultima_mensagem_em: '2026-10-10T00:00:00Z', ultima_mensagem_de: 'NOS', dias_parado: 14,
  ...over,
} as Lead)

function monta(leads: Lead[], por_estagio: Record<string, number> = {}) {
  mockUseLeads.mockReturnValue({
    data: { status: 'SUCCESS', leads, total: leads.length, totals: { total: leads.length, convertidos: 0, nao_convertidos: leads.length, por_estagio }, conversions: null },
    isLoading: false, isError: false, error: null, refetch: vi.fn(),
  })
  return render(<CrmPage />)
}

describe('CrmPage', () => {
  it('chips mostram a contagem e filtram', () => {
    monta([lead({})], { SUMIU: 7 })
    const chip = screen.getByRole('button', { name: /Sumiu/ })
    expect(chip).toHaveTextContent('7')
    fireEvent.click(chip)
    expect(mockUseLeads).toHaveBeenLastCalledWith(expect.objectContaining({ stage: 'SUMIU' }))
  })

  it('clicar no estagio abre o popover e salvar chama a mutation', () => {
    monta([lead({})])
    fireEvent.click(screen.getByRole('button', { name: /Corrigir estágio de Maria/ }))
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'NAO_AGENDOU' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(mockMutate).toHaveBeenCalledWith({ leadId: 'l1', stage: 'NAO_AGENDOU', reason: undefined }, expect.anything())
  })

  it('fato da agenda nao abre popover', () => {
    monta([lead({ stage: 'AGENDOU' })])
    expect(screen.queryByRole('button', { name: /Corrigir estágio/ })).toBeNull()
  })

  it('selecionar e disparar abre o modal com os leads', () => {
    monta([lead({}), lead({ id: 'l2', name: 'Joao' })])
    fireEvent.click(screen.getByRole('button', { name: 'Todos' }))
    fireEvent.click(screen.getByRole('button', { name: 'Disparar mensagem' }))
    expect(screen.getByTestId('modal')).toHaveTextContent('2 destinatarios')
  })

  it('vazio com filtro orienta a tirar o chip', () => {
    monta([])
    expect(screen.getByText(/Nada aqui/)).toBeInTheDocument()
  })
})
```

- [ ] **Passo 7: rodar** `cd frontend && npm run test && npm run lint && npm run build`, corrigir até zero warnings, e **commit** `feat(crm): pagina /crm com chips, correcao e disparo em lote`.

---

## Tarefa 12: Deploy em dev, backfill e E2E

- [ ] **Passo 1: deploy dev** do scheduler (sem Docker): `cd scheduler && npx serverless deploy --stage dev --aws-profile dev-andre`. Ler a saída, não o exit code.

- [ ] **Passo 2: dryRun em dev**

```bash
MSYS_NO_PATHCONV=1 aws lambda invoke --function-name clinic-scheduler-infra-dev-ClassificaLeads \
  --payload '{"dryRun": true}' --cli-binary-format raw-in-base64-out --profile dev-andre --region us-east-1 out.json && cat out.json
```

Esperado: `por_clinica` com `por_estagio` somando `leads`, `chamadas_modelo` abaixo do teto, sem `erro`.

- [ ] **Passo 3: rodar real em dev**, repetir a chamada sem `dryRun`, depois rodar o dryRun de novo: `mudaram` deve ser 0 na segunda (idempotência).

- [ ] **Passo 4: E2E no painel apontando para dev**: abrir `/crm`, conferir chips, filtrar "Sumiu" + "WhatsApp", corrigir um lead para "Não agendou" com motivo, recarregar e ver que ficou; selecionar 2 leads de teste e disparar; conferir que `/leads` não mudou.

- [ ] **Passo 5: prod**: migration (`setup_database` com as env de prod), deploy do scheduler em prod, dryRun em prod e **trazer a distribuição para o André antes do real**. Depois do real, conferir no painel.

- [ ] **Passo 6: documentação pós-task**: `tests/integration/057-crm-de-leads.md` (casos: filtros, PATCH recusa agenda, PATCH exige papel, job dryRun), `tests/postman/057-crm-de-leads.postman_requests.json` (GET com `stage`/`source`, PATCH, invoke manual), atualizar o Status do PRD 057 e `TASKS_LOG.md`.

- [ ] **Passo 7: abrir o PR** para `main` com o resumo das adaptações ao PRD (seção "Duas adaptações").

---

## Autorrevisão (feita ao escrever)

- **Cobertura do PRD:** dados (T1), regras (T2), transcrição (T3), classificador (T4), escrita e log (T5), job (T6), API GET (T7), PATCH e permissões (T7, T8), disparo (T10), página, rota, menu (T11), backfill e E2E (T12). Item 8.3 e `dias_parado` adaptados e declarados no topo.
- **Nomes cruzados:** `Sinais`/`Decisao`/`decide`, `ultimas_mensagens`/`resumo`, `Classificador.triagem/desfecho`, `precisa_de_triagem/precisa_de_desfecho`, `grava_estagio/registra_tentativa/marca_triagem/marca_desfecho_tentado`, `processa_clinica`, `contar_por_estagio`, `patchStage`, `useCorrigeEstagio`, `Destinatario` são os mesmos em todas as tarefas.
- **Pontos a confirmar ao implementar** (não são placeholders, são verificações): assinatura de `AnthropicService.create_message`; forma de chamada do `boto3 query` na T3 (uma forma só); nomes dos hooks `useClinic`/`useAvailabilityRules` em `PacientesPage`.
