# PRD - 059 Cancelamento pela conversa: o bot cancela, confirma e convida a remarcar

> Gerado na fase **Research** em 23/11/2026, a partir de um pedido da Essência
> ("não basta responder ao paciente: o sistema precisa cancelar, registrar o
> status e liberar o horário") e de uma medição em prod, só leitura, de 60 dias
> de conversas. Decisão já tomada pelo André: o PRD 054 (menos de 24 h é
> falta) se mantém.

---

## 1. Objetivo

Quando a paciente diz na conversa que não vai, quer cancelar ou desmarcar, o
agendamento tem de sair da agenda **naquele momento**, com o desfecho do PRD
054, o horário liberado para outra pessoa, e ela tem de receber uma
confirmação que a convide a remarcar pelo site. Hoje isso só acontece em
parte, e quase sempre pela mão da recepção.

---

## 2. Contexto

### 2.1 O que existe

- `cancel_appointment` (tool do bot, `ai_tools.py`) chama
  `AppointmentService.cancel_appointment`: grava `CANCELLED` ou `NO_SHOW`
  conforme a antecedência (PRD 054), libera o horário (a grade só lê
  `CONFIRMED`), cancela o lembrete e passa a estreia adiante. É "tool com
  efeito": o agente é obrigado a responder dizendo o que fez.
- A skill (PRD 020 fase 7) só oferece a tool a quem tem sessão marcada.
- **Sobreposição de lembrete** (PRD 027, `lembrete.ferramentas_a_remover`):
  em clínica com domínio próprio, enquanto o lembrete está vivo (até o fim do
  dia da sessão), `cancel_appointment` **sai** e o prompt manda: "se ela quiser
  REMARCAR ou CANCELAR, NÃO execute nada: envie o link". Decisão de 27/10.
  Essência e Nobre têm domínio, então em prod o bot nunca cancela em resposta
  ao lembrete.
- O texto pós-cancelamento é livre: o modelo escreve o que quiser. O template
  `CANCELLED` ("Agendamento cancelado com sucesso.") é legado e não é usado
  pelo agente. O bloco do site (PRD 046) existe para pacientes, mas não há
  regra de citar o link **depois de cancelar**.
- Com a conversa entregue a uma pessoa (`atendimento.esta_com_pessoa`:
  ATENDENTE, HANDOFF, CONTATO_MANUAL, CHAT_ANTERIOR), o bot não lê nem responde
  (`atendimento.pode_responder`). A detecção de termos antes do modelo
  (`nivel_de_risco`, PRD 020 §4.3) roda só quando o bot vai responder.

### 2.2 O que os dados de prod mostraram (23/11/2026, só leitura)

Janela: MessageEvents dos últimos 60 dias, lembretes enviados
(ScheduledReminders `SENT`) e `appointments`. "Pedido de saída" é mensagem da
paciente com cancelar, desmarcar, remarcar, reagendar, adiar, "não vou
conseguir" e variantes. Script no scratchpad da sessão (`mede_cancel_prod.py`),
ids e telefones fora deste documento.

**Respostas ao lembrete (PRD 027)**

| | Qtd |
|---|---|
| Lembretes enviados | 82 |
| Com resposta até o fim do dia da sessão | 53 |
| Resposta com pedido de saída | 15 |
| Cancelado pelo **bot** | 0 |
| Paciente cancelou ou remarcou pelo **site** (OTP enviado depois do link) | 5 |
| Recepção cancelou ou marcou falta no **painel** | 7 |
| Ficou `CONFIRMED` com a data passada (ninguém mexeu) | 2 |
| Sessão futura, ainda aberta | 1 |

Quem cancelou pelo site o fez em até 30 min. Quem não clicou dependeu da
recepção, que respondeu em 9 das 15 conversas.

**Fora da janela do lembrete**

| | Qtd |
|---|---|
| Mensagens com pedido de saída (pacientes com agendamento) | 129 |
| Sem nenhuma resposta do bot, atendente respondeu | 105 |
| Bot cancelou | 4 |
| Bot mandou o link | 3 |
| Bot respondeu outra coisa (dúvida de data, área, sem agendamento ativo) | 12 |
| Sem resposta de ninguém | 5 (todas já estavam canceladas) |

Desfecho do agendamento mais próximo:

| | Qtd |
|---|---|
| Status mudou no mesmo dia (60 `CANCELLED`, 18 `NO_SHOW`) | 78 |
| Mudou antes ou dias depois | 18 |
| **Ficou `CONFIRMED` com a data passada** | 15 |
| Sessão futura, ainda aberta | 4 |
| Sem agendamento ativo na data (falso positivo ou já cancelado) | 14 |

### 2.3 O problema

1. Em 144 pedidos de saída em 60 dias, o bot cancelou 4. O trabalho é da
   recepção, no painel, mensagem por mensagem. Na janela do lembrete o bot tem
   ordem expressa de **não** cancelar.
2. 17 agendamentos (2 do lembrete, 15 fora) ficaram `CONFIRMED` depois da data
   com um pedido de saída na conversa: o horário não voltou para a agenda e o
   relatório os conta como realizados. É o caso que a clínica descreveu.
3. A mensagem pós-cancelamento não convida a remarcar de forma consistente.
4. A maior parte dos pedidos (105 de 129) chega com a conversa **na mão de uma
   pessoa**. Qualquer solução só no bot deixa esse volume de fora.

---

## 3. Escopo

### Dentro do escopo

**A. Cancelar pela conversa também na janela do lembrete.** Em resposta ao
lembrete, pedido explícito de cancelar ou "não vou" leva a `cancel_appointment`
na conversa, após uma confirmação curta ("Posso cancelar a sessão de 18/11 às
19h?"), e não ao link. O link continua sendo o caminho para **remarcar**
(trocar a data), que o site faz melhor que a conversa. `confirm_attendance`
e a troca de áreas por `alterar_agendamento` não mudam.

**B. Mensagem pós-cancelamento fixa.** Depois de `cancel_appointment` com
sucesso, o agente envia o texto da clínica, com o link do site quando houver:

> Obrigada por nos avisar! Seu horário foi cancelado com sucesso. ☺️
>
> Caso queira remarcar, você pode acessar nosso link de agendamento e
> escolher uma nova data e horário conforme sua disponibilidade. É bem
> rapidinho e você consegue fazer tudo por lá! ✨
> {link}

O texto vai em `message_templates` (chave `CANCELADO_PELA_CONVERSA`), por
clínica, como os demais; o código manda o default acima. Sem domínio, o
parágrafo do link sai e o bot oferece remarcar na conversa.

**C. Pedido de saída com a conversa na mão de uma pessoa.** O bot não fala
nem cancela por cima de um atendimento humano. Em vez disso, o webhook
detecta o pedido por lista de termos (mesmo mecanismo do `nivel_de_risco`),
quando há agendamento `CONFIRMED` nos próximos 30 dias, e:
- abre uma **tarefa** na conversa ("Pediu para cancelar ou remarcar a sessão
  de DD/MM") visível na fila do painel, com atalho para cancelar ou editar;
- marca o lead como `AGUARDANDO_NOS` no CRM (PRD 057) com esse motivo, pela
  mesma regra de "entrega pendente" do PRD 058.

Nada é gravado na agenda sem uma pessoa decidir. O que muda é que o pedido
não some na thread: fica como pendência até alguém cancelar, editar ou fechar
a tarefa.

**D. Lembrete.** A paciente que cancela pelo site ou pela conversa deixa de
receber o lembrete (já é assim) e o bloco de lembrete da sessão morre junto.

### Fora do escopo

- Mudar o PRD 054: cancelar com menos de 24 h continua **falta**
  (`NO_SHOW`), com o horário liberado igual. Decisão do André em 23/11.
- Cancelar automaticamente quando a conversa está com uma pessoa (C é
  sinalização, não ação).
- Detectar "não vou" sem agendamento ativo, ou pedidos ambíguos de troca de
  horário dentro do mesmo dia: continuam com o modelo e com a recepção.
- Remarcar pela conversa durante o lembrete: segue pelo link (PRD 027).

---

## 4. Modelo de dados

- `message_templates`: chave nova `CANCELADO_PELA_CONVERSA` (default no código).
- Sessão (`atendimento`): a tarefa de C usa `vincula_tarefa` já existente, com
  `handoff_reason = pedido_de_saida` (novo valor em `MOTIVOS_LEGIVEIS`:
  "Pediu para cancelar ou remarcar").
- Sem migração em `appointments`.

---

## 5. Regras

### 5.1 Com o bot respondendo

1. Pedido explícito de cancelar, desmarcar ou "não vou poder ir" + sessão
   marcada → o bot confirma em uma linha (data e hora) e, no "sim", chama
   `cancel_appointment`. Uma só confirmação, nunca duas.
2. Pedido de remarcar (outra data) → link do site se houver domínio; sem
   domínio, `alterar_agendamento` como hoje.
3. Na janela do lembrete valem as mesmas regras 1 e 2. `ferramentas_a_remover`
   deixa de remover `cancel_appointment`; o bloco de prompt do lembrete passa a
   dizer: "se quiser CANCELAR, confirme e cancele por aqui; se quiser
   REMARCAR, envie o link".
4. Depois de `cancel_appointment` com sucesso, a resposta é o template de §3.B
   (o agente recebe o texto no tool_result e é instruído a enviá-lo tal qual,
   sem repetir o valor nem perguntar mais nada).

### 5.2 Com a conversa entregue a uma pessoa

1. INBOUND que casa a lista de termos de saída e tem agendamento `CONFIRMED`
   nos próximos 30 dias para alguma variante do telefone → tarefa aberta com o
   motivo `pedido_de_saida` e o `appointment_id`.
2. Tarefa idempotente: um pedido por agendamento; novo INBOUND não duplica.
3. Cancelar, editar ou marcar falta nesse agendamento pelo painel ou pelo
   site fecha a tarefa. "Fechar tarefa" manual também.
4. O CRM lê a tarefa como entrega pendente (PRD 058): `AGUARDANDO_NOS` com
   motivo "pediu para cancelar em DD/MM e ninguém registrou".

### 5.3 Lista de termos

`cancelar`, `desmarcar`, `não vou conseguir ir`, `não vou poder`, `não
consigo ir`, `não irei`, `não vai dar`, `remarcar`, `reagendar`, `adiar`,
`transferir`, `outro dia`, `outra data`. Mesma régua para 5.1 (pré-carga do
roteador) e 5.2, num módulo só (`pedido_de_saida.py`), com testes por frase
real da medição (anonimizadas).

---

## 6. Áreas / arquivos impactados

| Arquivo | Ação |
|---|---|
| `scheduler/src/services/pedido_de_saida.py` | criar: lista de termos, `detecta(texto)`, `agendamento_alvo(db, clinic, phone)` |
| `scheduler/src/services/lembrete.py` | `FERRAMENTAS_DE_SAIDA` vazia; bloco de prompt novo |
| `scheduler/src/services/ai_tools.py` | `_tool_cancel_appointment` devolve `mensagem` (template renderizado com link) |
| `scheduler/src/services/conversation_agent.py` | após cancelar, resposta é a `mensagem` da tool |
| `scheduler/src/services/template_service.py` | default `CANCELADO_PELA_CONVERSA` |
| `scheduler/src/services/bot_policy.py` | `MOTIVO_PEDIDO_DE_SAIDA` + legível |
| `scheduler/src/functions/webhook/...` | ramo humano: detectar e abrir tarefa |
| `scheduler/src/services/appointment_service.py` | ao encerrar/remarcar, fechar tarefa `pedido_de_saida` do agendamento |
| `scheduler/src/services/estagio_do_lead.py` | motivo novo da entrega pendente |
| `frontend` (fila do painel) | rótulo e atalho para cancelar/editar a partir da tarefa |
| Testes unitários e roteiro `tests/integration/059-...md` | criar |

---

## 7. Testes

Dev, com conversas fictícias na Essência de dev, reproduzindo a medição:

| # | Caso de prod | Esperado |
|---|---|---|
| 1 | Resposta ao lembrete "vou precisar cancelar hoje" | bot confirma, cancela (`NO_SHOW` por < 24 h), envia o template com link; lembrete morto |
| 2 | Resposta ao lembrete "gostaria de remarcar" | link do site, nada cancelado |
| 3 | Resposta ao lembrete "ok confirmado" | `confirm_attendance`, como hoje |
| 4 | Fora do lembrete, bot ativo, "pode cancelar por favor?" com sessão em 5 dias | confirma, `CANCELLED`, template |
| 5 | Conversa com atendente, "não vou conseguir ir hoje" | sem mensagem do bot; tarefa `pedido_de_saida` na fila; CRM `AGUARDANDO_NOS` |
| 6 | Caso 5 e a recepção cancela no painel | tarefa fechada; CRM volta à regra normal |
| 7 | Caso 5 e a paciente cancela pelo site | tarefa fechada |
| 8 | "não consigo nesses horários" sem agendamento ativo | nada acontece |
| 9 | Clínica sem domínio | template sem o parágrafo do link |

---

## 8. Critérios de aceite

- [ ] Em resposta ao lembrete, pedido de cancelar termina com o agendamento
  fora da agenda na mesma conversa, sem depender do link.
- [ ] Toda resposta a `cancel_appointment` é o template da clínica, com link
  quando há domínio.
- [ ] Pedido de saída em conversa humana aparece na fila do painel e no CRM
  até alguém agir; cancelar, editar ou falta fecham sozinhos.
- [ ] Medição repetida 30 dias depois do deploy: zero agendamentos
  `CONFIRMED` com data passada e pedido de saída na conversa sem tarefa
  fechada.

---

## 9. Referências

- PRD 027 (lembrete e sobreposição), PRD 046 (site como primeiro caminho),
  PRD 054 (desfechos), PRD 057/058 (CRM e entrega pendente), PRD 020 §4.3
  (nível 3 por termos).
- Pedido da clínica (Essência), texto da mensagem em §3.B.

---

## Status

- [x] PRD: 23/11/2026 (medição em prod só leitura)
- [ ] Decisões em aberto para o André: (a) confirmar em uma linha antes de
  cancelar, ou cancelar direto quando o pedido for inequívoco; (b) a parte C
  (tarefa em conversa humana) entra junto ou em PR separado.
- [ ] Spec
- [ ] Implementado em dev
- [ ] Implementado em prod
