# Débito técnico do Traffic-Manager

> Lista viva. Criada em **09/11/2026** ao fechar o PRD 043.
> Cada item tem o que está faltando, por que ficou de fora e o que destrava.
> Item que virar PRD sai daqui e passa a viver em `prd/`.

Legenda: 🔴 dói hoje · 🟡 dói quando acontecer · ⬜ dívida de manutenção

---

## Produto

| # | Item | Grau | Situação |
|---|---|---|---|
| D1 | **A paciente não é avisada quando a clínica remarca** | 🔴 | Nem o painel nem o backend mandam mensagem ao remarcar, e o lembrete do dia antigo é cancelado (`cancel_reminder`), então nada chega. A recepção avisa por fora, se lembrar. Desde o PRD 043 (09/11/2026) a tela **declara** isso no resumo da alteração, e a presença confirmada volta a Pendente - mas o aviso de verdade não existe. **Merece PRD próprio**, porque mandar a mensagem envolve template, horário de silêncio, pausa do bot e o silêncio declarado do PRD 039. Recomendado como próximo trabalho |
| D2 | **PRD 039 fase 2: relatório de contatos silenciados há muito tempo** | 🟡 | O silêncio não tem prazo por decisão; sem relatório, um número silenciado por engano fica mudo para sempre sem ninguém notar. Tabela `scheduler.contatos_silenciados` já guarda `silenciado_em` e o motivo |
| D3 | **Item `FAILED` na fila de saída é terminal** | 🔴 | Lead cujo primeiro contato falhou fica preso: a fila não tenta de novo, o painel recusa reenviar e a pausa de 24h ainda corre por cima. Receita de recuperação em `project_lead_preso_apos_falha` (chave do rastro `CLINIC#...#PHONE#...`) |
| D4 | **A pausa por instabilidade sobrevive à causa** | 🟡 | Quando o provedor ou a Anthropic falha, a conversa fica pausada pelo prazo cheio mesmo depois de o serviço voltar. Exposto pela pane de 05-06/11/2026 (18 h caladas) |

## Operação e infraestrutura

| # | Item | Grau | Situação |
|---|---|---|---|
| D5 | **`/dev/ASAAS_API_KEY` com a chave errada** | 🟡 | Dev está com a chave de produção da conta nova contra a base de sandbox, e pagamento em dev responde 502. A versão 1 do parâmetro no SSM restaura. Contexto em `project_asaas_conta_nova` |
| D6 | **Nenhum alarme para erro recorrente da Anthropic** | 🔴 | A pane de 05-06/11/2026 só foi descoberta por conversa reclamando. Não há alarme sobre erro repetido do `conversation_agent` |
| D7 | **`CLAUDE.md` manda usar um perfil AWS que não existe** | ⬜ | Os comandos de deploy citam `--aws-profile traffic-manager`; na máquina do André o perfil é `dev-andre`. Todo deploy começa com um erro evitável |
| D8 | **`serverless deploy` sai com código 0 mesmo falhando** | ⬜ | O que prova sucesso é a lista de funções/endpoints no fim da saída. Vale conferir o artefato publicado quando a mudança for sensível (feito no PRD 043) |
| D9 | **Força bruta no login** | 🟡 | `/auth/login` aceita tentativas ilimitadas. Pesa mais desde a primeira conta de recepção |
| D10 | **ADMIN ainda usa a chave compartilhada** | 🟡 | STAFF já tem sessão própria; o ADMIN não. Metade da dívida de autenticação por usuário segue aberta |

## Suspeitas a confirmar

| # | Item | Grau | Situação |
|---|---|---|---|
| D11 | **Envio duplicado em duas conversas da Essência** | 🟡 | Observado ao triar a pane de 05-06/11/2026, não diagnosticado. Precisa de uma leitura de `message-events` pelas duas conversas antes de virar PRD |

---

## Referências

- `docs/work/pendencias-campanhas-google-ads.md` - pendências de Google Ads (lista separada).
- `TASKS_LOG.md` - o que já foi entregue, com o motivo de cada decisão.
