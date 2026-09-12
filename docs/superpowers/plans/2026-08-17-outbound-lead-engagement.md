# Atendimento automático de leads pelo bot LLM — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Colocar o bot LLM atendendo leads da landing page no WhatsApp, em duas fases: primeiro num piloto restrito a uma lista de telefones, depois liberado para todos os leads de `landing-page`. Em nenhum momento pode haver disparo para leads antigos que já têm conversa em andamento.

**Architecture:** Uma política de resposta por clínica decide quem o bot atende (`OFF` → `PILOT` → `LEADS_ONLY` → `ALL`). O lead pode chegar de duas formas: escrevendo no WhatsApp (o bot responde) ou sem escrever (uma fila de envio abre a conversa). Nos dois casos quem fala é o mesmo agente LLM, com o mesmo prompt — não há mensagem de boas-vindas em template separado.

**Tech Stack:** Python 3.8 (Lambda), DynamoDB, PostgreSQL (Supabase), Serverless Framework, React 19 + TanStack Query no painel.

## Global Constraints

- **Nunca disparar para lead antigo.** Há 44 leads cadastrados, vários com conversa em andamento com atendentes humanos. Só lead recém-criado pode receber contato ativo, e o plano não inclui nenhum script de backfill.
- **`ALLOWED_PHONES` não é a allowlist do bot.** Ela vive no SSM (`/prod/ALLOWED_PHONES`, hoje `'*'`) e governa **todos** os envios do provider: lembretes de consulta, relatório diário e disparos do painel. Restringi-la quebraria lembretes de pacientes reais. A allowlist do piloto é separada, e a do provider não é tocada.
- **Nenhuma mudança pode desligar o bot de quem já usa.** `clinicadorods-da7b62` está em produção com `use_agent=true` e `bot_paused=false`. A coluna de política nasce com default `ALL` para preservar esse comportamento.
- **A voz é uma só.** O texto de abertura é gerado pelo agente LLM com o `AI_SYSTEM_PROMPT` já cadastrado. Não criar template paralelo de boas-vindas: dois textos divergem com o tempo.
- **Limite de 1 envio a cada 15 minutos por clínica**, proteção contra bloqueio do número no z-api (provider não-oficial, linha compartilhada com atendentes humanos).
- **Migrations idempotentes** na lista `MIGRATIONS` de `scheduler/src/scripts/setup_database.py`, com `IF NOT EXISTS`.
- **Logging com prefixo correlacionável**: `[<Componente>][req:<id>]`, padrão de `lead/create.py`.
- **Docstrings e comentários em português**; nomes de código em inglês. Nunca usar travessão (`—`), só hífen.
- Rodar `cd scheduler && python -m pytest tests/unit -q` antes de cada commit.

## Os dois cenários de chegada

O funil `google-ads → landing-page → lead → whatsapp` acontece de duas formas, e as duas terminam com o bot conduzindo:

| | Cenário A — lead escreve | Cenário B — lead não escreve |
|---|---|---|
| Gatilho | mensagem recebida no webhook | criação do lead no `POST /leads` |
| Quem inicia | o lead | a clínica |
| Horário comercial | irrelevante, a pessoa está online agora | obrigatório, é abordagem ativa |
| Limite de taxa | não se aplica | 1 a cada 15 min |
| Risco de incômodo | nenhum, ela procurou | real, por isso as guardas |
| Caminho no código | webhook → `should_bot_reply` → agente | `POST /leads` → fila → dispatcher → agente |

A diferença operacional é grande, mas o texto e o tom são os mesmos, porque nos dois casos é o `ConversationAgent` que escreve.

## Estado de que este plano parte

Já resolvido e em produção (PR #9, deploy 2026-08-29):
- O agente LLM voltou a funcionar (modelo e `temperature` corrigidos).
- `get_available_days` caiu de 82s para 8,2s.
- `AI_SYSTEM_PROMPT` (6.955 caracteres) e 17 FAQ cadastrados para a Essência.
- 6 datas de atendimento futuras cadastradas.

Configuração atual da Essência: `use_agent=false`, `bot_paused=true` — bot desligado.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `scheduler/src/services/bot_policy.py` | **Novo.** Função pura que decide se o bot responde uma conversa. |
| `scheduler/src/services/business_hours.py` | **Novo.** A clínica está aberta agora? Quando abre de novo? |
| `scheduler/src/services/outbound_queue.py` | **Novo.** Enfileirar, listar pendentes, marcar enviado/falho. |
| `scheduler/sls/resources/dynamodb/outbound-queue-table.yml` | **Novo.** Tabela + GSI `status-sendAfter-index`. |
| `scheduler/src/functions/outbound/processor.py` | **Novo.** Dispatcher em cron: drena a fila e faz o agente abrir a conversa. |
| `scheduler/sls/functions/outbound/interface.yml` | **Novo.** Declaração do dispatcher com `rate(15 minutes)`. |
| `scheduler/src/functions/lead/create.py` | **Modificar.** Enfileira contato ativo, com as guardas anti-disparo. |
| `scheduler/src/functions/webhook/handler.py` | **Modificar.** Aplica a política antes de responder. |
| `scheduler/src/functions/attendant/bot_toggle.py` | **Novo.** Liga/desliga o bot numa conversa (Fase 2). |
| `scheduler/src/scripts/setup_database.py` | **Modificar.** Colunas de política, allowlist e tracking. |
| `frontend/src/pages/leads/LeadsPage.tsx` | **Modificar.** Estado da conversa na lista (Fase 2). |

Testes em `scheduler/tests/unit/`: `test_bot_policy.py`, `test_business_hours.py`, `test_outbound_queue.py`, `test_outbound_guards.py`.

---

# FASE 1 — Piloto restrito a uma lista de telefones

Ao fim desta fase o bot atende de ponta a ponta, nos dois cenários, **apenas** para os telefones cadastrados no piloto. Qualquer outra pessoa que escreva continua sem resposta automática, exatamente como hoje.

---

### Task 1: Política de resposta e allowlist do piloto

**Files:**
- Modify: `scheduler/src/scripts/setup_database.py`
- Create: `scheduler/src/services/bot_policy.py`
- Modify: `scheduler/src/functions/clinic/update.py`
- Test: `scheduler/tests/unit/test_bot_policy.py`

**Interfaces:**
- Produces: `should_bot_reply(clinic: dict, session: dict, phone: str) -> bool`

Quatro políticas, em `clinics.bot_autoreply_policy`:

| Valor | Quem o bot atende |
|---|---|
| `ALL` (default) | todo mundo — comportamento atual de `clinicadorods-da7b62` |
| `PILOT` | só telefones em `clinics.bot_pilot_phones` |
| `LEADS_ONLY` | só conversas marcadas como lead da landing page (Fase 2) |
| `OFF` | ninguém |

- [ ] **Step 1: Adicionar as colunas**

Em `setup_database.py`, na lista `MIGRATIONS`:

```python
    # Política de resposta automática do bot, por clínica.
    # ALL preserva o comportamento atual; as demais restringem.
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS bot_autoreply_policy VARCHAR(20) NOT NULL DEFAULT 'ALL'",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_bot_autoreply_policy') THEN
            ALTER TABLE scheduler.clinics ADD CONSTRAINT chk_bot_autoreply_policy
            CHECK (bot_autoreply_policy IN ('ALL', 'PILOT', 'LEADS_ONLY', 'OFF'));
        END IF;
    END $$
    """,
    # Telefones do piloto, normalizados (55DDDNNNNNNNNN). Só usado com policy=PILOT.
    # Separado de ALLOWED_PHONES do SSM de propósito: aquela governa lembretes e
    # disparos do painel, e restringi-la deixaria pacientes reais sem lembrete.
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS bot_pilot_phones TEXT[] NOT NULL DEFAULT '{}'",
```

Adicionar `bot_autoreply_policy` e `bot_pilot_phones` à lista `ALLOWED_FIELDS` de `clinic/update.py`.

- [ ] **Step 2: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_bot_policy.py
"""Quem o bot responde automaticamente.

O default tem que continuar respondendo todo mundo: há clínica em produção
dependendo disso. Toda restrição é opt-in por clínica.
"""
import os
import time
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.bot_policy import should_bot_reply

PILOTO = "5511970521647"


class TestAll(unittest.TestCase):
    def test_responde_qualquer_um(self):
        self.assertTrue(should_bot_reply({"bot_autoreply_policy": "ALL"}, {}, "5511999999999"))

    def test_coluna_ausente_se_comporta_como_all(self):
        self.assertTrue(should_bot_reply({}, {}, "5511999999999"))


class TestOff(unittest.TestCase):
    def test_nao_responde_ninguem(self):
        self.assertFalse(should_bot_reply({"bot_autoreply_policy": "OFF"}, {}, PILOTO))


class TestPilot(unittest.TestCase):
    def setUp(self):
        self.clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PILOTO]}

    def test_responde_telefone_do_piloto(self):
        self.assertTrue(should_bot_reply(self.clinic, {}, PILOTO))

    def test_nao_responde_fora_do_piloto(self):
        self.assertFalse(should_bot_reply(self.clinic, {}, "5511988887777"))

    def test_compara_telefone_normalizado(self):
        # o webhook entrega o número em formatos variados
        self.assertTrue(should_bot_reply(self.clinic, {}, "+55 (11) 97052-1647"))

    def test_piloto_vazio_nao_responde_ninguem(self):
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": []}

        self.assertFalse(should_bot_reply(clinic, {}, PILOTO))


