# PRD - 040 Página de destino da Nobre Laser: do clique ao WhatsApp

> Gerado na fase **Research** em 08/11/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Fazer a página que recebe o clique do Google Ads da Nobre Laser (conta
524-665-3188) entregar o que o anúncio promete e levar a pessoa ao WhatsApp
com o mínimo de atrito - e fazer isso de um jeito que o Google consiga medir.

Hoje o Google classifica a experiência na página de destino como **abaixo da
média** em praticamente todas as keywords com dados, o Quality Score da
keyword que leva 27,6% do gasto é **2**, e 44-48% das impressões se perdem por
ranking. Do lado do negócio, 800 cliques viraram 101 formulários, 8
agendamentos e 4 sessões confirmadas (ROAS 0,12). A campanha em si está bem
construída; o que falha é o que acontece depois do clique.

O resultado esperado é duplo: `post_click_quality_score` de volta a "na média"
ou melhor (destravando o leilão), e a taxa lead → agendamento saindo de 8,3%
para a casa dos 20%, sem mexer em lance, orçamento ou estrutura de campanha.

---

## 2. Contexto

### 2.1 O funil medido (15/09 a 07/11/2026, 54 dias)

Cruzamento do Google Ads com `scheduler.leads` e `scheduler.lead_conversions`
em produção:

```
800 cliques                                   R$ 6.627,99
101 formulários (conversão no Google)   12,6%  CPA R$    65,62
 96 leads com gclid no banco
  8 agendamentos                         8,3%  CPA R$   828,50
  4 sessões confirmadas                  50%   CPA R$ 1.657,00
```

Nas quatro semanas de Q3 e Q4 (13/10 a 07/11): R$ 4.185,92 investidos, 71
conversões no Google, 4 agendamentos, **zero confirmados**.

A Essência, com gasto equivalente e o mesmo serviço, converte 9,4x melhor no
confirmado. A diferença não é mercado; é funil.

### 2.2 O que o Google está medindo

`keyword_view.quality_info` da campanha `Leads-SJC-Site`:

| Keyword | Grupo | Gasto | QS | CTR esperado | **Página de destino** | Destino |
|---|---|---|---|---|---|---|
| `depilação laser` | Geral | R$ 1.831 (27,6%) | **2** | abaixo | **abaixo** | home |
| `depilação definitiva` | Definitiva e tecnologia | R$ 949 | **3** | abaixo | **abaixo** | home |
| `depilação sjc` | Geral | R$ 230 | 3 | abaixo | **abaixo** | home |
| `sessão a laser` | Geral | R$ 265 | 3 | abaixo | **abaixo** | home |
| `depilação masculina` | SJC e sessão avulsa | R$ 67 | **1** | abaixo | **abaixo** | `/depilacao-a-laser-sjc` |
| `depilação a laser` | SJC e sessão avulsa | R$ 739 | 4 | abaixo | na média | `/depilacao-a-laser-sjc` |
| `laser sjc` | SJC e sessão avulsa | R$ 457 | 5 | abaixo | na média | `/depilacao-a-laser-sjc` |

`post_click_quality_score` é medição de comportamento de quem clicou, não
opinião sobre o anúncio. As únicas keywords com página "na média" são as que
caem em `/depilacao-a-laser-sjc`; nenhuma das que caem na home passa. É o
sinal mais direto que existe de que a home não está servindo como página de
destino.

O relatório de página de destino do próprio Google Ads
(`expanded_landing_page_view`, amostra das 20 URLs de maior custo) diz a
mesma coisa em dinheiro:

| Destino | Cliques | Custo | Conv. | CVR | CPA |
|---|---|---|---|---|---|
| `nobrelaser.com.br/` (home) | 280 | R$ 2.623,81 | 26,0 | 9,3% | R$ 100,92 |
| `/depilacao-a-laser-sjc` | 95 | R$ 1.010,43 | 19,5 | **20,6%** | **R$ 51,71** |

