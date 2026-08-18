# Atendimento automático de leads da landing page — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quando um lead preenche o formulário da landing page, o bot LLM inicia a conversa no WhatsApp automaticamente, dentro do horário comercial da clínica e sem risco de bloqueio — e o bot deixa de responder automaticamente qualquer outra conversa do número compartilhado.

**Architecture:** Uma fila de envio em DynamoDB, drenada por um dispatcher em cron de 15 minutos que envia no máximo uma mensagem por clínica por execução. O gatilho é o `POST /leads`, que enfileira o primeiro contato. A sessão da conversa nasce com o histórico do agente já semeado com a mensagem enviada e com uma marca de elegibilidade, que passa a ser a condição para o bot responder. A política de resposta automática vira opt-in por clínica, preservando o comportamento atual de quem já usa o bot.

**Tech Stack:** Python 3.11 (Lambda), DynamoDB, PostgreSQL (Supabase), Serverless Framework, React 19 + TanStack Query no painel.

## Global Constraints

- **O bot é LLM, não máquina de estados.** A clínica alvo roda com `use_agent = true`; o `ConversationEngine` legado não recebe nenhuma alteração neste plano.
- **Nenhuma mudança pode desligar o bot de quem já usa.** `clinicadorods-da7b62` está hoje com `use_agent=true` e `bot_paused=false`, respondendo todas as conversas. Toda inversão de comportamento entra como opt-in por clínica.
- **O `POST /leads` nunca pode falhar por causa da mensageria.** Capturar o lead é mais importante que enviar a mensagem: falha ao enfileirar é logada e engolida, a resposta segue 201.
- **Limite de 1 envio a cada 15 minutos por clínica.** É a proteção contra bloqueio do número no z-api, que é provider não-oficial e compartilhado com os atendentes humanos.
- **Migrations idempotentes** na lista `MIGRATIONS` de `scheduler/src/scripts/setup_database.py`, com `IF NOT EXISTS` (regra do `CLAUDE.md`).
- **Logging com prefixo correlacionável**, seguindo o padrão já usado em `lead/create.py`: `[<Componente>][req:<id>]`.
- **Docstrings e comentários em português**; nomes de código em inglês.
- **Nunca usar travessão (`—`) em texto novo.** Usar hífen simples.
- Rodar `cd scheduler && python -m pytest tests/unit -q` antes de cada commit.

## Pendências assumidas (fora deste plano)

- **O template do bot (`AI_SYSTEM_PROMPT`) fica para outro commit.** Hoje a Essência tem **zero** registros em `message_templates`. Este plano cria o caminho; o conteúdo que quebra objeção e gera desejo entra depois. A Task 4 usa uma mensagem de primeiro contato configurável com um default explícito.
- **Os horários da clínica serão corrigidos pelo dono depois.** Hoje `business_hours` é seg-sex 07:15-21:00, sem sábado nem domingo, e 5 dos 7 leads recentes chegaram fora dessa janela. A fila respeita o que estiver cadastrado; corrigir o cadastro é operação, não código.
- **`booked` continua sem sinal confiável.** Este plano passa a registrar `conversation_started_at`, que é observável. Ligar lead a agendamento real é o mesmo buraco do `revenue_real` e fica para a fase 0.5.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `scheduler/src/services/business_hours.py` | **Novo.** Funções puras: a clínica está aberta agora? qual o próximo instante em que abre? |
| `scheduler/src/services/outbound_queue.py` | **Novo.** Enfileirar, listar pendentes elegíveis, marcar enviado/falho. Única porta para a tabela. |
| `scheduler/sls/resources/dynamodb/outbound-queue-table.yml` | **Novo.** Tabela + GSI `status-sendAfter-index`, espelhando `scheduled-reminders`. |
| `scheduler/src/functions/outbound/processor.py` | **Novo.** Dispatcher em cron: drena a fila respeitando horário e limite de taxa. |
| `scheduler/sls/functions/outbound/interface.yml` | **Novo.** Declaração do dispatcher com `rate(15 minutes)`. |
| `scheduler/src/functions/lead/create.py` | **Modificar.** Enfileira o primeiro contato quando o lead é novo e veio da landing page. |
| `scheduler/src/services/conversation_agent.py` | **Modificar.** Respeita `bot_enabled`; reconstrói histórico do `MessageEvents` quando a sessão está vazia. |
| `scheduler/src/functions/webhook/handler.py` | **Modificar.** Política de resposta automática por clínica. |
| `scheduler/src/functions/attendant/bot_toggle.py` | **Novo.** `POST /clinics/{clinicId}/conversations/{phone}/bot` para ligar/desligar pelo painel. |
| `scheduler/src/scripts/setup_database.py` | **Modificar.** Colunas novas em `clinics` e `leads`. |
| `frontend/src/services/leads.service.ts` + `pages/leads/LeadsPage.tsx` | **Modificar.** Coluna de status da conversa. |
| `frontend/src/pages/bot/` | **Modificar.** Botão de ligar/desligar o bot na conversa. |

Testes em `scheduler/tests/unit/test_business_hours.py`, `test_outbound_queue.py`, `test_bot_eligibility.py`.

---

# PARTE A — Fila de envio

Entregável isolado: ao fim da Task 3 existe uma fila funcional que respeita horário comercial e limite de taxa, drenada por cron. Nada ainda a alimenta automaticamente.

---

### Task 1: Janela de horário comercial

**Files:**
- Create: `scheduler/src/services/business_hours.py`
- Test: `scheduler/tests/unit/test_business_hours.py`

**Interfaces:**
- Consumes: o JSONB `clinics.business_hours`, no formato `{"mon": {"start": "07:15", "end": "21:00"}, ...}`. Dias ausentes significam fechado.
- Produces:
  - `is_open(business_hours: dict, moment: datetime) -> bool`
  - `next_opening(business_hours: dict, moment: datetime) -> datetime | None` — devolve `moment` se já estiver aberto; `None` se a clínica não tem nenhum dia configurado.

Ambas operam em horário local da clínica (America/Sao_Paulo, via `pytz`, que já é dependência declarada).

- [ ] **Step 1: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_business_hours.py
"""Janela de envio a partir do horário comercial cadastrado pela clínica.

Os casos usam o horário real da Essência (seg-sex 07:15-21:00, sem fim de semana)
porque é ele que expõe o comportamento que importa: 5 dos 7 leads recentes
chegaram fora dessa janela, então o salto para a próxima abertura é o caminho
comum, não a exceção.
"""
import os
import unittest
from datetime import datetime

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.business_hours import is_open, next_opening

TZ = pytz.timezone("America/Sao_Paulo")
ESSENCIA = {
    "mon": {"start": "07:15", "end": "21:00"},
    "tue": {"start": "07:15", "end": "21:00"},
    "wed": {"start": "07:15", "end": "21:00"},
    "thu": {"start": "07:15", "end": "21:00"},
    "fri": {"start": "07:15", "end": "21:00"},
}


