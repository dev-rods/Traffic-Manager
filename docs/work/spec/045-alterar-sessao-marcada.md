# Spec - 045 Alterar uma sessão marcada é editar, nunca marcar outra

> Gerada em 09/11/2026 a partir de `prd/045-alterar-sessao-marcada.md`.
> Decisões do André: **§7.1 A** (mantém o horário; só move se não couber ou
> se ela pedir), **§7.2 A** (`alterar_agendamento` substitui
> `reschedule_appointment`), **§7.3 A** (alterar áreas fica no bot durante o
> lembrete; remarcar/cancelar seguem pelo link), **§7.4 A** (a campanha
> continua destravando; fica como achado).

---

## 1. O que muda, em uma frase

Para quem já tem sessão marcada, a agenda do bot deixa de contar a vaga dela
como ocupada, o modelo ganha uma tool que **edita** essa sessão (áreas, data,
hora), `book_appointment` recusa criar uma segunda sem a pessoa ter dito que
quer duas, e o prompt ganha o galho que descreve exatamente isso.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/services/availability_engine.py` | `excluindo(appointment_id)` - uma cópia do engine com `ignorar_agendamento` |
| `scheduler/src/services/ai_tools.py` | engine por turno (§3); tool `alterar_agendamento` no lugar de `reschedule_appointment` (§4); recusa em `book_appointment` (§5); áreas no `lookup_appointments` (§6) |
| `scheduler/src/services/identificacao_de_paciente.py` | `agendamento_futuro` ganha `areas` (§6) |
| `scheduler/src/services/estado_comercial.py` | QUEM É mostra as áreas; a linha "pergunte as áreas desta sessão" sai quando há horário futuro (§6) |
| `scheduler/src/services/roteador.py` | `tools_obrigatorias` pré-carrega `lookup_appointments` por estado (§6) |
| `scheduler/src/services/skills/__init__.py` | `TOOLS_DE_SESSAO_MARCADA` com o nome novo; bloco de `PACIENTE_COM_HORARIO` aponta para o galho 2b (§7) |
| `scheduler/src/services/lembrete.py` | `FERRAMENTAS_DE_SAIDA` perde a tool de remarcar e ganha `cancel_appointment` só; §7.3 A (§8) |
| `scheduler/src/services/conversation_agent.py` | `TOOLS_COM_EFEITO` e `TOOLS_QUE_MARCAM_SESSAO` com o nome novo |
| `scheduler/src/scripts/insere_galho_sessao_marcada.py` | **novo** - o galho 2b no `AI_SYSTEM_PROMPT` das duas clínicas, idempotente (§7) |
| `scheduler/src/services/template_service.py` | o mesmo galho no default do código (é o prompt de dev) |
| `scheduler/tests/unit/test_engine_exclui_a_propria_sessao.py` | **novo** |
| `scheduler/tests/unit/test_alterar_agendamento.py` | **novo** - a tool, em cada combinação |
| `scheduler/tests/unit/test_book_recusa_segunda_sessao.py` | **novo** |
| `scheduler/tests/unit/test_guarda_alterar_sessao.py` | **novo** - o laço do agente nos dois casos reais, dublados |
| testes existentes que citam `reschedule_appointment` como **nome de tool** (`test_skills`, `test_lembrete_no_agente`, `test_agente_nao_inventa`, `test_aviso_sai_apos_agendar`, `test_orientacoes_pos_sessao`, `test_reagendar_limpa_confirmacao`) | o nome troca; o método de serviço `AppointmentService.reschedule_appointment` **não** muda de nome |

Nenhuma migration.

---

## 3. A agenda exclui a sessão da paciente

### `availability_engine.py`

```python
def excluindo(self, appointment_id):
    """O mesmo engine, sem contar `appointment_id` como ocupado.

    Nova instância, não mutação: o engine do bot é compartilhado entre
    turnos (nasce em agent_runner.montar_agente) e dois turnos não podem
    disputar o mesmo atributo.
    """
    return AvailabilityEngine(self.db, ignorar_agendamento=appointment_id)
