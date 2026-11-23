# 060 - Sessão futura pergunta "remarcar ou mais uma?" e link direto para "Meus agendamentos"

Revisão do PRD 056. Criar um agendamento (site, bot ou painel) para quem já
tem sessão `CONFIRMED` futura em **outro mês** deixa de passar em silêncio:
responde 409 `OTHER_MONTH_APPOINTMENT` com a sessão existente, e a tela (ou a
tool do bot) pergunta "remarcar essa sessão ou marcar mais uma?". Repetir com
`remarcarExistente: true` faz a troca da 056 (a existente sai pelo desfecho da
054 e a nova nasce vinculada); com `maisUma: true` cria a segunda. Sem ADMIN
nem motivo. O mesmo mês continua exatamente como no 056.

O site ganha `?meus=1`, que abre "Meus agendamentos" direto. O bloco do
lembrete (PRD 059) manda esse link para remarcar; o popover da agenda tem
"Copiar link de remarcação".

## Pré-requisitos

Os mesmos dos roteiros anteriores (`API`, `KEY`, `BKEY`). Sem migração.

**Nenhum caso deste roteiro pode passar pelo envio de WhatsApp com número
inventado** (lição do 059: o z-api de dev envia de verdade). Por isso o smoke
de dev (`smoke_060_dev.py`, scratchpad da sessão) usa só o painel
(`POST appointments`, que não envia nada) e, no site, só o 401 sem token. Os
caminhos do site com token e o do bot ficam cobertos por testes unitários e
pela primeira conversa real em prod.

## Casos

| # | Porta | Chamada | Esperado |
|---|---|---|---|
| 1 | Painel | criar no mês A para um número sem sessão | 201 |
| 2 | Painel | criar no mês B (outro mês) sem flag | 409 `OTHER_MONTH_APPOINTMENT`, `existing` com `id/date/time/areas/patientName`; nada criado nem cancelado |
| 3 | Painel | o mesmo com `maisUma: true` | 201; a do mês A continua `CONFIRMED`; a nova sem `rescheduled_from_id` nem `second_in_month_by` |
| 4 | Painel | número com sessão só no mês B; criar no mês A com `remarcarExistente: true` | 201; a do mês B vira `CANCELLED` (ou `NO_SHOW` se < 24 h) com `rescheduled_to_id` = nova; nova com `rescheduled_from_id` |
| 5 | Painel | criar em OUTRA data do mesmo mês da sessão existente | 409 `SAME_MONTH_APPOINTMENT` (056 intacta) |
| 6 | Site | criar sem `token` | 401, nenhum envio |
| 7 | Site | com token, criar em outro mês sem flag | 409 `OTHER_MONTH_APPOINTMENT`, `existing` sem nome, `message` cita "Meus agendamentos" (unitário `test_carrinho_do_site.py`; em dev só com número combinado) |
| 8 | Site | diálogo "Você já tem uma sessão marcada": Remarcar / Marcar mais uma / Voltar | vitest `Booking.test.tsx` |
| 9 | Site | `https://{dominio}/?meus=1` | abre "Meus agendamentos"; fechar limpa a URL (vitest `BookingChrome.test.tsx`) |
| 10 | Bot | paciente com sessão futura em outro mês pede outra data | tool devolve `ja_tem_sessao_futura` e grava `pergunta_mais_uma` na sessão; `mais_uma=true` só vale depois disso (unitário `test_bot_mesmo_mes.py`) |
| 11 | Bot | bloco do lembrete com domínio | link `?meus=1` (unitário `test_lembrete_sobreposicao.py`) |
| 12 | Painel | popover de agendamento confirmado em clínica com domínio | "Copiar link de remarcação" copia `https://{dominio}/?meus=1` (vitest) |
| 13 | Prod | primeira pergunta real em cada porta | conferir no CloudWatch `[OutroMes]` |

## Resultado

**Dev, 23/11/2026** (scheduler layer 212, `smoke_060_dev.py` na clínica de
teste de dev, só pelo painel): casos 1 a 6 ok, 8 de 8 asserções. Caso 2: 409
`OTHER_MONTH_APPOINTMENT` com `existing` da sessão de novembro, nada criado.
Caso 3: `maisUma` criou a de dezembro e a de novembro continuou, sem vínculo
nem `second_in_month_by`. Caso 4: `remarcarExistente` deixou a de dezembro
`CANCELLED` com `rescheduled_to_id` apontando para a nova, e a nova com
`rescheduled_from_id`. Caso 5: outra data de novembro continuou 409
`SAME_MONTH_APPOINTMENT`. Caso 6: 401 sem token. Dados de dev cancelados pelo
próprio smoke no fim. Casos 7 a 12 cobertos por pytest (2.645, suíte inteira) e vitest
(site 126, painel 728); lint e build dos dois fronts limpos.

Nenhuma mensagem de WhatsApp foi disparada neste smoke.

**Prod, 23/11/2026** (scheduler layer 169, Lambdas atualizadas 19:16 UTC).
Sem smoke em prod de propósito: o caminho do site exige código por WhatsApp e
o do painel criaria agendamento real. Caso 13 fica para a primeira pergunta
real: procurar `[OutroMes]` no CloudWatch do PublicBooking, CreateAppointment
e WhatsAppWebhook. Site e painel sobem pela Vercel no merge do PR #249.
