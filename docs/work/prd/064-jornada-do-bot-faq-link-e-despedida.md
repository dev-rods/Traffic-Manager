# PRD - 064 Jornada do bot: FAQ como fonte (não como bolha), link no momento certo, despedida uma vez

> Gerado na fase **Research**. Use como input para a fase Spec.
> Status: RASCUNHO para decisão de negócio. As pendências do §8 precisam de
> resposta do André antes da Spec.

---

## 1. Objetivo

Rever a jornada de compra conduzida pelo bot, com três defeitos observados
em conversas reais da Nobre (24/11/2026) como ponto de partida, e uma
revisão geral do fluxo para que o bot responda o que foi perguntado, no
momento em que foi perguntado, conduza até o agendamento sem devolver
tarefa para a cliente, e saiba calar quando a conversa acabou. Tudo
mantendo as guardas determinísticas que hoje impedem invenção de preço,
data e área.

---

## 2. Contexto: o que aconteceu, com evidência

Fonte: MessageEvents e `agent_history` das sessões em prod (só leitura;
os contatos A, B e C são os três números passados pelo André em 25/11, fora
deste documento de propósito),
logs `WhatsAppWebhook`, prompt `AI_SYSTEM_PROMPT` da Nobre no banco e o
código em `scheduler/src/services/`. Números de 30 dias (26/10 a 25/11),
Logs Insights sobre as Lambdas do bot em prod.

### 2.1 Caso 1 (Nobre, lead A): o FAQ da virilha "do nada"

