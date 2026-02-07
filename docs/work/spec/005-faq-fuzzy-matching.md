# Spec — 005 Melhoria no matching de opcoes FAQ no fluxo de conversa

> Gerado na fase **Spec**. Use como input para a fase Code (implementacao).

- **PRD de origem:** `prd/005-faq-fuzzy-matching.md`

---

## 1. Resumo

Melhorar o fuzzy matching em `conversation_engine.py` para que opcoes de FAQ (e qualquer botao dinamico) sejam corretamente interpretadas mesmo quando o usuario digita texto com acentos, pontuacao ou variacoes. Adicionar normalizacao de texto (remocao de diacriticos e pontuacao) e scoring por sobreposicao de palavras. Renomear botao `faq_menu` para `go_faq_menu` para evitar colisao com prefixo `faq_` da extracao dinamica.

---

## 2. Arquivos a criar

Nenhum.

---

## 3. Arquivos a modificar

| Arquivo | Alteracoes |
|---------|------------|
| `scheduler/src/services/conversation_engine.py` | Adicionar `import unicodedata`; adicionar metodo `_normalize_text`; reescrever bloco de fuzzy matching em `_identify_input`; renomear `faq_menu` para `go_faq_menu` em STATE_CONFIG |

---

## 4. Arquivos a remover (se aplicavel)

Nenhum.

---

## 5. Ordem de implementacao sugerida

1. Adicionar `import unicodedata` nos imports (linha 1-8)
2. Adicionar metodo statico `_normalize_text()` na classe ConversationEngine (proximo aos outros helpers, ~linha 773)
3. Reescrever bloco de fuzzy matching em `_identify_input` (linhas 333-337)
4. Renomear `faq_menu` para `go_faq_menu` em STATE_CONFIG (linhas 199, 203)

---

## 6. Detalhes por arquivo

### `scheduler/src/services/conversation_engine.py`

#### 6.1 Import (linha 1)

- Adicionar: `import unicodedata` (junto aos imports da stdlib, antes de `os`)

#### 6.2 Helper `_normalize_text` (novo metodo statico na classe ConversationEngine)

Adicionar proximo aos outros helpers estaticos (~linha 773, junto a `_format_date_br`):

```python
@staticmethod
def _normalize_text(text: str) -> str:
    """Normalize text for fuzzy comparison: lowercase, strip accents and punctuation."""
    text = text.lower().strip()
    # Remove diacritics (accents): NFD decomposes, then strip combining marks
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove punctuation (keep alphanumeric and spaces)
    text = "".join(c for c in text if c.isalnum() or c.isspace())
    # Normalize whitespace
    text = " ".join(text.split())
    return text
```

- Remove acentos: "vocês" → "voces", "sessão" → "sessao"
- Remove pontuacao: "usam?" → "usam"
- Normaliza espacos: "  qual   equipamento  " → "qual equipamento"
- Lowercase: "Qual" → "qual"

#### 6.3 Reescrever fuzzy matching em `_identify_input` (linhas 333-337)

**Antes (atual):**
```python
        # Fuzzy label matching — LIKE '%text%' against button labels
        if buttons and text:
            matches = [btn for btn in buttons if text in btn.get("label", "").lower()]
            if len(matches) == 1:
                return matches[0]["id"]
```

**Depois (novo):**
```python
        # Fuzzy label matching — normalized substring + word overlap
        if buttons and text:
            normalized_input = self._normalize_text(text)
            normalized_buttons = [
                (btn, self._normalize_text(btn.get("label", "")))
                for btn in buttons
            ]

            # 1st pass: normalized substring (input in label OR label in input)
            substr_matches = [
                btn for btn, norm_label in normalized_buttons
                if normalized_input in norm_label or norm_label in normalized_input
            ]
            if len(substr_matches) == 1:
                return substr_matches[0]["id"]

            # 2nd pass: word overlap scoring (>= 50% of input words match)
            if not substr_matches or len(substr_matches) > 1:
                input_words = set(normalized_input.split())
                if input_words:
                    scored = []
                    for btn, norm_label in normalized_buttons:
                        label_words = set(norm_label.split())
                        overlap = len(input_words & label_words)
                        score = overlap / len(input_words)
                        if score >= 0.5:
                            scored.append((btn, score))
                    # Pick best match only if it is unambiguous (clear winner)
                    if scored:
                        scored.sort(key=lambda x: x[1], reverse=True)
                        if len(scored) == 1 or scored[0][1] > scored[1][1]:
                            return scored[0][0]["id"]
```

**Logica:**
1. **1st pass (substring normalizado):** Normaliza input e labels, faz match bidirecional (`input in label` OU `label in input`). Se houver exatamente 1 match, retorna.
2. **2nd pass (word overlap):** Se substring falha (0 ou multiplos matches), calcula sobreposicao de palavras. Seleciona apenas se houver um vencedor claro (score unico maximo, com >= 50% das palavras do input presentes no label).

**Exemplos de matching:**
| Input do usuario | Label do botao | 1st pass | 2nd pass | Resultado |
|---|---|---|---|---|
| "qual equipamento vocês usam?" | "Qual equipamento voces usam?" | ✅ norm: "qual equipamento voces usam" in "qual equipamento voces usam" | — | faq_EQUIPMENT |
| "equipamento" | "Qual equipamento voces usam?" | ✅ "equipamento" in "qual equipamento voces usam" | — | faq_EQUIPMENT (unico) |
| "como" | "Como funcionam as datas?" + "Como funciona o pagamento?" | ❌ 2 matches | score igual → ambiguo | sem match (retorna texto) |
| "pagamento" | "Como funciona o pagamento?" | ✅ "pagamento" in "como funciona o pagamento" | — | faq_PAYMENT |
| "intervalo sessoes" | "Qual o intervalo entre sessoes?" | ❌ nao e substring | ✅ 2/2 words = 100% | faq_SESSION_INTERVAL |

#### 6.4 Renomear `faq_menu` para `go_faq_menu` em STATE_CONFIG (linhas 196-208)

**Antes:**
```python
    ConversationState.FAQ_ANSWER: {
        "template_key": None,  # Content from FAQ
        "buttons": [
            {"id": "faq_menu", "label": "Outras duvidas"},
            {"id": "main_menu", "label": "Menu principal"},
        ],
        "transitions": {
            "faq_menu": ConversationState.FAQ_MENU,
            "main_menu": ConversationState.MAIN_MENU,
        },
```

**Depois:**
```python
    ConversationState.FAQ_ANSWER: {
        "template_key": None,  # Content from FAQ
        "buttons": [
            {"id": "go_faq_menu", "label": "Outras duvidas"},
            {"id": "main_menu", "label": "Menu principal"},
        ],
        "transitions": {
            "go_faq_menu": ConversationState.FAQ_MENU,
            "main_menu": ConversationState.MAIN_MENU,
        },
```

- `faq_menu` → `go_faq_menu` em 2 pontos: botao id e chave de transitions
- Evita que `_extract_dynamic_selection` extraia falsamente `session["selected_faq_key"] = "menu"` quando o usuario clica "Outras duvidas"

---

## 7. Convencoes a respeitar

- Logging: manter o log existente em `_extract_dynamic_selection`; nao adicionar logs adicionais no fuzzy matching (evitar verbosidade)
- Naming: metodos privados com prefixo `_`; helper statico pois nao depende de estado da instancia
- Imports: `unicodedata` e stdlib, colocar junto aos imports de stdlib existentes (linha 1-8)
- Nao alterar o comportamento de match por numero (linhas 328-331) nem por button_id (linhas 302-304)
