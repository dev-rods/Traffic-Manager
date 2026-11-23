# Spec - 060 Sessão futura pergunta "remarcar ou mais uma?" e link direto para "Meus agendamentos"

> Gerada em 23/11/2026 a partir de `docs/work/prd/060-sessao-futura-e-link-meus-agendamentos.md`. Decisões 1-5 do PRD: as propostas.

---

## 1. Backend (scheduler)

### `src/services/appointment_service.py`

- Exceção nova `OutraSessaoFutura(existente)`, irmã de `SessaoNoMesmoMes`, mesma carga (`id`, `appointment_date`, `start_time`, `areas_display`, `patient_name`).
- `sessao_no_mesmo_mes` passa a delegar a `_sessao_confirmada_futura(clinic_id, phone, data, mesmo_mes: bool, excluir_id)`; o SQL é o mesmo, só o operador do `date_trunc` muda (`=` ou `<>`). Novo público: `sessao_futura_em_outro_mes(clinic_id, phone, data)`.
- `create_appointment(..., remarcar_a_existente=False, mais_uma=False)`:
  1. mesmo mês: como hoje (`SessaoNoMesmoMes` / `substituir_mesmo_mes` / `permitir_duas`);
  2. sem sessão no mesmo mês e sem `permitir_duas`: consulta outro mês; se houver e nenhuma das duas flags, `OutraSessaoFutura`;
  3. a sessão a substituir é a do mesmo mês (com `substituir_mesmo_mes`) ou a de outro mês (com `remarcar_a_existente`); o cancelamento continua DEPOIS da checagem de conflito, e o vínculo é o `_leva_para_o_novo` de sempre. Log `[OutroMes]`.
  4. `mais_uma` só libera a criação; nada é gravado.
- `remarca` não muda (mover a data é remarcação).

### `src/services/mesmo_mes.py`

- `OTHER_MONTH_APPOINTMENT`; `resposta_409(existente, code=SAME_MONTH_APPOINTMENT, message=...)` serve os dois.

### `src/functions/appointment/create.py` (painel)

- `except OutraSessaoFutura` → `resposta_409(e.existente, OTHER_MONTH_APPOINTMENT, "Esta paciente já tem sessão confirmada em outro mês.")`.
- Corpo: `remarcarExistente: true` / `maisUma: true` → `remarcar_a_existente` / `mais_uma`.

### `src/functions/public_booking/create_appointment.py` (site)

- Mesmo 409 com `code: OTHER_MONTH_APPOINTMENT`, `existing` e mensagem para front em cache ("Você já tem uma sessão em {dd/mm}. Para remarcar, abra Meus agendamentos; para marcar mais uma, recarregue a página."). Corpo `remarcarExistente` / `maisUma`. Mensagem de sucesso "remarcado" também com `remarcarExistente`.

### `src/services/ai_tools.py` (bot)

- `book_appointment` ganha `mais_uma` (boolean) na definição.
- `_recusa_outro_mes(args, phone, ctx)`: sessão futura do ctx em OUTRO mês e sem `mais_uma=true` → recado `ja_tem_sessao_futura` com a sessão e "pergunte se ela quer REMARCAR a sessão de X para a data pedida ou MARCAR MAIS UMA; remarcar é alterar_agendamento; mais uma é book_appointment com mais_uma=true; não decida por ela". Grava na sessão `pergunta_mais_uma = appointment_id`.
- `mais_uma=true` só é honrado se `session["pergunta_mais_uma"]` for a sessão futura atual (a pergunta foi feita); senão a tool devolve a pergunta de novo. `OutraSessaoFutura` do serviço vira o mesmo recado.
- Criação com `mais_uma` passa `mais_uma=True` ao serviço e continua devolvendo `sessao_anterior_mantida`.

### `src/services/skills/__init__.py`

- `PACIENTE_COM_HORARIO` item 3: outro mês pergunta primeiro (remarcação = alterar_agendamento; mais uma = book_appointment com mais_uma=true).

### `src/services/autoatendimento.py` e `lembrete.py`

- `link_de_meus_agendamentos(clinic)` = `link_de_autoatendimento(clinic) + "?meus=1"` (None sem domínio). `lembrete.bloco_de_prompt` usa esse link para remarcar.

### Testes

