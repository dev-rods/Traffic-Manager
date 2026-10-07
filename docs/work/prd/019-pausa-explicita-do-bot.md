# PRD — 019 Pausar o bot tem de ser um ato, não uma ausência

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Quando alguém decide que o bot **não** conduz uma conversa, essa decisão passa a
ser gravada como pausa na sessão - e portanto honrada.

Hoje três controles diferentes registram a decisão e não governam o
comportamento. O caso que apareceu em produção: a caixa **"O bot conduz o
agendamento a partir deste disparo"** foi desmarcada, e o bot respondeu de todo
jeito.

---

## 2. Contexto

### 2.1 A caixa não está sendo sobrescrita - ela nunca teve efeito

A política da Essência é `LEADS_ONLY`, e a regra é:

```python
return bool(session.get("bot_enabled")) or campanha_viva(session)
```

A caixa governa o **segundo** termo: marcada, o front envia `campanha: {datas}`,
o `/send` chama `abre_campanha` e `campanha_viva` passa a valer. Desmarcada, o
front **não envia a chave** e nada acontece.

O primeiro termo é escrito em outro lugar - `webhook/handler.py:293`, em toda
mensagem recebida:

```python
if not session.get("bot_enabled"):
    leads_lp = db.execute_query(
        "SELECT id, first_contact_channel FROM scheduler.leads "
        "WHERE clinic_id = %s AND phone = ANY(%s) AND source = 'landing-page' LIMIT 1", ...)
    if leads_lp:
        mark_conversation_eligible(...)
        session["bot_enabled"] = True
```

Para quem veio da landing page, `bot_enabled` vira `True` e o `or` está
satisfeito. **A caixa é estruturalmente incapaz de calar o bot para essa
população.** Não é intermitência.

### 2.2 E a marca é permanente

`describe_time_to_live` na tabela de sessões de produção devolve
**`TimeToLiveStatus: DISABLED`**. Não há TTL, e `mark_conversation_eligible` faz
`put_item` sem atributo de expiração.

Então `bot_enabled=True` é gravado na primeira vez que a pessoa chega pela
landing page e vale **para sempre**, em qualquer conversa futura.

> **Correção de documentação:** o `CLAUDE.md` afirma "ConversationSessions (TTL
> 30min)". Está errado, e essa crença atrasou o diagnóstico - levou a descartar
> a hipótese de marca persistente.

### 2.3 O incidente, medido

Campanha de **30/09/2026 20:42** sobre outros procedimentos, com a caixa
desmarcada:

| | |
|---|---|
| receberam | 320 |
| já marcados com `bot_enabled` | 28 |
| responderam | 30 |
| **destes, com o bot elegível** | **10** |
| receberam resposta negando o produto | 2 |

As sessões das duas pacientes, lidas em produção, mostram a cadeia inteira:

```
campanha:     None    <- a caixa funcionou; nenhuma campanha foi aberta
bot_enabled:  True    <- o outro termo do `or`, e ele basta
```

As duas são `source='landing-page'` em `scheduler.leads` (11/09 e 24/09).

**A caixa foi contornada em 10 conversas, não em 2.** As outras 8 receberam
resposta do bot que ainda não foi classificada.

### 2.4 A regra que atropela existe por um bom motivo

O comentário do código diz: *"Quem veio da landing page tem direito a resposta
automática mesmo com a política LEADS_ONLY, tenha o bot falado primeiro ou
não"*, e cita *"Em 18/09/2026 a Ana Clara esperou 3 horas"* - lead da LP
escreveu e o bot ficou mudo.

A regra está **certa para quem nos procura**. Ela só não distingue isso de
**responder a um disparo nosso com o bot desligado de propósito**. A correção não
pode remover a elegibilidade do lead; tem de deixar a decisão explícita vencer.

### 2.5 O mesmo bug em outros dois lugares

Auditoria dos cinco pontos que escrevem pausa (`PAUSA_ATENDENTE`,
`PAUSA_CONTATO_MANUAL`, `PAUSA_CHAT_ANTERIOR`, `PAUSA_HANDOFF`,
`PAUSA_INSTABILIDADE`):

| | Onde | Diagnóstico | Casos em prod |
|---|---|---|---|
| **A** | caixa do disparo desmarcada | não escreve pausa nenhuma | **10** (campanha de 30/09) |
| **B** | `PAUSA_CONTATO_MANUAL`, `webhook/handler.py:314` | está **dentro** do `if not session.get("bot_enabled")`, então só pode ser aplicada na primeiríssima mensagem. `marcar_contatado.py` grava `first_contact_channel='HUMANO'` no Postgres e **não toca a sessão** | **1** de 9 |
| **C** | `PAUSA_CHAT_ANTERIOR`, `webhook/handler.py:332` | guardada por `if primeira_vez and ...`, com `primeira_vez = not session`. Um disparo anterior cria a sessão e desarma a proteção | **60** de 2912 |

