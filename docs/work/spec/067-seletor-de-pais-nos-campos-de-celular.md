# Spec - 067 Seletor de país (DDI) em todos os campos de celular

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/067-seletor-de-pais-nos-campos-de-celular.md`

---

## 1. Resumo

Só front, nos três apps. Cada app ganha (ou já tem, no checkin) um `ddi.ts`
com a mesma lista fixa e as mesmas funções, mais `paisDoNumero` para abrir um
número já gravado no país certo. Um componente de celular com país substitui
os campos de texto do inventário. O contrato com o backend não muda: `55` +
número para o Brasil, `+DDI` + número fora.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `booking-site/src/utils/ddi.ts` | lista, `numeroValido`, `formataNumero`, `limiteDeDigitos`, `paisDoNumero`, `valorDoSite` |
| `booking-site/src/utils/ddi.test.ts` | vetores comuns + `valorDoSite` |
| `booking-site/src/components/CelularComPais.tsx` | seletor + número; emite a string do site |
| `checkin/src/components/PaisDoCelular.tsx` | `select` "País" + "Código do país" (extraído do `PhoneStep`) |
| `frontend/src/utils/ddi.ts` | lista, validação, `paisDoNumero`, `telefoneDaApi` |
| `frontend/src/utils/ddi.test.ts` | vetores comuns + `paisDoNumero` |
| `frontend/src/components/CelularComPais.tsx` | seletor + número para formulários do painel |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `booking-site/src/utils/format.ts` | `isValidPhone` internacional: 7 a 17 dígitos |
| `booking-site/src/components/PhoneStep.tsx` | usa `CelularComPais` |
| `booking-site/src/components/CustomerInfoForm.tsx` | idem; `setValue('phone', valor)` |
| `booking-site/src/components/MyAppointmentsModal.tsx` | idem |
| testes do site que digitam celular | escolhem o país quando estrangeiro; sem a dica do `+` |
| `checkin/src/utils/ddi.ts` | `paisDoNumero` |
| `checkin/src/steps/PhoneStep.tsx` | keypad com `PaisDoCelular`; nativo usa o componente extraído |
| `checkin/src/steps/ConsentDataStep.tsx` | responsável com país (`numeroValido`, `montaTelefone`, prefill por `paisDoNumero`) |
| testes do checkin | iPad com estrangeiro; responsável estrangeiro |
| `frontend/src/utils/normalizePhone.ts` | número com `+` devolve só os dígitos, sem `55` |
| `frontend/src/pages/pacientes/components/CreatePatientModal.tsx` | `CelularComPais` + `setValue('phone')` |
| `frontend/src/pages/pacientes/components/EditPatientModal.tsx` | idem; envia telefone só se mudou |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | paciente nova com `CelularComPais` |
| testes do painel | modais com o seletor; `normalizePhone` com `+` |

---

## 4. Arquivos a remover

Nenhum. `isInternationalPhone`/`formatPhoneInput` do site continuam (o
resto do site lê a string com `+`).

---

## 5. Ordem de implementação

1. `ddi.ts` + testes nos três apps (vetores iguais).
2. checkin: `PaisDoCelular`, `PhoneStep`, `ConsentDataStep`, testes.
3. booking-site: componente, três telas, `isValidPhone`, testes.
4. frontend: `normalizePhone`, componente, três formulários, testes.
5. Testes, lint e build nos três; PR; previews (site e painel) e
   `checkin-dev`; conferência na largura do celular e do iPad.

---

## 6. Detalhes

### `ddi.ts` (mesma API nos três; checkin já tem a base)

```ts
export const BRASIL = '55'
export const OUTRO = 'outro'
export const PAISES: Pais[]           // 16 países, Brasil primeiro, sem bandeira
export function ddiValido(ddi): boolean          // 1 a 3 dígitos
export function numeroValido(ddi, digits): boolean
export function formataNumero(ddi, digits): string
export function limiteDeDigitos(ddi): number     // 11 Brasil, 14 fora
export function paisDoNumero(gravado): { pais: string; ddiLivre: string; digits: string }
```

- `numeroValido` Brasil: checkin = celular com nono dígito (como hoje);
  site e painel = 10 ou 11 dígitos (regra que já usavam). Fora: 6 a 14.
- `paisDoNumero`: só dígitos; com `+` na frente ou não. `55` + 10/11 →
  Brasil; 10/11 sem DDI → Brasil; senão o prefixo mais longo da lista (fora
  o 55) com resto de 6 a 14 → esse país; sem casamento → `OUTRO`, `ddiLivre`
  vazio, número inteiro.
- Comentário no topo de cada cópia citando as outras duas.

Específicos:
- site `valorDoSite(ddi, digits)`: Brasil → `formatPhoneInput(digits)`;
  fora e válido → `+${ddi}${digits}`; fora e inválido → `''`.
- painel `telefoneDaApi(ddi, digits)`: Brasil → `55${digits}`; fora e
  válido → `+${ddi}${digits}`; inválido → `''`.

### Componentes

- **site `CelularComPais`** `{ id, defaultValue?, onChange(valor), error?, disabled? }`:
  estado interno `pais/ddiLivre/digits` iniciado por `paisDoNumero`;
  `select#<id>-pais` "País", `Input` "Código do país" quando Outro,
  `Input#<id>` "Celular (WhatsApp)" com `formataNumero`, placeholder por país
  e dica "Número de fora do Brasil? Escolha o país acima." /
  "Sem o código do país: ele já está escolhido acima.". A cada mudança chama
  `onChange(valorDoSite(...))`. Estilo do `Input` do site (h-12, rounded-xl).
