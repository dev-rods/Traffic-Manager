# Spec - 015 Painel no mobile: Agenda, Pacientes e Registro de Sessão

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/015-painel-mobile-fase-1.md`

---

## 1. Resumo

Quatro entregas, cada uma isolada por `md:` para não tocar o desktop:
**(A)** um `Drawer` base reutilizado por sidebar e filtros; **(B)** `Modal`
com variante tela cheia, que resolve os 13 modais de uma vez, incluindo o
de registro de sessão; **(C)** a Agenda como lista do dia abaixo de `md`;
**(D)** Pacientes em lista de cards com filtros no drawer.

A ordem de implementação segue essa letra: A e B são a base que C e D
consomem.

**A seção 2 reverte um item do PRD:** a Agenda em mobile vira lista
cronológica, e não a grade de dia único que o PRD propôs. O motivo está
medido lá.

---

## 2. Revisão: a Agenda em mobile é LISTA, não grade

O PRD propôs reusar o modo "dia único" do PR #63. **Medi antes de aceitar a
própria proposta, e ela não se sustenta:**

```
grade de 7h as 22h x 112px/hora = 1680px
tela util de celular ~640px     = 2,6 telas de rolagem para ver UM dia

alvo de toque de 44px           = 23,6 minutos de agenda
```

Os dois números matam a ideia. O segundo é o pior: esticar uma sessão de 10
minutos até 44px tocáveis faz ela ocupar 23,6 minutos de espaço visual, e o
`distribuiEmColunas` (que usa `intervaloVisual`, não o horário real) jogaria
duas sessões seguidas em colunas separadas - partindo ao meio uma largura que
já é estreita. Densidade e toque são inconciliáveis numa grade de horário em
375px.

**Em mobile a Agenda do dia vira uma lista cronológica.** Cada sessão é uma
linha com horário, nome, áreas e duração - naturalmente acima de 44px, sem
sobreposição possível, e mostrando só o que existe em vez de 15 horas de
grade vazia. É o padrão "Agenda/Schedule" de todo calendário em celular, e
pela mesma razão.

O `expandido` do PR #63 **continua existindo e continua sendo de desktop**.
Não é desperdício: ele resolveu o problema dele lá.

### O que se perde, e por que aceito

A grade deixa ver **buraco livre** e permite tocar num vazio para agendar
(`onSlotClick`). A lista não mostra vazio.

Aceito porque o pedido do André foi *"não é possível **acompanhar** a agenda
pelo mobile"* - acompanhar é leitura, e leitura é o que a lista faz melhor. E
agendar continua possível pelo botão **+ Novo agendamento**, que não depende
da grade: ele pergunta data e hora usando a API de `available-slots`, que
conhece os buracos melhor que o olho.

---

## 3. Decisão de desenho: o componente `Drawer`

Sidebar (fixa hoje, vira "abre por cima") e filtros de Pacientes (hoje uma
linha, viram "abre por cima") são o **mesmo padrão de interação**: painel
lateral, overlay escuro atrás, fecha ao tocar fora ou no X. Construir um só
componente e reusar evita duas implementações de foco/scroll-lock/Esc
divergindo com o tempo - é a mesma razão pela qual `Modal.tsx` já é
compartilhado por 13 telas.

```tsx
// components/ui/Drawer.tsx
interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  side?: 'left' | 'right'   // sidebar = left, filtros = right
  children: React.ReactNode
}
```

Reaproveita o `overlayRef` + `Esc` + `body.style.overflow` que `Modal.tsx`
já tem - vale extrair esse pedaço para um hook (`useOverlayLock`) usado
pelos dois, em vez de duplicar.

---

## 4. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `frontend/src/components/ui/Drawer.tsx` | Painel lateral compartilhado |
| `frontend/src/hooks/useOverlayLock.ts` | Esc + scroll-lock, extraído de `Modal.tsx` para os dois usarem |
| `frontend/src/pages/pacientes/components/PatientCard.tsx` | Card de paciente para a lista mobile |
| `frontend/src/pages/pacientes/components/FiltrosDePacientesDrawer.tsx` | Os 3 filtros + data, dentro do `Drawer` |
| `frontend/src/hooks/useMediaQuery.ts` | `useMediaQuery('(min-width: 768px)')`, para o que não dá para decidir só com classe CSS - trocar grade por lista é escolher outro componente, não esconder um |
| `frontend/src/pages/agenda/components/AgendaDoDia.tsx` | A lista cronológica do dia, em mobile |

---

## 5. Arquivos a modificar

### A. Base

| Arquivo | Alterações |
|---|---|
| `components/ui/Modal.tsx` | Usa `useOverlayLock`. Abaixo de `md`: `inset-0` sem padding, sem `rounded-xl`, sem `max-w-*` - ocupa a tela inteira. Acima de `md`: comportamento atual, intocado |

### B. Layout / navegação

| Arquivo | Alterações |
|---|---|
| `layouts/AppLayout.tsx` | Abaixo de `md`: `<aside>` sai do fluxo e vira conteúdo do `Drawer` (`side="left"`), fechado por padrão. Cabeçalho novo, fixo no topo, com botão hambúrguer + nome da clínica - substitui a visão permanente da sidebar. Acima de `md`: sidebar como está hoje |

### C. Agenda

| Arquivo | Alterações |
|---|---|
| `pages/agenda/AgendaPage.tsx` | `useMediaQuery` decide `ehMobile`. Quando `true`: renderiza `AgendaDoDia` em vez de `WeekGrid`, e a navegação anda **de dia em dia** (reusa `handlePrev`/`handleNext` no modo que já existe para `diaExpandido`). O dia começa em hoje, ou na primeira data disponível |
| `pages/agenda/components/WeekGrid.tsx` | **Intocado.** A grade continua sendo de desktop, com `ALTURA_MINIMA = 18` como está desde 20/09 |
| `pages/agenda/components/AppointmentPopover.tsx` | Abaixo de `md`: abandona `anchorRect` para posicionamento - vira `fixed bottom-0 inset-x-0`, desliza de baixo, `rounded-t-xl`, sem depender de onde o toque ocorreu. Acima de `md`: intocado |

### D. Pacientes

| Arquivo | Alterações |
|---|---|
| `pages/pacientes/PacientesPage.tsx` | A linha `flex items-center gap-3` de filtros vira: `PatientSearch` sempre visível + botão **Filtros** (abaixo de `md`) que abre `FiltrosDePacientesDrawer`. O badge do botão mostra quantos filtros estão ativos (`nextVisitFilter !== 'all'`, etc., contados) |
| `pages/pacientes/components/PatientsTable.tsx` | Abaixo de `md`: renderiza `<PatientCard>` num `<ul>` em vez da `<table>`. Acima de `md`: tabela atual, intocada. Mesmas props (`onSelect`, `onWhatsApp`, `onPauseBot`, `onDelete`, seleção) repassadas ao card |

---

## 6. Conteúdo do `PatientCard`

Same-props que a linha da tabela, reorganizado para leitura vertical:

```
┌─────────────────────────────────┐
│ ☐  [B] Beatriz Nogueira    Fem  │
│    (11) 97770-0001              │
│    3 visitas · última 15/09     │
│    próxima: 23/09               │
│                    [wpp] [•••]  │
└─────────────────────────────────┘
```

Nome + telefone sempre visíveis; visitas/última/próxima numa segunda
linha, menor.

**WhatsApp e pausar bot ficam visíveis** (44px cada); **excluir vai para o
menu `•••`**. Os dois primeiros são de uso diário e merecem um toque só; o
terceiro é destrutivo, e um passo a mais ali é proteção, não atrito.

---

## 7. Decisões tomadas (eram perguntas na primeira versão)

1. **Altura das caixas na grade.** A pergunta desapareceu com a revisão da
   seção 2: a grade não vai a mobile, então `ALTURA_MINIMA` continua 18px e
   o trade-off "tocável vs. denso" não existe mais. Na lista, cada linha é
   naturalmente maior que 44px.
2. **Ações do card de paciente.** WhatsApp e pausar bot visíveis, excluir no
   menu `•••`. Critério: frequência de uso para os dois primeiros,
   e um passo a mais na frente do destrutivo.

---

## 8. Ordem de implementação

1. `useOverlayLock` (extração, sem mudança de comportamento) + `useMediaQuery`.
2. `Drawer.tsx`, testado isolado.
3. `Modal.tsx` com variante tela cheia - testar os 13 consumidores existentes não quebraram no desktop.
4. `AppLayout.tsx`: sidebar em drawer, cabeçalho mobile.
5. Agenda: `AgendaDoDia` (lista) → `AppointmentPopover` (bottom sheet) → `AgendaPage` (escolhe grade ou lista).
6. Pacientes: `PatientCard` → `PatientsTable` (troca condicional) → `FiltrosDePacientesDrawer` → `PacientesPage`.
7. `RegistroDeSessaoModal`: sem mudança estrutural esperada (herda a tela cheia do `Modal`); abrir em viewport de 375px e conferir que `AplicacoesField` não estoura.

---

## 9. Testes obrigatórios

| Arquivo | O que trava |
|---|---|
| `Drawer.test.tsx` | Abre/fecha, Esc, clique fora, scroll-lock |
| `Modal.test.tsx` (existente, estender) | Abaixo de `md` renderiza sem `max-w-*`; acima de `md` comportamento não muda |
| `useMediaQuery.test.ts` | Responde a mudança de `matchMedia`, sem vazar listener |
| `AgendaDoDia.test.tsx` | Ordena por horário; mostra áreas e duração; estado vazio; toque chama `onAppointmentClick` |
| `PatientsTable.test.tsx` (estender) | Abaixo de `md` renderiza `PatientCard`; acima de `md` renderiza `<table>`; mesmas props chegam nos dois |

**O que não dá para testar em CI** - fica para verificação manual, no
navegador do celular ou emulador de dispositivo:

- Toque real nas linhas da lista (44px é teórico até tocar).
- Bottom sheet do popover sobre teclado virtual aberto.
- Scroll da lista de pacientes com o drawer de filtro aberto.
- `RegistroDeSessaoModal` em tela cheia com o teclado do celular aberto,
  conferindo que o botão Salvar continua alcançável.