A página específica converte 2,2x a home com metade do CPA. E **4 dos 5
anúncios ativos apontam para a home**: `Geral` (2 anúncios), `Definitiva e
tecnologia` e `Concorrentes-SJC/Marcas`. Só o grupo `SJC e sessão avulsa` usa
a página específica - e é o grupo de melhor CPA da conta (R$ 54,74).

### 2.3 O que a página promete vs. o que o anúncio promete

O site vive no repo privado `rodsebaiano-bot/noble-laser-capture` (Lovable,
TanStack Start + Cloudflare; rotas `/`, `/depilacao-a-laser-sjc`,
`/agendamento`, `/oferta`). Conteúdo conferido na página publicada e no
código em 08/11/2026.

| O anúncio diz | Home `/` | `/depilacao-a-laser-sjc` |
|---|---|---|
| "A partir de R$50 por área" | **nenhum preço**; "Veja preços exclusivos" atrás do formulário | R$50 visível, 15%/20% de desconto |
| "Agende pelo WhatsApp" (em todos os 5 anúncios) | **zero links de WhatsApp** | **zero links de WhatsApp** - `Quero agendar` aponta para `#lead` (formulário) |
| "Sessão avulsa, sem pacote" | só o ícone "Pague por Sessão" no hero | H1 + seção "Como funciona o valor" |
| "Clínica 5 estrelas" (Essência) / confiança | **nenhuma prova social** (sem nota Google, sem depoimento) | nenhuma prova social |
| "Jardim Aquarius" | sim | sim |
| "Soprano Ice Platinum" | H1 | subtítulo |

Dois detalhes que agravam:

- O anúncio `Geral` 824801832675 e 825283325507 diz **"A partir de R$55"**; os
  outros três dizem R$50; o site diz R$50; `pricing.ts` tem o mínimo em R$50
  (Perianal) e o Buço em R$55. Três números para a mesma promessa.
- O docstring de `depilacao-a-laser-sjc.tsx` afirma que "os dois caminhos que o
  anúncio promete estão visíveis sem rolar: agendar direto pelo WhatsApp ou
  deixar o contato". O código só tem o segundo caminho. A intenção e a
  implementação divergiram, e ninguém mediu.

### 2.4 O formulário não termina nada: há uma segunda página

`formulario-de-lead.tsx` grava o lead (planilha + `POST /leads` do scheduler) e
faz `navigate("/agendamento")`. A conversão "Lead - formulário do site" dispara
aqui, no `dataLayer.push({event: "lead_form_submit"})`. Mas a pessoa ainda não
fez nada que o negócio considere resultado.

Em `/agendamento` (880 linhas) ela precisa, para chegar ao WhatsApp pelo
caminho principal: escolher gênero, ao menos uma área numa lista de ~30, uma
data e um horário, e enviar um segundo formulário (`bookingSchema` exige
`gender`, `date`, `time`). Só então `window.open(wa.me/...)`. Existem três
atalhos diretos (`carrinho`, `alternativo`, `flutuante`), mas a hierarquia
visual e o fluxo pedido levam ao formulário longo.

É aqui que 96 viram 8. O Google otimiza para o topo desse funil de dois passos
e nunca enxerga o fundo.

### 2.5 Depois do formulário ninguém chama - e quando o bot chama, não converte

O disparo automático do bot no cadastro **foi removido em 05/09/2026**
(`scheduler/src/services/elegibilidade_do_bot.py`): a atendente decide, pelo
painel, quando o bot abre conversa. Com isso:

| Leads `landing-page` (115) | n | Agendaram |
|---|---|---|
| Nunca receberam primeiro contato (`first_contact_status` nulo) | **90** | 8 |
| Bot enviou (`SENT`, canal `BOT`) | 25 | **0** |

Por quinzena: Q1 e Q2 tiveram 0% de contato pelo bot e 4 agendamentos em 36
leads (11%); Q4 teve 66% de contato pelo bot e 1 agendamento em 35 leads
(2,9%). O bot está chegando e não está convertendo - 25 mensagens enviadas
(fila `clinic-scheduler-infra-prod-outbound-queue`: 25 `SENT`, 2 `FAILED`, 2
`PENDING`), zero agendamentos a partir delas.