```

`janelas_livres` já lê `self.ignorar_agendamento`; nada mais muda no engine.

### `ai_tools.py`

Um só lugar decide qual engine o turno usa:

```python
def _engine_de(self, ctx):
    """A agenda vista pela pessoa deste turno: sem a sessão dela.

    `agendamento_futuro` vem de identificar_paciente e está em todo ctx.
    Para quem não tem sessão, é o engine como sempre.
    """
    futuro = ((ctx or {}).get("paciente") or {}).get("agendamento_futuro") or {}
    if futuro.get("id"):
        return self.availability_engine.excluindo(futuro["id"])
    return self.availability_engine
```

As três consultas passam a chamar `self._engine_de(ctx)`:
`_tool_check_availability` (`get_available_days_multi`), `_horarios`
(`get_available_slots_multi` e `cabe_no_horario`).

Por que pelo `ctx` e não pelo argumento da tool: o modelo não precisa saber
que isso existe. A exclusão é um fato sobre quem está na conversa, não uma
escolha dele.

---

## 4. A tool `alterar_agendamento`

Substitui `reschedule_appointment` (§7.2 A). Definição:

```
alterar_agendamento
  "Edita a sessão que a pessoa JÁ TEM: as áreas, a data, a hora, ou os três.
   Use para qualquer mudança numa sessão marcada. Nunca use book_appointment
   para isso: ele cria uma segunda sessão e deixa a primeira na agenda.
   Chame lookup_appointments antes para ter o appointment_id."
  appointment_id        string, obrigatório
  service_area_pairs    lista de {service_id, area_id}, opcional - as áreas
                        COMPLETAS da sessão depois da mudança, não só as que
                        mudam
  new_date              YYYY-MM-DD, opcional
  new_time              HH:MM, opcional
```

Pelo menos um dos três opcionais tem de vir, senão `{"error": "nada_a_alterar"}`.

### Execução

```
1. _barra_areas_nao_conversadas(args)      # a mesma trava do book
2. _troca_por_combos(args)                 # idem
3. atual = appointment_service.get_by_id(appointment_id)   # CONFIRMED, da mesma clínica
   se não existe → {"error": "agendamento_nao_encontrado"}
4. se service_area_pairs:
     appointment_service.update_appointment_services(
         appointment_id,
         service_id = pares[0]["service_id"],
         service_area_pairs = [{"serviceId": p["service_id"], "areaId": p["area_id"]} ...],
         verificar_conflito = not (new_date or new_time))
     # a mesma ordem e a mesma regra do painel (appointment/update.py):
     # áreas antes, porque mudam a duração; conflito só contra a data final
5. se new_date ou new_time:
     appointment_service.reschedule_appointment(
         appointment_id,
         new_date or atual.date, new_time or atual.time)
6. devolve a sessão como ficou:
     {"success": True, "appointment_id", "date", "date_label", "time",
      "areas": [...nomes...], "duration_minutes", "final_price_cents",
      "horario_mantido": bool}
