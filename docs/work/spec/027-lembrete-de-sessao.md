# Lembrete de sessão - Plano de implementação (Spec 027)

> **Para agentes:** executar tarefa por tarefa com `executing-plans` (ou um subagente por tarefa). Passos usam `- [ ]`. PRD de origem: `docs/work/prd/027-lembrete-de-sessao.md`.

**Objetivo:** lembrar pelo WhatsApp todo paciente com sessão confirmada num dia da agenda (botão hoje, gatilho automático por clínica depois), com texto que não cita cancelar nem remarcar; o bot assume a conversa e, se a pessoa pedir para cancelar ou remarcar, manda o link de "Meus agendamentos" em vez de executar; resposta positiva vira Confirmado na agenda.

**Arquitetura:** a unidade é "agenda do dia D da clínica". `lembrete_da_agenda.enfileira` seleciona os `CONFIRMED` do dia sem lembrete e grava um item por agendamento na tabela `scheduled-reminders` com um `send_at` único do lote. O `ReminderProcessor` (acordado por invocação e por cron horário) entrega, grava `lembrete_*` no agendamento e abre a **sobreposição de lembrete** na sessão. A sobreposição remove as ferramentas de cancelar e remarcar da chamada ao modelo quando a clínica tem site, injeta o bloco de prompt com o link e libera `confirm_attendance`. Uma Lambda horária calcula o lote automático para clínicas com `lembrete_automatico`.

**Stack:** Python 3.13 (Lambda, unittest), Postgres (Supabase), DynamoDB (`scheduled-reminders`, sessões, MessageEvents), z-api, React 19 + TS + TanStack Query v5 + Vitest.

## Restrições globais

- Branch `feat/027-lembrete-de-sessao`, PR para `main`. Sem commit em main. Sem co-author do agente no commit.
- Hífen `-`, nunca travessão.
- Migrations idempotentes; `CREATE TABLE` da lista `TABLES` atualizado junto.
- Backend: logs `[traceId: ...]`; testes em `scheduler/tests/unit/` com `unittest`, rodados por `cd scheduler && python -m unittest tests.unit.<modulo> -v`.
- Frontend: named exports, zero `any`, 4 estados, query keys por factory, `npm run lint` com zero warnings, design conforme `frontend/CLAUDE.md`.
- Template default `LEMBRETE_SESSAO` **não contém** "cancel" nem "remarc" nem link. Teste literal garante.
- Status de agendamento continua `CONFIRMED | CANCELLED | NO_SHOW`. Confirmação é coluna (`confirmado_em`), nunca status.
- Chave da sobreposição na sessão: `session["lembrete"]`. Tipo do item na fila: `reminderType = "LEMBRETE_SESSAO"`.

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `scheduler/src/scripts/setup_database.py` | migrations |
| `scheduler/src/services/template_service.py` | `LEMBRETE_SESSAO` no lugar de `REMINDER_24H` |
| `scheduler/src/services/autoatendimento.py` | `link_de_autoatendimento(clinic)` |
| `scheduler/src/services/lembrete.py` | sobreposição: `abre`, `esta_vivo`, `ferramentas_a_remover`, `ferramentas_a_liberar`, `bloco_de_prompt` |
| `scheduler/src/services/porta_do_disparo.py` | `motivo_para_nao_iniciar`, `MOTIVOS_QUE_O_DISPARO_DESTRAVA` (movidos de `send/handler.py`) |
| `scheduler/src/services/lembrete_da_agenda.py` | `seleciona`, `enfileira`, `inicio_da_agenda`, `renderiza_variaveis` |
| `scheduler/src/services/reminder_service.py` | `agenda_lembrete(appointment, clinic, send_at)`; sai `schedule_reminder` |
| `scheduler/src/services/session_store.py` | `abre_lembrete` |
| `scheduler/src/functions/reminder/processor.py` | entrega, grava `lembrete_*`, abre sobreposição, destrava |
| `scheduler/src/functions/reminder/automaticos.py` | Lambda horária |
| `scheduler/src/functions/appointment/lembretes_do_dia.py` | `POST /clinics/{clinicId}/agenda/{dia}/lembretes` |
| `scheduler/src/functions/appointment/update.py`, `list.py` | `confirmado` no PUT; campos novos no SELECT |
| `scheduler/src/services/ai_tools.py`, `conversation_agent.py` | `confirm_attendance`, filtro e bloco |
| `scheduler/sls/functions/reminder/interface.yml`, `appointment/interface.yml` | crons, invoke, rota |
| `frontend/src/types/index.ts`, `services/appointments.service.ts`, `hooks/useAppointments.ts` | campos e chamadas |
| `frontend/src/pages/agenda/components/LembrarAgendaDoDia.tsx` (novo), `AgendaHeader.tsx`, `AgendaDoDia.tsx`, `WeekGrid.tsx`, `AppointmentPopover.tsx`, `AgendaPage.tsx` | botão, badges, ações |
| `frontend/src/pages/configuracoes/ConfiguracoesPage.tsx` | seção de lembrete |

---

## Tarefa 1: Migrations e template

**Arquivos:** modificar `scheduler/src/scripts/setup_database.py`, `scheduler/src/services/template_service.py`; testar em `scheduler/tests/unit/test_template_lembrete.py`.

- [ ] **Passo 1: teste do template**

```python
# -*- coding: utf-8 -*-
"""O lembrete nao planta a ideia de cancelar. Teste literal, de proposito."""
import unittest

from src.services.template_service import DEFAULT_TEMPLATES


class TestTemplateDoLembrete(unittest.TestCase):
    def test_existe_e_o_antigo_saiu(self):
        self.assertIn("LEMBRETE_SESSAO", DEFAULT_TEMPLATES)
        self.assertNotIn("REMINDER_24H", DEFAULT_TEMPLATES)

    def test_nao_cita_cancelar_remarcar_nem_link(self):
        t = DEFAULT_TEMPLATES["LEMBRETE_SESSAO"].lower()
        for proibido in ("cancel", "remarc", "http", "responda ok"):
            self.assertNotIn(proibido, t)

    def test_tem_as_variaveis(self):
        t = DEFAULT_TEMPLATES["LEMBRETE_SESSAO"]
        for v in ("{{nome}}", "{{areas}}", "{{clinic_name}}", "{{dia}}", "{{hora}}"):
            self.assertIn(v, t)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: rodar e ver falhar**: `cd scheduler && python -m unittest tests.unit.test_template_lembrete -v`.

- [ ] **Passo 3: template.** Em `DEFAULT_TEMPLATES`, remover a linha `"REMINDER_24H": ...` e acrescentar:

```python
    # Lembrete de sessao (PRD 027). Sem "cancelar", "remarcar" nem link, de
    # proposito: citar a saida planta a ideia. O preparo pequeno (raspar, sol)
    # refor­ca o compromisso. O link so vai se a pessoa pedir, pelo bot.
    "LEMBRETE_SESSAO": (
        "Oi {{nome}}! Sua sessão de {{areas}} na {{clinic_name}} está confirmada "
        "para {{dia}} às {{hora}}. Já estamos preparando tudo para você. "
        "Lembre de raspar a área no dia e evitar sol até lá. Até breve! 😊"
    ),
```

(A sintaxe de variável do `render_template` é `{{chave}}`; na tela do painel, o texto de ajuda mostra `{{nome}}`.)

- [ ] **Passo 4: migrations**, ao fim de `MIGRATIONS`:

```python
    # -- Lembrete de sessao (PRD 027) ------------------------------------------
    #
    # `lembrete_*` e o rastro do envio por agendamento (idempotencia e estado
    # para o popover). `confirmado_*` e a resposta da pessoa ou da equipe.
    # Confirmacao NAO e status: `status` governa motor de horarios, conversao e
    # agenda, e um quarto valor exigiria revisar tudo isso.
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS lembrete_enviado_em TIMESTAMPTZ",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS lembrete_status VARCHAR(16)",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS lembrete_erro VARCHAR(120)",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS confirmado_em TIMESTAMPTZ",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS confirmado_por VARCHAR(16)",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_appointments_lembrete_status') THEN
            ALTER TABLE scheduler.appointments ADD CONSTRAINT chk_appointments_lembrete_status CHECK (
                lembrete_status IS NULL OR lembrete_status IN ('ENFILEIRADO','ADIADO','ENVIADO','FALHOU'));
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_appointments_confirmado_por') THEN
            ALTER TABLE scheduler.appointments ADD CONSTRAINT chk_appointments_confirmado_por CHECK (
                confirmado_por IS NULL OR confirmado_por IN ('PACIENTE','EQUIPE'));
        END IF;
    END $$
    """,
    """CREATE INDEX IF NOT EXISTS idx_appointments_sem_lembrete
       ON scheduler.appointments (clinic_id, appointment_date)
       WHERE lembrete_enviado_em IS NULL""",

    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS lembrete_automatico BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS lembrete_antecedencia_horas INTEGER NOT NULL DEFAULT 24",
```

E nos `CREATE TABLE` de `appointments` e `clinics` da lista `TABLES`, as mesmas colunas.

- [ ] **Passo 5: rodar em dev duas vezes** (idempotência), como na Spec 026 Tarefa 1, e o teste do Passo 1. **Commit:** `feat(lembrete): colunas de lembrete e confirmacao; template LEMBRETE_SESSAO`.

---

## Tarefa 2: Link de autoatendimento e porta do disparo

**Arquivos:** criar `scheduler/src/services/autoatendimento.py`, `scheduler/src/services/porta_do_disparo.py`; modificar `scheduler/src/functions/send/handler.py`; testar em `scheduler/tests/unit/test_autoatendimento.py` e ajustar `tests/unit/test_porta_de_atendimento.py` se importar o privado.

**Produz:**

```python
# autoatendimento.py
def link_de_autoatendimento(clinic: dict) -> Optional[str]   # "https://{custom_domain}/" ou None

# porta_do_disparo.py
MOTIVOS_QUE_O_DISPARO_DESTRAVA: frozenset   # {"atendimento_humano", "cooldown"}
def motivo_para_nao_iniciar(clinic, sessao, agora: int) -> Optional[str]
```

- [ ] **Passo 1: testes**

```python
# -*- coding: utf-8 -*-
import unittest

from src.services.autoatendimento import link_de_autoatendimento


class TestLink(unittest.TestCase):
    def test_com_dominio(self):
        self.assertEqual(link_de_autoatendimento({"custom_domain": "agendar.nobrelaser.com.br"}),
                         "https://agendar.nobrelaser.com.br/")

    def test_sem_dominio_e_none(self):
        self.assertIsNone(link_de_autoatendimento({"custom_domain": None}))
        self.assertIsNone(link_de_autoatendimento({"custom_domain": "  "}))
        self.assertIsNone(link_de_autoatendimento({}))

    def test_nao_duplica_esquema(self):
        self.assertEqual(link_de_autoatendimento({"custom_domain": "https://x.com"}), "https://x.com/")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: implementar `autoatendimento.py`**

```python
# -*- coding: utf-8 -*-
"""Onde a pessoa resolve o proprio agendamento sem falar com ninguem.

