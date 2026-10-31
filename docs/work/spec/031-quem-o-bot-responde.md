# Spec - 031 Quem o bot responde: os três cenários fechados

> Gerado na fase **Spec** em 31/10/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/031-quem-o-bot-responde.md`

---

## 1. Resumo

Três entregas, todas em cima de regras que já existem:

- **A. Origem do lead.** A regra "lead cadastrado dá direito ao bot" deixa de
  ser `source = 'landing-page'` e passa a ser `source <> 'whatsapp'`, numa
  constante única em `elegibilidade_do_bot`, usada pelo webhook (quem escreve
  primeiro) e pelo botão "Iniciar pelo Bot".
- **B. Lista de conversas.** `GET /clinics/{id}/conversations` passa a devolver
  `bot_paused` e `pause_reason` por conversa, calculados pela MESMA função que
  `conversations/active` e `attendant/status` já usam (hoje repetida inline em
  três lugares). O painel mostra um selo por linha, um filtro e o botão
  "Ativar bot" direto na linha.
- **C. "Ativar bot" responde a pergunta pendente.** Já existe:
  `POST /attendant/deactivate` chama `_agendar_retomada`, que lê os eventos,
  decide por `ha_pergunta_em_aberto` e responde numa invocação assíncrona
  (`conversation_resume.responder_se_ficou_em_aberto`). O PRD errou ao dizer
  que a pergunta ficava sem resposta. Fica para esta entrega: cobrir o caso
  `not_eligible` com teste, e corrigir um desencontro: a resposta HTTP diz
  `answering_open_question: true` antes de a execução assíncrona conferir
  `pode_iniciar`, então na janela de silêncio o painel mostra "respondendo" e
  nada sai.

Sem migration. Backend e frontend podem subir em qualquer ordem: o front trata
`pause_reason` ausente como "sem selo".

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/tests/unit/test_motivo_da_pausa.py` | A função única do motivo: os quatro valores e a ordem entre eles |
| `scheduler/tests/unit/test_conversations_com_motivo.py` | `conversations.py` devolve `bot_paused`/`pause_reason` por telefone, e não quebra sem sessão |
| `frontend/src/lib/motivoDaPausa.ts` | Rótulos de `PauseReason` para selo e para o cabeçalho da conversa (fonte única no front) |
| `frontend/src/pages/bot/components/ConversationList.test.tsx` | Selo por motivo, botão "Ativar bot" só em `not_eligible`, filtro |
| `scheduler/tests/integration/031-quem-o-bot-responde.md` | Os três cenários de ponta a ponta |
| `scheduler/tests/postman/031-quem-o-bot-responde.postman_requests.json` | `conversations` com motivo; `deactivate` em conversa fora da regra |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/services/elegibilidade_do_bot.py` | `ORIGENS_PERMITIDAS` sai; entram `ORIGEM_SEM_DIREITO = "whatsapp"` e `origem_da_direito_ao_bot(source)`; texto de `MOTIVOS["ORIGEM"]` |
| `scheduler/src/functions/webhook/handler.py` | Consulta do lead: `source <> %s` com `ORIGEM_SEM_DIREITO`, em vez de `source = 'landing-page'`; comentário |
| `scheduler/src/services/atendimento.py` | Nova `motivo_da_pausa(clinic, session, phone, agora) -> str | None` e constantes `PAUSA_ATENDENTE`, `PAUSA_CLINICA`, `PAUSA_FORA_DA_REGRA` |
| `scheduler/src/functions/attendant/list_active.py` | Troca o cálculo inline por `atendimento.motivo_da_pausa` |
| `scheduler/src/functions/attendant/handler.py` | `_handle_status` idem; `_agendar_retomada` confere `pode_iniciar` antes de prometer |
| `scheduler/src/functions/attendant/conversations.py` | Carrega clínica e sessões; anexa `bot_paused` e `pause_reason` a cada conversa |
| `scheduler/tests/unit/test_elegibilidade_do_bot.py` | `test_origem_que_nao_e_landing_page` vira dois testes (whatsapp/vazio recusa; outras origens passam) |
| `scheduler/tests/unit/test_lead_que_escreve_primeiro.py` | A asserção `"landing-page" in q` vira `"source <> %s" in q` |
| `scheduler/tests/unit/test_conversation_resume.py` | Caso: porta fechada (silêncio) devolve `answering_open_question: false` |
| `frontend/src/types/index.ts` | `ConversationPreview` ganha `bot_paused?: boolean` e `pause_reason?: PauseReason` |
| `frontend/src/pages/bot/components/ConversationList.tsx` | Selo, botão "Ativar bot" na linha, props `onResume`/`resumeLoadingPhone`, prop `filtro` |
| `frontend/src/pages/bot/components/ConversationThread.tsx` | `MOTIVO_DA_PAUSA` local sai; importa de `lib/motivoDaPausa` |
| `frontend/src/pages/bot/BotPage.tsx` | Estado `filtro` com os quatro valores; passa `onResume` à lista; reaproveita `answeringPhone` |
| `TASKS_LOG.md`, `docs/work/prd/031-quem-o-bot-responde.md` | Registro e status |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. **A** (backend): `elegibilidade_do_bot` + webhook + testes. Entrega
   independente, deploy possível já.
2. **B** (backend): `atendimento.motivo_da_pausa` e troca nos três pontos;
   `conversations.py` enriquecido; testes.
3. **C** (backend): `_agendar_retomada` confere a porta; teste.
4. **B** (frontend): `lib/motivoDaPausa.ts`, `ConversationList`, `BotPage`,
   `ConversationThread`; testes.
5. Docs de integração, Postman, TASKS_LOG, status do PRD.

Um PR só, commits por etapa.

---

## 6. Detalhes por arquivo

### `scheduler/src/services/elegibilidade_do_bot.py`

- **Modificar.**
- Substituir `ORIGENS_PERMITIDAS = {"landing-page"}` por:

```python
# A única origem que NÃO dá direito ao bot: quem escreveu direto no WhatsApp
# sem passar por cadastro algum (o webhook cria o lead com esta origem). Toda
# outra origem (landing-page, painel, integrações) é "lead cadastrado".
# Decisão do André em 31/10/2026 (PRD 031). Origem vazia também não dá direito:
# lead sem origem é lead que ninguém cadastrou de propósito.
ORIGEM_SEM_DIREITO = "whatsapp"


