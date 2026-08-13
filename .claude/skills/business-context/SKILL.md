---
name: business-context
description: Contexto de negócio da Essência (depilação a laser) para análise e otimização de campanhas Google Ads - orçamento, público-alvo, diferenciais, fórmula de revenue_projected e alvos de CPA/ROAS/CTR. Use ao analisar ou recomendar mudanças em campanhas da Essência.
---

# Contexto de Negócio — Essência

## Negócio
Clínica de depilação a laser (Soprano Ice Platinum), sessão avulsa, ticket médio informado pelo dono do negócio. Intervalo médio de 30 dias entre sessões por área.

## Orçamento
Orçamento mensal de mídia: **até R$ 3.000,00** (teto informado pelo dono do negócio). Equivale a ~R$ 98,70/dia. Qualquer recomendação de campanha/lance precisa respeitar esse teto, priorizando eficiência (CPA/ROAS) sobre volume.

## Público que converte (dados observados)

Duas fontes, propositalmente separadas porque medem coisas diferentes:

**1. Google Ads (`age_range_view` / `gender_view`, `customer=4601912200`, todo o histórico da conta até 2026-08-12)** — reflete quem clica/converte no anúncio (conversões do Ads, não agendamento confirmado):

- Gênero: **61% feminino**, 19% masculino, 20% indeterminado (Ads não identifica gênero de todo clique)
- Faixa etária: **25-34 anos concentra a maior fatia (31%)**, seguida por 18-24 (18,5%) e 35-44 (17,5%). A partir de 45 anos o volume cai bastante (45-54: 9%, 55-64: 3,5%, 65+: 0,5%). ~20% do tráfego fica "indeterminado" (Google não identifica idade).

**2. Banco do scheduler (`patients`, clínica `clinicaessenciaestetica-9668a4`, pacientes reais cadastrados)** — reflete quem de fato vira paciente, não só quem clica:

- Gênero: **84% feminino** (178), 8% masculino (17), 8% sem registro (17)
- Região (DDD do telefone, proxy geográfico): **75% DDD 11 (São Paulo capital/Grande SP)**, o resto pulverizado em DDDs do interior de SP (19-Campinas, 12-Vale do Paraíba, 16-Ribeirão Preto) e outros estados — cauda longa, sem segundo polo relevante.

**Leitura:** o anúncio já atrai público mais jovem (18-34) do que quem de fato agenda — o gap entre o gênero do clique (61% F) e o gênero de quem vira paciente (84% F) sugere que mulheres convertem em taxa bem maior que homens depois do clique. Não temos idade de quem agenda de verdade (não existe campo de data de nascimento em `patients`/`leads` no banco do scheduler) — a faixa etária acima é só do lado do anúncio.

> Falta validar com o dono do negócio se esse padrão bate com a percepção dele e se há algum recorte de público que ele prioriza que os dados não capturam (ex: motivo de escolha do serviço, ocupação, etc).

## Posicionamento e Diferenciais (visão do dono do negócio)

**Missão:** clínica premium, orientada por tecnologia e dados, com experiência transparente, confortável e baseada em evidências - não compete por preço.

**Posicionamento:** tecnologia, segurança, transparência, atendimento premium, decisões baseadas em dados. Comunicação com autoridade técnica sem ser excessivamente médica/acadêmica.

**Público-alvo (visão do dono):** pessoas que pesquisam antes de comprar, valorizam tecnologia, procuram menos dor no tratamento, preferem qualidade a promoção agressiva, querem confiança antes de iniciar. (Compatível com os dados observados acima: público majoritariamente feminino, concentrado em São Paulo capital/Grande SP.)

**Diferenciais competitivos:**
1. **Atendimento baseado em ciência** - sempre explicar o "porquê" (funcionamento do laser, diferenças de tecnologia, limitações, cuidados). Nunca linguagem sensacionalista.
2. **Tecnologia (Soprano Ice Platinum) como parte de um conjunto** - não é o único diferencial; some com profissionais qualificados, protocolos, avaliação personalizada e acompanhamento.
3. **Transparência** - comunicar número esperado de sessões, fatores que influenciam resultado, limitações. Evitar promessas absolutas ("resultado garantido", "depilação definitiva", "funciona para qualquer pessoa").
4. **Experiência premium** - conforto, confiança, acolhimento, organização, profissionalismo desde o primeiro contato.
5. **Marketing baseado em dados** - CAC, CPL, ROAS, conversões offline, Enhanced Conversions, GA4, GTM, tracking completo do funil. Toda campanha deve ser mensurável; propor testes A/B quando possível.
6. **Melhoria contínua** - cultura de medir, testar, aprender, iterar. Não assumir que uma estratégia está correta só porque funciona hoje.

**Tom de voz:** claro, elegante, humano, técnico quando necessário, objetivo, confiável. Evitar exageros, gatilhos baratos, promessas milagrosas, excesso de emojis, linguagem apelativa.

**Filosofia comercial:** a venda é consequência da confiança. Ordem: educar → tirar dúvidas → construir confiança → converter. Nunca inverter essa ordem (ex: peças de campanha/copy não devem pressionar conversão antes de gerar confiança).