Latência até o primeiro contato, quando houve: **mediana 789 minutos (13 h)**,
p90 92 h. O horário comercial da clínica é 07:15-21:00 (sáb. até 18:00); 23%
dos leads chegam entre 20h e 1h. Mas a mediana de 13 h não é horário
comercial, é fila humana: alguém precisa clicar.

### 2.6 O caminho direto pelo WhatsApp quase não existe - e a tabela de leads está poluída

Hipótese inicial: os **59 leads com `source = whatsapp`** criados desde 31/10
(gclid nulo, 5 "agendamentos") seriam visitantes da LP que clicaram num CTA
direto de WhatsApp. **Verificado em 08/11/2026 e refutado**, cruzando a
primeira mensagem INBOUND real de cada telefone em
`clinic-scheduler-infra-prod-message-events` com os moldes que a LP
pré-preenche no wa.me:

| Primeira mensagem dos 59 `whatsapp` | n |
|---|---|
| Molde da LP (`Olá! Sou ... gostaria de agendar minha sessão. Áreas escolhidas: ...`) | **6** |
| Já era paciente antes do "lead" (confirmando, cancelando, "até amanhã") | 14 |
| Pergunta de preço espontânea (orgânico, Instagram, indicação) | 12 |
| "Oi" / "Bom dia" / uma palavra | 14 |
| Candidatas a emprego, lembrete de reserva, mensagens para o André, lista de influencers | 13 |

Três conclusões:

1. **O caminho direto é marginal hoje:** 6 usos em 54 dias, nenhum com
   `(ref: gclid)`. O Google Ads confirma: a ação "Clique no WhatsApp" registrou
   **10 cliques** desde que a tag passou a disparar (semana de 19/10), contra
   56 formulários no mesmo período. Faz sentido: o único botão de WhatsApp fica
   em `/agendamento`, depois do formulário. Isso **reforça** o item B do escopo
   (WhatsApp acima da dobra), em vez de medir um ganho que já existe.
2. **Os 5 "agendamentos" entre os 59 são pacientes antigas**, não aquisição. O
   salto de 43 para 92 leads na Q4 é artefato: o webhook faz `upsert_lead(source
   = "whatsapp")` para **toda** mensagem com texto de **qualquer** número
   (`webhook/handler.py:267-279`), sem conferir se é paciente, fornecedor ou a
   própria equipe. Quando a instância z-api passou para a clínica em 31/10, cada
   conversa existente virou "lead" na primeira mensagem. O painel e qualquer
   métrica de "leads" ficam inflados enquanto isso valer.
3. **`raw_message` não é a primeira mensagem:** o `ON CONFLICT` sobrescreve
   (`raw_message = COALESCE(%s, raw_message)`). Para origem, a fonte confiável é
   `message-events`, que só tem histórico desde 31/10 e TTL de 60 dias.

Do lado dos **115 leads da LP**: só **16 (14%) alguma vez escreveram** no
WhatsApp da clínica; 3 deles via carrinho da LP, os outros respondendo ao bot
ou à atendente. Ressalva: `message-events` só enxerga a partir de 31/10, então
leads de setembro e outubro podem ter escrito para o número antigo. Entre os 35
leads criados a partir de 31/10, 8 escreveram (23%). Mesmo com a ressalva, três
em cada quatro pessoas que preenchem o formulário nunca chegam a uma conversa.

A lacuna de atribuição continua real - os três CTAs montam o wa.me sem gclid
embora o webhook saiba ler `(ref: GCLID)` (`lead_service.extract_gclid`) - mas
hoje custa pouco porque o caminho é pouco usado. Passa a custar muito assim que
o item B colocar o WhatsApp na primeira dobra; por isso o item D vem junto.

`whatsapp_click` chega ao GTM (`lib/whatsapp.ts`) e existe como ação "Clique
no WhatsApp" no Google Ads - **secundária**, fora do relatório e do lance.

### 2.7 Performance técnica (Lighthouse mobile, 08/11/2026, local)