def _local(ano, mes, dia, hora, minuto):
    return TZ.localize(datetime(ano, mes, dia, hora, minuto))


class TestIsOpen(unittest.TestCase):
    def test_dentro_da_janela(self):
        # segunda 17/08/2026, 16:46
        self.assertTrue(is_open(ESSENCIA, _local(2026, 8, 17, 16, 46)))

    def test_antes_da_abertura(self):
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 17, 7, 0)))

    def test_exatamente_na_abertura_esta_aberto(self):
        self.assertTrue(is_open(ESSENCIA, _local(2026, 8, 17, 7, 15)))

    def test_exatamente_no_fechamento_esta_fechado(self):
        # 21:00 é o instante em que fecha, não o último minuto aberto
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 17, 21, 0)))

    def test_dia_nao_configurado_esta_fechado(self):
        # sábado 15/08/2026
        self.assertFalse(is_open(ESSENCIA, _local(2026, 8, 15, 10, 0)))

    def test_sem_nenhum_dia_configurado(self):
        self.assertFalse(is_open({}, _local(2026, 8, 17, 10, 0)))


class TestNextOpening(unittest.TestCase):
    def test_ja_aberto_devolve_o_proprio_momento(self):
        momento = _local(2026, 8, 17, 16, 46)

        self.assertEqual(next_opening(ESSENCIA, momento), momento)

    def test_antes_da_abertura_salta_para_a_abertura_do_mesmo_dia(self):
        resultado = next_opening(ESSENCIA, _local(2026, 8, 17, 6, 0))

        self.assertEqual(resultado, _local(2026, 8, 17, 7, 15))

    def test_depois_do_fechamento_salta_para_o_dia_seguinte(self):
        # quarta 12/08/2026 23:46 (caso real do lead Guiguilson)
        resultado = next_opening(ESSENCIA, _local(2026, 8, 12, 23, 46))

        self.assertEqual(resultado, _local(2026, 8, 13, 7, 15))

    def test_sabado_salta_para_segunda(self):
        # sábado 15/08/2026 06:45 (caso real do lead Fernanda)
        resultado = next_opening(ESSENCIA, _local(2026, 8, 15, 6, 45))

        self.assertEqual(resultado, _local(2026, 8, 17, 7, 15))

    def test_domingo_salta_para_segunda(self):
        # domingo 16/08/2026 19:02 (caso real do lead Amanda)
        resultado = next_opening(ESSENCIA, _local(2026, 8, 16, 19, 2))

        self.assertEqual(resultado, _local(2026, 8, 17, 7, 15))

    def test_sem_nenhum_dia_configurado_devolve_none(self):
        self.assertIsNone(next_opening({}, _local(2026, 8, 17, 10, 0)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_business_hours.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'src.services.business_hours'`

- [ ] **Step 3: Implementar**

```python
"""Janela de envio derivada do horário comercial cadastrado pela clínica.

Funções puras, sem I/O. O formato de `business_hours` é o JSONB da tabela
`scheduler.clinics`: {"mon": {"start": "07:15", "end": "21:00"}, ...}. Dia ausente
significa fechado, que é como sábado e domingo aparecem hoje.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional

import pytz

CLINIC_TZ = pytz.timezone("America/Sao_Paulo")

# datetime.weekday(): 0 = segunda
_DIAS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DIAS_NA_SEMANA = 7


def _janela_do_dia(business_hours: Dict, momento: datetime):
    """(abertura, fechamento) do dia de `momento`, ou None se fechado."""
    dia = business_hours.get(_DIAS[momento.weekday()])
    if not dia or not dia.get("start") or not dia.get("end"):
        return None

    abre_h, abre_m = (int(p) for p in dia["start"].split(":"))
    fecha_h, fecha_m = (int(p) for p in dia["end"].split(":"))

    base = momento.replace(hour=0, minute=0, second=0, microsecond=0)
    abertura = base.replace(hour=abre_h, minute=abre_m)
    fechamento = base.replace(hour=fecha_h, minute=fecha_m)
    return abertura, fechamento


def is_open(business_hours: Dict, moment: datetime) -> bool:
    """A clínica está atendendo neste instante?

    A abertura é inclusiva e o fechamento exclusivo: às 21:00 em ponto já está
    fechada, porque 21:00 é o instante em que encerra.
    """
    janela = _janela_do_dia(business_hours or {}, moment)
    if janela is None:
        return False
    abertura, fechamento = janela
    return abertura <= moment < fechamento


def next_opening(business_hours: Dict, moment: datetime) -> Optional[datetime]:
    """Primeiro instante a partir de `moment` em que a clínica está aberta.

    Devolve o próprio `moment` se já estiver aberta, e None se nenhum dia da
    semana estiver configurado (senão a busca não terminaria).
    """
    business_hours = business_hours or {}
    if not any(business_hours.get(dia) for dia in _DIAS):
        return None

    if is_open(business_hours, moment):
        return moment

    # Hoje ainda pode abrir mais tarde; a partir de amanhã, sempre a abertura.
    janela = _janela_do_dia(business_hours, moment)
    if janela is not None and moment < janela[0]:
        return janela[0]

    candidato = moment
    for _ in range(_DIAS_NA_SEMANA):
        candidato = (candidato + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
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
git commit -m "feat(scheduler): janela de envio a partir do horário comercial da clínica"
```

---

### Task 2: Tabela e serviço da fila de envio

**Files:**
- Create: `scheduler/sls/resources/dynamodb/outbound-queue-table.yml`
- Create: `scheduler/src/services/outbound_queue.py`
- Modify: `scheduler/serverless.yml` (registrar o resource e a env var)
- Test: `scheduler/tests/unit/test_outbound_queue.py`

**Interfaces:**
- Consumes: `next_opening` da Task 1.
- Produces, em `OutboundQueueService`:
  - `enqueue(clinic_id, phone, content, *, lead_id=None, kind="FIRST_CONTACT", business_hours=None, now=None) -> dict` — calcula `sendAfter` pela próxima abertura e grava com `status="PENDING"`. Devolve o item.
  - `pending_due(now_iso: str, limit: int = 50) -> list` — itens `PENDING` com `sendAfter <= now_iso`, mais antigos primeiro.
  - `mark_sent(message_id, pk, sk)`
  - `mark_failed(message_id, pk, sk, error)`

Formato do item, espelhando `scheduled-reminders`:

```
pk        = "CLINIC#{clinic_id}"
sk        = "OUT#{sendAfter}#{messageId}"
messageId, clinicId, phone, leadId, kind, content
status    = PENDING | SENT | FAILED
sendAfter = ISO-8601 UTC, o instante a partir do qual pode sair
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

Registrar em `scheduler/serverless.yml` junto dos outros resources de DynamoDB e adicionar a env var `OUTBOUND_QUEUE_TABLE: ${self:custom.resourcePrefix}-outbound-queue` no bloco `provider.environment`, seguindo exatamente o padrão já usado por `SCHEDULED_REMINDERS_TABLE`.

- [ ] **Step 2: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_outbound_queue.py
"""Fila de envio: cálculo do instante de saída e transições de status.

O DynamoDB é substituído por um fake em memória que registra as chamadas, para
o teste cobrir a regra de negócio (quando a mensagem pode sair) sem depender de
infraestrutura.
"""
import os
import unittest
from datetime import datetime

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")

TZ = pytz.timezone("America/Sao_Paulo")
ESSENCIA = {
    "mon": {"start": "07:15", "end": "21:00"},
    "tue": {"start": "07:15", "end": "21:00"},
    "wed": {"start": "07:15", "end": "21:00"},
    "thu": {"start": "07:15", "end": "21:00"},
    "fri": {"start": "07:15", "end": "21:00"},
}


class FakeTable:
    def __init__(self):
        self.items = []
        self.updates = []

    def put_item(self, Item):
        self.items.append(Item)

    def update_item(self, **kwargs):
        self.updates.append(kwargs)


def _service(monkey_table):
    from src.services.outbound_queue import OutboundQueueService

    service = OutboundQueueService.__new__(OutboundQueueService)
    service.table = monkey_table
    return service


class TestEnqueue(unittest.TestCase):
    def test_dentro_do_horario_sai_imediatamente(self):
        table = FakeTable()
        service = _service(table)
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))

        item = service.enqueue(
            "clinica-x", "5511999999999", "Olá", business_hours=ESSENCIA, now=agora
        )

        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(item["sendAfter"], "2026-08-17T19:46:00Z")  # 16:46 BRT = 19:46 UTC

    def test_fora_do_horario_espera_a_proxima_abertura(self):
        table = FakeTable()
        service = _service(table)
        # sábado 06:45, caso real do lead Fernanda
        agora = TZ.localize(datetime(2026, 8, 15, 6, 45))

        item = service.enqueue(
            "clinica-x", "5511999999999", "Olá", business_hours=ESSENCIA, now=agora
        )

        # segunda 07:15 BRT = 10:15 UTC
        self.assertEqual(item["sendAfter"], "2026-08-17T10:15:00Z")

    def test_sem_horario_configurado_nao_enfileira(self):
        table = FakeTable()
        service = _service(table)
        agora = TZ.localize(datetime(2026, 8, 17, 10, 0))

        item = service.enqueue("clinica-x", "5511999999999", "Olá", business_hours={}, now=agora)

        self.assertIsNone(item)
        self.assertEqual(table.items, [])

    def test_grava_lead_id_e_chaves(self):
        table = FakeTable()
        service = _service(table)
        agora = TZ.localize(datetime(2026, 8, 17, 16, 46))

        item = service.enqueue(
            "clinica-x", "5511999999999", "Olá",
            lead_id="lead-123", business_hours=ESSENCIA, now=agora,
        )

        self.assertEqual(item["leadId"], "lead-123")
        self.assertEqual(item["kind"], "FIRST_CONTACT")
        self.assertEqual(item["pk"], "CLINIC#clinica-x")
        self.assertTrue(item["sk"].startswith("OUT#2026-08-17T19:46:00Z#"))
        self.assertEqual(len(table.items), 1)


class TestTransicoes(unittest.TestCase):
    def test_mark_sent_atualiza_status(self):
        table = FakeTable()
        service = _service(table)

        service.mark_sent("msg-1", "CLINIC#c", "OUT#x#msg-1")

        self.assertEqual(len(table.updates), 1)
        self.assertIn("SENT", str(table.updates[0]))

    def test_mark_failed_registra_erro(self):
        table = FakeTable()
        service = _service(table)

        service.mark_failed("msg-1", "CLINIC#c", "OUT#x#msg-1", "timeout do provider")

        self.assertIn("timeout do provider", str(table.updates[0]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar o teste para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_outbound_queue.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'src.services.outbound_queue'`

- [ ] **Step 4: Implementar**

```python
"""Fila de mensagens ativas, drenada pelo dispatcher em cron.

Existe porque o disparo não pode ser síncrono ao cadastro do lead: precisa
respeitar o horário comercial da clínica e um limite de taxa que protege o
número contra bloqueio no provider.
"""
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
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
        content: str,
        *,
        lead_id: Optional[str] = None,
        kind: str = "FIRST_CONTACT",
        business_hours: Optional[Dict] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Dict]:
        """Enfileira uma mensagem para o próximo horário em que a clínica atende.

        Devolve None quando a clínica não tem nenhum dia configurado: sem janela
        não há quando enviar, e enfileirar criaria um item que nunca sai.
        """
        agora = now or datetime.now(timezone.utc)
        saida = next_opening(business_hours or {}, agora)
        if saida is None:
            logger.warning(
                f"[OutboundQueue] Clínica {clinic_id} sem horário comercial configurado, "
                f"mensagem não enfileirada"
            )
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
            "content": content,
            "status": "PENDING",
            "sendAfter": send_after,
            "attempts": 0,
            "createdAt": agora.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ttl": int(time.time()) + TTL_DIAS * 24 * 60 * 60,
        }
        self.table.put_item(Item=item)
        logger.info(
            f"[OutboundQueue] Mensagem {message_id} enfileirada para {clinic_id} "
            f"sair a partir de {send_after}"
        )
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

### Task 3: Dispatcher com limite de 1 envio a cada 15 minutos

**Files:**
- Create: `scheduler/src/functions/outbound/__init__.py`
- Create: `scheduler/src/functions/outbound/processor.py`
- Create: `scheduler/sls/functions/outbound/interface.yml`
- Modify: `scheduler/serverless.yml` (incluir o novo interface.yml)

**Interfaces:**
- Consumes: `OutboundQueueService` (Task 2), `is_open` (Task 1), `MessageTracker`, `get_provider`.
- Produces: `handler(event, context) -> dict` com `{"processed", "sent", "skipped", "failed"}`.

**Como o limite de taxa funciona:** o dispatcher roda a cada 15 minutos e envia **no máximo uma mensagem por clínica por execução**. Isso entrega exatamente 1 envio a cada 15 minutos por clínica sem precisar de contador distribuído nem lock — o próprio intervalo do cron é o limitador. A constante `MAX_ENVIOS_POR_CLINICA_POR_EXECUCAO = 1` deixa a regra explícita e ajustável.

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

Incluir esse arquivo na lista de `functions` do `scheduler/serverless.yml`, no mesmo formato dos demais.

- [ ] **Step 2: Implementar o dispatcher**

```python
"""Dispatcher da fila de envio ativo.

Roda a cada 15 minutos e envia no máximo uma mensagem por clínica por execução.
Esse limite é a proteção contra bloqueio do número: o provider é o z-api, que é
não-oficial, e a linha é compartilhada com os atendentes humanos, então um
bloqueio derruba a operação inteira e não só o bot.

O horário comercial é reconferido na hora do envio, e não só no enfileiramento:
a clínica pode ter mudado os horários depois que a mensagem entrou na fila.
"""
import logging
import uuid
from datetime import datetime, timezone

from src.providers.whatsapp_provider import get_provider
from src.services.business_hours import CLINIC_TZ, is_open
from src.services.db.postgres import PostgresService
from src.services.message_tracker import MessageTracker
from src.services.outbound_queue import OutboundQueueService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_ENVIOS_POR_CLINICA_POR_EXECUCAO = 1


def handler(event, context):
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

            # Reconferência: os horários podem ter mudado após o enfileiramento.
            if not is_open(clinic.get("business_hours") or {}, agora_utc.astimezone(CLINIC_TZ)):
                logger.info(f"{prefixo} Clínica {clinic_id} fechada agora, adiando {message_id}")
                skipped += 1
                continue

            content = item.get("content", "")
            conversation_id = f"{clinic_id}#{phone}"
            provider = get_provider(clinic)

            tracker.track_outbound(
                clinic_id=clinic_id, phone=phone, message_id=message_id,
                conversation_id=conversation_id, message_type="TEXT",
                content=content, status="QUEUED",
                metadata={"kind": item.get("kind"), "leadId": item.get("leadId")},
            )

            response = provider.send_text(phone, content)

            if response.success:
                tracker.track_outbound(
                    clinic_id=clinic_id, phone=phone, message_id=message_id,
                    conversation_id=conversation_id, message_type="TEXT",
                    content=content, status="SENT",
                    provider_message_id=response.provider_message_id,
                    provider_response=response.raw_response,
                )
                queue.mark_sent(message_id, item["pk"], item["sk"])
                enviados_por_clinica[clinic_id] = enviados_por_clinica.get(clinic_id, 0) + 1
                sent += 1
                logger.info(f"{prefixo} Mensagem {message_id} enviada para {phone}")
            else:
                tracker.track_outbound(
                    clinic_id=clinic_id, phone=phone, message_id=message_id,
                    conversation_id=conversation_id, message_type="TEXT",
                    content=content, status="FAILED",
                    metadata={"error": response.error},
                )
                queue.mark_failed(
                    message_id, item["pk"], item["sk"], response.error or "Erro desconhecido"
                )
                failed += 1
                logger.error(f"{prefixo} Falha ao enviar {message_id}: {response.error}")

        except Exception as e:
            logger.error(f"{prefixo} Erro ao processar {message_id}: {e}", exc_info=True)
            queue.mark_failed(message_id, item["pk"], item["sk"], str(e))
            failed += 1

    logger.info(
        f"{prefixo} Concluído: {len(pendentes)} pendentes, {sent} enviados, "
        f"{skipped} adiados, {failed} falhas"
    )
    return {"processed": len(pendentes), "sent": sent, "skipped": skipped, "failed": failed}
```

- [ ] **Step 3: Validar que a suíte segue verde**

Run: `cd scheduler && python -m pytest tests/unit -q`
Expected: todos passando.

- [ ] **Step 4: Commit**

```bash
git add scheduler/src/functions/outbound/ scheduler/sls/functions/outbound/interface.yml scheduler/serverless.yml
git commit -m "feat(scheduler): dispatcher da fila com limite de 1 envio a cada 15 minutos"
```

---

# PARTE B — Gatilho no lead e contexto do agente

---

### Task 4: Enfileirar o primeiro contato quando o lead entra

**Files:**
- Modify: `scheduler/src/scripts/setup_database.py` (coluna `first_contact_template` em `clinics`)
- Modify: `scheduler/src/functions/lead/create.py`
- Modify: `scheduler/sls/functions/lead/interface.yml` (permissão na tabela da fila)

**Interfaces:**
- Consumes: `OutboundQueueService.enqueue` (Task 2).
- Produces: efeito colateral no `POST /leads`. A resposta HTTP **não muda**.

Regras: só enfileira quando o lead é **novo** (`created_at == updated_at` no retorno do upsert) e `source` está em `SOURCES_COM_PRIMEIRO_CONTATO = {"landing-page"}`. Lead recorrente não recebe a saudação de novo.

- [ ] **Step 1: Adicionar a coluna de mensagem**

Em `setup_database.py`, na lista `MIGRATIONS`:

```python
    # Mensagem de primeiro contato disparada quando um lead da landing page entra.
    # O template completo do bot (AI_SYSTEM_PROMPT) é assunto separado; esta é só
    # a primeira mensagem, que precisa existir para a fila ter o que enviar.
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS first_contact_template TEXT",
```

E adicionar `first_contact_template` à lista `ALLOWED_FIELDS` de `scheduler/src/functions/clinic/update.py`, para o painel poder editar.

- [ ] **Step 2: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_first_contact_trigger.py
"""O cadastro de um lead da landing page enfileira a saudação; o resto não.

Cobre a regra de elegibilidade isolada do handler HTTP, que depende de banco e
API Gateway. O que importa aqui é quando enfileirar, não como responder.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")

from src.functions.lead.create import should_send_first_contact

DEFAULT = {"created_at": "2026-08-17T10:00:00", "updated_at": "2026-08-17T10:00:00"}


class TestShouldSendFirstContact(unittest.TestCase):
    def test_lead_novo_da_landing_page_recebe(self):
        self.assertTrue(should_send_first_contact({**DEFAULT, "source": "landing-page"}))

    def test_lead_recorrente_nao_recebe_de_novo(self):
        lead = {"source": "landing-page",
                "created_at": "2026-08-10T10:00:00", "updated_at": "2026-08-17T10:00:00"}

        self.assertFalse(should_send_first_contact(lead))

    def test_outra_origem_nao_recebe(self):
        self.assertFalse(should_send_first_contact({**DEFAULT, "source": "whatsapp"}))

    def test_lead_none_nao_recebe(self):
        self.assertFalse(should_send_first_contact(None))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar o teste para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_first_contact_trigger.py -v`
Expected: FAIL com `ImportError: cannot import name 'should_send_first_contact'`

- [ ] **Step 4: Implementar**

Adicionar em `scheduler/src/functions/lead/create.py`, após os helpers de máscara:

```python
SOURCES_COM_PRIMEIRO_CONTATO = {"landing-page"}

DEFAULT_FIRST_CONTACT = (
    "Olá! Seja muito bem-vinda à {clinic_name}. "
    "Você já fez depilação a laser antes?"
)


def should_send_first_contact(lead) -> bool:
    """Só lead novo e vindo da landing page recebe a saudação automática.

    Lead recorrente cai em UPDATE no upsert (created_at != updated_at) e não deve
    ser cumprimentado de novo a cada formulário preenchido.
    """
    if not lead:
        return False
    if lead.get("source") not in SOURCES_COM_PRIMEIRO_CONTATO:
        return False
    return lead.get("created_at") == lead.get("updated_at")


def _enqueue_first_contact(log_prefix, db, lead, clinic_id):
    """Enfileira a saudação. Nunca propaga erro: capturar o lead vale mais."""
    try:
        clinics = db.execute_query(
            "SELECT name, business_hours, first_contact_template "
            "FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            logger.warning(f"{log_prefix} Clínica {clinic_id} não encontrada, sem primeiro contato")
            return

        clinic = clinics[0]
        template = clinic.get("first_contact_template") or DEFAULT_FIRST_CONTACT
        content = template.replace("{clinic_name}", clinic.get("name") or "")

        from src.services.outbound_queue import OutboundQueueService

        item = OutboundQueueService().enqueue(
            clinic_id,
            lead["phone"],
            content,
            lead_id=str(lead["id"]),
            business_hours=clinic.get("business_hours") or {},
        )
        if item:
            logger.info(
                f"{log_prefix} Primeiro contato enfileirado: messageId={item['messageId']} "
                f"sendAfter={item['sendAfter']}"
            )
    except Exception as e:
        logger.error(f"{log_prefix} Falha ao enfileirar primeiro contato: {e}", exc_info=True)
```

E chamar logo antes do `return http_response(201, ...)`, dentro do `else` que já trata `lead` não-nulo:

```python
            if should_send_first_contact(lead):
                _enqueue_first_contact(log_prefix, db, lead, body["clinicId"])
```

Adicionar à `iamRoleStatements` de `CreateLead` em `scheduler/sls/functions/lead/interface.yml`:

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
git add scheduler/src/functions/lead/create.py scheduler/src/functions/clinic/update.py \
        scheduler/src/scripts/setup_database.py scheduler/sls/functions/lead/interface.yml \
        scheduler/tests/unit/test_first_contact_trigger.py
git commit -m "feat(scheduler): enfileira primeiro contato quando lead da landing page entra"
```

---

### Task 5: Contexto e histórico do agente

**Files:**
- Modify: `scheduler/src/services/conversation_agent.py`
- Modify: `scheduler/src/functions/outbound/processor.py` (semear a sessão após enviar)
- Test: `scheduler/tests/unit/test_agent_history.py`

**Interfaces:**
- Produces:
  - `ConversationAgent.rebuild_history_from_events(clinic_id, phone, limit=20) -> list` — reconstrói `agent_history` a partir do `MessageEvents` quando a sessão está vazia.
  - `seed_agent_session(sessions_table, clinic_id, phone, assistant_message, lead_id=None)` em `src/services/outbound_queue.py` — grava a mensagem enviada como primeiro turno `assistant` e marca `bot_enabled=True`.

Sem semear, o lead responde e o agente começa do zero: não sabe que já cumprimentou e repete a saudação por cima da própria mensagem.

- [ ] **Step 1: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_agent_history.py
"""Contexto do agente ao iniciar a conversa e ao retomar depois.

Dois cenários que hoje quebram: o agente não sabe que já enviou a saudação
ativa, e perde tudo se a sessão for esvaziada apesar de o histórico existir em
MessageEvents.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("OUTBOUND_QUEUE_TABLE", "test-outbound-queue")

from src.services.outbound_queue import build_seed_session


class TestSeedSession(unittest.TestCase):
    def test_saudacao_entra_como_turno_do_assistente(self):
        session = build_seed_session("Olá! Já fez depilação a laser antes?", lead_id="lead-1")

        self.assertEqual(session["agent_history"][0]["role"], "assistant")
        self.assertIn("depilação a laser", session["agent_history"][0]["content"])

    def test_sessao_semeada_nasce_com_bot_habilitado(self):
        session = build_seed_session("Olá!", lead_id="lead-1")

        self.assertTrue(session["bot_enabled"])
        self.assertEqual(session["mode"], "agent")
        self.assertEqual(session["lead_id"], "lead-1")


class TestRebuildHistory(unittest.TestCase):
    def test_converte_eventos_em_turnos(self):
        from src.services.conversation_agent import events_to_history

        eventos = [
            {"direction": "OUTBOUND", "content": "Olá!"},
            {"direction": "INBOUND", "content": "Oi, nunca fiz"},
            {"direction": "OUTBOUND", "content": "Perfeito, posso te explicar"},
        ]

        history = events_to_history(eventos)

        self.assertEqual(
            [turno["role"] for turno in history], ["assistant", "user", "assistant"]
        )
        self.assertEqual(history[1]["content"], "Oi, nunca fiz")

    def test_ignora_eventos_sem_conteudo(self):
        from src.services.conversation_agent import events_to_history

        history = events_to_history([{"direction": "INBOUND", "content": ""}])

        self.assertEqual(history, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_agent_history.py -v`
Expected: FAIL com `ImportError: cannot import name 'build_seed_session'`

- [ ] **Step 3: Implementar a semente**

Em `scheduler/src/services/outbound_queue.py`:

```python
def build_seed_session(assistant_message: str, lead_id: Optional[str] = None) -> Dict:
    """Sessão inicial de uma conversa aberta pelo bot.

    A mensagem enviada entra como primeiro turno `assistant` para o agente saber
    que já cumprimentou; sem isso ele recomeça a conversa por cima da própria
    saudação quando o lead responde.
    """
    return {
        "agent_history": [{"role": "assistant", "content": assistant_message}],
        "mode": "agent",
        "bot_enabled": True,
        "lead_id": lead_id,
        "state": "AGENT_ACTIVE",
    }
```

- [ ] **Step 4: Implementar a reconstrução de histórico**

Em `scheduler/src/services/conversation_agent.py`, no nível do módulo:

```python
def events_to_history(events: List[Dict]) -> List[Dict]:
    """Converte eventos de mensagem em turnos de conversa para o agente.

    Usado quando a sessão está sem `agent_history` mas o MessageEvents ainda tem
    a conversa (retenção de 90 dias). Só texto: blocos de tool_use não são
    reconstruídos, porque o resultado das ferramentas já está refletido no que
    foi dito.
    """
    history = []
    for event in events:
        content = (event.get("content") or "").strip()
        if not content:
            continue
        papel = "assistant" if event.get("direction") == "OUTBOUND" else "user"
        history.append({"role": papel, "content": content})
    return history
```

E no método `process_message`, trocar a linha que carrega o histórico por:

```python
        history = self._truncate_history(session.get("agent_history", []))
        if not history:
            history = self._truncate_history(
                self.rebuild_history_from_events(clinic_id, phone)
            )
```

Adicionando o método:

```python
    def rebuild_history_from_events(self, clinic_id, phone, limit=20):
        """Histórico a partir do MessageEvents quando a sessão está vazia."""
        try:
            events = self.message_tracker.get_conversation_messages(
                f"{clinic_id}#{phone}", limit=limit
            )
            return events_to_history(events)
        except Exception as e:
            logger.warning(f"[ConversationAgent] Falha ao reconstruir histórico de {phone}: {e}")
            return []
```

- [ ] **Step 5: Semear a sessão no dispatcher**

Em `scheduler/src/functions/outbound/processor.py`, no bloco de sucesso do envio (logo após `queue.mark_sent`), gravar a sessão semeada:

```python
                _seed_session(clinic_id, phone, content, item.get("leadId"))
```

E a função auxiliar no mesmo arquivo:

```python
def _seed_session(clinic_id, phone, content, lead_id):
    """Cria a sessão da conversa já com a saudação no histórico do agente."""
    import os

    import boto3

    from src.services.outbound_queue import build_seed_session

    table = boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"])
    session = build_seed_session(content, lead_id=lead_id)
    table.put_item(
        Item={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}", **session}
    )
```

> **Atenção ao formato das chaves:** confira `_load_session`/`_save_session` em
> `scheduler/src/services/conversation_agent.py` e use exatamente o mesmo `pk`/`sk`.
> Se divergir, o agente não encontra a sessão semeada e o efeito é o mesmo de não
> ter semeado.

- [ ] **Step 6: Rodar os testes**

Run: `cd scheduler && python -m pytest tests/unit -q`
Expected: todos passando.

- [ ] **Step 7: Commit**

```bash
git add scheduler/src/services/conversation_agent.py scheduler/src/services/outbound_queue.py \
        scheduler/src/functions/outbound/processor.py scheduler/tests/unit/test_agent_history.py
git commit -m "feat(scheduler): semeia contexto do agente e reconstrói histórico do MessageEvents"
```

---

# PARTE C — Inversão da política de resposta

---

### Task 6: Bot responde só quem é elegível

**Files:**
- Modify: `scheduler/src/scripts/setup_database.py` (coluna `bot_autoreply_policy`)
- Modify: `scheduler/src/functions/webhook/handler.py`
- Modify: `scheduler/src/functions/clinic/update.py`
- Test: `scheduler/tests/unit/test_bot_eligibility.py`

**Interfaces:**
- Produces: `should_bot_reply(clinic: dict, session: dict) -> bool` em `scheduler/src/functions/webhook/handler.py`.

**Política por clínica, não global.** `clinics.bot_autoreply_policy` com dois valores:

| Valor | Comportamento |
|---|---|
| `ALL` (default) | Bot responde todas as conversas. É o de hoje. |
| `LEADS_ONLY` | Bot só responde conversas com `bot_enabled = true` na sessão, que é o que a Task 5 semeia para lead da landing page. |

O default `ALL` é obrigatório: `clinicadorods-da7b62` está em produção com `use_agent=true` e `bot_paused=false`, respondendo todas as conversas. Inverter o default globalmente desligaria esse bot em silêncio. A Essência entra em `LEADS_ONLY` por migration de dados explícita.

- [ ] **Step 1: Adicionar a coluna**

Em `setup_database.py`, na lista `MIGRATIONS`:

```python
    # Política de resposta automática por clínica.
    # ALL preserva o comportamento atual (bot responde todos); LEADS_ONLY restringe
    # às conversas marcadas como elegíveis, que hoje só nascem de lead da landing page.
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS bot_autoreply_policy VARCHAR(20) NOT NULL DEFAULT 'ALL'",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'chk_bot_autoreply_policy'
        ) THEN
            ALTER TABLE scheduler.clinics
            ADD CONSTRAINT chk_bot_autoreply_policy
            CHECK (bot_autoreply_policy IN ('ALL', 'LEADS_ONLY'));
        END IF;
    END $$
    """,
```

E incluir `bot_autoreply_policy` em `ALLOWED_FIELDS` de `clinic/update.py`.

- [ ] **Step 2: Escrever o teste que falha**

```python
# scheduler/tests/unit/test_bot_eligibility.py
"""Quem o bot responde automaticamente.

O default tem que continuar respondendo todo mundo: há clínica em produção
dependendo disso. A restrição é opt-in por clínica.
"""
import os
import time
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.functions.webhook.handler import should_bot_reply


class TestPolicyAll(unittest.TestCase):
    def test_responde_conversa_qualquer(self):
        self.assertTrue(should_bot_reply({"bot_autoreply_policy": "ALL"}, {}))

    def test_policy_ausente_se_comporta_como_all(self):
        self.assertTrue(should_bot_reply({}, {}))


class TestPolicyLeadsOnly(unittest.TestCase):
    def setUp(self):
        self.clinic = {"bot_autoreply_policy": "LEADS_ONLY"}

    def test_conversa_sem_marca_nao_recebe_resposta(self):
        self.assertFalse(should_bot_reply(self.clinic, {}))

    def test_conversa_de_lead_recebe_resposta(self):
        self.assertTrue(should_bot_reply(self.clinic, {"bot_enabled": True}))

    def test_bot_desligado_manualmente_nao_responde(self):
        self.assertFalse(should_bot_reply(self.clinic, {"bot_enabled": False}))


class TestAtendenteHumano(unittest.TestCase):
    def test_atendente_ativo_suspende_o_bot_mesmo_com_lead(self):
        session = {"bot_enabled": True, "attendant_active_until": int(time.time()) + 3600}

        self.assertFalse(should_bot_reply({"bot_autoreply_policy": "LEADS_ONLY"}, session))

    def test_atendente_expirado_nao_bloqueia(self):
        session = {"bot_enabled": True, "attendant_active_until": int(time.time()) - 10}

        self.assertTrue(should_bot_reply({"bot_autoreply_policy": "LEADS_ONLY"}, session))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar o teste para confirmar que falha**

Run: `cd scheduler && python -m pytest tests/unit/test_bot_eligibility.py -v`
Expected: FAIL com `ImportError: cannot import name 'should_bot_reply'`

- [ ] **Step 4: Implementar**

Em `scheduler/src/functions/webhook/handler.py`, no nível do módulo:

```python
POLICY_ALL = "ALL"
POLICY_LEADS_ONLY = "LEADS_ONLY"


def should_bot_reply(clinic: dict, session: dict) -> bool:
    """O bot deve responder automaticamente esta conversa?

    Atendente humano ativo sempre suspende o bot, em qualquer política. Fora
    disso, ALL responde tudo (comportamento histórico) e LEADS_ONLY exige a marca
    `bot_enabled` que nasce do primeiro contato com lead da landing page.
    """
    session = session or {}

    ativo_ate = session.get("attendant_active_until")
    if ativo_ate and int(ativo_ate) > int(time.time()):
        return False

    if (clinic or {}).get("bot_autoreply_policy", POLICY_ALL) != POLICY_LEADS_ONLY:
        return True

    return bool(session.get("bot_enabled"))
```

Garantir que `import time` está no topo do arquivo (já está, é usado pelo modo atendente).

No fluxo do handler, depois de carregar a clínica e antes de instanciar o engine, carregar a sessão e aplicar:

```python
        session = _load_session(_get_sessions_table(), clinic_id, incoming.phone)
        if not should_bot_reply(clinic, session):
            logger.info(
                f"[Webhook] Resposta automática suprimida para {incoming.phone} "
                f"(policy={clinic.get('bot_autoreply_policy', POLICY_ALL)})"
            )
            return http_response(200, {"status": "OK"})
```

> A mensagem recebida **continua sendo registrada** pelo `MessageTracker` antes
> desse ponto, para a conversa aparecer no painel do atendente. Suprimir a
> resposta não pode significar perder a mensagem.

- [ ] **Step 5: Rodar os testes**

Run: `cd scheduler && python -m pytest tests/unit -q`
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add scheduler/src/functions/webhook/handler.py scheduler/src/functions/clinic/update.py \
        scheduler/src/scripts/setup_database.py scheduler/tests/unit/test_bot_eligibility.py
git commit -m "feat(scheduler): política de resposta automática por clínica (ALL | LEADS_ONLY)"
```

---

### Task 7: Ligar e desligar o bot na conversa pelo painel

**Files:**
- Create: `scheduler/src/functions/attendant/bot_toggle.py`
- Modify: `scheduler/sls/functions/attendant/interface.yml`
- Modify: `frontend/src/services/bot.service.ts`
- Modify: `frontend/src/pages/bot/` (componente da conversa)

**Interfaces:**
- Produces: `POST /clinics/{clinicId}/conversations/{phone}/bot` com body `{"enabled": true|false}`, devolvendo `{"status": "SUCCESS", "bot_enabled": bool}`.

- [ ] **Step 1: Implementar o handler**

```python
"""Liga ou desliga a resposta automática do bot numa conversa específica.

Com a política LEADS_ONLY, uma conversa que não veio de lead nasce sem resposta
automática. Este endpoint é como a clínica ativa o bot manualmente numa conversa
que ela julgue que vale, direto pelo painel.
"""
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
        clinic_id = params.get("clinicId")
        phone = params.get("phone")
        if not clinic_id or not phone:
            return http_response(400, {"status": "ERROR", "message": "clinicId e phone são obrigatórios"})

        body = parse_body(event) or {}
        if "enabled" not in body:
            return http_response(400, {"status": "ERROR", "message": "Campo obrigatorio: enabled"})
        enabled = bool(body["enabled"])

        table = boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"])
        table.update_item(
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

Declarar em `scheduler/sls/functions/attendant/interface.yml`, copiando o bloco de `iamRoleStatements` de outra função que já acessa `conversation-sessions`, com:

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

Na tela de conversa em `frontend/src/pages/bot/`, incluir um toggle que chama `setConversationBot` via mutation do TanStack Query, invalidando a query da conversa no `onSuccess`. Seguir `frontend/CLAUDE.md`: named export, 4 estados tratados, `clsx` para variantes, alvo de toque mínimo de 44px e transição de 100-150ms.

Estados visíveis: **Bot ativo** (respondendo) e **Bot pausado** (só atendimento humano). Quando a política da clínica for `ALL`, o toggle deve aparecer desabilitado com a explicação de que a clínica responde todas as conversas — senão o usuário desliga e nada acontece.

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

# PARTE D — Tracking do lead no painel

---

### Task 8: Registrar o estado da conversa no lead

**Files:**
- Modify: `scheduler/src/scripts/setup_database.py`
- Modify: `scheduler/src/functions/outbound/processor.py`
- Modify: `scheduler/src/functions/webhook/handler.py`
- Modify: `scheduler/src/functions/lead/list.py`

**Interfaces:**
- Produces: colunas novas em `scheduler.leads`, expostas pelo `ListLeads`:
  - `first_contact_status VARCHAR(20)` — `QUEUED` | `SENT` | `FAILED`
  - `first_contact_at TIMESTAMPTZ`
  - `conversation_started_at TIMESTAMPTZ` — quando o lead **respondeu**

A distinção importa: `first_contact_at` é "falamos com ele", `conversation_started_at` é "ele respondeu". Sem separar, não dá para medir a taxa de resposta da abordagem.

- [ ] **Step 1: Adicionar as colunas**

Em `setup_database.py`, na lista `MIGRATIONS`:

```python
    # Rastreio do primeiro contato ativo com o lead.
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS first_contact_status VARCHAR(20)",
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMPTZ",
    # Preenchido quando o lead responde, não quando o bot fala.
    "ALTER TABLE scheduler.leads ADD COLUMN IF NOT EXISTS conversation_started_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS idx_leads_first_contact ON scheduler.leads(clinic_id, first_contact_status)",
```

E adicionar as três à lista `CREATE TABLE` de `leads`, para manter em sincronia (regra do `CLAUDE.md`).

- [ ] **Step 2: Marcar QUEUED ao enfileirar**

Em `_enqueue_first_contact` (Task 4), após o `enqueue` bem-sucedido:

```python
        if item:
            db.execute_query(
                "UPDATE scheduler.leads SET first_contact_status = 'QUEUED', updated_at = NOW() "
                "WHERE id = %s::uuid",
                (str(lead["id"]),),
            )
```

- [ ] **Step 3: Marcar SENT/FAILED no dispatcher**

Em `outbound/processor.py`, no bloco de sucesso:

```python
                if item.get("leadId"):
                    db.execute_query(
                        "UPDATE scheduler.leads SET first_contact_status = 'SENT', "
                        "first_contact_at = NOW(), updated_at = NOW() WHERE id = %s::uuid",
                        (item["leadId"],),
                    )
```

E no bloco de falha, o equivalente com `'FAILED'` e sem `first_contact_at`.

- [ ] **Step 4: Marcar a resposta do lead no webhook**

Em `webhook/handler.py`, ao processar uma mensagem recebida, antes de decidir sobre a resposta automática:

```python
        db.execute_query(
            "UPDATE scheduler.leads SET conversation_started_at = COALESCE(conversation_started_at, NOW()), "
            "updated_at = NOW() WHERE clinic_id = %s AND phone = %s AND conversation_started_at IS NULL",
            (clinic_id, incoming.phone),
        )
```

O `COALESCE` com o filtro `IS NULL` garante que só a **primeira** resposta conta, e que reprocessar o webhook não sobrescreve a data original.

- [ ] **Step 5: Expor no ListLeads**

Incluir as três colunas no `SELECT` de `scheduler/src/functions/lead/list.py` e no dicionário serializado da resposta.

- [ ] **Step 6: Validar**

Run: `cd scheduler && python -m pytest tests/unit -q`
Expected: todos passando.

- [ ] **Step 7: Commit**

```bash
git add scheduler/src/scripts/setup_database.py scheduler/src/functions/outbound/processor.py \
        scheduler/src/functions/webhook/handler.py scheduler/src/functions/lead/create.py \
        scheduler/src/functions/lead/list.py
git commit -m "feat(scheduler): rastreia primeiro contato e início de conversa no lead"
```

---

### Task 9: Mostrar o estado da conversa no painel

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/pages/leads/LeadsPage.tsx`

**Interfaces:**
- Consumes: os campos novos do `ListLeads` (Task 8).

- [ ] **Step 1: Estender o tipo**

Em `frontend/src/types/index.ts`, no tipo `Lead`:

```typescript
  first_contact_status?: 'QUEUED' | 'SENT' | 'FAILED' | null
  first_contact_at?: string | null
  conversation_started_at?: string | null
```

- [ ] **Step 2: Adicionar a coluna e corrigir a cópia**

Em `LeadsPage.tsx`:

- Nova coluna **Conversa** com badge derivado do estado:

```typescript
function ConversationBadge({ lead }: { lead: Lead }) {
  if (lead.conversation_started_at) return <Badge variant="success">Respondeu</Badge>
  if (lead.first_contact_status === 'SENT') return <Badge variant="neutral">Contatado</Badge>
  if (lead.first_contact_status === 'QUEUED') return <Badge variant="warning">Na fila</Badge>
  if (lead.first_contact_status === 'FAILED') return <Badge variant="danger">Falhou</Badge>
  return <Badge variant="neutral">Sem contato</Badge>
}
```

- Trocar o subtítulo `"Contatos que iniciaram conversa com o bot"` por `"Leads capturados pela landing page e pelo WhatsApp"`.
- Trocar a descrição do estado vazio `"Leads aparecem quando pacientes entram em contato via WhatsApp."` por `"Leads aparecem quando alguém preenche o formulário da landing page ou chama no WhatsApp."`.

**Corrigir também o KPI de taxa de conversão**, que hoje divide `leads.filter(...)` (página carregada) por `data.total` (total do servidor). Com mais leads que o `limit` a porcentagem fica errada em silêncio. Passar a calcular sobre o mesmo conjunto:

```typescript
  const conversionRate = leads.length > 0 ? Math.round((bookedCount / leads.length) * 100) : 0
```

- [ ] **Step 3: Validar**

Run: `cd frontend && npm run lint && npm run build && npm run test`
Expected: tudo passando, zero warnings.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/pages/leads/LeadsPage.tsx
git commit -m "feat(frontend): estado da conversa na lista de leads"
```

---

### Task 10: Ativar na Essência e documentar

**Files:**
- Modify: `scheduler/README.md`
- Modify: `CLAUDE.md` (seção do Scheduler)

- [ ] **Step 1: Rodar as migrations**

```bash
cd scheduler && python -m src.scripts.setup_database
```

- [ ] **Step 2: Configurar a clínica**

Pelo endpoint de update (`PUT /clinics/{clinicId}`), ou por SQL direto, definir para `clinicaessenciaestetica-9668a4`:

| Campo | Valor | Por quê |
|---|---|---|
| `use_agent` | `true` | O bot deve ser o LLM, não a máquina de estados |
| `bot_paused` | `false` | Hoje está `true`, ou seja, tudo desligado |
| `bot_autoreply_policy` | `'LEADS_ONLY'` | Só responde lead da landing page |
| `first_contact_template` | mensagem de boas-vindas | Senão cai no default do código |

**Não mexer nas outras duas clínicas.** `clinicadorods-da7b62` fica em `ALL`, preservando o comportamento atual.

> **Bloqueio conhecido:** o `AI_SYSTEM_PROMPT` da Essência ainda não existe — a clínica tem zero registros em `message_templates`. Com `use_agent=true` e sem esse template, o agente sobe sem instruções de negócio. **Não ative `use_agent` em produção antes do template existir.** É a pendência registrada no topo deste plano.

- [ ] **Step 3: Documentar**

Em `scheduler/README.md`, seção nova descrevendo: a fila de envio e seu limite de taxa, a política `ALL`/`LEADS_ONLY`, e o ciclo de vida do primeiro contato (`QUEUED` → `SENT` → resposta do lead → `conversation_started_at`).

Em `CLAUDE.md`, adicionar `outbound-queue` à lista de tabelas DynamoDB do Scheduler e `business_hours.py` / `outbound_queue.py` à lista de services.

- [ ] **Step 4: Commit**

```bash
git add scheduler/README.md CLAUDE.md
git commit -m "docs: fila de envio ativo e política de resposta automática"
```

---

## Riscos

**Bloqueio do número no z-api.** É o risco de maior impacto: o provider é não-oficial e a linha é compartilhada com os atendentes humanos, então um bloqueio derruba o atendimento inteiro, não só o bot. Mitigações neste plano: 1 envio a cada 15 minutos, envio só dentro do horário comercial, e disparo apenas para quem preencheu formulário há pouco (opt-in claro). Vale acompanhar os primeiros dias com volume baixo antes de confiar.

**Horário comercial atual atrasa muito o primeiro contato.** Com seg-sex 07:15-21:00, o lead de sábado 06:45 espera até segunda 07:15 — quase 49 horas. O plano respeita o que está cadastrado por decisão explícita, mas a taxa de resposta provavelmente vai sofrer até os horários serem revistos.

**A supressão de resposta é silenciosa para quem opera.** Com `LEADS_ONLY`, uma conversa não elegível não recebe nada do bot e nada indica isso no WhatsApp. Se ninguém olhar o painel, a mensagem fica sem resposta. O toggle da Task 7 e o painel de conversas ativas são a mitigação; vale confirmar que o time acompanha.

## Fora de escopo

- **`AI_SYSTEM_PROMPT`** com o comportamento de quebrar objeção e gerar desejo (pendência registrada, commit separado).
- **Correção dos horários da clínica** (operação, não código).
- **Ligar `booked` a agendamento real** — mesmo buraco de sinal do `revenue_real`, tratado na fase 0.5.
- **Reenvio automático em caso de falha.** O item fica `FAILED` e visível; retentativa automática contra um provider que pode estar bloqueando é justamente o que agrava um bloqueio.
