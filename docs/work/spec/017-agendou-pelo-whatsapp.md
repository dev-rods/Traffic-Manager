# Spec — 017 "Agendou pelo WhatsApp"

> Gerado na fase **Spec**, a partir de `docs/work/prd/017-agendou-pelo-whatsapp.md`.

---

## 1. A forma da mudança

O uploader hoje faz **uma** coisa por clínica: sobe compras e zera o valor das
que caíram. Passa a fazer **duas**, independentes:

```
para cada clinica mapeada:
    1. zera o valor das compras canceladas/falta   (existe)
    2. sobe compras novas                          (existe)
    3. sobe agendamentos novos                     (NOVO)
```

O passo 3 não tem contrapartida de retratação, e isso **não é omissão**: num
evento de agendamento, quem marcou e desmarcou agendou de verdade. É a
propriedade que torna este evento mais simples que o de compra.

### 1.1 O que muda no que já existe, e o que não muda

| | Compra (`7699541177`) | Agendamento (novo) |
|---|---|---|
| Elegibilidade | `CONFIRMED` + sessão passada + janela 90d | **janela 90d, e nada mais** |
| Carimbo | data da **sessão** | data do **agendamento** |
| `eventSource` | `IN_STORE` | `MESSAGE` |
| Marcador de envio | `uploaded_at` | `booking_uploaded_at` |
| Retratação / zerar valor | sim | **não** |
| Valor | `final_price_cents` | `final_price_cents` |

A regra da compra **não é tocada**. O `test_elegibilidade_tem_um_dono` continua
valendo, e as duas regras passam a ser travadas como **distintas** — porque o
risco novo é alguém "unificar" as duas por parecerem parecidas.

### 1.2 O carimbo do agendamento é `lc.created_at`, não `conversion_date`

`conversion_date` é a data da **sessão** — é o que a compra usa. Para o evento de
agendamento o momento é quando a pessoa marcou, e isso é `lc.created_at`.

Consequência medida e desejada: o pior caso clique→agendamento é **41 dias**,
contra 69 do clique→sessão. Mais folga na janela de 90 dias.

**Cuidado com as linhas de backfill.** As 16 criadas em 28/09 têm `created_at` da
data do backfill, não do agendamento real — para elas o carimbo sairia errado,
semanas depois do fato. O `LEAST(lc.created_at, lc.conversion_date)` resolve: a
sessão nunca é posterior ao agendamento num fluxo normal, então o `LEAST` pega o
agendamento quando ele é real e a sessão quando o `created_at` é artefato.

E o `GREATEST(..., click_date + 1 minuto)` continua necessário: o Google recusa
conversão anterior ao clique.

---

## 2. Arquivos, em ordem

### 2.1 `scheduler/src/scripts/setup_database.py`

```sql
ALTER TABLE scheduler.clinics
  ADD COLUMN IF NOT EXISTS booking_conversion_action_id VARCHAR(30);

ALTER TABLE scheduler.lead_conversions
  ADD COLUMN IF NOT EXISTS booking_uploaded_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_lead_conversions_agendamento_a_subir
  ON scheduler.lead_conversions (clinic_id)
  WHERE booking_uploaded_at IS NULL;
```

`VARCHAR(30)` acompanha `offline_conversion_action_id`. O índice parcial espelha
o `idx_lead_conversions_a_retratar` e serve à pergunta que a Lambda faz todo mês.

`CREATE TABLE` de `clinics` e `lead_conversions` em sincronia, pela convenção do
`CLAUDE.md`.

### 2.2 `infra/src/services/data_manager_service.py`

`EVENT_SOURCE` deixa de ser constante única:

```python
EVENT_SOURCE_COMPRA = "IN_STORE"        # a compra acontece na clinica
EVENT_SOURCE_AGENDAMENTO = "MESSAGE"    # o agendamento, numa conversa
```

