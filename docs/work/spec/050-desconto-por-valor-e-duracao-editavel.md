# Spec - 050 Desconto por valor ou percentual (com centavos) e duração editável no pop-up da agenda

> Gerada em 19/11/2026 a partir de `prd/050-desconto-por-valor-e-duracao-editavel.md`. Decisões da §4 do PRD confirmadas pelo André em 19/11.

---

## 1. O que muda, em duas frases

O desconto personalizado de um agendamento passa a ter duas formas, percentual com duas casas (`discount_pct`) ou valor em centavos (coluna nova `discount_cents`), e uma função só no backend (`desconto_personalizado.aplica`) e uma só no front (`lib/desconto.ts`) fazem a conta nos dois. O campo de duração fixada guarda o texto digitado e só exige número ao salvar.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/scripts/setup_database.py` | migration `discount_cents INTEGER` + CHECK; `CREATE TABLE` em sincronia |
| `scheduler/src/services/desconto_personalizado.py` | `aplica(total, pct, cents=None)`; **novas** `normaliza_centavos`, `pct_equivalente`, `DescontoInvalido` |
| `scheduler/src/services/appointment_service.py` | `create_appointment(discount_cents=None)`; `update_appointment_services` reaplica por `discount_cents`; INSERT/UPDATE gravam a coluna |
| `scheduler/src/functions/appointment/update.py` | aceita `discountPct` decimal **ou** `discountCents`; valida; grava pela fonte certa |
| `scheduler/src/functions/appointment/create.py` | repassa `discountCents` |
| `scheduler/src/functions/appointment/list.py` | `a.discount_cents` no SELECT |
| `scheduler/src/functions/clinic/dashboard.py` | `a.discount_cents` em `today`; filtros `discount_pct > 0` viram `(discount_pct > 0 OR discount_cents > 0)` |
| `scheduler/src/functions/clinic/reports.py` | mesmos filtros |
| `scheduler/tests/unit/test_desconto_por_valor.py` | **novo** |
| `scheduler/tests/unit/test_desconto_contrato.py` | casos de centavos na tabela do contrato |
| `frontend/src/lib/desconto.ts` (+ `desconto.test.ts`) | **novo módulo**: parse, conta, texto, payload, validação. `precoComDesconto` muda para cá; `cadastroPaciente.ts` reexporta |
| `frontend/src/pages/agenda/components/DescontoField.tsx` (+test) | **novo**: botões none/parceria/personalizado + seletor % / R$ + campo |
| `frontend/src/pages/agenda/components/DuracaoField.tsx` (+test) | `manual: string \| null`; vazio não derruba o modo fixado |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` (+test) | usa os dois campos; validação no submit; `discountChanged` por payload |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | idem |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | linha do desconto por `textoCurtoDoDesconto(a)` |
| `frontend/src/pages/dashboard/components/TodayAppointments.tsx` | idem |
| `frontend/src/lib/alteracaoDeAgendamento.ts` (+test) | `textoDoDesconto` recebe `DescontoEscolhido` |
| `frontend/src/types/index.ts` | `discount_cents`, `discountCents?` |
| `frontend/src/services/reports.service.ts` | `DashboardAppointment.discount_cents` |
| `scheduler/tests/integration/050-desconto-por-valor.md` | **novo** roteiro curl em dev |

---

## 3. Banco

`setup_database.py`, lista `MIGRATIONS` (idempotente) e `CREATE TABLE scheduler.appointments`:

```sql
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS discount_cents INTEGER;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'appointments_discount_cents_positivo') THEN
    ALTER TABLE scheduler.appointments ADD CONSTRAINT appointments_discount_cents_positivo
      CHECK (discount_cents IS NULL OR discount_cents > 0);
  END IF;
END $$;
```

Semântica: `NULL` = o desconto é o percentual de `discount_pct` (tudo que existe hoje). Preenchido = o desconto é este valor; `discount_pct` guarda o equivalente arredondado, só para leitura. Zero não existe: "sem desconto" é `discount_cents NULL` e `discount_pct 0`.

