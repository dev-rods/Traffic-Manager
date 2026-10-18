# Spec — 025 Booking-site: acabamento visual

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/025-booking-site-acabamento-visual.md`
- **Branch:** `feat/025-booking-site-visual`

---

## 1. Tokens (`src/index.css`)

- `ink-*` deixa o tom quente/marrom e vira **grafite levemente frio**, no mesmo
  matiz do `muted-700` (#515164) que a referência usa no botão neutro. O
  impeccable pede neutro com leve tinta, nunca cinza puro. `ink-500` (texto
  secundário) ≥ 4.5:1 sobre o fundo.
- `accent-*` deixa a terracota e vira **creme/dourado**, a família do
  `cream-*` já usado no "Reservar". Texto sobre acento usa `accent-700`.
- Fundo da página quase branco (`ink-50`), cartão branco tingido (`surface`).
- Sombra suave de cartão como token (`--shadow-card`).

## 2. Componentes

| Arquivo | Alteração |
|---|---|
| `components/ClinicWelcome.tsx` (novo) | Avatar + "Seja bem-vindo(a)" + nome. Usado pela Home e pelo Booking. |
| `components/ui/SectionTitle.tsx` (novo) | `h2` em frase normal, negrito, grafite. Substitui os títulos em caixa alta do Booking. |
| `pages/Home.tsx` | Usa `ClinicWelcome`. |
| `pages/Booking.tsx` | `ClinicWelcome` no topo de todas as etapas; `SectionTitle`; "Continuar" em largura total; espaçamento menor; "Voltar" mais discreto. |
| `layouts/BookingChrome.tsx` | `main` com `py-6`. |
| `components/CartSummary.tsx` | Cartão com sombra suave; nome em negrito; data com ícone de relógio; remover em botão rosa com lixeira. |
| `components/DayList.tsx` | Mês centralizado; faixa horizontal de blocos compactos (dia da semana + número), rolável com snap; selecionado em `accent-100` com barra dourada; sem o mês em cada dia. `aria-label` igual. |
| `components/TimeSlotGrid.tsx` | Blocos no mesmo estilo dos dias (neutro; selecionado em creme com borda dourada). |
| `components/AreaPicker.tsx`, `DiscountTiersNote.tsx` | Herdam o acento novo; nota de faixas em creme com texto `accent-700`. |
| `components/ui/icons.tsx` | `IconClock`, `IconTrash`. |
| `components/ServiceCard.tsx` | Nome em negrito grafite; preço com contraste novo. |

## 3. Testes

Os testes de comportamento continuam iguais (`aria-label` dos dias, nomes dos
botões). Novo teste do `ClinicWelcome` (com e sem logo). Revisão visual em 375
e 1280 px com puppeteer, comparando com os prints da referência.
