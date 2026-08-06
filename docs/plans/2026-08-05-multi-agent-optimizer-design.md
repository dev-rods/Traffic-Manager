# Design — Sistema Multi-Agente de Diagnóstico e Otimização de Campanhas

**Data:** 2026-08-05
**Autor:** André (brainstorming com Claude)
**Status:** Design aprovado — decomposição em fatias; pendências a resolver na spec da Fatia 0

---

## Contexto

Hoje o `infra/` tem integração com Google Ads e um otimizador **baseado em regras**
(`infra/src/functions/optimizer/generate_recommendations.py`, função `_decide_action`:
faixas de CPA → ação de CPC). O PR#3 adicionou atribuição offline: `scheduler.leads`
(com `gclid`) ⋈ `scheduler.lead_conversions` (`value_cents`, `booked`, `conversion_date`,
`click_date`, recompras), ligando cliques do Google Ads a **vendas reais**.

Queremos um sistema que, **sob demanda e por período** (ex.: "últimos 30 dias"), leia
amplamente os dados do Google Ads + LP + vendas reais, rode análises especializadas e
produza um **relatório executivo** com diagnóstico, problemas e ações recomendadas.

## Princípio central: cálculo determinístico ≠ julgamento da LLM

A motivação de arquitetura: **LLM não é confiável para aritmética/agregação**. Portanto:

- **Todo número** (agregações, ROAS, CPA, CTR, LTV, latência) é computado em **Python
  determinístico** e entregue "mastigado" num snapshot JSON.
- A **LLM só faz julgamento**: priorizar, interpretar, decidir trade-offs, redigir.

Isto generaliza o padrão que já existe em `_decide_action` (regra determinística decide,
não a LLM).

## Objetivo e guarda-corpos

Função-objetivo: **maximizar Receita Total**, sujeito a:
- `ROAS ≥ ROAS-alvo`
- `CPA ≤ CPA-alvo`
- `CTR ≥ CTR-piso`

Em conflito entre otimizadores, a política é **priorizar receita de longo prazo**
(usa recompra/LTV real do banco) **mantendo os valores-alvo acima**. Todos os alvos
vivem no `business-context` (fonte única de verdade do "o que é bom").

## Não-objetivos (v1)

- v1 é **somente recomendação**. Aplicar mudanças no Google Ads
  (aplicar-após-aprovação, via endpoints de escrita do `infra/`) é **fase 2** (Fatia 4).
- O MCP do Google Ads disponível é **read-only** (`search`, `list_accessible_customers`,
  `get_resource_metadata`); escrita futura passa por `infra/` (`googleads/action.py`,
  `recommendations/apply_recommendation.py`).

---

## Arquitetura (3 camadas)

```
Período (ex.: 30d) + customer
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ CAMADA A — Dados determinísticos (Python, ZERO LLM)          │
│  analysis/  → snapshot.json (mastigado)                      │
│   - data/google_ads.py  (GAQL por dimensão)                 │
│   - data/conversions.py (join gclid: período + HISTÓRICO)   │
│   - data/ga4.py         (LP: sessões, form, bounce)         │
│   - metrics.py          (ROAS/CPA/CTR/LTV/latência)         │
└─────────────────────────────────────────────────────────────┘
        │ snapshot.json + business-context
        ▼
┌─────────────────────────────────────────────────────────────┐
│ CAMADA B — Analisadores (skills = subagents; LLM julga)      │
│  search-term-analyzer   bid-optimizer (geo/público/device)  │
│  creative-optimizer     landing-optimizer                   │
│  budget-optimizer       audience-fit-analyzer               │
└─────────────────────────────────────────────────────────────┘
        │ recomendações priorizadas (por analisador)
        ▼
┌─────────────────────────────────────────────────────────────┐
│ CAMADA C — Síntese                                           │
│  attribution-agent  → une, resolve conflitos (política)     │
│  executive-reporter → cenário / problemas / ações / expect. │
└─────────────────────────────────────────────────────────────┘
```

### Orquestração no Claude Code

- Skill orquestradora **`campaign-audit`**: recebe o período, roda `analysis.pull`
  (determinístico), **dispara os analisadores como subagents em paralelo** (ferramenta
  Agent), cada um lendo o mesmo `snapshot.json` + `business-context`.
- O agente principal coleta as saídas, roda `attribution-agent` e `executive-reporter`.
- Leitura é paralela/isolada; escrita (fase 2) é serial e com aprovação item a item.

---

## Componentes

### Skill declarativa: `business-context`
Lida por **todos** os agentes. Contém:
- Limitações de **orçamento mensal**.
- Descrição do negócio: **depilação a laser** (ticket, recorrência, sazonalidade).
- **Público que realmente converte** na visão do dono do negócio.
- **Diferenciais** do serviço.
- **Alvos**: ROAS-alvo, CPA-alvo, CTR-piso (parametrizados).