def origem_da_direito_ao_bot(source) -> bool:
    return bool(source) and source != ORIGEM_SEM_DIREITO
```

- Em `por_que_nao_pode`: `if not origem_da_direito_ao_bot(lead.get("source")): return "ORIGEM"`.
- `MOTIVOS["ORIGEM"] = "Quem chegou pelo WhatsApp não pode ser iniciado pelo bot."`
- Atualizar o comentário acima de `pode_responder(...)` ("a origem landing-page
  ja foi conferida" vira "a origem já foi conferida").

### `scheduler/src/functions/webhook/handler.py`

- **Modificar** a consulta em torno da linha 341:

```python
from src.services.elegibilidade_do_bot import ORIGEM_SEM_DIREITO
...
leads_lp = db.execute_query(
    "SELECT id, first_contact_channel FROM scheduler.leads "
    "WHERE clinic_id = %s AND phone = ANY(%s) AND source <> %s "
    "ORDER BY created_at DESC LIMIT 1",
    (clinic_id, variantes, ORIGEM_SEM_DIREITO),
)
```

- Renomear `leads_lp` para `leads_cadastrados`. O `ORDER BY` existe porque
  agora pode haver mais de uma linha (painel + landing page); a mais recente
  carrega o `first_contact_channel` que importa.
- Comentário: "Quem veio da landing page" vira "Quem foi cadastrado por qualquer
  caminho que não o próprio WhatsApp".
- Nada muda no `upsert_lead`: a chave é `(clinic_id, phone, first_name)`, então
  um lead `whatsapp` (sem nome) e o mesmo telefone vindo depois pelo formulário
  (com nome) são linhas distintas, e a consulta acima encontra a segunda. Não há
  "promoção de origem" a fazer; o PRD é corrigido neste ponto.

### `scheduler/src/services/atendimento.py`

- **Modificar.** Acrescentar, depois de `pode_responder`:

```python
PAUSA_ATENDENTE = "attendant"
PAUSA_CLINICA = "clinic_paused"
PAUSA_FORA_DA_REGRA = "not_eligible"