`PAUSA_ATENDENTE`, `PAUSA_HANDOFF` e `PAUSA_INSTABILIDADE` estão corretos:
escrevem a pausa direto, e `esta_pausado` é o primeiro teste de
`should_bot_reply`.

### 2.5.1 A instância C é 100%, e os 52 com `ATENDENTE` são o retrato do dano

Das 2912 conversas que existiam antes de nós, **60** têm sessão com
`bot_enabled=True`, e **todas as 60** estão sem a pausa `CHAT_ANTERIOR`. Não é
uma fração - é a proteção inteira ausente para quem tem sessão.

A distribuição é o que torna o problema concreto:

```
bot_pausado_por = ATENDENTE   52     <- expira em 24h, de proposito
bot_pausado_por = (nenhum)     8
                              ---
                               60    e 57 receberiam resposta do bot agora
```

`PAUSAS_PERMANENTES` é `{CHAT_ANTERIOR, CONTATO_MANUAL}` - só essas duas vencem
para sempre. `ATENDENTE` e `HANDOFF` descrevem atendimento em curso e expiram em
24h, por decisão de 06/09/2026, para que uma conversa atendida uma vez não fique
morta.

Então nos 52: uma pessoa atendeu, a janela de 24h venceu, e como a pausa
permanente nunca foi escrita, **o bot volta a entrar numa conversa que uma
pessoa conduz desde antes de a gente existir** - exatamente o dano que o
docstring de `esta_pausado` diz que o botão "Já iniciada" existe para impedir.

**A raiz é comum:** a pausa é escrita sob condições que não têm relação com a
decisão humana. Quem decide é uma pessoa; quem determina se a decisão vale é o
estado acidental da sessão.

Isto já aconteceu antes neste mesmo arquivo, e o código registra: *"Sem isto o
botão era decorativo: ele registrava o fato e não governava nada"*. É o terceiro
retorno do mesmo padrão.

---

## 3. Escopo

### Dentro do escopo

- **A:** desmarcar a caixa passa a **escrever pausa** na sessão, no `/send`,
  junto do envio. Motivo próprio (ex. `PAUSA_DISPARO_SEM_BOT`).
- **B:** tirar a escrita de `PAUSA_CONTATO_MANUAL` de dentro do
  `if not bot_enabled`, e fazer `marcar_contatado.py` gravar a pausa quando
  marca `HUMANO` - a decisão vale no momento em que é tomada, não só se o
  webhook passar por um galho específico depois.
- **C:** a proteção de conversa anterior deixa de depender de `primeira_vez`.
- Teste que trave a propriedade geral: **com pausa na sessão, `should_bot_reply`
  devolve `False` independentemente de `bot_enabled` e de `campanha_viva`.**
- Corrigir a linha do `CLAUDE.md` sobre o TTL de 30 min.

### Fora do escopo

- **Ligar TTL na tabela de sessões.** É mudança de retenção com efeito em
  histórico, campanha de 7 dias e auditoria. Merece fatia própria.
- **Remover a elegibilidade do lead de landing page.** Ela resolve um problema
  real (2.4).
- **A guarda de saída** que impede o bot de afirmar que a clínica não faz algo.
  Problema diferente, fatia própria - e necessária: a frase *"trabalhamos só com
  depilação a laser"* não existe no código nem nos 19 itens de FAQ, o modelo a
  inventou.
