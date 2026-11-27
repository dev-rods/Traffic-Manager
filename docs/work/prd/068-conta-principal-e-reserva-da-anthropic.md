# PRD - 068 Conta principal e conta reserva da Anthropic

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

O bot passa a usar duas chaves da API da Anthropic, em ordem: a **principal**,
de uma conta de API do André, e a **reserva**, que é a chave usada hoje. Toda
chamada vai primeiro à principal. A reserva só entra quando a principal for
recusada por falta de saldo, limite de gasto ou chave inválida. Quando a
reserva for usada, o André recebe um aviso. Ele recebe outro aviso, mais
grave, se as duas falharem e o bot ficar calado.

O objetivo é de custo e de continuidade. O gasto normal sai da conta do
André, a conta atual vira rede de segurança, e o bot não para mais em
silêncio por falta de saldo, como parou em 14/09.

---

## 2. Contexto

### Onde o bot pega a conta hoje (levantado em 27/11/2026)

- **Uma chave só:** `ANTHROPIC_API_KEY` é variável de ambiente de todas as
  Lambdas do scheduler. O valor vem do SSM (`/${stage}/ANTHROPIC_API_KEY`) e é
  lido **no deploy** (`${ssm:...}` em `scheduler/serverless.yml:123`). Trocar
  o valor no SSM só vale depois de um novo deploy.
- **Parâmetros:** `/dev/ANTHROPIC_API_KEY` foi gravado em 04/04/2026 e
  `/prod/ANTHROPIC_API_KEY` em 26/04/2026. Os dois têm versão 1 e foram
  gravados pelo usuário IAM `traffic-manager`. O SSM não diz de qual conta da
  Anthropic é a chave. Isso se confere no Console da Anthropic, em API keys,
  pelo final da chave.
- **Ponto único de chamada:** `scheduler/src/services/anthropic_service.py`.
  É um `requests.post` direto em `/v1/messages`, com retentativa em 429, 5xx
  e falha de rede. Ele atende três usos:
  - a conversa do bot (`conversation_agent.py`);
  - a classificação de leads (`classificador_de_lead.py`);
  - a decisão de retomar ou calar no cron de expiração (`atendimento/expira.py` e `retomada.py`).

  Basta mexer num arquivo para cobrir os três.
- **Eval:** `tests/evaluation/eval_fluxo_agente.py` lê a chave de
  **prod** do SSM quando roda na máquina. Esse gasto não aparece nos logs das
  Lambdas.
- **Quando a API recusa hoje:** o erro 400 de saldo não é retentado. Vira
  `AnthropicError`, e o atendimento cai em `entrega_por_instabilidade` (regra
  de 15/09). O bot cala, a conversa vai para uma pessoa e só fica uma linha
  `ERROR` no log. Ninguém é avisado de fora.

### "A conta desta sessão"

Esta sessão do Claude Code não usa chave de API. Ela entra com a
**assinatura Max** do André no claude.ai, por login OAuth. A assinatura e a
API são cobradas separadamente:

- os créditos e limites do Max não pagam chamadas de API;
- o token de login do Claude Code é pessoal, renovado pelo próprio app, e não
  serve para alimentar um serviço;
- usar esse token num servidor iria contra os termos da Anthropic e
  quebraria na próxima renovação.

O que dá para fazer com a mesma conta é usar o **Console da Anthropic**
(console.anthropic.com), com o mesmo e-mail do André. Lá ele tem ou cria uma
organização de API, compra créditos ou liga a recarga automática e gera uma
chave. Essa chave é a **principal** deste PRD.

### Consumo medido (logs `[Consumo]`, últimos 30 dias, retenção de 90)

| Stage | Chamadas | Custo estimado |
|---|---|---|
| prod | 2.731 (WhatsAppWebhook 2.571, AttendantControl 160) | **US$ 104,68** |
| dev | 37 | US$ 1,25 |

A estimativa usa a tabela de preços de `consumo.py` e não inclui o eval rodado
na máquina. Sem picos, a principal precisa de uns **US$ 100 a 150 por mês**.

### Estado agora

O André disse que o bot está sem crédito. Os logs ainda não mostram erro: não
há linha de saldo nem de `Anthropic API error` em prod nos últimos 3 dias, nem
em dev nos últimos 7. Prod não chamou a API desde 26/11 às 20h06 (horário de
Brasília). As duas clínicas estão em `LEADS_ONLY`, e o bot só responde depois
do "Iniciar bot".

Quando a recepção iniciar o bot, a primeira chamada vai falhar e a conversa
vai calada para uma pessoa. Conferir o saldo com uma chamada de teste foi
bloqueado nesta sessão. O saldo se confere no Console.

**Paliativo imediato, antes deste PRD:** recarregar a conta atual ou trocar a
chave do SSM e fazer redeploy. Este PRD é a solução, não o paliativo.

---

## 3. Escopo

### Dentro do escopo

