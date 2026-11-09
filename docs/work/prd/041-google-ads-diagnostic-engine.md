# PRD - 041 Google Ads Diagnostic Engine

> Gerado na fase **Research** em 08/11/2026. Use como input para a fase Spec.
> Contas no escopo: Essência `460-191-2200` (Dra. Clara Dourado, clinic_id
> `clinicaessenciaestetica-9668a4`) e Nobre Laser `524-665-3188`
> (`nobrelaser-sjc`), ambas sob a MCC `287-835-6629`.

---

## 1. Objetivo

Construir, dentro do `infra/`, um motor de diagnóstico **somente leitura** e
**determinístico** que analisa todo dia as contas de Google Ads das clínicas e
responde, com evidência numérica: o que vai bem, o que vai mal, onde está o
gargalo, por que ele existe, que oportunidade há, quanto ela vale em reais e o
que atacar primeiro.

O motor não é um relatório de métricas. É a camada de inteligência que um
futuro agente de otimização vai consumir: cada diagnóstico sai estruturado,
persistido, com histórico, nível de confiança e rastro até a consulta que o
originou. Nenhum cálculo e nenhuma detecção primária passa por LLM.

O resultado esperado da v1: rodar sozinho, todo dia, e reproduzir sem ajuda
humana os achados da auditoria manual de 08/11/2026
(`docs/work/pendencias-campanhas-google-ads.md`), sem os dois erros de leitura
que ela cometeu (E4 e E8) e sem gerar alerta que a amostra não sustenta.

**Princípio:** cada diagnóstico é explicável, reproduzível, rastreável e
economicamente relevante. Preferimos 10 diagnósticos certos a 60 alertas.

---

## 2. Contexto

### 2.1 Por que agora

A gestão das duas contas é feita hoje em sessões de auditoria manual. A de
08/11 produziu 38 itens e errou dois: tratou ajuste de lance por
horário como ação válida sob Smart Bidding (E4) e classificou "sessão avulsa"
como desperdício quando é o diferencial da clínica (E8). Entre uma sessão e
outra ninguém olha: a medição offline da Essência ficou morta de 23/10 a 08/11
sem que nada avisasse (E1), e o orçamento da Nobre mudou seis vezes em 30 dias,
uma delas feita pelo próprio Google (ver §2.4).

### 2.2 Diagnóstico da infraestrutura existente

Levantamento do `infra/` em 08/11/2026.

**O que existe e será reutilizado**

| Peça | Onde | Uso no motor |
|---|---|---|
| Cliente Google Ads via MCC | `infra/src/functions/googleads/utils.py:63` `create_google_ads_client()` + `infra/src/services/google_ads_config.py:31` | Único caminho vivo de autenticação. Credenciais do SSM (`MCC_DEVELOPER_TOKEN`, `OAUTH2_CLIENT_ID/SECRET`, `MCC_ACCOUNT_ID`, `GOOGLE_ADS_REFRESH_TOKEN`), `login_customer_id` = MCC |
| SDK | `google-ads==31.2.0`, sem versão de API fixada (regra imposta por `infra/tests/unit/test_sem_versao_fixa_da_api.py`) | Mantém a regra |
| Postgres (Supabase) | `infra/src/services/postgres_service.py` (pool, `execute_query`, `execute_many`, `transaction`) | Persistência do motor. Já lê o schema `scheduler` |
| Vínculo clínica x conta | `scheduler.clinics.google_ads_customer_id` | Fonte única de "que contas analisar" |
| Verdade do negócio | `scheduler.leads` (gclid) e `scheduler.lead_conversions` (agendamento, compra, valor, retração) | Separar conversão contada de cliente adquirido |
| Lambda em imagem Docker, cron EventBridge, `http_response`, `require_api_key`, `log_step` | `infra/serverless.yml`, `infra/src/utils/` | Execução, rotas e log |

**O que existe e não serve de base**

| Peça | Problema verificado |
|---|---|
| `optimizer/generate_recommendations.py` (cron diário às 9h UTC, ativo) | Lê CPA de `get_campaign_from_google_ads`, cuja GAQL não tem filtro de data (`utils.py:144-155`), e grava `period: {days: 30}` (`:119`). O CPA comparado com a meta é o de toda a vida da campanha. A regra é uma tabela de 5 faixas de razão CPA/meta, sem amostra mínima |
| `metrics/collector.py` | Não está no deploy (`sls/functions/metrics/interface.yml` fora do `serverless.yml`). Grava em ExecutionHistory, que não é série temporal |
| `GoogleAdsClientService` (`services/google_ads_client_service.py`) | Depende de `Clients.googleAdsConfig`, que nenhum código grava. Tem métodos de leitura úteis como referência de GAQL, misturados com mutações (`add_negative_keywords`, `pause_campaign`, `update_ad_group_cpc`) |
| `keywords/analyze_negatives.py` e `analyze_expansion.py` | A decisão é do OpenAI (`gpt-4.1`). O oposto do requisito |
| DynamoDB `Clients.optimizationConfig` | Tem metas econômicas (`average_ticket`, `net_margin`, `healthy_cpa`...), mas `clientId` não tem chave para `clinic_id`. Não há como chegar dela à conta sem tabela de-para |

**O que não existe**

- Histórico de métricas. Nada no projeto guarda série diária.
- DDL ou migração no `infra/` (o padrão idempotente vive em
  `scheduler/src/scripts/setup_database.py`).
- Dependência científica (numpy, scipy, pandas, statsmodels). Base da imagem:
  `public.ecr.aws/lambda/python:3.9`.
- CI. Não há `.github/`. O `infra/` tem 3 testes unitários rodados à mão.
- Timeout padrão nas Lambdas (vale o default de 6 s do Serverless).

**Achado de segurança, fora do tema mas verificado:**
`infra/src/services/google_ads_mcc_service.py:34` faz
`print(f"Configuração do cliente MCC: {config}")`. O dict contém
`developer_token`, `client_secret` e `refresh_token`, que vão em claro para o
CloudWatch. Corrigir em PR próprio antes deste (ver §5).

### 2.3 Inventário do MCP e da Google Ads API

**MCP `google-ads-mcp`** (inspecionado em 08/11): três ferramentas, todas de
leitura.

| Ferramenta | O que faz |
|---|---|
| `list_accessible_customers` | Devolve os IDs acessíveis à credencial (hoje `1570932315`, `2878356629` = MCC, `8331526637`). As contas das clínicas são alcançadas por baixo da MCC |
| `get_resource_metadata(resource_name)` | Campos selecionáveis, filtráveis e ordenáveis de um recurso |
| `search(customer_id, resource, fields, conditions, orderings, limit)` | GAQL estruturado. Datas sempre explícitas (`BETWEEN`), sem literais como `LAST_30_DAYS` |

Papel de cada um: o **MCP é ferramenta de desenvolvimento e investigação**
(validar campo, conferir número, explorar hipótese numa sessão). O **motor em
produção usa o SDK** dentro da Lambda, pelo caminho MCC que já existe. Não há
segunda integração: é o mesmo OAuth, o mesmo developer token, a mesma MCC.

