# PRD — 009 Site de Agendamento Público (clone do SalonSoft "Agende Online")

> Gerado na fase **Research**. Use como input para a fase Spec.
> Referência mapeada: `https://agendeonline.salonsoft.com.br/{slug}` (ex.: `/ju` → "Juliana Lira").
> Data do mapeamento: 2026-09-02 (via Claude-in-Chrome).

---

## 1. Objetivo

Reconstruir o site público de **agendamento online** que o dono já teve no SalonSoft, hospedando-o em **domínio próprio** e servido pelo **backend serverless próprio** (endpoints já existentes / a completar). O produto é um **mini-app single-page multi-tenant**: cada estabelecimento tem uma URL `dominio.com/{slug}`, onde o cliente final escolhe serviço(s), profissional, data e horário, se identifica por nome + celular (WhatsApp), confirma o número por SMS e finaliza o agendamento. Há também uma área "Meus agendamentos" para o cliente consultar e cancelar.

A meta explícita do dono: **manter a simplicidade** do modelo antigo (poucas telas, fluxo linear, zero login) e ser **leve de operar** no novo domínio (deploy isolado, configuração mínima, sem acoplamento ao painel React atual em `frontend/`).

---

## 2. Contexto

- O dono construiu e gostava desse site antigo; quer o mesmo comportamento e as mesmas features, **UI clonada 1:1**, só que na sua stack.
- O backend serverless dele já existe (AWS Lambda + Serverless Framework, mesmo padrão do resto do monorepo). A ideia **não** é reescrever backend, e sim expor/ajustar os endpoints que este site consome.
- Este site é **público e sem autenticação** (o cliente final não tem conta). Isso o diferencia do `frontend/` (painel autenticado do dono da clínica) — por isso a recomendação é um **app separado**, não uma rota dentro do painel.
- Fase atual: **somente planejamento**. Nenhum código nesta task. Próximo passo após aprovação do PRD: gerar a Spec.

---

## 3. Mapeamento do site de referência (SalonSoft "Agende Online")

### 3.1. Stack e libs do original

| Item | Observado |
|------|-----------|
| Framework | **Angular** (build Angular CLI, bundles `runtime/polyfills/main-es2015` + `-es5` differential loading) |
| Roteamento | Praticamente sem router config (`path:""` e `path:"**"`); o app lê os **segmentos da URL manualmente**: `/{slug}` e `/{slug}/{id_service}` |
| Estado | Serviço Angular com `BehaviorSubject` do "salon"; **carrinho** de serviços em memória |
| Modais | Estilo SweetAlert ("Serviço adicionado", "Confirme o seu número") |
| Máscara de telefone | `formatter.js` (`cdnjs`) |
| Captura de imagem | `html2canvas` (provável "salvar comprovante" da confirmação) |
| Pagamento | **iugu** (`js.iugu.com/v2`, `assets/js/iugu-payment-token.js`) — tokenização de cartão; usado quando o plano exige sinal/pré-pagamento no agendamento |
| Assets | ícones SVG locais (`time-line`, `money-line`, `calendar-check-line`), FontAwesome 4.7, logo servido via CloudFront assinado |
| API base | `https://www.salonsoftware.com.br/api/` — namespace `agendamentoonline/*` |

### 3.2. Rotas (URL → tela)

| URL | Tela |
|-----|------|
| `/{slug}` | Home: cabeçalho + saudação + lista de serviços |
| `/{slug}/{id_service}` | Wizard de agendamento (profissional → data → horário → carrinho → dados → confirmação SMS) |
| `Meus agendamentos` (botão no header, sem mudar rota) | Modal "Confirme o seu número" → lista de agendamentos do cliente |

> Não há deep-link para etapas internas do wizard; o estado do wizard vive em memória. Recarregar volta ao início do serviço.

### 3.3. Telas, componentes e estados

**A. Header (global)**
- Logo "SALONSOFT" à esquerda (no clone: logo do dono / do estabelecimento).
- Botão "Meus agendamentos" à direita.

**B. Home / lista de serviços — `/{slug}`**
- Bloco de saudação: **foto** do estabelecimento (circular) + "Seja bem vindo(a) ao" + **nome** em destaque (`salon_name`).
- Título "Serviços".
- **Card de serviço** (repetido), com:
  - Nome do serviço (bold).
  - Duração, com ícone de relógio, formatada `1h:30min` / `30min` / `1h:00min`.
  - Preço, com ícone de cifrão: `a partir de R$ 120,00` — exibido **apenas se** `mostrar_preco === "sim"`.
  - Botão "Reservar" (com ícone de calendário) → navega para `/{slug}/{id_service}`.
