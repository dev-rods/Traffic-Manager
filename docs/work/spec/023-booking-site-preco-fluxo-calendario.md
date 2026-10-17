# Spec — 023 Booking-site: preço certo, fluxo enxuto e calendário do mês

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/023-booking-site-preco-fluxo-calendario.md`
- **Branch:** `feat/022-booking-site-preco-fluxo-calendario`

---

## 1. Resumo

O booking-site passa a pedir ao backend **tudo o que hoje calcula sozinho**:
duração da sessão, preço e desconto. O backend responde com as **mesmas
funções** que o agente de WhatsApp usa: combos, `calcula_duracao`, política de
desconto. Para isso, três peças que hoje vivem dentro de `ToolExecutor`
(`ai_tools.py`) ou de `AppointmentService` viram funções de módulo,
chamadas pelos dois lados. O front perde a etapa de profissional, as durações
visíveis e a grade semanal, e ganha uma lista dos dias disponíveis do mês
vigente e um resumo com Total, Desconto e Valor final.

O `conversation_engine` legado **não é tocado**: não atende nenhuma clínica
(PRD 020 §2.4) e vai ser apagado. A cópia dele do cálculo de desconto morre
junto.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/services/politica_de_desconto.py` | Decisão do desconto (personalizado > primeira sessão / faixas), preço de tabela do carrinho, texto do preço para a confirmação |
| `scheduler/src/services/carrinho.py` | Normaliza o carrinho do site (serviços + pares), aplica combos, devolve duração/preço/desconto: o ponto único que `quote`, `availability` e `create_appointment` públicos chamam |
| `scheduler/src/services/mes_vigente.py` | Janela de agendamento do site (hoje → último dia do mês) no fuso da clínica |
| `scheduler/src/functions/public_booking/quote.py` | `POST /public/clinics/{clinicId}/quote` |
| `scheduler/tests/unit/test_politica_de_desconto.py` | Caracterização: mesmas saídas que `_calcula_desconto` dava antes da extração |
| `scheduler/tests/unit/test_carrinho_do_site.py` | Paridade site × agente (preço, desconto, duração, combos) |
| `scheduler/tests/unit/test_mes_vigente.py` | Bordas da janela (último dia, virada, fuso) |
| `scheduler/tests/unit/test_days_status_reaproveita_janelas.py` | `get_days_status` = `janelas_livres` + grade; filtra horário passado |
| `scheduler/tests/mocks/public_booking/{quote,availability,create_appointment}.json` | Mocks de invoke local |
| `scheduler/tests/integration/023-booking-site-preco-fluxo-calendario.md` | Casos de teste manuais (curl) |
| `scheduler/tests/postman/023-booking-site-preco-fluxo-calendario.postman_requests.json` | Requests no padrão de `tests/postman/CLAUDE.md` |
| `booking-site/src/components/DayList.tsx` (+ `.test.tsx`) | Lista dos dias disponíveis do mês (substitui `WeekPicker`) |
| `booking-site/src/components/PriceBreakdown.tsx` (+ `.test.tsx`) | Total / Desconto / Valor final + combos aplicados |
| `booking-site/src/utils/discountLabel.ts` (+ `.test.ts`) | `discountReason` → texto legível |
| `booking-site/src/utils/monthWindow.ts` (+ `.test.ts`) | Datas de hoje até o fim do mês (para a chamada de disponibilidade) |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/services/ai_tools.py` | `_calcula_desconto` delega a `politica_de_desconto.decide`; `_troca_por_combos` delega a `carrinho.troca_por_combos`. Contrato das tools inalterado |
| `scheduler/src/services/appointment_service.py` | Bloco 2b (preço automático) chama `politica_de_desconto.preco_de_tabela`; duração sem área chama `duration_rules.duracao_do_carrinho` |
| `scheduler/src/services/duration_rules.py` | Nova `duracao_do_carrinho(db, clinic_id, service_ids, service_area_pairs)`, extraída do `create_appointment` |
| `scheduler/src/services/availability_engine.py` | `get_days_status` usa `janelas_livres`; novo parâmetro `a_partir_de` (minutos do dia de hoje) |
| `scheduler/src/functions/public_booking/availability.py` | Recebe o carrinho; duração no backend; aplica `mes_vigente`; filtra horário passado |
| `scheduler/src/functions/public_booking/create_appointment.py` | Usa `carrinho.cota`; passa desconto; valida mês e horário; confirmação com desconto + orientações |
| `scheduler/src/functions/public_booking/bootstrap.py` | Expõe `clinic.phone` (contato do estado vazio) |
| `scheduler/src/functions/public_booking/router.py` | Rota `POST public/clinics/{clinicId}/quote` |
| `scheduler/sls/functions/public_booking/interface.yml` | Evento HTTP `quote` (sem função nova, PRD 013) |
| `booking-site/src/pages/Booking.tsx` | Sem etapa `professional`; disponibilidade do mês; cotação; confirmação em dois passos na etapa `customer` |
| `booking-site/src/components/ServiceCard.tsx` | Sem duração/ícone de relógio |
| `booking-site/src/components/AreaPicker.tsx` | Sem duração; só preço de tabela da área |
| `booking-site/src/components/CartSummary.tsx` | Sem duração; totais vêm de `PriceBreakdown` |
| `booking-site/src/components/CustomerInfoForm.tsx` | `onPhoneValid(phone)` para refazer a cotação; texto do botão |
| `booking-site/src/hooks/useBooking.ts` | `useMonthAvailability`, `useQuote`; remove `useWeekAvailability` |
| `booking-site/src/services/booking.service.ts` | `availability(clinicId, dates, cart)`, `quote(clinicId, cart, phone?)` |
| `booking-site/src/store/CartProvider.tsx`, `cartContext.ts` | Remove `professionalId` |
| `booking-site/src/types/index.ts` | `QuoteResponse`, `CartPayload`; `Clinic.phone`; `WizardStep` sem `professional`; `CreateAppointmentPayload` sem `professionalId` |
| `booking-site/src/utils/cartTotals.ts` (+ test) | Remove `computeCartTotals` (duração e preço passam a ser do backend); mantém helpers de áreas e `buildServiceAreaPairs` |
| `booking-site/src/utils/format.ts` (+ test) | Remove `formatDuration` (sem uso) |
| `booking-site/src/pages/Booking.test.tsx` | Fluxo sem profissional; resumo com desconto; mês sem vaga |
| `booking-site/docs/visao-geral.md` | §2, §5, §7 atualizados; nova "Decisão que já mudou" (profissional, mês) |
| `booking-site/CLAUDE.md` | Remover menção a profissional por carrinho; "preço e duração vêm do backend" |
| `docs/work/prd/023-...md`, `TASKS_LOG.md` | Status e registro |

---

## 4. Arquivos a remover

| Arquivo | Motivo |
|---------|--------|
| `booking-site/src/components/ProfessionalPicker.tsx` | Etapa eliminada (PRD §3 item 7) |
| `booking-site/src/components/WeekPicker.tsx` | Substituído por `DayList` (só dias disponíveis, mês vigente) |

`slots.py` (`/available-slots`) **fica**: o PRD 009 o mantém por compatibilidade e
ele não é escopo aqui.

---

## 5. Ordem de implementação

Backend primeiro, e deploy dele antes do front: o backend novo continua
aceitando o payload do front antigo (§6, compatibilidade).

1. **Testes de caracterização** do desconto e dos combos do agente, rodando contra o
   código **atual** (`test_politica_de_desconto.py` importando `ToolExecutor`).
   Passam antes de qualquer extração.
2. `politica_de_desconto.py` + `ai_tools` delegando. Caracterização continua verde.
3. `carrinho.troca_por_combos` + `ai_tools._troca_por_combos` delegando. `test_combos.py` verde.
4. `duration_rules.duracao_do_carrinho` + `preco_de_tabela` usados por `AppointmentService`.
   Suíte de duração e criação (`test_duration_rules*`, `test_criacao_pelo_painel`,
   `test_duracao_*`) verde.
5. `availability_engine.get_days_status` sobre `janelas_livres` + `a_partir_de`.
6. `mes_vigente.py`, `carrinho.cota`.
7. Handlers: `quote.py`, `availability.py`, `create_appointment.py`, `bootstrap.py`,
   router, interface.yml.
8. `python -m unittest discover -s tests/unit` inteiro verde → deploy **dev** do scheduler →
   curl (§8).
9. Front: types → service → hooks → utils → componentes → `Booking.tsx` → testes.
10. `npm run lint && npm run test && npm run build` → deploy preview → revisão visual
    em 375px e 1280px (§6.14) → teste ponta a ponta em dev.
11. Docs, mocks, Postman, TASKS_LOG, status do PRD → `/no-mistakes`.

---

## 6. Detalhes por arquivo

### 6.1 `scheduler/src/services/politica_de_desconto.py` (criar)

Mesmo estilo dos módulos irmãos (`desconto_personalizado`, `primeira_visita`):
docstring explicando **por que** existe (três cópias do cálculo; o site
cobrava diferente do agente), funções puras onde der.

```python
RAZAO_PRIMEIRA = "first_session"
RAZAO_TIER_2 = "tier_2"
RAZAO_TIER_3 = "tier_3"
# RAZAO_PERSONALIZADA vem de desconto_personalizado.RAZAO