1. **Duas chaves, em ordem.**
   - `ANTHROPIC_API_KEY` passa a ser a principal, com a chave do André.
   - A nova `ANTHROPIC_API_KEY_RESERVA` recebe a chave de hoje.
   - As duas vêm do SSM no deploy, como hoje.
   - Sem reserva configurada, o comportamento é exatamente o de hoje.
2. **Quando vai para a reserva:** só em recusa da conta, nunca em falha passageira.

   | Resposta da principal | O que acontece |
   |---|---|
   | 400 com saldo insuficiente ou limite de gasto atingido | reserva |
   | 401 chave inválida ou revogada | reserva |
   | 403 sem permissão | reserva |
   | 429, 5xx, 529, timeout, rede | retentativa na própria principal, como hoje |
   | qualquer outro 400 (pedido mal formado) | erro, sem reserva |

   Um 400 de pedido mal formado falharia igual na reserva. Passar para ela só
   gastaria a outra conta.

   A spec confere na documentação da API o texto e o tipo exatos dos erros de
   saldo e de limite de gasto, e os fixa como vetores de teste.
3. **Memória da recusa (D4: 24 h).** Depois que a principal é recusada, o
   mesmo contêiner da Lambda vai direto à reserva por 24 horas e então tenta a
   principal de novo. Não se paga meio segundo de recusa em cada uma das 2 a
   4 chamadas de uma mensagem.

   A memória vive no contêiner, e a AWS recicla contêineres em horas. Na
   prática, cada contêiner novo tenta a principal uma vez e volta a ela se já
   houver saldo. Para voltar na hora depois de recarregar, basta um redeploy
   do scheduler, que zera todos os contêineres. O aviso de volta da principal
   (item 4) chega assim que ela atender a primeira chamada.
4. **Aviso de reserva em uso.** Cada chamada atendida pela reserva grava uma
   linha estruturada no log. Um alarme do CloudWatch transforma essa linha em
   um aviso por episódio, não um por chamada. Outro aviso sai quando a
   principal volta.
5. **Aviso de bot calado.** Um segundo alarme, mais grave, dispara quando as
   duas contas falham, ou quando só existe uma conta e ela falha. É o caso de
   `entrega_por_instabilidade`, hoje invisível.
6. **Consumo por conta.** A linha `[Consumo]` ganha `conta=principal` ou
   `conta=reserva`. Assim "quanto a reserva pagou este mês" vira uma
   consulta no Insights.
7. **Eval** passa a ler a principal e a reserva, como as Lambdas. Continua
   usando as chaves de prod, e o gasto vai para a principal.

### Fora do escopo

- Usar a assinatura Max ou o login do Claude Code no bot (ver 2).
- Mudar modelo, prompt ou número de chamadas por mensagem para reduzir custo.
- Ler a chave do SSM em tempo de execução para trocar sem deploy. Recarregar
  saldo não exige troca de chave, e trocar de chave é raro.
- Painel com saldo ou gasto. A Anthropic não expõe saldo pela API de
  mensagens. O gasto já sai do Insights pelo item 6.
