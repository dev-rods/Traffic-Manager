# Spec - 046 Para quem já é paciente, o link é o primeiro caminho

> Gerada em 10/11/2026 a partir de `prd/046-link-e-o-primeiro-caminho.md`.
> Decisões do André: **§7.1 A** (o domínio da clínica decide o roteiro da
> campanha; nada novo no painel), **§7.2 A** (segunda tentativa = o bot já
> mandou o link nesta conversa), **§7.3 A** (segunda sessão também começa pelo
> link).

---

## 1. O que muda, em uma frase

Em clínica com domínio, paciente cadastrada que quer marcar recebe o link do
site antes de qualquer área ou data; `check_availability` e `book_appointment`
só passam depois de o **bot** ter mandado o link nesta conversa; a campanha de
reagendamento segue a mesma regra. Lead nova não muda.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/services/autoatendimento.py` | `link_de_agendamento(clinic)` = `link_de_autoatendimento(clinic)`; é o mesmo link (a raiz do site) - alias com o nome do papel novo, documentado |
| `scheduler/src/services/skills/__init__.py` | `bloco_do_site(link)` - o bloco "PRIMEIRA TENTATIVA É O SITE", para as duas skills de paciente |
| `scheduler/src/services/conversation_agent.py` | `{{link_de_agendamento}}` no render; bloco do site depois do bloco da skill; `link_de_agendamento` no `ctx`; `link_enviado_em` na sessão quando o texto do bot leva o link |
| `scheduler/src/services/ai_tools.py` | recusa `primeiro_o_link` em `_tool_check_availability` e `_tool_book_appointment` |
| `scheduler/src/services/prompt_da_campanha.py` | `adapta(prompt, link=None)` - com link, o roteiro da campanha começa pelo site |
| `scheduler/src/services/template_service.py` | nada no default: as clínicas de dev não têm domínio e a variável renderiza vazia |
| `scheduler/tests/unit/test_link_primeiro.py` | **novo** - bloco, recusa, liberação, campanha, lead intocada, o caso real dublado |
| `tests/unit/test_skills.py`, `test_prompt_da_campanha.py`, `test_campanha_ponta_a_ponta.py` | ajustes onde o roteiro da campanha é afirmado |

Nenhuma migration. Nenhuma mudança no prompt do banco: o link entra por
variável e por bloco montado em código.

---

## 3. O link no contexto

### Render

Em `_build_system_prompt`, `variables["link_de_agendamento"] =
link_de_agendamento(clinic) or ""`. Clínica sem domínio renderiza vazio; o
prompt do banco não precisa citar a variável hoje - ela existe para o bloco do
site e para quem quiser usá-la no texto depois.

### `ctx` das tools

Nos dois pontos em que o agente monta o `context` (`conversation_agent.py:544`
e `:954`), entra `"link_de_agendamento": link`. A clínica já está carregada
(`clinic = self._clinica(clinic_id)`, linha 418) antes dos dois.

---

## 4. O bloco do site (skills de paciente)

`skills.bloco_do_site(link)` devolve `""` sem link, senão:

```
═══ PRIMEIRA TENTATIVA É O SITE ═══
Quem já é paciente agenda pelo site: {link}
Lá ela vê os horários, escolhe e confirma com o mesmo número de WhatsApp.
1. Pedido de agendar, pergunta sobre o link, sobre "onde marco" ou sobre o
   link que ela recebeu: responda em uma frase que é por lá, mande o link e
   se coloque à disposição para dúvidas. NÃO pergunte as áreas, NÃO ofereça
   datas, NÃO chame check_availability.
2. Só se ela disser que não consegue, que o link não abre, ou que prefere
   resolver por aqui, conduza o agendamento na conversa, como sempre.
3. Dúvidas (preço, preparo, endereço, áreas) continuam respondidas aqui.
```

No agente, logo após `system_prompt += skill.bloco` (linha 421, que só roda
fora de campanha):

```python
if skill is not skills.PRIMEIRO_AGENDAMENTO:
    system_prompt += skills.bloco_do_site(link)
```

`PRIMEIRO_AGENDAMENTO` fica de fora de propósito (PRD §4.2). `Skill` continua
`frozen`; o bloco do site é uma função, não um campo, porque depende da clínica
e não do estado.

---

## 5. A segunda tentativa, em código

### O que conta como "o link saiu"

Só mensagem **do bot**. O texto do disparo e a mensagem da recepção não
contam: a decisão pede reforço nesses casos. O rastro é um campo da sessão,
não o histórico (o `agent_history` reconstruído do `message-events` não
distingue quem escreveu):

```python
# depois de montar `outgoing`, antes de salvar a sessão
if link and any(link_citado(m.content, link) for m in outgoing):
    session["link_enviado_em"] = agora
    logger.info(f"[Link] {phone}: link enviado")