### Camada A — pacote `analysis/`
Snapshot JSON de um período, com duas janelas de conversão:
- **Período:** métricas do Google Ads por dimensão + leads/conversões gerados no período.
- **Histórico all-time:** coorte de **todos** os clientes que converteram via Google Ads
  (receita total, latência da 1ª conversão, nº de recompras, LTV) — para aprender com quem
  já trouxe receita, já que os leads do período podem ainda não ter maturado.

CLI: `python -m analysis.pull --customer 4601912200 --period 30d --out snapshot.json`

### Camada B — analisadores (uma skill cada)
- **search-term-analyzer** — termos de busca, negativos, alinhamento query↔keyword, receita
  real por termo.
- **bid-optimizer** — ajustes por **geo / público / device** com base em CPA/ROAS/LTV.
- **creative-optimizer** — desempenho de anúncios (CTR, conv), sugestões de criativo.
- **landing-optimizer** — GA4 (bounce, form start/complete, scroll) + conv-rate (leads ÷
  cliques) + análise do código-fonte da LP.
- **budget-optimizer** — realocação de orçamento entre campanhas/grupos rumo à receita.
- **audience-fit-analyzer** — compara o **perfil dos leads do período** com a **coorte
  histórica de alto LTV**: o público comprado agora está alinhado com quem paga a conta?

### Camada C — síntese
- **attribution-agent** — junta as recomendações, resolve conflitos pela política
  (receita de longo prazo, respeitando os alvos), produz o plano conjunto.
- **executive-reporter** — relatório: cenário inicial → problemas → ações recomendadas →
  expectativa de resultado.

---

## Decomposição / ordem de construção

Cada fatia é um ciclo **spec → plano → implementação** próprio.

- **Fatia 0 — Fundação:** `business-context` + camada `analysis/` (Google Ads + join de
  conversão período **e histórico** + GA4 + métricas) + formato do snapshot.
- **Fatia 1 — Prova do padrão:** `search-term-analyzer` ponta a ponta.
- **Fatia 2 — Replicar:** `bid-optimizer`, `budget-optimizer`, `creative-optimizer`,
  `landing-optimizer`, `audience-fit-analyzer`.
- **Fatia 3 — Síntese:** `attribution-agent` + `executive-reporter` + orquestrador
  `campaign-audit`.
- **Fatia 4 (fase 2):** aplicar-após-aprovação via `infra/`.

---

## Resoluções do brainstorm da Fatia 0 (2026-08-05)

1. **GA4 → movido para a Fatia 2** (junto do `landing-optimizer`, seu único consumidor).
   Fatia 0 fica: `business-context` + Google Ads pull + join de conversão (período e
   histórico) + métricas + snapshot.
2. **Mapeamento — resolvido.** Coluna `scheduler.clinics.google_ads_customer_id`
   (VARCHAR(20)) existe e está preenchida só para a Essência: **`4601912200`**. As outras
   2 clínicas estão `None` → v1 opera apenas para a Essência.
3. **Skills em `.claude/skills/`** (escopo do projeto).
4. **Definição de conversão/receita:** conversão real = agendamento **CONFIRMED com data
   já passada** (sessão ocorreu); **LTV = soma de `value_cents`** desses agendamentos.
   Mesma regra do `ConversionUploader` (`get_pending_conversions`) — consistência com o
   que sobe pro Google Ads.
5. **Coorte histórica:** todos os gclid all-time com ≥1 conversão real (acima), com
   `ltv_cents`, `latencia_dias` (1ª conversão) e `recompras`; perfil agregado por
   geo/device/audience/termo-origem para o `audience-fit-analyzer`.
6. **Alvos:** derivar **baseline** (ROAS/CPA/CTR reais do histórico) via `metrics.py`,
   apresentar ao dono, que ajusta os alvos a partir disso. `business-context` guarda os
   alvos finais.
7. **Atribuição de receita por dimensão:** receita_real por campanha/ad_group é sólida
   (sempre disponível). Para dimensões finas (keyword/termo/device/geo), usa-se o
   **`click_view`** (gclid → dimensão, **janela 90d**); onde o `click_view` não cobrir, o
   campo fica **`null`** (nunca inventar).

### Contrato do snapshot (`snapshot.json`)

```
meta:        { customer, period{start,end}, generated_at, currency }
baseline:    { roas, cpa, ctr }            # atuais, reais → semeiam os alvos
period:
  google_ads:
    campaigns[], ad_groups[], ads[], keywords[],
    search_terms[], geo[], devices[], audiences[]
    # cada linha: impressions, clicks, cost, ctr,
    #             conv_google, revenue_real, roas_real, cpa_real  (finas: null se sem click_view)
  leads:      { total, com_gclid, por_segmento{geo,device,...} }
historical_cohort:          # ALL-TIME
  customers[]: { gclid, ltv_cents, latencia_dias, recompras }
  perfil_alto_ltv: { distrib por geo/device/audience/termo_origem }
```

## Pendências remanescentes (Fatia 2+)

- **GA4:** property ID + service account com permissão de leitura (Fatia 2).
