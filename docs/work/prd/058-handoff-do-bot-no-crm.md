# PRD - 058 Handoff do bot no CRM: pedido de ajuda sem resposta é AGUARDANDO_NOS

> Gerado na fase **Research** em 22/11/2026, a partir dos dados da primeira
> classificação em prod do PRD 057 (22/11). Pendência registrada na revisão de
> 22/11 do PRD 057 ("handoff do bot conta como mensagem nossa").
> Vale como PRD e como spec de desenho: as decisões abaixo já foram tomadas.

---

## 1. Objetivo

Quando o bot entrega a conversa a uma pessoa ("vou confirmar com uma
especialista e já te retorno") e ninguém da clínica assume, o lead está
esperando por nós. O CRM (PRD 057) precisa mostrar esse lead em
`AGUARDANDO_NOS`, com o motivo "o bot pediu ajuda em DD/MM e ninguém assumiu",
e não deixar o modelo concluir que ele "não agendou".

---

## 2. Contexto

### 2.1 O que existe

- `estagio_do_lead.decide` (PRD 057) lê a transcrição do MessageEvents e
  decide pela **direção** da última mensagem: do lead → `AGUARDANDO_NOS`; nossa
  → `EM_ANDAMENTO`, e `SUMIU` depois de N dias. "Nossa" é qualquer OUTBOUND:
  bot, atendente ou sistema (PRD 057 §5.3).
- A mensagem de handoff do bot ("Vou confirmar as próximas datas com uma
  especialista e já te retorno") é um OUTBOUND do bot. Para a regra ela parece
  resposta. Não é: é um aviso de que a resposta vem de uma pessoa, e a pergunta
  do lead continua em aberto atrás dela. A retomada (PRD 020 fase 3,
  `conversation_resume.ha_pergunta_em_aberto`) já trata o aviso assim.
- O estado de atendimento (`atendimento.bloco`, PRD 020 §3.2) sabe quem
  entregou: `pausado_por` em `ENTREGAS_DO_BOT` (HANDOFF, INSTABILIDADE),
  `entregue_em` (epoch) e, com tarefa aberta, `HUMAN_PENDING`, que só sai por
  "fechar tarefa" ou "retomar bot" no painel. `status_da_conversa` já traduz
  isso para o rótulo AGUARDA_HUMANO da página `/leads`.
- O MessageEvents guarda o autor do OUTBOUND (`autoria_mensagem.autor_da_mensagem`:
  BOT, HUMANO, SISTEMA); a transcrição do 057 (`transcricao.Mensagem`) descarta
  o autor e guarda só LEAD/NOS.

### 2.2 O que os dados de prod mostraram (22/11/2026, só leitura)

1.667 sessões; 14 conversas entregues pelo bot e ainda com o bloco de entrega:

| Situação | Qtd | Estágio gravado em 22/11 | Certo? |
|---|---|---|---|
| Bot entregou, **ninguém assumiu**, última mensagem é o aviso do bot | 1 (Nobre, 09/11, tarefa aberta) | `NAO_AGENDOU` / MODELO, "indisponibilidade de horário no mês" | **Não.** A pergunta era nossa de responder. |
| Bot entregou, ninguém assumiu, última mensagem é do lead | 1 (Essência, 15/11) | `AGUARDANDO_NOS` | Sim, pela regra atual |
| Bot entregou por INSTABILIDADE (06/11), ninguém assumiu, bloco já venceu | 1 (Essência) | `NAO_AGENDOU` / MODELO, "cotando valores" | Fora deste PRD: o bloco venceu, o sinal não existe mais; é questão do prompt de desfecho |
| Bot entregou e **alguém da clínica respondeu** depois | 11 | AGENDOU 5, FALTOU 2, EM_ANDAMENTO 2, SUMIU 2 | Sim: agenda ou conversa normal |

Dois achados que mudam o desenho:

- `aguarda_especialista(sessao)` sozinho não serve: em 11 das 14 a atendente
  respondeu pelo celular e o bloco continuou `HANDOFF`/`HUMAN_PENDING` (a
  resposta humana renova o prazo, não troca o `pausado_por`, e a tarefa segue
  aberta até alguém fechar no painel). O sinal precisa cruzar com a transcrição:
  **houve fala HUMANA depois de `entregue_em`?**
- O veredito do modelo no caso da Nobre tem `stage_updated_at` (22/11)
  posterior ao handoff (09/11). A regra "mensagem nova depois do veredito" não
  o derruba. O veredito nasceu de um dado incompleto e precisa cair enquanto a
  entrega estiver pendente.

### 2.3 O problema

A recepção abre `/crm`, filtra AGUARDANDO_NOS e não vê o lead da Nobre: ele
está em "Não agendou", com um motivo que culpa a agenda. A fila do painel de
tarefas o mostra, mas o CRM, que é a fila semanal, não. E o modelo gastou uma
chamada para julgar um desfecho que ainda não existia.

---

## 3. Escopo

### Dentro do escopo

- Transcrição com autor: `Mensagem.autor` (BOT | HUMANO | SISTEMA | None para o
  lead), lido por `autoria_mensagem`.
- Sinal novo em `Sinais`: `bot_entregou_em` (datetime; preenchido só quando a
  sessão está com pessoa e `pausado_por` em `ENTREGAS_DO_BOT`) e
  `ultima_fala_humana_em` (último OUTBOUND de autor HUMANO).
- Regra `entrega_pendente(s)`: `bot_entregou_em` existe e não há fala humana
  posterior. Efeitos em `decide`:
  1. conta como "a bola está conosco" para CANCELOU/FALTOU (quem cancelou,
     pediu para remarcar e o bot entregou é AGUARDANDO_NOS);
  2. derruba `NAO_AGENDOU`/MODELO enquanto pendente (não derruba NAO_E_LEAD nem
     MANUAL);
  3. nas regras de conversa, vence a direção da última mensagem:
     `AGUARDANDO_NOS`/REGRA com motivo "bot pediu ajuda em DD/MM e ninguém
     assumiu".
- Job `ClassificaLeads` lê as sessões da clínica em lote
  (`status_da_conversa.sessoes_por_telefone`, um BatchGetItem por 100
  telefones) e **não pergunta o desfecho ao modelo** enquanto a entrega estiver
  pendente. A triagem "é lead?" continua.
- Painel: descrição do chip AGUARDANDO_NOS passa a citar o pedido de ajuda. O
  motivo já aparece na linha (`stage_reason`).
- Testes unitários; roteiro de dev com os casos de prod reproduzidos em
  conversas fictícias (seção 8).

### Fora do escopo

- Entrega vencida sem tarefa (INSTABILIDADE depois de 24 h + cooldown): o bloco
  volta ao bot e o sinal deixa de existir. Se o lead escrever, a regra normal
  já o põe em AGUARDANDO_NOS.
- Mudar o prompt de desfecho para "cotando valores sem resposta nossa". Fica
  anotado para a próxima revisão do classificador.
- Triagem para leads de origem `site` (candidatos a emprego da Nobre): outro
  ajuste, se repetir.
- AGENDOU sem distinguir sessão futura de paciente antiga (PRD futuro).

---

## 4. Modelo de dados

Nenhuma coluna nova. O sinal é derivado na hora da classificação de duas
fontes que já existem (bloco `atendimento` da sessão e autor no MessageEvents)
e o resultado é o `stage` + `stage_reason` de sempre.

---

## 5. Regras

### 5.1 Entrega pendente

```
entrega_pendente(s) =
    s.bot_entregou_em is not None
    and (s.ultima_fala_humana_em is None or s.ultima_fala_humana_em < s.bot_entregou_em)
```

`bot_entregou_em` só é preenchido quando `atendimento.aguarda_especialista(sessao)`
é verdadeiro (estado HUMAN_ACTIVE ou HUMAN_PENDING com `pausado_por` em
ENTREGAS_DO_BOT). Fechar a tarefa no painel (`fecha_pendencia`), "Retomar bot"
e o vencimento sem tarefa limpam o `pausado_por`, e o sinal some sozinho. Uma
resposta humana depois da entrega também o apaga, pela transcrição.

### 5.2 Precedência (PRD 057 §5.2, revisada)

```
FATO DA AGENDA  (CANCELOU/FALTOU cedem se o lead falou depois do horário OU se a
                 entrega do bot pendente é posterior ao horário)
NAO_E_LEAD
MANUAL
NAO_AGENDOU/MODELO  (cai com mensagem nova do lead OU com entrega pendente)
ENTREGA PENDENTE -> AGUARDANDO_NOS, REGRA, motivo "bot pediu ajuda em DD/MM e ninguém assumiu"
regras de conversa de sempre
```

"Nossa" mensagem continua sendo qualquer OUTBOUND para a direção; o autor só
entra para saber se **uma pessoa** respondeu depois da entrega. Mensagem do
SISTEMA (lembrete, link) depois do handoff não conta como resposta.

### 5.3 Modelo

`precisa_de_desfecho` não muda; o job pula o desfecho quando a entrega está
pendente. O desfecho julga por que o lead não agendou; com a pergunta dele sem
resposta, não há desfecho a julgar. Economiza a chamada e evita o veredito
errado da Nobre.

---

## 6. Job `ClassificaLeads`

- Lê `CONVERSATION_SESSIONS_TABLE` (já no `environment` global) com
  `dynamodb:BatchGetItem`, uma vez por clínica, para todas as variantes dos
  telefones dos leads.
- `_sinais` recebe a sessão e as mensagens com autor; converte `entregue_em`
  (epoch) para datetime no fuso da clínica, para o motivo sair com a data certa
  ("09/11", não "10/11" por UTC).
- dryRun loga a mudança como hoje; o motivo aparece na linha.

---

## 7. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/transcricao.py` | modificar | `Mensagem.autor`; `resumo` devolve `ultima_fala_humana_em` |
| `scheduler/src/services/estagio_do_lead.py` | modificar | `Sinais.bot_entregou_em`, `Sinais.ultima_fala_humana_em`, `entrega_pendente`, efeitos em `_pela_agenda`, `decide`, `_pela_conversa` |
| `scheduler/src/functions/lead/classifica_estagios.py` | modificar | sessões em lote, `_sinais(..., sessao)`, desfecho pulado com entrega pendente |
| `scheduler/sls/functions/lead/interface.yml` | modificar | `dynamodb:BatchGetItem` na tabela de sessões para ClassificaLeads |
| `frontend/src/pages/crm/estagios.ts` | modificar | descrição do AGUARDANDO_NOS |
| `scheduler/tests/unit/test_transcricao.py`, `test_estagio_do_lead.py`, `test_classifica_estagios.py` | modificar | casos novos |
| `scheduler/tests/integration/058-handoff-do-bot-no-crm.md` | criar | roteiro de dev com os casos de prod |
| `docs/work/prd/057-crm-de-leads.md` | modificar | §5.2 e §5.3 apontam para este PRD |

---

## 8. Testes

Unitários (puros): entrega pendente vira AGUARDANDO_NOS com motivo; fala humana
depois da entrega desliga o sinal; fala do SISTEMA não desliga; derruba
NAO_AGENDOU/MODELO; não derruba MANUAL nem NAO_E_LEAD; CANCELOU cede quando a
entrega é posterior ao horário; AGENDOU não cede; o job não chama o desfecho
com entrega pendente; `autor` lido do MessageEvents.

Dev (roteiro 058), conversas fictícias na Essência de dev que reproduzem os
casos de prod:

| Caso de prod | Semeadura em dev | Esperado |
|---|---|---|
| Nobre 09/11: handoff, ninguém assumiu, veredito NAO_AGENDOU gravado | sessão HANDOFF/HUMAN_PENDING com tarefa, aviso do bot por último, lead com `stage=NAO_AGENDOU`/MODELO | `AGUARDANDO_NOS`/REGRA com motivo, 0 chamadas de desfecho |
| Essência 17/11: handoff e a atendente respondeu no dia seguinte | idem + OUTBOUND `autor: HUMANO` depois | `EM_ANDAMENTO` |
| Nobre 06/11: handoff, atendente respondeu, lead sumiu há 16 d | idem, datas antigas | `SUMIU` (desfecho pode rodar) |
| Essência 15/11: handoff e o lead escreveu de novo | INBOUND por último | `AGUARDANDO_NOS` (regra de sempre) |
| Lembrete do sistema depois do handoff | OUTBOUND `metadata.origem` depois do aviso | `AGUARDANDO_NOS` |
| Tarefa fechada no painel | bloco COOLDOWN sem `pausado_por` | `EM_ANDAMENTO`/`SUMIU`, não AGUARDANDO_NOS |

---

## 9. Critérios de aceite

- [ ] Lead com handoff pendente aparece em `/crm` como AGUARDANDO_NOS com o
  motivo e a data da entrega.
- [ ] Nenhuma chamada de desfecho para lead com entrega pendente.
- [ ] Resposta humana depois da entrega devolve a regra normal; resposta do
  sistema não.
- [x] pytest, vitest, lint e build verdes; dryRun em dev com os seis casos.
- [x] Em prod, o lead da Nobre sai de NAO_AGENDOU para AGUARDANDO_NOS na
  primeira rodada (conferido no dryRun de 23/11 antes da rodada real).

---

## 10. Referências

- PRD 057 (§5.2, §5.3, revisão de 22/11) e roteiro `057-crm-de-leads.md`.
- PRD 020 §3.2-3.6 (bloco `atendimento`, tarefas, retomada).
- PRD 034 (autoria: BOT, HUMANO, SISTEMA).

## Status

- [x] PRD: 22/11/2026
- [x] Spec: `docs/work/spec/058-handoff-do-bot-no-crm.md` (22/11/2026)
- [x] Implementado em dev: 22/11/2026 (layer 210; smoke 9/9 com os seis casos de prod reproduzidos; pytest 2611, vitest, lint e build verdes)
- [x] Implementado em prod: 23/11/2026 (layer 166). DryRun antes da rodada real: das 25 mudanças previstas, 4 linhas vieram do 058 em 2 telefones (cada um com duas linhas de lead): o lead da Nobre de 09/11 (NAO_AGENDOU -> AGUARDANDO_NOS, o caso que motivou o PRD) e um lead da Essência que cancelou em 22/11, voltou a falar em 23/11, o bot entregou e ninguém assumiu (CANCELOU -> AGUARDANDO_NOS, regra 5.1). Nenhuma das 11 entregas com resposta humana mudou. Rodada real: 28 mudanças, 11 chamadas ao modelo, 0 erros; segundo dryRun sem mudança do 058.