| Página | Perf. | FCP | LCP | TBT | Peso | Contraste (falhas) |
|---|---|---|---|---|---|---|
| `/` | 74 | 4,0 s | **4,3 s** | 140 ms | **4.989 KB** | 13 |
| `/depilacao-a-laser-sjc` | 73 | 3,9 s | **4,4 s** | 60 ms | 828 KB | 18 |
| `/agendamento` | 76 | 3,8 s | **4,3 s** | 30 ms | 593 KB | 44 |

LCP "bom" para o Google é até 2,5 s; as três páginas estão a 4,3-4,4 s. O LCP é
texto (H1 ou parágrafo do hero), não imagem - o atraso vem de fonte e CSS
bloqueantes, não de mídia.

Onde o peso está:

- **Dois vídeos MP4 na home: 2.616 KB + 1.613 KB = 4.229 KB (85% da página)**,
  em `autoPlay` na seção "Nosso Atendimento", abaixo da dobra. Existe ainda um
  `nobre-hero-video.mp4` de 4.226 KB no repo.
- **Fontes: 123 KB** - Playfair Display em 6 variações + Inter em 5, duas folhas
  de estilo bloqueantes (`fonts.googleapis.com` ~850 ms, `styles.css` ~325 ms).
- **Logo `nobre-logo.jpeg`: 87 KB** renderizado a 36-44 px (economia estimada
  86 KB); `favicon.ico` 58 KB; imagens sem `srcset`, `width`/`height` nem
  WebP/AVIF (economia 82-124 KB por página).
- **JavaScript não usado: 148-157 KB**; GTM 152 KB.
- **Contraste:** `--primary` (terracota `oklch(0.605 0.13 40)`) sobre
  off-white dá 3,4-3,9:1 em rótulos, badges e no CTA `#lead` - abaixo do mínimo
  AA de 4,5:1. Em `/agendamento`, 44 elementos.

O `expanded_landing_page_view` do Google devolve `speed_score = 0` e
`mobile_friendly_clicks_percentage = 0` (sem dados, volume insuficiente), então
a leitura técnica vem do Lighthouse local.

### 2.8 Síntese

Cinco causas, em ordem de peso:

1. **Destino errado:** 4 de 5 anúncios caem numa home sem preço, sem WhatsApp e
   sem prova social, que o Google já mede como "abaixo da média" em todas as
   keywords. A página certa existe e converte 2,2x.
2. **Promessa quebrada:** todo anúncio diz "Agende pelo WhatsApp"; nenhuma
   página de destino tem um link de WhatsApp.
3. **Funil de dois passos:** o formulário leva a uma segunda página que exige
   gênero, área, data e horário antes do WhatsApp. 96 leads → 8 agendamentos.
4. **Pós-formulário sem dono:** 90 de 115 leads nunca foram contatados; os 25
   que o bot contatou (mediana 13 h depois) não agendaram.
5. **WhatsApp direto quase inexistente e sem atribuição:** 6 usos em 54 dias,
   10 cliques medidos pelo Google, nenhum com gclid; o clique no WhatsApp é
   conversão secundária. E a contagem de "leads" está inflada por pacientes
   antigas e ruído que o webhook registra como lead.

A velocidade (LCP 4,3 s, home de 4,9 MB) é o sexto fator: real, mensurável e
barato de corrigir, mas não é o que explica QS 2.

---

## 3. Escopo

### Dentro do escopo

**A. Roteamento: cada grupo de anúncio cai na página que responde à busca.**

- Trocar o `final_url` dos anúncios de `Geral` e `Definitiva e tecnologia` da
  home para `/depilacao-a-laser-sjc` (ou para as páginas por intenção do item
  B, quando existirem). `Concorrentes-SJC` está pausada; se voltar, recebe
  página própria com a mensagem "sem pacote, sem fidelidade".
- A home deixa de ser destino de anúncio. Pode continuar existindo para
  orgânico e Instagram.
- Mudança de URL final não reinicia o aprendizado da estratégia de lance; muda
  o criativo, então o anúncio passa por nova aprovação.

**B. Primeira dobra com correspondência de mensagem, em toda página de destino.**

- H1 espelha o título fixado do grupo (`Depilação a Laser em SJC`, `Depilação
  Definitiva em SJC`, `Depilação a Laser Sem Pacote`).
