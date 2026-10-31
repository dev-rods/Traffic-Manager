# Spec - 032 Site pede o cadastro de quem ainda não é paciente

> Gerado na fase **Spec** em 31/10/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/032-site-cadastro-do-paciente-novo.md`

---

## 1. Resumo

O site público passa a pedir CPF, data de nascimento e e-mail quando o celular
não é de um paciente com cadastro completo, e só os campos que faltam. A régua
é a do bot (`identificacao_de_paciente.CAMPOS_DO_CADASTRO`), exposta na
cotação (`/quote`, que já recebe o celular) e exigida na criação
(`/appointments`), pela mesma função. O serviço de agendamento grava os dados
no paciente novo e completa só o que está vazio no existente. CPF que já é de
outro paciente da clínica é recusado. Sem migration.

Achado na pesquisa: não existe validação de formato de e-mail no backend
(`patient/update.py` e `patient/create.py` só fazem `strip`). Esta spec cria
`utils/cadastro.email_valido` e a usa no site; o painel passa a usá-la também,
porque a regra tem que ser uma só.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/tests/unit/test_cadastro_pelo_site.py` | Quote com `cadastro`; criação exigindo, gravando e recusando CPF em uso; `campos_faltantes` |
| `booking-site/src/components/CadastroFields.tsx` | Os três campos condicionais (CPF, nascimento, e-mail), com máscaras, usados pelo `CustomerInfoForm` |
| `booking-site/src/components/CadastroFields.test.tsx` | Só os campos que faltam aparecem; validação de CPF, data e e-mail |
| `booking-site/src/utils/cadastro.ts` | `formatCpf`, `isValidCpf`, `formatDateInput`, `brDateToIso`, `isValidBirthDate`, `isValidEmail` |
| `booking-site/src/utils/cadastro.test.ts` | Tabela de casos das funções acima |
| `scheduler/tests/integration/032-site-cadastro-do-paciente-novo.md` | Número novo, completo, parcial, CPF em uso |
| `scheduler/tests/postman/032-site-cadastro-do-paciente-novo.postman_requests.json` | `quote` com celular; criação sem cadastro (400); criação completa (201) |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/services/identificacao_de_paciente.py` | `campos_faltantes(paciente) -> List[str]`; `cadastro_completo` passa a usá-la |
| `scheduler/src/utils/cadastro.py` | `email_valido(valor) -> bool` e `normaliza_email(valor) -> str | None | False` |
| `scheduler/src/services/carrinho.py` | `paciente_do_telefone(db, clinic_id, phone) -> Optional[Dict]` (SELECT por variantes, um só) e `cadastro_para_o_site(paciente) -> dict` |
| `scheduler/src/functions/public_booking/quote.py` | Resposta ganha `cadastro` quando há celular |
| `scheduler/src/functions/public_booking/create_appointment.py` | Lê e valida `cpf`, `birthDate`, `email`; `400 CADASTRO_INCOMPLETO`; `409 CPF_EM_USO`; repassa ao serviço |
| `scheduler/src/services/appointment_service.py` | `create_appointment(..., cpf=None, birth_date=None, email=None)`; `_get_or_create_patient(clinic_id, phone, full_name, cpf, birth_date, email)` |
| `scheduler/src/functions/patient/create.py`, `patient/update.py` | E-mail passa por `normaliza_email` (400 "E-mail inválido") |
| `scheduler/tests/unit/test_carrinho_do_site.py` | `Db` responde `FROM scheduler.patients` (paciente completo por padrão, para os testes atuais não mudarem) |
| `scheduler/tests/unit/test_identificacao_de_paciente.py` | Casos de `campos_faltantes` |
| `booking-site/src/types/index.ts` | `Quote.cadastro`, `CampoDoCadastro`, `CreateAppointmentPayload` com `cpf?`, `birthDate?`, `email?` |
| `booking-site/src/components/CustomerInfoForm.tsx` | Props `camposFaltantes`, `aguardandoCadastro`; schema dinâmico; renderiza `CadastroFields` |
| `booking-site/src/components/CustomerInfoForm.test.tsx` | Casos novos; o caso atual continua (sem `camposFaltantes`, só nome e celular) |
| `booking-site/src/pages/Booking.tsx` | Passa `quote.data?.cadastro`, monta o payload com os campos, trata `CADASTRO_INCOMPLETO` e `CPF_EM_USO` |
| `booking-site/src/pages/Booking.test.tsx` | Fluxo com número novo: campos aparecem e vão no payload |
| `booking-site/docs/visao-geral.md`, `booking-site/CLAUDE.md` | O passo "informa nome e celular" ganha o cadastro condicional |
| `TASKS_LOG.md`, PRD 032 | Registro e status |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. Backend puro: `campos_faltantes`, `email_valido`/`normaliza_email`,
   `paciente_do_telefone`, `cadastro_para_o_site`. Testes.
2. `quote.py` com `cadastro`. Teste.
3. `appointment_service` grava e completa. Teste.
4. `create_appointment.py` exige e recusa. Testes.
5. Painel: e-mail validado em create/update (dois arquivos, pequeno). Testes.
6. booking-site: utils, `CadastroFields`, `CustomerInfoForm`, `Booking.tsx`,
   tipos, service. Testes.
7. Docs, Postman, TASKS_LOG, status.

Um PR só, commits por etapa. Deploy do scheduler antes do merge (o backend
novo recusa paciente novo sem os campos; o site antigo mostraria erro
genérico até a Vercel publicar).

---

## 6. Detalhes por arquivo

### `scheduler/src/services/identificacao_de_paciente.py`

- **Modificar.**

```python
def campos_faltantes(paciente: Optional[Dict]) -> List[str]:
    """Os campos do cadastro ainda vazios, na ordem de CAMPOS_DO_CADASTRO.
    Paciente ausente: faltam todos."""
    paciente = paciente or {}
    return [c for c in CAMPOS_DO_CADASTRO if not _preenchido(paciente.get(c))]


