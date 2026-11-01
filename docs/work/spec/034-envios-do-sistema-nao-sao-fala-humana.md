# Spec - 034 Envios do sistema não são fala humana

> Gerada na fase **Spec** em 01/11/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/034-envios-do-sistema-nao-sao-fala-humana.md`

---

## 1. Resumo

Um ponto único de envio para mensagens do sistema fora do agente
(`envio_do_sistema.envia_texto`), que manda pelo provedor e grava o evento no
MessageEvents com o `providerMessageId` e `metadata.origem`. OTP, confirmação
e orientações do site e link de cobrança do check-in passam a usar esse ponto.
O webhook não muda: ele já reconhece eco por id (`foi_enviada_pelo_bot`). O
histórico do agente deixa de ver o OTP e rotula o resto como `[sistema]`. A
API de mensagens do painel passa a dizer quem enviou (`autor`), e a aba Bot
mostra um rótulo para atendente e para mensagem automática. A role da Lambda
do site ganha `PutItem` na tabela de eventos; sem isso o rastreio falha em
silêncio.

Achado da pesquisa que muda o plano: a Lambda `PublicBooking` é uma só para
OTP, agendamento e check-in, e a role dela só escreve em `booking-otp-codes`.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/src/services/envio_do_sistema.py` | `ORIGENS`, `envia_texto(clinic, phone, content, origem, *, conteudo_registrado=None) -> SendResult` |
| `scheduler/tests/unit/test_envio_do_sistema.py` | rastreio QUEUED→SENT com id e origem; falha vira FAILED; OTP gravado redigido; tabela fora do ar não derruba o envio |
| `scheduler/tests/unit/test_historico_ignora_o_sistema.py` | `events_to_history`: OTP some; confirmação entra como `[sistema]` no papel `user` |
| `scheduler/tests/unit/test_autor_da_mensagem_no_painel.py` | `attendant/messages.py`: `autor` em HUMANO / SISTEMA / BOT |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/utils/booking_verification.py` | `generate_and_send_code` usa `envia_texto(..., origem=SITE_OTP, conteudo_registrado="Código de confirmação enviado (expira em 5 minutos).")`; remove a construção manual de `ZApiProvider` |
| `scheduler/src/functions/public_booking/create_appointment.py` | `_send_confirmation_whatsapp` usa `envia_texto(..., origem=SITE_AGENDAMENTO)` nos dois envios; remove `ZApiProvider` |
| `scheduler/src/services/checkin.py` | o envio do link usa `envia_texto(..., origem=CHECKIN)`; `whatsapp_de` deixa de ser necessário para enviar texto |
| `scheduler/src/services/conversation_agent.py` | `events_to_history`: pula `origem == SITE_OTP`; outras origens viram turno `user` com prefixo `[sistema]: ` (mesma mecânica de `foi_de_pessoa_da_clinica`) |
| `scheduler/src/functions/attendant/messages.py` | cada mensagem ganha `autor`: `HUMANO` se `metadata.autor == HUMANO` ou (SENT sem providerMessageId); `SISTEMA` se `metadata.origem`; senão `BOT`. INBOUND não tem `autor` |
| `scheduler/sls/functions/public_booking/interface.yml` | role `PublicBooking`: `dynamodb:PutItem` em `${resourcePrefix}-message-events` |
| `frontend/src/types/index.ts` | `ConversationMessage.autor?: 'HUMANO' \| 'SISTEMA' \| 'BOT'` |
| `frontend/src/pages/bot/components/ConversationThread.tsx` | balão OUTBOUND com `autor` HUMANO ou SISTEMA mostra rótulo de 10px acima do texto: "atendente" / "automática" |

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação

1. `envio_do_sistema.py` + teste (sem tocar em quem chama).
2. `interface.yml` da Lambda do site (a permissão antes do código que a usa).
3. Os três chamadores: OTP, confirmação do site, check-in.
4. `events_to_history` + teste.
5. `attendant/messages.py` + teste; depois o front (tipo e rótulo).
6. Deploy do scheduler em dev, agendar pelo site de dev, conferir os critérios de aceite do PRD no log do webhook e na sessão. Depois prod. O front sobe pela Vercel no merge.

---

## 6. Detalhes por arquivo

### `scheduler/src/services/envio_do_sistema.py` (criar)

```python
SITE_OTP = "SITE_OTP"
SITE_AGENDAMENTO = "SITE_AGENDAMENTO"
CHECKIN = "CHECKIN"
ORIGENS = {SITE_OTP, SITE_AGENDAMENTO, CHECKIN}

