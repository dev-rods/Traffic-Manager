# PRD — 009 Exclusão e Rolagem na Tela de Horários

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Tornar a tela `/horarios` do painel da clínica capaz de **excluir** regras de disponibilidade e exceções cadastradas por engano, com reflexo imediato no banco e na UI (optimistic update com undo), e conter o crescimento vertical da página dando **altura máxima com rolagem** às listas de dias fixos, horários recorrentes e exceções.

Hoje a tela permite apenas cadastrar. A exclusão existe visualmente (o `×` nos chips de horário) mas **não funciona**: o frontend chama um endpoint que nunca foi implantado.

---

## 2. Contexto

### 2.1 A exclusão está quebrada, não ausente

`frontend/src/services/availability.service.ts:51` chama `DELETE /availability-rules/{ruleId}`. Esse endpoint não existe:

- `scheduler/sls/functions/availability/interface.yml` declara apenas 5 Lambdas: create/list de rules, create/list de exceptions e get de slots. Nenhuma rota DELETE.
- `scheduler/src/functions/availability/rules.py` tem apenas `create_handler` e `list_handler`. Não há `delete_handler` em nenhum arquivo do módulo.

Consequências observáveis hoje na produção:

1. O `×` no chip de horário (`HorariosPage.tsx:188` e `:235`) dispara uma mutation que falha. Como a mutation não trata erro, **nada acontece na tela** — o usuário clica e o horário continua lá, sem explicação.
2. Pior: **"Editar horário"** (`HorariosPage.tsx:107`) é implementado como `delete` seguido de `create`. O `deleteRule.mutateAsync` rejeita, o `await` interrompe o handler e o `createRule` nunca roda. O modal fica aberto com o botão em loading e o usuário não recebe feedback. Se o delete um dia passar a funcionar sem que o edit seja revisto, a sequência não é atômica e uma falha no create deixa o horário **apagado**.

### 2.2 A tela cresce sem limite

As três seções renderizam listas completas sem constraint de altura. A seção "Dias fixos" é a que mais cresce (uma linha por data cadastrada) e empurra "Horários recorrentes" e "Exceções" para fora do viewport. Numa clínica que cadastra dias fixos com semanas de antecedência, as duas seções de baixo ficam inacessíveis sem scroll longo da página inteira.

### 2.3 Restrição de schema que condiciona o design da exclusão

`setup_database.py:253` define:

```sql
ALTER TABLE scheduler.availability_rules
ADD CONSTRAINT uq_availability_rules_clinic_day UNIQUE (clinic_id, day_of_week);
```

Isso tem três implicações diretas nesta task:

- **Soft-delete em `availability_rules` é inviável.** O `list_handler` filtra `WHERE active = true`, então um soft-delete some da UI — mas a linha continua na tabela e continua ocupando o slot do UNIQUE. O usuário que exclui "Segunda 09:00–18:00" e tenta recadastrar "Segunda 08:00–17:00" recebe 409 permanente, sem nenhuma linha visível justificando o conflito. Por isso, para rules recorrentes a exclusão será **hard delete**. (Contraste com o PRD 008, onde soft-delete se justificava por FK de histórico em `appointments`; `availability_rules` não tem FK apontando para ela.)
- **Só é possível uma faixa recorrente por dia da semana.** A UI de `HorariosPage.tsx:226` renderiza `dayRules.map(...)` como se houvesse várias faixas por dia (manhã/tarde), mas o schema proíbe a segunda. O segundo "+ Adicionar faixa" no mesmo dia retorna 409. Fica **fora do escopo** desta task, mas é registrado na seção de riscos por afetar a leitura da tela.
- **Datas fixas não têm constraint alguma.** `rule_date` só aparece no índice não-único `idx_availability_rules_date`. Nada impede cadastrar a mesma data duas vezes — o que é justamente uma das formas de "cadastrar erroneamente" que motivou esta task. Adicionar a constraint faltante entra no escopo.

### 2.4 Exceções não têm exclusão nenhuma

`HorariosPage.tsx:275` lista exceções em modo somente-leitura. Não há botão, service, hook nem endpoint. Um feriado cadastrado na data errada é permanente hoje.

---

## 3. Escopo

### Dentro do escopo

#### Backend (`scheduler/`)

