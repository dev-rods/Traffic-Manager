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
2. Escolhe o(s) serviço(s). Se a clínica só tem **um** serviço no catálogo,
   essa escolha é pulada: o serviço já chega pré-selecionado.
3. Se o serviço tiver áreas de tratamento configuradas, escolhe quais.
4. Escolhe o profissional — pulado se a clínica só tem **um** cadastrado;
   bloqueado com aviso se não tem **nenhum** (não há quem atender).
5. Escolhe data e horário, numa grade semanal com os mesmos dias
   disponíveis/lotados que o bot de WhatsApp calcularia.
6. Informa nome e celular.
7. Agendamento é criado na hora — **sem verificação prévia do número**. A
   confirmação chega por WhatsApp (mesmo template `BOOKED` que o bot usa).
8. "Meus agendamentos" (botão no header): consulta ou cancela agendamentos
   existentes pelo celular — **esse caminho exige confirmar o número por
   código enviado via WhatsApp** (único lugar do site com essa verificação).

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
| Disponibilidade | `AvailabilityEngine.get_days_status` | Mesmo cálculo de dias abertos/lotados/fechados que o bot usa pra oferecer horário |
| Criação/cancelamento | `AppointmentService.completo(db)` | Mesma regra de negócio, inclusive a conversão de gclid pro Google Ads (por isso é sempre `.completo()`, nunca o construtor cru) |
| Confirmação | `TemplateService` + template `BOOKED` | A mensagem que chega no WhatsApp do cliente é a mesma customizável por clínica que o bot manda |
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
| GET | `/public/clinics/{clinicId}/bootstrap` | Clínica, serviços, profissionais, áreas — carregado uma vez no boot de cada página |
| GET | `/public/resolve-domain?host=` | Domínio próprio → `clinic_id` (só no `CustomDomainLayout`) |
| GET | `/public/clinics/{clinicId}/availability?dates=&totalDuration=` | Status por dia (`CLOSED\|FULL\|AVAILABLE`) + horários livres da semana visível |
| POST | `/public/clinics/{clinicId}/verify/send` | Envia código por WhatsApp — só usado por "Meus agendamentos" |
| POST | `/public/clinics/{clinicId}/verify/confirm` | Confirma o código, devolve token de sessão — idem |
| POST | `/public/clinics/{clinicId}/appointments` | Cria o agendamento (sem token/verificação) |
| GET | `/public/clinics/{clinicId}/my-appointments?phone=&token=` | Lista agendamentos do cliente (exige token) |
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
│   └── BookingChrome.tsx       # header + favicon + modal, compartilhado pelos dois
├── pages/
│   ├── Home.tsx                # lista de serviços (ou auto-skip, se só há um)
│   └── Booking.tsx             # o wizard: áreas → profissional → agenda → dados → sucesso
├── components/
│   ├── ServiceCard, CartAddedModal, CartSummary
│   ├── AreaPicker, ProfessionalPicker
│   ├── WeekPicker, TimeSlotGrid
│   ├── CustomerInfoForm, OtpCodeForm, MyAppointmentsModal
│   └── ui/                     # primitivos (Button, Modal, Spinner, EmptyState, ErrorState...)
├── hooks/useBooking.ts          # TanStack Query — bootstrap, disponibilidade, mutations
├── hooks/useClinicId.ts         # lê o contexto de clinicId/basePath (nunca useParams direto)
├── store/                       # CartProvider — carrinho em memória, por clinicId
├── services/booking.service.ts  # camada HTTP, um método por endpoint (§5)
├── utils/
│   ├── cartTotals.ts            # duração/preço do carrinho, considerando overrides de área
│   ├── domain.ts                 # isDefaultDomain
│   ├── format.ts, weekDates.ts
└── types/index.ts               # Clinic, Service, Professional, ServiceArea, Appointment, CartItem
```

Stack idêntica ao `frontend/` (React 19, TS strict, Vite 7, Tailwind v4,
React Router v7, TanStack Query v5) — ver `../CLAUDE.md` §"Diferenças" pra o
que diverge do painel autenticado.

---

## 7. Features atuais

- Catálogo de serviços com duração e preço ("a partir de"); agrupamento por
  categoria **não** foi implementado (o original tinha; decidido não entrar).
- Áreas de tratamento por serviço, com duração/preço podendo sobrescrever o
  valor base do serviço (`ServiceArea`).
- Skip automático de etapas sem decisão real: serviço único (catálogo com 1
  item) e profissional único — nos dois casos o item é pré-selecionado e a
  tela correspondente nem aparece.
- Aviso bloqueante quando a clínica não tem **nenhum** profissional
  cadastrado (sem isso, o calendário apareceria todo fechado sem explicação).
- Disponibilidade real por semana (não é agenda fake): mesma engine do bot,
  distinguindo "fechado" (sem regra de agenda) de "lotado" (tem regra, sem
  vaga) de "disponível".
- Carrinho multi-serviço no mesmo atendimento (não é "um agendamento por
  serviço" — é uma visita só, com duração somada).
- Criação de agendamento sem verificação prévia de telefone; confirmação via
  WhatsApp.
- "Meus agendamentos": consulta e cancelamento, com verificação por código
  via WhatsApp (OTP) — a única barreira de posse do número no site inteiro.
- Logo e favicon customizáveis por clínica (painel → "Site de Agendamento").
- Domínio próprio por clínica (painel → mesma página — ver §3).
- Botão "Voltar" sempre presente, no topo, em toda etapa do wizard.

### Limitação conhecida

Carrinho **misto** — alguns serviços com área configurada e outros sem —
não tem a duração/preço somados corretamente pelo
`AppointmentService.create_appointment` do backend (pré-existente à criação
do booking-site, não específico dele). `utils/cartTotals.ts` documenta o
cálculo do lado do front; o lado do backend não foi revisitado.

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
- `TASKS_LOG.md` — entradas `021-dominio-customizado` e `fix-booking-site-servico-unico` (bugs encontrados testando em produção)
- `../CLAUDE.md` — padrões de código, comandos, diferenças em relação ao `frontend/`
