# PRD - 031 Quem o bot responde: os três cenários fechados

> Gerado na fase **Research** em 31/10/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Fechar as brechas entre a regra de resposta automática que existe hoje
(`LEADS_ONLY`) e os três cenários que o André definiu para o WhatsApp de uma
clínica:

1. **Lead cadastrado que escreve primeiro** (clicou no WhatsApp do site): o bot
   responde sempre.
2. **Lead cadastrado que não escreveu, e a equipe clica "Iniciar pelo Bot"**: o
   bot inicia e continua a conversa sempre.
3. **Mensagem avulsa** de quem nunca passou pelo cadastro: o bot **não**
   responde de início. A recepção precisa enxergar essas conversas de cara no
   painel e, com um clique, colocar o bot para continuar o atendimento, já
   respondendo o que a pessoa perguntou.

Os três cenários já funcionam em parte. Este PRD entrega o que falta: lead de
qualquer origem que não seja WhatsApp conta como "cadastrado"; a lista de
conversas mostra por que o bot está calado; e "Ativar bot" responde na hora a
pergunta que ficou pendente.

---

## 2. Contexto

Levantamento feito em 31/10/2026 sobre `atendimento.pode_responder` e o
webhook, enquanto a Nobre Laser se preparava para ligar o WhatsApp:

| Cenário | Hoje | Brecha |
|---|---|---|
| 1 | O webhook procura um lead com o telefone e `source = 'landing-page'`; achando, marca `bot_enabled` e o bot responde | Só landing page conta. Lead criado pelo painel ou por outra integração fica mudo. |
| 2 | "Iniciar pelo Bot" enfileira a abordagem e marca `bot_enabled` | `elegibilidade_do_bot.ORIGENS_PERMITIDAS = {"landing-page"}`: a mesma restrição. |
| 3 | A mensagem cria um lead `source = 'whatsapp'`, o bot não responde; ao abrir a conversa o painel mostra "Fora da regra de resposta automática" e o botão "Ativar bot" | A lista de conversas não distingue essas conversas: é preciso abrir uma a uma. "Ativar bot" libera a conversa mas o bot só fala quando a pessoa escrever de novo; a primeira pergunta fica sem resposta. |

O André decidiu, em 31/10/2026:

- Item 1 do levantamento: selo na lista para "fora da regra", **e também** para
  os outros motivos de o bot estar calado (com atendente, clínica pausada).
- Item 2: "Ativar bot" responde na hora à mensagem pendente.
- Item 3: lead criado fora da landing page dá direito ao bot, **desde que a
  origem não seja `whatsapp`** (a origem `whatsapp` é justamente a marca do
  cenário 3).

A política continua sendo `LEADS_ONLY`. `ALL`, `PILOT` e `OFF` não mudam.

---

## 3. Escopo

### Dentro do escopo

**A. Origem do lead (cenários 1 e 2)**

- A regra "lead cadastrado" passa a ser `source <> 'whatsapp'`, numa função
  única (`lead_service` ou `elegibilidade_do_bot`), usada pelos dois pontos
  que hoje repetem `'landing-page'`:
  - `webhook/handler.py` (marcação de `bot_enabled` quando a pessoa escreve);
  - `elegibilidade_do_bot.ORIGENS_PERMITIDAS` (botão "Iniciar pelo Bot").
- Texto do motivo `ORIGEM` muda para "Quem chegou pelo WhatsApp não pode ser
  iniciado pelo bot."
- Um lead que nasceu `whatsapp` e depois preenche o formulário do site: o
  `upsert_lead` já existe; a Spec define se a origem é atualizada para a
  nova (recomendação: sim, a origem mais forte vence, e a conversa passa a
  ser elegível na próxima mensagem).

**B. Lista de conversas (cenário 3)**

- `GET /clinics/{clinicId}/conversations` já devolve `pause_reason`
  (`attendant | clinic_paused | not_eligible | null`). Nada muda na API.
- `ConversationList` mostra um selo por linha: "Fora da regra" (not_eligible),
  "Com atendente" (attendant), "Bot pausado" (clinic_paused). Sem selo quando o
  bot responde.
- Filtro na `BotPage`: Todas / Fora da regra / Com atendente / Bot ativo. O
  filtro é só de exibição, no front.
- Ação rápida na própria linha para `not_eligible`: botão "Ativar bot", o mesmo
  da conversa aberta, sem precisar abrir a conversa.

**C. "Ativar bot" responde a pergunta pendente (cenário 3)**

- Ao clicar "Ativar bot" (ou "Retomar bot") numa conversa cujo **último evento
  é INBOUND** (a pessoa escreveu e ninguém respondeu), o backend, depois de
  liberar a conversa, aciona o agente com as mensagens INBOUND desde o último
  OUTBOUND, juntas, como se tivessem acabado de chegar.
- Mecanismo: `POST /attendant/deactivate` invoca a Lambda `WhatsAppWebhook`
  de forma assíncrona com um payload interno (`internal_task =
  "responder_pendente"`), reaproveitando `_processar_mensagem`. A fonte das
  mensagens é `MessageEvents` (`INBOUND` após o último `OUTBOUND` do
  telefone).
- Se o último evento for OUTBOUND (a atendente já respondeu pelo celular, ou
  o bot já falou), nada é enviado. É o que impede resposta em dobro.