Rodar em dev (`/dev/SUPABASE_DB_*`) antes do deploy dev; em prod só com o André.

---

## 4. `desconto_personalizado.py`

```python
class DescontoInvalido(ValueError):
    """Desconto que não cabe no preço ou chegou ilegível. Vira 400 no handler."""

def aplica(total_cents, pct, cents=None) -> int:
    # cents vence: subtração exata, sem arredondamento. Negativo é erro, não zero.
    if cents is not None:
        if cents > total_cents: raise DescontoInvalido(f"desconto de R$ {cents/100:.2f} maior que o valor de R$ {total_cents/100:.2f}")
        return int(total_cents) - int(cents)
    ...  # caminho atual por percentual, intocado (TRUNCA)

def normaliza_centavos(valor) -> tuple[bool, Optional[int]]:
    # None/"" -> (True, None). Aceita int ou string de dígitos. Exige inteiro >= 1.
    # Não aceita "20,00": o front já manda centavos inteiros; reais com vírgula é assunto da tela.

def pct_equivalente(total_cents, cents) -> Decimal:
    # Decimal(cents) * 100 / total, quantize(PASSO, ROUND_HALF_UP). total 0 -> Decimal(0).
```

`normaliza_entrada` (percentual) fica como está e passa a ser usada pelo handler de edição, que hoje faz `int()`.

---

## 5. `appointment_service.py`

### 5.1 `create_appointment`
- Assinatura: `discount_pct=0, discount_reason=None, discount_cents: Optional[int] = None`.
- Depois do bloco 2a-bis (desconto da paciente) e do cálculo de `original_price_cents`:
  ```python
  if discount_cents is not None:
      if original_price_cents is None: raise DescontoInvalido("desconto em reais exige preço de tabela")
      final_price_cents = aplica(original_price_cents, None, cents=discount_cents)
      discount_pct = pct_equivalente(original_price_cents, discount_cents)
      discount_reason = discount_reason or RAZAO
  ```
  O bloco 2a-bis não roda quando `discount_cents` veio: o chamador opinou.
- INSERT: coluna `discount_cents` e parâmetro.

### 5.2 `update_appointment_services`
- Linha 613: ler também `discount_cents = appointment.get("discount_cents")`.
- Linha 644:
  ```python
  if original_price_cents:
      final_price_cents = aplica(original_price_cents, discount_pct, cents=discount_cents)
      if discount_cents is not None:
          discount_pct = pct_equivalente(original_price_cents, discount_cents)
  ```
  `DescontoInvalido` sobe quando o novo subtotal é menor que o valor fixado: a troca de área é recusada com a mensagem, e a recepção ajusta o desconto primeiro. Zerar em silêncio seria uma parceria que ninguém pediu (decisão 4).
- UPDATE: acrescentar `discount_pct = %s` (o derivado reescrito). `discount_cents` não muda aqui.

### 5.3 `set_manual_duration` e `reschedule_appointment`
Não mexem em preço. Nada a fazer.

---

## 6. `functions/appointment/update.py`

Leitura (junto das outras linhas 101-102):
```python
veio_pct = "discountPct" in body
veio_cents = "discountCents" in body
if veio_pct and veio_cents:
    return http_response(400, {"status": "ERROR", "message": "Mande discountPct ou discountCents, não os dois"})
```

