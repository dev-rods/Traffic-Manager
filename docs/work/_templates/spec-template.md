# Spec — [ID] Nome da Task

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/XXX-nome-da-task.md`

---

## 1. Resumo

(1 parágrafo: o que será implementado e em quais partes do projeto.)

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `infra/src/...` | … |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `infra/src/...` | Adicionar X; alterar função Y em Z; … |
| `infra/sls/...` | … |

---

## 4. Arquivos a remover (se aplicável)

| Arquivo | Motivo |
|---------|--------|
| `...` | … |

---

## 5. Ordem de implementação sugerida

1. 
2. 
3. 

---

## 6. Detalhes por arquivo

### `caminho/do/arquivo.py`

- **Criar** / **Modificar** / **Remover**
- (Bullets com o que fazer: funções, classes, imports, configs.)

### `outro/arquivo.yml`

- …

---

## 7. Convenções a respeitar

- Logging: `[traceId: {trace_id}]` (ver `CLAUDE.md`)
- Naming: client IDs kebab-case; Lambdas PascalCase; handlers como em `serverless.yml`
- Secrets: SSM `/${stage}/KEY`; credenciais com Fernet em DynamoDB