- **Reparar as 10 conversas de 30/09.** A clínica já pediu desculpa à mão.
- **Nomear o tipo de envio no `/send`** (`BOT`/`LEMBRETE`/`CAMPANHA`). Era a
  proposta anterior; ficou desnecessária, porque o disparo já conhece a decisão
  no momento em que acontece.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/bot_policy.py` | modificar | constante de pausa nova + rótulo legível na fila |
| `scheduler/src/functions/send/handler.py` | modificar | sem `campanha`, grava pausa; com `campanha`, segue como hoje |
| `scheduler/src/services/session_store.py` | modificar | função que grava pausa preservando o histórico, como `abre_campanha` faz |
| `scheduler/src/functions/webhook/handler.py` | modificar | desaninhar B, soltar C do `primeira_vez` |
| `scheduler/src/functions/lead/marcar_contatado.py` | modificar | marcar `HUMANO` grava a pausa |
| `frontend/.../CampanhaDoBot.tsx` | verificar | o texto já promete o comportamento correto; confirmar que não muda |
| `scheduler/tests/unit/` | criar | a propriedade geral + um caso por instância |
| `CLAUDE.md` | modificar | o TTL de 30 min não existe |

### 4.1 Por que pausa, e não um terceiro termo no `or`

`esta_pausado(session)` é o **primeiro** teste de `should_bot_reply` e dá
curto-circuito em tudo, inclusive em `bot_enabled` e `campanha_viva`. É o único
mecanismo que já vence os dois, e é operado: a aba "Bot pausado" da fila (PR #88)
é onde a recepção solta, e `PAUSA_CHAT_ANTERIOR` já funciona assim - *"bot
pausado até liberarem no painel"*.

Acrescentar `and not desligado_no_disparo` à expressão resolveria A e deixaria B
e C de pé, além de somar um quarto termo a uma regra que já é difícil de ler.

### 4.2 A pausa precisa durar mais que a conversa

As duas respostas medidas chegaram **2h** e **6h** depois do disparo. Como a
tabela não tem TTL (2.2), a pausa persiste naturalmente - o problema de
expiração não existe. **Isso é sorte, não desenho:** se o TTL for ligado na
fatia futura, esta pausa precisa de prazo explícito. Fica registrado como
dependência entre as duas.

---

## 5. Dependências e riscos

**Dependências**

- PR #88 mergeado e deployado (fila de atendimento e vocabulário de motivos). ✅

**Riscos**

### 5.1 Pausa permanente cala o bot para sempre

Sem TTL, uma pausa escrita hoje vale indefinidamente. Se a clínica disparar uma
campanha simples para 320 pessoas, as 320 ficam pausadas - e um lead da landing
page que escrever semanas depois não recebe resposta automática, reintroduzindo
o problema da Ana Clara pelo outro lado.

É o risco principal e a Spec tem de resolvê-lo. Dois caminhos a pesar:
**prazo na própria pausa** (ela expira sozinha), ou **pausa só para quem já tem
sessão**, deixando quem nunca falou com o bot livre. O segundo é mais simples e
cobre o incidente; o primeiro é mais honesto com a semântica de "este disparo".

### 5.2 Volume de conversas pausadas na fila

A aba "Bot pausado" passa a receber todo disparo sem bot. 320 por campanha é
muito para uma lista cujo propósito é triagem. Avaliar se essa pausa aparece lá
ou se é silenciosa até a paciente responder.

### 5.3 Mexer em `webhook/handler.py` é mexer no caminho de toda mensagem

B e C ficam no meio da função que atende todo WhatsApp recebido. A ordem das
guardas ali já é delicada - `primeira_vez` é capturado **antes** das mutações de
propósito. Alterar exige ler a função inteira, não só as linhas citadas.

### 5.4 A correção não alcança as 60 que já estão assim

Consertar o código faz a pausa valer para conversas **futuras**. As 60 da
instância C já têm sessão sem `CHAT_ANTERIOR`, e a guarda corrigida continuaria
sem alcançá-las se ela depender de um gatilho que já passou.

São 57 conversas em que o bot responderia hoje, a maioria conduzida por uma
pessoa desde antes de nós. **Decidir na Spec:** escrever a pausa
retroativamente nas 60 (um script, com a lista conferida antes), ou aceitar que
a correção só vale daqui para frente.

Inclinação: fazer o backfill. O dado para decidir quem recebe a pausa existe e é
explícito - `scheduler.whatsapp_chats` -, e deixar 57 conversas sabidamente
expostas depois de medi-las é diferente de não saber.

---

## 6. Critérios de aceite

- [ ] Desmarcar a caixa grava pausa, e o bot não responde a quem tem
      `bot_enabled=True` - reproduzido com os dados reais de Yasmin e Marie
- [ ] Marcar a caixa continua abrindo campanha, sem mudança de comportamento
- [ ] `PAUSA_CONTATO_MANUAL` é aplicada mesmo quando `bot_enabled` já existe
- [ ] A proteção de conversa anterior vale mesmo com sessão já criada
- [ ] Teste da **propriedade geral**: pausa na sessão ⇒ `should_bot_reply` é
      `False`, para toda combinação de `bot_enabled` e `campanha_viva`
- [ ] Decisão de 5.1 registrada (prazo na pausa, ou pausa só com sessão)
- [ ] As 60 conversas da instância C conferidas depois do deploy, com atenção
      aos 52 que têm `ATENDENTE` expirado
- [ ] Decidido se as 60 recebem a pausa `CHAT_ANTERIOR` retroativamente, ou se a
      correção só vale para conversas novas (ver 5.4)
- [ ] A linha do TTL no `CLAUDE.md` corrigida

---

## 7. Referências

- `scheduler/src/services/bot_policy.py` — `should_bot_reply`, as cinco pausas
- `scheduler/src/functions/webhook/handler.py:282-341` — as três guardas
- `scheduler/src/services/session_store.py` — por que a marca é permanente
- PR #88 — a fila onde a pausa fica visível
- `docs/work/prd/018-so-depilacao-a-laser.md` — a guarda por procedimento nomeado
- Conversas de produção: `5511994683015` e `5511984048030`, clínica
  `clinicaessenciaestetica-9668a4`, em `MessageEvents` (TTL 90d — extrair antes
  de **29/12/2026** se virarem teste)

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