Etapa 4 substitui o bloco `if new_discount_pct is not None:` por:
```python
if veio_pct or veio_cents:
    existing = db.execute_query("SELECT original_price_cents FROM scheduler.appointments WHERE id = %s::uuid", (appointment_id,))
    orig = existing[0].get("original_price_cents") if existing else None
    if veio_cents:
        ok, cents = normaliza_centavos(body.get("discountCents"))
        if not ok or cents is None: return 400 "discountCents deve ser um inteiro de centavos maior que zero"
        if orig is None: return 400 "desconto em reais exige preço de tabela"
        try: final = aplica(orig, None, cents=cents)
        except DescontoInvalido as e: return 400 str(e)
        pct = pct_equivalente(orig, cents)
    else:
        ok, pct = normaliza_entrada(body.get("discountPct"))   # Decimal 2 casas, 0..100
        if not ok: return 400 "discountPct deve ser de 0 a 100, com até duas casas decimais"
        pct = pct or Decimal(0); cents = None
        final = aplica(orig, pct) if orig is not None else None
    updates += ["discount_pct = %s", "discount_cents = %s", "discount_reason = %s"]
    params += [pct, cents, new_discount_reason]
    if final is not None: updates.append("final_price_cents = %s"); params.append(final)
    messages.append("desconto")
```
A etapa 1 (áreas) continua antes e já reaplica o desconto ANTIGO sobre o subtotal novo; a etapa 4 lê o `original_price_cents` já atualizado e grava o desconto NOVO por cima. Mesma ordem de hoje. Exceções `DescontoInvalido` vindas da etapa 1 viram 400 no `except` existente (conferir qual exceção o handler já mapeia para 400; se for `ValidationError`, fazer `DescontoInvalido` herdar dela).

`functions/appointment/create.py`: `discount_cents=body.get("discountCents")` passando por `normaliza_centavos` (400 se inválido), e `DescontoInvalido` → 400.

---

## 7. Leitores

- `list.py`: `a.discount_cents,` ao lado de `a.discount_pct`.
- `dashboard.py` `today`: `a.discount_cents` no SELECT e `"discount_cents": row.get("discount_cents")` no dict.
- `dashboard.py` e `reports.py`: todo `FILTER (WHERE ... AND discount_pct > 0)` e `AND discount_pct > 0` em `GROUP BY discount_reason` passam a `(discount_pct > 0 OR discount_cents > 0)`. São 4 pontos (dashboard 85, 206; reports 97, 124, 196: conferir com grep, pode ser 5).
- `checkin.py`: `discountPct` segue vindo do derivado. Não muda.

---

## 8. Frontend

### 8.1 `lib/desconto.ts` (novo)

```ts
export type TipoDeDesconto = 'pct' | 'cents'
export interface DescontoEscolhido {
  modo: 'none' | 'partnership' | 'custom'
  tipo: TipoDeDesconto          // só importa em 'custom'
  texto: string                 // o que está no campo: "12,5", "20", "37,90"
}
export const SEM_DESCONTO: DescontoEscolhido = { modo: 'none', tipo: 'pct', texto: '' }

/** "12,5" | "12.5" | "20" -> 12.5; mais de 2 casas, vazio ou lixo -> null. */
export function parseDecimal(texto: string): number | null
/** Reais digitados -> centavos inteiros ("37,9" -> 3790). */
export function reaisParaCentavos(texto: string): number | null
export function precoComDesconto(totalCents: number, pct: number): number      // vem de cadastroPaciente (TRUNCA)
export function precoComDescontoEmCentavos(totalCents: number, cents: number): number  // total - cents, nunca negativo aqui: a validação recusa antes
/** O que o modal mostra na linha "Desconto (...)" e o total. */
export function resumoDoDesconto(d: DescontoEscolhido, subtotalCents: number): { rotulo: string; descontoCents: number; totalCents: number } | null
/** Mensagem de erro para o submit, ou null. Precisa do subtotal para o teto em reais. */
export function validaDesconto(d: DescontoEscolhido, subtotalCents: number | undefined): string | null
/** O pedaço do payload. none -> {discountPct: 0, discountReason: null} na edição; undefined na criação. */
export function payloadDoDesconto(d: DescontoEscolhido): { discountPct?: number; discountCents?: number; discountReason: string | null }
/** Do agendamento gravado para o estado do campo. */
export function descontoDoAgendamento(a: Pick<Appointment, 'discount_pct' | 'discount_reason' | 'discount_cents'>): DescontoEscolhido
/** "-12,5%" | "-R$ 20,00" para popover e Hoje. */
export function textoCurtoDoDesconto(a: Pick<Appointment, 'discount_pct' | 'discount_cents'>): string
/** "12,5%" | "R$ 20,00" | "parceria (100%)" | "sem desconto" para o resumo do PRD 043. */
export function textoDoDesconto(d: DescontoEscolhido): string
```