def cadastro_completo(paciente: Optional[Dict]) -> bool:
    return not campos_faltantes(paciente)
```

### `scheduler/src/utils/cadastro.py`

- **Modificar.** Ao lado de `normaliza_cpf`:

```python
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normaliza_email(valor):
    """Minúsculo e sem espaços, ou None quando vazio, ou False quando inválido.
    Mesma convenção de `normaliza_cpf`: False é erro, None é ausência."""
    if valor is None:
        return None
    texto = str(valor).strip().lower()
    if not texto:
        return None
    return texto if _EMAIL.match(texto) else False
```

### `scheduler/src/services/carrinho.py`

- **Modificar.** Duas funções novas, usadas por `quote` e `create_appointment`:

```python
def paciente_do_telefone(db, clinic_id: str, phone: str) -> Optional[Dict]:
    """O paciente deste celular, ou None. Casa pelas variantes do número, como
    `identificacao_de_paciente.identificar`; mais de um casamento é tratado
    como nenhum (ambíguo: o site não tem como perguntar o nome, e pedir o
    cadastro é o lado seguro)."""
    linhas = db.execute_query(
        "SELECT id, name, birth_date, cpf, email FROM scheduler.patients "
        "WHERE clinic_id = %s AND phone = ANY(%s) AND deleted_at IS NULL",
        (clinic_id, sorted(variantes_do_numero(phone))),
    )
    return linhas[0] if len(linhas) == 1 else None


def cadastro_para_o_site(paciente: Optional[Dict]) -> Dict:
    """O que o site precisa saber: se está completo e o que falta. Só nomes de
    campos, nunca valores (a rota é pública e não pede OTP). `name` sai da
    lista: o site sempre pede o nome."""
    faltam = [c for c in campos_faltantes(paciente) if c != "name"]
    return {"completo": not faltam, "faltam": faltam}
```

- `from src.services.identificacao_de_paciente import campos_faltantes` e
  `from src.utils.phone import variantes_do_numero` (confirmar que `carrinho`
  ainda não importa `phone`; importa `normalize_phone`).

### `scheduler/src/functions/public_booking/quote.py`

- **Modificar.** Depois de `cotacao = cota(...)`:

```python
cadastro = carrinho.cadastro_para_o_site(
    carrinho.paciente_do_telefone(db, clinic_id, phone)) if phone else None
```

- Na resposta, dentro de `"quote"`: `"cadastro": cadastro` (None sem celular).
- Docstring: acrescentar o parágrafo do PRD sobre o tamanho do vazamento
  ("tem cadastro completo" é do mesmo tamanho de "primeira sessão", e nunca
  traz valores).
- O `import` do módulo passa a ser `from src.services import carrinho` (hoje
  importa nomes soltos; manter os soltos e acrescentar o módulo é aceitável,
  mas um só estilo é melhor).

### `scheduler/src/functions/public_booking/create_appointment.py`

- **Modificar.** Constantes ao lado de `HAS_FUTURE_APPOINTMENT`:

```python
CADASTRO_INCOMPLETO = "CADASTRO_INCOMPLETO"
CPF_EM_USO = "CPF_EM_USO"
```

- Depois de validar `phone` e antes da cotação (o cadastro não depende do
  carrinho), ler e normalizar:

```python
cpf = normaliza_cpf(body.get("cpf"))
if cpf is False or (cpf and not cpf_valido(cpf)):
    return http_response(400, {"status": "ERROR", "code": CADASTRO_INCOMPLETO,
                               "faltam": ["cpf"], "message": "CPF inválido"})