- **Agrupamento por categoria**: controlado por `agrupar_categorias` (`"0"` = lista plana, como no `/ju`; `≠ "0"` = seções por `categorias[].nome`).
- Estados: **loading** (buscando `get_inicial_online`), **erro** (salão inexistente / API fora), **empty** (sem serviços habilitados), **success** (lista).
- Caso `habilitado !== "sim"`: agendamento online desligado → tela de aviso.

**C. Wizard de agendamento — `/{slug}/{id_service}`**

Passo 1 — **Selecionar profissional**
- "Serviço selecionado: {nome}".
- "Selecione o profissional".
- Avatares dos profissionais habilitados para aquele serviço (`get_profs_hab`): foto + primeiro nome.
- Se só houver 1, já vem pré-selecionado (comportamento observado no `/ju`).

Passo 2 — **Selecionar data**
- Rótulo do mês ("Setembro 2026").
- **Faixa semanal**: 7 colunas (SEG…DOM) com dia do mês; setas `‹` / `›` avançam/voltam **1 semana**.
- Dia selecionado destacado.

Passo 3 — **Selecionar horário**
- "Selecione o horário de início".
- **Chips** de horários disponíveis (`get_horarios_profissional`), ex.: `10:00`, `10:30`.
- Empty state: "Nenhum horário disponível".
- Slots respeitam `working_plan` do profissional (janela por dia da semana + `breaks`), duração total do carrinho e `timezone` (offset em minutos enviado pelo cliente).

Passo 4 — **Carrinho** (modal "Serviço adicionado")
- Após escolher o horário: modal "Serviço adicionado ao carrinho. O que gostaria de fazer agora?" com 3 ações:
  - **Continuar** → vai para "Informações do usuário".
  - **Adicionar + serviço** → volta à lista de serviços para incluir outro (mesmo agendamento, encadeado).
  - **Ver carrinho** → lista do carrinho.
- **Card do carrinho** (por item): nome do serviço, `DD/MM/YYYY, HH:MM às HH:MM` (com ícone de relógio), preço `a partir de R$ X,XX`, `Profissional: {nome}`, botão **lixeira** para remover o item.

Passo 5 — **Informações do usuário**
- Campos: **Nome** ("Digite seu nome") e **Celular (WhatsApp)** ("Digite seu celular", com máscara).
- Botões: **Finalizar** / **Voltar**.

Passo 6 — **Confirmação de número (SMS)**
- Modal "Confirme o seu número" — "Por favor, escreva o número do celular usado para agendar o serviço." + campo Celular + **Finalizar** / **Voltar**.
- Fluxo: `verifica_celular` → `envia_sms` (OTP) → cliente digita o código → `verifica_horario_disponivel` (revalida o slot) → `post_agendamento`.

Passo 7 — **Confirmação final**
- Tela de sucesso do agendamento (provável opção de salvar comprovante como imagem via `html2canvas`).
- Estados de erro: slot tomado no meio do caminho, OTP inválido, telefone inválido.

**D. Meus agendamentos**
- Botão no header abre modal "Confirme o seu número" (só o campo de celular).
- `get_agendamentos_clientes/{slug}/{phone}` → lista de agendamentos do cliente (serviço, profissional, data/hora, status).
- Ação de **cancelar** → `cancela_agendamento_cliente`.
- Empty state: sem agendamentos para aquele número.

### 3.4. API consumida (namespace `agendamentoonline/`)

Base observada: `https://www.salonsoftware.com.br/api/`. No clone, tudo isso passa a apontar para o **backend serverless do dono**.

