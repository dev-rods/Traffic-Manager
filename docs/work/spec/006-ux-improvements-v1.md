# Spec — 006 UX Improvements v1 (Feedback Colaborador)

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/006-ux-improvements-v1.md`

---

## 1. Resumo

Implementar 10 melhorias de UX no fluxo de agendamento WhatsApp, impactando principalmente `conversation_engine.py` (fluxo de conversa), `template_service.py` (templates de mensagem), `setup_database.py` (migration) e `seed_clinic.py` (seed data). As mudanças abrangem: mensagens, formatação, skip de etapas, validações e nova coluna no banco.

---

## 2. Arquivos a criar

Nenhum arquivo novo necessário.

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/services/conversation_engine.py` | Items 1-10: welcome com endereço + intro, FAQ negrito, tabela sem duração, skip serviço único, preço só nas áreas, "falar com atendente", dia da semana nas datas, validação max_session_minutes, mensagem de recomendações |
| `scheduler/src/services/template_service.py` | Atualizar templates WELCOME_NEW, WELCOME_RETURNING, BOOKED; adicionar template RECOMMENDATIONS |
| `scheduler/src/scripts/setup_database.py` | Migration: `ADD COLUMN max_session_minutes`, `ADD COLUMN welcome_intro_message`; atualizar CREATE TABLE |
| `scheduler/src/scripts/seed_clinic.py` | Seed dos campos `max_session_minutes`, `welcome_intro_message` e `pre_session_instructions` |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. **Migration** — `setup_database.py`: adicionar colunas `max_session_minutes` e `welcome_intro_message`
2. **Templates** — `template_service.py`: atualizar templates de welcome e booked
3. **Conversation Engine** — `conversation_engine.py`: todas as 10 mudanças de lógica/UX
4. **Seed** — `seed_clinic.py`: atualizar seed data com novos campos

---

## 6. Detalhes por arquivo

### `scheduler/src/scripts/setup_database.py`

- **Modificar** — Adicionar migrations idempotentes ao final da lista `MIGRATIONS`:

```sql
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS max_session_minutes INTEGER DEFAULT 60;
ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS welcome_intro_message TEXT;
```

- **Modificar** — Atualizar o `CREATE TABLE scheduler.clinics` para incluir:

```sql
max_session_minutes INTEGER DEFAULT 60,
welcome_intro_message TEXT,
```

(Adicionar logo após a linha `owner_email VARCHAR(255),`, antes de `active BOOLEAN DEFAULT TRUE`)

O campo `welcome_intro_message` armazena a mensagem introdutória da clínica (ex: informações sobre equipamento, diferenciais). Se `NULL`, nenhuma mensagem extra é enviada no welcome.

---

### `scheduler/src/services/template_service.py`

- **Modificar** — Atualizar `DEFAULT_TEMPLATES`:

#### Item 1: Endereço + mensagem introdutória na boas-vindas

A mensagem de welcome agora inclui: endereço da clínica + mensagem introdutória (`welcome_intro_message`) configurável por clínica. A mensagem intro é enviada como **segunda mensagem** (separada da saudação) para melhor legibilidade no WhatsApp.

Alterar:
```python
"WELCOME_NEW": "Olá! Seja {{bem_vindx}} à {{clinic_name}}! Como posso te ajudar hoje?",
"WELCOME_RETURNING": "Olá, {{patient_name}}! {{Bem_vindx}} de volta à {{clinic_name}}! Como posso te ajudar?",
```

Para:
```python
"WELCOME_NEW": "Olá! Seja {{bem_vindx}} à *{{clinic_name}}*!\n📍 {{address}}\n\nComo posso te ajudar hoje?",
"WELCOME_RETURNING": "Olá, {{patient_name}}! {{Bem_vindx}} de volta à *{{clinic_name}}*!\n📍 {{address}}\n\nComo posso te ajudar?",
```

**Nota:** A mensagem introdutória (`welcome_intro_message`) não vai no template — é enviada como mensagem separada pelo `_on_enter_welcome()`. Ver detalhes na seção do conversation_engine.

#### Item 10: Template de recomendações pós-booking