def motivo_da_pausa(clinic, session, phone, agora=None):
    """Por que o bot NÃO responde esta conversa, ou None quando responde.

    A mesma ordem de `pode_responder`, dita em palavras para o painel: alguém da
    clínica está na conversa; a clínica pausou o bot; a política não cobre
    este número. Era calculado inline em três handlers, e os três tinham de
    concordar entre si e com `pode_responder`.
    """
    clinic = clinic or {}
    session = session or {}
    agora = _agora(agora)
    if esta_com_pessoa(session, agora):
        return PAUSA_ATENDENTE
    if clinic.get("bot_paused"):
        return PAUSA_CLINICA
    if not _politica_permite(clinic, session, phone, agora):
        return PAUSA_FORA_DA_REGRA
    return None
```

- Observação de ordem: `pode_responder` confere `bot_paused` antes de
  `esta_com_pessoa`, mas para o painel "com atendente" é mais útil que "clínica
  pausada" (é o que a recepção pode agir). Os handlers já faziam nesta ordem;
  a função só a formaliza.

### `scheduler/src/functions/attendant/list_active.py` e `handler.py` (`_handle_status`)

- **Modificar.** Substituir os blocos

```python
"pause_reason": (
    "attendant" if atendente_ativo
    else "clinic_paused" if clinic.get("bot_paused", False)
    else "not_eligible" if not responde
    else None
),
```

por `"pause_reason": atendimento.motivo_da_pausa(clinic, session, phone, now)`.
`bot_paused` continua `not responde`. Em `list_active` o telefone é o da sessão
(`sk` sem `PHONE#`).

### `scheduler/src/functions/attendant/handler.py` (`_agendar_retomada`)

- **Modificar.** Depois de `ha_pergunta_em_aberto` e antes do `invoke`:

```python
clinic_completa = _get_clinic_completa(clinic_id)   # SELECT * (precisa da janela de silêncio)
if not atendimento.pode_iniciar(clinic_completa, session, phone):
    logger.info(f"[Attendant] {phone}: há pergunta pendente, mas a porta está fechada agora; só ativei")
    return False
```

- `_agendar_retomada` passa a receber `session` (a já gravada, com
  `bot_enabled=True` e retomada). `_get_clinic` hoje seleciona só três colunas;
  criar `_get_clinic_completa` com `SELECT *` (a janela de silêncio mora em
  outras colunas) ou ampliar o SELECT existente. A execução assíncrona continua
  conferindo por conta própria (`responder_se_ficou_em_aberto`); aqui é só para
  a resposta HTTP não prometer o que não vai sair.
- Resposta: acrescentar `"motivo_sem_resposta": "fora_do_horario"` quando este
  guard barrar, para o painel poder mostrar "O bot responde quando a clínica
  abrir". Opcional na tela nesta entrega; o campo fica pronto.

### `scheduler/src/functions/attendant/conversations.py`

- **Modificar.** Depois de montar `conversations` e antes do enriquecimento de
  nomes:

```python
from src.services import atendimento
from src.services.session_store import carrega_sessoes_da_clinica  # ver abaixo

clinic = _get_clinic(clinic_id)              # mesma função de list_active (mover para um util comum ou duplicar o SELECT de 3 colunas)
sessoes = carrega_sessoes_da_clinica(clinic_id)   # {phone: session}
now = int(time.time())
for phone, conv in conversations.items():
    sessao = sessoes.get(phone, {})
    motivo = atendimento.motivo_da_pausa(clinic, sessao, phone, now)
    conv["pause_reason"] = motivo
    conv["bot_paused"] = motivo is not None
```

- `carrega_sessoes_da_clinica(clinic_id)`: uma `query` por `pk = CLINIC#{id}`
  (a mesma de `list_active`), devolvendo `{phone: item["session"]}` só para
  `sk` que começa com `PHONE#`. Colocar em `session_store.py`, ao lado de
  `carrega_sessao`, e usar também em `list_active` para não haver duas
  queries iguais escritas à mão.
- Conversa sem sessão (telefone que só aparece em `MessageEvents`) usa sessão
  vazia: em `LEADS_ONLY` vira `not_eligible`, que é exatamente o cenário 3.
