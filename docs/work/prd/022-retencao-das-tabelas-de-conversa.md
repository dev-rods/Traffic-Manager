# PRD — 022 Retenção das tabelas de conversa (TTL)

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Dar prazo de vida ao que é conversa e manter sem prazo o que é identidade. Duas
decisões do André em 12/10/2026:

- **30 dias de memória do bot.** Uma pessoa que volta depois de 30 dias de
  silêncio é tratada como conversa nova: o agente não lê o histórico antigo,
  nem da sessão nem dos eventos.
- **60 dias de histórico no painel.** Os eventos de mensagem (a aba Conversas
  do painel, o chat de cada número) vencem em 60 dias.

E uma correção de registro: o `CLAUDE.md` afirma TTLs (30 min, 90 dias, 48 h)
que nunca existiram. As três tabelas estão com TTL desligado.

---

## 2. Contexto

Medido em prod em 12/10/2026 (`clinic-scheduler-infra-prod-conversation-sessions`):

| item | quantidade | observação |
|---|---|---|
| `DEDUP#` (dedup de webhook do z-api) | 3434 | já nascem com `ttl` de 5 min; nunca morrem porque o TTL da tabela está desligado |
| `LID#` (vínculo LID → telefone) | 492 | identidade; sem prazo |
| `BUFFER#` (agregador de rajada) | poucos | já nascem com `ttl` |
| `PHONE#` (sessão de conversa) | 543 | 48 com mais de 90 dias |

`message-events`: 69.888 itens, 43 MB, sem TTL. `scheduled-reminders`: vazia.

Custo é irrelevante (centavos por mês). O que pesa:

1. **Memória sem fim.** O agente lê `agent_history` da sessão e, quando ela
   está vazia ou num gatilho, reconstrói os últimos 20 eventos. Nenhum dos dois
   olha a idade. Quem volta depois de dois meses tem a conversa de dois meses
   atrás alimentando o modelo. Apagar só a sessão não resolve: a reconstrução
   traria tudo de volta dos eventos.
2. **Lixo que não some.** 77% da tabela de sessões é dedup vencido.
3. **Documentação mentindo.** O `CLAUDE.md` levou a um diagnóstico errado em
   06/10 (ver memória `project_ttl_das_tabelas_dynamo`).

O que uma sessão carrega, e o que acontece se ela vencer:

| campo | natureza | ao vencer |
|---|---|---|
| `agent_history`, `respaldo_anterior`, `efeito_na_ultima_rodada`, `recusas_de_area`, `campanha` | conversa | some, e é o que se quer |
| `atendimento` (prazos de 24 h) | conversa | some depois de vencido há dias; inofensivo |
| `bot_enabled` (elegibilidade em LEADS_ONLY) | marca | o webhook **rederiva** da tabela `leads` (origem landing-page) quando a sessão não tem a marca. Só a marca dada pelo "Retomar bot" a quem não é lead de landing page se perde; depois de 30 dias de silêncio a política da clínica volta a valer, e isso é aceito |
| `lead_id` | marca | rederivado junto |
| `LID#` (item próprio) | identidade | **não recebe `ttl`**; sem ele a resposta da atendente pelo celular fica sem dono |

---

## 3. Escopo

### Dentro do escopo
- Ligar o TTL nas tabelas `conversation-sessions` e `message-events` (atributo `ttl`, epoch em segundos).
- Toda escrita de sessão `PHONE#` grava `ttl = agora + 30 dias`. `LID#` não grava.
- O agente ignora histórico mais velho que 30 dias: sessão cujo `updatedAt` passou de 30 dias é tratada como nova (o TTL do DynamoDB pode atrasar até 48 h), e a reconstrução a partir dos eventos só considera eventos dos últimos 30 dias.
- Todo evento de mensagem grava `ttl = createdAt + 60 dias`.
- Script idempotente de backfill para os eventos existentes (quem roda em prod é o André).
- `CLAUDE.md` corrigido.

### Fora do escopo
- `scheduled-reminders` (vazia; o lembrete 24 h nunca foi ligado, decisão à parte).
- Retenção dos leads e agendamentos no Postgres.
- Exportação de transcrições antes de vencer (PRD 019 mencionava; quem quiser guardar mais de 60 dias decide antes de ligar).

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/sls/resources/dynamodb/conversation-sessions-table.yml` | modificar | `TimeToLiveSpecification` em `ttl` |
| `scheduler/sls/resources/dynamodb/message-events-table.yml` | modificar | idem |
| `scheduler/src/services/session_store.py` | modificar | `ttl` em `grava_atendimento`, `mark_conversation_eligible`, `abre_campanha`; não em `vincula_lid` |
| `scheduler/src/services/conversation_agent.py` | modificar | `ttl` em `_save_session`; sessão velha é nova; reconstrução com janela |
| `scheduler/src/functions/webhook/handler.py` | modificar | `ttl` em `_save_session` |
| `scheduler/src/services/message_tracker.py` | modificar | `ttl` em todo item; `get_conversation_messages(desde=...)` |
| `scheduler/src/scripts/backfill_ttl_eventos.py` | criar | backfill idempotente |
| `CLAUDE.md` | modificar | retenções reais |

---

## 5. Dependências e riscos

- **Dependências:** CloudFormation aceita ligar `TimeToLiveSpecification` numa tabela existente sem recriá-la. Nenhuma env nova.
- **Risco 1, fase 1:** ligar o TTL na tabela de sessões apaga de imediato os itens que já têm `ttl` vencido: só `DEDUP#` e `BUFFER#`. Sessões e LIDs não têm o atributo e ficam intactos. O `BUFFER#` vencido já foi drenado (o `ttl` dele é posterior à janela).
- **Risco 2, fase 2:** um escritor de sessão que esqueça o `ttl` faz a sessão viver para sempre de novo, em silêncio. O teste de fonte única cobre todos os `put_item` da tabela.
- **Risco 3:** o painel perde conversas com mais de 60 dias na aba Conversas e no chat. Decisão do André.
- **Risco 4:** `rebuild_history_from_events` com janela: conversa que atravessa os 30 dias perde o começo. É o comportamento pedido.

---

## 6. Critérios de aceite

- [ ] `describe-time-to-live` das duas tabelas em prod: ENABLED em `ttl`.
- [ ] Depois de 48 h, zero itens `DEDUP#` com `ttl` vencido.
- [ ] Toda sessão `PHONE#` escrita depois do deploy tem `ttl` = `updatedAt` + 30 dias; nenhum `LID#` tem `ttl`.
- [ ] Todo evento escrito depois do deploy tem `ttl` = `createdAt` + 60 dias; backfill aplicado em prod.
- [ ] Teste: sessão com `updatedAt` de 31 dias atrás e histórico cheio → o modelo recebe só a mensagem nova; eventos de 31 dias atrás não entram na reconstrução.
- [ ] `CLAUDE.md` descreve 30 d / 60 d / sem TTL (lembretes).

---

## 7. Referências

- PRD 020 §3 (bloco `atendimento` e seus prazos); PRD 019 (transcrições).
- Memória `project_ttl_das_tabelas_dynamo`.

---

## Status (preencher após conclusão)

- [x] Spec gerada: `spec/022-retencao-das-tabelas-de-conversa.md`
- [x] Implementado em: fase 1 (TTL ligado) em 12/10/2026, PR #129; fase 2 (conversa vence) em 12/10/2026
- [x] Registrado em `TASKS_LOG.md`