| # | Método | Caminho | Entrada | Saída (shape observado) | Uso |
|---|--------|---------|---------|--------------------------|-----|
| 1 | GET | `get_inicial_online/{slug}` | slug na URL | `{ mostrar_preco:"sim\|nao", agrupar_categorias:"0\|...", moeda:"BRL", salon_name, habilitado:"sim\|nao", logo:<url>, pais:"br", assinatura:"assinante\|...", providers:[{ id_provider, name, working_plan:<JSON string>, foto_perfil, habilitado_agendamento_online:"sim\|nao" }], services:[{ id_service, name, price:"120.00", duration:"90", id_categoria }], categorias:[{ id_categoria, nome, outros }] }` | Bootstrap da Home |
| 2 | GET | `get_profs_hab/{slug}/{id_service}` | — | `[{ id, first_name, foto_perfil }]` | Profissionais habilitados p/ o serviço |
| 3 | POST | `get_horarios_profissional/` | `{ id_salon:slug, id_profissional, data:"YYYY-MM-DD", servicos:[{ id_servico, duracao }], timezone:<offset min> }` | `["HH:MM", ...]` (array de horários de início; `[]` = sem vaga) | Slots do dia |
| 4 | GET | `verifica_horario_disponivel/{p1}/{p2}/{p3}/{p4}/{p5}` | 5 params (inferido: `slug/id_profissional/data/hora/duracao`) | ok / conflito | Revalida o slot antes de gravar |
| 5 | GET | `verifica_celular/{slug}/{phone}` | — | `{ existe: boolean }` | Cliente já cadastrado? |
| 6 | GET | `envia_sms/{p1}/{p2}/{p3}` | 3 params (inferido: `slug/phone/…`) | status do envio | Dispara OTP por SMS |
| 7 | POST | `post_agendamento/` | **(inferido)** `{ id_salon:slug, cliente:{ nome, celular }, codigo_sms, timezone, itens:[{ id_servico, id_profissional, data:"YYYY-MM-DD", hora:"HH:MM", duracao }] }` | agendamento criado (id) | Cria o agendamento (carrinho inteiro) |
| 8 | GET | `get_agendamentos_clientes/{slug}/{phone}` | — | `[]` p/ número desconhecido; quando há, lista de agendamentos (serviço, profissional, data/hora, status) | "Meus agendamentos" |
| 9 | POST | `cancela_agendamento_cliente/…` | **(inferido)** `{ id_salon:slug, id_agendamento, celular }` | ok | Cancelar pelo cliente |
| 10 | GET | `get_config/{slug}` | — | config extra do salão (não detalhado — provável textos/flags/pagamento) | Config auxiliar |

> Endpoints que **existem no bundle mas são do painel admin do SalonSoft, fora do escopo deste site público**: `put_status`, `put_status_profissional`, `post_config_prof`, `put_slot`, `post_working_plan`, `post_prof_agendamento_online`.

> Itens **inferidos** (4, 6, 7, 9): o corpo/param exato não foi capturado no mapeamento (o fluxo não foi finalizado, por decisão de não criar agendamento real). A Spec deve fechar esse contrato contra o backend do dono.

### 3.5. Regras de negócio observadas

- **Sem login.** Identificação do cliente = nome + celular; posse do número validada por **OTP SMS**.
- **Carrinho multi-serviço** no mesmo agendamento: itens encadeados, cada um com seu profissional/horário; a duração total influencia os slots ofertados nos itens seguintes.
- **`working_plan`** por profissional (JSON): chave por dia (`monday`…`sunday`, `null` = fechado), cada dia `{ start:"08:00", end:"18:00", breaks:[{ start, end }] }`. Ex. do `/ju`: seg e dom fechados; ter–sex 08–18 (almoço 12–13); sáb 08–15.
- **`timezone`**: cliente envia `new Date().getTimezoneOffset()` (min); back calcula slots nesse fuso.
- **`mostrar_preco`** e **`agrupar_categorias`**: flags de exibição vindas de `get_inicial_online`.
- **`moeda` / `pais`**: formatação (`R$`, `pt-BR`).
- **`habilitado` / `habilitado_agendamento_online`**: liga/desliga o site e cada profissional.
- **Pagamento (iugu)**: em planos que exigem, há tokenização de cartão + cobrança de sinal no fechamento. **Confirmar com o dono se entra no MVP** (ver Escopo).
- **Preço "a partir de"**: o valor mostrado é piso; o preço final pode variar por profissional.

---

## 4. Escopo