Adicionar novo template:
```python
"RECOMMENDATIONS": "📋 *Recomendações importantes para sua sessão:*\n\n{{recommendations}}\n\nPor favor, confirme que leu e entendeu as recomendações acima.",
```

---

### `scheduler/src/services/conversation_engine.py`

#### Item 1: Endereço + mensagem introdutória na boas-vindas

**Método:** `_on_enter_welcome()` (linhas ~755-780)

Atualmente retorna `(variables, content)`. Precisa ser alterado para também retornar a mensagem intro como conteúdo extra.

- Buscar `address` e `welcome_intro_message` do clinic
- Adicionar `"address"` ao dict `variables` em ambos os caminhos (new/returning)
- Se `welcome_intro_message` existe, retorná-la como conteúdo adicional

```python
address = clinic.get("address", "") if clinic else ""
welcome_intro = clinic.get("welcome_intro_message", "") if clinic else ""

# No caminho returning:
variables = {"patient_name": patient_name, "clinic_name": clinic_name, "bem_vindx": bem_vindx, "Bem_vindx": Bem_vindx, "address": address}

# No caminho new:
variables = {"clinic_name": clinic_name, "bem_vindx": bem_vindx, "Bem_vindx": Bem_vindx, "address": address}
```

**Envio da mensagem intro como mensagem separada:**

O `_on_enter_welcome` precisa retornar a `welcome_intro` para que o engine a envie como mensagem de texto adicional ANTES do menu principal. A forma mais simples:

- Guardar na session: `session["_welcome_intro"] = welcome_intro`
- No `_on_enter()`, após chamar `_on_enter_welcome`, verificar se há intro e gerar mensagem extra:

```python
# Em _on_enter(), no bloco WELCOME/MAIN_MENU (linha ~638):
if state == ConversationState.WELCOME or state == ConversationState.MAIN_MENU:
    self._clear_flow_session_keys(session)
    template_vars, override_content = self._on_enter_welcome(clinic_id, phone, session)
    session["state"] = ConversationState.MAIN_MENU.value
    # Store intro for _build_messages to prepend
    welcome_intro = session.pop("_welcome_intro", "")
    if welcome_intro:
        session["_prepend_message"] = welcome_intro
```

- No `_build_messages()`, verificar se há `_prepend_message` na session e incluir como mensagem de texto antes do menu:

```python
# No início de _build_messages():
prepend = session.pop("_prepend_message", "")
messages = []
if prepend:
    messages.append(OutgoingMessage(message_type="text", content=prepend))
# ... resto do build ...
messages.append(...)  # mensagem principal com botões
return messages
```

---

#### Item 2: Negrito nas dúvidas (FAQ)

**Método:** `_on_enter_faq_menu()` (linhas ~1756-1776)

- Ao construir os botões dinâmicos, formatar o label com `*bold*`:

```python
dynamic_buttons.append({"id": btn_id, "label": f"*{faq['question_label']}*"})
```

**Nota:** O bold será visível na mensagem de texto quando listadas. Os botões WhatsApp não suportam markdown nativamente, mas a label aparece como texto no fallback.

---

#### Item 3: Remover duração da tabela de preços

**Método:** `_on_enter_price_table()` (linhas ~790-845)

- Remover `({dur_str})` da exibição de áreas e serviços:

Alterar linha ~834:
```python
# De:
lines.append(f"  • {area['name']}: {price_str} ({dur_str})")
# Para:
lines.append(f"  • {area['name']}: {price_str}")
```

Alterar linhas ~838-839:
```python
# De:
dur_str = f" ({dur}min)" if dur else ""
lines.append(f"  {price_str}{dur_str}")
# Para:
lines.append(f"  {price_str}")
```

(Pode remover as variáveis `dur` e `dur_str` que ficam sem uso nesse bloco.)

---

#### Item 4: Skip de serviço quando há apenas 1

**Método:** `_on_enter_select_services()` (linhas ~847-882)

- Quando `len(services) == 1`, auto-selecionar o serviço e redirecionar para `SELECT_AREAS`:

```python
if len(services) == 1:
    svc = services[0]
    session["selected_service_ids"] = [str(svc["id"])]
    session["selected_services_display"] = svc["name"]
    session["_available_services"] = [{"id": str(svc["id"]), "name": svc["name"], "price_cents": svc.get("price_cents", 0)}]
    logger.info(f"[ConversationEngine] _on_enter_select_services: single service '{svc['name']}' -> auto-selecting")
    # Redirect to SELECT_AREAS
    session["state"] = ConversationState.SELECT_AREAS.value
    result = self._on_enter_select_areas(clinic_id, phone, session)
    if result is None:
        # No areas -> skip to AVAILABLE_DAYS
        session["state"] = ConversationState.AVAILABLE_DAYS.value
        session["_skipped_areas"] = True
        tv, db = self._on_enter_available_days(clinic_id, phone, session)
        return tv, None, db
    return result
```

**Nota:** O método `_on_enter_select_services` precisa receber `phone` como parâmetro adicional (para passar a `_on_enter_select_areas`).

- Atualizar a assinatura: `def _on_enter_select_services(self, clinic_id: str, phone: str, session: dict)`
- Atualizar a chamada em `_on_enter()` (linha ~648): `self._on_enter_select_services(clinic_id, phone, session)`

**Tratamento de back navigation:** Quando o skip de serviço acontece e o usuário navega para trás a partir de SELECT_AREAS, deve voltar para SCHEDULE_MENU (não SELECT_SERVICES). Adicionar flag `_skipped_services` na session:

```python
session["_skipped_services"] = True
```

Na lógica de `back` (linhas ~412-435), adicionar:
```python
# When single service was auto-selected, back from SELECT_AREAS should go to SCHEDULE_MENU
if current_state == ConversationState.SELECT_AREAS and session.pop("_skipped_services", False):
    next_state = ConversationState.SCHEDULE_MENU
    logger.info("[ConversationEngine] Back navigation: skipped services, redirecting to SCHEDULE_MENU")
```

---

#### Item 5: Remover preço na seleção de serviço

**Método:** `_on_enter_select_services()` (linhas ~870-875) e `_on_enter_confirm_services()` (linhas ~914-918)

- Na construção da lista numerada, remover o preço:

```python
# De:
price_str = f" - R${price / 100:.2f}" if price else ""
lines.append(f"{i} - {svc['name']}{price_str}")
# Para:
lines.append(f"{i} - {svc['name']}")
```

- Mesma mudança no fallback de `_on_enter_confirm_services()` (linhas ~914-918).

---

#### Item 6: Manter preço na seleção de áreas

**Método:** `_build_areas_list()` (linhas ~934-950)

- Atualizar para exibir preço por área. O método precisa receber os dados de preço.
- Alterar assinatura para receber `service_area_data` (dict com preço por area_id):

```python
@staticmethod
def _build_areas_list(available_areas: list, multi_service: bool, price_map: dict = None) -> str:
    """Build the numbered areas list with prices, grouped by service when multi_service."""
    def format_area(i, a):
        price_str = ""
        if price_map:
            key = (a.get("service_id", ""), a["id"])
            price_cents = price_map.get(key)
            if price_cents:
                reais = int(price_cents) // 100
                centavos = int(price_cents) % 100
                price_str = f" - R$ {reais},{centavos:02d}"
        return f"{i} - {a['name']}{price_str}"

    if not multi_service:
        return "\n".join(format_area(i, a) for i, a in enumerate(available_areas, 1))

    lines = []
    current_service = None
    for i, area in enumerate(available_areas, 1):
        svc = area.get("service_name", "")
        if svc != current_service:
            if current_service is not None:
                lines.append("")
            lines.append(f"📌 {svc}:")
            current_service = svc
        lines.append(format_area(i, area))
    return "\n".join(lines)
```

**Método:** `_on_enter_select_areas()` (linhas ~996-1050)

- Atualizar a query para incluir preço:

```sql
SELECT a.id, a.name, sa.service_id, s.name as service_name,
       COALESCE(sa.price_cents, s.price_cents) as price_cents
FROM scheduler.service_areas sa
JOIN scheduler.areas a ON sa.area_id = a.id
JOIN scheduler.services s ON sa.service_id = s.id
WHERE sa.service_id::text IN ({placeholders})
AND sa.active = TRUE AND a.active = TRUE
ORDER BY s.name, a.display_order, a.name
```