- **Preço na primeira dobra:** "a partir de R$50 por área", 15% em 2-4 áreas,
  20% em 5 ou mais. Acaba o gate de preço atrás do formulário.
- **Dois CTAs lado a lado, acima da dobra:** `Agendar pelo WhatsApp` (wa.me
  direto, primário) e `Ver valores e horários` (formulário, secundário). O
  anúncio promete os dois caminhos; a página entrega os dois.
- Prova social: nota e quantidade de avaliações do Google Business Profile da
  Nobre, com link. Se a clínica ainda não tiver avaliações suficientes, a
  seção fica fora e isto vira dependência (ver §5), não placeholder.
- Variantes por intenção quando o volume justificar: `/depilacao-masculina-sjc`
  (barba, costas, peito - keyword `depilação masculina` tem QS 1 e caiu na
  página genérica) e `/depilacao-definitiva-sjc`. A ordem: primeiro a página
  genérica fica boa; depois se desdobra.

**C. `/agendamento` deixa de ser pré-requisito.**

- O WhatsApp direto vira o caminho principal em todas as páginas. A escolha de
  áreas continua disponível como *ajuda* para quem quer ver o valor antes,
  nunca como exigência.
- Remover `gender`, `date` e `time` como campos obrigatórios do
  `bookingSchema`. Data e horário são conversa de WhatsApp (o bot já faz isso)
  ou agendamento em `agendar.nobrelaser.com.br`.
- O formulário de nome + WhatsApp (que gera o lead e dispara a conversão
  `lead_form_submit`) passa a abrir o wa.me na mesma ação, com a mensagem
  pré-preenchida, em vez de navegar para outra página. Um clique a menos; a
  conversão do Google continua disparando no mesmo ponto.

**D. Atribuição: o gclid viaja em todo caminho até o WhatsApp.**

- Toda URL `wa.me` montada pela LP inclui `(ref: <gclid>)` no fim da mensagem
  quando `leAtribuicao().gclid` existir. O webhook já extrai e grava
  (`extract_gclid`). Mensagem sem gclid continua funcionando.
- `whatsapp_click` passa a ser conversão **primária** no Google Ads e
  `Lead - formulário do site` cai para secundária, **ou** as duas permanecem e
  o lance usa `BOOK_APPOINTMENT` quando a conversão offline estiver guiando -
  decisão de PRD separado (ver §Fora do escopo). Neste PRD, o mínimo é: o
  evento existe, dispara em todos os CTAs e carrega `origem`.
- ~~Verificar por telefone quantos dos 59 leads `whatsapp` coincidem com
  visitantes da LP.~~ **Feito em 08/11/2026 (§2.6): 6 de 59; hipótese
  refutada.** O que fica é a medição do antes/depois do item B: cliques de
  WhatsApp por semana na ação 7854661199 (baseline: 10 em três semanas) e
  proporção de primeiras mensagens com molde da LP em `message-events`.
- **Parar de registrar lead para quem não é lead.** O webhook não deve criar
  `source = whatsapp` para telefone que já é paciente da clínica, nem para
  número da equipe; o restante (desconhecido que escreve espontaneamente) é
  lead legítimo e continua. Mexe em `webhook/handler.py` e, idealmente, limpa
  as linhas de 31/10 em diante que são pacientes antigas. É pequeno, é do
  scheduler, e sem isso toda métrica de lead da Nobre mente - inclusive as
  deste PRD. A Spec decide se vai neste PR ou num hotfix à parte.

**E. Pós-formulário: ninguém fica sem resposta.**

- Para lead `landing-page` que **não** clicou no WhatsApp em N minutos (sugestão:
  10) dentro do horário comercial, o bot abre a conversa automaticamente. Fora
  do horário, na próxima abertura. A trava que motivou a remoção em 05/09
  ("não sei se a atendente já falou") não se aplica a quem acabou de preencher
  um formulário: ninguém falou ainda.
- Lead que clicou no WhatsApp e escreveu entra no fluxo normal do bot
  (`LEADS_ONLY` já cobre `source = landing-page`).