### Dentro do escopo
- App **novo e independente**, hospedado em **domínio próprio**, multi-tenant por `dominio.com/{slug}`.
- Clone **1:1** de UI e fluxo das telas B, C, D acima, com os **4 estados** (loading/erro/empty/success) em toda view que busca dados.
- Consumo dos endpoints 1, 2, 3, 4, 5, 6, 7, 8, 9 (10 se necessário) contra o **backend serverless do dono**, via camada HTTP tipada.
- Configuração enxuta para operar no novo domínio: base da API por env var, favicon/título, sem segredos no front.
- Responsivo (mobile-first — a maioria dos clientes agenda pelo celular).
- Formatação BR (telefone com máscara, moeda, datas `DD/MM/YYYY`).
- Comprovante da confirmação (equivalente ao `html2canvas`) — **nice-to-have**, pode cair para fase 2.

### Fora do escopo
- Qualquer tela **administrativa** (config de salão, working plan, habilitar profissional) — isso é o `frontend/` ou o backend do dono.
- Autenticação / conta de cliente.
- Migração de dados do SalonSoft.
- **Pagamento online (iugu)** no MVP — decisão pendente do dono; se entrar, é um épico à parte (tokenização + webhook no serverless).
- Notificações por WhatsApp (o SMS OTP é suficiente para o MVP; lembretes já são responsabilidade do `scheduler/`).
- i18n além de pt-BR.

---

## 5. Arquitetura proposta

**Recomendação: app separado no monorepo, deploy Vercel próprio, apontado para o novo domínio.**

| Decisão | Escolha | Porquê |
|---------|---------|--------|
| Localização | Novo diretório `Traffic-Manager/booking-site/` (nome a confirmar) | Isola do painel autenticado; build/deploy independentes; "leve de operar" |
| Stack | **React 19 + TypeScript strict + Vite 7 + TailwindCSS v4 + React Router v7 + TanStack Query v5 + Axios + React Hook Form + Zod** | Mesma stack do `frontend/` → padrões, lint e tooling reaproveitados (ver `frontend/CLAUDE.md`) |
| Roteamento | `/:slug` (home) e `/:slug/:idService` (wizard); wizard controla passos por estado local, não por rota | Fiel ao original; simples |
| Estado servidor | TanStack Query para todo fetch; carrinho em contexto/estado local | Regra do projeto: nunca chamar services direto do componente |
| HTTP | `src/services/` — um arquivo por recurso (`salon.ts`, `professionals.ts`, `slots.ts`, `appointments.ts`), tipado, base em `import.meta.env.VITE_API_BASE_URL` | Padrão `frontend/` |
| Multi-tenant | `slug` só na URL; nenhum build por cliente | Um deploy serve todos os estabelecimentos |
| Deploy | Projeto Vercel próprio (`vercel.json` com rewrite SPA), domínio custom do dono | Independente do painel |
| Design | Seguir princípios **Impeccable** (ver `frontend/CLAUDE.md` "Design Principles"), mantendo o layout/《feel》 minimalista do original | Regra do projeto para UI nova |
| Config visual do salão | Vem de `get_inicial_online` (logo, nome, flags) — nada hardcoded | Multi-tenant real |

**Contrato de backend (o que o serverless do dono precisa expor).** A Spec fará o *gap analysis* endpoint a endpoint. Alvo: replicar semanticamente os 9–10 endpoints da seção 3.4, com nomes/《shape》 à escolha do dono, desde que o front tenha:
1. bootstrap do salão por slug (flags + serviços + categorias + profissionais + working_plan);
2. profissionais habilitados por serviço;
3. slots por (profissional, data, lista de serviços, timezone);
4. revalidação de slot;
5. verificação de cliente por telefone;
6. envio de OTP SMS;
7. criação de agendamento (carrinho inteiro + OTP);
8. listagem de agendamentos por telefone;
9. cancelamento pelo cliente.

---

## 6. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `booking-site/` | criar | Novo app React/Vite (estrutura espelhando `frontend/src/`: `components/`, `hooks/`, `layouts/`, `pages/`, `services/`, `store/`, `types/`) |
| `booking-site/package.json`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `vitest.config.ts`, `vercel.json`, `index.html` | criar | Boilerplate alinhado ao `frontend/` |
| `booking-site/.env.example` | criar | `VITE_API_BASE_URL` etc. |
| `booking-site/src/pages/` | criar | `Home` (lista de serviços), `Booking` (wizard), componente `MeusAgendamentos` (modal) |
| `booking-site/src/services/` | criar | `salon.ts`, `professionals.ts`, `slots.ts`, `appointments.ts` |
| `booking-site/src/types/` | criar | Tipos espelhando o contrato da seção 3.4 |
| `booking-site/CLAUDE.md` | criar | Padrões específicos do app (ou referenciar `frontend/CLAUDE.md`) |
| Backend serverless (repo do dono) | modificar/expor | Endpoints da seção 5 — **detalhar na Spec após confirmar o que já existe** |
| `Traffic-Manager/CLAUDE.md` | modificar | Adicionar seção do novo app (build/deploy) |
| `docs/work/spec/009-site-agendamento-publico.md` | criar | Próxima fase |

