# Spec — 009 Exclusão e Rolagem na Tela de Horários

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/009-horarios-delete-scroll.md`

---

## 1. Resumo

Implementa exclusão de regras de disponibilidade e exceções de ponta a ponta (backend Lambda + rotas + UI) e substitui o "editar horário" atual, hoje um `delete → create` não-atômico e quebrado, por um `PATCH` real. No frontend, a página `/horarios` é quebrada em componentes por seção, ganha um container de rolagem com altura máxima reutilizável, exclusão com optimistic update e undo via toast, seleção múltipla de datas fixas e tratamento de erro em todas as mutations.

**Ordem de deploy obrigatória:** scheduler primeiro, frontend depois. O frontend novo aponta para rotas que só existem após o deploy do backend.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `frontend/src/components/ui/ScrollArea.tsx` | Container com altura máxima, rolagem interna e fade nas bordas |
| `frontend/src/components/ui/Toast.tsx` | `ToastProvider` + `useToast`, com suporte a ação (Desfazer) |
| `frontend/src/pages/horarios/components/FixedDaysSection.tsx` | Seção de dias fixos + modo de seleção múltipla |
| `frontend/src/pages/horarios/components/RecurringSection.tsx` | Seção de horários recorrentes |
| `frontend/src/pages/horarios/components/ExceptionsSection.tsx` | Seção de exceções + ação de excluir |
| `frontend/src/pages/horarios/components/TimeRangeChip.tsx` | Chip de faixa horária (clique = editar, × = excluir) |
| `frontend/src/hooks/useAvailabilityRules.test.ts` | Testes de optimistic update, rollback e undo |
| `scheduler/tests/mocks/availability/delete_rule.json` | Mock de evento DELETE de regra |
| `scheduler/tests/mocks/availability/delete_exception.json` | Mock de evento DELETE de exceção |
| `scheduler/tests/mocks/availability/update_rule.json` | Mock de evento PATCH de regra |
| `scheduler/tests/integration/availability-delete.md` | Casos de teste manuais via curl |
| `scheduler/tests/postman/availability-delete.postman_requests.json` | Requests do fluxo completo |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/functions/availability/rules.py` | `delete_handler`, `update_handler`; corrigir `except UniqueViolation` |
| `scheduler/src/functions/availability/exceptions.py` | `delete_handler` |
| `scheduler/sls/functions/availability/interface.yml` | 3 Lambdas novas: `DeleteAvailabilityRule`, `UpdateAvailabilityRule`, `DeleteAvailabilityException` |
| `scheduler/src/scripts/setup_database.py` | Índice único parcial para datas fixas |
| `frontend/src/services/availability.service.ts` | `deleteRule` com `clinicId`; `updateRule`; `deleteException` |
| `frontend/src/hooks/useAvailabilityRules.ts` | Optimistic update + rollback; `useUpdateAvailabilityRule`; `useDeleteAvailabilityException` |
| `frontend/src/types/index.ts` | `UpdateAvailabilityRulePayload`; remover `active` de `AvailabilityException` |
| `frontend/src/pages/horarios/HorariosPage.tsx` | Reduzir a orquestração; delegar às 3 seções |
| `frontend/src/main.tsx` | Envolver a app com `ToastProvider` |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. **Migration** (`setup_database.py`) — precedida da checagem de duplicatas da seção 6.1.
2. **Handlers backend** (`rules.py`, `exceptions.py`) + `interface.yml`.
3. **Deploy do scheduler em dev** e validação por curl antes de tocar no frontend.
4. **Camada de dados do frontend**: types → service → hooks (com optimistic update).
5. **Primitivos de UI**: `ScrollArea`, `Toast` + `ToastProvider` no `main.tsx`.
6. **Componentes de seção**: `TimeRangeChip` → `RecurringSection` → `ExceptionsSection` → `FixedDaysSection` (a última é a mais complexa, por causa da seleção múltipla).
7. **`HorariosPage`** — recomposição.
8. **Testes de hook**, lint, build.
9. **Mocks, integração e Postman.**

