# 057 - CRM de leads: estágio por lead, classificador diário, fila `/crm`

Cada lead ganha um `stage` gravado pela Lambda `ClassificaLeads` (7h BRT): fato
da agenda (PRD 054: o agendamento mais recente que não é remarcação) vence tudo;
depois NAO_E_LEAD, MANUAL, veredito do modelo e, por fim, as regras de conversa
lidas do MessageEvents (AGUARDANDO_NOS, SUMIU, INICIADA_SEM_RESPOSTA,
SEM_CONVERSA, EM_ANDAMENTO). O modelo (Haiku 4.5, temp 0, teto 200/execução)
só entra na triagem "é lead?" (WhatsApp, 3 msgs) e no desfecho "por que não
agendou" (parado > `clinics.crm_dias_parado`, padrão 7). Toda mudança vira linha
em `lead_stage_events`. A recepção (STAFF) vê e corrige em `/crm`; o disparo é
ADMIN. `POST /send` com `campanha` passou a recusar contato silenciado (PRD 039).

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
API=https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev
KEY=$(get /dev/SCHEDULER_API_KEY)          # ADMIN (chave mestra)
C=<clinic_id>
```

Migração antes do deploy: `python src/scripts/setup_database.py` com `RDS_*`
de `/dev/SUPABASE_DB_*` (colunas `stage*`, `triagem_feita_em`,
`desfecho_tentado_em`, `ultima_mensagem_*` em `leads`; `clinics.crm_dias_parado`;
tabela `lead_stage_events`). Depois do primeiro deploy, retenção de 90 dias nos
log groups `ClassificaLeads` e `AtualizaEstagioDoLead` (`aws logs
put-retention-policy`, só depois da primeira invocação).

Semear conversas em dev: itens `MSG#<iso>#<id>` no MessageEvents com
`direction` INBOUND/OUTBOUND, `content`, `createdAt` (ver
`smoke_057_dev.py` do scratchpad da sessão; o script limpa o que semeou de
rodadas anteriores pelo prefixo `smoke057-`).

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | `aws lambda invoke ... ClassificaLeads --payload '{"clinicId": "$C", "dryRun": true}'` | `por_estagio` somando `leads`; nada gravado |
| 2 | mesma chamada sem `dryRun` | `stage*` gravados; lead com conversa parada > 7 d e "achou caro" → `NAO_AGENDOU`/`MODELO` com motivo; lead com sessão na agenda → `AGENDOU`/`REGRA` mesmo com conversa parada |
| 3 | lead `source=whatsapp` com 3 msgs de fornecedor | `NAO_E_LEAD`/`MODELO`, `triagem_feita_em` preenchido |
| 4 | `SELECT * FROM lead_stage_events WHERE lead_id=...` | uma linha por mudança, com `fonte` e `motivo` |
| 5 | rodar de novo (dryRun) | `mudaram: 0`, `chamadas_modelo: 0` |
| 6 | `GET clinics/$C/leads?stage=NAO_AGENDOU&orderBy=dias_parado` | só o estágio pedido; `totals.por_estagio` com todos; `dias_parado` e `stage_reason` na linha; `source=` combina |
| 7 | `PATCH clinics/$C/leads/{id}/stage {"stage":"EM_ANDAMENTO","reason":"..."}` | 200, `stage_source=MANUAL`; `AGENDOU` → 400 "vem da agenda"; desconhecido → 400; outro clinic → 404; sem papel → 403 |
| 7c | rodar o job depois do PATCH | MANUAL sobrevive; no lead com sessão na agenda a agenda reverte (fato vence) |
| 8 | `POST send` com `campanha` para contato em `contatos_silenciados` | 409 `motivo: silenciado`; sem `campanha` passa |
| 9 | `POST send` com `campanha` para um lead da fila (clínica com bot ligado e z-api) | 200 `SENT` |
| 10 | Browser `/crm` (ADMIN e STAFF) | chips com contagem e filtro; motivo e ícone da fonte; correção inline salva e some do filtro; AGENDOU sem botão; seleção + "Disparar mensagem" só para ADMIN; modal lista os leads; sem erro no console |
| 12 | lead com `CANCELLED` e mensagem dele depois do horário (dryRun) | `AGUARDANDO_NOS`/`REGRA`, não CANCELOU; mensagem antes do horário mantém CANCELOU |
| 13 | lead só com mensagens nossas há mais de N dias | `SUMIU`/`REGRA`, sem chamada ao modelo |
| 14 | lead em AGUARDANDO_NOS parado há mais de N dias com "ok, obrigada" no fim | modelo roda; `NAO_AGENDOU`/`MODELO` com motivo ou `desfecho_tentado_em` preenchido |
| 11 | Backfill em prod | dryRun por clínica, distribuição para o André, depois real (não feito nesta entrega) |

