# PRD - 039 Silenciar o bot para um contato, sem prazo

> Gerado na fase **Research** em 08/11/2026. Use como input para a fase Spec.
> Reabre, de propósito e em parte, a **decisão 9.1 do PRD 020** (ver §3).

---

## 1. Objetivo

Dar à clínica um jeito de calar o bot para **um contato específico, por tempo
indeterminado**, com um gesto explícito de uma pessoa, e desfazer com outro
gesto explícito. Hoje toda pausa vence em 24 horas e o bot volta sozinho.

O gatilho é um caso real de 08/11/2026: na Essência, a conversa com um lead
estava sendo conduzida à mão por uma atendente havia dois dias. O bot estava
ativo para aquele número (cooldown vencido, política `LEADS_ONLY` cobrindo o
contato porque ele tem registro de lead) e responderia por cima dela assim que
a pessoa escrevesse. A pausa de 24 horas foi aplicada como paliativo, e vence
no dia seguinte.

---

## 2. O que existe hoje, e por que nada serve

`atendimento.pode_responder` tem três portas. Nenhuma cala um contato sem
prazo:

| Porta | O que é | Por que não serve |
|---|---|---|
| `clinic.bot_paused` | desliga o bot da clínica inteira | indefinido, mas atinge todos os contatos |
| `esta_com_pessoa(session)` | entrega a um humano | vence em 24 h (TTL), inclusive `CONTATO_MANUAL` e `CHAT_ANTERIOR` |
| política (`ALL`/`PILOT`/`LEADS_ONLY`/`OFF`) | quem o bot atende | é regra da clínica, não de um contato |

Três contornos foram testados em 08/11/2026 e **os três falham**:

1. **Renovar a pausa de 24 h.** Funciona enquanto alguém lembrar de renovar.
   Qualquer resposta da clínica no WhatsApp renova sozinha
   (`renova_por_mensagem_da_clinica`), mas um fim de semana sem mensagem
   devolve a conversa ao bot.
2. **Marcar a conversa como não elegível** (`bot_enabled = False`, só vale sob
   `LEADS_ONLY`). É desfeito na mensagem seguinte: o webhook, ao ver a conversa
   inelegível, procura o lead pelo telefone, acha, e remarca
   `bot_enabled = True` (`webhook/handler.py`, bloco de elegibilidade).
3. **Marcar o lead como "Já iniciada por uma pessoa"** (`first_contact_channel
   = HUMANO`). Não tem efeito numa conversa já elegível: o trecho que entrega a
   conversa por `CONTATO_MANUAL` só roda dentro do `if not
   session.get("bot_enabled")`, que não é verdade aqui.

---

## 3. Isto reabre a decisão 9.1 do PRD 020, e precisa reabrir

Em 05/10/2026 ficou decidido que **nenhuma pausa é permanente**: `CONTATO_MANUAL`
e `CHAT_ANTERIOR` passaram a vencer pelo TTL de inatividade. O argumento era
forte e continua de pé: eram **2912 conversas anteriores a nós** que ficariam
caladas para sempre por um critério implícito (quem começou a conversa), e o
cooldown já garante que o bot não inicia, só responde a quem escreve.

**O que muda aqui é a natureza do gesto, não o princípio.** A 9.1 proibiu
pausa permanente **derivada**, aplicada em bloco a milhares de conversas como
efeito colateral de um fato histórico. Este PRD propõe pausa permanente
**declarada**: uma pessoa escolhe um número, por um motivo, e assume. São
coisas diferentes, e a segunda não ressuscita o problema das 2912.

O risco 5.1 do PRD 019 ("pausa sem prazo cala o bot para sempre") deixa de ser
acidente e passa a ser a intenção. Mas ele **não desaparece**: continua valendo
para o contato que foi silenciado e esquecido. É por isso que a visibilidade
(§5) é parte da entrega, não enfeite. O PRD 020 §9.4 já registra o mesmo tipo
de risco: "`HUMAN_PENDING` sem alguém olhando é conversa esquecida com cara de
resolvida".

---

## 4. As duas perguntas que governam o desenho

