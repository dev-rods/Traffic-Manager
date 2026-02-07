# PRD — 005 Melhoria no matching de opcoes FAQ no fluxo de conversa

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Garantir que as opcoes do menu de FAQ (ex: "Qual equipamento voces usam?") sejam corretamente interpretadas independentemente de como o usuario digita a resposta — com ou sem acentos, pontuacao, variacao de texto, ou digitacao parcial.

---

## 2. Contexto

Ao navegar pelas opcoes de "Duvidas sobre sessao" (FAQ_MENU), a opcao "Qual equipamento voces usam?" nao foi corretamente interpretada. O problema esta no fuzzy matching do `_identify_input` que e muito simplista:

```python
# Linha 334-337 de conversation_engine.py
matches = [btn for btn in buttons if text in btn.get("label", "").lower()]
if len(matches) == 1:
    return matches[0]["id"]
```

**Falhas identificadas:**

1. **Sem normalizacao de acentos** — Se o label e "Qual equipamento voces usam?" (sem acento) e o usuario digita "vocês" (com cedilha), o substring match falha. O inverso tambem.

2. **Dependencia de match unico** — Se o texto do usuario for substring de mais de um label (ex: "como" aparece em "Como funcionam as datas?" e "Como funciona o pagamento?"), `len(matches) != 1` e o matching falha silenciosamente.

3. **Sem tolerancia a variacao** — O usuario pode digitar "equipamento laser", "qual equipamento", ou outras variacoes que nao sao substring exato do label.

4. **Colisao de prefixo `faq_`** — O botao `faq_menu` (em FAQ_ANSWER, linha 199) colide com o prefixo `faq_` usado em `_extract_dynamic_selection`, causando extracao falsa: `session["selected_faq_key"] = "menu"`.

5. **Fallback para UNRECOGNIZED** — Quando o matching falha no FAQ_MENU, o sistema mostra mensagem de nao reconhecido ao inves de tentar um match mais inteligente ou re-exibir o menu.

---

## 3. Escopo

### Dentro do escopo
- Criar funcao `_normalize_text()` que remove acentos/diacriticos, pontuacao e normaliza espacos
- Aplicar normalizacao no fuzzy matching de `_identify_input` (tanto no input quanto nos labels)
- Adicionar scoring por sobreposicao de palavras como fallback quando substring exato falha
- Renomear botao `faq_menu` para `go_faq_menu` para evitar colisao com prefixo `faq_`
- Atualizar transicoes e referencias ao antigo ID `faq_menu`

### Fora do escopo
- Integracao com NLP/AI para interpretacao de texto livre
- Alteracao no formato de armazenamento de FAQ items no banco
- Alteracao na z-api ou no provider de WhatsApp
- Adicionar novas FAQ items

---

## 4. Areas / arquivos impactados

| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `scheduler/src/services/conversation_engine.py` | modificar | Adicionar `_normalize_text()`, melhorar fuzzy matching em `_identify_input`, renomear `faq_menu` para `go_faq_menu` em STATE_CONFIG |

---

## 5. Dependencias e riscos

- **Dependencias:** `unicodedata` da stdlib Python (para normalizacao de acentos). Nenhuma dependencia externa.
- **Riscos:** Baixo. As mudancas sao retrocompativeis — o matching por numero (digitacao de "1", "2", etc.) e por button_id (clique de botao) continuam funcionando normalmente. O fuzzy matching melhora apenas o fallback de texto livre.

---

## 6. Criterios de aceite

- [ ] Texto com acentos (ex: "vocês") faz match com label sem acento (ex: "voces") e vice-versa
- [ ] Texto parcial que identifica uniquamente um botao faz match (ex: "equipamento" → faq_EQUIPMENT)
- [ ] Texto ambiguo (ex: "como") que aparece em multiplos labels NAO faz match incorreto (retorna texto as-is)
- [ ] Botao `faq_menu` renomeado para `go_faq_menu` sem quebrar transicoes
- [ ] `_extract_dynamic_selection` nao extrai falsamente quando input e `go_faq_menu`
- [ ] Match por numero continua funcionando (ex: "1" → primeiro botao)
- [ ] Match por button_id (clique de botao z-api) continua funcionando
- [ ] Pontuacao ignorada no matching (ex: "equipamento?" == "equipamento")

---

## 7. Referencias

- `CLAUDE.md` (padroes do projeto)
- `scheduler/src/services/conversation_engine.py` (conversation engine — linhas 301-340, 824-839)
- PRD `002-fuzzy-input-matching.md` (feature original de fuzzy matching)

---

## Status (preencher apos conclusao)

- [x] Pendente
- [x] Spec gerada: `spec/005-faq-fuzzy-matching.md`
- [x] Implementado em: 2026-02-07
- [ ] Registrado em `TASKS_LOG.md`