- Falha ao ler clínica ou sessões não derruba a lista: `pause_reason` fica
  ausente e o front não mostra selo. Logar como warning.

### `scheduler/tests/unit/test_elegibilidade_do_bot.py`

- **Modificar.** Trocar `test_origem_que_nao_e_landing_page` por:

```python
def test_origem_whatsapp_ou_vazia_nao_pode(self):
    for origem in ("whatsapp", None, ""):
        with self.subTest(origem=origem):
            self.assertEqual(por_que_nao_pode(lead(source=origem), CLINICA_ABERTA), "ORIGEM")

def test_qualquer_outra_origem_pode(self):
    """Decisão de 31/10/2026: lead cadastrado por qualquer caminho que não o WhatsApp."""
    for origem in ("landing-page", "painel", "harmonizacao", "indicacao"):
        with self.subTest(origem=origem):
            self.assertIsNone(por_que_nao_pode(lead(source=origem), CLINICA_ABERTA))
```

- `test_leads_only_pode_para_landing_page` ganha um irmão com `source="painel"`.

### `scheduler/tests/unit/test_lead_que_escreve_primeiro.py`

- **Modificar** `test_e_as_duas_consultas_continuam_existindo`: a asserção
  `any("landing-page" in q ...)` vira `any("source <> %s" in q ...)`, com a
  mensagem "sumiu a busca do lead cadastrado que habilita o bot". Acrescentar
  um teste AST de que `ORIGEM_SEM_DIREITO` é importado de
  `elegibilidade_do_bot` no webhook (mesmo molde de
  `test_o_webhook_importa_a_funcao_de_variantes`): é o que garante a fonte
  única.

### `scheduler/tests/unit/test_motivo_da_pausa.py` (novo)

- Casos: sessão com pessoa -> `attendant` mesmo com clínica pausada; clínica
  pausada sem pessoa -> `clinic_paused`; `LEADS_ONLY` sem `bot_enabled` ->
  `not_eligible`; `LEADS_ONLY` com `bot_enabled` -> `None`; `ALL` -> `None`;
  `OFF` -> `not_eligible`; PILOT fora da lista -> `not_eligible`.
- Um teste de coerência: para uma grade de clínicas e sessões,
  `(motivo_da_pausa(...) is None) == pode_responder(...)`. É o que impede as
  duas funções de divergirem.

### `scheduler/tests/unit/test_conversations_com_motivo.py` (novo)

- Mock de `boto3.resource` (tabela de eventos devolve três telefones; tabela de
  sessões devolve sessão só para um deles, com pessoa) e de `PostgresService`
  (clínica `LEADS_ONLY`). Esperado: o com pessoa -> `attendant`; os sem sessão ->
  `not_eligible`, `bot_paused: true`.
- Falha ao carregar sessões: lista volta sem `pause_reason` e com 200.

### `scheduler/tests/unit/test_conversation_resume.py`

- **Modificar.** Caso novo em `_agendar_retomada`: pergunta em aberto mas
  `pode_iniciar` falso (clínica em janela de silêncio) -> não invoca a Lambda e
  devolve `False`; a resposta HTTP de `deactivate` traz
  `answering_open_question: false` e `motivo_sem_resposta: "fora_do_horario"`.
- Caso `not_eligible`: sessão sem `bot_enabled`, clínica `LEADS_ONLY`, último
  evento INBOUND -> `deactivate` grava `bot_enabled`, invoca a retomada e
  devolve `answering_open_question: true`. É o cenário 3 do PRD, hoje sem
  teste direto.

### `frontend/src/lib/motivoDaPausa.ts` (novo)

```ts
import type { PauseReason } from '@/types'

/** Explicação completa, para o cabeçalho da conversa aberta. */
export const MOTIVO_DA_PAUSA: Record<NonNullable<PauseReason>, string> = {
  attendant: 'Atendimento humano em andamento',
  clinic_paused: 'Bot desligado para toda a clínica',
  not_eligible: 'Fora da regra de resposta automática',
}

/** Rótulo curto, para o selo na lista. */
export const SELO_DA_PAUSA: Record<NonNullable<PauseReason>, string> = {
  attendant: 'Com atendente',
  clinic_paused: 'Bot pausado',
  not_eligible: 'Fora da regra',
}

export const FILTROS = ['todas', 'fora_da_regra', 'com_atendente', 'bot_ativo'] as const
export type Filtro = (typeof FILTROS)[number]

export function passaNoFiltro(pauseReason: PauseReason | undefined, filtro: Filtro): boolean {
  switch (filtro) {
    case 'todas': return true
    case 'fora_da_regra': return pauseReason === 'not_eligible'
    case 'com_atendente': return pauseReason === 'attendant'
    case 'bot_ativo': return !pauseReason
  }
}
```