### 4.1 O que reativa o bot depois?

**Proposta: nada automático. Só um gesto humano explícito.** Um contato
silenciado continua silenciado até alguém clicar "Reativar bot" naquela
conversa. Não reativam: a pessoa escrever, a clínica responder, o tempo passar,
campanha, lembrete de sessão, "Retomar bot" genérico.

Isso exige decidir a precedência contra os três caminhos que hoje abrem a
conversa sob `LEADS_ONLY` (`_politica_permite`):

| Caminho | Hoje | Proposta |
|---|---|---|
| `bot_enabled` (lead escreveu) | abre | **silêncio vence** |
| `campanha_viva` | abre | **silêncio vence** |
| `lembrete_vivo` (PRD 027) | abre | **silêncio vence** |

O lembrete de sessão **continua sendo enviado** (é mensagem transacional da
clínica para a pessoa, não resposta do bot). O que muda é que, se ela responder
"preciso remarcar", o bot não responde: a conversa vai para a fila humana. Essa
é a consequência mais incômoda da proposta e precisa de decisão consciente,
porque ela transforma um lembrete útil numa conversa que alguém tem de atender
à mão.

> **Decidido (André, 08/11/2026):** o silêncio vence, **inclusive o lembrete
> de sessão**. Silenciar é dizer "o bot não fala com esta pessoa", sem exceção.
> O lembrete continua SAINDO (é a clínica falando, não o bot), e a resposta
> dela cai na fila humana.

### 4.2 Quem enxerga que aquele número está mudo?

Sem resposta para isso, o recurso vira dívida: número calado por engano, meses
depois, sem ninguém saber por quê.

> **Decidido (André, 08/11/2026):** marcar no painel, e também **no cadastro do
> paciente**. A marca aparece SÓ quando o contato está silenciado - quem não
> está não ganha selo nenhum, para a lista de pacientes não virar um mar de
> rótulos.

Entregar junto:

- **Motivo de pausa novo** no vocabulário do painel (PRD 031): `muted`, ao lado
  de `attendant`, `clinic_paused` e `not_eligible`. Fonte única em
  `atendimento.motivo_da_pausa` e `frontend/src/lib/motivoDaPausa.ts`.
- **Selo na lista de conversas** e **filtro "Silenciadas"**, como os três
  motivos já têm.
- **No cabeçalho da conversa**: quem silenciou, quando e o motivo escrito.
- **Precedência de exibição**: `muted` aparece antes de `attendant`, porque é o
  estado mais forte e o que a recepção precisa enxergar para agir.
- **No cadastro do paciente** (lista e card de `pacientes`): selo "Bot
  silenciado" quando, e apenas quando, aquele telefone está silenciado. Serve
  a quem abre o cadastro sem passar pela tela do bot.

---

## 5. Escopo

### Dentro

- Silenciar e reativar um contato, por clínica, com autor, data e motivo em
  texto livre (curto, obrigatório: silenciar sem motivo é o que produz o número
  esquecido).
- `pode_responder` e `pode_iniciar` passam a considerar o silêncio, antes de
  qualquer outra porta.
- Motivo `muted` no painel: selo, filtro, cabeçalho, e botão "Reativar bot".
- Registro de auditoria: quem silenciou, quem reativou, quando.
- Permissão: a mesma de quem hoje pausa e retoma o bot no painel.

### Fora

- Silenciar a clínica inteira: já existe (`clinic.bot_paused`).
- Pausa com prazo: já existe (24 h, renovável).
- Bloquear mensagens transacionais (lembrete de sessão, link de pagamento,
  check-in). Silenciar é sobre **o bot responder**, não sobre a clínica falar.