- `tests/unit/test_sessao_no_mesmo_mes.py`: `Db(outro_mes=True)` roteia pelo `<>`; casos: outro mês sem flag levanta e não escreve; `mais_uma` cria sem cancelar; `remarcar_a_existente` cancela a de outro mês e vincula; conflito de horário não cancela; `permitir_duas` não consulta outro mês; mesmo mês continua `SessaoNoMesmoMes`.
- `tests/unit/test_bot_mesmo_mes.py`: `TestOutroMesPassa` vira `TestOutroMesPergunta` (sem flag pergunta e grava na sessão; `mais_uma` sem pergunta prévia pergunta de novo; com pergunta cria; definição anuncia `mais_uma`; `OutraSessaoFutura` do serviço vira o recado).
- `tests/unit/test_painel_manter_as_duas.py` ou novo `test_painel_outro_mes.py`: 409 `OTHER_MONTH_APPOINTMENT` e os dois corpos.
- `tests/unit/test_lembrete_sobreposicao.py` / `test_lembrete_no_agente.py`: o bloco traz `?meus=1`.
- Novo `tests/unit/test_autoatendimento_meus.py` (ou dentro do existente): `link_de_meus_agendamentos` com e sem domínio; `link_citado` continua reconhecendo a raiz.

## 2. Site (`booking-site/`)

- `types`: `CreateAppointmentPayload.remarcarExistente?`, `maisUma?`.
- `pages/Booking.tsx`: `OTHER_MONTH_APPOINTMENT` → `conflito = { payload, existing, tipo: 'outro_mes' }`; `SAME_MONTH` → `tipo: 'mesmo_mes'`. Render `RemarcacaoDialog` (mesmo mês) ou `SessaoFuturaDialog` (outro mês).
- `components/SessaoFuturaDialog.tsx` (novo): título "Você já tem uma sessão marcada"; texto "Você já tem uma sessão em **{data} às {hora}**. O que você quer fazer?"; botões **Remarcar essa sessão para {nova data}** (`remarcarExistente: true`, `setRemarcado(true)`), **Marcar mais uma** (`maisUma: true`), Voltar; "Falar no WhatsApp" como no `RemarcacaoDialog`.
- `layouts/BookingChrome.tsx`: `useSearchParams`; `meus` presente abre o modal; fechar remove o parâmetro (replace).
- Testes: `Booking.test.tsx` describe novo (3 botões; cada um reenvia com a flag certa; sucesso "remarcado" só no remarcar); `BookingChrome.test.tsx` novo (`?meus=1` abre o modal; fechar limpa a URL; sem parâmetro fechado).
- `CLAUDE.md` do site: regra e link.

## 3. Painel (`frontend/`)

- `types`: `CreateAppointmentPayload.remarcarExistente?`, `maisUma?`.
- `ConflitoDoMes.tsx`: prop `variante?: 'mesmo_mes' | 'outro_mes'` (default `mesmo_mes`). `outro_mes`: "{nome} já tem sessão em {quando}." + "Remarcar essa sessão para {para}, ou marcar mais uma?"; botões Voltar / **Marcar mais uma** (`onMaisUma`) / **Remarcar essa sessão** (`onConfirmar`); sem "Manter as duas".
- `CreateAppointmentModal.tsx`: `conflito: { existing, variante }`; `OTHER_MONTH_APPOINTMENT` → `outro_mes`; `enviar` aceita `remarcarExistente` / `maisUma`.
- `lib/autoatendimento.ts` (novo): `linkDeMeusAgendamentos(customDomain)`.
- `AppointmentPopover.tsx`: prop `linkDeRemarcacao?: string | null`; ação "Copiar link de remarcação" (clipboard + toast) só quando vier. `AgendaPage` passa `linkDeMeusAgendamentos(clinic.custom_domain)` via `useClinic`.
- Testes: `ConflitoDoMes.test.tsx` (variante), `CreateAppointmentModal.test.tsx` (409 novo e os dois reenvios), `AppointmentPopover.test.tsx` (botão só com link; copia), `lib/autoatendimento.test.ts`.

## 4. Docs

- `scheduler/tests/integration/060-sessao-futura-e-link-meus-agendamentos.md`, `scheduler/tests/postman/060-....postman_requests.json`.
- PRD 060 Status, PRD 056 e 059 (ponteiros), `TASKS_LOG.md`.

## 5. Ordem

Backend + testes → site → painel → docs → deploy dev + roteiro (sem número inventado) → PR → prod (autorizado em 23/11).
