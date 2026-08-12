---
name: business-context
description: Contexto de negócio da Essência (depilação a laser) para análise e otimização de campanhas Google Ads — orçamento, público-alvo, diferenciais e alvos de ROAS/CPA/CTR. Use ao analisar ou recomendar mudanças em campanhas da Essência.
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

## Alvos

- ROAS alvo: **2.0** (definido pelo dono do negócio)
- CPA alvo: **R$ 78,00** (definido pelo dono do negócio)
- CTR alvo: **0.052** (~5,2%, calculado a partir do baseline real - ver nota abaixo)

> ROAS e CPA acima são metas operacionais definidas pelo dono do negócio, não o
> baseline calculado (que veio vazio - ver nota). CTR segue vindo do baseline
> real do `snapshot.json`, por enquanto sem meta definida pelo dono.
>
> **Nota sobre o baseline calculado em `analysis/`:** no pull rodado em
> 2026-08-09 contra prod (`customer=4601912200`, período de 90 dias:
> 2026-05-11 a 2026-08-09), o ROAS/CPA do baseline vieram vazios porque a
> coorte histórica de conversões reais (`scheduler.lead_conversions` cruzado
> com `appointments` `CONFIRMED` e já ocorridos) está vazia para essa clínica
> no banco de produção no momento desse pull — só 3 leads no período, 2 com
> `gclid`, e nenhuma conversão confirmada e já ocorrida ainda. Rode
> `python -m analysis.pull --customer 4601912200 --period 90d --stage prod`
> de novo depois que houver mais agendamentos confirmados no passado, para
> obter um baseline com sinal real.
