# PRD - 030 Site público oferece as próximas N datas

> Documentado junto com a implementação (ver `## Status`). Substitui a regra
> do mês vigente do PRD 023.

---

## 1. Objetivo

O site público de agendamento passa a oferecer **as próximas N datas com
horário livre**, contadas a partir de hoje, em vez de só as datas do mês
vigente. N é o campo "Datas futuras" (`clinics.max_future_dates`) que já existe
em Configurações e já limita quantos dias o bot de WhatsApp lista.

## 2. Contexto

A regra do mês vigente (PRD 023, decisão de outubro/2026) tinha um custo
anotado: no fim do mês o cliente podia ficar sem nenhum dia. Em 30/10/2026 o
custo apareceu de verdade: a Nobre Laser abre em 06/11 e o
`agendar.nobrelaser.com.br` não tinha nada para oferecer até a virada do mês.
O André pediu que o site liberasse sempre as N datas à frente, usando a
configuração que já existe.

## 3. Regra

- Hoje entra na conta, sem os horários que já passaram (fuso da clínica).
- Dia fechado (sem regra ou bloqueado) ou lotado não conta.
- Procura até 90 dias à frente (`MAX_SEARCH_DAYS`, o mesmo horizonte do bot);
  pode devolver menos que N quando a agenda não tem tantas.
- A criação só aceita data e horário que estejam na grade oferecida. Antes
  validava só a janela do mês; agora a grade da tela é a grade gravável, como
  já era para a duração e o preço.
- Vale só para o site. Bot e painel marcam para qualquer data.

## 4. Arquivos

| Arquivo | Ação |
|---|---|
| `scheduler/src/services/janela_do_site.py` | criar - `dias_oferecidos`, `quantas` |
| `scheduler/src/services/relogio.py` | criar - `agora_na_clinica`, `minutos_de_agora` (saíram de `mes_vigente`) |
| `scheduler/src/services/mes_vigente.py` | remover |
| `scheduler/src/services/availability_engine.py` | `datas_com_regra` (inclui hoje), `PADRAO_DATAS_FUTURAS` |
| `scheduler/src/functions/public_booking/availability.py` | sem `dates` e sem `window`; devolve as datas oferecidas |
| `scheduler/src/functions/public_booking/create_appointment.py` | valida contra a grade oferecida |
| `scheduler/src/services/caixa.py`, `checkin.py` | importam `relogio` |
| `booking-site` | `DayList` agrupa por mês, sem janela; `monthWindow` removido |
| `frontend` | texto de ajuda de "Datas futuras" |

## 5. Contrato

`GET /public/clinics/{clinicId}/availability?serviceIds=...&serviceAreaPairs=...`

```json
{"status": "SUCCESS", "days": {"2026-10-30": {"status": "AVAILABLE", "slots": ["15:00"]}, "2026-11-02": {"status": "AVAILABLE", "slots": ["09:00", "15:00"]}}}
```

`dates` ainda é aceito e ignorado (front em cache durante o deploy).

## 6. Deploy

Deploy do `scheduler` **antes** do merge: o front novo não manda `dates`, e o
backend antigo respondia 400 sem ele.

## Status

- [x] Implementado em 30/10/2026 (branch `feat/030-site-proximas-datas`).
- [ ] Deploy prod do scheduler, depois merge (Vercel publica o site e o painel).