- Construir `price_map` e passar para `_build_areas_list`:

```python
price_map = {}
for a in areas:
    price_map[(str(a["service_id"]), str(a["id"]))] = a.get("price_cents")

areas_list = self._build_areas_list(session["_available_areas"], multi_service, price_map)
```

- Guardar `price_map` nos `_available_areas` para reutilização no fallback de `_on_enter_confirm_areas`:

```python
session["_available_areas"] = [
    {"id": str(a["id"]), "name": a["name"], "service_id": str(a["service_id"]),
     "service_name": a.get("service_name", ""), "price_cents": a.get("price_cents")}
    for a in areas
]
```

**Método:** `_on_enter_confirm_areas()` — atualizar o fallback (linhas ~1093) para reconstruir o `price_map` a partir de `available_areas`:

```python
price_map = {(a["service_id"], a["id"]): a.get("price_cents") for a in available_areas}
areas_list = self._build_areas_list(available_areas, multi_service, price_map)
```

---

#### Item 7: "Falar com atendente" a partir da escolha de áreas

**Método:** `_on_enter_select_areas()` (linhas ~1048-1050)

- Adicionar botão "Falar com atendente" junto com o botão Voltar:

```python
back_button = [
    {"id": "human", "label": "Falar com atendente"},
    {"id": "back", "label": "Voltar"},
]
```

**STATE_CONFIG:** O estado `SELECT_AREAS` já aceita `free_text` input, e `human` já é tratado globalmente em `_identify_input()` e no step 3 (`elif user_input == "human"`), então não precisa de mudança no STATE_CONFIG.

**Mesma mudança em:** `CONFIRM_AREAS`, `CONFIRM_SERVICES`. Adicionar botão "Falar com atendente" nos botões estáticos desses estados em `STATE_CONFIG`:

```python
ConversationState.CONFIRM_SERVICES: {
    "buttons": [
        {"id": "confirm_services", "label": "Confirmar"},
        {"id": "human", "label": "Falar com atendente"},
        {"id": "back", "label": "Voltar"},
    ],
    "transitions": {
        "confirm_services": ConversationState.SELECT_AREAS,
        "human": ConversationState.HUMAN_HANDOFF,
    },
    ...
},
ConversationState.CONFIRM_AREAS: {
    "buttons": [
        {"id": "confirm_areas", "label": "Confirmar"},
        {"id": "human", "label": "Falar com atendente"},
        {"id": "back", "label": "Voltar"},
    ],
    "transitions": {
        "confirm_areas": ConversationState.AVAILABLE_DAYS,
        "human": ConversationState.HUMAN_HANDOFF,
    },
    ...
},
```

---

#### Item 8: Dia da semana nos dias disponíveis

**Método:** `_format_date_br()` (linhas ~1918-1926)

- Criar novo método `_format_date_br_with_weekday()`:

```python
@staticmethod
def _format_date_br_with_weekday(date_value) -> str:
    WEEKDAYS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
    if isinstance(date_value, str) and date_value:
        try:
            dt = datetime.strptime(date_value, "%Y-%m-%d")
            weekday = WEEKDAYS_PT[dt.weekday()]  # weekday(): 0=Monday, 6=Sunday
            return f"{dt.strftime('%d/%m/%Y')} ({weekday})"
        except ValueError:
            return date_value
    if isinstance(date_value, date):
        weekday = WEEKDAYS_PT[date_value.weekday()]
        return f"{date_value.strftime('%d/%m/%Y')} ({weekday})"
    return str(date_value)
```

**Método:** `_on_enter_available_days()` (linhas ~1230-1242)

- Usar `_format_date_br_with_weekday` nos botões e na lista:

```python
# Botões:
dynamic_buttons.append({"id": btn_id, "label": self._format_date_br_with_weekday(day)})

# Lista:
days_list = "\n".join([f"{i+1} - {self._format_date_br_with_weekday(d)}" for i, d in enumerate(days)])
```

**Mesma mudança em:** `_on_enter_reschedule_lookup()` (linhas ~1458-1460) e `_on_enter_show_current_appointment()` (linhas ~1538-1540) — usar `_format_date_br_with_weekday` nos botões de datas de remarcação.

