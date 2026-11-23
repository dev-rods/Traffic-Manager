# 058 - Handoff do bot no CRM: pedido de ajuda sem resposta é AGUARDANDO_NOS

Quando o bot entrega a conversa ("vou confirmar com uma especialista") e
nenhuma pessoa da clínica fala depois, o lead fica em `AGUARDANDO_NOS` com o
motivo "bot pediu ajuda em DD/MM e ninguém assumiu". O sinal cruza a sessão
(bloco `atendimento` entregue pelo bot e ainda com pessoa) com o autor das
mensagens no MessageEvents (BOT, HUMANO, SISTEMA). Enquanto pendente, o job não
pergunta o desfecho ao modelo e um `NAO_AGENDOU` do modelo cai. Resposta humana
depois da entrega, tarefa fechada ou "Retomar bot" devolvem a regra de sempre.

## Pré-requisitos

Os mesmos do roteiro 057 (`API`, `KEY`, `C`). Sem migração. O deploy dá à
`ClassificaLeads` `dynamodb:BatchGetItem` na tabela de sessões.

Semear em dev: `smoke_058_dev.py` (scratchpad da sessão) cria seis leads
fictícios na Essência de dev (`5511999990061..66`), os eventos com o autor
certo (BOT = `providerMessageId`; HUMANO = `metadata.autor`; SISTEMA =
`metadata.origem`) e a sessão com o bloco `atendimento` como o webhook grava
depois de um handoff (HANDOFF, tarefa aberta, HUMAN_PENDING). `--limpa` apaga
só o que semeou; `--mantem` deixa para olhar em `/crm`.

## Casos

Cada um reproduz uma conversa real vista em prod em 22/11/2026 (ids e telefones
fora do roteiro de propósito).

| # | Caso de prod reproduzido | Semeadura | Esperado |
|---|---|---|---|
| 1 | Nobre 09/11: pediu data, bot entregou, ninguém assumiu; o CRM tinha gravado `NAO_AGENDOU`/MODELO em 22/11 | pergunta, aviso do bot (BOT) há 13 d, sessão HANDOFF pendente, lead com `stage=NAO_AGENDOU`/MODELO | `AGUARDANDO_NOS`/REGRA, motivo com "ninguém assumiu" e a data da entrega; `desfecho_tentado_em` vazio; evento em `lead_stage_events` |
| 2 | Essência 17/11: handoff e a atendente respondeu pelo celular no dia seguinte | + OUTBOUND HUMANO há 4 d | `EM_ANDAMENTO` |
| 3 | Nobre 06/11: handoff, atendente respondeu, lead nunca mais falou | datas há 16 d | `SUMIU` (ou `NAO_AGENDOU` se o modelo decidir), `desfecho_tentado_em` preenchido |
| 4 | Essência 15/11: handoff e o lead escreveu de novo | INBOUND por último | `AGUARDANDO_NOS`/REGRA |
| 5 | Lembrete do sistema depois do aviso | OUTBOUND com `metadata.origem` por último | `AGUARDANDO_NOS` com o motivo do handoff (sistema não é pessoa) |
| 6 | Tarefa fechada no painel | bloco COOLDOWN sem `pausado_por`, aviso do bot por último há 3 d | `EM_ANDAMENTO`, sem motivo de handoff |
| 7 | Chamadas ao modelo | rodada real | só o caso 3 vai ao desfecho; 1 e 5 não gastam chamada |
| 8 | Idempotência | dryRun depois do real | `mudaram 0`, `chamadas_modelo 0` |
| 9 | Prod | dryRun por clínica antes do real | o lead da Nobre sai de NAO_AGENDOU para AGUARDANDO_NOS; os 11 com resposta humana não mudam |

## Resultado

**Dev, 22/11/2026** (layer 210, `smoke_058_dev.py`): 9/9. Os seis leads
fictícios ficaram na Essência de dev para conferência em `/crm`
(`--limpa` apaga). Distribuição da rodada: AGUARDANDO_NOS 3 (casos 1, 4, 5,
todos com o motivo e a data da entrega no fuso da clínica), EM_ANDAMENTO 2
(casos 2 e 6), SUMIU 1 (caso 3, única chamada ao modelo). Evento
`NAO_AGENDOU → AGUARDANDO_NOS` gravado para o caso 1; segunda rodada
`mudaram 0`. Prod (caso 9): pendente de autorização.