Regras: `validaDesconto` recusa `custom` com texto vazio, parse nulo, pct fora de 0,01..100, cents < 1, cents > subtotal ("O desconto não pode passar do valor da sessão"). `textoCurtoDoDesconto` formata o percentual com `toLocaleString('pt-BR', {maximumFractionDigits: 2})` para `12.5` sair `12,5` e `10` sair `10`.

`cadastroPaciente.ts`: `export { precoComDesconto } from './desconto'` para o teste de contrato não mudar de import.

`alteracaoDeAgendamento.ts`: `textoDoDesconto` sai daqui e passa a ser importada de `lib/desconto`. Teste acompanha.

### 8.2 `DescontoField.tsx` (novo)

Props: `{ valor: DescontoEscolhido; onChange: (d: DescontoEscolhido) => void; subtotalCents?: number; disabled?: boolean }`.

- Os três botões atuais (mesmas classes dos modais de hoje).
- Em `custom`: linha com dois botões de alternância **%** / **R$** (`aria-pressed`) e um `<input type="text" inputMode="decimal">` com `placeholder` "Ex: 12,5" ou "Ex: 20,00", largura `w-28`, sufixo "de desconto". Trocar o tipo limpa o texto.
- Abaixo, `validaDesconto(valor, subtotalCents)` em `text-xs text-red-500` quando há texto e ele é inválido; não aparece com campo vazio (a obrigação é do submit).

### 8.3 `DuracaoField.tsx`

- `manual: string | null` e `onChange(valor: string | null)`. `null` = seguindo o cálculo; string = fixada, inclusive `''`.
- "Ajustar" → `onChange(String(calculada))`. "Voltar ao cálculo" → `onChange(null)`.
- Input `type="number"`, `value={manual}`, `onChange={(e) => onChange(e.target.value)}`. Nunca converte vazio em `null`.
- Aviso: `const n = parseDuracao(manual)`; vazio → "Informe a duração ou volte ao cálculo." em cinza; número fora de 5..480 → o aviso vermelho atual.
- Exportar `parseDuracao(texto: string | null): number | null` (inteiro em 5..480 ou null) e manter `DURACAO_MANUAL`.
- Teste novo: "apagar o campo mantém o input e pede a duração"; os existentes mudam `manual={75}` para `manual="75"` e `toHaveBeenCalledWith(30)` para `'30'`.

### 8.4 `EditAppointmentModal.tsx`

- Estado: `const [duracaoFixada, setDuracaoFixada] = useState<string | null>(a.manual_duration_minutes === null ? null : String(a.manual_duration_minutes))`; `const manualDuration = parseDuracao(duracaoFixada)` (número ou null) alimenta `duracaoEfetiva`, `precisaMandarDuracao`, `manualChanged`, `alteracao.duracao` e o payload.
  - Atenção: `duracaoEfetiva = duracaoFixada === null ? totalDuration : (manualDuration ?? totalDuration)`. Com texto inválido, os horários são buscados pela calculada; nunca `NaN`.
  - Descarte por troca de áreas: `if (duracaoFixada !== null) { setDuracaoFixada(null); setDuracaoDescartada(true) }`.
