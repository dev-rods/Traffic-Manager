# PRD - 046 Para quem já é paciente, o link é o primeiro caminho

> Gerado na fase **Research** em 10/11/2026. Use como input para a fase Spec.
> Pedido do André: "o bot deve seguir o fluxo de agendamento pelo link para
> pacientes já cadastrados; principalmente quando a pergunta vier pelo disparo
> do link e quando a própria cliente perguntar sobre o link ele deve reforçar e
> encaminhar". Decisão dele em 10/11/2026: **o link vira o caminho padrão de
> primeira tentativa**.
>
> Nomes e telefones ficam fora deste documento; o rastro está no
> `message-events` e nos logs, e a conversa está identificada por clínica,
> data e hora.

---

## 1. Objetivo

Em clínica com site de autoatendimento, quem **já é paciente** e quer marcar
recebe primeiro o link do site - sempre, e com reforço quando ela própria
perguntar do link ou quando o disparo que a trouxe já o tinha mandado. O bot só
agenda na conversa como **segunda tentativa**: quando ela disser que não
consegue, não quer, ou pedir para resolver por aqui.

---

## 2. O caso

Essência, paciente cadastrada (sessões em setembro e outubro), parceira da
clínica.

| Quando (UTC) | Quem | O quê |
|---|---|---|
| 05/11 19:28 | recepção, pelo painel | disparo **com campanha** (REAGENDAMENTO, datas 18, 19, 25, 26/11 e 08/12, viva até 16/11). Texto: "confirmar as áreas, escolher um horário e **finalizar pelo link**: https://agendar…/agendar" |
| 09/11 21:06 | ela | "Para influencer também é por esse link?" |
| 09/11 21:08 | bot | **"Pode ser por aqui mesmo, sem problema! Me conta: quais áreas você quer tratar?"** |
| 09/11 21:19-21:23 | recepção | "O link é também pode ser usado! Ele é para todos agendamentos" + o link + "pelo link você consegue visualizar os horários… nenhum valor será cobrado, você já está cadastrada como parceira" |

A clínica escolheu o link; o bot puxou para a conversa; a recepção corrigiu em
três mensagens.

---

## 3. Por que acontece

### 3.1 O modo da campanha e o texto do disparo dizem coisas opostas

A campanha grava `modo: REAGENDAMENTO` na sessão e o agente troca o roteiro de
lead pelo da campanha (`prompt_da_campanha.FLUXO_DA_CAMPANHA`): áreas → datas
da campanha → "Confirmo?" → **`book_appointment`**. É um roteiro de agendar
na conversa. O texto que a atendente escreveu mandava finalizar pelo link. O
bot seguiu o roteiro que tinha - a resposta "pode ser por aqui mesmo" é
exatamente o passo 1 dele.

O painel não tem como dizer "esta campanha é pelo link": `CampanhaDoBot` só
liga o bot e escolhe as datas (`campanha: { datas }`).

### 3.2 Fora da campanha, o bot não sabe que o link existe

- O `AI_SYSTEM_PROMPT` das duas clínicas **não cita "link" nenhuma vez**.
- O link (`autoatendimento.link_de_autoatendimento(clinic)`, derivado de
  `custom_domain`) só chega ao modelo durante o lembrete de 24 h
  (`lembrete.bloco_de_prompt`), e só para remarcar/cancelar.
- Não há variável de prompt para ele - endereço e telefone entram como
  `{{clinic_address}}` e `{{clinic_phone}}`; o link não entra de nenhuma forma.

Essência (`agendar.draclaradourado.com.br`) e Nobre (`agendar.nobrelaser.com.br`)
têm domínio. As clínicas de dev não têm.

### 3.3 O que a skill de paciente diz hoje

`PACIENTE_COM_HORARIO` e `PACIENTE_SEM_HORARIO` (`skills/__init__.py`) conduzem
para áreas → agenda na conversa. Para `NO_NEXT_BOOKING`: "comece pelas áreas
DESTA sessão". Nada sobre site.

---

## 4. Proposta

Uma regra, "para quem já é paciente, o site é a primeira tentativa", aplicada
nos três lugares em que o bot decide o caminho - e, como nos PRDs 044 e 045,
com o código garantindo o que o prompt pede.

### 4.1 O link entra no contexto do bot

- Variável `{{link_de_agendamento}}` no render do prompt
  (`conversation_agent._build_system_prompt`), vazia quando a clínica não tem
  domínio. Mesmo mecanismo de `{{clinic_address}}`.
- Fica também no `ctx` das tools, para o código decidir (4.3).

### 4.2 As skills de paciente, em clínica com domínio

Bloco de conduta de `PACIENTE_COM_HORARIO` e `PACIENTE_SEM_HORARIO` ganha,
**só quando há link** (o bloco é montado em código, pode ser condicional):

```
PRIMEIRA TENTATIVA É O SITE
Quem já é paciente agenda pelo site: {{link_de_agendamento}}. Lá ela vê os
horários, escolhe e confirma com o mesmo WhatsApp.
1. Pedido de agendar, pergunta sobre o link ou sobre "onde marco": mande o
   link em uma frase e se coloque à disposição para dúvidas. Não pergunte as
   áreas, não ofereça datas.
2. Se ela disser que não consegue, que o link não abre, ou que prefere
   resolver por aqui - aí sim conduza o agendamento na conversa, como sempre.
3. Dúvidas (preço, preparo, endereço) continuam respondidas aqui, normalmente.
```