class Decisao(NamedTuple):
    pct: Union[int, Decimal]
    razao: Optional[str]
    is_first: bool

def decide(db, clinic_id: str, phone: Optional[str], qtd_areas: int) -> Decisao
def preco_de_tabela(db, service_ids: List[str], service_area_pairs: List[Dict]) -> Optional[int]
def texto_do_preco(original: Optional[int], final: Optional[int], pct, razao, qtd_areas: int) -> str
```

- `decide`: **cópia literal** da lógica de `ai_tools._calcula_desconto`
  (linhas após o total): personalizado (se `phone`) vence com `(pct, RAZAO, False)`;
  senão lê `discount_rules` ativa; sem regra → `(0, None, False)`;
  `is_first = e_primeira_visita(...)` só se houver `phone` (sem telefone → `False`);
  candidatos `first_session` e `tier_3` **elif** `tier_2`; vence o maior pct.
  Sem `phone`, a decisão só pode dar faixa de áreas: é o que o cliente vê
  antes de digitar o celular.
- `preco_de_tabela`: a query exata do bloco 2b de `create_appointment`
  (pares → `SUM(COALESCE(sa.price_cents, s.price_cents))` com `LEFT JOIN`
  e `sa.active`; sem pares → soma de `services.price_cents`). Devolve `None`
  quando zero/ausente (mesma semântica de hoje).
- `texto_do_preco`: usado só na confirmação do site.
  - Sem preço → `"Consultar"` (o que o site manda hoje).
  - Sem desconto → `"R$ 150,00"`.
  - Com desconto → `"~R$ 200,00~ → R$ 170,00 (15% off - primeira sessão)"`. É o
    mesmo formato que o bot usava em `_format_price_with_discount`, para a
    clínica reconhecer a mensagem. Rótulos: `first_session` → `primeira sessão`,
    `tier_*` → `{n} áreas`, `personalizado` → `desconto especial`.
  - Moeda com milhar (`R$ 1.200,00`), igual a `_resultado_de_desconto.reais`.

**`ai_tools._calcula_desconto`** passa a ser: soma do total (query atual
**mantida**, sem mudar para `preco_de_tabela`, porque a query do agente usa
`JOIN` sem filtro de `sa.active` e trocá-la mudaria preço do agente, fora do
escopo) → se zero, retorno atual → `d = decide(db, clinic_id, phone, len(pairs))`
→ `_resultado_de_desconto(total, d.pct, d.razao, d.is_first)`. A divergência
das duas queries de preço fica registrada como observação no TASKS_LOG.

### 6.2 `scheduler/src/services/carrinho.py` (criar)

O carrinho do site em um lugar só. Os três handlers públicos chamam
`cota`/`duracao`; nenhum handler monta preço ou duração à mão.

```python
class Cotacao(NamedTuple):
    pares: List[Dict]            # depois dos combos
    combos: List[Dict]           # [{"de": [...], "para": str, "economia_cents": int}]
    duracao_minutos: int
    original_cents: Optional[int]
    final_cents: Optional[int]
    desconto: Decisao
    qtd_areas: int

