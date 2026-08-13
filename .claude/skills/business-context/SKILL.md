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

### Fonte primária: base de pacientes do sistema da clínica

Export de 2026-08-12, 329 pacientes. É a **única fonte com idade real de quem vira
paciente** - `scheduler.patients` e `scheduler.leads` não têm data de nascimento.

- **Gênero: 90,4% feminino** (227 F / 24 M entre os 251 com registro; 78 sem preenchimento).
- **Idade: média 31,5 anos** (mín. 18, máx. 73), n=251.

| Faixa | Pacientes | % |
|---|---|---|
| 18-24 | 50 | 19,9% |
| **25-34** | **130** | **51,8%** |
| 35-44 | 53 | 21,1% |
| 45-54 | 9 | 3,6% |
| 55-64 | 7 | 2,8% |
| 65+ | 2 | 0,8% |

- **Região:** DDD 11 (São Paulo capital / Grande SP) = 201 de 269 telefones válidos
  (**74,7%**). Resto pulverizado no interior de SP (19-Campinas, 12-Vale do Paraíba,
  16-Ribeirão Preto) e outros estados. Sem segundo polo relevante.

> **Contaminação conhecida - excluir dos baselines:** 51 dos 329 registros (15,5%) têm
> DDD 74 (Bahia), todos cadastrados entre 24/04 e 14/05/2026, **todos sem idade e sem
> sexo**, nenhum presente no scheduler, vários com o sobrenome "Dourado" (o mesmo da LP
> `draclaradourado.com.br`). Têm cara de carga manual de contatos pessoais, não de
> pacientes adquiridos por campanha. Os números de idade/gênero acima já os excluem
> naturalmente (vêm vazios); os de DDD foram calculados sem eles.

> `HowDidMeet` está vazio em 328 dos 329 registros - não serve como fonte de atribuição.

### Fonte secundária: Google Ads (quem clica)

`age_range_view` / `gender_view`, `customer=4601912200`, histórico completo até 2026-08-12.
Reflete quem clica no anúncio, não quem vira paciente.

- Gênero: 61% feminino, 19% masculino, 20% indeterminado.
- Faixa etária: ~20% do tráfego fica "indeterminado" (Google não identifica idade).

### O gap entre o que a campanha compra e quem converte

Comparação por **cliques**, ambos os lados excluindo "indeterminado":

| Faixa | Cliques no Ads | Pacientes reais | Leitura |
|---|---|---|---|
| 18-24 | 22,2% | 19,9% | equilibrado |
| **25-34** | 32,3% | **51,8%** | **converte ~1,6x acima da fatia comprada** |
| 35-44 | 23,9% | 21,1% | equilibrado |
| 45-54 | 15,0% | 3,6% | converte ~4x abaixo |
| 55-64 | 5,6% | 2,8% | converte 2x abaixo |
| 65+ | 1,0% | 0,8% | irrelevante |

**45+ consome 21,6% dos cliques e entrega 7,2% dos pacientes.** É a alavanca mais direta
de ajuste de lance por faixa etária identificada até agora.

No gênero o gap é ainda maior: 61% dos cliques são femininos, mas 90,4% dos pacientes.
Mulheres convertem em taxa bem superior depois do clique.

### Funil medido (leads da LP x base real da clínica, 2026-08-12)

| Etapa | Qtd | Taxa |
|---|---|---|
| Leads reais únicos (sem teste/interno) | 91 | - |
| viraram paciente | 25 | 27,5% |
| **realizaram o procedimento** | **21** | **23,1%** |

Recorte só de `origem=depilacao`, que é o que a campanha alimenta: **21 de 82 = 25,6%**.
Dos 9 leads reais de `origem=harmonizacao`, **nenhum** virou paciente.

### Fonte obsoleta: `scheduler.patients`

Não usar para perfil demográfico. É um snapshot congelado: a cobertura sobre a base real
da clínica caiu de 95,4% (mar/2026) para 0% (jul e ago/2026). Números antigos desta skill
(84% feminino, 75% DDD 11) vinham daí e foram substituídos pelos da base primária.

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