Limitação encontrada: `search` em `change_event` com
`change_event.changed_fields` falha (`Unable to serialize unknown type:
FieldMask`). Sem esse campo a consulta funciona. O detalhe do que mudou
(`old_resource`, `new_resource`, `changed_fields`) só sai pelo SDK.

**Recursos da API por finalidade.** Consultados nesta pesquisa, em 08/11:
`campaign`, `campaign_budget`, `customer`, `conversion_action`, `keyword_view`,
`search_term_view`, `change_event` e o segmento `conversion_lag_bucket`. Os
demais sem asterisco foram usados na auditoria de 08/11 (PRD 040 e lista de
pendências). Os marcados com * ainda não foram exercitados neste projeto:

| Finalidade | Recurso | Observação |
|---|---|---|
| Conta, campanha, orçamento, estratégia | `customer`, `campaign`, `campaign_budget` | `optimization_score`, parcelas de impressão |
| Grupo | `ad_group` | |
| Keyword e qualidade | `keyword_view`, `ad_group_criterion` | `quality_info.*`. QS vem 0 quando não há dado (4 das 13 keywords da Essência) |
| Termos de pesquisa | `search_term_view` | Só termos acima do limiar de privacidade |
| Anúncios e ativos | `ad_group_ad`, `ad_group_ad_asset_view`* | `ad_strength`, `policy_summary` |
| Página de destino | `landing_page_view`*, `expanded_landing_page_view` | `speed_score` veio 0 (sem volume) na Nobre |
| Conversão | `conversion_action`, `campaign_conversion_goal`, `offline_conversion_upload_conversion_action_summary` | Ver §2.4 |
| Clique a clique | `click_view`* | gclid, keyword, dispositivo, local. Um dia por consulta, só 90 dias |
| Alterações | `change_event` | Só 30 dias, `LIMIT` ≤ 10.000 |
| Segmentos | `segments.date`, `day_of_week`, `hour`, `device`, `ad_network_type`, `conversion_action`, `conversion_lag_bucket`; `geographic_view`*, `user_location_view`*, `ad_group_audience_view`* | Compatibilidade varia por recurso |

A Spec deve confirmar cada campo com `get_resource_metadata` antes de escrever
a consulta. **Nenhum campo entra no código por memória.** Restrições conhecidas
a validar lá: parcela de impressões não existe em anúncio nem em termo de
pesquisa; `segments.hour` não combina com `search_term_view`;
`segments.conversion_action` não combina com custo e cliques; Informações do
leilão (concorrentes) não fazem parte da API padrão.

### 2.4 O que as contas dizem (09/10 a 07/11/2026, 30 dias)

| | Essência | Nobre |
|---|---|---|
| Campanhas ativas | 1 de 6 (`[Gestor]Depilacao_primeira_jardins`, Search, Maximizar conversões) | 1 de 3 (`Leads-SJC-Site`, Search, Maximizar conversões) |
| Impressões / cliques | 10.006 / 562 | 8.473 / 546 |
| Custo | R$ 5.017,16 | R$ 4.737,55 |
| Conversões (formulário) | 76 (CVR 13,5%) | 79 (CVR 14,5%) |
| Parcela de impressões | 48,6% | 49,8% |
| Perdida por ranking / orçamento | 44,0% / 7,4% | 46,6% / 3,6% |
| Optimization score | 0,65 | 0,75 |
| Keywords com impressão | 13 (uma delas com 79% do custo) | - |

Cinco fatos que definem o desenho:

1. **O volume é baixo e concentrado.** São de 0 a 6 conversões por dia. Na
   Essência, dos ~125 termos de pesquisa com clique no período, a grande
   maioria tem 1 clique; só um passa de 25. Estatística por entidade na
   granularidade fina quase nunca fecha. O motor precisa agregar (semana,
   n-grama, grupo) e dizer "sem volume" com frequência.
2. **Zero conversão raramente é evidência.** Com CVR de 13,5%, a chance de ver
   zero conversão em *n* cliques por puro acaso é 0,865^n. Só cai abaixo de 5%
   com **21 cliques** (20 na Nobre). As keywords pausadas em 08/11 por "0
   conversão" tinham 7 e 9 cliques: probabilidade de acaso de 36% e 27%. A
   pausa pode ter sido certa por outros motivos (QS 3, custo), mas a ausência
   de conversão não era um deles.
3. **A conversão que o Google conta não é a que o negócio quer.** As duas
   campanhas otimizam para formulário. Agendamento e compra chegam por upload
   offline, são secundárias e não licitáveis. Na Essência, "Lead - Formulário"
   tem valor fixo de R$ 100 (ROAS do painel é ficção) e seis ações herdadas de
   Smart Campaign seguem como primárias. Na Nobre, quatro "Local actions" são
   primárias. O ROAS por coorte de clique, cruzado com o banco, foi 1,09 na
   Essência e 0,12 na Nobre. O motor precisa das duas visões lado a lado.
4. **O atraso de conversão depende da ação.** Na Essência, 171 de 174
   conversões de formulário em 90 dias aconteceram em menos de um dia após o
   clique. Já agendamento e compra têm janela de 90 dias e sobem em lote
   mensal. Maturidade é propriedade da ação de conversão, não da conta.
5. **As contas mudam sem registro nosso.** Na Nobre, `change_event` mostra seis
   alterações de orçamento em 30 dias (22/10, 27/10, 30/10 e três em 03/11),
   uma delas com `client_type = GOOGLE_ADS_RECOMMENDATIONS`. O orçamento hoje é
   R$ 65/dia. A API só guarda 30 dias desse histórico: o que não for
   coletado se perde.

Há ainda um caso de teste natural: na Essência, de 23 a 26/10 o custo diário
caiu de ~R$ 200 para R$ 32 a R$ 100 e voltou. A causa não foi apurada. É o tipo
de pergunta que o motor deve responder sozinho.

### 2.5 Referência oficial do Google

A página indicada (`answer/6146252`) é o índice do guia. As regras operacionais
estão nas páginas que ela aponta, e viram **regras de referência** do motor,
sempre subordinadas à evidência da própria conta:

| Diretriz oficial | Fonte | Como entra no motor |
|---|---|---|
| 2 a 3 anúncios responsivos por grupo; eficácia "Boa" ou "Excelente" | `answer/7507883`, ponto 1 | Detector de cobertura criativa (Módulo 4). Eficácia nunca sozinha: só com CTR e CVR |
| Títulos alinhados a keyword e página de destino | `answer/7507883`, ponto 1 | Coerência keyword x anúncio x página, lida pelos três componentes do QS |
| Vários tipos de recurso (sitelinks, frases, chamada) | `answer/7507883`, ponto 2 | Checagem de recursos por campanha (Módulo 1) |
| Acompanhamento de conversões configurado; conversão online e offline | `answer/7507883` ponto 2; 12 sugestões, item 11 | Módulo 7 inteiro |
| Mistura de correspondências e negativas para filtrar pesquisa irrelevante | `answer/7507883`, ponto 3 | Módulo 3 |
| Fase de aprendizado de 5 a 7 dias; evitar alterações frequentes | `answer/7507883`, ponto 3 | Janela de quarentena após `change_event` de lance, orçamento ou meta: comparações que cruzam a janela são sinalizadas |
| Orçamento conforme desempenho | 12 sugestões, item 2 | Módulo 6 |
| Segmentação por local | 12 sugestões, item 4 | Vazamento geográfico (Módulos 3 e 5) |
| Simplificar a estrutura | 12 sugestões, item 8 | Fragmentação (Módulo 1) |
| Testar | 12 sugestões, item 12 | Fora da v1 (o motor não cria experimento); a saída aponta candidatos |

