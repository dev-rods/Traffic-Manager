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

(Adicione novas linhas acima desta.)

---

## Legenda

- **ID:** mesmo identificador do PRD e da Spec (ex: `001`, `002-refator-auth`).
- **PRD / Spec:** caminho do artefato em `docs/work/`.