class TestLeadsOnly(unittest.TestCase):
    def setUp(self):
        self.clinic = {"bot_autoreply_policy": "LEADS_ONLY"}

    def test_conversa_sem_marca_nao_recebe(self):
        self.assertFalse(should_bot_reply(self.clinic, {}, "5511999999999"))

    def test_conversa_de_lead_recebe(self):
        self.assertTrue(should_bot_reply(self.clinic, {"bot_enabled": True}, "5511999999999"))

    def test_desligado_manualmente_nao_recebe(self):
        self.assertFalse(should_bot_reply(self.clinic, {"bot_enabled": False}, "5511999999999"))


class TestAtendenteHumano(unittest.TestCase):
    def test_atendente_ativo_suspende_em_qualquer_politica(self):
        session = {"attendant_active_until": int(time.time()) + 3600, "bot_enabled": True}
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PILOTO]}

        self.assertFalse(should_bot_reply(clinic, session, PILOTO))

    def test_atendente_expirado_nao_bloqueia(self):
        session = {"attendant_active_until": int(time.time()) - 10}
        clinic = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": [PILOTO]}

        self.assertTrue(should_bot_reply(clinic, session, PILOTO))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar o teste para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_bot_policy.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'src.services.bot_policy'`

- [ ] **Step 4: Implementar**

```python
"""Decide se o bot responde automaticamente uma conversa.

Função pura, sem I/O: recebe a clínica, a sessão e o telefone, devolve sim ou não.
Fica fora do handler porque é a regra que muda a cada fase do rollout, e precisa
ser testável sem subir webhook.
"""
from typing import Dict

from src.utils.phone import normalize_phone

POLICY_ALL = "ALL"
POLICY_PILOT = "PILOT"
POLICY_LEADS_ONLY = "LEADS_ONLY"
POLICY_OFF = "OFF"


def should_bot_reply(clinic: Dict, session: Dict, phone: str) -> bool:
    """O bot deve responder automaticamente esta conversa?

    Atendente humano ativo sempre suspende o bot, em qualquer política: se alguém
    da clínica assumiu a conversa, o bot não fala por cima.
    """
    import time

    session = session or {}
    clinic = clinic or {}

    ativo_ate = session.get("attendant_active_until")
    if ativo_ate and int(ativo_ate) > int(time.time()):
        return False

    policy = clinic.get("bot_autoreply_policy") or POLICY_ALL

    if policy == POLICY_OFF:
        return False

    if policy == POLICY_ALL:
        return True

    if policy == POLICY_PILOT:
        piloto = {normalize_phone(p) for p in (clinic.get("bot_pilot_phones") or [])}
        return normalize_phone(phone) in piloto

    if policy == POLICY_LEADS_ONLY:
        return bool(session.get("bot_enabled"))

    return False
```

- [ ] **Step 5: Rodar os testes**

Run: `cd scheduler && python -m pytest tests/unit/test_bot_policy.py -v`
Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add scheduler/src/services/bot_policy.py scheduler/tests/unit/test_bot_policy.py \
        scheduler/src/scripts/setup_database.py scheduler/src/functions/clinic/update.py
git commit -m "feat(scheduler): política de resposta do bot com allowlist de piloto"
```

---

### Task 2: Aplicar a política no webhook (cenário A)

**Files:**
- Modify: `scheduler/src/functions/webhook/handler.py`

**Interfaces:**
- Consumes: `should_bot_reply` (Task 1).

Hoje o handler sai cedo quando `bot_paused=True` (linha ~125), **antes** de registrar a mensagem recebida. Por isso a Essência tem 7.200 eventos e **zero INBOUND**: toda mensagem de paciente é descartada sem rastro. Esta task inverte a ordem — registra primeiro, decide depois.

- [ ] **Step 1: Registrar a mensagem antes de decidir**

Em `webhook/handler.py`, substituir o bloco de saída antecipada por:

```python
        # A mensagem recebida é registrada ANTES de qualquer decisão sobre responder.
        # Suprimir a resposta não pode significar perder a mensagem: ela precisa
        # aparecer no painel do atendente de qualquer forma.
        incoming = provider.parse_incoming_message(body)
        tracker.track_inbound(
            clinic_id=clinic_id,
            phone=incoming.phone,
            message_id=incoming.message_id,
            conversation_id=f"{clinic_id}#{incoming.phone}",
            message_type=incoming.message_type,
            content=incoming.content,
        )

        from src.services.bot_policy import should_bot_reply

        session = _load_session(_get_sessions_table(), clinic_id, incoming.phone)
        if clinic.get("bot_paused", False) or not should_bot_reply(clinic, session, incoming.phone):
            logger.info(
                f"[Webhook] Resposta automática suprimida para {incoming.phone} "
                f"(paused={clinic.get('bot_paused')}, "
                f"policy={clinic.get('bot_autoreply_policy', 'ALL')})"
            )
            return http_response(200, {"status": "OK"})
```

`bot_paused` continua valendo como interruptor geral, acima da política — é o botão de pânico da clínica.

Mover a construção do `provider` e do `tracker` para antes desse bloco, se ainda não estiverem.

- [ ] **Step 2: Validar a suíte**

Run: `cd scheduler && python -m pytest tests/unit -q`
Expected: todos passando.

- [ ] **Step 3: Commit**

```bash
git add scheduler/src/functions/webhook/handler.py
git commit -m "feat(scheduler): webhook registra inbound e aplica política antes de responder"
```

---

### Task 3: Janela de horário comercial

**Files:**
- Create: `scheduler/src/services/business_hours.py`
- Test: `scheduler/tests/unit/test_business_hours.py`

**Interfaces:**
- Consumes: o JSONB `clinics.business_hours`, formato `{"mon": {"start": "07:15", "end": "21:00"}, ...}`. Dia ausente significa fechado.
- Produces:
  - `is_open(business_hours: dict, moment: datetime) -> bool`
  - `next_opening(business_hours: dict, moment: datetime) -> datetime | None`