def troca_por_combos(db, clinic_id, pares) -> Tuple[List[Dict], List[Dict]]
def cota(db, clinic_id, service_ids, service_area_pairs, phone=None) -> Cotacao
def valida_carrinho(db, clinic_id, service_ids, service_area_pairs) -> None  # levanta CarrinhoInvalido
```

- `troca_por_combos`: corpo atual de `ToolExecutor._troca_por_combos` movido
  para cá (mesmo `preco_de`, mesmo `try/except` que devolve os pares intactos).
  `ai_tools` chama esta função e continua escrevendo `args["service_area_pairs"]`
  e logando como hoje.
- `cota`: `normaliza_pares` → `troca_por_combos` → `duracao_do_carrinho` →
  `preco_de_tabela` → `decide(qtd_areas=len(pares))` → `aplica_desconto`. A
  ordem é a do agente: combos antes de preço, horário e agendamento.
- `valida_carrinho`: `service_ids` não vazio, todos UUIDs ativos **da clínica**
  (hoje `create_appointment` não confere se o serviço é da clínica do path);
  todo par aponta para um `service_id` do carrinho e para um `service_area`
  ativo. Erro → `CarrinhoInvalido(msg)` → 400.

### 6.3 `scheduler/src/services/duration_rules.py` (modificar)

```python
def duracao_do_carrinho(db, clinic_id, service_ids, service_area_pairs) -> int:
    if normaliza_pares(service_area_pairs):
        return calcula_duracao(db, clinic_id, service_area_pairs)
    bruto = soma das services.duration_minutes ativas de service_ids
    return duracao_da_sessao(bruto, get_duration_rules(db, clinic_id))
