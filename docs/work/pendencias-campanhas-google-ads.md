# Pendências das campanhas Google Ads - Essência e Nobre Laser

> Lista viva. Atualizada em **08/11/2026** ao fim da sessão de auditoria.
> Para retomar: abra este arquivo e o PRD 040 (`docs/work/prd/040-landing-page-nobre-do-clique-ao-whatsapp.md`).
> Contas: Essência `460-191-2200` (clinic_id `clinicaessenciaestetica-9668a4`), Nobre `524-665-3188` (`nobrelaser-sjc`), MCC `287-835-6629`.

Legenda: ✅ feito · 🟡 parcial · ⬜ pendente · ❌ descartado · ⏸️ cancelado por decisão

---

## Sequência recomendada

1. **I2 → I3** - credencial de produção. Sem isso, a conversão offline segue morta e tudo quebra de novo em ~15/11.
2. **N4** - bot abre conversa com lead de LP sem mensagem. Três em cada quatro leads da Nobre somem sem contato.
3. **I6** - webhook parar de criar lead `whatsapp` para paciente/equipe. Nenhum número de lead da Nobre é confiável até lá.
4. **E7** - negativas da Essência (R$222/mês, lista pronta, zero risco).
5. **E2 / N8** - metas de conversão licitáveis, quando o fluxo offline tiver 2-3 semanas de dado novo.
6. **N15 e I4** - conferências de 5 minutos no dia seguinte.

---

## Infraestrutura (afeta as duas contas)

| # | Item | Status | Situação / próximo passo |
|---|---|---|---|
| I1 | Credencial do MCP (`C:/Users/andre/google-ads-adc.json`) | ✅ | Token gerado com `infra/src/scripts/generate_refresh_token.py` em 08/11; ADC montado e validado (adwords + datamanager) |
| I2 | Token de prod no SSM revogado → cron mensal de conversão offline parado | ⬜ | `aws ssm put-parameter --name /prod/GOOGLE_ADS_REFRESH_TOKEN` (e `/dev/`) com o token de `infra/src/scripts/tokens/google_ads_refresh_token.txt`, depois `serverless deploy` do `infra/` em dev e prod (nunca em paralelo). O `${ssm:}` resolve no deploy |
| I3 | Durabilidade do token: app OAuth em **Testing** = refresh token expira em 7 dias | ⬜ | Vence ~15/11. Opções: User Type **Internal** (se a conta que administra a MCC for Google Workspace - elimina tudo) ou publicar o app em External (grátis; pede domínio verificado no Search Console; `*.vercel.app` não serve). Tokens gerados em Testing continuam de 7 dias mesmo após publicar - gerar de novo depois |
| I4 | Backlog de conversões offline enviado manualmente em 08/11 | ✅ | Essência 15 compras + 30 agendamentos; Nobre 3 agendamentos. API aceitou, banco marcado (`uploaded_at`/`booking_uploaded_at`). **Conferir** em `offline_conversion_upload_conversion_action_summary` se os contadores saíram de 8/30 (23/10) para 23/60. Se não subiram: limpar as marcações e reenviar |
| I5 | ROAS por coorte de clique (09/10-07/11) | ✅ | Essência 1,35 total / 1,09 confirmado; Nobre 0,24 / 0,12 |
| I6 | Webhook cria lead `source=whatsapp` para **qualquer** número que escreve (`scheduler/src/functions/webhook/handler.py` ~267) | ⬜ | Desde 31/10 (z-api movida para a Nobre) toda conversa existente virou "lead": dos 59, 14 já eram pacientes, 13 são ruído (emprego, lembretes, mensagens para o André). Não criar lead para telefone que já é paciente ou da equipe; limpar linhas desde 31/10 |
| I7 | `scheduler.leads.raw_message` guarda CPF/nascimento/e-mail quando a paciente manda cadastro pelo WhatsApp | ⬜ | PII em texto livre; só registrado. `raw_message` também é sobrescrito a cada mensagem (não é "primeira mensagem") |

---

## Essência - 460-191-2200 (campanha `[Gestor]Depilacao_primeira_jardins`)