---

#### Item 9: Parametrizar tempo máximo de soma de áreas

**Método:** `_on_enter_confirm_areas()` (linhas ~1052-1107)

- Após calcular `selected_service_area_pairs`, buscar `max_session_minutes` da clínica e validar:

```python
# Após montar selected_service_area_pairs (antes de salvar na session):

# Calculate total duration for validation
if selected_service_area_pairs:
    placeholders_pairs = ", ".join(["(%s::uuid, %s::uuid)"] * len(selected_service_area_pairs))
    params = ()
    for pair in selected_service_area_pairs:
        params += (pair["service_id"], pair["area_id"])
    dur_rows = self.db.execute_query(
        f"""SELECT SUM(COALESCE(sa.duration_minutes, s.duration_minutes)) as total
            FROM (VALUES {placeholders_pairs}) AS pairs(service_id, area_id)
            JOIN scheduler.services s ON s.id = pairs.service_id
            LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
        params,
    )
    total_duration = int(dur_rows[0]["total"]) if dur_rows and dur_rows[0]["total"] else 0

    # Validate against max_session_minutes
    clinic = self._get_clinic(clinic_id)
    max_session = (clinic.get("max_session_minutes") or 60) if clinic else 60
    if total_duration > max_session:
        logger.warning(
            f"[ConversationEngine] _on_enter_confirm_areas: total_duration={total_duration}min exceeds max_session={max_session}min"
        )
        session["state"] = ConversationState.SELECT_AREAS.value
        hours, mins = divmod(max_session, 60)
        max_str = f"{hours}h{mins:02d}min" if hours else f"{max_session}min"
        service_names = list(dict.fromkeys(a.get("service_name", "") for a in available_areas))
        multi_service = len(service_names) > 1
        price_map = {(a["service_id"], a["id"]): a.get("price_cents") for a in available_areas}
        areas_list = self._build_areas_list(available_areas, multi_service, price_map)
        content = (
            f"⚠️ A duração total das áreas selecionadas ({total_duration}min) excede o máximo "
            f"permitido por sessão (*{max_str}*).\n\n"
            f"Por favor, selecione menos áreas:\n\n{areas_list}"
        )
        back_button = [
            {"id": "human", "label": "Falar com atendente"},
            {"id": "back", "label": "Voltar"},
        ]
        session["dynamic_buttons"] = back_button
        return {}, content
```

---

#### Item 10: Mensagem de recomendações com confirmação de leitura

**STATE_CONFIG:** Adicionar novo estado `CONFIRM_RECOMMENDATIONS` entre `BOOKED` e os botões finais:

```python
# Novo estado no enum:
CONFIRM_RECOMMENDATIONS = "CONFIRM_RECOMMENDATIONS"
```

**Fluxo alterado:**
- `CONFIRM_BOOKING` → `confirm` → `BOOKED` (cria appointment, envia confirmação)
- `BOOKED` → auto-transition → `CONFIRM_RECOMMENDATIONS` (se há instruções)
- `CONFIRM_RECOMMENDATIONS` → `confirm_read` → `FAREWELL` / menu

**Implementação simplificada (sem novo estado):**

Melhor abordagem: enviar a mensagem de recomendações como parte do `_on_enter_booked()`, adicionando ao conteúdo e ajustando os botões.

**Método:** `_on_enter_booked()` (linhas ~1327-1407)

- Se há `pre_session_instructions`, alterar o template e os botões:

Alterar a construção do conteúdo para incluir pedido de confirmação:
```python
# Após construir pre_instructions (linha ~1385):
if pre_instructions:
    recommendations_msg = self.template_service.get_and_render(
        clinic_id, "RECOMMENDATIONS", {"recommendations": pre_instructions}
    )
    # Append recommendations to booking confirmation
    content = content + "\n\n---\n\n" + recommendations_msg
```

**STATE_CONFIG para BOOKED:** Alterar botões para incluir confirmação:

```python
ConversationState.BOOKED: {
    "buttons": [
        {"id": "confirm_read", "label": "✅ Li e entendi"},
        {"id": "human", "label": "Falar com atendente"},
    ],
    "transitions": {
        "confirm_read": ConversationState.FAREWELL,
        "human": ConversationState.HUMAN_HANDOFF,
    },
    ...
},
```

