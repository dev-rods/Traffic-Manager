# Spec - 047 Termo e anamnese em papel, registrados pelo paciente

> Gerada em 10/11/2026 a partir de `prd/047-papel-por-paciente.md`.
> Decisões do André: **§7.1 A** (ação na pasta do paciente e na linha da
> lista), **§7.2 B** (registro em lote com uma data para todos, com aviso),
> **§7.3 A** (selo só para quem está sem termo).

---

## 1. O que muda, em uma frase

A recepção registra "assinado em papel" pela pasta do paciente, pela linha da
lista ou em lote pela seleção, e a lista mostra e filtra quem está sem termo
vigente. O servidor só ganha o `consent_status` na listagem de pacientes e o
filtro; a rota de papel é a de hoje.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/functions/patient/list.py` | `consent_status` e `consent_enabled` por paciente (LATERAL igual ao da agenda); filtro `consent=missing\|ok` |
| `scheduler/tests/unit/test_lista_de_pacientes_sql.py`, `test_listagem_de_paciente.py` | o LATERAL, o filtro e a serialização |
| `frontend/src/types/index.ts` | `PatientWithStats.consent_status`, `consent_enabled`; `ConsentFilter` |
| `frontend/src/services/patients.service.ts` | `ListPatientsParams.consent` |
| `frontend/src/hooks/useConsents.ts` | `useRegistrarPapel` também invalida `patientKeys.lists()`; **novo** `useRegistrarPapelEmLote` |
| `frontend/src/components/RegistrarPapelModal.tsx` (+ test) | **novo** - o modal de hoje, compartilhado |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` (+ test) | usa o modal compartilhado |
| `frontend/src/pages/documentos/components/TermoDeConsentimento.tsx` (+ test) | botão "Assinado em papel" quando não há vigente; estado vazio com o botão |
| `frontend/src/pages/pacientes/components/SeloSemTermo.tsx` (+ test) | **novo** - o selo, no molde do `SeloSilenciado` |
| `frontend/src/pages/pacientes/components/contagemDeFiltros.ts`, `FiltrosDePacientes.tsx` (+ test) | filtro "Termo e anamnese" |
| `frontend/src/pages/pacientes/components/PatientsTable.tsx`, `PatientCard.tsx` (+ tests) | selo ao lado do nome; ação "Assinado em papel" para quem está sem termo |
| `frontend/src/pages/pacientes/components/AcoesEmLote.tsx`, `BatchPapelModal.tsx` (+ tests) | "Assinado em papel" na barra de seleção; modal do lote |
| `frontend/src/pages/pacientes/PacientesPage.tsx` | estado do filtro novo; abre os dois modais |
| `scheduler/tests/integration/047-papel-por-paciente.md` | **novo** - roteiro |

Nenhuma migration. Nenhuma rota nova.

---

## 3. Servidor: `patient/list.py`

### 3.1 `consent_status` por paciente

No `SELECT` principal (e só nele; o `COUNT` ganha o LATERAL apenas quando o
filtro `consent` está ligado), entra o mesmo bloco de `appointment/list.py`
118-131, trocando `a.clinic_id`/`a.patient_id` por `p.clinic_id`/`p.id`:

```sql
LEFT JOIN LATERAL (
    SELECT CASE WHEN pc.status IN ('SIGNED', 'PAPER') THEN pc.status ELSE 'SIGNING' END AS consent_status
    FROM scheduler.patient_consents pc
    WHERE pc.clinic_id = p.clinic_id AND pc.patient_id = p.id
      AND pc.term_version = %s AND pc.status IN ('SIGNED', 'PAPER', 'SIGNING')
    ORDER BY CASE pc.status WHEN 'SIGNED' THEN 0 WHEN 'PAPER' THEN 0 ELSE 1 END
    LIMIT 1
) ct ON TRUE
```

`ct.consent_status` entra na lista de colunas; o `GROUP BY p.id` já existente
precisa de `ct.consent_status` no agrupamento (ou `MAX(ct.consent_status)`;
usar o `GROUP BY` explícito, que é o que a query da agenda não precisa porque
não agrupa). `consentimento.versao()` vai no início dos `params`, antes de
`clinic_id`, como na agenda.

Na resposta, cada item leva `consent_status` (`SIGNED`/`PAPER`/`SIGNING`/
`null`) e o envelope leva `consent_enabled: bool(consentimento.versao())`,
uma vez só (não por item: é da clínica).

### 3.2 Filtro `consent`

Query string `consent`: `missing` ou `ok` (qualquer outro valor = sem filtro).

- `missing`: `ct.consent_status IS NULL OR ct.consent_status = 'SIGNING'` -
  quem o check-in ainda vai pedir. Entra no `WHERE` (não no `HAVING`: não é
  agregado), por isso o LATERAL também entra no `COUNT` quando o filtro está
  ligado.