---

## 6. Detalhes por arquivo

### 6.1 `scheduler/src/scripts/setup_database.py`

**Modificar.** Adicionar ao final da lista `MIGRATIONS`, após o bloco de `uq_availability_rules_clinic_day`:

```python
# Impede data fixa duplicada (mesma data + mesmo horario de inicio).
# Parcial: nao afeta regras recorrentes, onde rule_date e NULL.
"""
CREATE UNIQUE INDEX IF NOT EXISTS uq_availability_rules_clinic_date
ON scheduler.availability_rules (clinic_id, rule_date, start_time)
WHERE rule_date IS NOT NULL
""",
```

Também atualizar o `CREATE TABLE` de `availability_rules` na lista `TABLES` para incluir `rule_date DATE` e `day_of_week INTEGER` sem `NOT NULL` — hoje o CREATE TABLE está dessincronizado das migrations que já rodaram (`day_of_week` ainda aparece como `NOT NULL` e `rule_date` não aparece). Um banco criado do zero hoje diverge de um banco migrado.

> **Pré-requisito de deploy — rodar antes da migration:**
> ```sql
> SELECT clinic_id, rule_date, start_time, COUNT(*)
> FROM scheduler.availability_rules
> WHERE rule_date IS NOT NULL
> GROUP BY 1,2,3 HAVING COUNT(*) > 1;
> ```
> Se retornar linhas, o `CREATE UNIQUE INDEX` falha. Deduplicar (manter o `created_at` mais antigo) antes de prosseguir. **Não executar deduplicação em produção sem aprovação explícita do André.**

### 6.2 `scheduler/src/functions/availability/rules.py`

**Modificar.**

**`delete_handler(event, context)`** — `DELETE /clinics/{clinicId}/availability-rules/{ruleId}`

- Padrão idêntico a `src/functions/patient/delete.py`: `require_api_key(event)` → `extract_path_param` de `clinicId` e `ruleId` → 400 se faltar.
- **Hard delete** (justificativa no PRD §2.3):
  ```python
  deleted = db.execute_write_returning(
      "DELETE FROM scheduler.availability_rules "
      "WHERE id = %s::uuid AND clinic_id = %s RETURNING id",
      (rule_id, clinic_id),
  )
  ```
- `deleted is None` → 404 `"Regra de disponibilidade nao encontrada"`. Cobre tanto "não existe" quanto "pertence a outra clínica", sem distinguir os casos na resposta — não vazar existência entre tenants.
- Sucesso → 200 `{"status": "SUCCESS", "message": "Regra excluida"}`.
- `ruleId` inválido (não-UUID) faz o cast `%s::uuid` levantar `psycopg2.errors.InvalidTextRepresentation`. Capturar e devolver 400, não 500.
- Log: `logger.info(f"[clinicId: {clinic_id}] Availability rule deleted: {rule_id}")`.

**`update_handler(event, context)`** — `PATCH /clinics/{clinicId}/availability-rules/{ruleId}`

- Substitui o delete+create do frontend. Aceita apenas `start_time` e `end_time` — mudar o dia ou a data de uma regra é conceitualmente outra regra e continua sendo excluir + criar.
- Valida que ao menos um dos dois campos veio; 400 caso contrário.
- `UPDATE ... SET start_time = COALESCE(%s, start_time), end_time = COALESCE(%s, end_time) WHERE id = %s::uuid AND clinic_id = %s RETURNING *`.
- 404 se não afetou linha. 200 com a regra serializada via `_serialize_row`.
- Capturar `pg_errors.UniqueViolation` → 409 (um PATCH pode colidir com o novo índice de data fixa).
- **Validar `start_time < end_time`** e devolver 400 com mensagem clara. Não existe check constraint no banco para isso, e o `create_handler` também não valida — uma faixa invertida hoje entra no banco e gera zero slots silenciosamente. Adicionar a mesma validação ao `create_handler`.

