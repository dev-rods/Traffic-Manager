# Spec — 022 Retenção das tabelas de conversa (TTL)

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/022-retencao-das-tabelas-de-conversa.md`

---

## 1. Resumo

Duas fases, dois PRs. **Fase 1** liga o TTL nas duas tabelas (só infra): o
efeito imediato é apagar o lixo que já tem `ttl` (dedup, buffer). **Fase 2**
faz conversa vencer: sessões `PHONE#` gravam `ttl` de 30 dias em todos os
escritores, eventos gravam `ttl` de 60 dias, o agente ignora histórico mais
velho que 30 dias, e um backfill dá `ttl` aos eventos existentes.

Constantes, num lugar só:

```python
# src/services/retencao.py
MEMORIA_DO_BOT = 30 * 86400      # sessao PHONE# e janela de reconstrucao
HISTORICO_DO_PAINEL = 60 * 86400  # eventos de mensagem

def ttl_da_sessao(agora): return int(agora) + MEMORIA_DO_BOT
def ttl_do_evento(criado_em): return int(criado_em) + HISTORICO_DO_PAINEL
def sessao_vencida(updated_at_iso, agora) -> bool
```

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/src/services/retencao.py` | as constantes e as três funções acima |
| `scheduler/src/scripts/backfill_ttl_eventos.py` | varre `message-events` por clínica e grava `ttl = createdAt + 60 d` onde falta; idempotente; itens já mais velhos que 60 d recebem `ttl = agora + 1 d` |
| `scheduler/tests/unit/test_retencao.py` | constantes, `sessao_vencida`, e o teste de fonte única: todo `put_item`/`update_item` da tabela de sessões em `src/` passa por `retencao` (AST, não texto) |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `sls/resources/dynamodb/conversation-sessions-table.yml` | `TimeToLiveSpecification: {AttributeName: ttl, Enabled: true}` (fase 1) |
| `sls/resources/dynamodb/message-events-table.yml` | idem (fase 1) |
| `src/services/session_store.py` | `ttl` em `mark_conversation_eligible`, `abre_campanha`, `grava_atendimento` (SET na raiz, também no caminho de item novo); **não** em `vincula_lid` |
| `src/services/conversation_agent.py` | `_save_session` grava `ttl`; em `process_message`, se `sessao_vencida(updatedAt)` o histórico e os campos de conversa são descartados antes de qualquer leitura; `rebuild_history_from_events(..., desde=agora - MEMORIA_DO_BOT)` |
| `src/functions/webhook/handler.py` | `_save_session` grava `ttl`; `_load_session` devolve também `updatedAt` (hoje devolve só `session`) ou o agente lê o item |
| `src/services/message_tracker.py` | `ttl` nos três `put_item`; `get_conversation_messages(..., desde=None)` filtra `createdAt >= desde` |
| `CLAUDE.md` | linha das tabelas DynamoDB |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. **Fase 1 (PR próprio):** os dois `.yml` + `CLAUDE.md` + PRD/Spec. Deploy dev, conferir `describe-time-to-live`; deploy prod. Esperar 48 h e contar `DEDUP#`.
2. **Fase 2:** `retencao.py` e testes; `message_tracker` (escrita e leitura com janela); `session_store`; `webhook._save_session`; `conversation_agent` (grava, descarta sessão vencida, reconstrói com janela); backfill. Deploy dev, mensagem real, conferir `ttl` no item; prod; André roda o backfill em prod.

---

## 6. Detalhes por arquivo

### `src/services/retencao.py`
- `sessao_vencida(updated_at_iso, agora)`: `updatedAt` é ISO `%Y-%m-%dT%H:%M:%SZ`; sem `updatedAt` → não vencida (sessão nova). Pura.

### `src/services/session_store.py`
- `grava_atendimento`: `sets.append("#ttl = :ttl")` com `nomes["#ttl"] = "ttl"`, `valores[":ttl"] = ttl_da_sessao(agora)`; no `put_item` de item novo, `novo["ttl"]`.
- `mark_conversation_eligible` e `abre_campanha`: `"ttl": ttl_da_sessao(...)` no `Item`.
- `vincula_lid`: sem `ttl`, com comentário dizendo por quê.

### `src/services/conversation_agent.py`
- `_save_session`: `"ttl": ttl_da_sessao(now)`.
- `process_message`: a sessão carregada vem com `updatedAt` do item. Se `sessao_vencida`, log `[Retencao] {phone}: sessao de {dias} dias descartada` e `session = {k: v for k in session if k in CAMPOS_DE_IDENTIDADE}` (`bot_enabled`, `lead_id`). O resto é conversa.
- `rebuild_history_from_events`: passa `desde` ao tracker.

### `src/services/message_tracker.py`
- `ttl_do_evento(now)` em `track_outbound`, `track_inbound`, `update_status` (o status usa `event_time`).
- `get_conversation_messages(clinic_id, phone, limit=50, desde=None)`: com `desde` (epoch), `FilterExpression=Attr("createdAt").gte(iso)`; o `Limit` do DynamoDB é aplicado antes do filtro, então com `desde` a consulta usa `KeyConditionExpression` em `sk` (`begins_with` não serve; usar `sk >= f"MSG#{iso}"`, já que `sk` começa pelo ISO) e **não** filtro.

### `src/scripts/backfill_ttl_eventos.py`
- Argumentos: `stage`, `--aplicar`. Sem `--aplicar` só conta. Lê `MESSAGE_EVENTS_TABLE` pelo nome `clinic-scheduler-infra-{stage}-message-events`. `scan` com `FilterExpression=attribute_not_exists(ttl)`, `update_item` com `ConditionExpression=attribute_not_exists(ttl)` (idempotente mesmo em corrida com o tracker).

### Testes
- `test_retencao.py`: fonte única por AST (ver `test_nomes_resolvem.py` como modelo): em `src/`, toda chamada `put_item`/`update_item` cujo receptor é a tabela de sessões e cujo `sk` começa com `PHONE#` carrega `ttl`; `LID#` não.
- `test_agente_esquece_depois_de_30_dias.py`: com `dublagem_agente`, sessão com `updatedAt` de 31 dias e `agent_history` de 6 turnos; o modelo recebe só o turno novo. Com 29 dias, recebe os 6. Eventos de 31 dias não entram na reconstrução.
- `test_message_tracker` (existente?): `ttl` presente nos itens; `desde` corta.