Lead nova (`PRIMEIRO_AGENDAMENTO`) **não muda**: o site pede cadastro e o bot
já faz isso melhor na conversa (PRD 032/033) - fora do escopo desta decisão.

### 4.3 Código: a primeira chamada de `book_appointment` sem o link ter ido é recusada

Em clínica com domínio, para paciente cadastrada, `book_appointment` (e
`check_availability`, que é onde o roteiro de agendar começa) só seguem se o
link **já foi enviado nesta conversa** - o agente sabe o que mandou
(`message-events` / `respaldo`). Senão a tool responde:

```
{"error": "primeiro_o_link",
 "link": "https://agendar.…/",
 "o_que_fazer": "Esta pessoa já é paciente e esta clínica agenda pelo site.
   Mande o link em uma frase e pergunte se ela consegue por lá. Só se ela
   disser que não, chame de novo."}
```

É o padrão de `full_name_obrigatorio` e `ja_tem_sessao_marcada`: a tool
explica, o modelo refaz. A "segunda tentativa" fica registrada no rastro: a
tool só passa depois de o link ter saído.

### 4.4 Campanha: o roteiro acompanha a decisão

Como o padrão para paciente passa a ser o link, a campanha de reagendamento em
clínica com domínio passa a ter o roteiro:

```
1. Mande o link (se o disparo já o mandou, reforce em uma frase) e as datas
   da campanha. Não pergunte as áreas.
2. Se ela disser que não consegue pelo site, conduza aqui: áreas → datas da
   campanha → "Confirmo?" → book_appointment.
```

Em clínica **sem** domínio, o roteiro atual continua. O painel não precisa de
toggle novo: a clínica com site tem um comportamento, a sem site tem outro.
(Decisão §7.1 se o André preferir um toggle.)

### 4.5 Medir

```
[Link] <phone>: link enviado (skill|campanha)
[Link] <phone>: book_appointment recusado, link ainda não foi
[Link] <phone>: segunda tentativa - agendando na conversa
```

A razão "segunda tentativa / link enviado" por clínica diz se o site está
dando conta ou se as pessoas voltam para a conversa.

---

## 5. Achados fora do escopo

- **O texto do disparo é livre e pode contradizer o modo** (foi o caso). Com
  4.4 o roteiro passa a combinar com o texto que a recepção escreve hoje; se
  um dia o texto voltar a mandar agendar "por aqui" numa clínica com site,
  volta a divergir. Um template de disparo por clínica resolveria - não entra
  aqui.
- `appointments` não registra **por onde** o agendamento foi feito (site,
  bot, painel). A medição de 4.5 cobre o bot; a visão completa pede uma
  coluna de origem.

---

## 6. Escopo

### Dentro

- `{{link_de_agendamento}}` no render e no `ctx`.
- Bloco "PRIMEIRA TENTATIVA É O SITE" nas duas skills de paciente, condicional
  ao domínio.
- Recusa `primeiro_o_link` em `book_appointment` e `check_availability` para
  paciente cadastrada em clínica com domínio, até o link ter saído na conversa.
- Roteiro de campanha condicional ao domínio.
- Logs `[Link]`.
- Testes: skill com e sem domínio; a recusa e a liberação depois do link; lead
  nova intocada; campanha com e sem domínio; o caso real dublado ("para
  influencer também é por esse link?" → o link, não "quais áreas").

### Fora

- Lead nova (segue agendando na conversa).
- Template de texto do disparo por clínica.
- Coluna de origem em `appointments`.
- Alterar/cancelar (PRD 045 e lembrete já têm regra própria).

---

## 7. Decisões para o André

### 7.1 O painel precisa escolher, ou o domínio decide?

- **A (recomendada).** O domínio decide: clínica com site, campanha pelo
  link; sem site, campanha agenda na conversa. Nada novo no painel.
- **B.** Toggle "bot agenda na conversa" na campanha, para a recepção
  escolher caso a caso. Mais um botão para explicar; útil só se houver
  campanha em que a clínica NÃO queira o site.

### 7.2 O que conta como "segunda tentativa"

- **A (recomendada).** O link ter saído nesta conversa (rastro de mensagens),
  sem janela de tempo: mandou o link, a próxima mensagem dela já pode ser
  "não consigo" e o bot agenda.
- **B.** Além do link ter saído, exigir que ela diga explicitamente que não
  consegue/não quer. Mais fiel à decisão, mas depende de o modelo classificar
  a frase - e "quais áreas vocês fazem?" depois do link viraria impasse.

### 7.3 Paciente que já tem sessão futura e quer marcar OUTRA

- **A (recomendada).** Mesma regra: link primeiro. O PRD 045 continua valendo
  para alterar a que existe.
- **B.** Segunda sessão na conversa direto, já que ela está falando com o bot.

---

## 8. Status

- [x] Decisões §7 registradas em 10/11/2026: **§7.1 A** (o domínio decide o roteiro da campanha), **§7.2 A** (segunda tentativa = o link já saiu nesta conversa), **§7.3 A** (segunda sessão também começa pelo link)
- [x] Spec gerada em 10/11/2026 (`spec/046-link-e-o-primeiro-caminho.md`)
- [x] Implementado em dev em 10/11/2026 (PR #191, layer 194; E2E: link primeiro, segunda tentativa, lead nova intocada)
- [x] Em prod em 10/11/2026 (layer 152; sem script de prompt - o link entra por código)
- [x] Registrado no TASKS_LOG