## Receita: `revenue_projected` (métrica corrente)

Enquanto `revenue_real` não tiver fonte confiável (ver "Por que não usamos `revenue_real`"),
a métrica de receita usada em análise e otimização é **`revenue_projected`**:

```
revenue_projected = conversoes_google_ads * taxa_conversao_agendamento * ticket_medio * ltv_meses
```

Parâmetros definidos pelo dono do negócio (2026-08-12):

| Parâmetro | Valor | Origem |
|---|---|---|
| `taxa_conversao_agendamento` | **0,20** (20%) | definido pelo dono; medido em 23,1% no cruzamento leads x base de pacientes |
| `ticket_medio` | **R$ 250,00** | definido pelo dono |
| `ltv_meses` | **8** | definido pelo dono; 1 sessão/mês por área, intervalo médio de 30 dias |

**Cada conversão do Google Ads vale R$ 400,00 de receita projetada.**

Validade da entrada: `conversoes_google_ads` só é um proxy honesto de lead enquanto
`metrics.conversions` estiver contando ação de lead. Verificado em 2026-08-12: nos
últimos 90 dias, 100% das conversões vêm de `Lead - Formulário` (`SUBMIT_LEAD_FORM`).
O histórico all-time está inflado por dupla contagem da ação `Viu Obrigado Laser`
(hoje `REMOVED`), que registrava o mesmo evento do formulário - descontá-la ao usar
períodos longos. Reverificar essa composição antes de confiar no número em qualquer
janela nova.

## Alvos

- **CPA alvo: R$ 78,00** - meta de melhoria, definida pelo dono do negócio. É a métrica
  que puxa a operação para frente.
- **ROAS alvo: 4,52** - piso de não-regressão, igual ao ROAS observado na janela de 90
  dias (2026-05-15 a 2026-08-12). Cair abaixo disso significa piorar frente ao que a
  campanha já entrega hoje.
- **CTR alvo: 0,052** (~5,2%) - do baseline real calculado em `analysis/`.

> **CPA e ROAS são a mesma métrica sob a fórmula atual**, ligados por
> `ROAS = 400 ÷ CPA`. Por isso não são dois alvos independentes, e sim os dois extremos
> da faixa de operação aceitável:
>
> | | CPA | ROAS |
> |---|---|---|
> | Piso (não regredir) | R$ 88,50 | **4,52** |
> | Meta (melhorar até) | **R$ 78,00** | 5,13 |
>
> Hoje a campanha opera em CPA R$ 88,57 / ROAS 4,52, ou seja, **exatamente no piso**.
> Fechar a lacuna até R$ 78 exige ~12% de redução de CPA.
>
> Alvo anterior de ROAS (2,0) foi descartado: permitiria CPA de até R$ 200, ~2,5x mais
> folgado que o alvo real, o que o tornava inócuo como guarda-corpo.
>
> Se `ticket_medio`, `ltv_meses` ou `taxa_conversao_agendamento` mudarem, os dois valores
> de ROAS precisam ser recalculados - o CPA não.

Posição em 2026-08-12 (campanha `[Gestor]Depilacao_primeira_jardins`, customer 4601912200):

| Janela | Custo | Conv. | CPA | `revenue_projected` | ROAS |
|---|---|---|---|---|---|
| Últimos 30 dias | R$ 1.784,36 | 21 | R$ 84,97 | R$ 8.400 | 4,71 |
| Últimos 90 dias | R$ 3.631,31 | 41 | R$ 88,57 | R$ 16.400 | 4,52 |
| All-time (corrigido) | R$ 27.647,70 | ~243 | R$ 113,78 | R$ 97.200 | 3,52 |

Custo por paciente que efetivamente realiza: **R$ 425 a R$ 443**. Contra LTV de
R$ 2.000, o payback não é imediato - a 1ª sessão (R$ 250) não cobre a aquisição;
break-even por volta da 2ª sessão, ~2 meses após o clique.

## Por que não usamos `revenue_real` (ainda)

`revenue_real` segue no contrato do `snapshot.json` como receita **confirmada**, mas está
suspenso até existir fonte de verdade para "o paciente realizou a sessão". Dois bloqueios
identificados em 2026-08-12:

1. **A definição atual conta no-show como conversão.** A regra da Fatia 0 (`appointments.status
   = 'CONFIRMED'` com `appointment_date` no passado), também usada pelo `ConversionUploader`,
   assume que dia passado = sessão realizada. No cruzamento com a base real da clínica, as duas
   únicas pacientes com agendamento `CONFIRMED` passado (Alyne, 2026-04-15; Rebeca, 2026-04-28)
   **não realizaram o procedimento**. O schema do scheduler não tem estado de comparecimento.
2. **A base do scheduler está dessincronizada.** Cobertura de `scheduler.patients` sobre a base
   real da clínica caiu de 95,4% (mar/2026) para 0% (jul e ago/2026). Nenhum paciente novo entra
   no scheduler desde julho.

Enquanto isso não for resolvido, qualquer ROAS/CPA calculado sobre `lead_conversions` é
inválido - não por falta de volume, mas por erro de sinal.