---

## 7. Dependências e riscos

**Dependências**
- Backend serverless do dono expondo o contrato da seção 5 (o gap real será medido na Spec).
- Provedor de **SMS OTP** no backend (Twilio/SNS/zenvia/…): o front só chama o endpoint.
- Domínio próprio + projeto Vercel.
- (Se pagamento entrar) conta iugu + webhook.

**Riscos**
- **Contrato inferido** dos endpoints 4/6/7/9 — risco de retrabalho se o backend do dono divergir; mitigar fechando o contrato na Spec antes de codar.
- **Race condition de slot**: dois clientes no mesmo horário — o `verifica_horario_disponivel` reduz, mas o `post_agendamento` precisa ser atômico no backend.
- **Custo/entregabilidade de SMS** e limite de reenvio de OTP (rate limit no backend).
- **`working_plan` só no cliente vs. no servidor**: os slots devem ser calculados no **backend** (fonte da verdade); o front não deve reimplementar a lógica de disponibilidade.
- **Abuso** (endpoint público sem auth): precisa rate limiting / captcha leve no `post_agendamento` e `envia_sms`.
- **Fuso horário**: cliente em fuso diferente do salão — enviar offset e tratar no back.
- **SEO/entrada**: link é compartilhado direto (`/{slug}`); garantir `<title>`/OG por salão (pode exigir SSR ou pré-render — avaliar na Spec; provavelmente fora do MVP).

---

## 8. Critérios de aceite

- [ ] `dominio.com/{slug}` carrega nome, logo e lista de serviços do salão a partir de um único bootstrap, respeitando `mostrar_preco` e `agrupar_categorias`.
- [ ] Fluxo completo: serviço → profissional → data (faixa semanal com navegação) → horário → carrinho (adicionar/remover/《+ serviço》) → nome + celular → OTP SMS → confirmação.
- [ ] Slots vêm do backend por (profissional, data, serviços, timezone); "Nenhum horário disponível" quando vazio.
- [ ] Carrinho multi-serviço encadeado funciona e a duração acumulada afeta os slots seguintes.
- [ ] "Meus agendamentos": consulta por celular lista os agendamentos e permite cancelar.
- [ ] Todas as views com fetch tratam **loading / erro / empty / success**.
- [ ] Responsivo (mobile-first) e formatação pt-BR (telefone, moeda, data).
- [ ] Zero segredo no front; API base por env var; `npm run build` + `npm run lint` (zero warnings) + `npm run test` passam.
- [ ] Deploy Vercel independente no domínio do dono, sem afetar o `frontend/`.
- [ ] Sem nenhuma tela administrativa; sem login.

---

## 9. Referências

- Site de referência: `https://agendeonline.salonsoft.com.br/ju`
- API de referência: `https://www.salonsoftware.com.br/api/agendamentoonline/*`
- `Traffic-Manager/CLAUDE.md` (padrões do monorepo, secrets, deploy)
- `Traffic-Manager/frontend/CLAUDE.md` (padrões React 19 / TanStack Query / Impeccable design)
- `scheduler/` (domínio de agendamento já existente no backend — possível reaproveitamento de tabelas `appointments`, `services`, `professionals`, `availability_rules`)

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada: `spec/009-site-agendamento-publico.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`

### Decisões pendentes do dono (bloqueiam a Spec)
1. Nome/pasta do app (`booking-site/`? `agendamento/`?).
2. Pagamento online (iugu) entra no MVP? (recomendação: **não**).
3. Qual o estado atual dos endpoints no backend serverless — existe algo equivalente a `agendamentoonline/*` ou parte-se do `scheduler/`?
4. Provedor de SMS OTP disponível no backend.
5. Domínio final e se haverá 1 salão só (o dele) ou multi-tenant de verdade.