1. **`DELETE /clinics/{clinicId}/availability-rules/{ruleId}`**
   - Novo `delete_handler` em `scheduler/src/functions/availability/rules.py`.
   - **Hard delete**, pelo motivo da seção 2.3.
   - `WHERE id = %s AND clinic_id = %s` — o `clinic_id` no path e no WHERE garante isolamento multi-tenant. A rota atual usada pelo frontend (`/availability-rules/{ruleId}`, sem clinicId) permitiria a uma clínica excluir a regra de outra; a rota nova corrige isso.
   - 404 quando a regra não existe ou pertence a outra clínica (mesma resposta nos dois casos, para não vazar existência entre tenants).

2. **`DELETE /clinics/{clinicId}/availability-exceptions/{exceptionId}`**
   - Novo `delete_handler` em `scheduler/src/functions/availability/exceptions.py`, mesmo padrão. Hard delete (a tabela não tem coluna `active`).

3. **Rotas em `scheduler/sls/functions/availability/interface.yml`** — `DeleteAvailabilityRule` e `DeleteAvailabilityException`, seguindo o padrão de IAM/CORS/timeout dos handlers existentes do módulo. Atenção ao limite de nome de `iamRoleStatementsName` (os existentes já usam abreviações como `CreateAvailExcept`).

4. **Correção do tratamento de `UniqueViolation`** em `rules.py:96`. O `except` assume que `day_of_week` é um int e faz `DAY_NAMES[day_of_week]`. Quando a violação vier de uma regra de data fixa, `day_of_week` é `None` e o handler quebra com `TypeError` dentro do próprio except — devolvendo 500 em vez de 409. Passa a ramificar por tipo de regra e devolver mensagem adequada a cada caso.

5. **Migration idempotente** em `setup_database.py`: índice único parcial para datas fixas, que hoje não têm proteção nenhuma:
   ```sql
   CREATE UNIQUE INDEX IF NOT EXISTS uq_availability_rules_clinic_date
   ON scheduler.availability_rules (clinic_id, rule_date, start_time)
   WHERE rule_date IS NOT NULL;
   ```
   Inclui `start_time` para permitir faixas distintas na mesma data (manhã e tarde), bloqueando apenas a duplicata exata.
   > **Pré-requisito de deploy:** se já existirem duplicatas em produção, a criação do índice falha. A Spec deve incluir a query de verificação de duplicatas e a decisão de deduplicação antes de rodar a migration.

6. **Mocks, testes de integração e Postman** conforme o pós-implementação obrigatório do `CLAUDE.md`.

#### Frontend (`frontend/`)

7. **Camada de dados**
   - `availability.service.ts`: `deleteRule` migra para a rota com `clinicId`; novo `deleteException(clinicId, exceptionId)`.
   - `useAvailabilityRules.ts`: `useDeleteAvailabilityRule` ganha `onMutate`/`onError`/`onSettled` (optimistic update com rollback); novo `useDeleteAvailabilityException` no mesmo padrão. Ambos continuam invalidando `slotKeys.all`, já que excluir disponibilidade muda os slots ofertados pelo bot.

8. **Área máxima com rolagem** — componente reutilizável `components/ui/ScrollArea.tsx` (`maxHeight` + `overflow-y-auto`), aplicado às **três** seções, não só a dias fixos. As três têm a mesma estrutura de lista com `divide-y`; o componente evita repetir a solução três vezes. Indicação visual de conteúdo além do corte por máscara de fade nas bordas — não por sombra decorativa.

9. **Exclusão com undo otimista**
   - Clicar no `×` remove o item da lista imediatamente (cache do TanStack Query atualizado em `onMutate`) e dispara o DELETE.
   - Um toast "Horário excluído · Desfazer" fica visível por ~6s. "Desfazer" recria a regra com os mesmos campos.
   - Falha na API: rollback do cache (o item reaparece) + toast de erro com o motivo.
   - Requer um mecanismo de toast — verificar na Spec se já existe algum em `components/ui/` ou se precisa ser criado.

10. **Exclusão em lote de dias fixos** — modo de seleção na seção de dias fixos: checkbox por data, contador de selecionados e ação "Excluir N datas". Resolve o caso concreto de "cadastrei uma sequência errada" sem exigir N cliques individuais. Executa os DELETEs em paralelo e reporta falhas parciais explicitamente (ex.: "3 de 5 excluídas").