```

`AppointmentService.create_appointment` passo 2 troca o `if/else` atual por
esta chamada. Ela repete a query de serviços, que já é feita ali; o custo é
irrelevante e a regra fica num lugar só.

### 6.4 `scheduler/src/services/availability_engine.py` (modificar)

```python
def get_days_status(self, clinic_id, dates, duration_minutes, a_partir_de: Optional[Dict[str, int]] = None)
```

- Para cada data: `free_windows, buffer = self.janelas_livres(clinic_id, d)`.
  - `free_windows == []` precisa distinguir **CLOSED** de **FULL**. Extrair de
    `janelas_livres` um `_regras_do_dia(clinic_id, date) -> Optional[list]`
    (regras → fixas vencem → exceções; `None` = fechado/bloqueado), usado pelas
    duas. `janelas_livres` mantém a assinatura e o comportamento.
  - Gera a grade com `_generate_slots_in_windows`; se `a_partir_de` tem a data,
    descarta slots `< a_partir_de[data]`.
  - `AVAILABLE` se sobrou slot; `FULL` se havia regra; `CLOSED` se não havia.
- Nenhuma query própria: o teste
  `test_days_status_reaproveita_janelas.py` garante isso com um `db` fake que
  conta chamadas e compara com `get_available_slots_multi` dia a dia.
- O `buffer_minutes` passa a vir de `_get_buffer_minutes` (memoizado), e o
  fallback `10` da cópia atual some: vale o default de `_get_buffer_minutes`. Conferir na
  implementação se os dois defaults coincidem. Se não coincidirem, registrar no TASKS_LOG.

### 6.5 `scheduler/src/services/mes_vigente.py` (criar)

```python
def agora_na_clinica(timezone: Optional[str]) -> datetime   # pytz; inválido/None → America/Sao_Paulo
def janela(agora: datetime) -> Tuple[date, date]            # (hoje, último dia do mês)
def dentro(d: date, agora: datetime) -> bool
def proximo_mes_abre_em(agora: datetime) -> date            # dia 1 do mês seguinte
```

Docstring registra a decisão da reunião ("bloquear meses futuros até a
virada") e o risco de fim de mês (PRD §5). Vale **só para o site**: bot e
painel não importam este módulo.

### 6.6 `scheduler/src/functions/public_booking/quote.py` (criar)

`POST /public/clinics/{clinicId}/quote`. É POST porque o carrinho pode ter
dezenas de pares e o telefone não deve ir na URL nem em log de acesso.

```json
// request
{ "serviceIds": ["uuid"], "serviceAreaPairs": [{"serviceId": "uuid", "areaId": "uuid"}], "phone": "5511999999999" }
// 200
{
  "status": "SUCCESS",
  "quote": {
    "originalPriceCents": 20000,
    "discountPct": 15,
    "discountReason": "first_session",
    "finalPriceCents": 17000,
    "areaCount": 3,
    "combos": [{ "from": ["Virilha Completa", "Perianal/ânus"], "to": "Virilha Completa + ânus", "savingsCents": 7500 }]
  }
}
```

- `require_booking_intake_api_key`; clínica ativa (404); `valida_carrinho` (400).
- `phone` opcional; quando vier, normalizar como `create_appointment` faz
  (mesma função usada lá; conferir `src/utils/phone`).
- **Não** devolve duração (decisão do PRD: duração não é exibida) nem
  `is_first`. Também não diz *por que* um personalizado existe: só
  `discountReason: "personalizado"` (PRD §5, exposição).
- `discountPct` serializado como número (`Decimal` → `float`), igual a
  `_serialize_row` faria com `NUMERIC`.
- Log: `[PublicBooking][quote] {clinic_id}: pares={n} combos={k} original=… final=… razao=…`
  (sem telefone em claro: últimos 4 dígitos).

### 6.7 `scheduler/src/functions/public_booking/availability.py` (modificar)

`GET /availability?dates=…&serviceIds=a,b&serviceAreaPairs=svc:area,svc:area`

- Novo caminho (quando vier `serviceIds`): `valida_carrinho` → duração por
  `carrinho.troca_por_combos` + `duracao_do_carrinho`. É o mesmo cálculo da criação, e
  fecha a divergência D2.
- **Compatibilidade:** sem `serviceIds` e com `totalDuration`, comportamento
  antigo, com `logger.warning("[PublicBooking][availability] totalDuration legado")`.
  Remover num PR futuro, quando o log zerar (anotar no TASKS_LOG).
- `agora = mes_vigente.agora_na_clinica(clinic.timezone)`. Datas fora da
  janela → `{"status": "CLOSED", "slots": []}` sem consultar a agenda. Datas
  passadas também, o que hoje não acontece. Hoje: `a_partir_de = {hoje: minutos_agora}`.
- Resposta ganha `"window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "nextOpensOn": "YYYY-MM-DD"}`
  para o front montar o estado vazio sem duplicar a regra.
