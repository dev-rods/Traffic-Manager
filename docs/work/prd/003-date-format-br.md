# PRD — 003 Formatacao de datas no padrao brasileiro (DD/MM/YYYY)

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Formatar todas as datas exibidas ao usuario no fluxo de agendamento do WhatsApp no padrao brasileiro DD/MM/YYYY, substituindo o formato atual YYYY-MM-DD.

---

## 2. Contexto

Atualmente, as datas apresentadas nas mensagens do chatbot (dias disponiveis, confirmacao de agendamento, remarcacao) utilizam o formato ISO YYYY-MM-DD, que nao e familiar para usuarios brasileiros. Datas devem ser exibidas como DD/MM/YYYY para melhor experiencia do usuario.

Os dados internos (session, btn_id, chamadas de API) devem continuar usando YYYY-MM-DD para manter compatibilidade com o banco de dados e a availability_engine.

---

## 3. Escopo

### Dentro do escopo
- Formatar datas de exibicao (labels de botoes, listas de texto, variaveis de template) para DD/MM/YYYY
- Fluxo de agendamento: AVAILABLE_DAYS, SELECT_TIME, CONFIRM_BOOKING, BOOKED
- Fluxo de remarcacao: RESCHEDULE_FOUND (botoes de dias), SELECT_NEW_TIME, CONFIRM_RESCHEDULE, RESCHEDULED

### Fora do escopo
- Alterar formato de armazenamento interno (session, banco, btn_id permanecem YYYY-MM-DD)
- Alterar formato de datas vindas do banco (appointment_date via RDS)
- Templates customizados no banco (apenas o rendering no conversation_engine)

---

## 4. Areas / arquivos impactados

| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `scheduler/src/services/conversation_engine.py` | modificar | Formatar datas em _on_enter_available_days, _on_enter_select_time, _on_enter_confirm_booking, _on_enter_booked, _on_enter_reschedule_lookup, _on_enter_select_new_time, _on_enter_confirm_reschedule, _on_enter_rescheduled |

---

## 5. Dependencias e riscos

- **Dependencias:** Nenhuma nova dependencia. `datetime` da stdlib Python.
- **Riscos:** Datas vindas do banco (appointment_date) podem ter formato date object ou string; necessario tratar ambos os casos.

---

## 6. Criterios de aceite

- [ ] Botoes de dias disponiveis exibem DD/MM/YYYY (btn label), mas btn_id mantem YYYY-MM-DD
- [ ] Lista textual de dias (days_list) usa DD/MM/YYYY
- [ ] Template SELECT_TIME exibe data em DD/MM/YYYY
- [ ] Template CONFIRM_BOOKING exibe data em DD/MM/YYYY
- [ ] Template BOOKED exibe data em DD/MM/YYYY
- [ ] Fluxo de remarcacao exibe datas em DD/MM/YYYY (RESCHEDULE_FOUND botoes, SELECT_NEW_TIME, CONFIRM_RESCHEDULE, RESCHEDULED)
- [ ] Dados internos (session, API calls) continuam usando YYYY-MM-DD

---

## 7. Referencias

- `CLAUDE.md` (padroes do projeto)
- `scheduler/src/services/template_service.py` (templates com {{date}})

---

## Status (preencher apos conclusao)

- [x] Pendente
- [x] Spec gerada: `spec/003-date-format-br.md`
- [x] Implementado em: 2026-02-07
- [ ] Registrado em `TASKS_LOG.md`
