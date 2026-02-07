# PRD — 002 Fix Availability Bugs

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Corrigir dois bugs que impedem o fluxo de agendamento via WhatsApp de funcionar corretamente. O bug principal faz com que o usuario sempre receba "Nenhum horario disponivel" ao selecionar uma data, mesmo quando existem horarios disponiveis. O segundo bug faz com que regras de disponibilidade de domingo nunca sejam encontradas pelo motor de disponibilidade.

---

## 2. Contexto

Durante testes do fluxo de agendamento (SCHEDULE_MENU -> AVAILABLE_DAYS -> SELECT_TIME), ao clicar em uma data disponivel (botao `day_YYYY-MM-DD`), o sistema transiciona para o estado SELECT_TIME mas sempre retorna "Nenhum horario disponivel". A causa raiz sao dois bugs independentes:

**Bug 1 — Valores de selecao dinamica nunca extraidos dos button IDs:**
Quando o usuario clica um botao dinamico como `day_2025-02-10`, o `_resolve_transition` faz a transicao de estado corretamente, mas ninguem extrai `"2025-02-10"` do ID do botao e armazena em `session["selected_date"]`. O metodo `_on_enter_select_time` le `session.get("selected_date", "")` → sempre vazio → nunca chama o availability engine → retorna lista vazia.

O mesmo problema afeta: `selected_time`, `selected_new_date`, `selected_new_time` e `selected_faq_key`. Existe um helper `_extract_selection_from_input()` (linha 805) que foi criado para isso mas nunca foi conectado ao fluxo.

**Bug 2 — Mismatch de `day_of_week` para domingo:**
A API de regras (`rules.py`) valida `day_of_week` no range 0-6 com `DAY_NAMES[0] = "Domingo"` (0=Domingo). Porem o availability engine usa `dt.isoweekday()` que retorna 1-7 (Domingo=7). Regras de domingo sao armazenadas como `day_of_week=0` mas consultadas com valor `7` — nunca fazem match.

---

## 3. Escopo

### Dentro do escopo
- Extrair valores de botoes dinamicos (`day_`, `time_`, `newday_`, `newtime_`, `faq_`) e armazenar na sessao
- Corrigir calculo de `day_of_week` no availability engine para alinhar com convencao da API (0=Domingo)
- Ambas as correcoes nos fluxos de agendamento e remarcacao

### Fora do escopo
- Tratamento de timezone (usa `date.today()` do servidor)
- Otimizacao de performance do `get_available_days()` (N queries por dia)
- Tratamento de multiplas SPECIAL_HOURS exceptions no mesmo dia
- Validacao de input silenciosa em `_time_to_minutes()`

---

## 4. Areas / arquivos impactados

| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `scheduler/src/services/conversation_engine.py` | modificar | Adicionar extracao de valores de botoes dinamicos para sessao |
| `scheduler/src/services/availability_engine.py` | modificar | Corrigir calculo de `day_of_week` com `% 7` (2 locais) |

---

## 5. Dependencias e riscos

- **Dependencias:** Nenhuma nova. Usa apenas codigo existente.
- **Riscos:**
  - Se existirem regras de disponibilidade criadas com convencao ISO (1-7) em vez de 0-6, a correcao do `day_of_week` poderia quebrar. Verificar dados existentes no banco.
  - O prefixo `faq_` na extracao armazena a key sem o prefixo, enquanto `_on_enter_faq_answer` faz `replace("faq_", "")`. Confirmar que nao ha dupla remocao do prefixo.

---

## 6. Criterios de aceite

- [ ] Ao clicar em uma data disponivel, o sistema exibe horarios disponiveis (nao "Nenhum horario disponivel")
- [ ] `session["selected_date"]` contem o valor correto apos clicar `day_YYYY-MM-DD`
- [ ] `session["selected_time"]` contem o valor correto apos clicar `time_HH:MM`
- [ ] Fluxo de remarcacao funciona: `selected_new_date` e `selected_new_time` extraidos
- [ ] `selected_faq_key` extraido corretamente de botoes `faq_`
- [ ] Regras de disponibilidade de domingo (day_of_week=0) sao encontradas corretamente
- [ ] Dias de segunda a sabado continuam funcionando (nao ha regressao)

---

## 7. Referencias

- `CLAUDE.md` (padroes do projeto)
- `scheduler/src/services/conversation_engine.py` — state machine e fluxo de conversa
- `scheduler/src/services/availability_engine.py` — motor de disponibilidade
- `scheduler/src/functions/availability/rules.py` — API de regras (convencao day_of_week)

---

## Status (preencher apos conclusao)

- [x] Pesquisa concluida
- [x] Spec gerada: `spec/002-fix-availability-bugs.md`
- [x] Implementado em: 2026-02-07
- [x] Registrado em `TASKS_LOG.md`