- Estado: `const [desconto, setDesconto] = useState<DescontoEscolhido>(() => descontoDoAgendamento(a))`.
  - `discountChanged = JSON.stringify(payloadDoDesconto(desconto)) !== JSON.stringify(payloadDoDesconto(descontoDoAgendamento(a)))`.
  - Resumo de preço usa `resumoDoDesconto(desconto, subtotal)`.
  - `alteracao.desconto = { de: textoDoDesconto(descontoDoAgendamento(a)), para: textoDoDesconto(desconto) }`.
- `handleSubmit`, antes do `hasChanges`:
  ```ts
  if (duracaoFixada !== null && manualDuration === null) { setError('Informe a duração fixada entre 5 e 480 minutos, ou volte ao cálculo.'); return }
  const erroDesconto = validaDesconto(desconto, subtotal); if (erroDesconto) { setError(erroDesconto); return }
  ```
  `subtotal` sai do IIFE do resumo e vira `const` acima dele (`useMemo` desnecessário).
- `executa`: `if (discountChanged) Object.assign(payload, payloadDoDesconto(desconto))`.
- Botão "Salvar alterações" continua `disabled={!hasChanges}`. Duração fixada vazia conta como mudança (`manualChanged` compara `manualDuration` ao servidor; `null` vs `30` muda), então a mensagem aparece.

### 8.5 `CreateAppointmentModal.tsx`

Mesmas trocas: `duracaoFixada: string | null`, `desconto: DescontoEscolhido`. Prefill da paciente (linha 164): `setDesconto({ modo: 'custom', tipo: 'pct', texto: String(patient.custom_discount_pct).replace('.', ',') })`, e `modo: 'partnership'` quando for 100 (hoje já vira custom com 100; manter o que `descontoDoAgendamento` faria: 100 + custom = mostrar como personalizado 100%; não mudar comportamento). Payload: `...(desconto.modo === 'none' ? {} : payloadDoDesconto(desconto))`. Validação de duração e desconto no submit como em 8.4.

### 8.6 Exibição

- `AppointmentPopover.tsx` linha 256: condição `(a.discount_pct > 0 || a.discount_cents) && a.original_price_cents != null`; texto `{textoCurtoDoDesconto(a)} ({DISCOUNT_LABELS[...]})`.
- `TodayAppointments.tsx` `PriceCell`: condição `!apt.discount_reason || (apt.discount_pct === 0 && !apt.discount_cents)`; texto `{textoCurtoDoDesconto(apt)} {label}`.
- `types/index.ts`: `Appointment.discount_cents: number | null`; `CreateAppointmentPayload.discountCents?: number`; `UpdateAppointmentPayload.discountCents?: number`. Até o prod subir, a API pode não mandar o campo: `textoCurtoDoDesconto` e `descontoDoAgendamento` tratam `undefined` como `null`.
- `reports.service.ts`: `DashboardAppointment.discount_cents: number | null`.

---

## 9. Testes

### Backend
- `test_desconto_por_valor.py`:
  - `aplica(19500, None, cents=2000) == 17500`; `aplica(19500, None, cents=19500) == 0`; `cents=19501` → `DescontoInvalido`; `cents` vence `pct`.
  - `normaliza_centavos`: `None`/`""` → `(True, None)`; `2000`, `"2000"` → `(True, 2000)`; `0`, `-1`, `"20,00"`, `1.5`, `"abc"` → `(False, None)`.
  - `pct_equivalente(19500, 2000) == Decimal("10.26")`; `(10000, 1) == Decimal("0.01")`; `(100000, 1) == Decimal("0.00")`; `(0, 1) == 0`.
  - Handler `update`: `discountCents` grava `discount_cents=2000, discount_pct=Decimal("10.26"), final=17500`; `discountPct: "12,5"` grava `Decimal("12.50")` e `discount_cents=None`; os dois juntos → 400; `discountCents` acima do preço → 400 com a mensagem; `discountPct: 12.5` não é mais truncado (o teste de regressão do `int()`).
  - `update_appointment_services` com `discount_cents=2000` e subtotal novo 30000 → `final=28000`, `discount_pct=Decimal("6.67")`; subtotal novo 1500 → `DescontoInvalido`.
  - `create_appointment(discount_cents=2000)` grava a coluna e não consulta o desconto da paciente.
  - Guarda: `grep` no fonte de `functions/`, `services/` por `int(new_discount_pct)` ou `int(body.get("discountPct"` → nenhum (a conversão é só por `normaliza_entrada`).