**Correção do `except pg_errors.UniqueViolation` (linhas 96–102)**

O bloco atual faz `DAY_NAMES[day_of_week]` incondicionalmente. Numa violação vinda de regra de data fixa, `day_of_week` é `None` e o `except` quebra com `TypeError`, escapando para o `except Exception` e devolvendo **500 em vez de 409**. Com o índice novo da §6.1, esse caminho passa a ser alcançável de fato. Reescrever:

```python
except pg_errors.UniqueViolation:
    if day_of_week is not None:
        DAY_NAMES = ["Domingo", "Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado"]
        message = f"Ja existe uma regra de disponibilidade para {DAY_NAMES[day_of_week]} nesta clinica"
    else:
        message = f"Ja existe um horario cadastrado para {rule_date} comecando as {start_time}"
    return http_response(409, {"status": "ERROR", "message": message})
```

### 6.3 `scheduler/src/functions/availability/exceptions.py`

**Modificar.** `delete_handler` — `DELETE /clinics/{clinicId}/availability-exceptions/{exceptionId}`. Mesma estrutura do `delete_handler` de rules; hard delete (a tabela não tem coluna `active`). 404 → `"Excecao nao encontrada"`.

### 6.4 `scheduler/sls/functions/availability/interface.yml`

**Modificar.** Três entradas novas, copiando o bloco IAM/CORS/timeout dos handlers existentes do arquivo:

| Lambda | handler | path | method |
|---|---|---|---|
| `DeleteAvailabilityRule` | `src.functions.availability.rules.delete_handler` | `clinics/{clinicId}/availability-rules/{ruleId}` | `delete` |
| `UpdateAvailabilityRule` | `src.functions.availability.rules.update_handler` | `clinics/{clinicId}/availability-rules/{ruleId}` | `patch` |
| `DeleteAvailabilityException` | `src.functions.availability.exceptions.delete_handler` | `clinics/{clinicId}/availability-exceptions/{exceptionId}` | `delete` |

`iamRoleStatementsName` tem limite de 64 caracteres no CloudFormation e o prefixo `${self:service}-${self:custom.stage}-` já consome boa parte — por isso o arquivo já usa abreviações como `CreateAvailExcept`. Usar: `DelAvailRule`, `UpdAvailRule`, `DelAvailExcept`.

### 6.5 `frontend/src/types/index.ts`

**Modificar.**

```ts
export interface UpdateAvailabilityRulePayload {
  start_time?: string
  end_time?: string
}
```

Remover `active: boolean` de `AvailabilityException` (linha 198). A tabela `scheduler.availability_exceptions` não tem essa coluna — o campo nunca chega da API e o tipo mente sobre a resposta. Verificar antes se algum consumidor lê `exception.active`.

### 6.6 `frontend/src/services/availability.service.ts`

**Modificar.**

```ts
deleteRule(clinicId: string, ruleId: string) {
  return api.delete(`/clinics/${clinicId}/availability-rules/${ruleId}`).then((r) => r.data)
},

updateRule(clinicId: string, ruleId: string, payload: UpdateAvailabilityRulePayload) {
  return api.patch<RuleResponse>(`/clinics/${clinicId}/availability-rules/${ruleId}`, payload)
    .then((r) => r.data.data)
},

deleteException(clinicId: string, exceptionId: string) {
  return api.delete(`/clinics/${clinicId}/availability-exceptions/${exceptionId}`).then((r) => r.data)
},
```

A rota antiga `/availability-rules/${ruleId}` (sem `clinicId`) sai — nunca existiu no backend e não era escopada por tenant.

### 6.7 `frontend/src/hooks/useAvailabilityRules.ts`

**Modificar.** Núcleo da sensação de fluidez pedida.

**`useDeleteAvailabilityRule`** com optimistic update:

```ts
return useMutation({
  mutationFn: (ruleId: string) => availabilityService.deleteRule(clinicId!, ruleId),
  onMutate: async (ruleId) => {
    // Obrigatorio: sem cancelar, um refetch em voo repoe o item excluido.
    await queryClient.cancelQueries({ queryKey: availabilityRuleKeys.list(clinicId!) })
    const previous = queryClient.getQueryData<ListAvailabilityRulesResponse>(
      availabilityRuleKeys.list(clinicId!)
    )
    queryClient.setQueryData(availabilityRuleKeys.list(clinicId!), (old) =>
      old ? { ...old, data: old.data.filter((r) => r.id !== ruleId) } : old
    )
    return { previous }
  },
  onError: (_err, _ruleId, context) => {
    if (context?.previous) {
      queryClient.setQueryData(availabilityRuleKeys.list(clinicId!), context.previous)
    }
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: availabilityRuleKeys.list(clinicId!) })
    queryClient.invalidateQueries({ queryKey: slotKeys.all })
  },
})
```

- `cancelQueries` não é opcional. Sem ele, uma query em voo sobrescreve o cache e o item excluído reaparece sozinho — o bug clássico desse padrão.
- `invalidateQueries` vai em `onSettled`, não em `onSuccess`: precisa rodar também no erro, para reconciliar com o servidor.
- `slotKeys.all` continua sendo invalidado; excluir disponibilidade muda os slots que o bot do WhatsApp oferece.

**`useDeleteAvailabilityException`** — mesmo padrão sobre `exceptionKeys.list(clinicId!)`. Atenção: `listExceptions` retorna o array direto (`r.data.data`), enquanto `listRules` retorna o envelope `{status, data}`. As duas funções de update do cache têm formatos diferentes; não copiar uma na outra sem ajustar.

**`useUpdateAvailabilityRule`** — mutation simples, sem optimistic (o usuário está num modal esperando confirmação). Invalida a lista e `slotKeys.all`.

O `staleTime: 5 * 60 * 1000` da query de rules (linha 30) permanece, mas a invalidação em `onSettled` o ignora — comportamento correto.

### 6.8 `frontend/src/components/ui/Toast.tsx`

**Criar.** Não existe nenhum mecanismo de toast no projeto (nem componente próprio, nem `sonner`/`react-hot-toast`). Implementar interno, sem dependência nova.

- `ToastProvider` com contexto e fila; `useToast()` devolve `showToast({ message, variant, action?, duration? })`.
- `action?: { label: string; onClick: () => void }` — é o que viabiliza o "Desfazer".
- Variantes: `success`, `error`. `error` **não** auto-dismissa (o usuário precisa poder ler a falha); `success` sai em 6s.
- Posição: canto inferior direito, empilhados, `z-index` acima do `Modal`.
- Entrada/saída animando **apenas `transform` e `opacity`**, 200–300ms, easing `ease-out-quart`. Respeitar `prefers-reduced-motion` (sem movimento, só opacidade).
- `role="status"` / `aria-live="polite"` para success, `aria-live="assertive"` para error.
- Não usar cor como único sinal: ícone + texto distinguem sucesso de erro.

### 6.9 `frontend/src/components/ui/ScrollArea.tsx`

**Criar.**

```ts
interface ScrollAreaProps {
  maxHeight: number      // px
  children: React.ReactNode
  className?: string
}
```

- `<div style={{ maxHeight }} className="overflow-y-auto">`. Com conteúdo menor que `maxHeight` o container encolhe naturalmente — não pode reservar área vazia.
- Fade nas bordas indicando corte, renderizado **só quando há conteúdo além do limite**. Detectar via `scrollHeight > clientHeight` e posição do scroll (`ResizeObserver` + handler de `scroll`), alternando as máscaras de topo e base. Um fade permanente mente sobre o conteúdo quando a lista é curta.
- O fade é `pointer-events-none` e cobre a borda do container pai, sem escurecer conteúdo interativo.
- Não capturar o scroll da página quando a lista chega ao fim (`overscroll-behavior: contain`).