Quando o usuário confirma que leu, vai para FAREWELL. Se não há instruções, manter o fluxo original (farewell + menu).

**Lógica condicional no `_on_enter_booked()`:**
```python
# No final do método, setar botões dinâmicos baseado em se há instruções:
if pre_instructions:
    session["dynamic_buttons"] = [
        {"id": "confirm_read", "label": "✅ Li e entendi"},
        {"id": "human", "label": "Falar com atendente"},
    ]
    session["dynamic_transitions"] = {
        "confirm_read": ConversationState.FAREWELL.value,
        "human": ConversationState.HUMAN_HANDOFF.value,
    }
```

Se não há instruções, usa os botões padrão do STATE_CONFIG (farewell, menu, human).

Restaurar botões padrão do `STATE_CONFIG.BOOKED` para o caso sem instruções:
```python
ConversationState.BOOKED: {
    "buttons": [
        {"id": "farewell", "label": "Finalizar atendimento"},
        {"id": "main_menu", "label": "Menu principal"},
        {"id": "human", "label": "Falar com atendente"},
    ],
    "transitions": {
        "farewell": ConversationState.FAREWELL,
        "main_menu": ConversationState.MAIN_MENU,
        "human": ConversationState.HUMAN_HANDOFF,
        "confirm_read": ConversationState.FAREWELL,
    },
    ...
},
```

---

### `scheduler/src/scripts/seed_clinic.py`

- **Modificar** — Adicionar `max_session_minutes` e `welcome_intro_message` ao INSERT/UPDATE da clínica seed:

```python
"max_session_minutes": 60,  # 1 hora padrão
"welcome_intro_message": """✨ Nós trabalhamos com o Soprano Ice Platinum, uma das tecnologias mais avançadas do mundo em depilação a laser.

💎 Trata-se de um equipamento de ponta, avaliado em cerca de R$ 350 a R$ 400 mil reais, reconhecido pela sua segurança e eficiência.

📅 As sessões têm intervalo médio de 30 dias, ou seja, você realiza aproximadamente 1 sessão por mês.

Como o equipamento é de alto valor, ele é locado exclusivamente para alguns dias de atendimento durante o mês, garantindo que cada paciente seja recebido em estrutura adequada.

👉 Trabalhamos somente com sessão avulsa, para dar liberdade e flexibilidade a cada pessoa.""",
```

- **Modificar** — Garantir que `pre_session_instructions` da clínica está preenchido com recomendações genéricas de proteção (se ainda não estiver).

---

## 7. Convenções a respeitar

- Logging: `[ConversationEngine]` prefix com contexto
- Naming: `max_session_minutes` snake_case para DB column
- Migrations idempotentes: `ADD COLUMN IF NOT EXISTS`
- Templates: `{{variable}}` syntax
- WhatsApp markdown: `*bold*` para negrito, `~strikethrough~` para tachado
- Botões WhatsApp: max 3 botões nativos, usar `list` ou fallback texto se mais
- Preços: sempre em centavos no banco, formatados com `_format_price_brl()`

---

## 8. Impacto no fluxo (resumo visual)

```
WELCOME → [endereço + msg intro] → MAIN_MENU
  ↓
SCHEDULE_MENU → SELECT_SERVICES
  ↓                ↓ (1 serviço: auto-skip)
  ↓           CONFIRM_SERVICES [+atendente]
  ↓                ↓
  ↓           SELECT_AREAS [+preço, +atendente]
  ↓                ↓
  ↓           CONFIRM_AREAS [+atendente, +validação max_session]
  ↓                ↓
  ↓           AVAILABLE_DAYS [+dia da semana]
  ↓                ↓
  ↓           SELECT_TIME
  ↓                ↓
  ↓           CONFIRM_BOOKING
  ↓                ↓
  ↓           BOOKED [+recomendações com confirmação]
  ↓                ↓
  ↓           FAREWELL (após "Li e entendi")

FAQ_MENU → [perguntas em negrito] → FAQ_ANSWER

PRICE_TABLE → [sem duração]
```
