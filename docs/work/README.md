# Workflow de Desenvolvimento — Research → Spec → Code

Este diretório concentra o processo em **3 etapas** para implementar tasks, refatorar e documentar mudanças no Traffic Manager.

---

## 1. Pesquisa (Research) → PRD

**Input (você):**  
> "Preciso implementar X" / "Quero refatorar Y" / "Eliminar o código Z"

**O que o Claude faz:**
- Pesquisa a base de código (`infra/src/`, `infra/sls/`, etc.)
- Consulta documentação existente (`infra/docs/`, `CLAUDE.md`)
- Identifica padrões, dependências e onde a mudança se encaixa

**Output:** `prd/XXX-nome-da-task.md` (Product Requirements Document)

**Conteúdo típico do PRD:**
- Objetivo e contexto
- Escopo (o que entra e o que fica de fora)
- Arquivos/áreas impactados
- Dependências e riscos
- Critérios de aceite

---

## 2. Especificação (Spec) → Spec

**Input (você):**  
> "Leia o PRD `prd/XXX-nome-da-task.md` e gere uma spec"

**O que o Claude faz:**
- Lê o PRD
- Lista **arquivos a criar** e **arquivos a modificar**
- Detalha **o que** deve ser criado/alterado em cada um
- Ordena passos de implementação

**Output:** `spec/XXX-nome-da-task.md`

**Conteúdo típico da Spec:**
- Lista de arquivos (criar | modificar | remover)
- Alterações por arquivo (funções, classes, configs)
- Ordem de implementação sugerida

---

## 3. Implementação (Code)

**Input (você):**  
> "Implemente a spec `spec/XXX-nome-da-task.md`"

**O que o Claude faz:**
- Lê a Spec
- Implementa com janela de contexto livre (pode abrir os arquivos necessários)
- Mantém padrões do projeto (`CLAUDE.md`, logging, naming)

**Output:** Código aplicado no repositório.

---

## Convenção de nomes

Use um identificador único por task:

- `001` — primeira task
- `002` — segunda, etc.

Ou por tema: `001-refator-auth`, `002-remove-legacy-x`, `003-feature-y`.

- PRD: `prd/001-nome-da-task.md`
- Spec: `spec/001-nome-da-task.md`

Assim PRD e Spec da mesma task ficam fáceis de cruzar.

---

## Documentar tarefas realizadas

Após concluir uma task (fase Code):

1. **No PRD:** adicione no final, por exemplo:
   ```markdown
   ## Status
   - [x] Concluído em 2025-01-24
   - Spec: `spec/001-nome-da-task.md`
   - Commits / PR: (link ou hash se aplicável)
   ```

2. **No `TASKS_LOG.md` (raiz do projeto):** registre uma linha com:
   - ID, título, data, e 1–2 frases do que foi feito.

Isso mantém histórico rastreável e documentação alinhada ao código.

---

## Uso em uma sessão

Você pode rodar as 3 fases em sequência na mesma sessão:

1. "Preciso implementar X" → Claude gera `prd/001-x.md`
2. "Gere a spec a partir de `prd/001-x.md`" → Claude gera `spec/001-x.md`
3. "Implemente `spec/001-x.md`" → Claude altera o código

Ou em sessões diferentes: a Spec e o PRD servem como handoff entre conversas.