O *optimization score* e a página Recomendações do Google são coletados como
dado, nunca como veredito: a recomendação do Google que mudou o orçamento da
Nobre em 03/11 é exatamente o tipo de evento que o motor deve registrar e
avaliar.

---

## 3. Escopo

### 3.1 Decisões de arquitetura

| # | Decisão | Motivo |
|---|---|---|
| D1 | O motor mora em `infra/src/diagnostics/`, pacote novo e isolado | É gestão de campanha, domínio do `infra/`. Isolado porque o resto do `infra/` mistura leitura e mutação |
| D2 | Persistência em **Postgres**, schema novo `ads` | Série temporal, comparação entre períodos e junção com `scheduler.lead_conversions` são SQL. DynamoDB não faz nenhuma das três bem |
| D3 | Contas vêm de `scheduler.clinics.google_ads_customer_id` | Fonte única que já existe e já é mantida |
| D4 | Metas econômicas em `ads.account_targets`, por `clinic_id` | `Clients.optimizationConfig` não tem chave para a clínica. Uma fonte só: o motor não lê o DynamoDB |
| D5 | Estatística em **Python puro** (`math`, `statistics`), sem numpy/scipy | Os métodos necessários (Wilson, binomial exata, Poisson, MAD, EWMA, CUSUM, reamostragem com semente) cabem em poucas centenas de linhas testáveis. Evita engordar a imagem e amarrar o motor ao Python 3.9 |
| D6 | Coleta diária **recoleta a janela inteira de 90 dias** e faz upsert | No volume destas contas são poucas centenas de linhas. Elimina lógica de "o que mudou" e absorve a reatribuição tardia de conversões |
| D7 | Somente leitura, **provada por teste** | Teste por AST garante que nada em `diagnostics/` referencia serviço de mutação nem importa `GoogleAdsClientService`. O único verbo de API permitido é `GoogleAdsService.search_stream` |
| D8 | Uma Lambda agendada, laço por conta, falha isolada por conta | Duas contas. Fila ou Step Function só se o número de contas exigir |
| D9 | Saída em JSON; relatório em Markdown gerado por código | Sem LLM em nenhum ponto. Narrativa por agente é consumo futuro |
| D10 | Detectores declarativos: cada um é uma função pura `(dados, config) -> diagnósticos` registrada num catálogo | Baixo acoplamento, teste por detector, liga e desliga por configuração |

### 3.2 Arquitetura

```
EventBridge (diário, 07:00 America/Sao_Paulo)
        |
        v
 DiagnosticsRunner (Lambda)                     somente leitura
        |
   para cada conta de scheduler.clinics
        |
  1. collect/      GAQL por entidade e finalidade  -->  Google Ads API (search_stream)
  2. normalize/    micros -> BRL, enums -> texto, fuso da conta
  3. store/        upsert em ads.* (fatos diários + fotos de configuração)
  4. metrics/      métricas derivadas com denominador protegido
  5. stats/        intervalos, testes, anomalias, mudança de regime
  6. detectors/    8 módulos -> achados brutos
  7. rootcause/    decomposição + árvore de hipóteses -> causa classificada
  8. opportunity/  achados positivos com faixa de impacto
  9. scoring/      prioridade 0-100, deduplicação por causa-raiz
 10. persist/      ads.diagnostics (ciclo de vida) + ads.diagnostic_runs
 11. report/       JSON consolidado + Markdown

 GET /diagnostics, /diagnostics/{id}, /diagnostics/report   (x-api-key)
```

As etapas 4 a 9 são funções puras sobre dados já gravados: um diagnóstico
pode ser recalculado para qualquer data passada com o mesmo resultado
(`as_of` é parâmetro, nunca `now()`).

### 3.3 Coleta (uma consulta por entidade e finalidade)

| Conjunto | Recurso | Grão | Frequência |
|---|---|---|---|
| C1 Conta e campanhas | `customer`, `campaign`, `campaign_budget` | foto diária de configuração | diária |
| C2 Desempenho de campanha | `campaign` x `segments.date` | dia | janela de 90 dias |
| C3 Campanha x dispositivo, x rede | idem + `segments.device` / `ad_network_type` | dia | janela de 90 dias |
| C4 Campanha x dia da semana x hora | idem + `segments.hour` | dia e hora | janela de 90 dias |
| C5 Campanha x ação de conversão | idem + `segments.conversion_action` (só métricas de conversão) | dia | janela de 90 dias |
| C6 Atraso de conversão | `segments.conversion_lag_bucket` por ação | acumulado de 90 dias | diária |
| C7 Grupos | `ad_group` x data | dia | janela de 90 dias |
| C8 Keywords | `keyword_view` x data + `quality_info` e componentes | dia; QS como foto | janela de 90 dias |
| C9 Termos de pesquisa | `search_term_view` x data, com keyword acionadora e correspondência | dia | janela de 90 dias |
| C10 Anúncios e ativos | `ad_group_ad`, `ad_group_ad_asset_view` | dia; textos e eficácia como foto | janela de 90 dias |
| C11 Páginas de destino | `landing_page_view` | dia | janela de 90 dias |
| C12 Local e público | `geographic_view`, `user_location_view`, `ad_group_audience_view` | semana | janela de 90 dias |
| C13 Ações e metas de conversão | `conversion_action`, `campaign_conversion_goal`, resumo de upload offline | foto diária | diária |
| C14 Negativas e recursos | `campaign_criterion`, `ad_group_criterion` negativos, `campaign_asset` | foto diária | diária |
| C15 Alterações | `change_event` (com `old_resource`/`new_resource`) | evento | últimos 30 dias, guarda para sempre |
| C16 Cliques | `click_view` | clique (gclid) | D-1 a D-3, guarda para sempre |

Regras da coleta:

- Toda linha carrega `run_id`, `collected_at` e o hash da GAQL que a gerou.
- Métricas de parcela de impressões vêm como `null` quando o Google devolve
  "< 10%"; nunca viram zero.
- Paginação por `search_stream`. Erros transitórios com retry exponencial (3
  tentativas); erro de cota ou de autenticação aborta a conta, registra em
  `ads.diagnostic_runs` e não gera diagnóstico (ausência de coleta nunca vira
  "queda de 100%").
- Orçamento de API: ordem de 20 a 30 consultas por conta por dia, mais uma por
  dia de `click_view`. Registrar o total por execução.
