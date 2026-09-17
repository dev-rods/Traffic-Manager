# TASKS_LOG — Registro de tarefas realizadas

Registro curto das tasks feitas com o workflow **Research → Spec → Code**.  
Use para rastrear o que foi implementado, refatorado ou removido.

---

## Formato de cada entrada

```text
- **[ID]** Título da task (YYYY-MM-DD) — 1–2 frases do que foi feito. PRD: `prd/ID-nome.md`, Spec: `spec/ID-nome.md`.
```

---

## Histórico

- **000** Setup do workflow Research → Spec → Code (2025-01-24) — Criada a estrutura `docs/work/` (prd/, spec/, _templates/), `docs/work/README.md`, templates de PRD e Spec, atualizado `CLAUDE.md` com a tabela do workflow e criado `TASKS_LOG.md`. PRD: N/A, Spec: N/A.

- **002** Fix Availability Bugs (2026-02-07) — Corrigido bug critico onde valores de botoes dinamicos (day_, time_, newday_, newtime_, faq_) nunca eram extraidos para a sessao, causando "Nenhum horario disponivel" mesmo com horarios disponiveis. Corrigido mismatch de day_of_week para domingo (0 vs 7). PRD: `prd/002-fix-availability-bugs.md`, Spec: `spec/002-fix-availability-bugs.md`.

- **003** Date Format BR DD/MM/YYYY (2026-02-07) — Formatacao de todas as datas exibidas ao usuario no padrao brasileiro DD/MM/YYYY (antes YYYY-MM-DD). Adicionado helper `_format_date_br` que aceita string e date objects. Aplicado em 10 pontos: botoes de dias, listas textuais e variaveis de template nos fluxos de agendamento e remarcacao. Dados internos (btn_id, session, API) permanecem YYYY-MM-DD. PRD: `prd/003-date-format-br.md`, Spec: `spec/003-date-format-br.md`.

- **004** Gestao Unificada de Leads com GCLID (2026-03-01, dev-andre) — Implementada tabela `scheduler.leads` no PostgreSQL para rastrear leads de todas as origens (WhatsApp e formulario do site), conectando telefone ao GCLID do Google Ads. O webhook do WhatsApp extrai automaticamente o GCLID da mensagem `(ref: GCLID)` enviada pelo botao flutuante do site e faz upsert do lead (unique por phone+clinic_id). Quando um agendamento e criado, o lead e automaticamente marcado como `booked=TRUE` com o valor do primeiro agendamento. Objetivo: permitir retornar conversoes reais (agendamentos) ao Google Ads para otimizar campanhas. Arquivos criados: `src/services/lead_service.py`, `src/functions/lead/list.py`, `src/functions/lead/update.py`, `sls/functions/lead/interface.yml`. Arquivos modificados: `setup_database.py`, `webhook/handler.py`, `appointment_service.py`, `serverless.yml`. Testes: 14 novos + 2 corrigidos (45/45 ok). PRD: N/A, Spec: N/A.

- **008** Soft-Delete de Pacientes (2026-04-25) — Adicionada coluna `deleted_at TIMESTAMPTZ` em `scheduler.patients` (migration idempotente + indice `idx_patients_deleted`). Novo endpoint `DELETE /clinics/{id}/patients/{patientId}` (idempotente, 404 em inexistente). Filtro `deleted_at IS NULL` adicionado em todos os pontos que tratam paciente como entidade ativa: `patient/list.py`, `patient/update.py`, `clinic/reports.py`, `attendant/conversations.py`, `attendant/list_active.py`, `send/handler.py`, `appointment_service` (lookups por phone), `conversation_engine._on_enter_welcome`. JOINs historicos em `appointments` preservam o nome do paciente deletado. Restore on recreate em duas frentes: `POST /patients` retorna `status: "RESTORED"` quando o phone existe soft-deletado, e `_get_or_create_patient` (WhatsApp) restaura em vez de violar o `UNIQUE(clinic_id, phone)`. Frontend: novo `useDeletePatient` hook, `DeletePatientConfirmModal`, botao de excluir na `PatientsTable`, banner de feedback transitorio diferenciando CREATE/RESTORED, tipo `CreatePatientResponse`. Mocks, integration tests e Postman collection criados em `tests/`. PRD: `prd/008-patient-soft-delete.md`, Spec: `spec/008-patient-soft-delete.md`.

- **009** Exclusão e Rolagem na Tela de Horários (2026-08-29) — Implementados `DELETE /clinics/{id}/availability-rules/{ruleId}` (hard delete, escopado por clinicId) e `DELETE /clinics/{id}/availability-exceptions/{exceptionId}`, endpoints que o frontend já chamava sem nunca terem sido implantados. Novo `PATCH /clinics/{id}/availability-rules/{ruleId}` substitui o antigo "editar horário" (delete + create sequencial, não atômico). Corrigido `except UniqueViolation` que quebrava com `TypeError` em regras de data fixa. Adicionada validação `start_time < end_time` no create e no update. Novo índice único parcial impede data fixa duplicada. Frontend: `HorariosPage` dividida em `FixedDaysSection`/`RecurringSection`/`ExceptionsSection`, exclusão com optimistic update e undo via novo `Toast`/`ToastProvider`, `ScrollArea` com altura máxima e fade condicional aplicado às três seções, seleção múltipla de datas fixas para exclusão em lote. PRD: `prd/009-horarios-delete-scroll.md`, Spec: `spec/009-horarios-delete-scroll.md`.

- **011** Duração Manual do Agendamento (2026-09-16) — Nova coluna `manual_duration_minutes` em `scheduler.appointments` (migration idempotente) registra a duração que a recepção fixou para UM agendamento, separada de `total_duration_minutes` (a efetiva). Novo módulo `duracao_manual.py` é a única autoridade sobre a faixa (5-480, inteiro) e sobre qual duração vale; ele NÃO importa `duration_rules`, porque o manual ignora piso, teto e passo de propósito. `create_appointment` aceita `manual_duration_minutes`; novo `set_manual_duration` (com `verificar_conflito` opcional) fixa e solta o override, recalculando das áreas ao soltar. Duas correções de bug junto: `reschedule_appointment` parou de reaplicar `duracao_da_sessao` por cima de decisão humana (um override de 75min virava 50 no teto ao remarcar) e passou a gravar `total_duration_minutes` junto do `end_time` — divergência que já existia SEM override. `update_appointment_services` descarta o override e devolve `manual_duration_descartada` para a tela avisar. A ordem das etapas em `update.py` mudou: áreas → duração → reschedule → campos simples, porque a duração depois do reschedule calcularia o `end_time` com o valor antigo; o handler usa `"manualDurationMinutes" in body` para distinguir `null` (soltar) de ausente (não mexer). Frontend: novo `DuracaoField` compartilhado pelos dois modais, com os horários disponíveis buscados pela duração efetiva e descarte do override ao trocar áreas. O bot não chega ao campo: nenhuma tool do agente o expõe, e `total_duration_minutes` vindo do chamador continua ignorado. `scheduler.duration_rules` não é escrita em nenhum caminho. PRD: `prd/011-duracao-manual-do-agendamento.md`, Spec: `spec/011-duracao-manual-do-agendamento.md`.

(Adicione novas linhas acima desta.)

---

## Legenda

- **ID:** mesmo identificador do PRD e da Spec (ex: `001`, `002-refator-auth`).
- **PRD / Spec:** caminho do artefato em `docs/work/`.