birth_date = normaliza_data_nascimento(body.get("birthDate"))
if birth_date is False or (birth_date and birth_date >= agora.date().isoformat()):
    return http_response(400, {... "faltam": ["birth_date"], "message": "Data de nascimento inválida"})
email = normaliza_email(body.get("email"))
if email is False:
    return http_response(400, {... "faltam": ["email"], "message": "E-mail inválido"})
```

  (`agora` já é calculado para a janela; mover a linha para antes, ou usar
  `relogio.agora_na_clinica` aqui. `normaliza_data_nascimento` devolve ISO.)

- A exigência, pela mesma função do `/quote`:

```python
paciente = carrinho.paciente_do_telefone(db, clinic_id, phone)
informados = {"cpf": cpf, "birth_date": birth_date, "email": email}
faltam = [c for c in carrinho.cadastro_para_o_site(paciente)["faltam"] if not informados.get(c)]
if faltam:
    return http_response(400, {
        "status": "ERROR", "code": CADASTRO_INCOMPLETO, "faltam": faltam,
        "message": "Para a primeira sessão precisamos de CPF, data de nascimento e e-mail.",
    })
```

- CPF em uso por outro paciente (só quando `cpf` veio):

```python
if cpf:
    dono = db.execute_query(
        "SELECT id FROM scheduler.patients WHERE clinic_id = %s AND cpf = %s AND deleted_at IS NULL "
        "AND (%s::uuid IS NULL OR id <> %s::uuid) LIMIT 1",
        (clinic_id, cpf, paciente and str(paciente["id"]), paciente and str(paciente["id"])),
    )
    if dono:
        return http_response(409, {"status": "ERROR", "code": CPF_EM_USO,
                                   "message": "Este CPF já está cadastrado com outro celular. Fale com a clínica."})