- Carga inicial: a API serve métrica histórica por data. A primeira execução
  busca 12 meses de C2 e 90 dias do resto, então as comparações funcionam no
  primeiro dia. Só as fotos (configuração, QS, alterações com mais de 30 dias,
  cliques com mais de 90) começam do zero.

### 3.4 Modelo de dados (schema `ads`)

| Tabela | Chave | Conteúdo |
|---|---|---|
| `ads.accounts` | `customer_id` | `clinic_id`, fuso, moeda, primeira e última coleta |
| `ads.account_targets` | `clinic_id` | `cac_maximo`, `cpa_alvo_lead`, `ticket_medio`, `margem_contribuicao`, `taxa_lead_agendamento`, `taxa_agendamento_compra`, pesos do score, calendário de eventos. Versionada por `valid_from` |
| `ads.entities` | (`customer_id`, `entity_type`, `entity_id`) | Nome e hierarquia atuais (campanha, grupo, keyword, anúncio, ação de conversão) |
| `ads.entity_snapshots` | (..., `snapshot_date`) | Foto de configuração em JSONB: status, lance, orçamento, QS e componentes, eficácia, textos, política. Gravada só quando muda (hash) |
| `ads.fact_daily` | (`customer_id`, `entity_type`, `entity_id`, `date`, `segment_type`, `segment_value`) | impressões, cliques, custo, conversões, valor, parcelas de impressão. `segment_type = 'none'` para o total |
| `ads.fact_conversion_daily` | (..., `date`, `conversion_action_id`) | conversões e valor por ação, por data do clique e por data da conversão |
| `ads.search_terms_daily` | (`customer_id`, `ad_group_id`, `search_term`, `keyword_id`, `match_type`, `date`) | métricas do termo |
| `ads.clicks` | `gclid` | data, campanha, grupo, keyword, dispositivo, local. Liga a `scheduler.leads.gclid` |
| `ads.change_events` | `change_resource_name` + `change_date_time` | tipo, operação, origem (`client_type`), antes e depois |
| `ads.diagnostic_runs` | `run_id` | conta, `as_of`, versão do motor, hash da configuração, consultas feitas, duração, status |
| `ads.diagnostics` | `diagnostic_id` | Ver §3.10 |
| `ads.diagnostic_observations` | (`diagnostic_id`, `run_id`) | O que o diagnóstico valia em cada execução (score, evidências). É o histórico de evolução |

