# Spec — 002 Fix Availability Bugs

> Gerado na fase **Spec**. Use como input para a fase Code (implementacao).

- **PRD de origem:** `prd/002-fix-availability-bugs.md`

---

## 1. Resumo

Corrigir dois bugs no scheduler que impedem o fluxo de agendamento: (1) valores de selecao dinamica (data, horario, FAQ) nunca sao extraidos dos button IDs para a sessao, fazendo com que `_on_enter_select_time` sempre retorne "Nenhum horario disponivel"; (2) calculo de `day_of_week` usa `isoweekday()` (Domingo=7) mas o banco armazena Domingo=0, quebrando disponibilidade aos domingos.

---

## 2. Arquivos a criar

| Arquivo | Descricao |
|---------|-----------|
| Nenhum | — |

---

## 3. Arquivos a modificar

| Arquivo | Alteracoes |
|---------|------------|
| `scheduler/src/services/conversation_engine.py` | Adicionar metodo `_extract_dynamic_selection()`; chamar no `process_message` entre steps 3 e 4 |
| `scheduler/src/services/availability_engine.py` | Alterar `day_of_week = dt.isoweekday()` para `dt.isoweekday() % 7` em 2 locais |

---

## 4. Arquivos a remover (se aplicavel)

| Arquivo | Motivo |
|---------|--------|
| Nenhum | — |

---

## 5. Ordem de implementacao sugerida

1. `availability_engine.py` — corrigir `day_of_week` (mudanca isolada, sem dependencias)
2. `conversation_engine.py` — adicionar `_extract_dynamic_selection()` e chamar em `process_message`

---

## 6. Detalhes por arquivo

### `scheduler/src/services/availability_engine.py`

- **Modificar** metodo `get_available_slots()` (linha 37):
  - De: `day_of_week = dt.isoweekday()  # 1=Monday, 7=Sunday`
  - Para: `day_of_week = dt.isoweekday() % 7  # 0=Sunday, 1=Monday, ..., 6=Saturday`
  - Atualizar comentario da linha 34 para refletir convencao correta

- **Modificar** metodo `get_available_slots_for_areas()` (linha 154):
  - De: `day_of_week = dt.isoweekday()`
  - Para: `day_of_week = dt.isoweekday() % 7  # 0=Sunday, 1=Monday, ..., 6=Saturday`

### `scheduler/src/services/conversation_engine.py`

- **Adicionar** metodo `_extract_dynamic_selection(self, user_input: str, session: dict) -> None` na classe `ConversationEngine`, proximo ao helper existente `_extract_selection_from_input` (linha 805):
  - Mapa de prefixos para session keys:
    - `"day_"` → `"selected_date"` (ex: `day_2025-02-10` → `session["selected_date"] = "2025-02-10"`)
    - `"time_"` → `"selected_time"` (ex: `time_14:00` → `session["selected_time"] = "14:00"`)
    - `"newday_"` → `"selected_new_date"`
    - `"newtime_"` → `"selected_new_time"`
    - `"faq_"` → `"selected_faq_key"` (ex: `faq_preco` → `session["selected_faq_key"] = "preco"`)
  - Iterar sobre o mapa; ao encontrar match com `startswith`, extrair o valor apos o prefixo e armazenar na session key correspondente
  - Log com `logger.info` seguindo padrao `[ConversationEngine]`

- **Modificar** metodo `process_message()` (entre linhas 278-280):
  - Inserir chamada `self._extract_dynamic_selection(user_input, session)` entre o log de transicao (step 3) e o bloco de `on_enter` (step 4)
  - Adicionar comentario `# 3.5 Extract values from dynamic button IDs into session`

- **Nota sobre `faq_`**: `_on_enter_faq_answer` (linha 700) ja faz `replace("faq_", "")` como safety. Com a extracao removendo o prefixo, o replace sera um no-op — comportamento correto, sem dupla remocao.

---

## 7. Convencoes a respeitar

- Logging: `[ConversationEngine]` prefix (padrao existente no arquivo)
- Naming: metodos privados com `_` prefix (padrao existente)
- Sem novas dependencias ou imports
- Manter compatibilidade com botoes estaticos (que nao tem prefixo dinamico)