Só o cenário B usa isso. O cenário A responde na hora, porque a pessoa está do outro lado esperando.

- [ ] **Step 1: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_business_hours.py
"""Janela de envio a partir do horário comercial cadastrado.

Os casos usam o horário real da Essência (seg-sex 07:15-21:00, sem fim de semana)
porque é ele que expõe o comportamento que importa: a maior parte dos leads chega
fora dessa janela, então o salto para a próxima abertura é o caminho comum.
"""
import os
import unittest
from datetime import datetime

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.business_hours import is_open, next_opening

TZ = pytz.timezone("America/Sao_Paulo")
ESSENCIA = {d: {"start": "07:15", "end": "21:00"} for d in ["mon", "tue", "wed", "thu", "fri"]}


def _local(ano, mes, dia, hora, minuto):
    return TZ.localize(datetime(ano, mes, dia, hora, minuto))


class TestIsOpen(unittest.TestCase):
    def test_dentro_da_janela(self):
        self.assertTrue(is_open(ESSENCIA, _local(2026, 8, 17, 16, 46)))

    def test_antes_da_abertura(self):
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 17, 7, 0)))

    def test_na_abertura_esta_aberto(self):
        self.assertTrue(is_open(ESSENCIA, _local(2026, 8, 17, 7, 15)))

    def test_no_fechamento_esta_fechado(self):
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 17, 21, 0)))

    def test_dia_nao_configurado(self):
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 15, 10, 0)))

    def test_sem_configuracao(self):
        self.assertFalse(is_open({}, _local(2026, 8, 17, 10, 0)))


