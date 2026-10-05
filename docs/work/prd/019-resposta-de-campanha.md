# PRD — 019 Resposta de campanha vai para uma pessoa

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Quando a clínica dispara uma campanha e a paciente **responde**, essa resposta vai
para a fila de atendimento humano - não para o bot.

O motivo é simples e não depende de interpretar nada: a campanha prometeu uma
pessoa. "Responda esta mensagem e enviamos nosso catálogo completo em PDF" é um
compromisso que o bot não tem como cumprir, e tentar cumprir é o que produziu o
incidente de 30/09/2026.

---

## 2. Contexto

### 2.1 O que aconteceu, medido

Em **30/09/2026 20:42** a Essência disparou:

> Você sabia que, além da depilação a laser, também temos outros procedimentos
> aqui na Clínica Essência? 💉 **Toxina botulínica (Botox)** 💋 **Preenchimentos**
> ✨ **Bioestimuladores de colágeno** 🧖 **Tratamentos faciais**
> [...] **Responda esta mensagem e enviamos nosso catálogo completo em PDF.**

| | |
|---|---|
| receberam | **320** |
| responderam | **30** |
| receberam resposta negando o produto | **2** |

As duas conversas, transcritas de produção:

**Marie Gabriella** (01/10 02:28)

> **Paciente:** Qual está sendo o valor do botox para a região da testa e olhos?
> **Bot:** Aqui na Essência trabalhamos só com depilação a laser, **não oferecemos
> botox** 😊
> **Paciente:** Vocês que mandaram essa mensagem. Não entendi…
> **Bot:** Verifiquei aqui e não encontrei nenhum agendamento ativo no seu nome.
> **Pode ter sido algum engano.**

**Yasmin** (30/09 22:46)

> **Paciente:** Conhecer procedimentos e valores / Gostaria de conhecer
> **Bot:** A Essência Estética trabalha **só** com Depilação a Laser [+ tabela
> inteira de preços de laser]

Nos dois casos alguém da clínica pediu desculpa à mão na manhã seguinte.

### 2.2 A frase que o bot disse não existe em lugar nenhum

Conferido em produção: "trabalhamos só com depilação a laser" **não está no
código** e **não está em nenhum dos 19 itens de FAQ** da clínica - todos de
laser. O modelo sintetizou a exclusividade a partir de um contexto inteiramente
de laser, tendo a campanha da própria clínica no histórico da conversa.

Isso é o padrão de sempre: a resposta ruim do modelo se explica pelo contexto que
ele recebeu, não por falta de instrução.

### 2.3 Por que o PRD 018 não fecha isso

O 018 é a guarda determinística por procedimento nomeado. Testado contra as
mensagens reais:

```
MARIE  "...valor do botox para a testa e olhos?"   -> toxina_botulinica   DISPARA
YASMIN "Conhecer procedimentos e valores"          -> None               NÃO DISPARA
```

**Marie o 018 resolve.** Yasmin não: nenhuma mensagem dela nomeia procedimento. O
que ela quer está na mensagem **da clínica**, e `fora_do_escopo.detecta()` só olha
o texto recebido.

Sobra a instrução de prompt - que é justamente a rede que o 018 trata como fraca,
e com razão: instrução o modelo contorna.

### 2.4 Por que não resolver ampliando o detector

Fazer o detector olhar o histórico significaria casar a mensagem da paciente
contra o que a clínica disse antes. Isso transforma uma lista de 14 termos numa
heurística de correferência - "Sim" quer dizer o quê, depende de quando - e é
exatamente a classe de inferência que o 018 recusou fazer, por bons motivos.

O disparo de campanha, em contraste, é um **fato registrado**: existe mensagem
enviada, com carimbo, pelo caminho de campanha. Não há o que inferir.

---

## 3. Escopo

### Dentro do escopo

- Identificar que a última mensagem enviada na conversa foi um disparo de
  campanha (não lembrete, não resposta do bot, não mensagem de atendente).
- A próxima mensagem recebida nessa conversa, dentro de uma janela, entrega a
  conversa a uma pessoa com motivo próprio - antes do bot interpretar.
- Motivo novo no vocabulário fechado de `bot_policy` (ex.
  `resposta_de_campanha`), com rótulo legível na fila do painel.
- A paciente recebe uma confirmação honesta: alguém vai responder. Sem prometer
  prazo, como o `fora_do_escopo.TEXTO` já faz.

### Fora do escopo

- **Enviar o catálogo em PDF automaticamente.** O disparo prometeu uma pessoa, e
  automatizar o envio é outra decisão - inclusive comercial.