def envia_texto(clinic, phone, content, origem, *, conteudo_registrado=None) -> SendResult
```

- `origem` fora de `ORIGENS` levanta `ValueError` na hora: origem é contrato
  com o painel e o histórico, não texto livre.
- `provider = get_provider(clinic)` (`whatsapp_provider.get_provider`), o
  mesmo que o check-in já usa. Os dois pontos do site constroem `ZApiProvider`
  à mão com os mesmos três campos; passam a usar a fábrica.
- Mesma sequência de `agent_runner`: `track_outbound(status="QUEUED")`,
  `provider.send_text`, `track_outbound(status="SENT"|"FAILED",
  provider_message_id=..., provider_response=...)`. `message_id` é um
  `uuid4` só, para as duas linhas colapsarem no painel (`messages.py` agrupa
  por `messageId`).
- `metadata={"origem": origem}` nas DUAS gravações. Em falha, acrescenta
  `"error": result.error`. `MessageTracker._sanitize_for_dynamo` já cuida do
  tipo.
- `conteudo_registrado`: o que vai para o MessageEvents no lugar de
  `content`. O OTP é segredo de 5 minutos e o MessageEvents vive 60 dias e
  aparece no painel: grava-se o aviso, não o código. Os outros passam `None`
  e o texto real é gravado.
- `conversation_id = f"{clinic_id}#{phone}"`, como o bot.
- Rastreio nunca derruba o envio: `track_outbound` já engole exceção e loga
  `[MessageTracker] Erro ao rastrear outbound`. O chamador recebe o
  `SendResult` do provedor e decide o que fazer (o OTP levanta
  `SendFailedError`, o site só loga, o check-in devolve `sent`).
- Log: `[EnvioDoSistema] {origem} {clinic_id} tel=***{4 últimos} enviado={bool}`.
  Nunca o conteúdo.

### `scheduler/src/utils/booking_verification.py`

- `generate_and_send_code`: trocar o bloco `provider = ZApiProvider(...)` +
  `provider.send_text(phone, message)` por
  `envia_texto(clinic, phone, message, SITE_OTP, conteudo_registrado="Código de confirmação enviado (expira em 5 minutos).")`.
- O resto (TTL, dev devolve o código, `SendFailedError`) não muda.
- O import de `ZApiProvider` sai.

### `scheduler/src/functions/public_booking/create_appointment.py`

- `_send_confirmation_whatsapp`: remover a construção do provider; os dois
  `provider.send_text(phone, ...)` viram `envia_texto(clinic, phone, ...,
  SITE_AGENDAMENTO)`. Os dois `try` separados continuam: falha num não impede
  o outro.
- O import de `ZApiProvider` sai.

### `scheduler/src/services/checkin.py`

- No envio do link (`whatsapp_de(clinica).send_text(appt["patient_phone"],
  _mensagem_do_link(...))`): `envia_texto(clinica, appt["patient_phone"],
  _mensagem_do_link(...), CHECKIN)`. `enviado = bool(resposta.success)` fica.
- Se `whatsapp_de` só servia a esse envio, apagar; se outro ponto do
  check-in usa o provedor para outra coisa, manter. Conferir na hora.

### `scheduler/src/services/conversation_agent.py`

- Nova função ao lado de `foi_de_pessoa_da_clinica`:

```python
def origem_do_sistema(event) -> Optional[str]:
    """`metadata.origem` de um OUTBOUND enviado pelo sistema (PRD 034), ou None."""
```

- Em `events_to_history`, logo após o `continue` do conteúdo vazio:
  - `if origem_do_sistema(event) == SITE_OTP: continue` (o código não é
    conversa; e é segredo).
  - `elif origem_do_sistema(event)`: `papel = "user"`,
    `content = f"[sistema]: {content}"`. Entra como fato que a clínica
    comunicou, não como fala do bot: o modelo não deve "continuar" uma
    confirmação que não fez, pela mesma razão da fala da atendente.
- Docstring com a data e o caso (21/10/2026, três ecos do site).

### `scheduler/src/functions/attendant/messages.py`

- Na montagem de `msg`, incluir `item.get("metadata")` na leitura e derivar:

```python
def _autor(item) -> Optional[str]:
    if item.get("direction") != "OUTBOUND":
        return None
    meta = item.get("metadata") or {}
    if meta.get("origem"):
        return "SISTEMA"
    if meta.get("autor") == "HUMANO" or (item.get("status") == "SENT" and not item.get("providerMessageId")):
        return "HUMANO"
    return "BOT"
