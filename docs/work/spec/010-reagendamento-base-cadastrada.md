# Spec 010 - Agendamento de pacientes já cadastrados

**PRD:** `docs/work/prd/010-reagendamento-base-cadastrada.md`
**Decisões do André (09/09/2026):** campanha de 7 dias, 3 datas padrão, áreas
anteriores via tool, elegibilidade derivada da campanha (não marca permanente).

---

## Princípio que governa a spec

O modo **nunca** é inferido pelo modelo. É gravado no ato do disparo e lido do
banco. O prompt recebe o modo já resolvido, como já acontece com
`single_service_hint` e o bloco de calendário.

---

## 1. A campanha na sessão

Objeto único dentro de `session` (nunca na raiz do item - `session_store.py`
documenta por que a raiz é invisível para quem lê a sessão):

```python
session["campanha"] = {
    "modo": "REAGENDAMENTO",
    "expira_em": <epoch>,          # disparo + 7 dias
    "datas": ["2026-10-07", ...],  # as datas anunciadas no disparo
}
```

### Novo módulo `src/services/campanha.py`

Função pura, testável sem AWS - mesmo desenho de `bot_policy.py`.

| Função | Contrato |
|---|---|
| `DURACAO_PADRAO_DIAS = 7` | decisão do André |
| `MAX_DATAS = 3` (padrão, parametrizável) | |
| `abre(datas, agora=None) -> dict` | monta o objeto acima |
| `esta_viva(session, agora=None) -> bool` | `campanha` existe **e** `expira_em > agora` |
| `datas_da_campanha(session) -> list[str]` | `[]` se morta - nunca vaza data velha |

`esta_viva` falha fechada: sem campanha, campanha malformada ou sem `expira_em`,
devolve False.

---

## 2. Elegibilidade (`src/services/bot_policy.py`)

Uma linha, e é a linha que faz o fluxo existir:

```python
if policy == POLICY_LEADS_ONLY:
    return bool(session.get("bot_enabled")) or esta_viva(session)
```

**Por que não `bot_enabled = True` no disparo.** A tabela de sessões está com
TTL **desabilitado** (conferido em prod: `TimeToLiveStatus: DISABLED`) - sessão
gravada não expira nunca. `bot_enabled` permanente faria cada campanha mensal
deixar um rastro de pacientes que o bot atende para sempre, inclusive daqui a
seis meses, num assunto qualquer, em modo LEAD - pedindo CPF de quem já é
cadastrada. Em poucos meses o `LEADS_ONLY` viraria decorativo, sem sintoma
visível. Derivar da campanha faz a trava voltar sozinha quando ela vence.

**`esta_pausado` continua sendo consultado primeiro e não muda.** Conversa em
que a atendente está falando permanece muda mesmo com campanha aberta - a
campanha não tem poder de despausar. É o "Retomar bot" que libera.

---

## 3. Abertura da campanha no disparo

### Backend - `src/functions/send/handler.py`

Campo **opcional** no body:

```json
"campanha": { "datas": ["2026-10-07","2026-10-14","2026-10-21"], "dias": 7 }
```

Quando presente **e o envio deu certo**, grava a campanha na sessão da paciente.
Ausente (todo envio manual da atendente hoje), nada muda.

Regras:
- Só grava **depois** do envio bem-sucedido. Campanha aberta sem mensagem
  entregue deixa o bot esperando resposta de algo que ninguém recebeu.
- Falha ao gravar **não** derruba o envio - a mensagem já saiu. Loga e reporta
  no retorno (`campanha_aberta: true|false`), como `mark_conversation_eligible`
  já faz.
- Preserva o resto da sessão (ler-mesclar-gravar).
- `datas` limitado a `MAX_DATAS`; vazio ⇒ 400.

**Por que dentro do `/send` e não num endpoint novo:** marcar e enviar precisam
ser o mesmo ato. Separados em duas chamadas, divergem - marcada sem envio (bot
esperando no vazio) ou enviada sem marca (bot mudo). E reaproveita a máquina de
lote que já existe: progresso, rate limit e conferência de entrega.

### Frontend - `BatchMessageModal.tsx`
Seletor das datas da campanha (3 por padrão) e um aviso explícito de que **o bot
assume a conversa a partir do disparo**. As datas escolhidas entram no payload de
cada paciente. Sem datas selecionadas, o disparo segue sendo mensagem simples,
sem campanha - o comportamento de hoje.

---

## 4. ~~Tool `ultimas_areas_do_paciente`~~ - REVERTIDO em 11/09/2026