```

`link_citado(texto, link)` compara pelo domínio, sem esquema nem barra final:
o modelo pode escrever `agendar.x.com.br/agendar`.

Validade: **7 dias** (`campanha.DURACAO_PADRAO_DIAS`), o mesmo prazo da
campanha. Sem prazo, uma paciente que mandou o link em agosto agendaria na
conversa de primeira em novembro; a sessão vive 30 dias.

```python
def link_ja_foi(session, agora) -> bool
```

### A recusa

Em `_tool_check_availability` e `_tool_book_appointment`, **antes** de tudo:

```python
recusa = self._recusa_sem_o_link(args, phone, ctx)
```

```python
def _recusa_sem_o_link(self, args, phone, ctx):
    link = (ctx or {}).get("link_de_agendamento")
    paciente = (ctx or {}).get("paciente") or {}
    if not link or not paciente.get("encontrado"):
        return None                      # sem site, ou lead nova: como sempre
    if link_ja_foi(ctx.get("session"), agora):
        return None                      # segunda tentativa
    logger.info(f"[Link] {phone}: {tool} recusado, link ainda não foi")
    return {
        "error": "primeiro_o_link",
        "link": link,
        "o_que_fazer": (
            "Esta pessoa já é paciente e esta clínica agenda pelo site. Mande o "
            f"link ({link}) em uma frase e pergunte se ela consegue por lá. Só se "
            "ela disser que não, chame esta tool de novo."
        ),
    }
```

Ordem em `book_appointment`: `primeiro_o_link` → `ja_tem_sessao_marcada`
(PRD 045) → trava de áreas. `alterar_agendamento` **não** recebe a recusa:
alterar a sessão que existe continua pela conversa (PRD 045; o site remarca,
mas não troca áreas).

Quando a tool é recusada e o modelo então escreve o link, o campo da sessão é
gravado nesse mesmo turno (§5, "o que conta"), e a próxima chamada passa.

### Log da segunda tentativa

Na primeira chamada que passa por `link_ja_foi`:
`[Link] {phone}: segunda tentativa - agendando na conversa`.

---

## 6. Campanha em clínica com domínio

`adapta(prompt, link=None)`. Com link, `FLUXO_DA_CAMPANHA` dá lugar a:

```
1. LINK
   Mande o link {link} com as datas da campanha, em uma frase. Se o disparo já
   o mandou e ela perguntou dele, confirme que é por lá e mande de novo. NÃO
   pergunte as áreas.
2. SE ELA NÃO CONSEGUIR PELO SITE
   Aí sim: áreas → datas da campanha (check_availability e get_time_slots) →
   "Confirmo?" → calculate_discount → book_appointment. Sem valor, sem cadastro.
3. ENCERRAMENTO
   Confirme e informe o endereço. O aviso de preparo é do sistema.
```

E em `_bloco_da_campanha`, o item 4 ("Comece pelas ÁREAS") vira, com link,
"Comece pelo LINK; áreas só se ela não conseguir pelo site". O chamador
(`_build_system_prompt`, linha 1543) passa `link_de_agendamento(clinic)` - a
clínica já está carregada ali.

A recusa do §5 vale também na campanha: `check_availability` e
`book_appointment` só passam depois de o bot ter mandado o link. O texto do
disparo não conta, de propósito.

---

## 7. Testes (`test_link_primeiro.py`)

- **Bloco:** `bloco_do_site("")` vazio; com link cita o link e "NÃO chame
  check_availability"; no agente, aparece para `PACIENTE_SEM_HORARIO` e
  `PACIENTE_COM_HORARIO` com domínio, não para `PRIMEIRO_AGENDAMENTO`, não sem
  domínio (reutiliza `test_skills.TestNoAgente._roda`, passando clínica com
  `custom_domain`).
- **Recusa:** paciente encontrada + link + sessão sem `link_enviado_em` →
  `check_availability` e `book_appointment` devolvem `primeiro_o_link` e nada
  é consultado/gravado; `alterar_agendamento` não é afetado.
- **Liberação:** com `link_enviado_em` recente, passam; com 8 dias, recusam de
  novo; lead nova (`encontrado=False`) passa sempre; sem link passa sempre.
- **O campo da sessão:** turno em que o texto do bot cita o domínio grava
  `link_enviado_em`; texto sem o link não grava; o link escrito com `/agendar`
  no fim conta.
- **O caso real dublado:** paciente cadastrada, campanha viva, mensagem "para
  influencer também é por esse link?" → o roteiro do modelo pede
  `check_availability` → recusado → o modelo escreve o link → a mensagem que
  sai leva o link e **não** pergunta áreas; sessão com `link_enviado_em`.
- **Campanha:** `adapta(prompt, link)` troca o roteiro e cita o link;
  `adapta(prompt)` continua como hoje; `test_prompt_da_campanha` e
  `test_campanha_ponta_a_ponta` ajustados onde afirmam "comece pelas áreas"
  (com link) sem perder o caso sem domínio.

---

## 8. Ordem de implementação

1. `autoatendimento.link_de_agendamento` + `link_citado` + `link_ja_foi`
   (puros) e testes.
2. Variável no render; `link` no `ctx`; gravação de `link_enviado_em`.
3. `skills.bloco_do_site` e a inserção no agente.
4. Recusa nas duas tools.
5. `adapta(prompt, link)` e o item 4 do bloco de campanha.
6. `pytest`; deploy em dev. Em dev nenhuma clínica tem domínio: para o E2E,
   dar `custom_domain` à clínica de teste de dev (campo da clínica, via
   `PATCH /clinics/{id}` ou SQL em dev), rodar os três passos (pergunta do
   link → link; "não consigo" → agenda; lead nova → como antes) e tirar o
   domínio depois.
7. Prod só com aval do André. Sem script de prompt desta vez.

---

## 9. O que esta spec deliberadamente não faz

- Não toca na lead nova.
- Não cria toggle no painel (§7.1 A).
- Não muda o texto do disparo nem cria template por clínica (PRD §5).
- Não grava a origem do agendamento em `appointments` (PRD §5).
- Não mexe em alterar/cancelar (PRD 045 e lembrete).