### `frontend/src/types/index.ts`

- `ConversationPreview` ganha `bot_paused?: boolean` e `pause_reason?: PauseReason`
  (opcionais: backend antigo não os manda).

### `frontend/src/pages/bot/components/ConversationList.tsx`

- Props novas: `onResume: (phone: string) => void`, `resumeLoadingPhone: string | null`.
- Por linha, à direita do horário: selo `SELO_DA_PAUSA[conv.pause_reason]`
  quando houver motivo (cores: `not_eligible` âmbar, `attendant` azul,
  `clinic_paused` cinza). Sem motivo, sem selo.
- Em `not_eligible`: botão pequeno "Ativar bot" na linha, com
  `e.stopPropagation()` para não abrir a conversa, `loading` quando
  `resumeLoadingPhone === conv.phone`. A linha deixa de ser um `<button>` único
  (botão dentro de botão é HTML inválido): vira `<div role="button" tabIndex=0>`
  com `onKeyDown` para Enter/Espaço, ou `<li>` com o botão de abrir separado.
- Estado vazio do filtro: "Nenhuma conversa neste filtro".

### `frontend/src/pages/bot/BotPage.tsx`

- `const [filtro, setFiltro] = useState<Filtro>('todas')`; barra de chips acima
  da lista com os quatro filtros (mesmo estilo dos chips de período das
  métricas) e a contagem entre parênteses.
- `conversations={(recentData?.conversations ?? []).filter((c) => passaNoFiltro(c.pause_reason, filtro))}`.
- `onResume={(phone) => ativar(phone)}` onde `ativar` é a mesma função do
  `onResume` da thread (extrair a função que hoje está inline, com o
  `setAnsweringPhone` e o timeout), para a linha e o cabeçalho fazerem a
  mesma coisa.
- `resumeLoadingPhone={resumeBot.isPending ? resumeBot.variables ?? null : null}`.

### `frontend/src/pages/bot/components/ConversationThread.tsx`

- Remover a constante local `MOTIVO_DA_PAUSA`; importar de `@/lib/motivoDaPausa`.

### `frontend/src/pages/bot/components/ConversationList.test.tsx` (novo)

- Selo "Fora da regra" aparece para `not_eligible` e não aparece quando
  `pause_reason` é `null` ou ausente.
- "Ativar bot" só na linha `not_eligible`; clicar chama `onResume(phone)` e não
  chama `onSelect`.
- `passaNoFiltro`: tabela de casos.

### Documentação

- `scheduler/tests/integration/031-quem-o-bot-responde.md`: os três cenários
  com curl (criar lead pelo painel com origem `painel`, simular webhook de um
  número avulso, `GET conversations` mostrando `not_eligible`, `POST
  attendant/deactivate` e a resposta chegando).
- Postman 031: `GET conversations` (asserta `pause_reason` presente) e `POST
  attendant/deactivate` (asserta `answering_open_question` booleano).
- TASKS_LOG e status do PRD.

---

## 7. Convenções a respeitar

- Fonte única: a regra de origem vive em `elegibilidade_do_bot` e o motivo da
  pausa em `atendimento`; nenhum handler ou componente reescreve a regra
  (memória "fonte única de verdade").
- Logging com prefixo do módulo (`[Attendant]`, `[Conversations]`, `[Webhook]`).
- Frontend: named exports, 4 estados, TanStack Query; nada de `any`; lint zero.
- Testes de comportamento, não de texto do fonte (exceto os AST já existentes
  que protegem a fonte única).
- Branch `feat/031-quem-o-bot-responde`, PR para `main`. Deploy do scheduler
  manual; frontend pela Vercel no merge.