- `MAX_DATES_PER_CALL = 31` continua; o mês inteiro cabe numa chamada.

### 6.8 `scheduler/src/functions/public_booking/create_appointment.py` (modificar)

Ordem nova do handler:

1. Auth, clinicId, body, campos obrigatórios (como hoje). `professionalId`
   continua **aceito** (front antigo em cache) e repassado. Ausente, o
   `AppointmentService` escolhe, como já faz.
2. Clínica: o `SELECT` passa a trazer `timezone`.
3. `valida_carrinho` → 400.
4. `mes_vigente.dentro(date)` e, se hoje, `time >= agora` → senão 400
   `"Esta data não está disponível para agendamento online."`.
5. `cot = carrinho.cota(db, clinic_id, service_ids, pairs, phone)`.
6. `create_appointment(..., service_area_pairs=cot.pares or None,
   discount_pct=cot.desconto.pct, discount_reason=cot.desconto.razao)`.
   Os **pares pós-combo** vão para a criação: duração, preço e o que fica gravado são os mesmos
   que o agente gravaria. Preço não é passado: o serviço calcula pelo
   `preco_de_tabela` (o mesmo da cotação) e aplica o pct.
7. Confirmação (`_send_confirmation_whatsapp`):
   - `price` = `texto_do_preco(result.original_price_cents, result.final_price_cents,
     result.discount_pct, result.discount_reason, cot.qtd_areas)`. Lê do **gravado**, não da cotação.
   - Envia `BOOKED`; em seguida, mensagem separada com
     `orientacoes_pos_sessao.texto(template_service, clinic_id)`, como o agente
     faz (`conversation_agent.py`, `TOOLS_QUE_MARCAM_SESSAO`). Mensagem
     separada e não concatenada, pelo motivo documentado no agente: a
     orientação vai crua.
   - Cada envio com seu próprio `try`; falha em um não impede o outro nem o 201.