- Silenciar por conteúdo ou automaticamente (ex.: "pediu para parar de receber
  mensagens"). Vale um PRD próprio, com LGPD junto.

---

## 6. Onde o silêncio mora (proposta)

**Tabela nova no Postgres**, `scheduler.contatos_silenciados`: `clinic_id`,
`phone` (normalizado), `motivo`, `silenciado_por`, `silenciado_em`,
`reativado_por`, `reativado_em`. Único por `(clinic_id, phone)` enquanto ativo.

Três razões para não morar na sessão do DynamoDB:

1. **Retenção.** O PRD 020 §9.3 registra que `conversation-sessions` está sem
   TTL e que isso precisa de fatia própria. Se alguém ligar TTL depois, o
   silêncio sumiria com o item, e o bot voltaria a falar sem ninguém ter pedido.
2. **A lista precisa ser consultável.** "Quais números estão mudos nesta
   clínica?" é a pergunta que mantém o recurso honesto, e no DynamoDB ela exige
   varredura da tabela.
3. **Auditoria.** Quem, quando e por quê é registro, e registro mora em tabela.

**Como chega a `pode_responder` sem pesar no caminho de toda mensagem:** a
função não ganha acesso ao banco. Quem já lê o Postgres antes de decidir (o
webhook, o processador da fila, o lembrete) consulta o silêncio e **passa como
argumento explícito** (`pode_responder(..., silenciado=True)`).

Na redação de 08/11 esta seção propunha injetar o valor no dict da sessão
(`session["silenciado_em"]`), "como já faz com `bot_enabled`". **Isso está
errado e foi corrigido:** `bot_enabled` mora de verdade na sessão, o silêncio
não. E `session_store.grava_atendimento`, quando a sessão ainda não existe,
grava o dict inteiro (`put_item(Item=session)`) - o campo injetado viraria uma
cópia persistida de um dado cuja fonte é o Postgres, livre para divergir em
silêncio. Argumento explícito não persiste nada.

---

## 7. Critérios de aceite

- [ ] Contato silenciado: o bot não responde quando a pessoa escreve, e não
      inicia por campanha nem por lembrete.
- [ ] O silêncio sobrevive a: a pessoa escrever, a clínica responder, 24 h,
      uma semana, e ao "Retomar bot" genérico.
- [ ] O lembrete de sessão continua saindo para o número silenciado (decisão
      §4.1), e a resposta dela cai na fila humana.
- [ ] A conversa aparece no painel com selo próprio, filtro, e com quem, quando
      e por que foi silenciada.
- [ ] "Reativar bot" devolve a conversa ao bot, e o evento fica registrado.
- [ ] Silenciar exige motivo.
- [ ] Nenhum caminho remarca o contato como elegível por trás (os três de §2).
- [ ] O cadastro do paciente mostra o selo "Bot silenciado" quando, e só
      quando, aquele telefone está silenciado.
- [ ] `pytest`, `npm run build`, `npm run lint` e `npm run test` verdes.

---

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Número silenciado e esquecido (risco 5.1 do PRD 019, agora intencional) | Filtro e selo no painel; motivo obrigatório; relatório ou aviso de contatos silenciados há muito tempo pode entrar na fase 2 |
| Silenciar por engano e a paciente ficar sem resposta | O gesto é explícito e reversível em um clique; o selo mostra o estado em toda lista |
| Lembrete de sessão cair em conversa muda | Decisão §4.1; a resposta vai para a fila humana, que é onde a recepção já olha |
| Silêncio divergir entre Postgres e sessão | A fonte é o Postgres; a sessão só carrega a cópia da leitura daquela mensagem, nunca grava |

---

## 9. Referências

- `docs/work/prd/020-arquitetura-de-atendimento-unico.md` §9.1 (decisão de
  05/10/2026), §9.2 (`bot_enabled` permanente), §9.3 (tabelas sem TTL), §9.4.
- `docs/work/prd/019-pausa-explicita-do-bot.md` (risco 5.1).
- `docs/work/prd/031-quem-o-bot-responde.md` (vocabulário de motivo da pausa).
- `scheduler/src/services/atendimento.py` (`pode_responder`, `motivo_da_pausa`,
  `_politica_permite`), `scheduler/src/functions/webhook/handler.py` (bloco de
  elegibilidade), `frontend/src/lib/motivoDaPausa.ts`.

---

## Status

- [x] Aprovado: §4.1 e §4.2 decididos em 08/11/2026
- [ ] Spec gerada: `spec/039-silenciar-contato.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
