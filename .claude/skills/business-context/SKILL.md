---
name: business-context
description: Contexto de negócio da Essência (depilação a laser) para análise e otimização de campanhas Google Ads — orçamento, público-alvo, diferenciais e alvos de ROAS/CPA/CTR. Use ao analisar ou recomendar mudanças em campanhas da Essência.
---

# Contexto de Negócio — Essência

## Negócio
Clínica de depilação a laser (Soprano Ice Platinum), sessão avulsa, ticket médio informado pelo dono do negócio. Intervalo médio de 30 dias entre sessões por área.

## Orçamento
Orçamento mensal de mídia: [preencher com valor informado pelo dono].

## Público que converte (visão do dono)
[preencher com a descrição do dono: faixa etária, região, gênero predominante, canais que mais convertem]

## Diferenciais
[preencher com os diferenciais que o dono destaca frente à concorrência]

## Alvos (seedados pelo baseline calculado em `analysis/`)

Pull real rodado em 2026-08-09 contra prod (`customer=4601912200`, período de 90 dias: 2026-05-11 a 2026-08-09):

- ROAS alvo: **0.0** (coorte histórica de conversões reais ainda vazia — 0 registros no período analisado)
- CPA alvo: **indisponível** (sem conversões confirmadas para calcular)
- CTR alvo: **0.052** (~5,2%)

> Estes alvos vêm do `baseline` do `snapshot.json` (coorte histórica all-time ÷
> custo total do período) e devem ser revisados com o dono do negócio antes de
> virarem meta operacional — o baseline é um piso estatístico, não uma meta.
>
> **Nota importante:** o ROAS/CPA vieram vazios porque a coorte histórica de
> conversões reais (`scheduler.lead_conversions` cruzado com `appointments`
> `CONFIRMED` e já ocorridos) está vazia para essa clínica no banco de
> produção no momento deste pull — só 3 leads no período, 2 com `gclid`, e
> nenhuma conversão confirmada e já ocorrida ainda. Rode
> `python -m analysis.pull --customer 4601912200 --period 90d --stage prod`
> de novo depois que houver mais agendamentos confirmados no passado, para
> obter um baseline com sinal real.