- **Fazer o bot responder sobre outros procedimentos.** Continua proibido pelo
  018. Esta fatia só garante que a pergunta chegue a quem pode responder.
- **Ampliar o detector do 018 para olhar histórico.** Ver 2.4.
- **A campanha em si** (quem recebe, texto, cadência). Não se mexe.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/bot_policy.py` | modificar | motivo novo + rótulo, no vocabulário fechado |
| `scheduler/src/functions/webhook/handler.py` | modificar | a guarda roda junto da do 018: depois da agregação de mensagens, antes do agente |
| `scheduler/src/services/conversation_engine.py` | modificar | mesmo ponto no caminho legado - aplicar só num dos dois é como a divergência começa |
| `frontend/src/pages/bot/components/FilaDeAtendimento.tsx` | verificar | deve exibir o motivo novo sem mudança, por ser rótulo vindo do backend |
| `scheduler/tests/unit/` | criar | as duas conversas reais como caso de teste |

### 4.1 A pergunta de modelagem a resolver na Spec

**Como a conversa sabe que recebeu um disparo?** Três caminhos, e a Spec precisa
escolher com os dados na mão:

1. **Marcar na sessão no momento do disparo.** Direto, mas a sessão tem TTL de
   30 minutos e as respostas chegaram **2h e 6h depois** - a sessão já não existia.
   Isso provavelmente elimina a opção.
2. **Consultar `MessageEvents`** pela última `OUTBOUND` da conversa e checar se é
   campanha. O dado existe e tem TTL de 90 dias; custa uma consulta por mensagem
   recebida.
3. **Marcar em tabela própria no disparo** (`campaign_sends`), com janela
   explícita. Mais escrita, leitura trivial, e dá para medir a campanha depois.

A janela também é decisão: as duas respostas vieram em **2h** e **6h**. Uma
janela de 24-48h cobre com folga; curta demais recria o problema.

---

## 5. Dependências e riscos

**Dependências**

- PRD 018 mergeado (PR #88). ✅ - a fila e o vocabulário de motivos vêm dele.

**Riscos**

### 5.1 Pegar resposta que o bot deveria atender

Alguém recebe a campanha e responde "quero marcar laser na axila". Com esta regra
isso vai para a fila, e um agendamento que o bot fazia sozinho passa a custar
atendimento humano.

Mitigação possível: deixar o detector do 018 e a intenção de agendamento
decidirem primeiro - se a mensagem é claramente de laser, o bot segue. Mas isso
reintroduz inferência, e a Spec precisa pesar: 30 respostas por campanha é um
volume que a recepção absorve, e o custo do erro inverso (negar o produto) é alto.

### 5.2 Volume na fila

320 enviados, 30 respostas - ~10%. É pouco em absoluto, mas chega **concentrado**
nas horas seguintes ao disparo. A fila do 018 ordena por espera mais antiga, o que
ajuda, mas vale avisar a clínica antes de uma campanha grande.

### 5.3 A exposição se repete a cada campanha

Esta é a razão de prioridade, não um risco da solução: sem isso, **a próxima
campanha produz o mesmo estrago**. O trabalho manual de 01/10 - duas desculpas
escritas à mão - é o custo recorrente que esta fatia elimina.

---

## 6. Critérios de aceite

- [ ] Resposta a disparo de campanha entrega a conversa a uma pessoa **antes** de
      o modelo ver a mensagem
- [ ] Motivo próprio no vocabulário fechado, com rótulo na fila do painel
- [ ] As duas conversas reais (Marie e Yasmin) viram teste, com as mensagens
      exatas de produção
- [ ] A guarda vale nos **dois** caminhos (webhook novo e engine legado)
- [ ] A paciente recebe confirmação sem promessa de prazo
- [ ] Janela escolhida com justificativa escrita (as respostas medidas foram 2h e 6h)
- [ ] Decisão de 5.1 registrada: resposta claramente de laser segue no bot, ou não

---

## 7. Referências

- `docs/work/prd/018-so-depilacao-a-laser.md` — a guarda por procedimento nomeado
- PR #88 — fila de atendimento e vocabulário de motivos
- `scheduler/src/services/fora_do_escopo.py` — por que a guarda é determinística
- Conversas de produção: `5511994683015` (Marie), `5511984048030` (Yasmin),
  clínica `clinicaessenciaestetica-9668a4`, em `MessageEvents` (TTL 90d - extrair
  antes de **29/12/2026**)

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