| # | Gargalo | Status | Situação / próximo passo |
|---|---|---|---|
| E1 | Medição offline morta desde 23/10 (último upload 23/10 18:45) | 🟡 | Backlog subiu (I4); recorrência depende de I2 |
| E2 | Campanha otimiza para formulário, não agendamento | ⬜ | **Não basta promover `primary_for_goal`**: em `campaign_conversion_goal` só `SUBMIT_LEAD_FORM` é `biddable`. Conserto: ligar `BOOK_APPOINTMENT` e desligar `SUBMIT_LEAD_FORM` nas metas da campanha 23449039185. Reinicia aprendizado. Pré-requisito: I2 funcionando |
| E3 | QS 4 na keyword `depilação definitiva` (79% do gasto); 44% de IS perdido por ranking | ⬜ | Causa: única keyword genérica + frase com expansão de significado = coletor de 9 intenções. Desenho pronto: G1 núcleo, G2 proximidade (CPA R$54,80), G3 pague por sessão, G4 masculino (CPA R$21,98). André optou por não reestruturar agora (não reiniciar aprendizado) |
| E4 | Horário 14h/18h/0h com R$770 e 3 conv | ❌ | Ação inválida: Smart Bidding ignora ajuste de lance por horário. Só exclusão funcionaria e o dado é fino |
| E5 | Grupo `Tecnologia` CPA 53% acima | ✅ | `depilação a laser sem dor` e `laser diodo` pausadas; `[soprano ice platinum]` exata criada (critério 318203369699) |
| E6 | `depilação a laser virilha` R$67, 0 conv, QS 3 | ✅ | Pausada |
| E7 | Vazamento geográfico e informacional nos termos (R$222/mês) | ⬜ | Negativar na campanha: `moema`, `vila mariana`, `vila prudente`, `zona norte`, `brooklin`, `pinheiros`, `campo limpo`, `tiete plaza`, `mooca`, `jabaquara`, `cotia`, `são bernardo`, `bragança`, `dermatologista`, `fiber`, `nd yag`, `onde fazer`, `melhor laser`, `loiras`, `pelo loiro`, `pelo branco`, `black friday`, `infinit`. **Manter** `perdizes` (2 conv). Adicionar variantes sem acento (`graça`/`grátis` estão sozinhas) |
| E8 | "Preço/sessão avulsa" tratado como desperdício | ❌ | Erro de leitura: é o diferencial da clínica ("Pague Só Por Sessão" no anúncio; `depilação laser avulsa` CTR 15%). Virou oportunidade de grupo (E3/G3) |
| E9 | Público masculino CPA R$22 sem grupo próprio | ⬜ | Melhor CPA da conta com 2,4% do gasto. Depende de E3 |
| E10 | 6 ações legadas de Smart Campaign como primárias | ❌ | API recusa (`MUTATE_NOT_ALLOWED`) e é desnecessário: categorias já `biddable: false` na campanha |
| E11 | Anúncio órfão em grupo removido | ✅ | Pausado |
| E12 | Valor de conversão fixo R$100 → ROAS do painel é ficção | ⬜ | Resolve quando o valor real fluir pela conversão offline (E1/E2) |
| E13 | Um só anúncio no grupo que leva 87% do gasto | ⬜ | Anúncio rico (30 títulos), mas sem variante. Junto com E3 |

---

## Nobre Laser - 524-665-3188 (campanha `Leads-SJC-Site`)

| # | Gargalo | Status | Situação / próximo passo |
|---|---|---|---|
| N1 | Funil pós-formulário: 800 cliques → 101 form → 96 leads → 8 agendamentos → 4 confirmados | 🟡 | Formulário agora abre o WhatsApp (nova aba) com `(ref: gclid)` - PRs #5/#6 em `rodsebaiano-bot/noble-laser-capture`, no ar, E2E verificado. Falta N4 |
| N2 | Página de destino "abaixo da média", QS 2-3, 44-48% de IS perdido por ranking | 🟡 | Todos os anúncios ativos caem em `/depilacao-a-laser-sjc` (convertia 2,2x a home); preço unificado R$50. Falta: performance (LCP 4,3 s; home 4,9 MB com 2 MP4; fontes 123 KB; contraste AA) e medir QS em 4 semanas |
| N3 | Anúncio promete "Agende pelo WhatsApp", página não tinha WhatsApp | ✅ | |
| N4 | 90 de 115 leads da LP nunca contatados; bot contatou 25 (mediana 13 h) com 0 agendamentos | ⬜ | **Maior item aberto.** Disparo automático foi removido em 05/09 (`elegibilidade_do_bot.py`). Proposta: bot abre conversa para lead `landing-page` sem mensagem em N min, com as travas que já existem. Antes, ler as 25 conversas e refazer o texto da primeira mensagem |
| N5 | Atribuição no WhatsApp direto | ✅ | `(ref:)` em toda URL via `linkWhatsApp`. Hipótese "caminho direto converte mais" **refutada** (6 de 59 leads `whatsapp` vinham da LP) |
| N6 | `whatsapp_click` no envio do formulário | ✅ | Disparando. GTM `GTM-WTPMSJ2R`: `lead_form_submit` → AW-18451988965/5IMJCKCjl_kcEOWDzN5E; `whatsapp_click` → AW-18451988965/JIvCCM-8sqEdEOWDzN5E (lido do container). Passa a contar ~1:1 com formulário |
| N7 | Relatório inflado 2,4x (visita ao site, rota, engajamento como primárias) | ⬜ | Não afeta lance (`biddable: false`). Só pelo painel |
| N8 | Sem action de `PURCHASE` (`offline_conversion_action_id` nulo); `BOOK_APPOINTMENT` secundária e `biddable: false` | ⬜ | Criar com `cria_conversion_action.py --compra`. Promoção só após N4 e I2 |
| N9 | `[depilação a laser sjc]` exata | ✅ | Criada em 08/11 (+ variante sem acento, redundante) |
| N10 | Keywords locais expandidas | ✅ | `[laser sjc]`, `[depilação sjc]`, `[depilação a laser são josé dos campos]`, `"depilação a laser jacarei"` no grupo SJC. Em 7-10 dias: se termos locais seguirem saindo por `depilação definitiva`, negativar `sjc` naquele grupo |
| N11 | Desperdício nos termos | ✅ | 15 negativas (taubaté, caçapava, led, fotodepilação, hakon, testículos, variantes sem acento de concorrentes). Deixados de fora com motivo: `jacarei` (3 conv), `ana hickmann` (1 conv), `yag` (Soprano usa Nd:YAG) |
| N12 | Anúncio AVERAGE no grupo que mais gasta (`SJC e sessão avulsa`) | ⬜ | Segunda variante de RSA |
| N13 | tCPA R$54,75 nunca batido (CPA real R$65,62) | ⬜ | Ajustar só depois de N2 refletir no QS |
| N14 | Grupo `Geral` pausado (48,8% do gasto histórico) | ⬜ | Anúncios dele corrigidos em 08/11, não veiculam. Decidir se volta |
| N15 | 3 anúncios editados + 6 keywords novas em revisão | ⬜ | Conferir aprovação em 09/11 |
| N16 | `AGENTS.md` da LP desatualizado | ✅ | PR #6 mergeado; regra: muda no mesmo PR do comportamento |
| N17 | Grupo de anúncio `Masculino` | ⏸️ | 47 operações validadas pela API em 08/11 (grupo, 15 keywords, RSA 15/4, 4 sitelinks, negativas de roteamento, pausa de 2 keywords) e **cancelado pelo André antes de aplicar**. Desenho em `docs/work/pendencias-campanhas-google-ads.md` §Anexo |
| N18 | Seção/página masculina na LP | ⬜ | Pré-requisito natural de N17 (`AreasDestaqueSjc` foi removida; página não tem sinal masculino além da tabela). PRD 040 §3.B fase 2 |