```

  Observação: o `409` sem `code` continua sendo horário ocupado; o site já
  distingue por `code`.

- Na chamada `service.create_appointment(...)`: `cpf=cpf, birth_date=birth_date, email=email`.
- Docstring do handler: os três campos novos no corpo, "obrigatórios quando o
  celular não é de um paciente com cadastro completo".

### `scheduler/src/services/appointment_service.py`

- **Modificar.** `create_appointment` ganha `cpf: Optional[str] = None,
  birth_date: Optional[str] = None, email: Optional[str] = None` e passa os
  três a `_get_or_create_patient(clinic_id, phone, full_name, cpf, birth_date, email)`.
- `_get_or_create_patient`:
  - INSERT: `(clinic_id, phone, name, cpf, birth_date, email, created_at, updated_at)`.
  - Paciente existente ativo: um UPDATE só, substituindo o atual que só tratava
    o nome:

```python
atualizado = self.db.execute_write_returning(
    """
    UPDATE scheduler.patients
       SET name = COALESCE(NULLIF(name, ''), %s),
           cpf = COALESCE(cpf, %s),
           birth_date = COALESCE(birth_date, %s::date),
           email = COALESCE(NULLIF(email, ''), %s),
           updated_at = NOW()
     WHERE id = %s::uuid
       AND (NULLIF(name, '') IS NULL OR cpf IS NULL OR birth_date IS NULL OR NULLIF(email, '') IS NULL)
    RETURNING *
    """,
    (nome, cpf, birth_date, email, str(existing["id"])),
)
return atualizado or existing
```

    O `WHERE` evita escrever quando não há nada vazio (e o `updated_at` não
    muda à toa). Dado existente nunca é sobrescrito: é `COALESCE(existente,
    novo)`, a regra que o nome já seguia.
  - Restaurado de soft-delete: o UPDATE de restauração também recebe os
    `COALESCE` acima.
  - Docstring: "O nome entra junto" vira "Nome, CPF, nascimento e e-mail
    entram juntos; o que já existe não é sobrescrito".
- Bot e painel chamam sem os campos novos: `None` em tudo, comportamento
  idêntico ao atual.

### `scheduler/src/functions/patient/create.py` e `update.py`

- **Modificar.** `email = normaliza_email(body.get("email"))`; `False` vira
  `400 "E-mail inválido"`. Em `update.py`, no ramo `field == "email"`.

### Testes do scheduler

- `test_identificacao_de_paciente.py`: `campos_faltantes(None) ==
  ["name", "birth_date", "cpf", "email"]`; paciente com e-mail `""` ->
  `["email"]`; completo -> `[]`.
- `test_carrinho_do_site.py`: `Db.__init__(..., paciente="completo")`;
  `execute_query` responde `FROM scheduler.patients` com
  `{"id": PACIENTE, "name": "Maria", "cpf": "52998224725", "birth_date": "1990-01-01", "email": "m@x.com"}`
  quando `completo`, `[]` quando `None`, e um dict parcial quando `"parcial"`.
  Os testes atuais de quote e criação não mudam de resultado.
- `test_cadastro_pelo_site.py` (novo), reaproveitando `_Handler`, `Db`,
  `motor_falso` e `_Criacao` por import:
  - Quote com celular de paciente completo: `cadastro == {"completo": True, "faltam": []}`.
  - Quote com celular novo: `{"completo": False, "faltam": ["birth_date", "cpf", "email"]}`.
  - Quote sem celular: `cadastro is None`.
  - Criação, número novo, sem os campos: `400`, `code == CADASTRO_INCOMPLETO`,
    `faltam` com os três; `create_appointment` não chamado.
  - Criação, número novo, com os três válidos: `201`; kwargs do serviço trazem
    `cpf="52998224725"`, `birth_date="1990-01-01"`, `email="m@x.com"` (e-mail
    normalizado em minúsculo).
  - Criação, parcial (falta só e-mail): sem e-mail `400 faltam == ["email"]`;
    com e-mail `201`.
  - CPF inválido (`"11111111111"`), data futura, e-mail sem `@`: `400` com o
    campo em `faltam`.
  - CPF de outro paciente: `Db` responde a consulta `cpf = %s` com um id
    diferente -> `409 CPF_EM_USO`.
  - Paciente completo e requisição sem os campos: `201` (nada exigido).
- `test_appointment_service` (ou novo `test_paciente_do_site.py`):
  `_get_or_create_patient` com paciente existente sem CPF e com e-mail: o
  UPDATE leva `COALESCE`; com tudo preenchido, não há `execute_write_returning`.
- Painel: `test_cadastro_paciente.py` ganha "e-mail inválido -> 400" em
  create e update.

### `booking-site/src/utils/cadastro.ts` (novo)

```ts
export function onlyDigits(v: string): string
export function formatCpf(v: string): string          // 000.000.000-00, copiado do checkin
export function isValidCpf(v: string): boolean        // dígitos verificadores, copiado do checkin
export function formatDateInput(v: string): string    // DD/MM/AAAA enquanto digita
export function brDateToIso(v: string): string | null // "31/10/1990" -> "1990-10-31", null se inválida
export function isValidBirthDate(v: string): boolean  // data real, no passado, ano >= 1900
export function isValidEmail(v: string): boolean      // mesmo regex do backend
```

### `booking-site/src/types/index.ts`

```ts
export type CampoDoCadastro = 'cpf' | 'birth_date' | 'email'

export interface CadastroDoSite {
  completo: boolean
  faltam: CampoDoCadastro[]
}

export interface Quote {
  ...
  /** null sem celular; o que falta no cadastro deste número (PRD 032). */
  cadastro: CadastroDoSite | null
}