Jornada: "Olá / Tudo bem? / Quanto é a depilação na virilha? Obrigada" às
18:00. O bot ficou calado 44 minutos (política `LEADS_ONLY` da Nobre:
quem escreve por conta própria espera alguém da clínica apertar "Retomar
bot"; logs `Resposta automática suprimida ... policy=LEADS_ONLY`). Às
18:44 a retomada rodou com `__RETOMAR_CONVERSA__`, o modelo chamou
`get_faq_answer(BIKINI_TYPES)` e saíram DUAS mensagens nesta ordem:

1. a bolha literal do FAQ (simples, cavada, completa, perianal, dica de
   raspar), ANTES de qualquer saudação;
2. "Oi, tudo ótimo! Aqui é da Nobre Laser SJC... Sobre a virilha, temos
   três opções (te mandei os detalhes de cada uma). Qual delas você
   prefere? E você gostaria de incluir também a região perianal?"

Ninguém perguntou a diferença entre as virilhas; a pergunta era de preço.
O bot não respondeu o preço nem explicou que ele depende do tipo.

Por que aconteceu (não é "o modelo errou"; é o desenho):

- O prompt do banco (etapa 3 ÁREAS, texto do PRD 037) manda literalmente:
  "Virilha (simples, cavada, completa): chame get_faq_answer sobre os
  tipos de virilha. O texto do FAQ já vai para a pessoa como mensagem
  própria; a sua fala é só a pergunta 'qual delas você prefere?'".
- A tool entrega o item inteiro como bolha própria, byte a byte, SEMPRE
  antes da fala do modelo (`conversation_agent.py:1716`), e descarta a
  fala do modelo se ela repetir metade do item (`policy_do_faq.py:120`).
  O modelo é instruído a "NÃO repetir, NÃO resumir, NÃO reformular".
- Resultado: o único jeito de o bot explicar os tipos é jogar o item
  inteiro, e sempre antes do "oi".

Frequência: em 30 dias saíram 185 bolhas de FAQ em prod; 108 chamadas
foram de `BIKINI_TYPES`. Mais da metade das bolhas literais é o texto da
virilha, disparado toda vez que a palavra aparece.

### 2.2 Caso 2 (Nobre, paciente B): coletou tudo e mandou o link

Jornada: campanha de 24/11 13:16 ("novas datas... link agendar.nobrelaser.
com.br"). Ela respondeu "Podemos marcar dia 3/12 às 15:30?". O bot
perguntou áreas, confirmou perianal, consultou horários (15:30 não cabia,
ofereceu 15:40), ela aceitou, ele resumiu, ela confirmou ("Isso"). Só
então `book_appointment` devolveu `primeiro_o_link` e o bot escreveu "Pra
agilizar, você consegue fazer esse agendamento direto no nosso site?".
Ela foi ao site e agendou 3 minutos depois (ficou), mas depois de cinco
mensagens de trabalho dela.

Por que aconteceu:

- PRD 046 (10/11): para quem já é paciente em clínica com domínio, o site
  é a primeira tentativa. A regra existe em dois lugares que não
  conversam: um bloco de prompt (`skills.bloco_do_site`, só para as skills
  de paciente) e uma trava na tool (`ai_tools._recusa_sem_o_link`, que
  olha `paciente.encontrado`).
- Esta pessoa tinha cadastro, mas nenhuma sessão feita e nenhuma futura:
  estado comercial `NEW_LEAD`, skill `PRIMEIRO_AGENDAMENTO`, SEM o bloco
  do site. O modelo conduziu como lead nova, como o prompt mandava, e a
  trava apareceu só na última tool. O texto do disparo trazia o link, mas
  "link mandado pelo disparo não conta, de propósito" (`autoatendimento.py`,
  decisão de 10/11).
- Mesmo com o bloco presente (paciente com sessão feita), a trava ainda
  seria a última linha de defesa, e o modelo pode chegar nela com dados
  já coletados.

Frequência: 0 ocorrências de `primeiro_o_link` nos logs de 30 dias com o
filtro usado (o log da recusa é `[Link] ... recusado`); a trava só
dispara com domínio + paciente encontrada + sem link do bot em 7 dias, e
a Nobre começou a ter pacientes recorrentes agora. Vai crescer com a
campanha de datas.

### 2.3 Caso 3 (Nobre, paciente C): despedida em dobro

Jornada: agendou pelo site após a campanha; "Muito obrigada 😊" → "Por nada,
{nome}! Até o dia 03/12 💛" → "Até 🙂" → "Até lá, {nome}! 💛".

Por que aconteceu:

- Não existe caminho para o agente ficar calado. Resposta vazia do modelo
  é tratada como falha: pede versão curta, depois handoff com "Deixa eu
  confirmar isso certinho com uma especialista" (`conversation_agent.py:
  765-787, 1039`). O modelo, corretamente, prefere responder.
- O prompt default ainda diz "Termine TODA mensagem com uma pergunta".
- A guarda de fecho social (`retomada.e_fecho_social`, regex com
  obrigada/tchau/até mais) existe só na retomada automática por vencimento
  do humano. Nem o fluxo normal nem a retomada pelo painel a usam.

Frequência: `sem_consulta_necessaria` foi chamada 340 vezes em 30 dias,
boa parte em agradecimento/despedida; não há métrica do "dobro" hoje.

### 2.4 Achados da revisão geral (além dos três casos)

1. **Instruções contraditórias sobre o FAQ no mesmo prompt.** O template
   do banco diz "Responda com o que a tool devolveu. Pode resumir e
   ajustar o tom"; o bloco que o código anexa diz "NÃO o repita, NÃO o
   resuma, NÃO o reformule". O modelo recebe as duas.
2. **Lead cadastrada sem sessão é tratada como lead nova pelo prompt e
   como paciente pela trava** (caso 2). Fonte única violada
   ([[feedback-fonte-unica-de-verdade]]).
3. **44 minutos de silêncio por política** (caso 1): com `LEADS_ONLY`,
   1.768 mensagens recebidas em 30 dias na Nobre ficaram sem resposta
   automática até alguém apertar "Retomar bot". É decisão de negócio da
   Nobre, mas a jornada de compra começa com o lead esperando.
4. **Retomada pelo painel sem a guarda de fecho social**: "obrigada"
   como última mensagem gera uma resposta a mais quando alguém retoma.
5. **Primeira resposta na retomada não responde o que foi perguntado**
   (caso 1): o prompt da retomada manda "responder exatamente o que ela
   perguntou por último" e o modelo foi para a etapa de áreas. A
   instrução da virilha no prompt vence a da retomada.
6. **O prompt default (código) ainda manda `present_options` para
   serviços** e termina toda mensagem com pergunta; o prompt de prod da
   Nobre e da Essência diverge do default em vários pontos. Dois prompts
   vivos sem teste de regressão entre eles.
7. **O eval não cobre pacientes nem FAQ** (corpus só de leads, FAQ vazio
   no banco falso): os três casos deste PRD não seriam pegos.

---

## 3. Princípios de produto (o que "bom" significa aqui)

Pensando como jornada de compra, não como atendimento:

- **Responder primeiro o que foi perguntado**, na mesma mensagem, mesmo
  que a resposta seja "depende de X, qual é o seu caso?".
- **Informação sob demanda**: a base de conhecimento é fonte para o bot
  escrever, não um texto a ser entregue. Explicação completa só quando a
  pessoa pede a explicação.
- **Nunca devolver tarefa a quem já está fazendo o trabalho na conversa**:
  se a pessoa está respondendo perguntas do bot, o bot fecha. O link é
  oferta, não recusa.
- **Uma despedida.** Conversa encerrada não recebe eco.
- **Determinismo onde a regra é de negócio, modelo onde é linguagem**:
  decisões de "link ou conversa", "calar ou responder", "literal ou
  resumido" são código; a redação é do modelo.
- **Toda mudança medida** no eval antes de prod, com os três casos como
  fixtures de regressão.

---

## 4. Proposta

### 4.1 FAQ como fonte de verdade, com dois modos de entrega (caso 1)

Hoje: todo item sai literal, em bolha própria, antes da fala do modelo.

Proposta: cada item do FAQ ganha um modo, escolhido no painel:

| Modo | Comportamento | Para quê |
|---|---|---|
| `fonte` (padrão) | A tool devolve o texto ao modelo como "DADOS CONSULTADOS AGORA". O modelo responde SÓ a pergunta feita, com as palavras do item, resumido. Nada vai literal. | Tipos de virilha, dor, número de sessões, intervalo, resultado, estacionamento |
| `literal` | Como hoje: bolha própria, byte a byte, e o modelo não repete. | Textos que a clínica quer exatos: contraindicações, cuidados pré e pós, política de cancelamento |

Guardas que ficam e guardas novas:

- Continua obrigatório chamar a tool antes de responder dúvida de
  procedimento; a tool continua com enum fechado; "sem item" continua
  handoff. O que muda é a entrega.
- No modo `fonte`, a fala do modelo passa por uma checagem de
  ancoragem: os números e termos factuais da resposta (quantidades,
  prazos, graus, nomes de produto) precisam existir no item devolvido;
  se não, reescreve uma vez com "PARE" (mesmo molde das travas de
  narração e valor) e, na segunda, cai para a bolha literal. Isso
  mantém a promessa do PRD 020 ("FAQ literal") no pior caso.
- Ordem na mensagem: saudação (se for a primeira), resposta, pergunta
  de condução. Bolha literal, quando houver, sai DEPOIS da fala do
  modelo, não antes.

Virilha, em particular (prompt do banco, etapa 3): trocar a instrução
"chame get_faq_answer; o texto já vai; sua fala é só 'qual prefere?'" por:

> Virilha sem o tipo dito: pergunte qual (simples, cavada ou completa)
> com uma linha de diferença para cada, usando o item BIKINI_TYPES como
> fonte. Se a pergunta era de preço, diga que o valor depende do tipo e
> já pergunte o tipo. Depois do tipo, uma linha: incluir perianal?
> Explicação completa dos tipos só se ela pedir.

Resposta esperada para o caso 1 (uma mensagem):

> Oi, tudo ótimo! 😊 Aqui é da Nobre Laser SJC. O valor da virilha
> depende do tipo: simples (só o que fica para fora do biquíni), cavada
> (quase toda, deixando uma faixa central) ou completa (toda a região).
> Qual delas você quer? Se quiser, dá para incluir a região perianal
> junto com a completa.

Alternativa (menor): manter a bolha literal, mas só quando a pessoa
PERGUNTA a diferença (detecção de pergunta sobre tipos), nunca quando só
cita a área; e inverter a ordem (fala do modelo antes da bolha). Resolve
o caso 1 sem mexer na tool, mas mantém "jogar o texto todo" como a única
forma de explicar e não resolve o item 1 do §2.4.

### 4.2 Link ou conversa: decisão no início do turno, nunca na última tool (caso 2)

Hoje: bloco de prompt para algumas skills + trava na tool de agendar.

Proposta: uma função só, `caminho_de_agendamento(clinic, paciente,
session, intencao)`, decidida ANTES do modelo, com três saídas:

| Saída | Quando | O que o bot faz |
|---|---|---|
| `conversa` | lead sem cadastro; OU clínica sem domínio; OU a pessoa já está no meio de um agendamento na conversa (áreas ou data ditas neste atendimento); OU o link já foi (7 dias) | agenda na conversa, como sempre |
| `link_primeiro` | paciente com cadastro, primeiro pedido de agendar neste atendimento, link ainda não enviado PELO BOT (campanha e lembrete não contam) | responde em uma frase com o link, sem oferta de marcar por aqui, e se coloca à disposição para dúvidas |
| `conversa_por_insistencia` | ela pede de novo para marcar pela conversa depois do link (segundo pedido, ou "não consigo", "prefiro aqui") | agenda na conversa até o fim; nenhuma guarda devolve link no fechamento |

Regras:

- A trava `primeiro_o_link` na tool deixa de existir como recusa. Fica
  como asserção de consistência (log) para o eval: se o caminho decidido
  foi `link_primeiro` e o modelo chamou `book_appointment` sem ter
  mandado o link, é violação medida, não recusa à cliente.
- Link da campanha e do lembrete NÃO contam (mantém a decisão de 10/11):
  a primeira resposta do bot a um pedido de agendar é o link, sozinho.
  Decisão P2 de 25/11.
- Estado `NEW_LEAD` com cadastro recebe o mesmo bloco das skills de
  paciente (fecha o item 2 do §2.4).
- O resumo de confirmação ("Então ficou assim... Confirmo?") passa a ser
  compromisso: depois dele, nenhuma guarda pode trocar o fechamento por
  link.

Resposta esperada para o caso 2 (após a campanha com link): "Boa tarde,
{nome}! Claro. Pra eu marcar, me confirma as áreas dessa sessão?" e
segue até "Agendamento confirmado", sem link.

Alternativa: manter "link primeiro" como está, mas mover a decisão para o
início do turno (mensagem fixa com link + oferta de fechar por aqui) e
nunca depois de coletar dados. Mais barato; mantém o site como primeira
tentativa, que foi a decisão de 10/11. Ver pendência P1.

### 4.3 Despedida uma vez: caminho de silêncio (caso 3)

Proposta, em código, antes do modelo:

- `e_fecho_social(texto)` (já existe) aplicado à mensagem recebida; se a
  última mensagem do bot nas últimas 24 h também foi de encerramento
  (despedida/agradecimento, sem pergunta em aberto) e a fala nova não
  contém pergunta nem informação nova (sem "?", sem data, sem área, sem
  número), o bot NÃO responde. Log `[FechoSocial] calei`.
- A mesma guarda entra na retomada pelo painel (`conversation_resume`).
- O agente ganha um retorno explícito "sem resposta" distinto de "falha":
  resposta vazia depois de `sem_consulta_necessaria(motivo=despedida)`
  deixa de virar handoff.
- Prompt: "Depois de se despedir, não responda a outra despedida. Só
  volte se houver pergunta ou informação nova." e remover do default
  "Termine TODA mensagem com uma pergunta".

Alternativa: em vez de calar, reagir com emoji (z-api `send-reaction`)
na mensagem dela. Dá sinal de recebido sem abrir outro turno. Depende de
confirmar que a z-api expõe reação para a instância da clínica. Ver
pendência P4.

### 4.4 Retomada responde a última pergunta (caso 1, §2.4 item 5)

- No gatilho `__RETOMAR_CONVERSA__`, o bloco de retomada passa para o
  FIM do system prompt (último vence) e inclui a última pergunta da
  pessoa extraída pelo código ("Pergunta em aberto: 'Quanto é a
  depilação na virilha?'").
- Trava determinística: se a última fala da pessoa tem "?" e a resposta
  do modelo não contém nenhum termo dela (preço/valor/quanto) nem número,
  reescreve uma vez: "PARE. Responda primeiro a pergunta: ...".

### 4.5 Fonte única do prompt e eval com pacientes (§2.4 itens 1, 6, 7)

- Apagar do bloco do código a instrução "NÃO resuma" (vira regra por modo
  do item) e do default "present_options para serviços" e "termine toda
  mensagem com pergunta". O default do código passa a ser o prompt de
  prod da Essência (uma fonte), com as variáveis por clínica.
- Eval: corpus com pacientes (cadastro, com e sem sessão), FAQ real da
  clínica no banco falso, e as três conversas deste PRD como fixtures
  com asserções: (1) caso 1 → resposta contém "depende do tipo" ou os
  três tipos, sem bolha literal, saudação antes; (2) caso 2 → zero link
  após o resumo de confirmação; (3) caso 3 → zero mensagens no segundo
  "até". Rodar antes e depois; custo ~US$ 5 por rodada.
- Métricas novas de produto, por clínica e semana (do MessageEvents +
  logs): mensagens até o agendamento, taxa conversa → agendamento (bot e
  site), bolhas de FAQ por modo, links enviados e agendamentos pelo site
  em até 24 h após o link, "calei" por fecho social, handoffs por motivo.

### 4.6 Saudação pelo relógio, não pelo eco (pedido do André em 25/11)

Hoje o bot repete a saudação da pessoa: "Olá, boa noite" recebido à noite
e respondido na manhã seguinte (retomada, política `LEADS_ONLY`) sai como
"Olá, boa noite". O turno da pessoa já traz o bloco `═══ CALENDÁRIO ═══`
com a data; falta a hora.

Proposta: o código acrescenta ao bloco a hora local da clínica e o
período ("Agora: terça, 24/11, 08:12 - manhã"), e o prompt passa a dizer:
"Cumprimente pelo período de AGORA (bom dia até 12h, boa tarde até 18h,
boa noite depois), nunca copiando a saudação da pessoa. Em dúvida, só
'Olá'." Trava determinística: se a resposta contém "bom dia/boa tarde/
boa noite" de período diferente do atual, troca pelo período certo (ou
por "Olá") antes de enviar. Custo zero de modelo, e cobre a retomada.

Alternativa (se o relógio der trabalho): só "Olá", sempre, e remover
"boa noite/bom dia" da saída por regex.

### 4.7 Fora do escopo

- Mudar a política `LEADS_ONLY` da Nobre (é decisão da clínica; ver P5).
- Reescrever o prompt da Essência (só as etapas tocadas aqui).
- Campanha e lembrete (textos e gatilhos) seguem como estão.

---

## 5. Áreas / arquivos impactados (previsão; a Spec detalha)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/policy_do_faq.py`, `ai_tools.py` (get_faq_answer) | modificar | modo por item (`fonte`/`literal`), retorno do texto ao modelo, ancoragem |
| `scheduler/src/scripts/setup_database.py` | modificar | `faq_items.delivery_mode` (migration idempotente) |
| `frontend/` (FAQ no painel) | modificar | seletor do modo por item |
| `scheduler/src/services/caminho_de_agendamento.py` | criar | decisão link/conversa no início do turno |
| `scheduler/src/services/ai_tools.py` (`_recusa_sem_o_link`) | modificar | recusa vira asserção/log |
| `scheduler/src/services/skills/__init__.py`, `conversation_agent.py` | modificar | bloco do site por cadastro, não por skill; caminho de silêncio; retomada |
| `scheduler/src/services/fecho_social.py` (extraído de `retomada.py`) | criar | guarda de despedida compartilhada |
| `scheduler/src/services/conversation_resume.py` | modificar | guarda de fecho social |
| `scheduler/src/services/template_service.py` | modificar | default = prompt de prod; remove instruções contraditórias |
| `scheduler/src/scripts/corrige_prompt_virilha.py` | criar | reescreve a etapa 3 no banco (Essência e Nobre) |
| `scheduler/tests/evaluation/` | modificar | corpus com pacientes, FAQ real, 3 fixtures de regressão |

---

## 6. Dependências e riscos

- **Dependências:** prompt de prod no banco (duas clínicas), painel para o
  modo do FAQ, eval com acesso ao banco de prod (só leitura).
- **Riscos:**
  - Modo `fonte` abre espaço para o modelo "melhorar" o texto da clínica;
    a ancoragem e o fallback literal limitam, mas não zeram. Começar com
    `literal` nos itens médicos (contraindicações, cuidados) e `fonte`
    nos comerciais.
  - Agendar na conversa para paciente (4.2) aumenta o custo por
    conversa (mais turnos com tools) e tira do site a confirmação por
    código. Medir taxa e custo por agendamento nos dois caminhos.
  - Calar por fecho social pode engolir uma mensagem real ("obrigada,
    e amanhã abre?"). A guarda exige ausência de "?" e de dado novo;
    falso negativo vira uma resposta a mais, nunca uma pergunta sem
    resposta.
  - Dois prompts vivos (Essência e Nobre) tocados por script: rodar o
    eval com `--prompt-arquivo` antes de gravar, como no PRD 037.

---

## 7. Critérios de aceite

- [ ] Caso 1 replayado: uma mensagem, saudação antes, pergunta do tipo
      com uma linha por tipo, sem bolha literal, perianal depois.
- [ ] Caso 2 replayado: nenhum link depois do resumo de confirmação;
      agendamento criado na conversa (ou link na primeira resposta, se P1
      decidir assim).
- [ ] Caso 3 replayado: zero mensagens após o segundo "até".
- [ ] Eval antes/depois sem piora em I1 a I5; fixtures novas passando.
- [ ] Painel: modo por item do FAQ; itens médicos em `literal`.
- [ ] Logs `[FAQ] modo=...`, `[Caminho] link|conversa`, `[FechoSocial]
      calei` em prod por uma semana, com os números de §4.5 no TASKS_LOG.

---

## 8. Pendências de negócio (decidir antes da Spec)

Decisões do André em 25/11/2026: P1 proposta; P3 alternativa (tudo em
modo `fonte`, bolha literal só como fallback da ancoragem); P4 proposta
(calar); P5 alternativa, com mensagem menos fria; P6 alternativa (listar
os três tipos com valor e perguntar qual); P7 proposta (calar).
P2 (25/11, depois da reexplicação): alternativa, SEM a oferta "se preferir
eu marco agora". O link vai sozinho na primeira resposta. Se ela insistir
mais uma vez em marcar pela conversa, o bot conduz o agendamento até o
fim e nunca manda link no fechamento. A mesma regra vale para a P1 (a
oferta sai de lá também): primeira resposta é só o link; insistência é
conversa até o fim.

Texto proposto para P5 (mensagem imediata na Nobre quando o bot não pode
atender pela política; não conta como atendimento do bot e não repete na
mesma conversa em 24 h): "Oi! Que bom ter você por aqui 😊 Já recebi sua
mensagem e uma especialista da Nobre vai te responder em instantes."

P2, reexplicada. A campanha e o lembrete já levam o link do site no
texto. Quando a paciente responde a esse texto pedindo para marcar, o bot
precisa decidir se aquele link "já foi":
- Conta (proposta): ela viu o link e mesmo assim escreveu; o bot entende
  que ela prefere resolver na conversa e agenda aqui, sem reenviar nada.
- Não conta (alternativa): o bot reenvia o link uma vez na primeira
  resposta, com a oferta "se preferir, eu marco por aqui", e só agenda na
  conversa se ela disser que prefere.
Com P1 = proposta, a diferença prática é só esta: depois de uma campanha,
a primeira resposta do bot a "podemos marcar dia 3?" é "claro, me confirma
as áreas" (conta) ou "é pelo link, mas se preferir eu marco" (não conta).

| # | Pergunta | Proposta | Alternativa |
|---|---|---|---|
| P1 | Para paciente com cadastro que pede para agendar NA CONVERSA (sem campanha/lembrete), o site continua sendo a primeira tentativa? | Sim, mas decidido no início: uma frase com o link + "se preferir, eu marco agora"; nunca recusar depois de coletar dados | Abandonar "link primeiro": paciente que escreve é atendida na conversa; link só sai proativo (campanha, lembrete, cancelamento) |
| P2 | Link mandado pela campanha ou lembrete conta como "link já foi"? | Sim: quem responde à campanha é agendada na conversa, sem reenvio | Não (como hoje): o bot reenvia o link uma vez, com a oferta de fechar aqui |
| P3 | Quais itens do FAQ devem continuar literais? | Contraindicações, cuidados pré/pós, política de cancelamento/atraso; o resto em modo `fonte` | Tudo em `fonte`, com fallback literal só na falha de ancoragem |
| P4 | Despedida repetida: calar ou reagir com emoji? | Calar (zero custo, zero ruído) | Reação 💛 via z-api, se a API expuser |
| P5 | Nobre em `LEADS_ONLY`: a jornada começa com até 44 min de silêncio para quem escreve por conta própria. Manter? | Trocar para `ALL` na Nobre, mantendo as guardas (risco, fora do escopo, handoff) e a pausa automática quando alguém da clínica responde | Manter `LEADS_ONLY` e mandar uma mensagem fixa imediata ("já te respondo") que não conte como atendimento do bot |
| P6 | Preço de virilha: ao perguntarem "quanto é a virilha", o bot pode dizer os três valores direto (de list_areas) em vez de perguntar o tipo primeiro? | Perguntar o tipo com uma linha por tipo (menos ruído, conduz) | Listar os três com valor e perguntar qual (mais informação, uma mensagem a menos) |
| P7 | Retomada pelo painel quando a última mensagem é "obrigada": calar ou "estou à disposição"? | Calar (mesma guarda do fecho social) | Uma linha à disposição, como o prompt manda hoje |

---

## 9. Referências

- PRD 020 (atendimento único: FAQ literal, skills por estado), 027
  (lembrete), 037 (áreas em conversa), 046 (site como primeira tentativa),
  056/060 (uma sessão por mês, `?meus=1`), 059 (cancelamento).
- Memória: `bugs-do-bot-06-10` (receita de diagnóstico), decisão de
  23/11 sobre o FAQ `INTIMATE_AREA_SCOPE`.
- Código: `scheduler/src/services/conversation_agent.py`, `policy_do_faq.py`,
  `ai_tools.py`, `skills/__init__.py`, `autoatendimento.py`, `retomada.py`,
  `conversation_resume.py`, `tests/evaluation/eval_fluxo_agente.py`.

---

## Status (preencher após conclusão)

- [x] Decisões P1 a P7 fechadas em 25/11/2026
- [x] Spec gerada: `spec/064-jornada-do-bot-faq-link-e-despedida.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
