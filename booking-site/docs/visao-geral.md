# Booking-site — Visão Geral

> Referência viva do que o produto **é hoje**. Não é PRD nem Spec — aquelas
> documentam mudanças pontuais (`docs/work/prd/`, `docs/work/spec/`); este
> arquivo descreve o estado atual e é atualizado conforme o produto muda.
> Para padrões de código e comandos de dev, ver `../CLAUDE.md`.

---

## 1. O que é

Site público de agendamento online, sem login, para os pacientes de uma
clínica marcarem horário sozinhos — clone 1:1 do fluxo de um produto antigo
do dono (SalonSoft "Agende Online"), reconstruído sobre o backend serverless
próprio do `scheduler/`.

Multi-tenant: um deploy só atende todas as clínicas, cada uma identificada
por `clinic_id` (via path, ou via domínio próprio — ver §3).

---

## 2. Como o cliente final usa

1. Abre o link da clínica (`booking-site-neon.vercel.app/<clinic_id>`, ou o
   domínio próprio dela — ver §3).
2. Escolhe o(s) serviço(s), vendo só o preço "a partir de" — **duração não
   aparece** em nenhuma tela (é conta interna da agenda). Se a clínica só tem
   **um** serviço no catálogo, essa escolha é pulada: o serviço já chega
   pré-selecionado.
3. Se o serviço tiver áreas de tratamento configuradas, escolhe quais. Acima
   da lista, o **desconto progressivo** da clínica (`discountTiers` do
   bootstrap: "2 a 3 áreas: 10% off · 4 ou mais áreas: 20% off") e quanto
   falta para a próxima faixa, pela contagem de áreas da cotação (depois dos
   combos). É só anúncio: o valor cobrado continua sendo o de `/quote`.
   O "Continuar" fica preso no rodapé da tela durante essa etapa, com a
   contagem de áreas marcadas e o valor final da cotação ao lado (o valor só
   aparece quando a cotação das áreas atuais chegou; nunca é calculado no
   front).
4. **Não escolhe profissional** — o backend atribui se houver um ativo; sem
   nenhum, o agendamento fica sem profissional e o fluxo segue normal (o
   horário é da clínica inteira, não de alguém).
5. Escolhe o dia numa lista que mostra **só os dias com horário**, de hoje até
   o fim do mês vigente (fuso da clínica), e depois o horário. Sem vaga no
   resto do mês, a tela diz quando o próximo mês abre e oferece o WhatsApp da
   clínica.
6. Informa nome e celular. Ao digitar o celular, o resumo é recalculado:
   **Total**, **Desconto** (percentual) e **Valor final** aparecem antes de
   confirmar. Com celular a cotação não diz o motivo do desconto — a rota é
   pública e sem verificação, e o motivo revelaria a quem digitasse um número
   qualquer se ele já foi paciente ou tem desconto combinado. Sem celular o
   motivo aparece (só a faixa por quantidade de áreas é possível). O motivo
   continua gravado no agendamento e vai na confirmação por WhatsApp, que só
   o dono do número recebe.
