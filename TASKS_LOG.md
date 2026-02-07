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

(Adicione novas linhas acima desta.)

---

## Legenda

- **ID:** mesmo identificador do PRD e da Spec (ex: `001`, `002-refator-auth`).
- **PRD / Spec:** caminho do artefato em `docs/work/`.