- `test_desconto_contrato.py`: tabela de centavos `[(19500, 2000, 17500), (1, 1, 0), (20000, 20000, 0)]` espelhada em `desconto.test.ts`.

### Frontend
- `desconto.test.ts`: contrato (existente, importa de `cadastroPaciente`, continua passando), parse (`"12,5"`, `"12.5"`, `"12,555"` → null, `""` → null), `reaisParaCentavos("37,9") === 3790`, `validaDesconto` (vazio, acima do subtotal, 100,01), `payloadDoDesconto` nos 4 caminhos, `descontoDoAgendamento` com `discount_cents` e sem, `textoCurtoDoDesconto` (`12.5` → `-12,5%`, `cents 2000` → `-R$ 20,00`).
- `DescontoField.test.tsx`: alternar R$ limpa o texto; erro aparece só com texto inválido.
- `DuracaoField.test.tsx`: apagar mantém o input e mostra "Informe a duração".
- `EditAppointmentModal.test.tsx`: desconto `R$ 20` sobre fixture de R$ 195 mostra total R$ 175,00 e manda `discountCents: 2000, discountReason: 'custom'`; `12,5` manda `discountPct: 12.5`; duração apagada + salvar → mensagem e `mutateAsync` não chamado; `R$ 250` → mensagem.

---

## 10. Ordem

1. `desconto_personalizado.py` + `test_desconto_por_valor.py` (parte da lib) + contrato.
2. `appointment_service.py` (create, update_services) + testes.
3. `update.py`, `create.py`, `list.py`, `dashboard.py`, `reports.py` + testes do handler.
4. `setup_database.py`. `pytest tests/unit`.
5. `lib/desconto.ts` + teste; `cadastroPaciente.ts` reexporta; `alteracaoDeAgendamento.ts`.
6. `DuracaoField`, `DescontoField` + testes.
7. Modais, popover, Hoje, types. `vitest`, `build`, `lint`.
8. Migration em dev; `serverless deploy --stage dev`; roteiro `050-desconto-por-valor.md`; smoke no painel apontando para dev.
9. Prod: migration e deploy só com o André na tela.

---

## 11. Roteiro curl (dev) - esqueleto

Fixture: clínica `clinicadepilacaopremium-3fbce9`, Axilas (R$ de tabela da área), dia com `availability_rule` (reaproveitar `2026-11-27` do 049).

| # | Chamada | Esperado |
|---|---|---|
| 1 | `PUT {"discountPct": 12.5, "discountReason": "custom"}` | 200; `discount_pct 12.50`, `final = trunc(orig*0.875)` |
| 2 | `PUT {"discountPct": "12,5", ...}` | 200, igual |
| 3 | `PUT {"discountCents": 2000, "discountReason": "custom"}` | 200; `discount_cents 2000`, `discount_pct` equivalente, `final = orig - 2000` |
| 4 | `PUT {"discountCents": 999999, ...}` | 400 "maior que o valor" |
| 5 | `PUT {"discountPct": 10, "discountCents": 100}` | 400 |
| 6 | `PUT {"serviceId", "serviceAreaPairs": [+1 área]}` com o desconto do caso 3 | 200; `final = novo orig - 2000`; `discount_pct` reescrito |
| 7 | `PUT {"discountPct": 0, "discountReason": null}` | 200; `discount_cents NULL`, `final = orig` |
| 8 | `POST appointments {"discountCents": 500, "discountReason": "custom"}` | 201; coluna gravada |
| 9 | `GET clinics/{c}/appointments?date=` e `GET .../dashboard` | `discount_cents` presente |
