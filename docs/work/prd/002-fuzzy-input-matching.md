# PRD — 002 Fuzzy Input Matching

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Melhorar o `_identify_input` do `ConversationEngine` para que texto digitado pelo usuario seja comparado contra os labels dos botoes disponiveis no estado atual usando substring matching (estilo SQL `LIKE '%texto%'`), substituindo os arrays de keywords hardcoded. Tambem reintegrar a extracao de valores de botoes dinamicos (`day_`, `time_`, `faq_`, etc.) no fluxo `process_message`, que foi removida.

---

## 2. Contexto

Atualmente, `_identify_input` usa arrays fixos de keywords para mapear texto digitado a acoes (ex: `text in ("voltar", "back", "0")`). Isso e fragil:
- Nao escala quando novos botoes sao adicionados
- Nao reconhece variacoes naturais que o usuario pode digitar (ex: "quero agendar", "duvida", "preco")
- Requer manutencao manual dos arrays a cada mudanca de label

O matching por substring contra os labels dos botoes resolve isso de forma generica e auto-mantida.

Alem disso, o metodo `_extract_dynamic_selection` foi removido do `process_message` (antigo step 3.5), mas o helper `_extract_selection_from_input` existe sem ser chamado. Sem essa extracao, selecoes dinamicas (datas, horarios, FAQs) nao populam a session corretamente.

---

## 3. Escopo

### Dentro do escopo
- Substituir keyword arrays em `_identify_input` por fuzzy matching contra botoes do estado atual
- Manter atalhos globais ("back"/"voltar", "menu", "human") como fallbacks que funcionam em qualquer estado
- Reintegrar extracao de valores dinamicos (`day_`, `time_`, `newday_`, `newtime_`, `faq_`) no `process_message`
- Manter matching numerico (usuario digita "1", "2", etc.)

### Fora do escopo
- NLP ou IA para matching semantico
- Alteracoes nos templates ou labels dos botoes
- Alteracoes em outros services

---

## 4. Areas / arquivos impactados

| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `scheduler/src/services/conversation_engine.py` | modificar | `_identify_input`: fuzzy matching; `process_message`: reintegrar extracao dinamica |

---

## 5. Dependencias e riscos

- **Dependencias:** Nenhuma externa. Apenas logica interna ao `conversation_engine.py`.
- **Riscos:**
  - Substring ambiguo: usuario digita "sessao" e bate em multiplos botoes (ex: "Agendar sessao", "Remarcar sessao"). Mitigacao: so resolver se houver exatamente 1 match.
  - Labels com acentos vs texto sem acento: labels atuais ja estao sem acento, entao nao e problema imediato.

---

## 6. Criterios de aceite

- [ ] Usuario digita "agendar" no MAIN_MENU -> resolve para `schedule` (match em "Agendar sessao")
- [ ] Usuario digita "remarcar" no MAIN_MENU -> resolve para `reschedule`
- [ ] Usuario digita "duvida" no MAIN_MENU -> resolve para `faq`
- [ ] Usuario digita "sessao" no MAIN_MENU -> NAO resolve (ambiguo, bate em 3 botoes) -> retorna texto raw
- [ ] Usuario digita "preco" no SCHEDULE_MENU -> resolve para `price_table` (match em "Ver tabela de precos")
- [ ] Atalhos globais continuam funcionando: "voltar", "menu", "oi", "humano"
- [ ] Matching numerico continua funcionando: "1", "2", "3"
- [ ] Selecoes dinamicas (day_, time_, faq_, etc.) continuam populando a session corretamente
- [ ] Button clicks (incoming.button_id) continuam com prioridade maxima

---

## 7. Referencias

- `CLAUDE.md` (padroes do projeto)
- `scheduler/src/services/conversation_engine.py` (arquivo alvo)

---

## Status (preencher apos conclusao)

- [x] Pendente
- [x] Spec gerada: `spec/002-fuzzy-input-matching.md`
- [x] Implementado em: 2026-02-07
- [ ] Registrado em `TASKS_LOG.md`