8. 201 com o `appointment` serializado, como hoje.

Log antes do `create_appointment`: `[PublicBooking][create] {clinic_id} {date} {time} dur={cot.duracao_minutos}`.
No 409 também: `logger.warning` com data, hora e duração. Hoje o 409 não deixa rastro
nenhum, e é exatamente o que falta para investigar o "agendamento que não chegou".

### 6.9 `bootstrap.py`, `router.py`, `interface.yml` (modificar)

- bootstrap: `phone` no `SELECT` de clínica.
- router: import `quote`; `("POST", "public/clinics/{clinicId}/quote"): quote.handler`;
  docstring "7 rotas" → contagem atual.
- interface.yml: `- http: { path: public/clinics/{clinicId}/quote, method: post, cors: true }`.
  `test_limite_de_recursos.py` precisa continuar verde (um Method + um Resource a mais).

### 6.10 Front: types, service, hooks

```ts
// types
export interface CartPayload { serviceIds: string[]; serviceAreaPairs: { serviceId: string; areaId: string }[] }
export type DiscountReason = 'first_session' | 'tier_2' | 'tier_3' | 'personalizado'
export interface Quote {
  originalPriceCents: number | null
  discountPct: number
  discountReason: DiscountReason | null
  finalPriceCents: number | null
  areaCount: number
  combos: { from: string[]; to: string; savingsCents: number }[]
}
export interface AvailabilityWindow { start: string; end: string; nextOpensOn: string }
export interface AvailabilityResponse { days: Record<string, DayAvailability>; window: AvailabilityWindow }
```

- `booking.service.ts`: `availability(clinicId, dates, cart)` serializa
  `serviceIds` e `serviceAreaPairs` (`svc:area`) nos params; `quote(clinicId, cart, phone?)`.
- `useBooking.ts`:
  - `cartPayloadKey(cart)`: string estável (ids ordenados) para a queryKey.
  - `useMonthAvailability(clinicId, cart)`: datas de `monthWindow(today)`;
    `enabled` quando o carrinho não tem área pendente; `staleTime: 30s`. Agenda
    muda, e voltar à etapa deve refazer a busca.
  - `useQuote(clinicId, cart, phone?)`: `useQuery` (cotação é leitura, mesmo
    sendo POST), `placeholderData: keepPreviousData` para o valor não piscar ao
    entrar o telefone, `staleTime: 60s`.
  - Remove `useWeekAvailability` e a key `weekAvailability`.
- `monthWindow(today: Date): string[]`: de hoje ao último dia do mês, local
  do navegador. O backend é a autoridade (fuso da clínica): o front só
  escolhe quais datas perguntar, e a lista exibida vem de `window` + `days`.

### 6.11 Front: `DayList.tsx` (criar; substitui `WeekPicker`)

- Props: `days`, `window`, `isLoading`, `isError`, `onRetry`, `selectedDate`,
  `onSelectDate`, `clinicPhone`.
- Renderiza **só** os dias `AVAILABLE`, em ordem, como grid de botões
  (`grid-cols-4` no mobile, `sm:grid-cols-7`), cada um com dia da semana curto,
  número e mês curto (`QUA · 22 · out`). Alvo de toque ≥ 44px.
  `aria-pressed` no selecionado. Título com o mês (`Outubro 2026`).