export interface CreateAppointmentPayload extends CartPayload {
  ...
  cpf?: string        // só dígitos
  birthDate?: string  // YYYY-MM-DD
  email?: string
}
```

### `booking-site/src/components/CadastroFields.tsx` (novo)

- Props: `faltam: CampoDoCadastro[]`, `register`, `errors`, `setValue`
  (tipados com `UseFormReturn<CustomerInfoFormData>`).
- Renderiza só os campos em `faltam`, na ordem CPF, nascimento, e-mail, com um
  texto acima: "Primeira vez aqui? Completamos seu cadastro." CPF e data com
  máscara e `inputMode="numeric"`; e-mail com `inputMode="email"` e
  `autoComplete="email"`.
- Campos de CPF e data controlados localmente como o celular já é (o
  `watch()` quebra o React Compiler nesse componente, ver comentário em
  `CustomerInfoForm`).

### `booking-site/src/components/CustomerInfoForm.tsx`

- Props novas: `camposFaltantes?: CampoDoCadastro[]` (default `[]`) e
  `aguardandoCadastro?: boolean` (a cotação com o celular ainda não voltou:
  o botão fica desabilitado com "Verificando cadastro...").
- Schema dinâmico, montado com `useMemo` a partir de `camposFaltantes`:

```ts
function schemaPara(faltam: CampoDoCadastro[]) {
  return z.object({
    fullName: z.string().min(2, 'Digite seu nome completo'),
    phone: z.string().refine(isValidBrPhone, 'Celular inválido'),
    cpf: faltam.includes('cpf') ? z.string().refine(isValidCpf, 'CPF inválido') : z.string().optional(),
    birthDate: faltam.includes('birth_date') ? z.string().refine(isValidBirthDate, 'Data inválida') : z.string().optional(),
    email: faltam.includes('email') ? z.string().refine(isValidEmail, 'E-mail inválido') : z.string().optional(),
  })
}
export type CustomerInfoFormData = z.infer<ReturnType<typeof schemaPara>>
```

- `onSubmit` recebe os campos como digitados; a conversão (CPF só dígitos,
  data ISO) acontece em `Booking.tsx` ao montar o payload.
- O teste existente ("envia os dados válidos" com `toEqual({fullName, phone})`)
  passa a usar `toMatchObject`, porque o objeto ganha chaves opcionais vazias.

### `booking-site/src/pages/Booking.tsx`

- `camposFaltantes = quote.data?.cadastro?.faltam ?? []`.
- `aguardandoCadastro = quotePhone !== undefined && (quote.isFetching || quote.isPlaceholderData)`.
- Em `handleCustomerSubmit`, no payload: `cpf: onlyDigits(data.cpf ?? '') || undefined`,
  `birthDate: data.birthDate ? brDateToIso(data.birthDate) ?? undefined : undefined`,
  `email: data.email?.trim() || undefined`.
- Em `onError`: `CADASTRO_INCOMPLETO` -> `setSubmitError('Precisamos completar seu cadastro: ' + faltam traduzidos)`
  e a cotação é refeita (`quote.refetch()`) para os campos aparecerem;
  `CPF_EM_USO` -> `setSubmitError(err.message)`. `ApiError` precisa expor
  `body.faltam` (ver `services/api.ts`: `ApiError` já guarda `body`).
- Rótulos dos campos para a mensagem: `{ cpf: 'CPF', birth_date: 'data de nascimento', email: 'e-mail' }`
  em `utils/cadastro.ts`.

### Testes do booking-site

- `utils/cadastro.test.ts`: CPF válido/inválido/repetido, máscara, data
  `29/02/2024` válida e `31/02/2024` inválida, data futura inválida, e-mail.
- `CadastroFields.test.tsx`: `faltam=['email']` mostra só e-mail; `faltam=[]`
  não renderiza nada; máscara do CPF enquanto digita.
- `CustomerInfoForm.test.tsx`: sem `camposFaltantes`, igual a hoje; com os
  três, não envia com CPF inválido; com os três válidos, `onSubmit` recebe
  `cpf`, `birthDate`, `email`.
- `Booking.test.tsx`: quote mock com `cadastro.faltam = ['cpf','birth_date','email']`
  -> os campos aparecem e o payload de `createAppointment` traz `cpf` só
  dígitos e `birthDate` ISO; quote com `cadastro.completo = true` -> só nome e
  celular; `createAppointment` rejeitando com `CADASTRO_INCOMPLETO` -> mensagem
  na tela.

### Docs

- `booking-site/docs/visao-geral.md` §2 passo 6 e §5; `booking-site/CLAUDE.md`
  ("Criar agendamento não exige verificação" ganha a frase sobre o cadastro).
- `tests/integration/032-*.md`: os quatro casos do PRD com curl.
- Postman 032: `quote` com celular (asserta `quote.cadastro`), criação sem
  cadastro (400 `CADASTRO_INCOMPLETO`), criação completa (201).
- TASKS_LOG e status do PRD.

---

## 7. Convenções a respeitar

- Fonte única: a régua do cadastro é `CAMPOS_DO_CADASTRO`; a decisão "o que
  falta" é `cadastro_para_o_site`, usada por `quote` e `create_appointment`.
- Validações pelas funções de `utils/cadastro.py`; o front valida para
  feedback imediato, o servidor decide.
- Nunca logar CPF, e-mail ou nascimento; manter o padrão `_final_do_telefone`.
- Frontend: named exports, 4 estados, zero `any`, lint zero.
- Branch `feat/032-site-cadastro-do-paciente-novo`, PR para `main`. Deploy do
  scheduler antes do merge.