**Altura máxima por seção:** `maxHeight={320}` (≈ 5 linhas de 64px). Valor único como constante em `HorariosPage`, aplicado às três seções — não valores diferentes por seção sem motivo.

### 6.10 `frontend/src/pages/horarios/components/TimeRangeChip.tsx`

**Criar.** Extrai o chip hoje duplicado em `HorariosPage.tsx:180-195` e `:227-242` (mesma estrutura, só muda a cor).

```ts
interface TimeRangeChipProps {
  startTime: string
  endTime: string
  tone: 'fixed' | 'recurring'
  onEdit: () => void
  onDelete: () => void
  disabled?: boolean
}
```

- **Corrigir acessibilidade:** o chip atual é um `<span>` com `onClick` — não é focável nem acionável por teclado. Vira `<button>`, com o `×` como `<button>` irmão, **não aninhado** (botão dentro de botão é HTML inválido; hoje o código faz exatamente isso e depende de `stopPropagation`).
- Touch target mínimo 44px no alvo de exclusão.
- `aria-label` explícito no `×`: `"Excluir horário das 09:00 às 18:00"`.
- Substituir o `—` do label (`{start} — {end}`) por `–` (en dash) ou hífen. Travessão é proibido pela preferência do André.

### 6.11 `frontend/src/pages/horarios/components/FixedDaysSection.tsx`

**Criar.** A seção mais complexa; concentra a seleção em lote.

- Props: `rules: AvailabilityRule[]`, `onEdit(rule)`, `onAdd()`.
- Agrupa por `rule_date` (lógica hoje em `HorariosPage.tsx:62-67`, movida para cá) e ordena por data crescente.
- Envolve a lista em `<ScrollArea maxHeight={320}>`.
- **Modo de seleção:** botão "Selecionar" no header alterna o modo. Ativo → checkbox por **data** (não por chip), contador "N datas selecionadas", ações "Excluir selecionadas" e "Cancelar". Selecionar uma data marca todas as faixas daquela data.
- Exclusão em lote: `Promise.allSettled` sobre os DELETEs (não `Promise.all` — precisamos do resultado de cada um). Depois:
  - Todos ok → toast `"N datas excluídas"` com undo.
  - Falha parcial → toast de **erro** `"3 de 5 datas excluídas. As demais falharam."` Nunca reportar sucesso genérico quando parte falhou.
- Empty state mantém o texto atual, que já orienta a ação.
- **Formatação de data:** manter o padrão `new Date(date + 'T12:00:00')` já usado no arquivo (o meio-dia evita o off-by-one de fuso ao parsear `YYYY-MM-DD` como UTC). Extrair para util, já que se repete em 3 pontos.

### 6.12 `frontend/src/pages/horarios/components/RecurringSection.tsx`

**Criar.** Extração direta de `HorariosPage.tsx:205-250`, com `ScrollArea` e `TimeRangeChip`.

Nota: os 7 dias sempre renderizam, então a lista tem altura fixa e o `ScrollArea` raramente corta. Manter mesmo assim, por consistência e porque o custo é zero quando não há overflow.

### 6.13 `frontend/src/pages/horarios/components/ExceptionsSection.tsx`

**Criar.** Extração de `HorariosPage.tsx:253-300` mais o botão de excluir por linha (hoje inexistente), com o mesmo padrão de optimistic + undo.

Tratar também o estado de **erro** da query de exceções: hoje `useAvailabilityExceptions` tem seu `isError` ignorado (`HorariosPage.tsx:24` só desestrutura `data` e `isLoading`), e uma falha renderiza o empty state "Nenhuma exceção cadastrada" — informação falsa. Passa a mostrar `ErrorState` com retry.

### 6.14 `frontend/src/pages/horarios/HorariosPage.tsx`

**Modificar.** De ~500 linhas para orquestração: queries, estado dos 4 modais e composição das 3 seções.