class TestNextOpening(unittest.TestCase):
    def test_ja_aberto_devolve_o_momento(self):
        momento = _local(2026, 8, 17, 16, 46)
        self.assertEqual(next_opening(ESSENCIA, momento), momento)

    def test_antes_da_abertura_salta_para_hoje(self):
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 17, 6, 0)), _local(2026, 8, 17, 7, 15))

    def test_depois_do_fechamento_salta_para_amanha(self):
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 12, 23, 46)), _local(2026, 8, 13, 7, 15))

    def test_sabado_salta_para_segunda(self):
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 15, 6, 45)), _local(2026, 8, 17, 7, 15))

    def test_domingo_salta_para_segunda(self):
        self.assertEqual(next_opening(ESSENCIA, _local(2026, 8, 16, 19, 2)), _local(2026, 8, 17, 7, 15))

    def test_sem_configuracao_devolve_none(self):
        self.assertIsNone(next_opening({}, _local(2026, 8, 17, 10, 0)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_business_hours.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
"""Janela de envio derivada do horário comercial cadastrado pela clínica.

Funções puras, sem I/O. Formato de `business_hours` é o JSONB de
`scheduler.clinics`. Dia ausente significa fechado, que é como sábado e domingo
aparecem hoje na Essência.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional

import pytz

CLINIC_TZ = pytz.timezone("America/Sao_Paulo")

# datetime.weekday(): 0 = segunda
_DIAS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DIAS_NA_SEMANA = 7


def _janela_do_dia(business_hours: Dict, momento: datetime):
    dia = business_hours.get(_DIAS[momento.weekday()])
    if not dia or not dia.get("start") or not dia.get("end"):
        return None

    abre_h, abre_m = (int(p) for p in dia["start"].split(":"))
    fecha_h, fecha_m = (int(p) for p in dia["end"].split(":"))

    base = momento.replace(hour=0, minute=0, second=0, microsecond=0)
    return base.replace(hour=abre_h, minute=abre_m), base.replace(hour=fecha_h, minute=fecha_m)


def is_open(business_hours: Dict, moment: datetime) -> bool:
    """A clínica está atendendo neste instante?

    Abertura inclusiva, fechamento exclusivo: às 21:00 em ponto já fechou.
    """
    janela = _janela_do_dia(business_hours or {}, moment)
    if janela is None:
        return False
    abertura, fechamento = janela
    return abertura <= moment < fechamento


def next_opening(business_hours: Dict, moment: datetime) -> Optional[datetime]:
    """Primeiro instante a partir de `moment` em que a clínica está aberta.

    Devolve o próprio `moment` se já estiver aberta, e None se nenhum dia estiver
    configurado — sem isso a busca não terminaria.
    """
    business_hours = business_hours or {}
    if not any(business_hours.get(d) for d in _DIAS):
        return None

    if is_open(business_hours, moment):
        return moment

    janela = _janela_do_dia(business_hours, moment)
    if janela is not None and moment < janela[0]:
        return janela[0]

    candidato = moment
    for _ in range(_DIAS_NA_SEMANA):
        candidato = (candidato + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        janela = _janela_do_dia(business_hours, candidato)
        if janela is not None:
            return janela[0]

    return None
```

- [ ] **Step 4: Rodar os testes**

Run: `cd scheduler && python -m pytest tests/unit/test_business_hours.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add scheduler/src/services/business_hours.py scheduler/tests/unit/test_business_hours.py
git commit -m "feat(scheduler): janela de envio a partir do horário comercial"
```

---

### Task 4: Fila de envio ativo

**Files:**
- Create: `scheduler/sls/resources/dynamodb/outbound-queue-table.yml`
- Create: `scheduler/src/services/outbound_queue.py`
- Modify: `scheduler/serverless.yml`
- Test: `scheduler/tests/unit/test_outbound_queue.py`

**Interfaces:**
- Consumes: `next_opening` (Task 3).
- Produces, em `OutboundQueueService`:
  - `enqueue(clinic_id, phone, *, lead_id=None, business_hours=None, now=None) -> dict | None`
  - `pending_due(now_iso: str, limit: int = 50) -> list`
  - `mark_sent(message_id, pk, sk)` / `mark_failed(message_id, pk, sk, error)`

Repare que `enqueue` **não recebe texto**: o conteúdo é gerado pelo agente na hora do envio (Task 5), para não existir um segundo texto de boas-vindas fora do prompt.

Formato do item, espelhando `scheduled-reminders`:

```
pk        = "CLINIC#{clinic_id}"
sk        = "OUT#{sendAfter}#{messageId}"
messageId, clinicId, phone, leadId, kind
status    = PENDING | SENT | FAILED
sendAfter = ISO-8601 UTC, instante a partir do qual pode sair
attempts, createdAt, sentAt, error
ttl       = createdAt + 30 dias
```

- [ ] **Step 1: Criar a tabela**

`scheduler/sls/resources/dynamodb/outbound-queue-table.yml`:

```yaml
Resources:
  OutboundQueueTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: ${self:custom.resourcePrefix}-outbound-queue
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S
        - AttributeName: status
          AttributeType: S
        - AttributeName: sendAfter
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: status-sendAfter-index
          KeySchema:
            - AttributeName: status
              KeyType: HASH
            - AttributeName: sendAfter
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
```

Registrar em `serverless.yml` junto dos outros resources e adicionar a env var `OUTBOUND_QUEUE_TABLE: ${self:custom.resourcePrefix}-outbound-queue` em `provider.environment`, como já é feito com `SCHEDULED_REMINDERS_TABLE`.

- [ ] **Step 2: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_outbound_queue.py
"""Fila de envio: quando a mensagem pode sair e transições de status.

O DynamoDB é substituído por um fake em memória para o teste cobrir a regra de
negócio sem depender de infraestrutura.
"""
import os
import unittest
from datetime import datetime

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")

TZ = pytz.timezone("America/Sao_Paulo")
ESSENCIA = {d: {"start": "07:15", "end": "21:00"} for d in ["mon", "tue", "wed", "thu", "fri"]}


class FakeTable:
    def __init__(self):
        self.items = []
        self.updates = []

    def put_item(self, Item):
        self.items.append(Item)

    def update_item(self, **kwargs):
        self.updates.append(kwargs)


def _service(table):
    from src.services.outbound_queue import OutboundQueueService

    service = OutboundQueueService.__new__(OutboundQueueService)
    service.table = table
    return service


class TestEnqueue(unittest.TestCase):
    def test_dentro_do_horario_sai_imediatamente(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours=ESSENCIA, now=agora)

        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(item["sendAfter"], "2026-08-17T19:46:00Z")  # 16:46 BRT = 19:46 UTC

    def test_fora_do_horario_espera_a_proxima_abertura(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 15, 6, 45))  # sábado

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours=ESSENCIA, now=agora)

        self.assertEqual(item["sendAfter"], "2026-08-17T10:15:00Z")  # segunda 07:15 BRT

    def test_sem_horario_configurado_nao_enfileira(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 10, 0))

        item = _service(table).enqueue("clinica-x", "5511999999999", business_hours={}, now=agora)

        self.assertIsNone(item)
        self.assertEqual(table.items, [])

    def test_grava_chaves_e_lead(self):
        table = FakeTable()
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))

        item = _service(table).enqueue(
            "clinica-x", "5511999999999", lead_id="lead-1", business_hours=ESSENCIA, now=agora
        )

        self.assertEqual(item["leadId"], "lead-1")
        self.assertEqual(item["kind"], "FIRST_CONTACT")
        self.assertEqual(item["pk"], "CLINIC#clinica-x")
        self.assertTrue(item["sk"].startswith("OUT#2026-08-17T19:46:00Z#"))
        self.assertEqual(len(table.items), 1)


class TestTransicoes(unittest.TestCase):
    def test_mark_sent(self):
        table = FakeTable()
        _service(table).mark_sent("msg-1", "CLINIC#c", "OUT#x#msg-1")
        self.assertIn("SENT", str(table.updates[0]))

    def test_mark_failed_registra_erro(self):
        table = FakeTable()
        _service(table).mark_failed("msg-1", "CLINIC#c", "OUT#x#msg-1", "timeout")
        self.assertIn("timeout", str(table.updates[0]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_outbound_queue.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 4: Implementar**

```python
"""Fila de mensagens ativas, drenada pelo dispatcher em cron.

Existe porque o disparo não pode ser síncrono ao cadastro do lead: precisa
respeitar o horário comercial e um limite de taxa que protege o número contra
bloqueio no provider.

A fila guarda a INTENÇÃO de falar, não o texto. O texto é gerado pelo agente no
momento do envio, com o mesmo prompt usado quando o lead escreve primeiro.
"""
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from src.services.business_hours import next_opening

logger = logging.getLogger(__name__)

TTL_DIAS = 30


class OutboundQueueService:

    def __init__(self):
        self.table = boto3.resource("dynamodb").Table(os.environ["OUTBOUND_QUEUE_TABLE"])

    def enqueue(
        self,
        clinic_id: str,
        phone: str,
        *,
        lead_id: Optional[str] = None,
        kind: str = "FIRST_CONTACT",
        business_hours: Optional[Dict] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Dict]:
        """Enfileira uma abordagem para o próximo horário em que a clínica atende.

        Devolve None quando não há horário configurado: sem janela não há quando
        enviar, e o item ficaria preso na fila para sempre.
        """
        agora = now or datetime.now(timezone.utc)
        saida = next_opening(business_hours or {}, agora)
        if saida is None:
            logger.warning(f"[OutboundQueue] Clínica {clinic_id} sem horário configurado, não enfileirado")
            return None

        send_after = saida.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        message_id = str(uuid.uuid4())
        item = {
            "pk": f"CLINIC#{clinic_id}",
            "sk": f"OUT#{send_after}#{message_id}",
            "messageId": message_id,
            "clinicId": clinic_id,
            "phone": phone,
            "leadId": lead_id,
            "kind": kind,
            "status": "PENDING",
            "sendAfter": send_after,
            "attempts": 0,
            "createdAt": agora.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ttl": int(time.time()) + TTL_DIAS * 24 * 60 * 60,
        }
        self.table.put_item(Item=item)
        logger.info(f"[OutboundQueue] {message_id} enfileirado para {clinic_id}, sai a partir de {send_after}")
        return item

    def pending_due(self, now_iso: str, limit: int = 50) -> List[Dict]:
        """Itens PENDING cujo sendAfter já passou, mais antigos primeiro."""
        response = self.table.query(
            IndexName="status-sendAfter-index",
            KeyConditionExpression=Key("status").eq("PENDING") & Key("sendAfter").lte(now_iso),
            Limit=limit,
        )
        return response.get("Items", [])

    def mark_sent(self, message_id: str, pk: str, sk: str) -> None:
        self.table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression="SET #s = :status, sentAt = :sent_at, attempts = attempts + :one",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "SENT",
                ":sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ":one": 1,
            },
        )

    def mark_failed(self, message_id: str, pk: str, sk: str, error: str) -> None:
        self.table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression="SET #s = :status, #e = :error, attempts = attempts + :one",
            ExpressionAttributeNames={"#s": "status", "#e": "error"},
            ExpressionAttributeValues={":status": "FAILED", ":error": error, ":one": 1},
        )
```

- [ ] **Step 5: Rodar os testes**

Run: `cd scheduler && python -m pytest tests/unit/test_outbound_queue.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add scheduler/src/services/outbound_queue.py scheduler/tests/unit/test_outbound_queue.py \
        scheduler/sls/resources/dynamodb/outbound-queue-table.yml scheduler/serverless.yml
git commit -m "feat(scheduler): fila de envio ativo com janela de horário comercial"
```

---

### Task 5: Dispatcher — o agente abre a conversa (cenário B)

**Files:**
- Create: `scheduler/src/functions/outbound/__init__.py`
- Create: `scheduler/src/functions/outbound/processor.py`
- Create: `scheduler/sls/functions/outbound/interface.yml`
- Modify: `scheduler/serverless.yml`

**Interfaces:**
- Consumes: `OutboundQueueService`, `is_open`, `should_bot_reply`, `ConversationAgent`.
- Produces: `handler(event, context) -> dict` com `{"processed", "sent", "skipped", "failed"}`.

**Como o texto é gerado.** O dispatcher chama o `ConversationAgent` com uma mensagem sintética de abertura (`__INICIAR_CONVERSA__`), que o prompt trata como "primeiro contato". A resposta do agente é o que sai no WhatsApp. Isso garante uma voz só: o mesmo prompt que atende quem escreve primeiro é o que abre a conversa.

**Limite de taxa.** O cron roda a cada 15 minutos e envia no máximo **uma** mensagem por clínica por execução. O próprio intervalo é o limitador — sem contador distribuído, sem lock.

- [ ] **Step 1: Declarar a função**

`scheduler/sls/functions/outbound/interface.yml`:

```yaml
OutboundProcessor:
  handler: src.functions.outbound.processor.handler
  memorySize: 512
  timeout: 120
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-OutboundProcessor-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:Query
        - dynamodb:UpdateItem
        - dynamodb:GetItem
        - dynamodb:PutItem
      Resource:
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-outbound-queue"
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-outbound-queue/index/*"
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-message-events"
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-conversation-sessions"
    - Effect: Allow
      Action:
        - ssm:GetParameter
      Resource:
        - "arn:aws:ssm:${self:provider.region}:*:parameter/${self:custom.stage}/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - schedule:
        rate: rate(15 minutes)
```

Incluir o arquivo na lista `functions` do `serverless.yml`.

- [ ] **Step 2: Implementar o dispatcher**

```python
"""Dispatcher da fila de envio ativo.

Roda a cada 15 minutos e envia no máximo uma mensagem por clínica por execução.
Esse limite é a proteção contra bloqueio do número: o provider é o z-api, que é
não-oficial, e a linha é compartilhada com os atendentes humanos, então um
bloqueio derruba a operação inteira e não só o bot.

O texto não vem da fila: é o ConversationAgent que escreve, com o mesmo prompt
usado quando o lead escreve primeiro. A fila guarda só a intenção de falar.
"""
import logging
import time
import uuid

from src.providers.whatsapp_provider import IncomingMessage, get_provider
from src.services.bot_policy import should_bot_reply
from src.services.business_hours import CLINIC_TZ, is_open
from src.services.db.postgres import PostgresService
from src.services.message_tracker import MessageTracker
from src.services.outbound_queue import OutboundQueueService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_ENVIOS_POR_CLINICA_POR_EXECUCAO = 1
GATILHO_ABERTURA = "__INICIAR_CONVERSA__"


def _monta_agente(db, clinic, provider, tracker):
    from src.services.appointment_service import AppointmentService
    from src.services.availability_engine import AvailabilityEngine
    from src.services.conversation_agent import ConversationAgent
    from src.services.template_service import TemplateService

    return ConversationAgent(
        db=db,
        template_service=TemplateService(db),
        availability_engine=AvailabilityEngine(db),
        appointment_service=AppointmentService(db),
        provider=provider,
        message_tracker=tracker,
    )


def handler(event, context):
    from datetime import datetime, timezone

    trace_id = str(uuid.uuid4())[:8]
    prefixo = f"[OutboundProcessor][trace:{trace_id}]"
    logger.info(f"{prefixo} Iniciando drenagem da fila")

    queue = OutboundQueueService()
    tracker = MessageTracker()
    db = PostgresService()

    agora_utc = datetime.now(timezone.utc)
    pendentes = queue.pending_due(agora_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))

    enviados_por_clinica = {}
    sent = skipped = failed = 0
    clinic_cache = {}

    for item in pendentes:
        clinic_id = item.get("clinicId", "")
        message_id = item.get("messageId", "")
        phone = item.get("phone", "")

        if enviados_por_clinica.get(clinic_id, 0) >= MAX_ENVIOS_POR_CLINICA_POR_EXECUCAO:
            skipped += 1
            continue

        try:
            if clinic_id not in clinic_cache:
                clinicas = db.execute_query(
                    "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
                    (clinic_id,),
                )
                clinic_cache[clinic_id] = clinicas[0] if clinicas else None
            clinic = clinic_cache[clinic_id]

            if not clinic:
                queue.mark_failed(message_id, item["pk"], item["sk"], "Clínica não encontrada")
                failed += 1
                continue

            # A política é reconferida no envio: o piloto pode ter mudado depois
            # que o item entrou na fila, e ninguém deve receber abordagem de uma
            # clínica que voltou atrás.
            if clinic.get("bot_paused") or not should_bot_reply(clinic, {}, phone):
                logger.info(f"{prefixo} Política não permite falar com {phone}, descartando {message_id}")
                queue.mark_failed(message_id, item["pk"], item["sk"], "politica_nao_permite")
                skipped += 1
                continue

            # Horário reconferido: a clínica pode ter mudado os horários.
            if not is_open(clinic.get("business_hours") or {}, agora_utc.astimezone(CLINIC_TZ)):
                logger.info(f"{prefixo} Clínica {clinic_id} fechada agora, adiando {message_id}")
                skipped += 1
                continue

            provider = get_provider(clinic)
            agente = _monta_agente(db, clinic, provider, tracker)

            # O agente escreve a abertura. A mensagem sintética não é registrada
            # como INBOUND: ninguém escreveu isso, é só o gatilho.
            abertura = IncomingMessage(
                message_id=str(uuid.uuid4()), phone=phone, sender_name="",
                timestamp=int(time.time()), message_type="TEXT", content=GATILHO_ABERTURA,
            )
            saidas = agente.process_message(clinic_id, abertura)

            if not saidas:
                queue.mark_failed(message_id, item["pk"], item["sk"], "agente_nao_gerou_texto")
                failed += 1
                continue

            # O ConversationAgent já envia e rastreia via provider/tracker.
            queue.mark_sent(message_id, item["pk"], item["sk"])
            enviados_por_clinica[clinic_id] = enviados_por_clinica.get(clinic_id, 0) + 1
            sent += 1
            logger.info(f"{prefixo} Conversa aberta com {phone} ({message_id})")

            if item.get("leadId"):
                db.execute_query(
                    "UPDATE scheduler.leads SET first_contact_status = 'SENT', "
                    "first_contact_at = NOW(), updated_at = NOW() WHERE id = %s::uuid",
                    (item["leadId"],),
                )

        except Exception as e:
            logger.error(f"{prefixo} Erro em {message_id}: {e}", exc_info=True)
            queue.mark_failed(message_id, item["pk"], item["sk"], str(e))
            failed += 1

    logger.info(
        f"{prefixo} Concluído: {len(pendentes)} pendentes, {sent} enviados, "
        f"{skipped} adiados, {failed} falhas"
    )
    return {"processed": len(pendentes), "sent": sent, "skipped": skipped, "failed": failed}
```

- [ ] **Step 3: Ensinar o prompt a tratar o gatilho**

O `AI_SYSTEM_PROMPT` da Essência (já cadastrado em `message_templates`) precisa de um trecho novo, aplicado por `UPDATE` no banco:

```
═══ ABERTURA DE CONVERSA ═══
Se a mensagem do usuário for exatamente __INICIAR_CONVERSA__, ninguém escreveu nada:
é a clínica iniciando o contato com alguém que acabou de preencher o formulário no site.
Nesse caso, cumprimente, diga em uma linha que viu o interesse pelo site, apresente a
clínica em 2 ou 3 linhas (tecnologia + sessão avulsa) e pergunte quais áreas a pessoa
gostaria de tratar. Nunca mencione o gatilho nem diga que é uma mensagem automática.
```

- [ ] **Step 4: Validar a suíte**

Run: `cd scheduler && python -m pytest tests/unit -q`
Expected: todos passando.

- [ ] **Step 5: Commit**

```bash
git add scheduler/src/functions/outbound/ scheduler/sls/functions/outbound/interface.yml scheduler/serverless.yml
git commit -m "feat(scheduler): dispatcher onde o agente abre a conversa, 1 envio a cada 15min"
```

---

### Task 6: Gatilho no lead, com as guardas anti-disparo

**Files:**
- Modify: `scheduler/src/scripts/setup_database.py`
- Modify: `scheduler/src/functions/lead/create.py`
- Modify: `scheduler/sls/functions/lead/interface.yml`
- Test: `scheduler/tests/unit/test_outbound_guards.py`

**Interfaces:**
- Produces: `should_start_conversation(lead, clinic, *, agora=None) -> bool`

**Esta é a task mais sensível do plano.** Há 44 leads cadastrados, muitos com conversa em andamento. Um disparo indevido não tem desfazer: a mensagem chega no WhatsApp da pessoa.

Quatro guardas independentes, todas precisam passar:

| Guarda | Bloqueia |
|---|---|
| Lead novo | lead que caiu em UPDATE no upsert (`created_at != updated_at`) |
| Origem | qualquer `source` que não seja `landing-page` |
| Idade | lead criado há mais de 10 minutos — mata qualquer backfill ou replay |
| Política | telefone que a política da clínica não autoriza |

- [ ] **Step 1: Colunas de tracking**

Em `setup_database.py`, na lista `MIGRATIONS`:

```python
    # Rastreio do primeiro contato ativo com o lead.
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS first_contact_status VARCHAR(20)",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMPTZ",
    # Preenchido quando o lead responde, não quando o bot fala.
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS conversation_started_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS idx_leads_first_contact ON scheduler.leads(clinic_id, first_contact_status)",
```

Adicionar as três também ao `CREATE TABLE` de `leads`, para manter em sincronia.

- [ ] **Step 2: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_outbound_guards.py
"""Guardas contra disparo indevido de contato ativo.

Há 44 leads cadastrados, vários com conversa em andamento com atendentes humanos.
Uma mensagem enviada por engano não tem desfazer, então cada guarda é testada
isoladamente e em conjunto.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")

from src.functions.lead.create import should_start_conversation

AGORA = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
CLINICA = {"bot_autoreply_policy": "PILOT", "bot_pilot_phones": ["5511970521647"]}


def _lead(**over):
    lead = {
        "phone": "5511970521647",
        "source": "landing-page",
        "created_at": AGORA,
        "updated_at": AGORA,
    }
    lead.update(over)
    return lead


class TestLeadNovo(unittest.TestCase):
    def test_lead_novo_da_landing_page_dispara(self):
        self.assertTrue(should_start_conversation(_lead(), CLINICA, agora=AGORA))

    def test_lead_recorrente_nao_dispara(self):
        # caiu em UPDATE no upsert: já existia antes
        lead = _lead(created_at=AGORA - timedelta(days=30))

        self.assertFalse(should_start_conversation(lead, CLINICA, agora=AGORA))


class TestOrigem(unittest.TestCase):
    def test_whatsapp_nao_dispara(self):
        self.assertFalse(should_start_conversation(_lead(source="whatsapp"), CLINICA, agora=AGORA))

    def test_harmonizacao_nao_dispara(self):
        self.assertFalse(should_start_conversation(_lead(source="harmonizacao"), CLINICA, agora=AGORA))


class TestIdade(unittest.TestCase):
    def test_lead_antigo_nao_dispara_mesmo_parecendo_novo(self):
        """A guarda que protege contra backfill.

        Um script que reprocessasse leads antigos criaria linhas com
        created_at == updated_at, passando pela primeira guarda. A idade barra.
        """
        antigo = AGORA - timedelta(hours=2)
        lead = _lead(created_at=antigo, updated_at=antigo)

        self.assertFalse(should_start_conversation(lead, CLINICA, agora=AGORA))

    def test_lead_de_um_minuto_atras_dispara(self):
        recente = AGORA - timedelta(minutes=1)
        lead = _lead(created_at=recente, updated_at=recente)

        self.assertTrue(should_start_conversation(lead, CLINICA, agora=AGORA))


class TestPolitica(unittest.TestCase):
    def test_fora_do_piloto_nao_dispara(self):
        self.assertFalse(should_start_conversation(_lead(phone="5511988887777"), CLINICA, agora=AGORA))

    def test_policy_off_nao_dispara(self):
        self.assertFalse(should_start_conversation(_lead(), {"bot_autoreply_policy": "OFF"}, agora=AGORA))

    def test_policy_leads_only_dispara_para_landing_page(self):
        clinica = {"bot_autoreply_policy": "LEADS_ONLY"}

        self.assertTrue(should_start_conversation(_lead(), clinica, agora=AGORA))


class TestEntradasInvalidas(unittest.TestCase):
    def test_lead_none(self):
        self.assertFalse(should_start_conversation(None, CLINICA, agora=AGORA))

    def test_clinica_none(self):
        self.assertFalse(should_start_conversation(_lead(), None, agora=AGORA))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_outbound_guards.py -v`
Expected: FAIL com `ImportError: cannot import name 'should_start_conversation'`

- [ ] **Step 4: Implementar**

Adicionar em `scheduler/src/functions/lead/create.py`:

```python
from datetime import datetime, timedelta, timezone

SOURCES_COM_CONTATO_ATIVO = {"landing-page"}
# Janela máxima entre a criação do lead e o disparo. É a guarda que impede que
# qualquer reprocessamento ou backfill dispare mensagem para lead antigo: mesmo
# que created_at == updated_at, um lead de horas atrás não é abordado.
IDADE_MAXIMA_MINUTOS = 10


def should_start_conversation(lead, clinic, *, agora=None) -> bool:
    """O bot deve abrir conversa com este lead?

    Quatro guardas independentes. Todas precisam passar, porque a mensagem chega
    no WhatsApp de uma pessoa real e não tem desfazer.
    """
    if not lead or not clinic:
        return False

    if lead.get("source") not in SOURCES_COM_CONTATO_ATIVO:
        return False

    # Lead recorrente cai em UPDATE no upsert: não é primeiro contato.
    if lead.get("created_at") != lead.get("updated_at"):
        return False

    criado = lead.get("created_at")
    if criado is None:
        return False
    if criado.tzinfo is None:
        criado = criado.replace(tzinfo=timezone.utc)
    referencia = agora or datetime.now(timezone.utc)
    if referencia - criado > timedelta(minutes=IDADE_MAXIMA_MINUTOS):
        return False

    from src.services.bot_policy import should_bot_reply

    return should_bot_reply(clinic, {}, lead.get("phone") or "")


def _enfileira_contato_ativo(log_prefix, db, lead, clinic_id):
    """Enfileira a abertura de conversa. Nunca propaga erro: capturar o lead vale mais."""
    try:
        clinics = db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            logger.warning(f"{log_prefix} Clínica {clinic_id} não encontrada, sem contato ativo")
            return
        clinic = clinics[0]

        if not should_start_conversation(lead, clinic):
            logger.info(f"{log_prefix} Contato ativo não elegível para este lead")
            return

        from src.services.outbound_queue import OutboundQueueService

        item = OutboundQueueService().enqueue(
            clinic_id,
            lead["phone"],
            lead_id=str(lead["id"]),
            business_hours=clinic.get("business_hours") or {},
        )
        if item:
            db.execute_query(
                "UPDATE scheduler.leads SET first_contact_status = 'QUEUED', updated_at = NOW() "
                "WHERE id = %s::uuid",
                (str(lead["id"]),),
            )
            logger.info(
                f"{log_prefix} Contato ativo enfileirado: {item['messageId']} "
                f"sai a partir de {item['sendAfter']}"
            )
    except Exception as e:
        logger.error(f"{log_prefix} Falha ao enfileirar contato ativo: {e}", exc_info=True)
```

Chamar logo antes do `return http_response(201, ...)`, dentro do ramo em que `lead` não é nulo:

```python
            _enfileira_contato_ativo(log_prefix, db, lead, body["clinicId"])
```

Adicionar à `iamRoleStatements` de `CreateLead` em `sls/functions/lead/interface.yml`:

```yaml
    - Effect: Allow
      Action:
        - dynamodb:PutItem
      Resource:
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-outbound-queue"
```

- [ ] **Step 5: Rodar os testes**

Run: `cd scheduler && python -m pytest tests/unit -q`
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add scheduler/src/functions/lead/create.py scheduler/src/scripts/setup_database.py \
        scheduler/sls/functions/lead/interface.yml scheduler/tests/unit/test_outbound_guards.py
git commit -m "feat(scheduler): abre conversa com lead novo, com quatro guardas anti-disparo"
```

---

### Task 7: Ativar o piloto

**Files:** nenhum. É operação.

- [ ] **Step 1: Rodar as migrations**

```bash
cd scheduler && python -m src.scripts.setup_database
```

- [ ] **Step 2: Conferir que ninguém mais foi afetado**

```sql
SELECT clinic_id, bot_autoreply_policy, bot_pilot_phones, use_agent, bot_paused
FROM scheduler.clinics;
```

Esperado: as três clínicas com `bot_autoreply_policy = 'ALL'` (o default) e `bot_pilot_phones = {}`. A `clinicadorods-da7b62` precisa continuar exatamente como estava.

- [ ] **Step 3: Configurar a Essência para o piloto**

```sql
UPDATE scheduler.clinics SET
    bot_autoreply_policy = 'PILOT',
    bot_pilot_phones = ARRAY['5511970521647'],
    use_agent = TRUE,
    bot_paused = FALSE
WHERE clinic_id = 'clinicaessenciaestetica-9668a4';
```

A ordem importa: `bot_autoreply_policy` tem de estar em `PILOT` **antes** de `bot_paused` virar `FALSE`. Se `bot_paused` cair primeiro, existe uma janela em que o bot responde todo mundo, porque o default da política é `ALL`.

- [ ] **Step 4: Deploy**

```bash
cd scheduler && npx serverless deploy --stage prod --aws-profile dev-andre
```

- [ ] **Step 5: Testar o cenário A**

Do número `+55 11 97052-1647`, mandar "oi" no WhatsApp da clínica. Esperado: o bot responde com as boas-vindas do prompt e pergunta as áreas.

De qualquer outro número, mandar "oi". Esperado: **nenhuma resposta automática**, e a mensagem aparecendo no painel de conversas.

- [ ] **Step 6: Testar o cenário B**

```bash
curl -X POST "$API/leads" -H "x-api-key: $INTAKE_KEY" -H "content-type: application/json" \
  -d '{"clinicId":"clinicaessenciaestetica-9668a4","phone":"5511970521647",
       "name":"Teste Piloto","source":"landing-page","gclid":"teste-piloto-1"}'
```

Esperado: item `PENDING` na `outbound-queue`, e na próxima execução do cron (até 15 min, dentro do horário comercial) o bot abre a conversa sozinho.

Conferir também que um lead de outro telefone **não** entra na fila.

---

# FASE 2 — Todos os leads de landing-page

Só começa depois que o piloto rodar com conversa real de ponta a ponta nos dois cenários.

---

### Task 8: Marcar a conversa como elegível

**Files:**
- Modify: `scheduler/src/functions/outbound/processor.py`
- Modify: `scheduler/src/functions/webhook/handler.py`
- Test: `scheduler/tests/unit/test_bot_policy.py` (estender)

Com `LEADS_ONLY`, o bot só responde conversas com `bot_enabled=true` na sessão. Essa marca precisa nascer nos dois cenários.

- [ ] **Step 1: Marcar no cenário B (dispatcher)**

Em `outbound/processor.py`, após `queue.mark_sent`, gravar a marca na sessão:

```python
            _marca_sessao_elegivel(clinic_id, phone, item.get("leadId"))
```

E a função no mesmo arquivo:

```python
def _marca_sessao_elegivel(clinic_id, phone, lead_id):
    """Marca a conversa como elegível para resposta automática.

    Usa UpdateExpression em vez de put_item: o ConversationAgent acabou de
    gravar a sessão com o histórico, e um put sobrescreveria esse histórico.
    """
    import os

    import boto3

    tabela = boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"])
    tabela.update_item(
        Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"},
        UpdateExpression="SET bot_enabled = :t, lead_id = :l",
        ExpressionAttributeValues={":t": True, ":l": lead_id},
    )
```

> **Atenção:** confira o formato de `pk`/`sk` em `_load_session`/`_save_session` de
> `conversation_agent.py` e use exatamente o mesmo. Divergir aqui faz a marca
> nunca ser encontrada, e o bot silenciosamente para de responder.

- [ ] **Step 2: Marcar no cenário A (webhook)**

Quando chega mensagem de um telefone que tem lead de `landing-page`, a conversa também é elegível. Em `webhook/handler.py`, antes de aplicar a política:

```python
        if not session.get("bot_enabled"):
            leads = db.execute_query(
                "SELECT id FROM scheduler.leads WHERE clinic_id = %s AND phone = %s "
                "AND source = 'landing-page' LIMIT 1",
                (clinic_id, incoming.phone),
            )
            if leads:
                session["bot_enabled"] = True
                _save_session(_get_sessions_table(), clinic_id, incoming.phone, session)
```

- [ ] **Step 3: Validar a suíte**

Run: `cd scheduler && python -m pytest tests/unit -q`
Expected: todos passando.

- [ ] **Step 4: Commit**

```bash
git add scheduler/src/functions/outbound/processor.py scheduler/src/functions/webhook/handler.py
git commit -m "feat(scheduler): marca conversa de lead da landing page como elegível"
```

---

### Task 9: Ligar e desligar o bot na conversa pelo painel

**Files:**
- Create: `scheduler/src/functions/attendant/bot_toggle.py`
- Modify: `scheduler/sls/functions/attendant/interface.yml`
- Modify: `frontend/src/services/bot.service.ts`
- Modify: `frontend/src/pages/bot/`

**Interfaces:**
- Produces: `POST /clinics/{clinicId}/conversations/{phone}/bot`, body `{"enabled": bool}`.

Com `LEADS_ONLY`, uma conversa que não veio de lead nasce sem resposta automática. Este endpoint é como a clínica ativa o bot manualmente numa conversa que julgue valer.

- [ ] **Step 1: Implementar o handler**

```python
"""Liga ou desliga a resposta automática do bot numa conversa específica."""
import logging
import os

import boto3

from src.utils.http import http_response, parse_body, require_api_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    try:
        _, error_response = require_api_key(event)
        if error_response:
            return error_response

        params = event.get("pathParameters") or {}
        clinic_id, phone = params.get("clinicId"), params.get("phone")
        if not clinic_id or not phone:
            return http_response(400, {"status": "ERROR", "message": "clinicId e phone são obrigatórios"})

        body = parse_body(event) or {}
        if "enabled" not in body:
            return http_response(400, {"status": "ERROR", "message": "Campo obrigatorio: enabled"})
        enabled = bool(body["enabled"])

        boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"]).update_item(
            Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"},
            UpdateExpression="SET bot_enabled = :enabled",
            ExpressionAttributeValues={":enabled": enabled},
        )

        logger.info(f"[BotToggle] bot_enabled={enabled} para {clinic_id}/{phone}")
        return http_response(200, {"status": "SUCCESS", "bot_enabled": enabled})

    except Exception as e:
        logger.error(f"[BotToggle] Erro: {e}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
```

Declarar em `sls/functions/attendant/interface.yml`, copiando o bloco de `iamRoleStatements` de outra função que já acessa `conversation-sessions`, com:

```yaml
  events:
    - http:
        path: clinics/{clinicId}/conversations/{phone}/bot
        method: post
        cors: true
```

- [ ] **Step 2: Expor no service do frontend**

Em `frontend/src/services/bot.service.ts`:

```typescript
  setConversationBot(clinicId: string, phone: string, enabled: boolean) {
    return api
      .post<{ status: string; bot_enabled: boolean }>(
        `/clinics/${clinicId}/conversations/${phone}/bot`,
        { enabled },
      )
      .then((r) => r.data)
  },
```

- [ ] **Step 3: Adicionar o controle na conversa**

Na tela de conversa em `frontend/src/pages/bot/`, incluir um toggle que chama `setConversationBot` via mutation do TanStack Query, invalidando a query da conversa no `onSuccess`. Seguir `frontend/CLAUDE.md`: named export, 4 estados tratados, `clsx` para variantes, alvo de toque de 44px, transição de 100-150ms.

Estados visíveis: **Bot ativo** e **Bot pausado**. Quando a política da clínica for `ALL`, o toggle aparece desabilitado com a explicação de que a clínica responde todas as conversas — senão o usuário desliga e nada acontece.

- [ ] **Step 4: Validar**

Run: `cd scheduler && python -m pytest tests/unit -q`
Run: `cd frontend && npm run lint && npm run build`
Expected: tudo passando, zero warnings.

- [ ] **Step 5: Commit**

```bash
git add scheduler/src/functions/attendant/bot_toggle.py scheduler/sls/functions/attendant/interface.yml \
        frontend/src/services/bot.service.ts frontend/src/pages/bot/
git commit -m "feat: liga/desliga o bot por conversa pelo painel"
```

---

### Task 10: Estado da conversa no lead e no painel

**Files:**
- Modify: `scheduler/src/functions/webhook/handler.py`
- Modify: `scheduler/src/functions/lead/list.py`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/pages/leads/LeadsPage.tsx`

`first_contact_at` é "falamos com ele"; `conversation_started_at` é "ele respondeu". Sem separar, não dá para medir a taxa de resposta da abordagem.

- [ ] **Step 1: Marcar a resposta do lead no webhook**

Em `webhook/handler.py`, ao processar mensagem recebida:

```python
        db.execute_query(
            "UPDATE scheduler.leads SET conversation_started_at = COALESCE(conversation_started_at, NOW()), "
            "updated_at = NOW() WHERE clinic_id = %s AND phone = %s AND conversation_started_at IS NULL",
            (clinic_id, incoming.phone),
        )
```

O `COALESCE` com o filtro `IS NULL` garante que só a primeira resposta conta, e que reprocessar o webhook não sobrescreve a data original.

- [ ] **Step 2: Expor no ListLeads**

Incluir `first_contact_status`, `first_contact_at` e `conversation_started_at` no `SELECT` de `lead/list.py` e no dicionário serializado.

- [ ] **Step 3: Estender o tipo no frontend**

Em `frontend/src/types/index.ts`, no tipo `Lead`:

```typescript
  first_contact_status?: 'QUEUED' | 'SENT' | 'FAILED' | null
  first_contact_at?: string | null
  conversation_started_at?: string | null
```

- [ ] **Step 4: Coluna e correções na tela**

Em `LeadsPage.tsx`, coluna **Conversa**:

```typescript
function ConversationBadge({ lead }: { lead: Lead }) {
  if (lead.conversation_started_at) return <Badge variant="success">Respondeu</Badge>
  if (lead.first_contact_status === 'SENT') return <Badge variant="neutral">Contatado</Badge>
  if (lead.first_contact_status === 'QUEUED') return <Badge variant="warning">Na fila</Badge>
  if (lead.first_contact_status === 'FAILED') return <Badge variant="danger">Falhou</Badge>
  return <Badge variant="neutral">Sem contato</Badge>
}
```

Corrigir também a cópia, que hoje descreve o bot do WhatsApp e não a landing page:
- subtítulo → `"Leads capturados pela landing page e pelo WhatsApp"`
- estado vazio → `"Leads aparecem quando alguém preenche o formulário da landing page ou chama no WhatsApp."`

E o KPI de conversão, que divide `leads.filter(...)` (página carregada) por `data.total` (total do servidor) e fica errado em silêncio quando passar de 100 leads:

```typescript
  const conversionRate = leads.length > 0 ? Math.round((bookedCount / leads.length) * 100) : 0
```

- [ ] **Step 5: Validar**

Run: `cd scheduler && python -m pytest tests/unit -q`
Run: `cd frontend && npm run lint && npm run build && npm run test`

- [ ] **Step 6: Commit**

```bash
git add scheduler/src/functions/webhook/handler.py scheduler/src/functions/lead/list.py \
        frontend/src/types/index.ts frontend/src/pages/leads/LeadsPage.tsx
git commit -m "feat: rastreia contato ativo e resposta do lead no painel"
```

---

### Task 11: Virar a chave para todos os leads

**Files:** nenhum. É operação.

- [ ] **Step 1: Conferir o estado da fila antes**

```sql
SELECT COUNT(*) FROM scheduler.leads
WHERE clinic_id = 'clinicaessenciaestetica-9668a4'
  AND source = 'landing-page' AND created_at > NOW() - INTERVAL '10 minutes';
```

Se isso devolver mais que 1 ou 2, **não vire a chave agora**: significa que há leads recentes que passariam pela guarda de idade e seriam abordados de uma vez.

- [ ] **Step 2: Trocar a política**

```sql
UPDATE scheduler.clinics
SET bot_autoreply_policy = 'LEADS_ONLY', bot_pilot_phones = '{}'
WHERE clinic_id = 'clinicaessenciaestetica-9668a4';
```

Nenhum lead antigo é abordado: a fila só é alimentada pelo `POST /leads` no momento da criação, e a guarda de idade rejeita qualquer coisa com mais de 10 minutos. Não existe caminho no código que enfileire lead existente.

- [ ] **Step 3: Acompanhar os primeiros dias**

Com volume baixo (cerca de 1 lead por dia), acompanhar item a item:

```sql
SELECT name, phone, created_at, first_contact_status, first_contact_at, conversation_started_at
FROM scheduler.leads
WHERE clinic_id = 'clinicaessenciaestetica-9668a4' AND created_at > NOW() - INTERVAL '3 days'
ORDER BY created_at DESC;
```

- [ ] **Step 4: Documentar**

Em `scheduler/README.md`, seção descrevendo as quatro políticas, os dois cenários de chegada, a fila com seu limite de taxa e o ciclo `QUEUED → SENT → resposta`.

Em `CLAUDE.md`, adicionar `outbound-queue` às tabelas DynamoDB e `bot_policy.py`, `business_hours.py`, `outbound_queue.py` aos services.

---

## Riscos

**Disparo indevido para lead antigo.** É o risco de maior dano, porque atinge pessoas reais com conversa em andamento e não tem desfazer. Mitigado por quatro guardas independentes, pela ausência de qualquer script de backfill no plano, e pelo fato de a fila só ser alimentada na criação do lead. A Task 11 ainda checa quantos leads recentes existem antes de virar a chave.

**Bloqueio do número no z-api.** Provider não-oficial, linha compartilhada com os atendentes: um bloqueio derruba o atendimento inteiro, não só o bot. Mitigado por 1 envio a cada 15 minutos, janela de horário comercial e opt-in claro (a pessoa preencheu formulário minutos antes). O piloto da Fase 1, com um único telefone, é o primeiro teste real disso.

**Horário comercial atrasa o primeiro contato.** Com seg-sex 07:15-21:00, um lead de sábado 06:45 espera até segunda — quase 49 horas. Dos 7 leads analisados em agosto, só 2 chegaram dentro da janela. O plano respeita o que está cadastrado; ampliar a janela de mensageria é decisão do dono.

**Supressão silenciosa.** Com `PILOT` ou `LEADS_ONLY`, quem não é elegível não recebe nada e nada sinaliza isso no WhatsApp. A partir da Task 2 a mensagem passa a ser registrada e aparece no painel, o que é a mitigação — mas depende de alguém olhar.

## Fora de escopo

- **Correção dos horários da clínica** (operação, não código).
- **CPF, data de nascimento e e-mail** no cadastro: `patients` não tem essas colunas e `book_appointment` não as aceita. Pedir e descartar seria pior que não pedir.
- **Ligar `booked` a agendamento real** — mesmo buraco de sinal do `revenue_real`, tratado na fase 0.5.
- **Reenvio automático em caso de falha.** O item fica `FAILED` e visível; retentativa automática contra um provider que pode estar bloqueando é o que agrava um bloqueio.
- **FAQ `PAIN`** afirma "é o laser mais indolor do mercado", superlativo que o posicionamento manda evitar. É conteúdo da clínica, corrigível pelo painel.