```

- A regra de HUMANO é a MESMA de `conversation_agent.foi_de_pessoa_da_clinica`.
  Para não nascer uma terceira cópia, mover `foi_de_pessoa_da_clinica` e
  `origem_do_sistema` para `src/services/autoria_mensagem.py` (que já tem
  `foi_enviada_pelo_bot`) e importar dos dois lugares.
- Ao colapsar QUEUED/SENT por `messageId`, `autor` vem da linha que tem
  `metadata`; promover como já se faz com `providerMessageId`.
- `autor` entra no JSON de resposta de `GET /attendant/{clinicId}/messages/{phone}`.

### `frontend/src/types/index.ts`

- `ConversationMessage` ganha `autor?: 'HUMANO' | 'SISTEMA' | 'BOT'`.

### `frontend/src/pages/bot/components/ConversationThread.tsx`

- No balão OUTBOUND, antes de `<p>{msg.content}</p>`:
  `{msg.autor === 'HUMANO' ? <span ...>atendente</span> : msg.autor === 'SISTEMA' ? <span ...>automática</span> : null}`,
  `text-[10px] uppercase tracking-wide text-brand-200`. Cor do balão não muda:
  tudo que saiu do número da clínica continua à direita.
- Sem estado novo: é só leitura do campo. Os 4 estados da tela já existem.

### `scheduler/sls/functions/public_booking/interface.yml`

- Na role de `PublicBooking`, novo statement:

```yaml
    - Effect: Allow
      Action:
        - dynamodb:PutItem
      Resource:
        - "arn:aws:dynamodb:${self:provider.region}:${self:custom.accountId}:table/${self:custom.resourcePrefix}-message-events"
```

- Comentário no yml com o motivo (PRD 034: sem isto o `put_item` falha,
  `MessageTracker` engole, e o eco volta a parecer atendente).
- Não cria recurso novo no CloudFormation (a role já existe); o stack segue
  em 463/500.

---

## 7. Testes

Por comportamento, com tabela falsa que GRAVA o que recebe (ver
`feedback_dublagem_aplica_a_condicao`): o teste lê o item gravado, não o
mock chamado.

- `test_envio_do_sistema.py`
  - envio com sucesso: dois `put_item` com o mesmo `messageId`, o segundo com
    `status=SENT`, `providerMessageId` do provedor falso e
    `metadata.origem`.
  - OTP: o `content` gravado é o aviso, não o código; o provedor falso recebeu
    o código.
  - provedor falha: segundo item `FAILED` com `metadata.error`; o `SendResult`
    devolvido tem `success=False`.
  - `put_item` levanta: o provedor ainda é chamado e o `SendResult` é o dele.
  - origem desconhecida: `ValueError` antes de enviar.
- `test_historico_ignora_o_sistema.py`: lista de eventos com INBOUND, OTP,
  confirmação e resposta do bot; o histórico não tem o código e tem
  `[sistema]: Agendamento confirmado...` no papel `user`.
- `test_autor_da_mensagem_no_painel.py`: três OUTBOUND (bot com id, humano
  sem id, sistema com origem) e um INBOUND; `autor` correto e ausente no
  INBOUND.
- Já existe `test_autoria_mensagem.py`: ganha um caso "id gravado pelo site é
  eco" com o `providerMessageId` que `envia_texto` grava, para deixar escrito
  que o webhook depende disso.

---

## 8. Verificação após deploy (dev, depois prod)

1. Agendar pelo site com um número de teste. No log de `WhatsAppWebhook`,
   filtrar pelo número: os três ecos devem sair como `Eco do próprio bot`, e
   não pode haver `Modo atendente ativado/renovado`.
2. `conversation-sessions`, item `CLINIC#..`/`PHONE#..`: bloco `atendimento`
   com `handler` que não seja `HUMAN_ACTIVE`.
3. Mandar "qual o horário mesmo?" desse número: o bot responde.
4. Aba Bot do painel: OTP aparece como "automática" com o texto redigido;
   confirmação como "automática".
5. `agent_history` da sessão não contém "código de confirmação".
6. Check-in com link de cobrança em dev: mesmo roteiro do item 1.

---

## 9. Convenções

- Logging com prefixo de módulo entre colchetes, sem conteúdo de mensagem.
- Nada de `any` no front; export nomeado.
- Testes `unittest` em `scheduler/tests/unit`, com `os.environ.setdefault`
  das tabelas no topo, como `test_autoria_mensagem.py`.
- Deploy do scheduler é manual (`serverless deploy`), perfil `dev-andre`;
  o front sobe pela Vercel no merge.