`_evento` e os métodos públicos passam a receber `event_source`. **Sem default** —
um default faria o evento novo herdar `IN_STORE` em silêncio se alguém esquecesse
de passar, e o erro só apareceria como atribuição estranha no Google, semanas
depois.

Método novo: `ingest_bookings`, que é `ingest_offline_conversions` com outro
`event_source` e outro nome. Nomes distintos porque os dois eventos têm regras
distintas, e um parâmetro `tipo=` convidaria a unificar as regras depois.

### 2.3 `infra/src/functions/conversions/uploader.py`

- `_get_mapped_clinics`: devolve as duas colunas de action. O `WHERE` deixa de
  exigir `offline_conversion_action_id IS NOT NULL` e passa a exigir **ao menos
  uma** das duas — senão ligar só o evento novo não faria a clínica aparecer.
- `_get_pending_bookings(db, clinic_id)`: `booking_uploaded_at IS NULL` + janela
  de 90 dias. **Sem filtro de status.**
- `_mark_booking_uploaded`.
- `_sobe_agendamentos(db, dm, clinic, trace_id, validate_only)`.
- `handler`: executa os três passos, e cada um só roda se a action dele estiver
  configurada.
- `summary` ganha `bookings_uploaded` / `bookings_failed` / `bookings_validated`.

### 2.4 `scheduler/src/scripts/liga_conversao_offline.py`

Passa a aceitar qual action ligar, e a listar as duas no modo sem argumentos.

---

## 3. Testes

| Teste | Onde | O que trava |
|---|---|---|
| a regra do agendamento NÃO filtra status | `infra/tests/unit` | é a diferença central entre os dois eventos |
| a regra da compra CONTINUA filtrando status e sessão passada | `infra/tests/unit` | as duas não foram unificadas |
| as duas regras são queries distintas | `infra/tests/unit` | ninguém juntou por parecerem parecidas |
| agendamento usa `MESSAGE`, compra usa `IN_STORE` | `infra/tests/unit` | o evento novo não herda o source do antigo |
| `event_source` é obrigatório no serviço | `infra/tests/unit` | sem default silencioso |
| cada evento marca só a sua coluna | `infra/tests/unit` | subir um não queima o outro |
| nada de retratação no caminho do agendamento | `infra/tests/unit` | a ausência é decisão, não esquecimento |
| clínica com só uma action configurada aparece | `infra/tests/unit` | o `WHERE` não exige as duas |
| o carimbo do agendamento usa `LEAST(created_at, conversion_date)` | `infra/tests/unit` | as linhas de backfill não carimbam semanas depois |
| migrations idempotentes, `CREATE TABLE` em sincronia | `scheduler/tests/unit` | convenção do projeto |

Comportamento (rede mockada) para `ingest_bookings`, espelhando o que já existe
para a compra: sucesso devolve identifiers, erro HTTP devolve lista vazia,
`validateOnly` não marca nada.

---

## 4. Fora do escopo

- Criar a action no Google Ads e promover a biddable — painel, não código.
- A faixa do painel (risco 5.3 do PRD): `resumo_de_conversoes` conta
  `uploaded_at` e passaria a mostrar retrato parcial. **Decisão pendente do
  André**, registrada; não se resolve aqui.
- Renomear `uploaded_at` → `purchase_uploaded_at`. Exigiria mexer no uploader e
  no painel ao mesmo tempo, em produção.
- Backfill do evento novo: as 30 linhas existentes têm `booking_uploaded_at`
  nulo, então entram no primeiro ciclo naturalmente. **Isso é intencional** — o
  histórico sobe de uma vez e dá ao Google a base que o evento precisa.

---

## 5. Risco

**O primeiro ciclo sobe 30 agendamentos de uma vez.** É desejável (base para o
algoritmo), mas vale rodar o ensaio `validateOnly` antes e conferir o número, em
vez de descobrir pelo relatório.

**Clínica com action nova e sem a antiga** passa a aparecer em
`_get_mapped_clinics`. O passo da compra tem de checar a action dele antes de
rodar, senão enviaria para `None`.