- A resposta do agente passa pelas mesmas portas de sempre
  (`pode_responder`), já com a conversa liberada. A janela de silêncio não
  barra: quem clicou está respondendo a uma pessoa que escreveu.
- Resposta do endpoint ganha `respondeu_pendente: true | false` para o painel
  mostrar "Bot respondendo..." ou nada.

### Fora do escopo

- Mudar o comportamento de `ALL`, `PILOT` e `OFF`.
- Mudar a regra de 24h do atendimento humano e o cooldown (PRD 020).
- Classificar a conversa avulsa (é o PRD 026, CRM de leads).
- Botão de "Ativar bot" em massa.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/elegibilidade_do_bot.py` | modificar | `ORIGENS_PERMITIDAS` vira `origem_da_direito_ao_bot(source)`: tudo menos `whatsapp`; texto de `ORIGEM` |
| `scheduler/src/functions/webhook/handler.py` | modificar | Consulta do lead sem `source = 'landing-page'`, usando a mesma função; `internal_task = "responder_pendente"` |
| `scheduler/src/services/lead_service.py` | modificar | `upsert_lead` promove a origem quando a nova não é `whatsapp` (se a Spec confirmar) |
| `scheduler/src/functions/attendant/handler.py` | modificar | `_handle_deactivate` lê o último evento em `MessageEvents` e dispara `responder_pendente` quando é INBOUND; devolve `respondeu_pendente` |
| `scheduler/src/services/message_tracker.py` | modificar | Consulta "INBOUND desde o último OUTBOUND" para um telefone |
| `scheduler/sls/functions/attendant/interface.yml` | modificar | IAM para `lambda:InvokeFunction` do webhook e env com o nome da função |
| `frontend/src/pages/bot/components/ConversationList.tsx` | modificar | Selo por `pause_reason`; botão "Ativar bot" na linha |
| `frontend/src/pages/bot/BotPage.tsx` | modificar | Filtro Todas / Fora da regra / Com atendente / Bot ativo |
| `frontend/src/pages/bot/components/ConversationThread.tsx` | modificar | "Bot respondendo..." quando `respondeu_pendente` |
| `frontend/src/types/index.ts` | modificar | Resposta de `deactivate` |
| `scheduler/tests/unit/` | criar/modificar | `test_elegibilidade_do_bot`, `test_webhook_*` (origem), `test_attendant_responder_pendente` |
| `frontend/src/pages/bot/components/*.test.tsx` | criar/modificar | Selo, filtro, ação na linha |
| `scheduler/tests/integration/031-quem-o-bot-responde.md`, `tests/postman/031-*.json` | criar | Casos dos três cenários |

---

## 5. Dependências e riscos

- **Dependências:** `MessageEvents` (TTL 60 dias, PRD 022) é a fonte do
  "pendente". Conversa mais velha que isso não tem pendente a responder, o
  que é aceitável.
- **Risco - resposta em dobro:** a atendente respondeu pelo celular, o
  webhook ainda não registrou o `fromMe`, e alguém clica "Ativar bot". Janela
  de segundos; o critério "último evento é INBOUND" é a mitigação. A Spec
  define se vale esperar a janela de agrupamento do webhook antes de
  responder.
- **Risco - origem promovida:** promover `whatsapp` para a origem nova no
  `upsert_lead` muda relatórios por origem. Registrar a origem anterior em
  `metadata` para não perder o rastro.
- **Risco - PILOT:** o lead fora da lista piloto continua sem bot; o selo
  "Fora da regra" vai aparecer para ele também, e está certo.
- **Deploy:** backend e frontend independentes; sem migration. O frontend
  pode subir antes (o selo lê um campo que já existe).

---

## 6. Critérios de aceite

- [ ] Lead criado pelo painel (origem diferente de `whatsapp`) que escreve no
      WhatsApp recebe resposta do bot em `LEADS_ONLY`.
- [ ] "Iniciar pelo Bot" acende para lead de origem diferente de `whatsapp`
      e continua apagado para `whatsapp`, com o motivo novo.
- [ ] Mensagem avulsa não recebe resposta; a conversa aparece na lista com o
      selo "Fora da regra" e o filtro a isola.
- [ ] "Ativar bot" na linha ou na conversa aberta faz o bot responder a
      mensagem pendente em até alguns segundos, uma vez só.
- [ ] Depois de a atendente responder pelo celular, "Retomar bot" não manda
      nada até a pessoa escrever de novo.
- [ ] Selos "Com atendente" e "Bot pausado" aparecem nos respectivos casos.
- [ ] Suites do scheduler e do frontend verdes; lint zero.

---

## 7. Referências

- `scheduler/src/services/atendimento.py` (`pode_responder`, `_politica_permite`)
- `scheduler/src/services/elegibilidade_do_bot.py`
- `scheduler/src/functions/webhook/handler.py` (marcação de `bot_enabled`, `_processar_mensagem`)
- `scheduler/src/functions/attendant/list_active.py` (`pause_reason`)
- PRD 019 (pausa do bot), PRD 020 (atendimento único), PRD 022 (TTL de eventos), PRD 026 (CRM de leads)

---

## Status

- [x] Pendente
- [ ] Spec gerada: `spec/031-quem-o-bot-responde.md`
- [ ] Implementado em:
- [ ] Registrado em `TASKS_LOG.md`