- `ok`: `ct.consent_status IN ('SIGNED', 'PAPER')`.
- Sem `TCLE_VERSION` configurada, o filtro é ignorado (tudo seria `missing`
  e não há nada a regularizar).

### 3.3 Testes (pytest)

Em `test_lista_de_pacientes_sql.py` (molde já existente, que confere a SQL
montada): o LATERAL aparece com `versao()` como primeiro parâmetro; `consent=
missing` adiciona a cláusula e leva o LATERAL ao `COUNT`; `consent=ok` idem;
valor inválido não muda nada; sem versão, nada muda. Em
`test_listagem_de_paciente.py`: `consent_status` serializado por item,
`consent_enabled` no envelope.

---

## 4. Painel

### 4.1 Tipos e serviço

```ts
// types/index.ts
export interface PatientWithStats extends Patient {
  ...
  /** Termo e anamnese (PRD 036/047). null = nada da versão vigente. */
  consent_status: ConsentStatus | null
}
export type ConsentFilter = 'all' | 'missing' | 'ok'
export interface PaginatedResponse<T> { ...; consent_enabled?: boolean }
```

`ListPatientsParams.consent?: 'missing' | 'ok'`. A `PacientesPage` guarda
`consentFilter` como os outros três filtros e passa
`consent: consentFilter !== 'all' ? consentFilter : undefined`.

### 4.2 `RegistrarPapelModal` (compartilhado)

`frontend/src/components/RegistrarPapelModal.tsx`:

```ts
interface RegistrarPapelModalProps {
  open: boolean
  patientId: string
  onClose: () => void
  /** Chamado depois do toast de sucesso; quem abriu decide o que fazer. */
  onRegistrado?: () => void
}
```