- Quatro estados:
  - loading: skeleton de 8 células;
  - erro: `ErrorState` com retry;
  - vazio: "Não há mais horários disponíveis em {mês}." + "A agenda de
    {próximo mês} abre em {dd/mm}." + link `https://wa.me/{phone}` "Falar com a
    clínica" quando há `clinicPhone`;
  - sucesso: o grid.
- Ao trocar a seleção, rola suavemente até a grade de horários
  (`scrollIntoView({ block: 'nearest' })`, respeitando `prefers-reduced-motion`).

### 6.12 Front: `PriceBreakdown.tsx` + `discountLabel.ts` (criar)

- `discountLabel(reason, areaCount)`: `first_session` → "Primeira sessão";
  `tier_2`/`tier_3` → `Desconto para ${areaCount} áreas`;
  `personalizado` → "Desconto especial"; `null` → `null`.
- `PriceBreakdown({ quote, isLoading, isError })`:
  - Sem desconto: uma linha **Total** (`finalPriceCents`).
  - Com desconto: **Total** (`originalPriceCents`, riscado), **Desconto ·
    {label}** (`− R$ x · {pct}%`, cor de sucesso), **Valor final** (destaque,
    `font-semibold`, maior).
  - Combos: nota discreta acima do total: "Virilha Completa + Perianal/ânus
    viraram o combo Virilha Completa + ânus (economia de R$ 75,00)".
  - Preço nulo: "Valor a combinar na clínica" (o "Consultar" da mensagem).
  - Loading: skeleton da linha; erro: "Não foi possível calcular o valor",
    sem bloquear o fluxo, porque o backend calcula de novo na criação.
  - Valores com `tabular-nums`.

### 6.13 Front: `Booking.tsx` e componentes do fluxo

- `WizardStep = 'cart' | 'areas' | 'schedule' | 'customer' | 'success'`.
  `goToScheduleOrProfessional` → `goToSchedule`; `goBack` sem o ramo de
  profissional. O aviso de "nenhum profissional" **fica**.
- Estado `weekStart` some; `useMonthAvailability(clinicId, cart)`.
- `CartSummary`: sem duração em item e total; per-item mostra áreas e preço
  de tabela (`formatCurrencyBRL`, sem "a partir de" quando as áreas já foram
  escolhidas, porque aí o valor é exato); total via `<PriceBreakdown>` com
  `useQuote(clinicId, cart, quotePhone)`. Sem profissional no resumo.
- Etapa `customer`: o formulário chama `onPhoneValid(phone)` quando o telefone
  fica válido (via `watch` do RHF + `isValidBrPhone`). `Booking` guarda
  `quotePhone` e a cotação é refeita com ele. Primeira sessão/personalizado
  aparecem **antes** do clique. Botão: "Confirmar agendamento".
- Sucesso: ícone `IconCheck` no lugar do `✓` de texto; data e hora; **valor
  final** (do `appointment` retornado, `final_price_cents`); "Enviamos a
  confirmação e as orientações por WhatsApp para {telefone formatado}". Hoje o
  número aparece cru (`55119…`); usar `formatPhoneInput` sem o `55`.
- `ServiceCard`: só nome + "a partir de R$ x" com `IconMoney`; remove `IconClock`
  do arquivo de ícones se ficar sem uso (lint).
- `AreaPicker`: só `formatCurrencyBRL(area.price_cents)` à direita.
- `CustomerInfoForm`: prop `onPhoneValid?: (phone: string) => void`; texto do
  submit recebido por prop (`submitLabel`).

### 6.14 Revisão visual (PRD §3 item 8)

Na implementação, abrir o preview (`vercel deploy` de dev) em 375×812 e
1280×800, em todas as etapas, e corrigir no mesmo PR: ícones que não renderizam
(investigar se é `currentColor` herdando cor transparente, ou SVG sem
`shrink-0` colapsando em flex), alinhamento de ícone com texto
(`items-center` + `shrink-0`), botões com alvo < 44px, "Voltar" com `‹` de
texto → ícone SVG. O que for encontrado entra numa tabela no TASKS_LOG
(achado → causa → correção). Regras: `frontend/CLAUDE.md` §Impeccable.