---

## Documentação

| Item | Status |
|---|---|
| PRD 040 - landing page da Nobre | 🟡 Escrito e corrigido (§2.6 refutada); **untracked em `main`** - precisa de branch + PR |
| Este arquivo | criado em 08/11, untracked |
| Memória do agente | `project_nobre_landing_page_08_11.md` (estado e pendências), `project_acesso_aws_traffic_manager.md` (credenciais) |

---

## Anexo - desenho do grupo `Masculino` (N17, cancelado)

Para não refazer do zero se voltar à pauta.

**Keywords (15):** `[depilação a laser masculina]` + frase · `[depilação masculina]` + frase · `[depilação masculina sjc]` · `"depilação a laser homem"` · `"depilação a laser para homens"` · `"laser masculino"` · `[barba a laser]` + frase · `"depilação a laser barba"` · `"tirar barba a laser"` · `"contorno de barba a laser"` · `"depilação a laser costas"` · `"depilação a laser peito"`.
Evidência: Essência `depilação a laser masculina` 1 conv CTR 10%, `costas masculina` 1 conv, `barba depilação a laser` 1 conv; Nobre `tirar barba a laser` 1 conv, `depilação masculina sjc` 1 conv, `depilação masculina` em frase com QS 1 (anúncio errado).

**Negativas no grupo:** `íntima`, `intima`, `virilha`, `feminina`, `feminino` (Nobre não faz íntima masculina).
**Roteamento:** negativas em frase nos outros grupos (`masculina`, `masculino`, `homem`, `homens`, `barba`); pausar `depilação masculina` (2003781558) e `barba a laser` (303608683867) no grupo SJC.

**RSA** - fixados H1: `Depilação a Laser Masculina` · `Laser Masculino em SJC` · `Barba, Costas e Peito a Laser`. Demais: `Contorno de Barba a Laser` · `Barba Completa a Laser` · `Costas e Ombros Sem Pelos` · `Peito e Abdômen a Laser` · `Menos Foliculite na Barba` · `Contorno de Barba por R$100` · `Pague Só a Sessão Realizada` · `Sessão Avulsa, Sem Pacote` · `Praticamente Indolor` · `Soprano Ice Platinum` · `Agende Agora pelo WhatsApp` · `Clínica no Jardim Aquarius`.
Descrições: (1) *Laser masculino em SJC: barba, costas, peito e abdômen. Sem pacote, você paga só a sessão.* (2) *Contorno de barba R$100, barba completa R$130, costas R$200. Pague só a sessão que fez.* (3) *Soprano Ice Platinum, praticamente indolor e seguro para pele negra. Sala privativa.* (4) *Menos foliculite e pelo encravado na barba. Agende pelo WhatsApp e pague só a sessão.*
Path `masculina/sjc`, destino `/depilacao-a-laser-sjc`. Preços de `src/lib/pricing.ts` da LP.

**Sitelinks do grupo:** Barba a Laser · Costas, Peito e Ombros · Valores por Área (→ `#precos`) · Agende pelo WhatsApp (→ `#lead`).

**Ressalvas registradas:** a página não tem seção masculina; grupo novo nasce sem histórico; `barba` como negativa nos outros grupos bloqueia buscas femininas raras com a palavra.
