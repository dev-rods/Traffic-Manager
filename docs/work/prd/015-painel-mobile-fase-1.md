# PRD - 015 Painel no mobile: Agenda, Pacientes e Registro de Sessão

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Tornar usáveis em celular as três telas que a operação do dia a dia mais
toca: **Agenda**, **Pacientes** e o modal de **Registro de sessão**. Hoje o
painel é utilizável apenas em desktop.

---

## 2. Contexto

Conferido no código: **zero breakpoints** (`sm:`/`md:`/`lg:`) em todo o
frontend. O painel foi construído inteiro para desktop, e isso aparece em
pontos concretos:

- **Sidebar fixa de 224px** (`AppLayout.tsx`, `w-56 flex-shrink-0`), sem modo
  colapsado. Num celular de 375px sobra menos de 150px para o conteúdo.
- **`WeekGrid` sempre desenha as 7 colunas da semana**
  (`grid-template-columns: repeat(7, 1fr)`), o que resulta em colunas
  ilegíveis em tela estreita.
- **`AppointmentPopover` tem 320px fixos** (`w-80`), posicionado à direita do
  toque - não cabe do lado numa tela de 375px.
- **A régua de filtros de Pacientes** é uma linha `flex` sem `flex-wrap` com
  busca + 3 seletores, que estoura a largura da tela.
- **`Modal`** (`components/ui/Modal.tsx`) é centralizado com `max-w-md/lg`,
  sem variante de tela cheia. Ele é a base de **13 modais**, incluindo os
  três que mais interessam aqui: `CreateAppointmentModal`,
  `EditAppointmentModal` e `RegistroDeSessaoModal`.

### Uma peça já existe pronta

O PR #63 (21/09/2026) deu ao `WeekGrid` um modo de **dia único**, pensado
originalmente para telas cheias em desktop (`expandido`, controlado por
`onDayClick`). Ele já resolve o problema central do mobile - renderizar um
dia só, com a largura toda - sem precisar de grid novo. Em mobile este modo
deixa de ser um recurso opcional e vira **o padrão**.

---

## 3. Decisões

| Pergunta | Decisão |
|---|---|
| Breakpoint | `md` (768px) do Tailwind, sem customização. Abaixo disso é "mobile" |
| Sidebar em mobile | Vira **drawer**: escondida por padrão, abre por um botão hambúrguer no cabeçalho |
| Agenda em mobile | Abre direto no **modo dia único** (reuso do `expandido` do PR #63); navegação por dia com botões grandes |
| Popover de agendamento em mobile | Vira **bottom sheet** (desliza de baixo), não flutua ao lado do toque |
| Tabela de Pacientes em mobile | Vira **lista de cards** |
| Filtros de Pacientes em mobile | Colapsam num **drawer de filtro**, acionado por um botão |
| Modais (`Modal.tsx`) em mobile | Viram **tela cheia**, e não um retângulo centralizado |
| Ações em lote (seleção, WhatsApp em massa) | Mantidas como estão - checkbox na lista de cards funciona igual à tabela |

### Por que a régua de filtros vira drawer, e não `flex-wrap`

`flex-wrap` seria o remendo mais barato, mas empilha 4 campos de largura
variável um sobre o outro e ainda sobra a régua de ações em lote acima. Um
drawer com um botão **Filtros** (mostrando quantos estão ativos) é o padrão
mais previsível em tela estreita, e o mesmo padrão que a sidebar já vai
usar - um componente de drawer serve aos dois casos.

### Por que o popover vira bottom sheet

O popover hoje se ancora em `anchorRect.right + 8`: ele pressupõe espaço à
direita do toque. Numa tela de 375px, uma caixa perto da borda direita não
tem para onde abrir, e `Math.min(left, window.innerWidth - 340)` ficaria
sobrepondo o próprio agendamento tocado. Bottom sheet não depende de onde
o toque aconteceu.

---

## 4. Escopo

### Dentro

- Sidebar responsiva (drawer abaixo de `md`).
- `WeekGrid`/`AgendaPage`: modo dia único como padrão abaixo de `md`,
  navegação por dia, alvos de toque de 44px nas caixas de agendamento.
- `AppointmentPopover`: variante bottom sheet abaixo de `md`.
- `Modal.tsx`: variante tela cheia abaixo de `md` - beneficia
  automaticamente `CreateAppointmentModal`, `EditAppointmentModal` e
  `RegistroDeSessaoModal`, sem tocar nesses três arquivos além do
  necessário para o conteúdo interno caber.
- `PatientsTable` → lista de cards abaixo de `md`.
- Filtros de `PacientesPage` → drawer abaixo de `md`.
- `RegistroDeSessaoModal`/`AplicacoesField`: conferir que o conteúdo
  interno (que já usa `flex-wrap`) se comporta bem em tela cheia estreita.

### Fora (fica para uma fase 2, fora deste PRD)

- Relatórios, Catálogo (Serviços/Áreas/Descontos/Duração/Horários), Bot,
  Leads, FAQ, Configurações, Usuários.
- PWA / instalação como app / modo offline.
- Gestos avançados (swipe para cancelar, arrastar para remarcar).
- Redesenho visual - o objetivo é caber e ser tocável, não uma repaginação.

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `frontend/src/components/ui/Modal.tsx` | modificar | Variante tela cheia abaixo de `md` |
| `frontend/src/layouts/AppLayout.tsx` | modificar | Sidebar vira drawer; cabeçalho mobile com hambúrguer |
| `frontend/src/pages/agenda/AgendaPage.tsx` | modificar | Forçar modo dia único abaixo de `md` |
| `frontend/src/pages/agenda/components/WeekGrid.tsx` | modificar | Alvos de toque; ajustes de navegação por dia |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | modificar | Variante bottom sheet abaixo de `md` |
| `frontend/src/pages/pacientes/PacientesPage.tsx` | modificar | Filtros migram para drawer abaixo de `md` |
| `frontend/src/pages/pacientes/components/PatientsTable.tsx` | modificar | Lista de cards abaixo de `md` |
| `frontend/src/pages/pacientes/components/PatientCard.tsx` | criar | O card da lista mobile |
| `frontend/src/components/ui/Drawer.tsx` | criar | Base compartilhada: sidebar, filtros de Pacientes |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx` | conferir | Sem mudança estrutural esperada; validar em tela estreita |

---

## 6. Dependências e riscos

- **Dependências:** nenhuma nova lib. Tailwind v4 já dá os breakpoints
  (`md:`) e utilitários de flex/grid necessários.
- **Risco de regressão no desktop:** `Modal.tsx` e `WeekGrid.tsx` são
  compartilhados por várias telas. Toda mudança neles usa `md:` para
  isolar o comportamento novo - o desktop atual não pode mudar.
- **Risco de teste manual:** não há como testar toque, gesto ou teclado
  virtual em CI. A verificação final é no navegador do celular, e cada
  fase da spec fecha com uma lista do que precisa ser tocado à mão.

---

## Status

- [x] Pendente
- [ ] Spec gerada
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