A tool foi implementada, foi a produção e **foi removida**.

A ideia era boa no papel: ler as áreas da última sessão realizada, propor as
mesmas e pedir confirmação - exatamente o que a atendente faz hoje à mão.

O piloto mostrou o problema. Propor é um convite a induzir, e o bot já tinha
demonstrado que induz: numa conversa em que ninguém citou área, ele escolheu
três sozinho e chegou a um "sim" de agendar R$ 400,50. O que a paciente fez da
última vez não responde o que ela quer agora.

**Decisão do André em 11/09/2026: as áreas são SEMPRE perguntadas.** A tool foi
removida, não desencorajada - enquanto a capacidade existir, alguém a usa. O
prompt agora diz que não há consulta ao histórico de áreas.

A trava de `confirmacao_de_areas` continua valendo e é o que garante: nenhuma
área entra em horário, preço ou agendamento sem ter sido dita na conversa.

## 5. Bloco de modo no prompt

`conversation_agent.py`:

- `_build_system_prompt(clinic_id, phone)` → `(clinic_id, phone, session)`.
  O `process_message` já carregou a sessão na linha 164; passa adiante.
- Ao final, se `esta_viva(session)`, concatena o bloco de REAGENDAMENTO, no
  mesmo lugar onde `discount_context` já é concatenado.

Conteúdo do bloco (texto novo, `AI_SYSTEM_PROMPT` fica intacto):

```
═══ CONVERSA DE CAMPANHA ═══
Esta paciente JÁ É CADASTRADA e já recebeu de nós a mensagem com as datas
abertas. A conversa começou por nossa iniciativa.

Nome: {nome}
Datas anunciadas: {datas}

- NÃO dê boas-vindas nem se apresente. A conversa já está em andamento.
- NUNCA peça nome, CPF, data de nascimento ou e-mail. Já temos o cadastro.
- NÃO anuncie preço, total nem desconto, a menos que perguntem.
- Comece pelas áreas: pergunte quais ela quer tratar DESTA VEZ. Sempre
  pergunte - nunca deduza do atendimento anterior.
- Ofereça apenas as datas anunciadas acima; confirme horários com
  check_availability e get_time_slots.
- Ao fechar, encerre com get_pre_session_instructions, como sempre.
```

`calculate_discount` **continua obrigatória** antes de `book_appointment`: o
preço gravado tem de estar certo. O que muda é não anunciar o valor.

`full_name` (exigido por `book_appointment`) vem do bloco, do cadastro - o bot
repassa à tool sem nunca perguntar.

---

## 6. Ordem de implementação

1. `campanha.py` + testes (puro, sem I/O)
2. `bot_policy.py` - a linha da elegibilidade + testes de mutação
3. `/send` - abertura da campanha + testes de handler
4. ~~Tool `ultimas_areas_do_paciente`~~ - revertido, ver seção 4
5. Bloco de modo no prompt
6. Frontend - datas no modal de disparo
7. Piloto no número do André antes da base

Cada fase entra verde antes da seguinte. 1-2 são o núcleo: sem elas nada
responde.

---

## 7. Testes que precisam existir

**Não basta a suíte passar** - as travas do `LEADS_ONLY` falham em silêncio, com
tudo verde, exatamente como a permissão de IAM que matou a agregação.

| Teste | Por que |
|---|---|
| Campanha viva ⇒ responde sob LEADS_ONLY | é o fluxo inteiro |
| Campanha vencida (8º dia) ⇒ **não** responde | a trava tem de voltar sozinha |
| Campanha viva + pausa de atendente ⇒ **não** responde | campanha não despausa |
| Sessão sem campanha ⇒ comportamento de hoje | não vazar para lead |
| `/send` sem `campanha` não encosta na sessão | resposta manual da atendente |
| `/send` com falha no envio não abre campanha | bot esperando no vazio |
| `datas_da_campanha` de campanha morta ⇒ `[]` | não oferecer data velha |
| Paciente sem histórico ⇒ `encontrou: false` | o bot pergunta em vez de travar |
| Prompt sem campanha não contém o bloco | modo não vaza para o fluxo de lead |

Mutação obrigatória em: a linha da elegibilidade, o `>` de `expira_em`, e a
ordem "envia depois grava" no `/send`.

---

## 8. Fora do escopo

- Repescagem de quem não respondeu
- Agendar o disparo automaticamente (segue manual, pelo painel)
- Mexer no fluxo de lead