- `handleEditRule` (linhas 107-117) passa a chamar `useUpdateAvailabilityRule`. Some o `delete` + `create` sequencial — a origem do modal preso em loading e do risco de perder o horário.
- Todas as mutations ganham `onError` com toast. Hoje nenhuma trata erro.
- Modais de criação: manter, mas exibir erro inline (ex.: o 409 de "já existe regra para Segunda") em vez de fechar ou travar.

### 6.15 `frontend/src/main.tsx`

**Modificar.** `<ToastProvider>` dentro de `QueryClientProvider` e por fora de `RouterProvider`, para que qualquer rota alcance o toast.

### 6.16 `frontend/src/hooks/useAvailabilityRules.test.ts`

**Criar.** Vitest + `@testing-library/react`, com `QueryClientProvider` de teste e service mockado.

- Delete remove o item do cache **antes** da resolução da promise.
- Erro da API restaura o item (rollback).
- `cancelQueries` é chamado no `onMutate` — é a proteção contra o item reaparecer.
- Falha parcial em lote produz a contagem correta.

### 6.17 Testes de integração e Postman

`scheduler/tests/integration/availability-delete.md` — curl com `source .env && ... -H "x-api-key: $API_KEY"`, cobrindo:

1. Criar regra recorrente → excluir → **recriar no mesmo dia sem 409** (valida a decisão de hard delete).
2. Excluir regra de outra clínica → 404.
3. Excluir `ruleId` inexistente → 404; `ruleId` malformado → 400.
4. Criar data fixa duplicada (mesma data + start_time) → **409 com mensagem legível, não 500**.
5. Criar duas faixas distintas na mesma data → ambas aceitas.
6. `PATCH` de horário → 200 e reflexo em `GET /available-slots`.
7. `PATCH` com `start_time > end_time` → 400.
8. Excluir exceção → some do `GET`.

---

## 7. Convenções a respeitar

- **Logging:** `logger.info(f"[clinicId: {clinic_id}] ...")` — padrão já usado no módulo availability.
- **Naming:** Lambdas PascalCase no `interface.yml`; handlers `src.functions.{domain}.{module}.{fn}`; componentes PascalCase; hooks `use*`; services `*.service.ts`.
- **Frontend:** named exports; zero `any`; 4 estados (loading, erro, vazio, sucesso) em toda view com fetch; nunca chamar service direto do componente.
- **Migrations idempotentes:** `CREATE UNIQUE INDEX IF NOT EXISTS`; `CREATE TABLE` em `TABLES` mantido em sincronia.
- **Impeccable:** grid de 4pt; sem card dentro de card; animar só `transform`/`opacity`; `prefers-reduced-motion`; touch targets ≥ 44px; sem depender de cor isolada para transmitir estado; hierarquia de botões (a exclusão em lote é `danger`, a individual é ghost/ícone).
- **Sem travessão (`—`)** em texto de UI, comentário ou mensagem de commit. O código atual usa em vários pontos dos chips; corrigir nos arquivos tocados.
- **Secrets:** nada hardcoded; API key de teste vem do `.env`.

---

## 8. Riscos de implementação (recap acionável)

| Risco | Mitigação |
|---|---|
| Migration falha por duplicatas preexistentes | Rodar a query de checagem da §6.1 antes; deduplicar só com aprovação |
| Item excluído reaparece sozinho | `cancelQueries` no `onMutate` — não omitir |
| Undo colide com o UNIQUE após novo cadastro no mesmo dia | Tratar 409 no recreate com toast de erro explícito |
| Frontend em prod antes do backend | Deploy do scheduler primeiro, validado por curl |
| Hard delete é irreversível | Undo de 6s; regra de disponibilidade é barata de recriar |
| Excluir data com agendamento existente deixa appointment órfão | **Fora do escopo desta task** (o create também não valida, logo não é regressão). Registrado para task própria |