- Revisar o texto da primeira mensagem do bot para lead de landing page: 25
  envios, 0 agendamentos é taxa de uma mensagem que não funciona. Hipótese a
  validar nas conversas: a mensagem não retoma o que a pessoa viu (áreas,
  preço) nem oferece o próximo passo concreto (duas opções de horário).
- Esta parte toca o `scheduler` (política em `elegibilidade_do_bot.py`,
  disparo em `lead/create.py`, fila `outbound_queue`), não a LP. Entra aqui
  porque é inseparável do resultado; a Spec pode quebrar em dois PRs.

**F. Performance e acessibilidade.**

- Vídeos da home: remover do caminho crítico. Opções, da mais simples: trocar
  por poster estático com clique para reproduzir; ou recomprimir para WebM/H.264
  ≤ 400 KB cada, `preload="none"`, `poster`. Como a home sai do roteamento de
  anúncio (item A), a decisão tem menos pressa - mas 4,2 MB em `autoPlay` é
  dívida em qualquer página.
- Fontes: reduzir a 2 pesos de Playfair (400, 600) e 2 de Inter (400, 600),
  `font-display: swap` já está; avaliar self-host para cortar a folha
  bloqueante de `fonts.googleapis.com` (~850 ms).
- Imagens: logo em SVG ou WebP ≤ 5 KB; `favicon.ico` → PNG/SVG ≤ 5 KB; fotos
  em WebP com `srcset`, `width` e `height`.
- Contraste: ajustar `--primary` para ≥ 4,5:1 sobre `--background` em texto
  (terracota mais escura, ex.: `oklch(0.50 0.13 40)`) ou usar
  `--terracotta-deep` em rótulos e badges. Meta: zero falhas AA no Lighthouse.
- Meta: LCP < 2,5 s e peso < 1 MB em toda página de destino.

**G. Coerência de preço nos anúncios.**

- `Geral` 824801832675 e 825283325507: "A partir de R$55" → "R$50", alinhado aos
  outros três anúncios, ao site e ao `pricing.ts`. Mudança de criativo; não
  reinicia lance.

**H. Medição do antes e depois.**

- Registrar no PRD, na data da implantação: `post_click_quality_score` e QS
  por keyword (tabela de §2.2), CVR e CPA por página de destino (§2.2), taxa
  lead → agendamento e lead → contato (§2.5), Lighthouse das três páginas
  (§2.7). Reavaliar em 4 e 8 semanas - QS leva semanas para refletir.

### Fora do escopo

- Reestruturar campanhas ou grupos de anúncio, mudar tCPA (R$ 54,75) ou
  orçamento. A estrutura está adequada; PRD próprio se o dado pós-mudança
  pedir.
- Promover `BOOK_APPOINTMENT` a licitável e criar a action de `PURCHASE` na
  Nobre (hoje `offline_conversion_action_id` é nulo). É o passo seguinte de
  medição e tem pré-requisito: o cron de conversão offline voltar a rodar
  (credencial do SSM revogada em 08/11/2026).
- A Essência. Mesmo diagnóstico de destino (um anúncio só, QS 4) mas a página
  dela está "na média" e o funil converte; não é urgente.
- Redesenhar `agendar.nobrelaser.com.br` (booking-site deste repo). Ele é
  destino do bot e do "Meus agendamentos", não do anúncio.
- `/oferta`: não é destino de anúncio; herda o que couber do item C sem ser
  prioridade.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| **Repo `rodsebaiano-bot/noble-laser-capture`** (Lovable, sincroniza da `main`) | | |