É o JSX de hoje em `TermoDoAgendamento.tsx` (título "Termo assinado em
papel", texto "Guarde o papel na pasta da paciente. Aqui fica só o registro,
sem PDF.", campo "Assinado em" `type=date` `max=hoje()`, botões Cancelar e
Registrar), com `useRegistrarPapel` dentro e os toasts de hoje ("Termo em papel
registrado" / "Não foi possível registrar o termo."). A data começa em
`hoje()` e volta a `hoje()` ao fechar.

`TermoDoAgendamento` passa a renderizar `<RegistrarPapelModal open={modal ===
'papel'} patientId={a.patient_id} onClose={fechar} />` e perde o estado
`assinadoEm` e `confirmarPapel`. O `papel.isSuccess` que hoje muda a situação
local vira callback: `onRegistrado={() => setEmPapel(true)}`. O teste de
`TermoDoAgendamento` que cobre o papel continua passando (o DOM é o mesmo); o
teste novo do modal cobre data, toast e `onRegistrado`.

`useRegistrarPapel` passa a invalidar também `patientKeys.lists()`, para a
lista (selo e filtro) refletir o registro.

### 4.3 Pasta do paciente (`TermoDeConsentimento`)

- `vigente` já é calculado (`SIGNED`/`PAPER` da `term_version`). Quando
  `data.consent_enabled && !vigente`, um botão "Assinado em papel" (secundário,
  pequeno) acima da tabela, à direita de "Versão vigente".
- Estado vazio com `consent_enabled`: a descrição vira "A paciente assina o
  termo e responde a ficha no check-in do iPad. Se já assinou em papel,
  registre aqui." e `action` é o mesmo botão. Sem versão configurada, nada.
- O botão abre `RegistrarPapelModal` com o `patientId` da página. Depois do
  registro a lista de consents é invalidada pelo hook e a linha "Em papel"
  aparece; o botão some porque `vigente` passa a existir.
- Permissão: como na agenda, o painel não esconde o botão por permissão; a
  rota exige `agenda.escrever` e o toast de erro mostra a mensagem do 403.

### 4.4 Lista: selo, filtro e ação na linha

- **`SeloSemTermo`**: "Sem termo", `Badge` âmbar (`bg-amber-50
  text-amber-700 ring-amber-600/20`), mesmo molde do `SeloSilenciado`, com
  `title="Termo e anamnese sem assinatura vigente"`. Renderiza quando `consent_enabled && consent_status !== 'SIGNED'
  && consent_status !== 'PAPER'` (§7.3 A: quem está em dia não ganha nada;
  `SIGNING` conta como sem termo, igual ao `DOCS` da agenda). `consent_enabled`
  desce da página por prop, como `pausedPhones`.
- **Filtro**: `FiltrosDePacientes` ganha o quarto campo, select "Termo e
  anamnese" com "Todos" / "Sem termo vigente" / "Com termo vigente"; só
  aparece quando `consent_enabled`. `contaFiltrosAtivos` conta `consent !==
  'all'`. O drawer do celular herda sem trabalho (é o mesmo JSX).
- **Ação na linha** (§7.1 A): em `PatientsTable` e `PatientCard`, entre
  "Documentos" e "Excluir", um botão com ícone de assinatura/caneta,
  `title="Assinado em papel"`, **só para quem mostra o selo**. Chama
  `onPapel(p)`; a página abre `RegistrarPapelModal` com `p.id`. Ao registrar,
  o hook invalida a lista e o selo some da linha.

### 4.5 Lote (§7.2 B)

- `AcoesEmLote` ganha `onPapel` e o botão "Assinado em papel" entre WhatsApp e
  Excluir.
- `useRegistrarPapelEmLote` em `useConsents.ts`: cópia do molde de
  `useBatchDeletePatients` (laço sequencial, `results`, `progress`, `reset`,
  `runningRef`), chamando `consentsService.registerPaper(clinicId, id,
  signedAt)`. Resultado por pessoa: `'pending' | 'registered' | 'already' |
  'failed'`. `already` é quando a resposta vem **200** em vez de 201, ou o
  `consent` devolvido tem `paper_signed_at` diferente da data pedida - a rota
  devolve o vigente sem gravar quando já existe (`registra_papel` captura o
  `IntegrityError`); conferir o status HTTP é o sinal mais simples: `registerPaper` passa a
  devolver `{ consent, created: r.status === 201 }` (o `useRegistrarPapel`
  ignora `created`). Ao terminar,
  invalida `patientKeys.lists()`, `consentKeys.all` e `appointmentKeys.lists()`.
- `BatchPapelModal` (`pages/pacientes/components/`): molde do
  `BatchDeletePatientsModal`. Antes de rodar: a lista dos selecionados (nome),
  o campo "Assinado em" (`max=hoje()`) e o aviso em destaque: **"A mesma data
  vale para todas as pessoas selecionadas. Quem já tem termo vigente não é
  alterada."** Botão "Registrar N". Durante: barra de progresso e a lista com
  o estado de cada um (Registrado / Já tinha / Erro com a mensagem). Ao
  fechar depois de rodar: `onDone` limpa a seleção (`clearSelection`), como o
  excluir.
- A seleção só traz quem está na página; quem já está em dia pode estar
  selecionado - o lote não filtra, o servidor responde "já tinha" e o modal
  mostra. Simples e sem surpresa.

### 4.6 Testes (Vitest)

- `RegistrarPapelModal.test.tsx`: data padrão hoje, `max`, Registrar chama
  o serviço com `patientId` e a data, toast de sucesso e `onRegistrado`,
  toast de erro com a mensagem do servidor.
- `TermoDeConsentimento.test.tsx`: botão aparece sem vigente e some com
  `SIGNED`/`PAPER`; estado vazio com o botão; sem `consent_enabled`, nada.
- `SeloSemTermo.test.tsx`: nos quatro estados (`null`, `SIGNING`, `SIGNED`,
  `PAPER`) e com `consent_enabled=false`.
- `FiltrosDePacientes.test.tsx` / `contagemDeFiltros`: o campo novo, a
  contagem.
- `PatientsTable.test.tsx` / `PatientCard`: selo e ação só para quem está sem
  termo; `onPapel` com a paciente certa.
- `BatchPapelModal.test.tsx`: aviso presente, Registrar roda o laço na ordem,
  estados por pessoa (registrado, já tinha, erro), `onDone` ao fechar.
- `AcoesEmLote.test.tsx`: o botão novo chama `onPapel`.

Nome de paciente nos testes: fictício (`Paciente Teste 047`).

---

## 5. Ordem de implementação

1. Servidor: `list.py` (LATERAL, `consent_enabled`, filtro) + pytest.
2. Tipos, serviço (`consent`, `created` no `registerPaper`), hook de lote.
3. `RegistrarPapelModal` + troca em `TermoDoAgendamento` (sem mudança visível).
4. Pasta do paciente.
5. Lista: selo, filtro, ação na linha, `PacientesPage`.
6. Lote: `AcoesEmLote`, `BatchPapelModal`.
7. `npm run build`, `npm run lint`, `npm run test`; `pytest`.
8. Deploy dev; E2E em dev (clínica de teste com `TCLE_VERSION`): pasta,
   linha, lote com uma "já tinha"; conferir `DOCS` sumindo na agenda e o
   check-in pulando o termo. Prod com aval; conferir o tempo da listagem de
   pacientes na Essência depois do deploy.

---

## 6. Fora desta spec

- Registro em lote com data por pessoa.
- Separar termo de anamnese; anexar scan; mudar o gatilho do check-in.