```

O mapa `service_id → serviceId` no passo 4 existe porque
`update_appointment_services` fala o dialeto do painel (camelCase) e as tools
do bot falam snake_case. Fica dentro da tool, num só lugar.

`ConflictError` no passo 4 ou 5 volta como
`{"error": "nao_cabe", "o_que_fazer": "as áreas novas não cabem em <hora>
neste dia; chame get_time_slots com as áreas novas e ofereça primeiro o
horário mais próximo no MESMO dia"}`. O `get_time_slots` desse próximo turno já
exclui a sessão dela (§3), então "o mais próximo" inclui o horário atual quando
ele cabe.

### Logs

```
[Alteracao] <phone>: sessão <id> áreas "<antes>" -> "<depois>", horário mantido
[Alteracao] <phone>: sessão <id> movida 2026-11-18 14:50 -> 2026-11-19 15:25
[Alteracao] <phone>: sessão <id> não cabe em <data> <hora> com as áreas novas
```

### Onde o nome antigo era citado

`TOOLS_COM_EFEITO`, `TOOLS_QUE_MARCAM_SESSAO` (`conversation_agent.py`),
`TOOLS_DE_SESSAO_MARCADA` (`skills`), `FERRAMENTAS_DE_SAIDA` (`lembrete`, ver
§8). O método `AppointmentService.reschedule_appointment` e a rota do site
(`public_booking/reschedule_appointment.py`) **não** mudam.

---

## 5. `book_appointment` não cria uma segunda sessão em silêncio

Em `_tool_book_appointment`, antes da trava de áreas:

```python
futuro = ((ctx or {}).get("paciente") or {}).get("agendamento_futuro") or {}
if futuro.get("id") and not args.get("segunda_sessao"):
    logger.info(f"[Alteracao] {phone}: book_appointment recusado, sessão futura {futuro['id']}")
    return {
        "error": "ja_tem_sessao_marcada",
        "sessao": {"appointment_id": futuro["id"], "date": futuro["data"],
                   "time": futuro["hora"], "areas": futuro.get("areas")},
        "o_que_fazer": (
            "Esta pessoa já tem sessão marcada (acima). Se ela quer MUDAR essa "
            "sessão - áreas, dia ou hora -, chame alterar_agendamento. Só se "
            "ela disser, com todas as letras, que quer OUTRA sessão além dessa, "
            "chame book_appointment de novo com segunda_sessao=true e diga a "
            "ela que a primeira continua marcada."
        ),
    }
```

`segunda_sessao` (boolean, opcional) entra na definição de `book_appointment`
com a descrição: "true SOMENTE depois de a pessoa confirmar que quer uma
segunda sessão além da que já tem". É o registro, no rastro da tool, de que a
duplicidade foi pedida.

O mesmo padrão de `full_name_obrigatorio`: a tool explica, o modelo refaz.

---

## 6. O modelo passa a saber o que ela tem marcado

- `identificacao_de_paciente.py`: o `json_build_object` de `agendamento_futuro`
  ganha `'areas', (SELECT string_agg(area_name, ', ' ORDER BY created_at)
  FROM scheduler.appointment_service_areas WHERE appointment_id = a.id)`.
- `estado_comercial.bloco`: a linha vira
  `Próximo horário marcado: 18/11 às 14:50 - Axilas, Buço, Linha alba.`
  (data em dd/mm, para o modelo não copiar ISO para a pessoa); e a linha "As
  áreas desta sessão você pergunta e confirma com ela" só entra quando
  **não** há `agendamento_futuro` - para `ACTIVE_CUSTOMER` com horário quem
  manda é a skill (§7).
- `_tool_lookup_appointments`: cada item ganha `areas` (de `areas_display`),
  `duration_minutes` (`total_duration_minutes`) e `final_price_cents`.
- `roteador.tools_obrigatorias(intencoes, estado_comercial)`: para
  `FIRST_BOOKING` e `ACTIVE_CUSTOMER`, `lookup_appointments` entra sempre,
  depois de `identificar_paciente`. O chamador em `conversation_agent.py:540`
  passa `estado`. A docstring que dizia "hoje não muda a lista" é atualizada.

---

## 7. Prompt e skill

### Galho 2b no `AI_SYSTEM_PROMPT` das duas clínicas

`src/scripts/insere_galho_sessao_marcada.py`, no molde de
`corrige_endereco_no_prompt.py`: `ANCORA = "3. ÁREAS\n"`; insere o bloco
abaixo imediatamente antes; `JA_APLICADO` se "2b. SESSÃO JÁ MARCADA" existe;
`ANCORA_AUSENTE` se não acha "3. ÁREAS"; `--aplicar` grava, sem flag simula.
O mesmo bloco entra no default de `template_service.py`.

```
2b. SESSÃO JÁ MARCADA
   Se o bloco QUEM É mostra um próximo horário, você está falando com alguém
   que já tem sessão. Qualquer pedido de mudança - trocar, tirar ou incluir
   área, mudar o dia ou a hora - é ALTERAÇÃO dessa sessão, nunca marcação de
   outra.
   1. Leia as áreas que ela tem marcadas (QUEM É ou lookup_appointments) e
      confirme em uma frase o que muda: "Então fica só axilas, no mesmo dia
      18/11 às 14:50 - é isso?"
   2. O horário dela é dela. Mantenha data e hora por padrão. Só proponha
      outro horário se ela pedir ou se alterar_agendamento responder que as
      áreas novas não cabem - e aí ofereça primeiro o mais próximo no MESMO
      dia, por get_time_slots.
   3. Confirmada a mudança, chame alterar_agendamento. Nunca book_appointment:
      ele cria uma segunda sessão e deixa a primeira ocupando a agenda.
   4. Só se ela disser, com todas as letras, que quer OUTRA sessão além da que
      tem, siga para 3. ÁREAS - e diga a ela que a primeira continua marcada.
```

### `PACIENTE_COM_HORARIO`

Itens 2 e 3 do bloco passam a:

```
2. Quem já tem sessão marcada raramente quer marcar outra. Pedido de mudança
   é ALTERAÇÃO da sessão que existe: siga o passo 2b e use alterar_agendamento.
3. Marcar uma segunda sessão só depois de ela confirmar que quer duas; aí
   pergunte e confirme as áreas como sempre.
```

---

## 8. Lembrete (§7.3 A)

`lembrete.FERRAMENTAS_DE_SAIDA = frozenset({"cancel_appointment"})`.
`alterar_agendamento` fica disponível durante o lembrete mesmo com site. O
`bloco_de_prompt` do lembrete com link passa a dizer: "Se ela quiser REMARCAR
ou CANCELAR, envie o link ... Se ela quiser só trocar as áreas, resolva por
aqui com alterar_agendamento, mantendo o horário."

Remarcar pelo bot durante o lembrete continua **fora**: a tool existe, mas o
prompt do lembrete manda o link - como hoje. O que o código garante é que a
troca de áreas tem caminho.

---

## 9. Testes

- **Engine:** mesma agenda falsa; `cabe_no_horario` e `get_available_slots_multi`
  negam a vaga dela sem exclusão e aceitam com `excluindo(id)`; `excluindo` não
  altera o engine original.
- **`_engine_de`:** com `agendamento_futuro` usa a cópia; sem, usa o original.
- **`alterar_agendamento`:** só áreas (horário mantido, `update_appointment_services`
  chamado com camelCase e `verificar_conflito=True`); só data/hora
  (`reschedule_appointment` chamado, áreas intocadas); os dois (áreas com
  `verificar_conflito=False`, depois reschedule); nada → `nada_a_alterar`;
  `ConflictError` → `nao_cabe` com `o_que_fazer`; área não conversada → a
  mesma recusa do book.
- **`book_appointment`:** com `agendamento_futuro` e sem `segunda_sessao`
  recusa e `create_appointment` não é chamado; com `segunda_sessao=true`
  segue; sem `agendamento_futuro` segue como antes.
- **Agente (dublado, `dublagem_agente.py`):** o caso da Nobre - "só a axila"
  → confirmação → `alterar_agendamento` com horário mantido, e nenhuma
  chamada a `book_appointment`; o caso da Essência - cinco áreas → a tool
  responde `nao_cabe` → `get_time_slots` no mesmo dia → `alterar_agendamento`
  com `new_time`; e a segunda sessão explícita → `book_appointment` com
  `segunda_sessao=true`.
- **Pré-carga:** `tools_obrigatorias(set(), ACTIVE_CUSTOMER)` inclui
  `lookup_appointments`; para `NEW_LEAD`, não.
- **Script do prompt:** aplica uma vez, segunda rodada `JA_APLICADO`, sem
  âncora `ANCORA_AUSENTE`.

---

## 10. Ordem de implementação

1. Engine: `excluindo` + teste.
2. `_engine_de` nas três consultas + teste.
3. `agendamento_futuro.areas`, QUEM É, `lookup_appointments`, pré-carga por estado.
4. `alterar_agendamento` (definição + handler) e a troca do nome nos conjuntos; testes.
5. Recusa em `book_appointment` + `segunda_sessao`; teste.
6. Skill, lembrete, default do prompt; script do galho 2b.
7. Teste do laço com os dois casos.
8. `pytest` completo; deploy em dev; script do prompt em dev; conversa de ponta
   a ponta em dev com uma paciente que tem sessão: trocar área (horário
   mantido), mudar dia, pedir segunda sessão.
9. Prod só com aval do André: deploy, depois o script do prompt nas duas clínicas.

---

## 11. O que esta spec deliberadamente não faz

- Não avisa a paciente quando a **clínica** altera (débito D1).
- Não mexe em `porta_do_disparo` (§7.4 A).
- Não muda o painel nem o site.
- Não remove da pessoa a opção de remarcar pelo link durante o lembrete.