| `src/routes/depilacao-a-laser-sjc.tsx` | modificar | Primeira dobra com preço, dois CTAs (wa.me + formulário), prova social; vira a página de destino padrão |
| `src/routes/index.tsx` | modificar | Vídeos fora do caminho crítico; CTA de WhatsApp; deixa de ser destino de anúncio |
| `src/routes/agendamento.tsx` | modificar | `bookingSchema` sem `gender`/`date`/`time` obrigatórios; WhatsApp direto como caminho principal; gclid na mensagem |
| `src/components/formulario-de-lead.tsx` | modificar | Abre wa.me na mesma ação do envio (sem `navigate("/agendamento")`) |
| `src/lib/whatsapp.ts` | modificar | `linkWhatsApp(mensagem, gclid?)` anexa `(ref: <gclid>)`; todos os CTAs passam por aqui |
| `src/lib/atribuicao.ts` | manter | Já captura e guarda gclid/UTMs em `sessionStorage` |
| `src/components/prova-social.tsx` | criar | Nota e avaliações do Google Business Profile |
| `src/routes/depilacao-masculina-sjc.tsx` | criar (fase 2) | Página por intenção para o grupo masculino |
| `src/routes/__root.tsx` | modificar | Fontes reduzidas / self-host; preload do CSS crítico |
| `src/styles.css` | modificar | `--primary` com contraste AA |
| `src/assets/*.mp4`, `nobre-logo.jpeg`, `favicon` | modificar | Recompressão / troca de formato |
| **Google Ads (conta 524-665-3188)** | | |
| `ad_group_ad` 824801832675, 825283325507, 828474521518 | modificar | `final_urls` → `/depilacao-a-laser-sjc`; "R$55" → "R$50" nos dois primeiros |
| `conversion_action` "Clique no WhatsApp" (7854661199) | modificar | Primária ou, no mínimo, conferir que o tag dispara em todos os CTAs |
| GTM `GTM-WTPMSJ2R` | conferir | `lead_form_submit` e `whatsapp_click` presentes; mapear `whatsapp_click` à ação do Google Ads se ainda não estiver |
| **Scheduler (este repo)** | | |
| `scheduler/src/services/elegibilidade_do_bot.py` | modificar | Regra de disparo automático para `landing-page` sem clique em N minutos |
| `scheduler/src/functions/lead/create.py` | modificar | Enfileirar `FIRST_CONTACT` com `atraso_minutos` quando a regra permitir |
| `scheduler/src/services/outbound_queue.py` | manter | Já suporta `atraso_minutos` e horário comercial |
| Texto da primeira mensagem para lead de LP | modificar | Onde quer que viva (template/prompt); revisar após leitura das 25 conversas |
| `docs/work/prd/040-*.md` | atualizar | Baseline de §H na implantação e nas reavaliações |

---

## 5. Dependências e riscos

**Dependências**

- Acesso de escrita ao repo `rodsebaiano-bot/noble-laser-capture` (conta
  `andrefelipe11` tem; Lovable republica a partir da `main`).
- Google Business Profile da Nobre com avaliações. Sem elas, a seção de prova
  social não entra - e vale a pena a clínica pedir avaliações às 4 pacientes
  confirmadas antes de a página subir.
- Credencial do Google Ads válida para alterar `final_urls` e textos (hoje o
  token local em Testing vence ~15/11/2026; o do SSM está revogado).
- Horário comercial e política `LEADS_ONLY` da Nobre já configurados no banco
  (conferido: 07:15-21:00 seg-sex, até 18:00 sáb; `bot_paused = false`).
- Instância z-api da Nobre conectada (pendência registrada em 01/11/2026). Sem
  WhatsApp conectado, o item E não sai.

**Riscos**

- **Reaprovação de anúncios.** Trocar `final_url` e texto manda os anúncios
  para revisão; pode haver horas sem veiculação. Fazer fora do pico (fim de
  semana) e um grupo por vez.
- **Disparo automático escrever para quem já está sendo atendido.** Foi o
  motivo da remoção em 05/09. A regra proposta restringe a `source =
  landing-page` + sem `conversation_started_at` + sem `first_contact_*` + sem
  `has_whatsapp_chat`, as mesmas travas de `por_que_nao_pode`. O risco residual
  é a atendente ter respondido fora do WhatsApp (telefone); mitigar com o
  botão "Já iniciada" que já existe.
- **Mensagem do bot continuar não convertendo.** 25 → 0 é evidência de que
  automatizar o envio sem rever o texto só acelera uma mensagem que não
  funciona. Ler as 25 conversas antes de redigir.