"Meus agendamentos" vive na Home do booking-site. Com dominio proprio da
clinica a raiz JA e a clinica; sem dominio, nao ha link: o bot volta a
cancelar e remarcar pela conversa (decisao do Andre em 27/10/2026). O dominio
Vercel padrao fica de fora de proposito; se um dia servir, e uma env var aqui,
num lugar so.
"""
from typing import Optional


def link_de_autoatendimento(clinic: dict) -> Optional[str]:
    dominio = ((clinic or {}).get("custom_domain") or "").strip()
    if not dominio:
        return None
    dominio = dominio.replace("https://", "").replace("http://", "").rstrip("/")
    return f"https://{dominio}/"
```

- [ ] **Passo 3: mover a porta.** Criar `porta_do_disparo.py` com o conteúdo de `MOTIVOS_QUE_O_DISPARO_DESTRAVA` e `_motivo_para_nao_iniciar` (renomeada `motivo_para_nao_iniciar`, mesmo corpo e docstring) de `send/handler.py`. No handler, trocar as definições por `from src.services.porta_do_disparo import MOTIVOS_QUE_O_DISPARO_DESTRAVA, motivo_para_nao_iniciar` e manter `_motivo_para_nao_iniciar = motivo_para_nao_iniciar` como alias para os testes existentes que fazem patch no nome antigo.

- [ ] **Passo 4: rodar** `python -m unittest tests.unit.test_autoatendimento tests.unit.test_porta_de_atendimento -v`. **Commit:** `refactor(disparo): porta do disparo em servico proprio; link de autoatendimento`.

---

## Tarefa 3: Sobreposição de lembrete no bot

**Arquivos:** criar `scheduler/src/services/lembrete.py`; modificar `scheduler/src/services/session_store.py`, `scheduler/src/services/ai_tools.py`, `scheduler/src/services/conversation_agent.py`; testar em `scheduler/tests/unit/test_lembrete_sobreposicao.py`.

**Produz:**

```python
# lembrete.py
FERRAMENTAS_DE_SAIDA = frozenset({"reschedule_appointment", "cancel_appointment"})
FERRAMENTA_DE_CONFIRMACAO = "confirm_attendance"
def abre(appointment: dict, clinic: dict, agora: Optional[int] = None) -> dict
    # {"appointment_id", "dia": "YYYY-MM-DD", "hora": "HH:MM", "areas": str, "expira_em": epoch do fim do dia da sessao no fuso da clinica}
def esta_vivo(session, agora=None) -> bool
def appointment_id(session, agora=None) -> Optional[str]
def ferramentas_a_remover(session, clinic, agora=None) -> frozenset
def ferramentas_a_liberar(session, agora=None) -> frozenset     # {confirm_attendance} se vivo
def bloco_de_prompt(session, clinic, agora=None) -> str          # "" se nao vivo

# session_store.py
def abre_lembrete(table, clinic_id, phone, lembrete: dict) -> bool
```

- [ ] **Passo 1: testes**

```python
# -*- coding: utf-8 -*-
"""A sobreposicao de lembrete: viva ate o fim do dia da sessao, esconde cancelar
e remarcar quando ha site, libera confirm_attendance, e o bloco traz o link."""
import unittest
from datetime import date, time

import pytz

from src.services import lembrete as L

TZ = pytz.timezone("America/Sao_Paulo")
CLINIC_COM_SITE = {"timezone": "America/Sao_Paulo", "custom_domain": "agendar.x.com.br", "display_name": "X"}
CLINIC_SEM_SITE = {"timezone": "America/Sao_Paulo", "custom_domain": None, "display_name": "X"}
APPT = {"id": "a1", "appointment_date": date(2026, 11, 6), "start_time": time(9, 0), "areas": "Axilas, Virilha Completa"}

# 05/11/2026 12:00 BRT
AGORA = int(TZ.localize(__import__("datetime").datetime(2026, 11, 5, 12, 0)).timestamp())


def sessao(lembrete):
    return {"lembrete": lembrete}


class TestAbre(unittest.TestCase):
    def test_expira_no_fim_do_dia_da_sessao(self):
        l = L.abre(APPT, CLINIC_COM_SITE, agora=AGORA)
        self.assertEqual(l["appointment_id"], "a1")
        self.assertEqual(l["dia"], "2026-11-06")
        self.assertEqual(l["hora"], "09:00")
        fim = TZ.localize(__import__("datetime").datetime(2026, 11, 6, 23, 59, 59))
        self.assertEqual(l["expira_em"], int(fim.timestamp()))


class TestVivo(unittest.TestCase):
    def test_vivo_antes_de_expirar(self):
        self.assertTrue(L.esta_vivo(sessao(L.abre(APPT, CLINIC_COM_SITE, AGORA)), AGORA))

    def test_morto_depois(self):
        l = L.abre(APPT, CLINIC_COM_SITE, AGORA)
        self.assertFalse(L.esta_vivo(sessao(l), l["expira_em"] + 1))

    def test_falha_fechada(self):
        self.assertFalse(L.esta_vivo({}, AGORA))
        self.assertFalse(L.esta_vivo(sessao({"expira_em": "x"}), AGORA))
        self.assertFalse(L.esta_vivo(None, AGORA))


class TestFerramentas(unittest.TestCase):
    def test_com_site_remove_saida_e_libera_confirmacao(self):
        s = sessao(L.abre(APPT, CLINIC_COM_SITE, AGORA))
        self.assertEqual(L.ferramentas_a_remover(s, CLINIC_COM_SITE, AGORA), L.FERRAMENTAS_DE_SAIDA)
        self.assertEqual(L.ferramentas_a_liberar(s, AGORA), {L.FERRAMENTA_DE_CONFIRMACAO})

    def test_sem_site_nao_remove_nada(self):
        s = sessao(L.abre(APPT, CLINIC_SEM_SITE, AGORA))
        self.assertEqual(L.ferramentas_a_remover(s, CLINIC_SEM_SITE, AGORA), frozenset())
        self.assertEqual(L.ferramentas_a_liberar(s, AGORA), {L.FERRAMENTA_DE_CONFIRMACAO})

    def test_morto_nao_mexe_em_nada(self):
        l = L.abre(APPT, CLINIC_COM_SITE, AGORA)
        depois = l["expira_em"] + 1
        self.assertEqual(L.ferramentas_a_remover(sessao(l), CLINIC_COM_SITE, depois), frozenset())
        self.assertEqual(L.ferramentas_a_liberar(sessao(l), depois), frozenset())


class TestBloco(unittest.TestCase):
    def test_com_site_tem_link_e_proibe_executar(self):
        b = L.bloco_de_prompt(sessao(L.abre(APPT, CLINIC_COM_SITE, AGORA)), CLINIC_COM_SITE, AGORA)
        self.assertIn("https://agendar.x.com.br/", b)
        self.assertIn("NÃO execute", b)
        self.assertIn("confirm_attendance", b)
        self.assertIn("06/11", b)

    def test_sem_site_diz_que_resolve_por_aqui(self):
        b = L.bloco_de_prompt(sessao(L.abre(APPT, CLINIC_SEM_SITE, AGORA)), CLINIC_SEM_SITE, AGORA)
        self.assertNotIn("http", b)
        self.assertIn("por aqui mesmo", b)

    def test_morto_e_vazio(self):
        l = L.abre(APPT, CLINIC_COM_SITE, AGORA)
        self.assertEqual(L.bloco_de_prompt(sessao(l), CLINIC_COM_SITE, l["expira_em"] + 1), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: rodar e ver falhar.**

- [ ] **Passo 3: implementar `lembrete.py`**

```python
# -*- coding: utf-8 -*-
"""A sobreposicao de lembrete (PRD 027), nos moldes de `campanha.py`.

Gravada na sessao no ato da ENTREGA do lembrete, nunca inferida pelo modelo.
Enquanto viva (ate o fim do dia da sessao, no fuso da clinica):

- com site de autoatendimento, `cancel_appointment` e `reschedule_appointment`
  NAO vao ao modelo: a pessoa recebe o link e resolve sozinha. Nao e so prompt:
  a ferramenta nao existe para ele.
- sem site, nada e removido: o bot cancela e remarca como sempre.
- `confirm_attendance` so existe aqui: resposta positiva vira Confirmado.

Funcoes puras, sem I/O.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, FrozenSet, Optional

from src.services.autoatendimento import link_de_autoatendimento
from src.services.business_hours import fuso

CHAVE = "lembrete"
FERRAMENTAS_DE_SAIDA = frozenset({"reschedule_appointment", "cancel_appointment"})
FERRAMENTA_DE_CONFIRMACAO = "confirm_attendance"


def _hora(valor) -> str:
    if hasattr(valor, "strftime"):
        return valor.strftime("%H:%M")
    if isinstance(valor, timedelta):
        s = int(valor.total_seconds())
        return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"
    return str(valor)[:5]


def _dia(valor) -> str:
    return valor.isoformat() if hasattr(valor, "isoformat") else str(valor)[:10]