11. **Botão de excluir nas exceções**, hoje inexistente.

12. **Correção do "Editar horário"** — `handleEditRule` (`HorariosPage.tsx:107`) para de ser delete+create não-atômico. Opção preferida: `PATCH` no backend. Se ficar fora do orçamento desta task, no mínimo inverter a ordem (create novo → delete antigo, para nunca perder o horário) e tratar o erro de forma visível. A Spec decide.

13. **Estados de erro visíveis** em todas as mutations da tela — hoje nenhuma trata `isError`.

### Fora do escopo

- Cadastro de datas fixas por intervalo/período (decisão do André: só rolagem + exclusão nesta task).
- Remover ou flexibilizar `uq_availability_rules_clinic_day` para permitir múltiplas faixas recorrentes por dia (manhã/tarde). Registrado como risco, tratado em task própria.
- Edição de exceções (apenas criar e excluir).
- Regras por profissional (`professional_id` existe no schema mas não é exposto na tela).
- Redesign visual da página além do necessário para rolagem e seleção.
- Histórico/auditoria de quem excluiu.

---

## 4. Áreas / arquivos impactados

### Backend (scheduler/)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/functions/availability/rules.py` | modificar | `delete_handler` (hard delete, escopado por clinic_id) + correção do except de `UniqueViolation` |
| `scheduler/src/functions/availability/exceptions.py` | modificar | `delete_handler` |
| `scheduler/sls/functions/availability/interface.yml` | modificar | Lambdas `DeleteAvailabilityRule` e `DeleteAvailabilityException` + rotas DELETE |
| `scheduler/src/scripts/setup_database.py` | modificar | Índice único parcial `uq_availability_rules_clinic_date` |

### Frontend (frontend/)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `frontend/src/services/availability.service.ts` | modificar | `deleteRule` com clinicId; novo `deleteException` |
| `frontend/src/hooks/useAvailabilityRules.ts` | modificar | Optimistic update + rollback; `useDeleteAvailabilityException` |
| `frontend/src/components/ui/ScrollArea.tsx` | criar | Container com altura máxima, rolagem e fade nas bordas |
| `frontend/src/pages/horarios/HorariosPage.tsx` | modificar | Wire-up geral; hoje concentra ~500 linhas e 4 modais |
| `frontend/src/pages/horarios/components/FixedDaysSection.tsx` | criar | Extração da seção de dias fixos + modo de seleção múltipla |
| `frontend/src/pages/horarios/components/ExceptionsSection.tsx` | criar | Extração da seção de exceções + ação de excluir |
| `frontend/src/components/ui/Toast.tsx` | criar (a confirmar) | Toast com ação de desfazer — só se ainda não existir |