DDL em `infra/src/scripts/setup_ads_schema.py`, no padrão do
`setup_database.py` do scheduler: lista única, tudo idempotente (`CREATE ... IF
NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, constraints em `DO $$`). Dev e prod
têm bancos separados; o script roda nos dois.

Retenção: fatos diários e eventos ficam para sempre (é o ativo que a API não
guarda). Volume estimado abaixo de 200 mil linhas por conta por ano.

### 3.5 Métricas derivadas

Camada única, usada por todos os módulos. CTR, CPC, CVR, CPA, ROAS, CPM, mais:

- **Demanda elegível** = impressões / parcela de impressões. Separa "o mercado
  encolheu" de "nós perdemos espaço".
- **Custo por agendamento e por compra reais**, e **ROAS real**, por coorte de
  clique: `ads.clicks` x `scheduler.leads` x `scheduler.lead_conversions`.
  Disponível por campanha, grupo, keyword, dispositivo.
- **Cobertura dos termos de pesquisa** = cliques visíveis em `search_term_view`
  / cliques da campanha. Todo diagnóstico de tráfego declara sobre que fração
  do gasto ele fala.

Toda métrica é um par (numerador, denominador), nunca um número solto: é isso
que permite agregar, calcular intervalo e recusar a conta quando o denominador
é zero ou pequeno. Divisão por zero devolve `None` com motivo, nunca 0 nem
infinito.

Toda métrica de conversão tem **maturidade**: fração esperada das conversões
finais já registrada, derivada da distribuição de atraso (C6) da ação de
conversão. Dias com maturidade abaixo do limiar configurado (sugestão: 90%)
ficam fora de comparações ou entram corrigidos e marcados.

### 3.6 Motor estatístico

O método é escolhido pelo tipo de métrica e pelo volume, não aplicado em bloco.

| Pergunta | Tipo de dado | Método | Quando não conclui |
|---|---|---|---|
| Esta taxa (CTR, CVR) é diferente daquela? | proporção | Intervalo de Wilson; teste de duas proporções; binomial exata quando o esperado é menor que 5 | Intervalos sobrepostos ou poder insuficiente |
| Zero conversões é sinal? | contagem rara | P(0 em n cliques) à CVR de referência (§2.4, fato 2) | P > 5% |
| CPA, CPC, ROAS mudaram? | razão de somas | Reamostragem por dia, em blocos de 7, com semente fixa | Intervalo da diferença contém zero |
| Hoje foi anormal? (impressões, custo, CPC, parcela) | série diária | Z robusto (mediana e MAD) contra o mesmo dia da semana nas 8 semanas anteriores | Menos de 6 pontos de referência |
| Conversões caíram? | contagem baixa | Poisson sobre semana cheia, nunca sobre um dia | Semana imatura |
| Houve mudança de patamar? | série | CUSUM sobre a série sem o efeito do dia da semana; data provável da quebra | Menos de 28 dias |
| Há tendência? | série | EWMA semanal e inclinação com intervalo | Menos de 6 semanas |
| A distribuição mudou? (mix de dispositivo, termos, horas) | composição | Distância entre participações + decomposição mix x taxa | Variação do mix abaixo do limiar |
| Este segmento é fora da curva? | muitos segmentos | Comparação contra o restante com controle de falsa descoberta (Benjamini-Hochberg) | Não sobrevive à correção |

Regras obrigatórias, valendo para todo detector:

1. Todo teste declara amostra mínima. Abaixo dela o resultado é
   `evidencia_insuficiente`, que é um resultado válido e persistido, não um
   silêncio.
2. Ausência de evidência não é evidência de ausência: "0 conversões em 7
   cliques" produz "sem volume para concluir", nunca "não converte".
3. Anomalia (um ponto) e deterioração (patamar ou tendência) são categorias
   diferentes, com detectores diferentes.
4. Nenhuma comparação cruza um período imaturo, incompleto, de carga inicial
   de campanha (primeiros 14 dias) ou de aprendizado (7 dias após alteração de
   lance, meta de conversão ou orçamento maior que 20%) sem carregar a
   limitação correspondente.
5. Sazonalidade: com menos de um ano de dado só o ciclo semanal é aprendido.
   Efeitos anuais e de calendário (Black Friday, feriados, fim de mês) vêm de
   um calendário configurado em `account_targets`. O que não dá para verificar
   é dito: "sazonalidade anual não verificável".
6. A **confiança** de um diagnóstico (0 a 1) é função documentada de três
   coisas: força estatística, maturidade do dado e cobertura (fração do gasto
   observada). Não é um número escolhido à mão por detector.

### 3.7 Módulos de diagnóstico

Catálogo da v1. "Adiado" quer dizer: o volume destas contas não sustenta hoje,
o detector fica especificado e desligado.

**M1 Estrutura**

| Detector | Evidência | v1 |
|---|---|---|
| Grupo ou keyword ativa sem impressão em 30 dias | fato diário | sim |
| Concentração: uma keyword com mais de X% do custo absorvendo intenções distintas | participação no custo + diversidade de termos acionados | sim |
| Keywords duplicadas ou sobrepostas entre grupos (mesmo termo servido por mais de uma) | termos x keyword acionadora | sim |
| Grupo com menos de 2 anúncios responsivos ativos | foto | sim |
| Anúncio ativo em grupo pausado ou removido; destino divergente dentro do mesmo grupo | foto | sim |
| Recursos ausentes (sitelink, frase de destaque, chamada) | foto | sim |
| Fragmentação excessiva | grupos com volume abaixo do mínimo de aprendizado | adiado |

**M2 Leilão**

| Detector | Evidência | v1 |
|---|---|---|
| Perda por orçamento | parcela perdida por orçamento sustentada + gasto próximo do teto | sim |
| Teto mensal atingido (orçamento diário x 30,4) explicando queda no fim do mês | gasto acumulado do mês x teto | sim |
| Perda por ranking, com o componente de QS responsável | parcela perdida por ranking + QS e componentes | sim |
| CPC em alta sem ganho de posição | CPC x parcela no topo | sim |
| Deterioração de competitividade | mudança de patamar na parcela de impressões com demanda estável | sim |

**M3 Tráfego**

| Detector | Evidência | v1 |
|---|---|---|
| Vazamento por tema (bairro, cidade, concorrente, informacional) | agregação por **n-grama** dos termos; custo e conversões do n-grama contra o resto | sim |
| Keyword com gasto e sem retorno | teste de zero conversões + conversão real | sim |
| Correspondência capturando intenção diferente da keyword | termo x keyword acionadora x tipo | sim |
| Termo rentável sem keyword própria | n-grama com CVR acima do resto e volume | sim |
| Candidata a negativa | só quando o n-grama passa no teste de amostra **e** não bate numa lista de proteção | sim |

A lista de proteção (`account_targets`) guarda os temas que são proposta da
clínica ("avulsa", "por sessão", "perdizes"...). É o que evita repetir o E8. O
motor nunca recomenda negativar pela ausência de conversão de um termo
isolado.

**M4 Criativo**

| Detector | Evidência | v1 |
|---|---|---|
| Cobertura criativa (um anúncio só no grupo que concentra o gasto) | foto + participação | sim |
| Componente "CTR esperado" ou "relevância do anúncio" abaixo da média nas keywords de maior gasto | QS | sim |
| Anúncio com CTR alto e CVR baixo em relação aos irmãos do mesmo grupo | duas proporções | adiado (um anúncio por grupo hoje) |
| Ativo com rótulo de desempenho baixo | `ad_group_ad_asset_view` | sim, só informativo |

Eficácia do anúncio entra como dado de contexto, nunca como achado isolado.

**M5 Conversão**

| Detector | Evidência | v1 |
|---|---|---|
| Página de destino com CVR inferior a outra da mesma conta | duas proporções por URL | sim |
| "Experiência na página de destino" abaixo da média | QS | sim |
| Diferença de CVR por dispositivo | duas proporções | sim |
| Queda abrupta de CVR | Poisson semanal + mudança de patamar | sim |
| Vazamento entre formulário e agendamento | lead x agendamento do banco, por coorte | sim |
| CVR por local e por hora | segmentos | adiado (células pequenas demais) |

**M6 Econômico**

| Detector | Evidência | v1 |
|---|---|---|
| Custo por agendamento e por compra reais acima do CAC máximo | coorte de clique x metas | sim |
| ROAS real abaixo do ponto de equilíbrio (margem) | idem | sim |
| Divergência entre o que o painel mostra e o real (valor de conversão fixo, conversões infladas) | ações de conversão x banco | sim |
| Campanha com custo real saudável e parcela perdida por orçamento (escala) | M2 + M6 | sim |
| Redistribuição entre campanhas | exige 2 ou mais campanhas ativas por conta | adiado |

Sob Smart Bidding, ajuste de lance por horário, dispositivo ou local não é
ação válida (o erro E4). O catálogo de recomendações conhece a estratégia de
lance da campanha e só oferece ações que ela aceita.

**M7 Mensuração**

| Detector | Evidência | v1 |
|---|---|---|
| A meta licitável da campanha não é o resultado de negócio | `campaign_conversion_goal.biddable` x categorias | sim |
| Ações primárias herdadas ou de engajamento inflando "conversões" | foto das ações | sim |
| Valor de conversão fixo | `always_use_default_value` | sim |
| Upload offline parado | dias desde o último upload aceito x cadência esperada | sim |
| Divergência Google x banco (formulários contados x leads com gclid) | contagem por dia | sim |
| Ação ativa sem volume em 30 dias; possível duplicidade (duas ações na mesma categoria disparando junto) | fato por ação | sim |

Um problema de mensuração só é declarado com evidência de configuração (um
campo da API) ou com divergência medida contra o banco. Suspeita sem as duas
sai como hipótese.

**M8 Temporal**

| Detector | Evidência | v1 |
|---|---|---|
| Queda ou alta abrupta de impressões, custo, CPC, parcela | Z robusto por dia da semana | sim |
| Mudança de patamar e sua data | CUSUM | sim |
| Tendência de deterioração | EWMA semanal | sim |
| Antes e depois de alteração | `change_events` como marcador; comparação de janelas maduras dos dois lados | sim |

### 3.8 Causa-raiz

Para cada achado, uma árvore fixa de hipóteses é avaliada por código. A
investigação é decomposição aritmética primeiro, correlação temporal depois.

Decomposições usadas:

- `CPA = CPC / CVR`, em log: a variação do CPA se reparte exatamente entre
  variação de CPC e de CVR.
- **Mix x taxa** por dimensão (dispositivo, grupo, keyword, correspondência,
  hora): quanto da variação vem de o tráfego ter mudado de composição e quanto
  de cada segmento ter piorado por dentro.
- `conversões = demanda elegível x parcela de impressões x CTR x CVR`: localiza
  em que elo a perda aconteceu.

Classificação, com critério escrito:

| Classe | Critério |
|---|---|
| **Confirmada** | Identidade aritmética explica a maior parte da variação (limiar configurável, sugestão 70%) **e** existe o mecanismo observado: um `change_event`, um teto de orçamento atingido, um campo de configuração |
| **Provável** | A decomposição aponta o fator, com significância, mas sem mecanismo observado |
| **Hipótese a investigar** | Coincidência temporal ou fator compatível, sem significância |
| **Evidência insuficiente** | Amostra ou maturidade não permitem repartir a variação |

O motor nunca promove coincidência temporal a causa. Uma alteração no mesmo
dia de uma queda é, no máximo, "provável" se a decomposição concordar.
Mudança na página de destino fora do Google Ads (deploy do site) não é
observável pela API: aparece sempre como hipótese, com essa limitação escrita.

### 3.9 Oportunidades e priorização

Oportunidade é um diagnóstico de sinal positivo, com os mesmos campos e mais:
volume potencial, impacto estimado **em faixa** (pessimista, central, otimista),
complexidade e riscos.

Regras de estimativa:

- Ganho por parcela de impressões é limitado pela demanda elegível medida, e
  o retorno marginal sofre desconto configurável (os cliques que faltam ganhar
  são piores que os já ganhos).
- Economia por negativa conta só o gasto do n-grama, líquido das conversões
  reais que ele trouxe.
- Nada é extrapolado além de 30 dias nem além do orçamento atual sem dizer.
- Sem meta econômica cadastrada para a clínica, o impacto sai em volume
  (cliques, conversões), não em reais, e a limitação é registrada.

**Score de prioridade (0 a 100)** = soma ponderada de cinco componentes
normalizados de 0 a 1: gravidade, impacto econômico (em relação ao gasto mensal
da conta), confiança, viabilidade e urgência (dinheiro perdido por dia ou prazo
externo). Pesos em `account_targets`, com padrão sugerido 20/35/20/10/15.
Diagnóstico com confiança abaixo do piso não entra na lista de prioridades,
qualquer que seja o impacto.

**Deduplicação:** achados com a mesma causa-raiz classificada viram um
diagnóstico só, com os demais como sintomas. Exemplo real: QS 4, parcela
perdida por ranking de 44% e CPC alto na Essência são um diagnóstico
(concentração numa keyword genérica), não três.

### 3.10 Saída estruturada e ciclo de vida

O schema do prompt original é adotado com quatro ajustes: chaves em
`snake_case` (padrão do Postgres do projeto), `fingerprint`, `sintomas` e o
bloco de rastreabilidade.

```json
{
  "diagnostic_id": "uuid",
  "fingerprint": "sha256(customer_id|detector|entity_type|entity_id|chave)",
  "customer_id": "4601912200",
  "clinic_id": "clinicaessenciaestetica-9668a4",
  "kind": "problem | opportunity",
  "module": "traffic",
  "detector": "ngram_leak",
  "detector_version": "1.0.0",
  "entity_type": "campaign",
  "entity_id": "23449039185",
  "entity_name": "[Gestor]Depilacao_primeira_jardins",
  "category": "traffic_quality",
  "problem": "Termos de outros bairros consomem gasto sem conversão",
  "severity": "medium",
  "priority_score": 71,
  "confidence": 0.86,
  "period": {"start_date": "2026-10-09", "end_date": "2026-11-07"},
  "comparison_period": null,
  "evidence": [
    {"metric": "cost", "observed_value": 222.0, "benchmark_value": null,
     "sample": {"clicks": 31, "conversions": 0},
     "test": {"name": "zero_conversions", "p_value": 0.011},
     "interpretation": "31 cliques sem conversão; esperado 4,2 à CVR da campanha"}
  ],
  "root_cause_hypotheses": [
    {"cause": "Correspondência de frase com expansão geográfica",
     "classification": "probable", "confidence": 0.8}
  ],
  "symptoms": [],
  "economic_impact": {"low": 150.0, "mid": 222.0, "high": 222.0,
                      "currency": "BRL", "horizon_days": 30,
                      "estimation_type": "potential_recoverable_spend"},
  "recommendations": [
    {"action": "add_negative_keywords", "params": {"terms": ["moema", "..."]},
     "valid_under_bidding_strategy": true, "risk": "low"}
  ],
  "limitations": ["Termos visíveis cobrem 61% dos cliques da campanha"],
  "traceability": {"run_id": "uuid", "as_of": "2026-11-08",
                   "query_hashes": ["..."], "config_hash": "..."},
  "status": "open",
  "first_seen": "2026-11-08", "last_seen": "2026-11-08"
}
```

(Os números do exemplo ilustram o formato; não são medição.)

`recommendations.action` vem de um vocabulário fechado, com parâmetros. É o
contrato que o agente executor futuro vai consumir. O motor não executa nada.

Ciclo de vida, guiado pelo `fingerprint`: `open` na primeira detecção;
`ongoing` enquanto reaparece (cada execução grava uma observação);
`resolved` após N execuções sem reaparecer **com amostra suficiente para
ter reaparecido**; `dismissed` por decisão humana, com motivo e validade
(um descarte suprime o fingerprint, não o detector). `evidencia_insuficiente`
é estado próprio e pode amadurecer para `open`.

### 3.11 Relatório

`GET /diagnostics/report?clinic_id=...&as_of=...` devolve JSON e, com
`format=md`, o mesmo conteúdo em Markdown. Seções: resumo executivo (saúde da
conta, 5 maiores problemas, 5 maiores oportunidades, evolução contra o período
anterior, riscos), campanhas, grupos, keywords, termos de pesquisa, anúncios e
ativos, segmentações, análise econômica (painel x real), prioridades
recomendadas e, no fim, **o que não foi possível concluir e por quê**.

A "saúde da conta" é derivada dos diagnósticos abertos e das metas, com
fórmula documentada; não é um número de impressão geral.

### 3.12 Validação

**Cenários sintéticos.** Gerador com semente em `infra/tests/diagnostics/`,
que produz séries com o volume real destas contas (ordem de 500 cliques e 75
conversões por mês) e injeta o efeito. Para cada cenário a Spec fixa resultado
esperado, diagnóstico correto, evidências obrigatórias e o falso positivo a
evitar:

| # | Cenário | Diagnóstico esperado | Não pode acontecer |
|---|---|---|---|
| 1 | CPC sobe, CVR estável | CPA explicado por CPC (leilão) | Culpar página ou criativo |
| 2 | CVR cai, CPC estável | CPA explicado por CVR (conversão) | Culpar leilão |
| 3 | CPA sobe por mix de dispositivo | Efeito mix, taxas internas estáveis | "CVR piorou" |
| 4 | Desperdício em termos | N-grama com gasto e teste de zero aprovado | Negativar termo protegido |
| 5 | Limitada por orçamento | Parcela perdida por orçamento + teto | Confundir com ranking |
| 6 | Perdendo por ranking | Parcela perdida por ranking + componente de QS | Recomendar mais orçamento |
| 7 | Queda por atraso de mensuração | "Período imaturo", sem alerta de queda | Declarar queda de conversão |
| 8 | Keyword com poucos cliques e zero conversão | `evidencia_insuficiente` | Recomendar pausa |
| 9 | Anúncio com CTR alto e CVR baixo | Desalinhamento anúncio x página | Premiar o CTR |
| 10 | Bom CPA e potencial de escala | Oportunidade com faixa e desconto marginal | Extrapolação linear |
| 11 | Queda sazonal | Explicada pelo calendário ou pelo dia da semana | Mudança de patamar |
| 12 | Mudança após alteração de orçamento | Antes e depois ancorado no `change_event`, com quarentena | Causa confirmada só pela coincidência |
| 13 | Série estável (nulo) | Nenhum diagnóstico | Qualquer alerta |
| 14 | Coleta falhou num dia | Execução marcada como falha | "Queda de 100%" |

Cada cenário roda com 200 sementes. Metas: precisão ≥ 90% e recall ≥ 80% por
detector no tamanho de efeito de projeto; no cenário nulo, no máximo 5% das
execuções com algum diagnóstico; causa-raiz correta em ≥ 80% dos casos
detectados. O relatório de validação (matriz de confusão por detector) é
artefato versionado.

**Reprodução da auditoria de 08/11.** Rodando com `as_of = 2026-11-08` sobre
dado real, o motor deve:

- encontrar E1 (upload offline parado), E2 e N8 (meta licitável é formulário),
  E3 (concentração e ranking), E7 (vazamento geográfico), E12 (valor fixo),
  E13 e N12 (cobertura criativa), N2 (página de destino), N7 (primárias
  infladas), N13 (meta de CPA nunca atingida);
- **não** propor ajuste de lance por horário (E4) nem negativar "avulsa" (E8);
- classificar as keywords de 7 e 9 cliques sem conversão como
  `evidencia_insuficiente`;
- registrar as seis alterações de orçamento da Nobre, incluindo a de origem
  `GOOGLE_ADS_RECOMMENDATIONS`;
- dar uma resposta classificada para a queda de 23 a 26/10 na Essência.

Divergência entre o motor e a auditoria é revisada caso a caso: ou o motor
está errado, ou a auditoria estava.

### 3.13 Plano de implementação

Cada fase é um PR, entregue em dev e conferida antes da seguinte.

| Fase | Entrega | Pronto quando |
|---|---|---|
| 0 | Correção do log de segredos (`google_ads_mcc_service.py:34`); `pytest` configurado no `infra/` e workflow de CI rodando os testes | CI verde em PR |
| 1 | Schema `ads`, coleta C1 a C16, normalização, métricas derivadas, junção com o banco, carga inicial | Números de 30 dias batem com §2.4 e com o painel do Google; segunda execução no mesmo dia não altera nada |
| 2 | Motor estatístico | Testes de propriedade (cobertura dos intervalos, taxa de falso positivo sob nulo) |
| 3 | Módulos M1 a M8 (detectores "sim" da v1) | Cenários 4 a 9, 13 e 14 |
| 4 | Causa-raiz e oportunidades | Cenários 1 a 3 e 10 a 12 |
| 5 | Score, deduplicação, ciclo de vida, rotas e relatório | Reprodução da auditoria de 08/11 |
| 6 | Validação completa, documentação (`infra/docs/diagnostics/`, `tests/integration/`, Postman), skills do projeto atualizadas | Metas de §3.12 atingidas; duas semanas rodando em prod sem intervenção |

### Dentro do escopo

- Tudo em §3.1 a §3.13, para as duas contas e para qualquer clínica futura com
  `google_ads_customer_id` preenchido.
- Campanhas de Pesquisa. As demais (PMax, Smart) são coletadas em nível de
  campanha e recebem só os módulos que se aplicam (leilão, econômico,
  mensuração, temporal).

### Fora do escopo

- **Qualquer escrita na conta.** Nem negativas, nem orçamento, nem pausa.
- Execução automática de recomendações e o agente que as consome.
- LLM em qualquer etapa (inclusive redação do relatório).
- Tela no painel (`frontend/`). A v1 entrega API e Markdown.
- Alertas ativos (WhatsApp, e-mail). Vêm depois que a taxa de falso positivo
  estiver medida em produção.
- Consertar ou remover o `optimizer` atual, `metrics/collector.py`,
  `analyze_negatives` e `analyze_expansion`. O defeito do optimizer (§2.2) fica
  registrado; a decisão de desligá-lo é do André (ver §5).
- Informações do leilão (concorrentes), Planejador de palavras-chave,
  experimentos.
- Medição técnica da página (Lighthouse). O motor usa só o que o Google Ads
  devolve sobre a página.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `infra/src/diagnostics/collect/` | criar | Uma consulta GAQL por conjunto (C1 a C16), cliente via `create_google_ads_client()` |
| `infra/src/diagnostics/normalize/` | criar | Micros, enums, fuso, `null` de parcela de impressões |
| `infra/src/diagnostics/store/` | criar | Upsert e leitura do schema `ads`; leitura de `scheduler.*` |
| `infra/src/diagnostics/metrics/` | criar | Métricas como par numerador/denominador, maturidade, coorte real |
| `infra/src/diagnostics/stats/` | criar | Wilson, binomial, Poisson, MAD, EWMA, CUSUM, reamostragem, BH |
| `infra/src/diagnostics/detectors/` | criar | Um arquivo por módulo (M1 a M8) e o catálogo |
| `infra/src/diagnostics/rootcause/`, `opportunity/`, `scoring/`, `report/` | criar | §3.8, §3.9, §3.11 |
| `infra/src/functions/diagnostics/runner.py` | criar | Lambda agendada |
| `infra/src/functions/diagnostics/api.py` | criar | `GET /diagnostics`, `/diagnostics/{id}`, `/diagnostics/report`, `PATCH /diagnostics/{id}` (descartar) |
| `infra/sls/functions/diagnostics/interface.yml` | criar | Cron diário, timeout 900 s e memória explícitos |
| `infra/serverless.yml` | modificar | Incluir a interface nova |
| `infra/src/scripts/setup_ads_schema.py` | criar | DDL idempotente do schema `ads` |
| `infra/src/scripts/seed_account_targets.py` | criar | Metas e lista de proteção das duas clínicas |
| `infra/tests/diagnostics/` | criar | Gerador sintético, cenários, teste AST de somente leitura, testes de estatística |
| `infra/tests/mocks/diagnostics/`, `infra/tests/integration/diagnostics.md`, `infra/tests/postman/diagnostics.postman_requests.json` | criar | Pós-implementação obrigatória |
| `infra/pytest.ini` (ou `pyproject.toml`), `.github/workflows/infra-tests.yml` | criar | Fase 0 |
| `infra/src/services/google_ads_mcc_service.py` | modificar | Remover o `print` da configuração (fase 0) |
| `infra/docs/diagnostics/` | criar | Arquitetura, catálogo de detectores, validação |
| `scheduler/` | não muda | O motor só lê `scheduler.clinics`, `leads`, `lead_conversions` |

---

## 5. Dependências e riscos

**Dependências**

- **Credencial durável (pendências I2 e I3).** O refresh token do SSM está
  revogado e o app OAuth está em *Testing*, com token de 7 dias. Um cron diário
  morre toda semana enquanto isso valer. É pré-requisito da fase 1 em produção,
  não do desenvolvimento.
- **Nível de acesso do developer token** (cota diária de operações). Conferir
  antes da fase 1; o volume estimado é pequeno, mas o número precisa estar
  escrito.
- **Metas econômicas das duas clínicas** (CAC máximo, ticket, margem) e a
  **lista de proteção** de temas. Entrada do André e das clínicas. Sem elas o
  módulo econômico roda em volume, não em reais.
- **Limpeza dos leads (pendência I6).** Enquanto o webhook criar lead para
  paciente antiga, a junção lead x agendamento da Nobre fica contaminada. O
  motor filtra por `gclid` não nulo, o que isola o tráfego pago, mas a taxa
  lead → agendamento de origem `whatsapp` não é confiável.
- **Recorrência do upload offline** (depende de I2). Sem ele o "real" para de
  crescer e o próprio motor vai acusar (detector de M7).

**Riscos**

- **Volume baixo produzir um motor mudo.** Com 75 conversões por mês, muitos
  detectores vão responder "sem volume". É o comportamento correto, mas pode
  parecer que o motor não faz nada. Mitigação: o relatório mostra o que foi
  testado e por que não concluiu, e os detectores de configuração (M1, M7), que
  não dependem de volume, entregam valor desde o primeiro dia.
- **Falso positivo por múltiplas comparações.** Dezenas de segmentos por dia,
  todo dia. Mitigação: correção de falsa descoberta, piso de confiança e a
  meta de 5% no cenário nulo.
- **Stack do `infra/` e limite do CloudFormation.** A contagem de recursos do
  stack `infra` não está documentada. Conferir antes de adicionar Lambdas e
  rotas; as três rotas de leitura podem ser uma Lambda só.
- **Python 3.9 na imagem.** Fim de vida. D5 evita dependência nativa
  justamente para não prender a subida de versão.
- **Dev e prod leem as mesmas contas reais.** É leitura, sem risco para a
  conta; o risco é diagnóstico de dev ser confundido com o de prod. Cada linha
  carrega o stage, e a junção com `scheduler.*` em dev usa o banco de dev, onde
  o dado de negócio é incompleto. Validação com dado real é em prod.
- **Mudança de API.** O SDK não fixa versão; um campo pode sumir numa subida
  da lib. Mitigação: teste de contrato que valida todas as GAQL do motor contra
  a API (consulta com `LIMIT 1`) no deploy em dev.
- **Dois motores dizendo coisas diferentes.** O `optimizer` atual continua
  gravando recomendações com CPA de período errado. Recomendação: desligar o
  cron dele quando a fase 5 entrar. Decisão pendente.
- **PII.** `ads.clicks` guarda gclid e a junção chega em lead. Diagnósticos e
  relatórios só carregam agregados; nenhum nome ou telefone sai pela API do
  motor.

**Decisões em aberto para a Spec**

1. Desligar o cron do `optimizer` na fase 5 ou mantê-lo?
2. Metas iniciais: migrar os valores de `Clients.optimizationConfig` (ticket
   270, margem 0,60...) como ponto de partida ou cadastrar do zero com as
   clínicas?
3. Horário do cron: 07:00 pega D-1 completo no fuso da conta. Confirmar que não
   coincide com o `ConversionUploader` no último dia do mês.

---

## 6. Critérios de aceite

Somente leitura e reprodutibilidade:

- [ ] Teste por AST falha se qualquer arquivo de `infra/src/diagnostics/` ou
      `infra/src/functions/diagnostics/` referenciar serviço de mutação da
      Google Ads API ou importar `GoogleAdsClientService`. O teste prova o caso
      positivo com um arquivo de exemplo que deve reprovar.
- [ ] `change_event` das duas contas não registra nenhuma alteração de origem
      `GOOGLE_ADS_API` nos horários de execução do motor durante a validação.
- [ ] Rodar duas vezes com o mesmo `as_of` produz os mesmos diagnósticos, com os
      mesmos scores, e nenhuma linha duplicada.
- [ ] Todo diagnóstico tem `run_id`, hashes das consultas e hash da
      configuração; a partir deles é possível refazer cada número da evidência
      com SQL sobre `ads.*`.

Coleta e histórico:

- [ ] Custo, cliques, impressões e conversões de 09/10 a 07/11 das duas
      campanhas ativas batem com §2.4 ao centavo e à unidade.
- [ ] Após a carga inicial existem 12 meses de série diária de campanha e 90
      dias dos demais conjuntos.
- [ ] Falha de coleta numa conta não impede a outra e não gera diagnóstico de
      queda.
- [ ] `ads.change_events` contém as seis alterações de orçamento da Nobre de
      22/10 a 03/11, com valor antes e depois e origem.
- [ ] `ads.clicks` liga ao menos 95% dos `scheduler.leads` com gclid criados
      após o início da coleta.

Estatística e diagnóstico:

- [ ] Metas de §3.12 atingidas nos 14 cenários, com o relatório de validação
      versionado.
- [ ] Reprodução da auditoria de 08/11 conforme §3.12, com cada divergência
      explicada por escrito.
- [ ] Nenhum diagnóstico `open` tem amostra abaixo do mínimo declarado pelo
      detector.
- [ ] Nenhuma recomendação emitida é inválida para a estratégia de lance da
      campanha.
- [ ] Achados de mesma causa-raiz aparecem como um diagnóstico com sintomas.

Saída:

- [ ] `GET /diagnostics` filtra por clínica, status, módulo e tipo, ordenado por
      `priority_score`; `GET /diagnostics/{id}` devolve o histórico de
      observações.
- [ ] O relatório em Markdown das duas clínicas tem todas as seções de §3.11,
      incluindo "o que não foi possível concluir".
- [ ] Custo por agendamento e ROAS reais aparecem ao lado dos do painel, por
      campanha.

Engenharia:

- [ ] `print` da configuração removido de `google_ads_mcc_service.py`; nenhum
      segredo em log do motor.
- [ ] CI roda `pytest` do `infra/` em todo PR.
- [ ] Logs do motor no padrão `[traceId: ...]`, com `run_id` como trace.
- [ ] Mocks, `tests/integration/diagnostics.md` e Postman criados.
- [ ] Duas semanas em prod com execução diária bem-sucedida nas duas contas.

---

## 7. Referências

- `CLAUDE.md` (padrões do projeto)
- `docs/work/pendencias-campanhas-google-ads.md` - auditoria de 08/11/2026;
  gabarito da reprodução (§3.12) e pendências I2, I3, I6
- PRD 040 (landing page da Nobre), PRDs 016 e 017 (conversões offline)
- `infra/src/functions/googleads/utils.py`, `infra/src/services/google_ads_config.py` - cliente via MCC
- `infra/src/services/postgres_service.py` - acesso ao Postgres
- `infra/src/functions/conversions/uploader.py` - leitura de `scheduler.lead_conversions`
- `scheduler/src/scripts/setup_database.py` - padrão de DDL idempotente
- `infra/tests/unit/test_sem_versao_fixa_da_api.py` - regra de não fixar versão da API
- Google Ads, guia: https://support.google.com/google-ads/answer/6146252?hl=pt
- Google Ads, estratégia de 3 pontos para Pesquisa: https://support.google.com/google-ads/answer/7507883
- Google Ads, práticas recomendadas: https://support.google.com/google-ads/answer/6154846
- Google Ads, 12 sugestões: https://support.google.com/google-ads/topic/10560748?hl=pt
- Google Ads API, gramática GAQL: https://developers.google.com/google-ads/api/docs/query/grammar
- Google Ads API, campos por recurso: https://developers.google.com/google-ads/api/fields/v23/overview

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada: `spec/041-google-ads-diagnostic-engine.md`
- [ ] Implementado em: (data)
- [ ] Validação de §3.12 registrada em: (data)
- [ ] Registrado em `TASKS_LOG.md`