def abre(appointment: Dict, clinic: Dict, agora: Optional[int] = None) -> Dict:
    dia = _dia(appointment.get("appointment_date"))
    tz = fuso(clinic)
    fim = tz.localize(datetime.strptime(dia, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
    return {
        "appointment_id": str(appointment.get("id")),
        "dia": dia,
        "hora": _hora(appointment.get("start_time")),
        "areas": appointment.get("areas") or "",
        "expira_em": int(fim.timestamp()),
    }


def _dados(session) -> Optional[Dict]:
    d = (session or {}).get(CHAVE)
    return d if isinstance(d, dict) else None


def esta_vivo(session, agora: Optional[int] = None) -> bool:
    d = _dados(session)
    if not d:
        return False
    try:
        expira = int(d["expira_em"])
    except (KeyError, TypeError, ValueError):
        return False
    return expira > int(agora if agora is not None else time.time())


def appointment_id(session, agora: Optional[int] = None) -> Optional[str]:
    return _dados(session)["appointment_id"] if esta_vivo(session, agora) else None


def ferramentas_a_remover(session, clinic, agora: Optional[int] = None) -> FrozenSet[str]:
    if not esta_vivo(session, agora) or not link_de_autoatendimento(clinic):
        return frozenset()
    return FERRAMENTAS_DE_SAIDA


def ferramentas_a_liberar(session, agora: Optional[int] = None) -> FrozenSet[str]:
    return frozenset({FERRAMENTA_DE_CONFIRMACAO}) if esta_vivo(session, agora) else frozenset()


def bloco_de_prompt(session, clinic, agora: Optional[int] = None) -> str:
    if not esta_vivo(session, agora):
        return ""
    d = _dados(session)
    dia_br = datetime.strptime(d["dia"], "%Y-%m-%d").strftime("%d/%m")
    link = link_de_autoatendimento(clinic)
    saida = (
        f"Se ela quiser CANCELAR ou REMARCAR, NÃO execute nada: envie o link {link} e diga "
        "que ela resolve em um minuto por lá, com o mesmo número de WhatsApp. "
        "Se disser que não vai poder ir sem pedir nada, pergunte se prefere remarcar ou "
        "cancelar e então envie o link.\n"
        if link else
        "Se ela quiser cancelar ou remarcar, pode resolver por aqui mesmo com as ferramentas, como sempre.\n"
    )
    return (
        "\n═══ LEMBRETE ENVIADO ═══\n"
        f"Esta pessoa acabou de receber o lembrete da sessão de {dia_br} às {d['hora']}"
        f"{' (' + d['areas'] + ')' if d.get('areas') else ''}.\n"
        "Se ela responder confirmando que vai (ok, confirmado, estarei lá, joinha), use "
        f"`{FERRAMENTA_DE_CONFIRMACAO}` e agradeça em uma linha, sem perguntar mais nada.\n"
        + saida +
        "Dúvidas sobre a sessão, preparo e endereço: responda normalmente.\n"
    )
```

- [ ] **Passo 4: `session_store.abre_lembrete`**, cópia de `abre_campanha` trocando `session["campanha"] = campanha` por `session["lembrete"] = lembrete`, mesmo zeramento de `agent_history` (o lembrete começa uma conversa) e log `[SessionStore] Lembrete aberto para {phone}`. Extrair o corpo comum em `_abre_sobreposicao(table, clinic_id, phone, chave, dados, rotulo)` e fazer as duas chamarem.

- [ ] **Passo 5: ferramenta `confirm_attendance` em `ai_tools.py`.** Em `TOOL_DEFINITIONS`:

```python
    {
        "type": "function",
        "function": {
            "name": "confirm_attendance",
            "description": "A pessoa confirmou que vai à sessão sobre a qual acabou de receber o lembrete. Marca a presença como confirmada. Só existe após um lembrete.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
```

E em `ToolExecutor`:

```python
    def _tool_confirm_attendance(self, args, clinic_id, phone, ctx):
        """Grava `confirmado_em` no agendamento do lembrete vivo na sessao.
        O id vem da sessao, nao do modelo: ele nao tem como inventar outro."""
        from src.services import lembrete
        appointment_id = lembrete.appointment_id(ctx.get("session"))
        if not appointment_id:
            return {"error": "Nenhum lembrete ativo nesta conversa"}
        n = self.db.execute_write(
            """UPDATE scheduler.appointments
                  SET confirmado_em = COALESCE(confirmado_em, NOW()), confirmado_por = COALESCE(confirmado_por, 'PACIENTE'),
                      updated_at = NOW()
                WHERE id = %s::uuid AND status = 'CONFIRMED'""",
            (appointment_id,),
        )
        return {"success": n > 0, "appointment_id": appointment_id}
```

Confira que `ctx` carrega `session` (o agente monta o `context` das tools; se não tiver, acrescentar `"session": session` ao dict no ponto em que `ToolExecutor.execute` é chamado) e que `self.db` existe no executor (se não, usar `self.appointment_service.db`).

**Filtro base:** `confirm_attendance` precisa estar fora das tools por padrão. Em `skills/__init__.py`, acrescentar `"confirm_attendance"` a `tools_vetadas` de TODAS as skills, com comentário "só a sobreposição de lembrete libera". A liberação acontece no agente (Passo 6).

- [ ] **Passo 6: agente.** Em `conversation_agent.py`:

Depois de `if not campanha_viva(session): system_prompt += skill.bloco`:

```python
        # Sobreposicao de lembrete (PRD 027): bloco por cima de qualquer skill,
        # como a campanha. Gravada na entrega do lembrete, nunca inferida.
        system_prompt += lembrete.bloco_de_prompt(session, clinic)
```

No lugar de `tools = skill.filtra(get_tool_definitions(format="anthropic", faq=itens_do_faq))`:

```python
        definicoes = get_tool_definitions(format="anthropic", faq=itens_do_faq)
        remover = lembrete.ferramentas_a_remover(session, clinic)
        liberar = lembrete.ferramentas_a_liberar(session)
        tools = [
            d for d in skill.filtra([d for d in definicoes if d.get("name") not in remover])
        ] + [d for d in definicoes if d.get("name") in liberar]
```

`clinic` é o dict da clínica já carregado no agente (confira o nome da variável nesse escopo; se só houver `clinic_id`, carregar uma vez no início do método como as outras consultas por clínica).

- [ ] **Passo 7: teste do filtro no agente** (acrescentar a um teste existente de skills ou criar `test_lembrete_no_agente.py`): montar `definicoes` falsas com os três nomes e uma skill qualquer, aplicar o mesmo trecho via função extraída `_ferramentas_para(session, clinic, skill, definicoes)` em `conversation_agent.py`, e verificar que com lembrete vivo e site: sem cancelar/remarcar e com `confirm_attendance`; sem site: com as duas e com `confirm_attendance`; sem lembrete: sem `confirm_attendance`. Extrair essa função pura é parte desta tarefa.

- [ ] **Passo 8: rodar** `python -m unittest tests.unit.test_lembrete_sobreposicao tests.unit.test_lembrete_no_agente -v` e a suíte de skills existente. **Commit:** `feat(lembrete): sobreposicao no bot - link em vez de cancelar, confirm_attendance`.

---

## Tarefa 4: Seleção e enfileiramento do lote

**Arquivos:** criar `scheduler/src/services/lembrete_da_agenda.py`; modificar `scheduler/src/services/reminder_service.py`; testar em `scheduler/tests/unit/test_lembrete_da_agenda.py`.

**Produz:**

```python
# lembrete_da_agenda.py
def seleciona(db, clinic_id: str, dia: str) -> dict
    # {"enfileiraveis": [appt...], "ja_lembrados": int, "sem_telefone": int, "enfileirados_antes": int}
def inicio_da_agenda(appointments: list) -> Optional[time]        # menor start_time dos CONFIRMED
def send_at_do_lote(clinic, agora: datetime) -> datetime         # fim do silencio se dentro, senao agora
def enfileira(db, reminder_service, clinic, dia: str, send_at: datetime, simular=False) -> dict
    # {"enfileirados", "ja_lembrados", "sem_telefone", "send_at": iso}
def variaveis_do_template(appt: dict, clinic: dict) -> dict      # nome, areas, clinic_name, dia, hora

# reminder_service.py
def agenda_lembrete(self, appointment: dict, clinic: dict, send_at: datetime) -> dict   # item com reminderType LEMBRETE_SESSAO
# `schedule_reminder` e removido; as chamadas em appointment_service (guardadas por self.reminder_service, hoje None) saem junto.
```

- [ ] **Passo 1: testes**

```python
# -*- coding: utf-8 -*-
"""Um lembrete por agendamento confirmado do dia, nunca repetido; o lote sai
de uma vez, no fim do silencio se preciso."""
import unittest
from datetime import date, datetime, time, timezone
from unittest import mock

import pytz

from src.services import lembrete_da_agenda as LA

TZ = pytz.timezone("America/Sao_Paulo")
CLINIC = {"clinic_id": "c1", "timezone": "America/Sao_Paulo", "name": "Essencia", "display_name": "Essência",
          "janela_de_silencio": None}


def appt(i, **kw):
    base = {"id": f"a{i}", "clinic_id": "c1", "appointment_date": date(2026, 11, 6), "start_time": time(9 + i, 0),
            "status": "CONFIRMED", "patient_phone": f"551199999000{i}", "full_name": f"Pessoa {i}",
            "patient_name": None, "areas": "Axilas", "lembrete_enviado_em": None, "lembrete_status": None}
    base.update(kw)
    return base


class BancoFalso:
    def __init__(self, linhas):
        self.linhas = linhas
        self.escritas = []
    def execute_query(self, sql, params=None):
        return self.linhas
    def execute_write(self, sql, params=None):
        self.escritas.append((" ".join(sql.split()), params)); return 1


class TestSeleciona(unittest.TestCase):
    def test_separa_enfileiraveis_lembrados_e_sem_telefone(self):
        db = BancoFalso([appt(1), appt(2, lembrete_enviado_em=datetime.now(timezone.utc), lembrete_status="ENVIADO"),
                         appt(3, patient_phone=None), appt(4, lembrete_status="ENFILEIRADO")])
        r = LA.seleciona(db, "c1", "2026-11-06")
        self.assertEqual([a["id"] for a in r["enfileiraveis"]], ["a1"])
        self.assertEqual((r["ja_lembrados"], r["sem_telefone"], r["enfileirados_antes"]), (1, 1, 1))

    def test_duas_sessoes_da_mesma_pessoa_sao_dois_lembretes(self):
        db = BancoFalso([appt(1), appt(2, patient_phone="5511999990001")])
        self.assertEqual(len(LA.seleciona(db, "c1", "2026-11-06")["enfileiraveis"]), 2)


class TestInicioESendAt(unittest.TestCase):
    def test_inicio_e_o_menor_horario(self):
        self.assertEqual(LA.inicio_da_agenda([appt(2), appt(1)]), time(10, 0))
        self.assertIsNone(LA.inicio_da_agenda([]))

    def test_fora_do_silencio_e_agora(self):
        agora = TZ.localize(datetime(2026, 11, 5, 10, 0))
        self.assertEqual(LA.send_at_do_lote(CLINIC, agora), agora)

    def test_dentro_do_silencio_vai_para_o_fim(self):
        agora = TZ.localize(datetime(2026, 11, 5, 23, 0))
        s = LA.send_at_do_lote(CLINIC, agora)
        self.assertGreater(s, agora)
        self.assertEqual(s.astimezone(TZ).date(), date(2026, 11, 6))


class TestEnfileira(unittest.TestCase):
    def test_simular_nao_escreve(self):
        db = BancoFalso([appt(1)]); rs = mock.MagicMock()
        r = LA.enfileira(db, rs, CLINIC, "2026-11-06", datetime.now(timezone.utc), simular=True)
        self.assertEqual(r["enfileirados"], 1)
        rs.agenda_lembrete.assert_not_called()
        self.assertEqual(db.escritas, [])

    def test_enfileira_e_marca(self):
        db = BancoFalso([appt(1), appt(2)]); rs = mock.MagicMock()
        send_at = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        r = LA.enfileira(db, rs, CLINIC, "2026-11-06", send_at)
        self.assertEqual(r["enfileirados"], 2)
        self.assertEqual(rs.agenda_lembrete.call_count, 2)
        self.assertTrue(all("lembrete_status = 'ENFILEIRADO'" in s for s, _ in db.escritas))
        self.assertEqual(r["send_at"], "2026-11-05T12:00:00Z")


class TestVariaveis(unittest.TestCase):
    def test_variaveis(self):
        v = LA.variaveis_do_template(appt(1, areas="Axilas, Virilha Completa, Buço"), CLINIC)
        self.assertEqual(v["nome"], "Pessoa")
        self.assertEqual(v["areas"], "Axilas, Virilha Completa e Buço")
        self.assertEqual(v["clinic_name"], "Essência")
        self.assertEqual(v["dia"], "sexta, 06/11")
        self.assertEqual(v["hora"], "10:00")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: rodar e ver falhar.**

- [ ] **Passo 3: implementar `lembrete_da_agenda.py`**

```python
# -*- coding: utf-8 -*-
"""O lote de lembretes de UM dia da agenda (PRD 027).

Um lembrete por agendamento confirmado, nunca repetido (`lembrete_enviado_em`
e `ENFILEIRADO` barram). O dia inteiro sai com o mesmo `send_at`: antecedencia
e relativa ao primeiro horario do dia, nao a cada sessao.
"""
import logging
from datetime import datetime, time, timezone
from typing import Dict, List, Optional

from src.services.business_hours import fim_do_silencio, fuso

logger = logging.getLogger(__name__)

DIAS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _linhas_do_dia(db, clinic_id: str, dia: str) -> List[Dict]:
    return db.execute_query(
        """
        SELECT a.*, p.phone AS patient_phone, p.name AS patient_name,
               (SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at)
                  FROM scheduler.appointment_service_areas asa WHERE asa.appointment_id = a.id) AS areas
          FROM scheduler.appointments a
          LEFT JOIN scheduler.patients p ON p.id = a.patient_id
         WHERE a.clinic_id = %s AND a.appointment_date = %s AND a.status = 'CONFIRMED'
         ORDER BY a.start_time
        """,
        (clinic_id, dia),
    )


def seleciona(db, clinic_id: str, dia: str) -> Dict:
    enfileiraveis, ja_lembrados, sem_telefone, antes = [], 0, 0, 0
    for a in _linhas_do_dia(db, clinic_id, dia):
        if a.get("lembrete_enviado_em"):
            ja_lembrados += 1
        elif a.get("lembrete_status") == "ENFILEIRADO":
            antes += 1
        elif not (a.get("patient_phone") or "").strip():
            sem_telefone += 1
        else:
            enfileiraveis.append(a)
    return {"enfileiraveis": enfileiraveis, "ja_lembrados": ja_lembrados,
            "sem_telefone": sem_telefone, "enfileirados_antes": antes}


def inicio_da_agenda(appointments: List[Dict]) -> Optional[time]:
    horarios = [a["start_time"] for a in appointments if a.get("status", "CONFIRMED") == "CONFIRMED" and a.get("start_time")]
    return min(horarios) if horarios else None


def send_at_do_lote(clinic: Dict, agora: datetime) -> datetime:
    """Agora, ou o fim da janela de silencio se agora cai dentro dela."""
    return fim_do_silencio(clinic, agora)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def enfileira(db, reminder_service, clinic: Dict, dia: str, send_at: datetime, simular: bool = False) -> Dict:
    sel = seleciona(db, clinic["clinic_id"], dia)
    if not simular:
        for a in sel["enfileiraveis"]:
            reminder_service.agenda_lembrete(a, clinic, send_at)
            db.execute_write(
                "UPDATE scheduler.appointments SET lembrete_status = 'ENFILEIRADO', lembrete_erro = NULL, updated_at = NOW() WHERE id = %s::uuid",
                (str(a["id"]),),
            )
    return {"enfileirados": len(sel["enfileiraveis"]), "ja_lembrados": sel["ja_lembrados"],
            "sem_telefone": sel["sem_telefone"], "enfileirados_antes": sel["enfileirados_antes"],
            "send_at": _iso_utc(send_at)}


def _com_e(partes: List[str]) -> str:
    partes = [p.strip() for p in partes if p and p.strip()]
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def variaveis_do_template(appt: Dict, clinic: Dict) -> Dict[str, str]:
    nome_completo = appt.get("full_name") or appt.get("patient_name") or ""
    dia = appt.get("appointment_date")
    dia = dia if hasattr(dia, "weekday") else datetime.strptime(str(dia)[:10], "%Y-%m-%d").date()
    hora = appt.get("start_time")
    hora_txt = hora.strftime("%H:%M") if hasattr(hora, "strftime") else str(hora)[:5]
    return {
        "nome": nome_completo.split(" ")[0] if nome_completo else "tudo bem",
        "areas": _com_e((appt.get("areas") or "").split(",")) or "depilação a laser",
        "clinic_name": clinic.get("display_name") or clinic.get("name") or "",
        "dia": f"{DIAS_PT[dia.weekday()]}, {dia.strftime('%d/%m')}",
        "hora": hora_txt,
    }
```

- [ ] **Passo 4: `reminder_service.agenda_lembrete`**, substituindo `schedule_reminder`:

```python
    def agenda_lembrete(self, appointment: Dict[str, Any], clinic: Dict[str, Any], send_at: datetime) -> Dict[str, Any]:
        """Um item na fila com o `sendAt` do LOTE (PRD 027). Quem decide o
        horario e o chamador; aqui so se grava."""
        reminder_id = str(uuid.uuid4())
        send_at_iso = send_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        item = {
            "pk": f"REMINDER#{reminder_id}", "sk": f"SEND_AT#{send_at_iso}",
            "reminderId": reminder_id, "appointmentId": str(appointment.get("id", "")),
            "clinicId": appointment.get("clinic_id", ""),
            "phoneNumber": appointment.get("patient_phone") or appointment.get("phone") or "",
            "patientName": appointment.get("full_name") or appointment.get("patient_name") or "",
            "reminderType": "LEMBRETE_SESSAO", "status": "PENDING", "sendAt": send_at_iso,
            "appointmentDate": str(appointment.get("appointment_date")),
            "appointmentTime": str(appointment.get("start_time")),
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.table.put_item(Item=item)
        logger.info(f"[ReminderService] Lembrete enfileirado: {reminder_id} appointment={item['appointmentId']} sendAt={send_at_iso}")
        return item
```

Remover `schedule_reminder` e, em `appointment_service.py`, os dois blocos `if self.reminder_service: ... schedule_reminder(...)` (criação e remarcação). Manter `cancel_reminder` e a chamada dele na remarcação. Rodar a suíte inteira (`python -m unittest discover tests/unit`) para pegar qualquer teste que citasse `schedule_reminder`.

- [ ] **Passo 5: rodar e commit** `feat(lembrete): lote do dia - selecao, send_at e enfileiramento`.

---

## Tarefa 5: Processador de entrega

**Arquivos:** modificar `scheduler/src/functions/reminder/processor.py`, `scheduler/sls/functions/reminder/interface.yml`; testar em `scheduler/tests/unit/test_reminder_processor.py`.

**Consome:** Tarefas 2 a 4; `atendimento.retoma_pelo_painel(sessao)`, `grava_atendimento(table, clinic_id, phone, sessao, extras)`, `abre_lembrete`, `porta_do_disparo.motivo_para_nao_iniciar`.

**Produz:** `handler(event, context)` com `event` vazio (cron) ou `{"clinicId": ...}` (invocação); função `entrega(reminder, deps, agora) -> str` que devolve `"enviado" | "adiado" | "falhou" | "descartado"`.

- [ ] **Passo 1: testes**

```python
# -*- coding: utf-8 -*-
"""O processador entrega o lembrete, grava o rastro no agendamento e abre a
sobreposicao. Cancelado e pulado; bot pausado falha; silencio adia; humano e
cooldown destravam (como o disparo em lote)."""
import os
import unittest
from datetime import date, datetime, time, timezone
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")
os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "t")

from src.functions.reminder import processor as P

CLINIC = {"clinic_id": "c1", "name": "Essencia", "display_name": "Essência", "timezone": "America/Sao_Paulo",
          "bot_paused": False, "custom_domain": "agendar.x.com.br", "janela_de_silencio": None, "active": True}
REM = {"reminderId": "r1", "appointmentId": "a1", "clinicId": "c1", "phoneNumber": "5511999990001",
       "patientName": "Maria", "pk": "REMINDER#r1", "sk": "SEND_AT#x", "reminderType": "LEMBRETE_SESSAO"}
APPT = {"id": "a1", "clinic_id": "c1", "status": "CONFIRMED", "appointment_date": date(2026, 11, 6),
        "start_time": time(9, 0), "full_name": "Maria Silva", "patient_phone": "5511999990001", "areas": "Axilas"}
MEIO_DIA = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)  # 12:00 BRT


class Deps:
    def __init__(self, appt=APPT, clinic=CLINIC, sessao=None, envio_ok=True):
        self.db = mock.MagicMock(); self.db.execute_query.side_effect = lambda sql, p=None: (
            [clinic] if "FROM scheduler.clinics" in sql else [appt] if appt else [])
        self.reminder_service = mock.MagicMock()
        self.template_service = mock.MagicMock(); self.template_service.get_and_render.return_value = "Oi Maria!"
        self.tracker = mock.MagicMock()
        self.provider = mock.MagicMock(); self.provider.send_text.return_value = mock.MagicMock(success=envio_ok, provider_message_id="pm", raw_response={}, error=None if envio_ok else "boom")
        self.sessao = sessao or {}
        self.tabela_sessoes = mock.MagicMock()
        self.abre_lembrete = mock.MagicMock(return_value=True)
        self.grava_atendimento = mock.MagicMock(return_value=True)


class TestEntrega(unittest.TestCase):
    def test_sucesso_grava_enviado_e_abre_sobreposicao(self):
        d = Deps()
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "enviado")
        sql = " ".join(d.db.execute_write.call_args[0][0].split())
        self.assertIn("lembrete_status = 'ENVIADO'", sql); self.assertIn("lembrete_enviado_em = NOW()", sql)
        d.abre_lembrete.assert_called_once()
        d.reminder_service.mark_sent.assert_called_once()

    def test_cancelado_e_descartado_e_limpa_status(self):
        d = Deps(appt=dict(APPT, status="CANCELLED"))
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "descartado")
        self.assertIn("lembrete_status = NULL", " ".join(d.db.execute_write.call_args[0][0].split()))
        d.provider.send_text.assert_not_called()

    def test_bot_pausado_falha_com_motivo(self):
        d = Deps(clinic=dict(CLINIC, bot_paused=True))
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "falhou")
        self.assertIn("bot pausado", d.db.execute_write.call_args[0][1])

    def test_silencio_adia_e_marca_adiado(self):
        madrugada = datetime(2026, 11, 6, 4, 0, tzinfo=timezone.utc)  # 01:00 BRT
        d = Deps()
        self.assertEqual(P.entrega(REM, d, madrugada), "adiado")
        d.reminder_service.adia.assert_called_once()
        self.assertIn("lembrete_status = 'ADIADO'", " ".join(d.db.execute_write.call_args[0][0].split()))

    def test_humano_destrava_e_envia(self):
        from src.services import atendimento
        sessao = {atendimento.CAMPO: {"handler": "HUMAN_ACTIVE", "human_until": int(MEIO_DIA.timestamp()) + 3600, "versao": 1}}
        d = Deps(sessao=sessao)
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "enviado")
        d.grava_atendimento.assert_called_once()

    def test_falha_do_provider(self):
        d = Deps(envio_ok=False)
        self.assertEqual(P.entrega(REM, d, MEIO_DIA), "falhou")
        d.reminder_service.mark_failed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

(Confirmar o nome do campo de estado dentro do bloco `atendimento` olhando `atendimento.estado`; ajustar o fixture `sessao` do teste de humano para o formato real.)

- [ ] **Passo 2: rodar e ver falhar.**

- [ ] **Passo 3: reescrever `processor.py`** mantendo a estrutura e extraindo `entrega`:

```python
# -*- coding: utf-8 -*-
"""Entrega os lembretes vencidos da fila (PRD 027).

Acordado por invocacao (botao do painel) e por cron horario (lotes
automaticos). Para cada item: recarrega o agendamento (cancelado e descartado),
confere a porta (bot pausado falha; silencio adia; humano e cooldown
destravam, como o disparo em lote), envia, grava `lembrete_*` no agendamento e
abre a sobreposicao de lembrete na sessao.
"""
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from src.providers.whatsapp_provider import get_provider
from src.services import atendimento, lembrete
from src.services.business_hours import fim_do_silencio
from src.services.db.postgres import PostgresService
from src.services.lembrete_da_agenda import variaveis_do_template
from src.services.message_tracker import MessageTracker
from src.services.porta_do_disparo import MOTIVOS_QUE_O_DISPARO_DESTRAVA, motivo_para_nao_iniciar
from src.services.reminder_service import ReminderService
from src.services.session_store import abre_lembrete, carrega_sessao, grava_atendimento
from src.services.template_service import TemplateService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MOTIVO_LEGIVEL = {"bot_da_clinica_pausado": "bot pausado", "janela_de_silencio": "fora do horário"}


def _marca(db, appointment_id, status, erro=None, enviado=False):
    db.execute_write(
        "UPDATE scheduler.appointments SET lembrete_status = %s, lembrete_erro = %s"
        + (", lembrete_enviado_em = NOW()" if enviado else "")
        + ", updated_at = NOW() WHERE id = %s::uuid",
        (status, erro, appointment_id),
    )


def _agendamento(db, appointment_id):
    linhas = db.execute_query(
        """SELECT a.*, p.phone AS patient_phone, p.name AS patient_name,
                  (SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at)
                     FROM scheduler.appointment_service_areas asa WHERE asa.appointment_id = a.id) AS areas
             FROM scheduler.appointments a LEFT JOIN scheduler.patients p ON p.id = a.patient_id
            WHERE a.id = %s::uuid""",
        (appointment_id,),
    )
    return linhas[0] if linhas else None


def entrega(reminder, deps, agora: datetime) -> str:
    rid, aid = reminder.get("reminderId", ""), reminder.get("appointmentId", "")
    clinic_id, phone = reminder.get("clinicId", ""), reminder.get("phoneNumber", "")
    pk, sk = reminder.get("pk", ""), reminder.get("sk", "")
    db, rs = deps.db, deps.reminder_service

    clinicas = db.execute_query("SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE", (clinic_id,))
    clinic = clinicas[0] if clinicas else None
    appt = _agendamento(db, aid) if aid else None
    if not clinic or not appt or appt.get("status") != "CONFIRMED":
        rs.mark_failed(rid, pk, sk, "agendamento_nao_confirmado")
        if aid:
            db.execute_write("UPDATE scheduler.appointments SET lembrete_status = NULL, updated_at = NOW() WHERE id = %s::uuid", (aid,))
        return "descartado"

    sessao = deps.sessao if hasattr(deps, "sessao") else carrega_sessao(clinic_id, phone)
    epoch = int(agora.timestamp())
    motivo = motivo_para_nao_iniciar(clinic, sessao, epoch)
    if motivo == "janela_de_silencio":
        novo = fim_do_silencio(clinic, agora).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rs.adia(pk, sk, novo, motivo)
        _marca(db, aid, "ADIADO")
        return "adiado"
    if motivo and motivo not in MOTIVOS_QUE_O_DISPARO_DESTRAVA:
        rs.mark_failed(rid, pk, sk, motivo)
        _marca(db, aid, "FALHOU", MOTIVO_LEGIVEL.get(motivo, motivo))
        return "falhou"

    content = deps.template_service.get_and_render(clinic_id, "LEMBRETE_SESSAO", variaveis_do_template(appt, clinic))
    msg_id, conversation_id = str(uuid.uuid4()), f"{clinic_id}#{phone}"
    deps.tracker.track_outbound(clinic_id=clinic_id, phone=phone, message_id=msg_id, conversation_id=conversation_id,
                                message_type="TEXT", content=content, status="QUEUED",
                                metadata={"reminderType": "LEMBRETE_SESSAO", "reminderId": rid, "appointmentId": aid})
    resp = deps.provider.send_text(phone, content)
    if not resp.success:
        deps.tracker.track_outbound(clinic_id=clinic_id, phone=phone, message_id=msg_id, conversation_id=conversation_id,
                                    message_type="TEXT", content=content, status="FAILED", metadata={"error": resp.error})
        rs.mark_failed(rid, pk, sk, resp.error or "Erro desconhecido")
        _marca(db, aid, "FALHOU", (resp.error or "erro de envio")[:120])
        return "falhou"

    deps.tracker.track_outbound(clinic_id=clinic_id, phone=phone, message_id=msg_id, conversation_id=conversation_id,
                                message_type="TEXT", content=content, status="SENT",
                                provider_message_id=resp.provider_message_id, provider_response=resp.raw_response)
    rs.mark_sent(rid, pk, sk)
    _marca(db, aid, "ENVIADO", enviado=True)

    # Depois do envio confirmado, como o disparo em lote: destrava e abre a
    # sobreposicao. Mensagem que nao saiu nao pode deixar o bot esperando.
    if motivo in MOTIVOS_QUE_O_DISPARO_DESTRAVA:
        atendimento.retoma_pelo_painel(sessao)
        sessao["bot_enabled"] = True
        deps.grava_atendimento(deps.tabela_sessoes, clinic_id, phone, sessao, extras={"bot_enabled": True})
    deps.abre_lembrete(deps.tabela_sessoes, clinic_id, phone, lembrete.abre(appt, clinic, epoch))
    return "enviado"


@dataclass
class _Deps:
    db: object; reminder_service: object; template_service: object; tracker: object
    provider: object; tabela_sessoes: object; abre_lembrete: object; grava_atendimento: object


def handler(event, context):
    trace_id = str(uuid.uuid4())[:8]
    logger.info(f"[traceId: {trace_id}] [ReminderProcessor] inicio")
    import boto3
    db = PostgresService()
    rs = ReminderService()
    agora = datetime.now(timezone.utc)
    pendentes = rs.get_pending_reminders(agora.strftime("%Y-%m-%dT%H:%M:%SZ"))
    tabela = boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"])
    contagem = {"enviado": 0, "adiado": 0, "falhou": 0, "descartado": 0}
    providers = {}
    for r in pendentes:
        try:
            cid = r.get("clinicId", "")
            if cid not in providers:
                c = db.execute_query("SELECT * FROM scheduler.clinics WHERE clinic_id = %s", (cid,))
                providers[cid] = get_provider(c[0]) if c else None
            deps = _Deps(db, rs, TemplateService(db), MessageTracker(), providers[cid], tabela, abre_lembrete, grava_atendimento)
            resultado = entrega(r, deps, agora)
        except Exception as e:
            logger.error(f"[traceId: {trace_id}] lembrete {r.get('reminderId')} falhou: {e}")
            rs.mark_failed(r.get("reminderId", ""), r.get("pk", ""), r.get("sk", ""), str(e)[:200])
            resultado = "falhou"
        contagem[resultado] += 1
    logger.info(f"[traceId: {trace_id}] [ReminderProcessor] {len(pendentes)} processados: {contagem}")
    return {"processed": len(pendentes), **contagem}
```

No teste, `Deps` tem `sessao`; em produção `_Deps` não tem e `entrega` carrega da tabela. Mantenha `hasattr` só nesse ponto, documentado.

- [ ] **Passo 4: interface.** Em `reminder/interface.yml`: `schedule` passa a `rate(60 minutes)`, `enabled: true`; IAM ganha `dynamodb:PutItem` e `dynamodb:UpdateItem` na tabela de sessões (abre sobreposição e destrava). `timeout: 120`.

- [ ] **Passo 5: rodar** `python -m unittest tests.unit.test_reminder_processor -v`. **Commit:** `feat(lembrete): processador entrega, grava rastro e abre sobreposicao`.

---

## Tarefa 6: Endpoint manual e Lambda automática

**Arquivos:** criar `scheduler/src/functions/appointment/lembretes_do_dia.py`, `scheduler/src/functions/reminder/automaticos.py`; modificar `scheduler/sls/functions/appointment/interface.yml`, `reminder/interface.yml`; testar em `scheduler/tests/unit/test_lembretes_do_dia.py`, `test_lembretes_automaticos.py`.

- [ ] **Passo 1: testes do endpoint**

```python
# -*- coding: utf-8 -*-
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t"); os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "t")

from src.functions.appointment import lembretes_do_dia as h
from src.utils.acesso import Identidade, STAFF

IDENT = Identidade(papel=STAFF, user_id="u1", clinic_id="c1")


def evento(dia, simular=False):
    return {"pathParameters": {"clinicId": "c1", "dia": dia}, "queryStringParameters": {"simular": "true"} if simular else None,
            "headers": {"x-api-key": "k"}, "body": None}


class TestEndpoint(unittest.TestCase):
    def chama(self, ev, resultado=None):
        with mock.patch.object(h, "require_acesso", return_value=(IDENT, None)), \
             mock.patch.object(h, "PostgresService") as db, \
             mock.patch.object(h, "ReminderService"), \
             mock.patch.object(h, "enfileira", return_value=resultado or {"enfileirados": 2, "ja_lembrados": 1, "sem_telefone": 0, "enfileirados_antes": 0, "send_at": "2026-11-05T12:00:00Z"}) as enf, \
             mock.patch.object(h, "_acorda_processador") as acorda, \
             mock.patch.object(h, "_hoje", return_value="2026-11-05"):
            db.return_value.execute_query.return_value = [{"clinic_id": "c1", "timezone": "America/Sao_Paulo", "custom_domain": "x.com", "janela_de_silencio": None}]
            return h.handler(ev, None), enf, acorda

    def test_simular_devolve_contagens_e_nao_acorda(self):
        r, enf, acorda = self.chama(evento("2026-11-06", simular=True))
        self.assertEqual(r["statusCode"], 200)
        self.assertTrue(enf.call_args.kwargs["simular"])
        acorda.assert_not_called()
        self.assertTrue(json.loads(r["body"])["tem_link_de_autoatendimento"])

    def test_real_enfileira_e_acorda(self):
        r, enf, acorda = self.chama(evento("2026-11-06"))
        self.assertEqual(json.loads(r["body"])["enfileirados"], 2)
        acorda.assert_called_once()

    def test_dia_passado_recusa(self):
        r, _, _ = self.chama(evento("2026-11-04"))
        self.assertEqual(r["statusCode"], 400)

    def test_dia_invalido_recusa(self):
        r, _, _ = self.chama(evento("06-11-2026"))
        self.assertEqual(r["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: implementar `lembretes_do_dia.py`**

```python
# -*- coding: utf-8 -*-
"""Lembrar a agenda de um dia, pelo botao do painel (PRD 027).

POST /clinics/{clinicId}/agenda/{dia}/lembretes[?simular=true]

`simular` devolve as contagens para a previa. Sem ele, enfileira o lote com
`send_at` = agora (ou o fim do silencio) e acorda o processador para a entrega
sair na hora, como IniciarConversaPeloBot faz com o OutboundProcessor.
"""
import json
import logging
import os
from datetime import datetime, timezone

from src.services.autoatendimento import link_de_autoatendimento
from src.services.business_hours import fuso
from src.services.db.postgres import PostgresService
from src.services.lembrete_da_agenda import enfileira, send_at_do_lote
from src.services.reminder_service import ReminderService
from src.utils.acesso import hoje_na_clinica, require_acesso
from src.utils.http import extract_path_param, extract_query_param, http_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _hoje(clinic):
    return hoje_na_clinica(clinic.get("timezone")).isoformat()


def _acorda_processador():
    import boto3
    nome = os.environ.get("REMINDER_PROCESSOR_FUNCTION_NAME")
    if not nome:
        logger.warning("[LembretesDoDia] REMINDER_PROCESSOR_FUNCTION_NAME ausente; o cron horario entrega")
        return
    boto3.client("lambda").invoke(FunctionName=nome, InvocationType="Event", Payload=json.dumps({}).encode())


def handler(event, context):
    try:
        identidade, erro = require_acesso(event, "agenda.escrever")
        if erro:
            return erro
        clinic_id = extract_path_param(event, "clinicId")
        dia = extract_path_param(event, "dia") or ""
        simular = (extract_query_param(event, "simular") or "").lower() in ("1", "true")
        try:
            datetime.strptime(dia, "%Y-%m-%d")
        except ValueError:
            return http_response(400, {"status": "ERROR", "message": "dia deve ser YYYY-MM-DD"})

        db = PostgresService()
        clinicas = db.execute_query("SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE", (clinic_id,))
        if not clinicas:
            return http_response(404, {"status": "ERROR", "message": "Clinica nao encontrada"})
        clinic = clinicas[0]
        if dia < _hoje(clinic):
            return http_response(400, {"status": "ERROR", "message": "Nao se lembra agenda de dia passado"})

        agora = datetime.now(timezone.utc)
        send_at = send_at_do_lote(clinic, agora)
        resultado = enfileira(db, ReminderService(), clinic, dia, send_at, simular=simular)
        resultado["adiados_para"] = resultado["send_at"] if send_at > agora else None
        resultado["tem_link_de_autoatendimento"] = link_de_autoatendimento(clinic) is not None
        if not simular and resultado["enfileirados"] > 0 and resultado["adiados_para"] is None:
            _acorda_processador()
        logger.info(f"[LembretesDoDia] {clinic_id} {dia} simular={simular}: {resultado}")
        return http_response(200, {"status": "SUCCESS", **resultado})
    except Exception as e:
        logger.error(f"Erro ao lembrar agenda: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
```

- [ ] **Passo 3: testes da automática**

```python
# -*- coding: utf-8 -*-
"""O lote automatico sai `antecedencia` horas antes do primeiro horario do dia,
uma vez por dia, e so para clinica com o interruptor ligado."""
import os
import unittest
from datetime import date, datetime, time, timezone
from unittest import mock

import pytz

os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "t")

from src.functions.reminder import automaticos as A

TZ = pytz.timezone("America/Sao_Paulo")
CLINIC = {"clinic_id": "c1", "timezone": "America/Sao_Paulo", "lembrete_automatico": True, "lembrete_antecedencia_horas": 24, "janela_de_silencio": None}


def appts(*horas):
    return [{"id": f"a{h}", "status": "CONFIRMED", "start_time": time(h, 0), "lembrete_enviado_em": None, "lembrete_status": None, "patient_phone": "551199"} for h in horas]


class TestDeveDisparar(unittest.TestCase):
    def test_antes_da_hora_nao(self):
        agora = TZ.localize(datetime(2026, 11, 5, 8, 59))
        self.assertIsNone(A.send_at_se_vencido(CLINIC, "2026-11-06", appts(9, 11), agora))

    def test_na_hora_sim(self):
        agora = TZ.localize(datetime(2026, 11, 5, 9, 0))
        self.assertIsNotNone(A.send_at_se_vencido(CLINIC, "2026-11-06", appts(9, 11), agora))

    def test_sem_agendamento_nao(self):
        agora = TZ.localize(datetime(2026, 11, 5, 12, 0))
        self.assertIsNone(A.send_at_se_vencido(CLINIC, "2026-11-06", [], agora))

    def test_vencido_dentro_do_silencio_vai_para_o_fim(self):
        clinic = dict(CLINIC, lembrete_antecedencia_horas=10)  # 9h - 10h = 23h do dia anterior
        agora = TZ.localize(datetime(2026, 11, 5, 23, 30))
        s = A.send_at_se_vencido(clinic, "2026-11-06", appts(9), agora)
        self.assertGreater(s, agora)


class TestHandler(unittest.TestCase):
    def test_so_clinica_ligada_e_so_uma_vez(self):
        db = mock.MagicMock()
        db.execute_query.side_effect = lambda sql, p=None: (
            [CLINIC, dict(CLINIC, clinic_id="c2", lembrete_automatico=False)] if "FROM scheduler.clinics" in sql
            else appts(9))
        agora = TZ.localize(datetime(2026, 11, 5, 10, 0)).astimezone(timezone.utc)
        with mock.patch.object(A, "PostgresService", return_value=db), mock.patch.object(A, "ReminderService"), \
             mock.patch.object(A, "enfileira", return_value={"enfileirados": 1}) as enf, mock.patch.object(A, "_agora", return_value=agora):
            r = A.handler({}, None)
        clinicas = {c.args[2]["clinic_id"] for c in enf.call_args_list}
        self.assertEqual(clinicas, {"c1"})
        self.assertEqual(r["lotes"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 4: implementar `automaticos.py`**

```python
# -*- coding: utf-8 -*-
"""Lotes automaticos de lembrete (PRD 027). Horario.

Para cada clinica com `lembrete_automatico`, olha hoje+1..hoje+3 e dispara o
dia inteiro quando `agora >= primeiro horario - antecedencia`. A selecao e por
agendamento sem lembrete, entao um encaixe de ultima hora e pego na proxima
rodada, e um dia ja lembrado nao repete.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from src.services.business_hours import fim_do_silencio, fuso
from src.services.db.postgres import PostgresService
from src.services.lembrete_da_agenda import enfileira, inicio_da_agenda
from src.services.reminder_service import ReminderService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DIAS_A_FRENTE = 3


def _agora():
    return datetime.now(timezone.utc)


def send_at_se_vencido(clinic: Dict, dia: str, appointments: List[Dict], agora: datetime) -> Optional[datetime]:
    pendentes = [a for a in appointments if a.get("status") == "CONFIRMED" and not a.get("lembrete_enviado_em") and a.get("lembrete_status") != "ENFILEIRADO"]
    inicio = inicio_da_agenda(pendentes)
    if inicio is None:
        return None
    tz = fuso(clinic)
    primeiro = tz.localize(datetime.combine(datetime.strptime(dia, "%Y-%m-%d").date(), inicio))
    send_at = primeiro - timedelta(hours=int(clinic.get("lembrete_antecedencia_horas") or 24))
    if agora < send_at:
        return None
    return fim_do_silencio(clinic, agora)


def handler(event, context):
    trace_id = str(uuid.uuid4())[:8]
    db = PostgresService()
    rs = ReminderService()
    agora = _agora()
    lotes = 0
    clinicas = db.execute_query("SELECT * FROM scheduler.clinics WHERE active = TRUE AND lembrete_automatico = TRUE")
    for clinic in clinicas:
        tz = fuso(clinic)
        hoje = agora.astimezone(tz).date()
        for n in range(1, DIAS_A_FRENTE + 1):
            dia = (hoje + timedelta(days=n)).isoformat()
            try:
                appts = db.execute_query(
                    """SELECT a.id, a.status, a.start_time, a.lembrete_enviado_em, a.lembrete_status, p.phone AS patient_phone
                         FROM scheduler.appointments a LEFT JOIN scheduler.patients p ON p.id = a.patient_id
                        WHERE a.clinic_id = %s AND a.appointment_date = %s AND a.status = 'CONFIRMED'""",
                    (clinic["clinic_id"], dia))
                send_at = send_at_se_vencido(clinic, dia, appts, agora)
                if send_at is None:
                    continue
                r = enfileira(db, rs, clinic, dia, send_at)
                lotes += 1 if r["enfileirados"] else 0
                logger.info(f"[traceId: {trace_id}] {clinic['clinic_id']} {dia}: {r}")
            except Exception as e:
                logger.error(f"[traceId: {trace_id}] {clinic['clinic_id']} {dia} falhou: {e}")
    return {"traceId": trace_id, "clinicas": len(clinicas), "lotes": lotes}
```

- [ ] **Passo 5: interfaces.** Em `appointment/interface.yml`:

```yaml
LembretesDoDia:
  handler: src.functions.appointment.lembretes_do_dia.handler
  memorySize: 512
  timeout: 60
  environment:
    REMINDER_PROCESSOR_FUNCTION_NAME: ${self:service}-${self:custom.stage}-ReminderProcessor
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-LembretesDoDia-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action: [dynamodb:PutItem]
      Resource:
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-scheduled-reminders"
    # Acorda o processador: a atendente clica e olha a tela.
    - Effect: Allow
      Action: [lambda:InvokeFunction]
      Resource:
        - "arn:aws:lambda:${self:provider.region}:${self:custom.accountId}:function:${self:service}-${self:custom.stage}-ReminderProcessor"
    - Effect: Allow
      Action: [logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents]
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: clinics/{clinicId}/agenda/{dia}/lembretes
        method: post
        cors: true
```

Em `reminder/interface.yml`, acrescentar:

```yaml
LembretesAutomaticos:
  handler: src.functions.reminder.automaticos.handler
  memorySize: 512
  timeout: 120
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-LembretesAutomaticos-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action: [dynamodb:PutItem]
      Resource:
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-scheduled-reminders"
    - Effect: Allow
      Action: [logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents]
      Resource: "arn:aws:logs:*:*:*"
  events:
    # De hora em hora, no minuto 5; o processador roda no minuto 0 da hora
    # seguinte e entrega. Precisao de uma hora basta para "antecedencia".
    - schedule:
        rate: cron(5 * * * ? *)
        enabled: true
```

Conferir o limite de recursos do stack (memória `project_divida_limite_cloudformation`: dev e prod em 435/500); duas funções novas somam ~10 recursos. Cabe.

- [ ] **Passo 6: rodar** os dois testes. **Commit:** `feat(lembrete): endpoint manual com previa e Lambda horaria automatica`.

---

## Tarefa 7: Confirmação pela equipe e campos na agenda

**Arquivos:** modificar `scheduler/src/functions/appointment/update.py`, `scheduler/src/functions/appointment/list.py`, `scheduler/src/functions/clinic/update.py`; testar em `scheduler/tests/unit/test_confirmacao_pela_equipe.py`.

- [ ] **Passo 1: testes**

```python
# -*- coding: utf-8 -*-
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("SCHEDULED_REMINDERS_TABLE", "t")

from src.functions.appointment import update as h
from src.utils.acesso import Identidade, STAFF

IDENT = Identidade(papel=STAFF, user_id="u1", clinic_id="c1")


def evento(body):
    return {"pathParameters": {"appointmentId": "a1"}, "headers": {"x-api-key": "k"}, "body": json.dumps(body)}


class TestConfirmado(unittest.TestCase):
    def chama(self, body):
        db = mock.MagicMock()
        db.execute_query.return_value = [{"id": "a1", "clinic_id": "c1", "status": "CONFIRMED"}]
        db.execute_write_returning.return_value = {"id": "a1", "confirmado_em": "2026-11-05T12:00:00Z", "confirmado_por": "EQUIPE"}
        with mock.patch.object(h, "require_acesso", return_value=(IDENT, None)), \
             mock.patch.object(h, "PostgresService", return_value=db), \
             mock.patch.object(h, "pode_tocar_agendamento", return_value=True):
            return h.handler(evento(body), None), db

    def test_confirma_grava_equipe(self):
        r, db = self.chama({"confirmado": True})
        self.assertEqual(r["statusCode"], 200)
        sql = " ".join(db.execute_write_returning.call_args[0][0].split())
        self.assertIn("confirmado_por = 'EQUIPE'", sql)

    def test_desconfirma_limpa(self):
        r, db = self.chama({"confirmado": False})
        sql = " ".join(db.execute_write_returning.call_args[0][0].split())
        self.assertIn("confirmado_em = NULL", sql)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: `update.py`**, logo depois do parse do body e antes dos outros campos:

```python
        # Confirmacao de presenca (PRD 027). Coluna, nao status: nao mexe em
        # horario nem em conversao. Vem sozinha no body, e e tratada aqui.
        if "confirmado" in body and len(body) == 1:
            if body["confirmado"]:
                sql = ("UPDATE scheduler.appointments SET confirmado_em = NOW(), confirmado_por = 'EQUIPE', "
                       "updated_at = NOW() WHERE id = %s::uuid AND status = 'CONFIRMED' RETURNING *")
            else:
                sql = ("UPDATE scheduler.appointments SET confirmado_em = NULL, confirmado_por = NULL, "
                       "updated_at = NOW() WHERE id = %s::uuid RETURNING *")
            db = PostgresService()
            result = db.execute_write_returning(sql, (appointment_id,))
            if not result:
                return http_response(404, {"status": "ERROR", "message": "Agendamento nao encontrado ou nao confirmado"})
            return http_response(200, para_o_staff(identidade, {"status": "SUCCESS", "appointment": _serialize_row(result)}))
```

Encaixar respeitando a verificação `pode_tocar_agendamento` que o handler já faz para STAFF (ler o trecho e colocar o bloco depois dela).

- [ ] **Passo 3: `list.py`**, acrescentar ao SELECT: `a.lembrete_enviado_em, a.lembrete_status, a.lembrete_erro, a.confirmado_em, a.confirmado_por,`.

- [ ] **Passo 4: `clinic/update.py`**, `ALLOWED_FIELDS` ganha `"lembrete_automatico"`, `"lembrete_antecedencia_horas"`. Validar `1 <= lembrete_antecedencia_horas <= 72` com 400 fora disso.

- [ ] **Passo 5: rodar** e **commit** `feat(lembrete): confirmacao pela equipe, campos na agenda e configuracao da clinica`.

---

## Tarefa 8: Frontend - tipos, service, hooks

**Arquivos:** modificar `frontend/src/types/index.ts`, `frontend/src/services/appointments.service.ts`, `frontend/src/hooks/useAppointments.ts`; testar em `frontend/src/services/appointments.service.test.ts` (criar se não houver).

- [ ] **Passo 1: tipos.** Em `Appointment`:

```ts
  /** Rastro do lembrete de sessao (PRD 027). null = nunca enfileirado. */
  lembrete_enviado_em: string | null
  lembrete_status: 'ENFILEIRADO' | 'ADIADO' | 'ENVIADO' | 'FALHOU' | null
  lembrete_erro: string | null
  /** Presenca confirmada pela pessoa (bot) ou pela equipe (popover). */
  confirmado_em: string | null
  confirmado_por: 'PACIENTE' | 'EQUIPE' | null
```

Em `Clinic` e `UpdateClinicPayload`: `lembrete_automatico: boolean` / `?: boolean` e `lembrete_antecedencia_horas: number` / `?: number`. Novo:

```ts
export interface LembretesDoDiaResponse {
  status: string
  enfileirados: number
  ja_lembrados: number
  sem_telefone: number
  enfileirados_antes: number
  send_at: string
  /** ISO quando o lote caiu na janela de silencio; null quando sai agora. */
  adiados_para: string | null
  tem_link_de_autoatendimento: boolean
}
```

- [ ] **Passo 2: service**

```ts
  /** Previa ou disparo do lembrete da agenda do dia (PRD 027). */
  lembrarAgendaDoDia(clinicId: string, dia: string, simular: boolean) {
    return api
      .post<LembretesDoDiaResponse>(`/clinics/${clinicId}/agenda/${dia}/lembretes`, null, { params: simular ? { simular: 'true' } : undefined })
      .then((r) => r.data)
  },

  confirmarPresenca(appointmentId: string, confirmado: boolean) {
    return api.put(`/appointments/${appointmentId}`, { confirmado }).then((r) => r.data)
  },
```

- [ ] **Passo 3: hooks**

```ts
export function useLembrarAgendaDoDia() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ dia, simular }: { dia: string; simular: boolean }) =>
      appointmentsService.lembrarAgendaDoDia(clinicId!, dia, simular),
    onSuccess: (_, { simular }) => { if (!simular) invalidaAgenda(queryClient) },
  })
}

export function useConfirmarPresenca() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ appointmentId, confirmado }: { appointmentId: string; confirmado: boolean }) =>
      appointmentsService.confirmarPresenca(appointmentId, confirmado),
    onSuccess: () => invalidaAgenda(queryClient),
  })
}
```

- [ ] **Passo 4: teste do service** (mock de `api` como os outros arquivos `.service.test.ts`): `lembrarAgendaDoDia` com `simular` manda `params.simular = 'true'`; sem, não manda params; `confirmarPresenca` faz PUT com `{ confirmado: true }`.

- [ ] **Passo 5: rodar** `npm run test -- appointments.service && npm run lint`. **Commit:** `feat(lembrete): tipos, service e hooks do lembrete e da confirmacao`.

---

## Tarefa 9: Frontend - agenda

**Arquivos:** criar `frontend/src/pages/agenda/components/LembrarAgendaDoDia.tsx` e `.test.tsx`; modificar `AgendaHeader.tsx`, `AgendaPage.tsx`, `AgendaDoDia.tsx`, `WeekGrid.tsx`, `AppointmentPopover.tsx`.

- [ ] **Passo 1: `LembrarAgendaDoDia.tsx`** (prévia inline, sem modal)

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useLembrarAgendaDoDia } from '@/hooks/useAppointments'
import type { LembretesDoDiaResponse } from '@/types'

interface LembrarAgendaDoDiaProps {
  dia: string
  disabled?: boolean
}

function horaLocal(iso: string) {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Botao com previa: primeiro conta, depois envia. A previa evita o clique
 * duplo e diz a atendente o que o bot vai fazer se alguem pedir para cancelar.
 */
export function LembrarAgendaDoDia({ dia, disabled }: LembrarAgendaDoDiaProps) {
  const [previa, setPrevia] = useState<LembretesDoDiaResponse | null>(null)
  const [resultado, setResultado] = useState<LembretesDoDiaResponse | null>(null)
  const lembrar = useLembrarAgendaDoDia()

  const abrirPrevia = () => lembrar.mutate({ dia, simular: true }, { onSuccess: (r) => { setPrevia(r); setResultado(null) } })
  const confirmar = () => lembrar.mutate({ dia, simular: false }, { onSuccess: (r) => { setResultado(r); setPrevia(null) } })
  const fechar = () => { setPrevia(null); setResultado(null) }

  return (
    <div className="relative">
      <Button variant="secondary" onClick={abrirPrevia} disabled={disabled || lembrar.isPending} loading={lembrar.isPending && !previa}>
        Lembrar agenda do dia
      </Button>

      {lembrar.isError && <p role="alert" className="mt-2 text-sm text-red-600">Não foi possível preparar o lembrete. Tente de novo.</p>}

      {previa && (
        <div role="dialog" aria-label="Confirmar lembrete" className="absolute right-0 z-20 mt-2 w-80 rounded-xl border border-gray-200 bg-white p-4 shadow-lg flex flex-col gap-3 text-sm">
          <p className="text-gray-800">
            <strong>{previa.enfileirados}</strong> para lembrar
            {previa.ja_lembrados > 0 && <>, {previa.ja_lembrados} já lembrado{previa.ja_lembrados > 1 ? 's' : ''}</>}
            {previa.sem_telefone > 0 && <>, {previa.sem_telefone} sem telefone</>}.
          </p>
          <p className="text-gray-500">
            {previa.tem_link_de_autoatendimento
              ? 'Se alguém pedir para cancelar ou remarcar, o bot envia o link do site.'
              : 'Esta clínica não tem site: o bot cancela e remarca pela conversa.'}
          </p>
          {previa.adiados_para && <p className="text-amber-700">Fora do horário: saem às {horaLocal(previa.adiados_para)}.</p>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={fechar}>Cancelar</Button>
            <Button size="sm" onClick={confirmar} disabled={previa.enfileirados === 0} loading={lembrar.isPending}>
              Enviar para {previa.enfileirados}
            </Button>
          </div>
        </div>
      )}

      {resultado && (
        <p role="status" className="mt-2 text-sm text-emerald-700">
          {resultado.enfileirados} lembrete{resultado.enfileirados > 1 ? 's' : ''}
          {resultado.adiados_para ? ` saem às ${horaLocal(resultado.adiados_para)}` : ' a caminho'}.
          <button type="button" onClick={fechar} className="ml-2 underline cursor-pointer">ok</button>
        </p>
      )}
    </div>
  )
}
```

- [ ] **Passo 2: teste**

```tsx
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { LembrarAgendaDoDia } from './LembrarAgendaDoDia'

const mutate = vi.fn()
vi.mock('@/hooks/useAppointments', () => ({ useLembrarAgendaDoDia: () => ({ mutate, isPending: false, isError: false }) }))

const previa = { status: 'SUCCESS', enfileirados: 8, ja_lembrados: 3, sem_telefone: 1, enfileirados_antes: 0, send_at: 'x', adiados_para: null, tem_link_de_autoatendimento: true }

describe('LembrarAgendaDoDia', () => {
  it('mostra a previa e envia com o numero certo', () => {
    mutate.mockImplementation((vars: { simular: boolean }, opts: { onSuccess: (r: unknown) => void }) => opts.onSuccess(vars.simular ? previa : { ...previa, enfileirados: 8 }))
    render(<LembrarAgendaDoDia dia="2026-11-06" />)
    fireEvent.click(screen.getByRole('button', { name: 'Lembrar agenda do dia' }))
    expect(screen.getByText(/3 já lembrados/)).toBeInTheDocument()
    expect(screen.getByText(/envia o link do site/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Enviar para 8' }))
    expect(mutate).toHaveBeenLastCalledWith({ dia: '2026-11-06', simular: false }, expect.anything())
    expect(screen.getByRole('status')).toHaveTextContent('8 lembretes a caminho')
  })

  it('avisa quando o lote foi adiado', () => {
    mutate.mockImplementation((_v: unknown, opts: { onSuccess: (r: unknown) => void }) => opts.onSuccess({ ...previa, adiados_para: '2026-11-06T11:00:00Z' }))
    render(<LembrarAgendaDoDia dia="2026-11-06" />)
    fireEvent.click(screen.getByRole('button', { name: 'Lembrar agenda do dia' }))
    expect(screen.getByText(/Fora do horário/)).toBeInTheDocument()
  })
})
```

- [ ] **Passo 3: `AgendaHeader`** ganha a prop opcional `diaParaLembrar?: string | null` e `podeLembrar?: boolean`; renderiza `<LembrarAgendaDoDia dia={diaParaLembrar} disabled={!podeLembrar} />` à esquerda de "+ Novo agendamento" quando `diaParaLembrar` existe. Em `AgendaPage`, passar `diaParaLembrar={diaUnico}` (o dia expandido) e `podeLembrar={diaUnico >= todayStr() && permissoes.agenda_escrever}` conforme o helper de permissão que a página já usa para "Novo agendamento".

- [ ] **Passo 4: badges.** Em `AgendaDoDia.tsx` e `WeekGrid.tsx`, ao lado do nome, quando `a.lembrete_enviado_em`:

```tsx
{a.lembrete_enviado_em && (
  <span className={a.confirmado_em
    ? 'rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700'
    : 'rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700'}>
    {a.confirmado_em ? 'CONFIRMADO' : 'PENDENTE'}
  </span>
)}
```

Extrair para `ConfirmacaoBadge.tsx` no mesmo diretório, usado nos dois lugares (padrão repetido 2 vezes).

- [ ] **Passo 5: `AppointmentPopover`.** Props novas `onConfirmar(a)`, `onDesconfirmar(a)`. Linha de estado do lembrete:

```tsx
<p className="text-xs text-gray-500">
  {a.lembrete_status === 'ENVIADO' && a.lembrete_enviado_em && `Lembrete enviado às ${new Date(a.lembrete_enviado_em).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`}
  {a.lembrete_status === 'ADIADO' && 'Lembrete aguardando o horário de envio'}
  {a.lembrete_status === 'ENFILEIRADO' && 'Lembrete a caminho'}
  {a.lembrete_status === 'FALHOU' && `Lembrete falhou: ${a.lembrete_erro ?? 'erro'}`}
  {!a.lembrete_status && 'Lembrete não enviado'}
</p>
```

Ações (só `status === 'CONFIRMED'`): "Marcar como confirmado" quando `!a.confirmado_em`, "Desfazer confirmação" quando tem. Em `AgendaPage`, ligar a `useConfirmarPresenca`.

- [ ] **Passo 6: rodar** `npm run test && npm run lint && npm run build`. **Commit:** `feat(lembrete): botao com previa, badges Pendente/Confirmado e acoes no popover`.

---

## Tarefa 10: Frontend - configurações

**Arquivos:** modificar `frontend/src/pages/configuracoes/ConfiguracoesPage.tsx`; teste em `ConfiguracoesPage.test.tsx` (existente ou novo).

- [ ] **Passo 1:** no `form` inicial, `lembrete_automatico: clinic.lembrete_automatico ?? false`, `lembrete_antecedencia_horas: clinic.lembrete_antecedencia_horas ?? 24`. Nova `Section`:

```tsx
<Section title="Lembrete de sessão" description="Lembra quem tem sessão marcada. O texto não menciona cancelamento de propósito; o bot envia o link do site só se a pessoa pedir.">
  <div className="flex items-center justify-between gap-4">
    <span className="text-sm text-gray-700">Enviar automaticamente</span>
    <Switch checked={form.lembrete_automatico as boolean} onChange={(v) => set('lembrete_automatico', v)} aria-label="Enviar lembrete automaticamente" />
  </div>
  <NumberField label="Antecedência (horas) em relação ao primeiro horário do dia" value={form.lembrete_antecedencia_horas as number} min={1} max={72} onChange={(v) => set('lembrete_antecedencia_horas', v)} />
  <TemplateField
    templateKey="LEMBRETE_SESSAO"
    label="Texto do lembrete"
    help="Use {{nome}}, {{areas}}, {{clinic_name}}, {{dia}} e {{hora}}."
  />
</Section>
```

`NumberField` é o mesmo componente que `buffer_minutes` usa (confira o nome real na página). `TemplateField` edita `message_templates` da clínica via o hook de templates que a página de Bot/FAQ já usa para `AI_SYSTEM_PROMPT` ou `POST_BOOKING_INSTRUCTIONS`; se não houver um componente reutilizável, criar `frontend/src/components/TemplateField.tsx` sobre o service de templates existente, com textarea, botão Salvar e pré-visualização renderizando as variáveis com dados de exemplo (`nome: Maria`, `areas: Axilas e Virilha Completa`, `dia: sexta, 06/11`, `hora: 09:00`).

- [ ] **Passo 2: teste**: a seção aparece, mudar o switch chama `set` com `lembrete_automatico`, valor fora de 1..72 mostra erro do campo.

- [ ] **Passo 3: rodar** e **commit** `feat(lembrete): configuracao do lembrete automatico e do texto`.

---

## Tarefa 11: Deploy em dev, E2E e documentação

- [ ] **Passo 1:** migration em dev (Tarefa 1) e `cd scheduler && npx serverless deploy --stage dev --aws-profile dev-andre`. Ler a saída.
- [ ] **Passo 2:** no painel apontando para dev, criar 3 agendamentos para amanhã com números de teste (um em conversa humana para testar o destravar). Clicar "Lembrar agenda do dia": prévia mostra 3; enviar; em até 1 minuto as mensagens chegam. Segundo clique: prévia mostra "3 já lembrados", botão desabilitado.
- [ ] **Passo 3:** responder "preciso remarcar" em um número: o bot manda o link e nada muda na agenda. Responder "ok" em outro: badge vira Confirmado. Num terceiro, no popover, "Marcar como confirmado" e "Desfazer".
- [ ] **Passo 4:** cancelar um agendamento depois de enfileirado (clicar às 23h para cair em ADIADO, cancelar, esperar o cron): o lembrete não sai e `lembrete_status` volta a NULL.
- [ ] **Passo 5:** ligar `lembrete_automatico` na clínica de dev com antecedência que caia na próxima hora, criar agendamento para amanhã e conferir que o cron enfileira e o processador entrega.
- [ ] **Passo 6:** prod: migration, deploy (nunca em paralelo com dev), conferir que `REMINDER_24H` não existe em `message_templates` de prod (não existe, conforme memória), botão disponível, `lembrete_automatico` desligado para todas.
- [ ] **Passo 7:** `tests/integration/027-lembrete-de-sessao.md`, `tests/postman/027-lembrete-de-sessao.postman_requests.json`, Status do PRD 027 e `TASKS_LOG.md`. Abrir o PR.

---

## Autorrevisão

- **Cobertura do PRD:** dados e template (T1), link e porta (T2), sobreposição, filtro e `confirm_attendance` (T3), lote e `send_at` (T4), processador com destravar e sobreposição (T5), endpoint manual e automático (T6), confirmação pela equipe, campos e config (T7), painel (T8 a T10), E2E e prod (T11). Critérios de aceite do PRD, cada um tem teste nas tarefas 1, 3, 4, 5, 6 ou 7, mais o E2E.
- **Nomes cruzados:** `link_de_autoatendimento`, `motivo_para_nao_iniciar`, `MOTIVOS_QUE_O_DISPARO_DESTRAVA`, `lembrete.abre/esta_vivo/appointment_id/ferramentas_a_remover/ferramentas_a_liberar/bloco_de_prompt`, `abre_lembrete`, `seleciona/enfileira/inicio_da_agenda/send_at_do_lote/variaveis_do_template`, `agenda_lembrete`, `entrega`, `send_at_se_vencido`, `lembrarAgendaDoDia/confirmarPresenca`, `useLembrarAgendaDoDia/useConfirmarPresenca` iguais em todas as tarefas.
- **Verificações ao implementar** (não placeholders): nome da variável da clínica no escopo do agente; `ctx["session"]` chegando ao `ToolExecutor`; formato real do bloco `atendimento` na sessão para o fixture do teste de humano; nomes de `NumberField`/`Switch`/hook de templates na página de configurações; helper de permissão de escrita em `AgendaPage`.