- **Lovable sobrescrever mudanças.** O repo é fonte da verdade e o Lovable
  publica da `main`; editar pelo editor visual depois de um PR pode reverter.
  Combinar que mudanças passam por PR.
- **Medição do QS demora.** O Google recalcula `post_click` com semanas de
  dados; não concluir nada antes de 4 semanas. CVR por página e lead →
  agendamento respondem em dias e são os indicadores antecedentes.
- **Remover gênero do `/agendamento`** tira a informação "atendimento
  masculino/feminino" da mensagem; o bot precisa perguntar quando relevante
  (depilação íntima masculina não é atendida - já está no FAQ).

---

## 6. Critérios de aceite

Página e anúncio:

- [ ] Nenhum anúncio ativo da conta 524-665-3188 tem `final_url` na home `/`.
- [ ] Toda página de destino mostra "a partir de R$50 por área" e um link
      `wa.me` acima da dobra em viewport mobile (375 px) sem rolar.
- [ ] H1 de cada página de destino contém o título fixado (`HEADLINE_1`) do
      grupo que aponta para ela.
- [ ] Os cinco anúncios dizem o mesmo preço mínimo, igual ao da página e ao de
      `pricing.ts`.

Funil:

- [ ] Enviar o formulário de nome + WhatsApp abre o wa.me na mesma ação, sem
      navegar para `/agendamento`.
- [ ] `/agendamento` permite chegar ao WhatsApp sem preencher gênero, data ou
      horário.
- [ ] 100% das URLs `wa.me` geradas pela LP contêm `(ref: <gclid>)` quando há
      gclid na sessão; teste automatizado em `whatsapp.ts`.
- [ ] Lead `landing-page` criado em horário comercial e sem clique no WhatsApp
      recebe a primeira mensagem do bot em até N minutos (N definido na Spec);
      fora do horário, na próxima abertura. Verificável na fila
      `outbound-queue` e em `first_contact_at`.
- [ ] Texto da primeira mensagem revisado com base nas 25 conversas sem
      agendamento, e a nova versão registrada no PRD.

Técnica (Lighthouse mobile, as três páginas):

- [ ] LCP < 2,5 s; peso total < 1 MB; zero falhas de contraste AA.
- [ ] Nenhum `<video autoPlay>` fora do viewport inicial; nenhum MP4 > 400 KB
      no caminho crítico.

Medição (4 e 8 semanas após implantação, registradas no PRD):

- [ ] `post_click_quality_score` ≥ `AVERAGE` em todas as keywords com dados.
- [ ] QS de `depilação laser` e `depilação definitiva` ≥ 5 (hoje 2 e 3).
- [ ] CVR da página de destino ≥ 15% (hoje 9,3% na home, 20,6% na específica).
- [ ] Taxa lead → agendamento ≥ 20% (hoje 8,3%).
- [ ] Zero leads `landing-page` com `first_contact_status` nulo após 24 h.

---

## 7. Referências

- `CLAUDE.md` (padrões do projeto)
- Auditoria da conta Nobre Laser em 08/11/2026 (sessão de trabalho; dados em
  `keyword_view`, `search_term_view`, `expanded_landing_page_view`,
  `campaign_conversion_goal` da conta 524-665-3188)
- Repo da LP: `github.com/rodsebaiano-bot/noble-laser-capture` (privado)
- `scheduler/src/services/elegibilidade_do_bot.py` - histórico da remoção do
  disparo automático (05/09/2026)
- `scheduler/src/services/lead_service.py` - `extract_gclid`, padrão `(ref: ...)`
- `scheduler/src/services/outbound_queue.py` - fila com `atraso_minutos`
- PRD 016/017 (conversões offline), PRD 031 (quem o bot responde), PRD 032
  (site pede cadastro)
- Google: *Landing page experience* e *Quality Score* -
  https://support.google.com/google-ads/answer/2404197

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada: `spec/040-landing-page-nobre-do-clique-ao-whatsapp.md`
- [ ] Implementado em: (data)
- [ ] Baseline de §3.H registrada em: (data)
- [ ] Registrado em `TASKS_LOG.md`