7. Agendamento é criado na hora — **sem verificação prévia do número**. Se o
   número já tem agendamento futuro confirmado, o site pergunta antes ("Quer
   manter os dois?"): a criação responde 409 `HAS_FUTURE_APPOINTMENT` só com a
   contagem, sem data nem nome, porque qualquer um pode digitar o número de
   outra pessoa. Confirmando, reenvia com `confirmDuplicate: true`. A
   confirmação chega por WhatsApp (template `BOOKED`, com o nome digitado
   naquele agendamento e o valor já com desconto), seguida das orientações
   pré-sessão da clínica.
8. "Meus agendamentos" (botão no header): consulta ou cancela agendamentos
   existentes pelo celular — **esse caminho exige confirmar o número por
   código enviado via WhatsApp** (único lugar do site com essa verificação).
   Cada cartão mostra o nome de quem agendou: o mesmo telefone pode agendar
   para mais de uma pessoa. A busca compara o telefone normalizado e tolera a
   falta do nono dígito (paciente criado pelo bot fora dos DDDs 11-28).

---

## 3. Multi-tenant: path ou domínio próprio

Duas formas de uma clínica ser acessada, decididas **uma vez, no boot**, pelo
hostname (`isDefaultDomain`, `src/utils/domain.ts`) — as duas nunca coexistem
na mesma sessão:

| | Domínio padrão (`*.vercel.app` / `localhost`) | Domínio próprio da clínica |
|---|---|---|
| URL | `booking-site-neon.vercel.app/<clinic_id>` | `agendar.suaempresa.com.br/` |
| Quem decide o `clinic_id` | o path (`/:clinicId`) | `GET /public/resolve-domain?host=...` |
| Configuração | nenhuma — funciona pra qualquer clínica | clínica configura em "Site de Agendamento" → "Domínio customizado" no painel |
| Layout usado | `BookingLayout` | `CustomDomainLayout` |

Os dois layouts montam o mesmo `BookingChrome` (header, favicon dinâmico,
modal "Meus agendamentos") depois de resolver o `clinic_id` — toda a lógica
de página (`Home`, `Booking`) lê o id via `useClinicId()`, nunca via
`useParams` direto, e não sabe qual dos dois caminhos trouxe ela até ali.

Ver `docs/work/prd/021-dominio-customizado-booking-site.md` para como o
domínio próprio é registrado (painel → Vercel) e por que a integração não
custa nenhum recurso novo de CloudFormation.

---

## 4. O que o backend reaproveita do bot de WhatsApp

Nada da lógica de agendamento foi duplicada — o site público é uma segunda
porta de entrada para o **mesmo** motor que o bot usa:

| Peça | Classe/arquivo | Papel |
|---|---|---|
| Disponibilidade | `AvailabilityEngine.get_days_status` | Chama `janelas_livres`, a mesma agenda do bot; só preserva o motivo de "sem horário" (fechado × lotado) |
| Carrinho | `carrinho.py` | Combos (`combos.troca_no_catalogo`) → duração (`duration_rules.duracao_do_carrinho`) → preço (`politica_de_desconto.preco_de_tabela`) → desconto (`politica_de_desconto.decide`), na ordem do agente. Cotação, disponibilidade e criação chamam este módulo |
| Desconto | `politica_de_desconto.decide` | A mesma decisão que a tool `calculate_discount` do agente: personalizado > maior entre primeira sessão e faixa de áreas |
| Janela | `mes_vigente.py` | Hoje até o fim do mês, no fuso da clínica — **só o site** usa |
| Criação/cancelamento | `AppointmentService.completo(db)` | Mesma regra de negócio, inclusive a conversão de gclid pro Google Ads (por isso é sempre `.completo()`, nunca o construtor cru) |
| Confirmação | `TemplateService` + template `BOOKED` + `orientacoes_pos_sessao` | A mensagem que chega no WhatsApp do cliente é a mesma customizável por clínica que o bot manda, e as orientações pré-sessão vão logo depois, como no agente |
| Envio | `ZApiProvider` | Mesmo provedor de WhatsApp, mesmo allowlist de telefones em dev |

Todas as rotas públicas (`public/clinics/{clinicId}/*` e
`public/resolve-domain`) vivem numa **única Lambda** (`PublicBooking`, roteada
internamente por `router.py`) — decisão forçada pelo limite de 500 recursos
por stack do CloudFormation (ver
`docs/work/prd/013-limite-do-cloudformation.md`). Toda rota pública nova deve
entrar ali, não como função própria.

---

## 5. Endpoints consumidos

| Método | Rota | Uso |
|---|---|---|
| GET | `/public/clinics/{clinicId}/bootstrap` | Clínica, serviços, profissionais, áreas e `discountTiers` (faixas de desconto por quantidade de áreas) — carregado uma vez no boot de cada página |
| GET | `/public/resolve-domain?host=` | Domínio próprio → `clinic_id` (só no `CustomDomainLayout`) |
| GET | `/public/clinics/{clinicId}/availability?dates=&serviceIds=&serviceAreaPairs=` | Status por dia (`CLOSED\|FULL\|AVAILABLE`) + horários livres do mês, com a duração calculada **no backend** pelo carrinho; `window` traz o fim da janela e quando o próximo mês abre. `totalDuration` (legado) ainda é aceito e logado |
| POST | `/public/clinics/{clinicId}/quote` | Total, desconto e valor final do carrinho (com `phone`, também primeira sessão e personalizado, mas `discountReason` vem null) — o mesmo que a criação grava |
| POST | `/public/clinics/{clinicId}/verify/send` | Envia código por WhatsApp — só usado por "Meus agendamentos" |
| POST | `/public/clinics/{clinicId}/verify/confirm` | Confirma o código, devolve token de sessão — idem |
| POST | `/public/clinics/{clinicId}/appointments` | Cria o agendamento (sem token/verificação), com desconto da política e pares pós-combo; recusa data fora do mês vigente e horário que já passou; 409 `HAS_FUTURE_APPOINTMENT` se o número já tem agendamento futuro e falta `confirmDuplicate: true` |
| GET | `/public/clinics/{clinicId}/my-appointments?phone=&token=` | Lista agendamentos futuros do número, com `full_name` de cada um (exige token; telefone normalizado e tolerante ao nono dígito) |
| POST | `/public/clinics/{clinicId}/appointments/{id}/cancel` | Cancela (exige token) |

> `GET /public/clinics/{clinicId}/available-slots` (`slots.py`) ainda existe
> no router por compatibilidade, mas **não é mais chamado** pelo front — foi
> substituído por `/availability`, que já traz o status do dia junto.

---

## 6. Estrutura do código

```
booking-site/src/
├── layouts/
│   ├── BookingLayout.tsx       # clinicId por path (domínio padrão)
│   ├── CustomDomainLayout.tsx  # clinicId por hostname (domínio próprio)
│   └── BookingChrome.tsx       # header ("Agende online", sem logo) + favicon + modal, compartilhado pelos dois
├── pages/
│   ├── Home.tsx                # lista de serviços (ou auto-skip, se só há um)
│   └── Booking.tsx             # o wizard: carrinho → áreas → agenda → dados → sucesso
├── components/
│   ├── ClinicWelcome            # avatar + nome da clínica, no topo de toda tela
│   ├── ServiceCard, CartAddedModal, CartSummary
│   ├── AreaPicker, PriceBreakdown
│   ├── DayList, TimeSlotGrid
│   ├── CustomerInfoForm, OtpCodeForm, MyAppointmentsModal
│   └── ui/                     # primitivos (Button, Modal, Spinner, EmptyState, ErrorState...)
├── hooks/useBooking.ts          # TanStack Query — bootstrap, disponibilidade do mês, cotação, mutations
├── hooks/useClinicId.ts         # lê o contexto de clinicId/basePath (nunca useParams direto)
├── store/                       # CartProvider — carrinho em memória, por clinicId
├── services/booking.service.ts  # camada HTTP, um método por endpoint (§5)
├── utils/
│   ├── cartTotals.ts            # helpers de área + toCartPayload (duração/preço NÃO são calculados no front)
│   ├── domain.ts                 # isDefaultDomain
│   ├── monthWindow.ts, discountLabel.ts
│   ├── format.ts, dates.ts
└── types/index.ts               # Clinic, Service, Professional, ServiceArea, Appointment, CartItem
```

Stack idêntica ao `frontend/` (React 19, TS strict, Vite 7, Tailwind v4,
React Router v7, TanStack Query v5) — ver `../CLAUDE.md` §"Diferenças" pra o
que diverge do painel autenticado.

---

## 7. Features atuais

- Catálogo de serviços com preço ("a partir de"), sem duração; agrupamento
  por categoria **não** foi implementado (o original tinha; decidido não entrar).
- Áreas de tratamento por serviço, com preço de tabela por área (`ServiceArea`).
- Preço, desconto e duração **sempre do backend**, pelas mesmas funções do
  agente de WhatsApp: combos do cadastro, regras de duração (piso, teto,
  passo) e política de desconto. O resumo mostra Total, Desconto (motivo só sem celular) e
  Valor final, e o valor final é o que fica gravado.
- Skip automático da etapa de serviço quando o catálogo tem 1 item.
- Profissional atribuído pelo backend (o conflito de horário é da clínica
  inteira, então a escolha não reservava a agenda de ninguém).
- Agenda do mês vigente: só os dias com horário aparecem; horários que já
  passaram hoje não são oferecidos; a criação recusa data fora da janela.
- Horário ocupado enquanto o cliente preenchia (409): volta para a agenda com
  aviso e grade atualizada.
- Carrinho multi-serviço no mesmo atendimento (não é "um agendamento por
  serviço" — é uma visita só, com duração somada).
- Criação de agendamento sem verificação prévia de telefone; confirmação via
  WhatsApp.
- "Meus agendamentos": consulta e cancelamento, com verificação por código
  via WhatsApp (OTP) — a única barreira de posse do número no site inteiro.
- Logo e favicon customizáveis por clínica (painel → "Site de Agendamento").
  O logo aparece nas boas-vindas (`ClinicWelcome`) de toda tela, não no header.
- Domínio próprio por clínica (painel → mesma página — ver §3).
- Botão "Voltar" no topo de toda etapa do wizard, exceto com catálogo de 1
  item onde ele levaria à lista de serviços (revisão, áreas, ou agenda sem
  áreas): ali ele some, e a lista (`/:clinicId`) redireciona sempre direto
  para o agendamento, mesmo com o carrinho cheio.

### Carrinho misto

Carrinho **misto** — alguns serviços com área configurada e outros sem — soma
as áreas escolhidas **e** a duração/preço próprios dos serviços que nenhum par
cobre (`duracao_do_carrinho`, `preco_de_tabela`). A duração passa uma vez só
por piso/teto/passo sobre o total; a faixa de desconto continua contando só as
áreas. Grade, cotação e criação (site e painel) usam a mesma conta.

---

## 8. Adiado / fora de escopo (decisão já tomada, não é esquecimento)

Da fase de planejamento original (`prd/009-site-agendamento-publico.md`):

- **Pagamento online** (o original usava iugu para sinal/pré-pagamento em
  alguns planos) — fora do MVP, não revisitado.
- **Tela administrativa** dentro do booking-site (config de salão, working
  plan) — é o `frontend/` (painel), não este app.
- **Migração de dados do SalonSoft antigo.**
- **i18n** além de pt-BR.

Da feature de domínio customizado (`prd/021-...`):

- **Múltiplos domínios por clínica** — uma clínica, um domínio.
- **Registro do domínio em si** — compra/DNS continuam manuais, por fora do
  sistema; o painel só orienta (mostra o registro a criar) e confirma a
  verificação.

### Decisões que mudaram no PRD 023 (reunião de outubro/2026)

- **Profissional:** deixou de ser escolhido pelo cliente, em todas as clínicas.
- **Duração:** deixou de ser exibida.
- **Calendário:** de grade semanal com dias desabilitados para lista dos dias
  com horário, só no mês vigente. O mês seguinte abre na virada — e no fim do
  mês, sem vaga, o cliente fica sem dia (a tela explica e oferece contato).
  A regra mora inteira em `scheduler/src/services/mes_vigente.py`.
- **Preço:** deixou de ser calculado no navegador. Antes o site cobrava sem
  primeira sessão, sem faixas e sem combos — mais caro que o WhatsApp para o
  mesmo pedido — e pedia horário com uma duração diferente da gravada.

### Decisão que já mudou desde o PRD original

O PRD 009 previa verificação de posse do número (SMS OTP) **antes de criar**
o agendamento, igual ao SalonSoft. Isso foi revisto: criar agendamento não
exige mais verificação (igual ao bot de WhatsApp, onde o número já é a
identidade da conversa) — só "Meus agendamentos" exige, porque ali alguém
veria/cancelaria o agendamento de outra pessoa só digitando o telefone dela.
Verificação também passou de SMS para **WhatsApp** (mesmo canal que o bot já
usa, sem precisar de um segundo provedor).

---

## 9. Deploy e ambientes

| Ambiente | URL | Projeto Vercel |
|---|---|---|
| Produção | `https://booking-site-neon.vercel.app` (+ domínios próprios por clínica) | `booking-site` |
| Dev | `https://booking-site-dev.vercel.app` | `booking-site` (mesmo projeto, env de Preview) |

Env vars: `VITE_API_BASE_URL`, `VITE_BOOKING_API_KEY` (não é segredo — é só
um filtro básico contra bots, mesmo padrão do `LEADS_INTAKE_API_KEY` da
landing page).

Deploy a partir da raiz do monorepo (não de dentro de `booking-site/`):

```bash
vercel deploy --yes --project booking-site          # preview/dev
vercel deploy --prod --yes --project booking-site   # produção
```

---

## 10. Referências

- `docs/work/prd/009-site-agendamento-publico.md` + `spec/009-...` — origem do produto, mapeamento do site de referência
- `docs/work/prd/013-limite-do-cloudformation.md` — por que as rotas públicas vivem numa Lambda só
- `docs/work/prd/021-dominio-customizado-booking-site.md` + `spec/021-...` — domínio próprio por clínica
- `docs/work/prd/023-booking-site-preco-fluxo-calendario.md` + `spec/023-...` — preço/desconto do agente, sem profissional, mês vigente
- `docs/work/prd/024-booking-site-meus-agendamentos-aviso-nome.md` + `spec/024-...` — "Meus agendamentos" pelo telefone normalizado, faixas de desconto à vista, aviso de agendamento repetido, nome de quem agenda
- `TASKS_LOG.md` — entradas `021-dominio-customizado` e `fix-booking-site-servico-unico` (bugs encontrados testando em produção)
- `../CLAUDE.md` — padrões de código, comandos, diferenças em relação ao `frontend/`