- Avisar a clínica. O aviso é para o André.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/anthropic_service.py` | modificar | ordem principal → reserva, classificação da recusa, memória de 24 h, linha de log por conta |
| `scheduler/src/services/consumo.py` | modificar | `conta=` na linha `[Consumo]` |
| `scheduler/serverless.yml` | modificar | `ANTHROPIC_API_KEY_RESERVA` vindo do SSM |
| `scheduler/sls/resources/` (novo arquivo) | criar | tópico SNS, assinatura do aviso, 2 filtros de métrica e 2 alarmes |
| `scheduler/tests/unit/test_anthropic_reserva.py` | criar | vetores de recusa e de falha passageira, ordem, memória, sem reserva |
| `scheduler/tests/unit/test_anthropic_retentativa.py` | conferir | retentativa continua só na mesma conta |
| `scheduler/tests/evaluation/eval_fluxo_agente.py` | modificar | lê as duas chaves |
| SSM `/{dev,prod}/ANTHROPIC_API_KEY_RESERVA` | criar | **feito em 27/11**: cópia da chave de hoje |
| SSM `/{dev,prod}/ALERTA_EMAIL` | criar | e-mail do André para o aviso (D2), fora do repositório |
| SSM `/{dev,prod}/ANTHROPIC_API_KEY` | atualizar | chave do André. **Quem grava é o André**: a chave não passa por esta sessão |

Os recursos novos de CloudFormation são 6 por stage (tópico, assinatura, 2
filtros, 2 alarmes). Prod está em 430 de 500 desde o PRD 066 e fica em 436,
dentro da folga.

---

## 5. Dependências e riscos

- **Conta de API do André:** organização no Console com saldo ou recarga
  automática ligada, e uma chave criada para o bot. É pré-requisito do deploy
  em prod, não da implementação. Recomendado também:
  - definir no Console um limite mensal de gasto para a chave principal;
  - deixar a reserva com saldo baixo, já que é só rede de segurança.
- **Ordem de gravação no SSM:** primeiro copiar a chave de hoje para
  `_RESERVA`, depois o André grava a dele em `ANTHROPIC_API_KEY`. Se a ordem
  inverter, perde-se a chave de hoje (o SSM guarda o histórico de versões, mas
  é melhor não depender disso).
- **Classificação errada da recusa:**
  - Se a classificação for larga demais, um 400 de pedido mal formado vai à
    reserva. Gasta a outra conta e falha igual. Os vetores de teste seguram
    isso.
  - Se for estreita demais, a reserva não entra e o bot cala. O alarme de bot
    calado cobre esse caso.
- **Cache de prompt por conta:** o cache da Anthropic é por organização. Na
  primeira chamada após a troca, a reserva paga a escrita do cache de novo
  (cerca de 1,25x do prefixo). É custo pequeno e de uma vez por janela de cache.
- **Aviso por e-mail exige confirmação:** a assinatura do SNS manda um e-mail
  de confirmação. Até o André clicar, nenhum aviso chega. O critério de aceite
  cobre isso.
- **Dev manda WhatsApp de verdade:** o teste da reserva em dev não passa pelo
  webhook com número inventado. O teste é de unidade, mais uma chamada real
  com a chave principal inválida de propósito, feita por script direto no
  serviço, sem WhatsApp.

---

## 6. Critérios de aceite

- [ ] Com a principal válida, nenhuma chamada usa a reserva e o `[Consumo]`
      mostra `conta=principal`.
- [ ] Com a principal recusando por saldo ou chave, a chamada é atendida pela
      reserva, a paciente recebe a resposta normal e o `[Consumo]` mostra
      `conta=reserva`.
- [ ] 429, 5xx e falha de rede continuam retentados na principal, sem tocar
      a reserva.
- [ ] Um 400 de pedido mal formado não vai à reserva.
- [ ] Sem `ANTHROPIC_API_KEY_RESERVA`, o comportamento é idêntico ao de hoje.
- [ ] O André recebe um aviso no primeiro uso da reserva e um quando a
      principal volta, sem repetir a cada chamada. Com as duas falhando, ele
      recebe o aviso de bot calado.
- [ ] Em dev, o teste real com a principal inválida de propósito gera o aviso
      e a resposta sai pela reserva, sem WhatsApp.
- [ ] Testes, lint e deploy em dev verdes. Prod só depois da chave do André
      no SSM e do OK dele.

---

## 7. Referências

- `scheduler/src/services/anthropic_service.py`, `consumo.py`,
  `bot_policy.entrega_por_instabilidade` (incidente de 14 e 15/09).
- PRD 066 (contagem de recursos do CloudFormation).
- Memórias `pane-anthropic-05-11` e `divida-limite-cloudformation`.

---

## Decisões (André, 27/11/2026)

- **D1. Canal do aviso:** e-mail pelo SNS, disparado por alarme do
  CloudWatch. Não precisa de código para evitar aviso repetido, porque o
  alarme só muda de estado uma vez, e também avisa quando a principal volta.
  Não depende do WhatsApp nem do bot. Descartado: WhatsApp pelo número de uma
  clínica.
- **D2. Para quem:** só o André. O e-mail fica fora do repositório, no SSM
  `/${stage}/ALERTA_EMAIL`, lido no deploy.
- **D3. Dev:** igual a prod, com a chave do André como principal e a de hoje
  como reserva. As reservas `/{dev,prod}/ANTHROPIC_API_KEY_RESERVA` já foram
  copiadas da chave atual em 27/11 (conferido por hash).
- **D4. Memória da recusa:** 24 horas (ver item 3 do escopo).

---

## Status (preencher após conclusão)

- [x] Pendente
- [x] Spec gerada: `spec/068-conta-principal-e-reserva-da-anthropic.md`
- [x] Implementado em: 2026-11-27, EM PROD (PR #285, merge `3971f46`; scheduler dev layer 230, prod layer 184). Antes, redeploy de prod a partir da main (layer 183) para a chave nova valer.
- [x] Registrado em `TASKS_LOG.md`

Verificação:
- Local, contra a API real: a principal inventada recebeu 401, a reserva atendeu, e saíram a métrica EMF e o `[Consumo]` com `conta=reserva`.
- Em dev, os alarmes foram disparados por `put-metric-data`: os dois foram para ALARM e publicaram no SNS.
- Não houve teste do EMF dentro de uma Lambda. Nenhuma rota chama o modelo sem poder enviar WhatsApp: a `ClassificaLeads` com `dryRun` não precisou do modelo.

Pendências:
- O André confirmar as duas assinaturas de e-mail (dev e prod).
- Conferir a primeira chamada real com `conta=principal`.
- `/dev/ANTHROPIC_API_KEY` ainda é a chave antiga (D3).
- A chave antiga respondeu 200 em 27/11: a conta tinha saldo nesse dia.