---

## 7. Testes

### Backend (`unittest`, padrão de `tests/unit/`)

- **Caracterização do desconto** (antes da extração, via `ToolExecutor`, e depois
  via `decide`), com tabela de casos: sem regra; primeira sessão; tier 2;
  tier 3; primeira sessão vs tier com pct maior vencendo; personalizado 10%;
  personalizado **0%** vencendo primeira sessão; sem telefone (só tier).
- **Paridade site × agente:** para carrinhos com e sem combo, `carrinho.cota`
  produz o mesmo `final_cents`, `pct`, `razao` e duração que
  `_calcula_desconto` + `calcula_duracao` do agente, depois do combo.
- **Duração:** availability e create usam a mesma `duracao_do_carrinho`;
  cenário com piso, teto e passo em que a soma crua do front divergiria (ex.: soma
  17, passo 5 → 15; piso 20 → 20).
- **`get_days_status`:** CLOSED / FULL / AVAILABLE iguais à versão anterior
  para os mesmos dados; zero queries próprias; `a_partir_de` corta slots.
- **`mes_vigente`:** dia 31 → janela de um dia; 23:30 de 31/10 em São Paulo =
  ainda outubro mesmo com UTC já em novembro; timezone inválido → SP.
- **Handlers:** `quote` 200/400/404; `availability` com carrinho novo e com
  `totalDuration` legado; `create` 400 fora do mês, 400 horário passado,
  400 serviço de outra clínica, 201 gravando desconto; confirmação: dois
  envios, falha no primeiro não impede o segundo nem o 201.
- `test_limite_de_recursos.py` verde.

### Front (Vitest + Testing Library)

- `discountLabel`, `monthWindow` (fim de mês, ano bissexto).
- `DayList`: 4 estados; não renderiza dia FULL/CLOSED; link de contato só com telefone.
- `PriceBreakdown`: sem desconto, com desconto, combo, preço nulo, loading, erro.
- `Booking.test.tsx`: serviço único com dois profissionais **não** mostra
  seleção de profissional; payload de criação sem `professionalId`; resumo
  mostra desconto após digitar telefone (mock de `quote` muda com phone);
  nenhum texto `min` de duração na tela (`queryByText(/\d+min/)` nulo).

---

## 8. Testes manuais (dev, curl)

```bash
source .env
BASE="$SCHEDULER_API_URL_DEV"; C="<clinic-id-dev>"
# cotação sem e com telefone
curl -s -X POST "$BASE/public/clinics/$C/quote" -H "x-api-key: $BOOKING_API_KEY" -H 'content-type: application/json' \
  -d '{"serviceIds":["<svc>"],"serviceAreaPairs":[{"serviceId":"<svc>","areaId":"<a1>"},{"serviceId":"<svc>","areaId":"<a2>"}]}'
# disponibilidade do mês com carrinho
curl -s "$BASE/public/clinics/$C/availability?dates=2026-10-20,2026-10-21&serviceIds=<svc>&serviceAreaPairs=<svc>:<a1>" -H "x-api-key: $BOOKING_API_KEY"
# criação fora do mês → 400
```

Casos completos em `tests/integration/023-...md`. Os nomes das variáveis de
`.env` devem ser conferidos no arquivo, sem nunca copiar valores.

---

## 9. Convenções a respeitar

- Logging com prefixo de módulo (`[PublicBooking][quote]`), padrão do scheduler; telefone mascarado.
- Rotas públicas novas só via `router.py` + `interface.yml` da `PublicBooking` (PRD 013).
- Docstrings em português explicando o **porquê**, como nos módulos vizinhos.
- Front: named exports, zero `any`, TanStack Query para todo server state, 4 estados, Impeccable.
- Sem migration: nenhuma coluna nova.
- Deploy: backend dev → front preview → validação → prod backend → prod front.