- **checkin `PaisDoCelular`** `{ pais, ddiLivre, onPais, onDdiLivre, disabled }`:
  o `select` e o `TextField` que hoje estão no `PhoneStep`, sem mudança visual.
- **painel `CelularComPais`** `{ label, defaultValue?, onChange(apiPhone), error? }`:
  `select` compacto (w-40) ao lado do número numa linha, "Código" quando
  Outro; estilo do `Input` do painel.

### checkin

- `PhoneStep` keypad: `PaisDoCelular` acima do visor; visor com
  `formataNumero(ddi, digits)` e placeholder por país; `Keypad maxLength={limiteDeDigitos(ddi)}`;
  válido por `numeroValido`; envia `montaTelefone`. Trocar o país corta os
  dígitos ao novo limite.
- `ConsentDataStep`: estado `guardianPais`, `guardianDdiLivre`; prefill por
  `paisDoNumero(g.phone)`; erro "Informe o celular com DDD." no Brasil e
  "Informe o número sem o código do país." fora; payload `montaTelefone`.

### booking-site

- `PhoneStep`: `CelularComPais id="phone" defaultValue={defaultValue}`;
  `valido = isValidPhone(valor)`.
- `CustomerInfoForm`: troca o `Input` do celular; `onChange` faz
  `setValue('phone', v, { shouldValidate: true })` e `onPhoneChange`.
- `MyAppointmentsModal`: `phone` vira o valor emitido; resto igual.
- `isValidPhone` internacional: `digits.length >= 7 && <= 17`.

### frontend

- `normalizePhone`: `if (phone.trim().startsWith('+')) return digits` antes
  das regras brasileiras; comentário citando o caso `551202...`.
- `CreatePatientModal`: `CelularComPais label="WhatsApp" onChange={(v) => setValue('phone', v, { shouldValidate: true })}`;
  schema `phone: z.string().min(1, 'Telefone inválido')`; `reset()` remonta o
  componente por `key`.
- `EditPatientModal`: `defaultValue={patient.phone}`; envia
  `phone` só se `normalizePhone(data.phone) !== normalizePhone(patient.phone)`.
- `CreateAppointmentModal`: `CelularComPais` no lugar do `Input` "Telefone";
  `setNewPhone(v)`; o resto (`newPhone.trim()`) segue.

---

## 7. Verificação

- Vitest, lint e `npm run build` nos três apps.
- `checkin-dev` via CLI: bundle com "EUA / Canadá" no keypad; headless na
  largura do iPad deitado (1180x820) com o keypad inteiro visível.
- Previews do site e do painel (SSO): build verde no PR; conferência visual
  logada pelo André.
- Nenhum código enviado para número inventado em dev.