## Resultado

**Dev, 21/11/2026** (migração aplicada 2x sem erro; `serverless deploy --stage
dev` layers 206 e 207; PR #243):

- dryRun geral: Premium 61 leads (AGUARDANDO_NOS 22, SUMIU 18, CANCELOU 7,
  AGENDOU 6, NAO_E_LEAD 3, NAO_AGENDOU 3, SEM_CONVERSA 2; 50 chamadas ao
  modelo), Rods 4, Essência 6. É o teste de carga: 71 leads em uma invocação.
- Smoke por script na Essência (`smoke_057_dev.py`), 16 de 16: conversas
  semeadas para o contato do André (autorizado), para "Paula Teste 057"
  (`5511999990058`, site) e para um fornecedor fictício (`5511999990057`,
  WhatsApp).
  - 1 → dryRun não grava. 2 → André `AGENDOU`/`REGRA` (tem sessão confirmada
    na Essência de dev; a agenda vence a conversa parada); Paula
    `NAO_AGENDOU`/`MODELO`, motivo "Achou caro, vai pensar",
    `desfecho_tentado_em` preenchido. 3 → fornecedor `NAO_E_LEAD`/`MODELO`,
    motivo "Fornecedor oferecendo produtos e serviços". 4 → evento
    `(None → NAO_AGENDOU, MODELO, motivo)`. 5 → `mudaram 0`.
  - 6 → `GET /leads?stage=NAO_AGENDOU&orderBy=dias_parado` filtra, traz
    `por_estagio` e `dias_parado = 11`; `source=whatsapp&stage=NAO_E_LEAD` acha
    o fornecedor.
  - 7 → PATCH grava MANUAL; `AGENDOU` → 400; PATCH no André aceita (200) e o job
    seguinte devolve `AGENDOU`/`REGRA` (a agenda é quem reverte, como o PRD
    manda; a tela nem oferece o botão nesse caso). 7c → o MANUAL da Paula
    sobrevive ao job.
  - 8 → `/send` com campanha para silenciado: 409 `silenciado`.
  - 9 → `/send` com campanha para o André pela Premium (bot ligado): 200
    `SENT`, mensagem recebida no WhatsApp. A Essência de dev está com o bot
    pausado e recusa com `bot_da_clinica_pausado`, como esperado.
- Caso 10 (Playwright, painel local com proxy do Vite para dev, sessão ADMIN e
  STAFF), 13 de 13. Achado e corrigido no caminho: o popover absoluto era
  cortado pelo `overflow-x` da tabela; virou linha de correção inline abaixo do
  lead. Também: lead que só existe no espelho do z-api passou a gravar a data
  do espelho em `ultima_mensagem_em` (antes ficava "Sumiu" com "parado há -").
- Limpeza: os leads e eventos semeados ficam em dev com prefixo `smoke057-`;
  a correção manual da Paula fica como está (não afeta nada).
- Prod: não feito. Precisa de migração, deploy e dryRun por clínica com a
  distribuição para o André antes do real (caso 11).

**Dev, 22/11/2026** (revisão da classificação; `serverless deploy --stage dev`
layers 208 e 209): casos 12 a 14 cobertos por teste unitário e conferidos pelo
dryRun na Premium. Antes: AGUARDANDO_NOS 22, NAO_AGENDOU 3. Depois:
AGUARDANDO_NOS 11, NAO_AGENDOU 14, 22 chamadas ao modelo, 0 descartes; os
outros estágios iguais (SUMIU 18, CANCELOU 7, AGENDOU 6, NAO_E_LEAD 3,
SEM_CONVERSA 2). Os 11 que mudaram eram "ok, obrigada", "não obrigado", fechou
em outro lugar, achou caro, mora longe, contraindicação e um que negou o
cadastro: nenhum deles era pergunta sem resposta. O dryRun passou a logar uma
linha por mudança (`lead <id> <antes> -> <depois> (<fonte>: <motivo>)`), sem
telefone, para a conferência em prod ser por log. Rods e Essência: `mudaram 0`.

**Prod, 22/11/2026** (autorizado pelo André; migração idempotente 220/220;
`serverless deploy --stage prod` layer 164, depois 165 com a correção do
relatório; PR #243 mergeado antes, correção no PR seguinte):

- Caso 11. dryRun por clínica, com o log de uma linha por mudança lido antes
  do real. Achado no caminho: na Essência o teto de 200 chamadas estourou e os
  245 leads que ficaram para a próxima noite saíram como `descartes`, com
  `chamadas_modelo` zerado. Corrigido: `adiados` separado de `descartes`, a
  contagem de chamadas sobrevive ao teto, e o payload aceita
  `maxChamadasModelo` para o backfill. Repetido com 900: 431 chamadas, 0
  adiados.
- Rodada real (mesma distribuição do dryRun):

  | Clínica | Leads | Distribuição | Modelo |
  |---|---|---|---|
  | Essência | 746 | AGENDOU 234, SUMIU 213, EM_ANDAMENTO 64, NAO_AGENDOU 60, NAO_E_LEAD 44, CANCELOU 36, AGUARDANDO_NOS 35, FALTOU 34, INICIADA_SEM_RESPOSTA 16, SEM_CONVERSA 10 | 431 |
  | Nobre | 230 | SUMIU 136, AGENDOU 34, EM_ANDAMENTO 21, SEM_CONVERSA 9, CANCELOU 8, NAO_E_LEAD 8, NAO_AGENDOU 8, AGUARDANDO_NOS 4, FALTOU 2 | 98 |
  | Premium | 63 | SEM_CONVERSA 45, CANCELOU 10, AGENDOU 3, AGUARDANDO_NOS 2, SUMIU 2, NAO_E_LEAD 1 | 8 |
  | Rods | 2 | SEM_CONVERSA 2 | 0 |

- Conferido no banco: 1.041 leads, nenhum sem `stage` (REGRA 898, MODELO 121,
  HISTORICO 22); 1.281 linhas em `lead_stage_events`. dryRun seguinte na Nobre:
  `mudaram 0`, `chamadas_modelo 0`.
- Vereditos lidos no log: NAO_E_LEAD são fornecedores, cobrança de aluguel,
  conversa interna da equipe, spam; NAO_AGENDOU são recusa, "só pesquisando",
  horário indisponível. Dois leads da Nobre vindos do site eram candidatos a
  emprego e saíram como NAO_AGENDOU, não NAO_E_LEAD, porque a triagem só roda
  para origem WhatsApp. Correção manual na tela resolve; se repetir, abrir a
  triagem para o site.
- Retenção de 90 dias nos log groups `ClassificaLeads` e `AtualizaEstagioDoLead`
  (este criado por um PATCH inválido, 400, sem escrita).
- Premium em prod tem 45 de 63 em SEM_CONVERSA: leads antigos, sem evento nos
  60 dias e sem espelho do z-api (a Premium de prod não tem instância). É o
  esperado.
