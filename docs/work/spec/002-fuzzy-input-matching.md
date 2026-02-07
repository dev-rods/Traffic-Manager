# Spec — 002 Fuzzy Input Matching

> Gerado na fase **Spec**. Use como input para a fase Code (implementacao).

- **PRD de origem:** `prd/002-fuzzy-input-matching.md`

---

## 1. Resumo

Modificar `_identify_input` em `conversation_engine.py` para usar substring matching (LIKE '%text%') contra os labels dos botoes do estado atual, substituindo arrays de keywords hardcoded. Reintegrar extracao de valores dinamicos no `process_message`.

---

## 2. Arquivos a criar

Nenhum.

---

## 3. Arquivos a modificar

| Arquivo | Alteracoes |
|---------|------------|
| `scheduler/src/services/conversation_engine.py` | Refatorar `_identify_input`; reintegrar extracao dinamica em `process_message` |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementacao sugerida

1. Reintegrar extracao de valores dinamicos no `process_message` (entre steps 3 e 4)
2. Refatorar `_identify_input` para adicionar fuzzy matching contra labels dos botoes

---

## 6. Detalhes por arquivo

### `scheduler/src/services/conversation_engine.py`

#### 6.1 — `process_message`: reintegrar extracao dinamica

Adicionar chamada para extrair valores de selecoes dinamicas entre a resolucao de estado (step 3) e o `_on_enter` (step 4):

```python
# Entre step 3 e step 4, adicionar:
self._extract_dynamic_selection(user_input, session)
```

Renomear `_extract_selection_from_input` de volta para `_extract_dynamic_selection` e restaurar a logica completa com o mapa de prefixos:

```python
PREFIX_TO_KEY = {
    "day_": "selected_date",
    "time_": "selected_time",
    "newday_": "selected_new_date",
    "newtime_": "selected_new_time",
    "faq_": "selected_faq_key",
}
```

#### 6.2 — `_identify_input`: fuzzy matching

Manter a ordem de prioridade atual, adicionando fuzzy matching apos o check numerico:

1. **Button ID** (prioridade maxima) — `incoming.button_id`
2. **Atalhos globais** — "voltar"/"back"/"0" -> `"back"`; "menu"/"oi"/etc -> `"main_menu"`; "humano"/etc -> `"human"` — SUBSTITUIR arrays hardcoded por substring match contra labels dos botoes, mas manter atalhos globais que nao sao labels (ex: "oi", "ola", "hi", "0")
3. **Numerico** — "1" -> botoes[0]["id"]
4. **Fuzzy label match (NOVO)** — `text in label.lower()` para cada botao. So resolve se exatamente 1 match.
5. **Free text** — retorna raw

Logica do fuzzy match:
```python
if buttons and text:
    matches = [btn for btn in buttons if text in btn.get("label", "").lower()]
    if len(matches) == 1:
        return matches[0]["id"]
```

---

## 7. Convencoes a respeitar

- Logging: `[ConversationEngine]` prefix (padrao existente)
- Nao adicionar dependencias externas
- Manter compatibilidade com todos os estados da state machine
