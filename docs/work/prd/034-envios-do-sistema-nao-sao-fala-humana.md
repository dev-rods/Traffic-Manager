# PRD - 034 Envios do sistema não são fala humana

> Gerado na fase **Research** em 01/11/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Toda mensagem que o sistema manda pelo WhatsApp da clínica deve ser
reconhecida como mensagem do sistema quando o z-api a devolve ao webhook: não
pausa o bot, não aparece no painel como fala da recepção e não entra no
histórico do agente como se fosse turno de alguém.

Hoje três caminhos escapam: o OTP e a confirmação do site público, e o link de
cobrança do check-in.

---

## 2. Contexto

O WhatsApp da clínica tem um número só. O z-api devolve ao webhook toda
mensagem que sai dele (`fromMe = true`), venha do bot, do site, do check-in ou
do celular da atendente. O que separa uma da outra é o `providerMessageId`: ao
enviar, o bot grava o evento no MessageEvents com o id que o provedor devolveu
(`MessageTracker.track_outbound`), e o webhook, ao receber o eco, procura esse
id (`autoria_mensagem.foi_enviada_pelo_bot`). Id conhecido é eco; id
desconhecido é alguém digitando no celular, e aí o webhook grava a mensagem
como `metadata.autor = HUMANO` e chama `_activate_attendant_mode`, que entrega
a conversa à pessoa por 24 horas (`atendimento.renova_por_mensagem_da_clinica`).

Quem envia direto pelo provedor, sem o tracker, cai no segundo caso:

| Caminho | Onde | Rastreia? |
|---|---|---|
| Bot (agente) | `agent_runner.py`, `webhook/handler.py` | sim |
| Painel (`POST /send`) | `send/handler.py` | sim |
| Lembretes | `reminder/processor.py` | sim |
| Relatório diário | `report/daily.py` | sim |
| Campanha/disparo | via `send/handler.py` | sim |
| **OTP do site** | `utils/booking_verification.generate_and_send_code` | **não** |
| **Confirmação e orientações do site** | `public_booking/create_appointment._send_confirmation_whatsapp` | **não** |
| **Link de cobrança do check-in** | `services/checkin.py` (`whatsapp_de(clinica).send_text`) | **não** |

Evidência em prod (Essência, 21/10/2026 20:02 UTC, paciente que remarcou pelo
site): três mensagens seguidas do site, e para cada uma o log do webhook diz
`Atendente humano respondeu ... pelo celular; pausando o bot por 24h` e `Modo
atendente ativado/renovado (TTL 24h)`.

Tamanho em outubro de 2026 (MessageEvents da Essência, eventos OUTBOUND sem
`providerMessageId`): 35 OTPs em 16 conversas e 44 confirmações em 35
conversas. Cerca de 40 conversas ficaram com o bot calado por 24 horas logo
depois de a pessoa agendar pelo site, que é justamente quando ela costuma
perguntar algo ("qual o horário mesmo?", "posso ir mais cedo?"). O painel
mostra "Seu código de confirmação é 362447" como se a recepção tivesse
digitado, e o agente recebe esse texto no histórico como turno `assistant`.

Por que foi assim: o site e o check-in nasceram depois da regra de autoria
(PRD 020 §3.4) e construíram o provedor na mão, sem o tracker. Não é regressão.

---

## 3. Escopo

### Dentro do escopo
- Um ponto único de envio para mensagens do sistema fora do agente:
  `services/envio_do_sistema.py` (nome sugerido) com `envia_texto(clinica,
  phone, content, origem)` que chama o provedor e grava o evento no
  MessageEvents com o `providerMessageId` e `metadata.origem` em
  `{SITE_OTP, SITE_AGENDAMENTO, CHECKIN}`. Falha de rastreio não derruba o
  envio (log de erro), como já é no bot.
- Os três caminhos passam a usar esse ponto: OTP, confirmação + orientações
  do site, link de cobrança do check-in.
- `conversation_agent.events_to_history`: evento com `metadata.origem` do
  sistema entra como turno do usuário rotulado (`[sistema]: ...`) ou é
  ignorado; decidir na Spec. OTP não deve entrar de jeito nenhum: é segredo
  de curta duração e ruído para o modelo.
- Painel: o evento com `origem` aparece como mensagem automática (rótulo
  "sistema"), não como atendente nem como bot. Conferir onde a aba de
  conversas decide a autoria e ajustar.
- Testes por comportamento (ver `feedback_dublagem_aplica_a_condicao`):
  a tabela falsa recebe o item com `providerMessageId` e `origem`; o webhook,
  ao receber o eco com esse id, NÃO ativa modo atendente; o histórico não
  contém o OTP.

### Fora do escopo
- Relatório diário e lembretes: já rastreiam.
- Mensagens que a atendente manda pelo celular: continuam sendo fala humana e
  continuam pausando o bot. Esse é o comportamento certo.
- Reprocessar as ~40 conversas de outubro: a pausa de 24 h já venceu.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/envio_do_sistema.py` | criar | envio + rastreio com origem |
| `scheduler/src/utils/booking_verification.py` | modificar | OTP pelo envio rastreado |
| `scheduler/src/functions/public_booking/create_appointment.py` | modificar | confirmação e orientações pelo envio rastreado |
| `scheduler/src/services/checkin.py` | modificar | link de cobrança pelo envio rastreado |
| `scheduler/src/services/conversation_agent.py` | modificar | histórico ignora/rotula origem do sistema |
| `scheduler/src/functions/attendant/messages.py` e tela de conversas do painel | modificar | autoria "sistema" |
| `scheduler/tests/unit/...` | criar | os três comportamentos |

---

## 5. Dependências e riscos

- **Dependência:** `MessageTracker` lê `MESSAGE_EVENTS_TABLE` do ambiente; as
  Lambdas do site e do check-in precisam ter a variável e permissão de
  `PutItem` na tabela. Conferir em `sls/functions/*.yml` antes de assumir.
- **Risco:** o eco do z-api pode chegar ANTES de o `put_item` terminar (o bot
  já convive com isso usando `ECO_JANELA_DE_BUSCA`). Gravar o evento antes de
  devolver a resposta HTTP do site reduz a janela; medir no log `[Webhook] Eco
  do próprio bot` após o deploy.
- **Risco:** o painel hoje pode inferir "bot" de todo OUTBOUND sem `autor`;
  o OTP passaria a aparecer como mensagem do bot. Por isso o rótulo "sistema"
  entra no mesmo PR.

---

## 6. Critérios de aceite

- [ ] Agendar pelo site em prod e, no log do webhook, os três ecos saem como
      `Eco do próprio bot`, sem `Modo atendente ativado`.
- [ ] A sessão da pessoa continua `BOT_ACTIVE` depois do agendamento pelo site;
      uma pergunta dela em seguida é respondida pelo bot.
- [ ] No painel, OTP e confirmação aparecem como mensagem automática.
- [ ] O OTP não aparece no `agent_history` da sessão.
- [ ] Link de cobrança do check-in idem.
- [ ] Testes unitários dos três comportamentos passando.

---

## 7. Referências

- PRD 020 §3.4 (autoria da mensagem; só a clínica renova o prazo humano)
- PRD 033 (onde o efeito foi encontrado, na varredura das conversas de outubro)
- `scheduler/src/services/autoria_mensagem.py` (a regra do id conhecido)

---

## Status

- [ ] Pendente
- [x] Spec gerada: `spec/034-envios-do-sistema-nao-sao-fala-humana.md`
- [x] Implementado em: 01/11/2026
- [x] Registrado em `TASKS_LOG.md`