### Tests / Mocks / Postman

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/tests/mocks/availability/delete_rule.json` | criar | Mock de evento DELETE de regra |
| `scheduler/tests/mocks/availability/delete_exception.json` | criar | Mock de evento DELETE de exceção |
| `scheduler/tests/integration/availability-delete.md` | criar | Casos de teste manuais via curl |
| `scheduler/tests/postman/availability-delete.postman_requests.json` | criar | Requests do fluxo create → list → delete → list |

---

## 5. Dependências e riscos

### Dependências

- **O frontend só funciona após o deploy do scheduler.** As rotas DELETE precisam estar publicadas antes do merge do frontend em produção, senão a tela troca uma falha silenciosa por outra.
- A migration do índice único roda pelo `setup_database.py`, já parte do fluxo de deploy.
- Sem dependência externa (z-api, OpenAI, Sheets não são tocados).

### Riscos

- **Duplicatas preexistentes de `rule_date` bloqueiam a migration.** Verificar antes de deployar; a Spec traz a query de checagem.
- **Hard delete é irreversível.** Mitigado pelo undo no cliente, que é uma janela curta e não cobre fechamento de aba. Aceito: uma regra de disponibilidade é barata de recriar, ao contrário de um paciente com histórico.
- **Undo otimista e o `chk_rule_type`/UNIQUE.** Se o usuário exclui uma regra recorrente, cadastra outra no mesmo dia e depois clica em "Desfazer", o recreate colide com o UNIQUE e retorna 409. O undo precisa tratar esse erro com mensagem clara, não falhar em silêncio.
- **Optimistic update e cache compartilhado.** `onMutate` precisa `cancelQueries` antes de mexer no cache, ou um refetch em voo restaura o item excluído. Erro clássico e a causa mais provável de "voltou sozinho".
- **Exclusão em lote com falha parcial.** Não pode reportar sucesso genérico se apenas parte dos DELETEs passou.
- **Excluir disponibilidade não valida agendamentos existentes.** Excluir a regra de uma data que já tem appointment marcado deixa o appointment órfão de disponibilidade. Comportamento atual do sistema (a criação também não valida), portanto não regride nada — mas merece aviso na UI quando a data tiver agendamentos. A Spec decide se cabe nesta task.
- **A UI sugere múltiplas faixas recorrentes por dia, o schema proíbe.** Não é introduzido por esta task, mas quem testar "+ Adicionar faixa" duas vezes no mesmo dia vai encontrar 409 e pode atribuir à mudança.

---

## 6. Critérios de aceite

### Backend

- [ ] `DELETE /clinics/{clinicId}/availability-rules/{ruleId}` retorna 200 e remove a linha.
- [ ] DELETE de regra de outra clínica retorna 404 (sem vazar existência).
- [ ] DELETE de regra inexistente retorna 404.
- [ ] `DELETE /clinics/{clinicId}/availability-exceptions/{exceptionId}` idem.
- [ ] Após excluir uma regra recorrente, é possível recriar outra no mesmo `day_of_week` sem 409 (valida a decisão de hard delete).
- [ ] Cadastrar data fixa duplicada (mesma data + mesmo start_time) retorna 409 com mensagem legível — não 500.
- [ ] Cadastrar duas faixas distintas na mesma data fixa continua funcionando.
- [ ] Migration idempotente: `setup_database.py` roda duas vezes seguidas sem erro.
- [ ] `GET /available-slots` reflete a exclusão imediatamente.

### Frontend

- [ ] As três seções respeitam altura máxima e rolam internamente; a página inteira não cresce sem limite.
- [ ] Com poucos itens, a lista não mostra área vazia nem scroll desnecessário.
- [ ] O corte de conteúdo é visualmente perceptível (fade), não um corte seco ambíguo.
- [ ] Excluir um horário remove o chip imediatamente, antes da resposta da API.
- [ ] Toast "Desfazer" restaura o item excluído.
- [ ] Falha na API faz o item reaparecer e mostra o erro.
- [ ] Seleção múltipla de datas fixas exclui todas as selecionadas; falha parcial é reportada com contagem.
- [ ] Exceções têm botão de excluir funcional.
- [ ] "Editar horário" não deixa mais o modal preso em loading, e nunca perde o horário em caso de falha.
- [ ] Nenhuma mutation da tela falha silenciosamente.
- [ ] Rolagem e seleção funcionam em tablet; touch targets ≥ 44px.
- [ ] `prefers-reduced-motion` respeitado nas animações de saída dos chips.

### QA geral

- [ ] `npm run lint` no frontend sem warnings.
- [ ] `npm run build` no frontend sem erros.
- [ ] Testes de hook: optimistic update, rollback em erro, undo.
- [ ] Postman executa create → list → delete → list-vazio.
- [ ] `tests/integration/availability-delete.md` cobre os casos acima.

---

## 7. Referências

- `Traffic-Manager/CLAUDE.md` — workflow e padrões
- `Traffic-Manager/frontend/CLAUDE.md` — React/TanStack Query e princípios Impeccable
- `docs/work/prd/008-patient-soft-delete.md` — precedente de rota DELETE escopada por clinicId; note o contraste soft vs hard delete
- `docs/work/prd/002-fix-availability-bugs.md` — histórico de bugs no mesmo módulo
- `scheduler/src/scripts/setup_database.py:253` — `uq_availability_rules_clinic_day`, restrição central desta task
- `frontend/src/pages/horarios/HorariosPage.tsx` — tela atual
- https://traffic-manager-eight.vercel.app/horarios — produção

---

## Status (preencher após conclusão)

- [x] Pendente
- [x] Spec gerada: `spec/009-horarios-delete-scroll.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
