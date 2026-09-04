# Onde paramos — branch `feat/eval-e-economia-de-token`

Trabalho de 03/09/2026. Três dos cinco itens entregues; dois parados esperando
crédito da Anthropic, **de propósito**.

## A regra que ordena o resto

Os itens 2 e 4 mudam comportamento do agente. Nenhum dos dois se aprova no olho:
os dois passam pelo eval, e a condição é **I1 e I2 não podem piorar**.

Foi por isso que o eval veio primeiro. Todo buraco de 02-03/09 apareceu porque
alguém mandou mensagem no WhatsApp e leu log depois — quatro vezes, com a suíte
unitária verde nas quatro.

## Entregue

| Commit | O quê |
|---|---|
| `0334333` | Eval de fluxo + prompt caching |
| `92dd7e9` | Testes reorganizados por comportamento |

**Eval** (`tests/evaluation/eval_fluxo_agente.py`) — replaya 39 conversas reais
(226 turnos, anonimizadas, em `corpus/conversas.json`) pelo agente de verdade,
com tools mockadas e modelo real. Quatro invariantes:

- `I1` agenda sem respaldo — **defeito**
- `I2` fato sem consulta — **defeito**
- `I3` bloqueio disparado — **custo** da rede de segurança
- `I4` fuga pela `sem_consulta_necessaria` — **custo**

Ele **recusa dar nota** quando não mediu (erro de API, zero token): imprime
`NOTA INVÁLIDA`, não grava e sai com código 1. A primeira versão reportou
"0 violações" com a API fora, porque o agente trata o erro e responde "estou com
dificuldades" — o que de fora parece turno normal.

**Caching** — `cache_control` no último bloco de system, que pela ordem de
render (`tools` → `system` → `messages`) cobre tools + system. Exigiu tirar o
bloco `DADOS CONSULTADOS AGORA` de dentro do system prompt: o conteúdo muda a
cada mensagem e um byte volátil no prefixo invalida tudo depois dele. Há teste
prendendo o invariante.

## Parado — item 2: consolidar o prompt

Meta: cortar ~30% dos 13.705 chars mantendo comportamento.

A redundância mapeada: a regra "fato vem de tool" aparece em **quatro seções**
com fraseados diferentes (`ANTES DE RESPONDER, DECIDA`, `DE ONDE VÊM OS FATOS`,
`O QUE VOCÊ NUNCA FAZ` item 1, e por etapa em `COMO CONDUZIR A CONVERSA`). São
28 regras "nunca" no total. Não é só token: fraseado divergente é onde o modelo
escorregou duas vezes em 03/09.

O corte é escrito como script com dry-run, no padrão dos outros
(`prompt_orquestrador.py`, `prompt_faq_tool.py`), e **só se aplica depois de o
eval aprovar**.

## Sugestão para depois — item 4: modelo para Haiku 4.5

**Cancelado em 04/09 por decisão do André.** O Sonnet 5 fica. Fica registrado
aqui com a medição já feita, para quem retomar não precisar remedir.

`DEFAULT_MODEL` em `src/services/anthropic_service.py:12`. Fonte única — é a
única ocorrência de model id no repositório.

| | Sonnet 5 (hoje) | Haiku 4.5 |
|---|---|---|
| Preço /MTok | $3 / $15 | **$1 / $5** |
| Mínimo cacheável | 1.024 tokens | **4.096 tokens** |
| Contexto | 1M | 200K |
| `output_config.effort` | aceita | **erra** (não usamos hoje) |

**O risco de cache já foi medido e está descartado** (`count_tokens`, 04/09):

| Modelo | Prefixo (tools + system) | Mínimo | Cacheia? |
|---|---|---|---|
| Sonnet 5 | 9.659 tokens | 1.024 | sim |
| Haiku 4.5 | 7.490 tokens | 4.096 | sim, 83% de folga |

O Haiku também tokeniza o mesmo texto em 22% menos tokens, então a economia vai
além do preço por token. Uma rodada de eval nele custaria ~US$ 1,55 contra
~US$ 4,70 no Sonnet.

**O que falta é só medir o comportamento.** Haiku é menos capaz, e todo o
trabalho de 02-03/09 foi contra um modelo que inventa fato — é exatamente o que
o eval existe para decidir. Sequência: `eval --nome haiku` e
`--comparar base-v2 haiku`; se I1 e I2 não piorarem, a troca se aprova sozinha.

## Sequência para retomar

```sh
cd scheduler

# 1. baseline com o que está em produção hoje
python -X utf8 tests/evaluation/eval_fluxo_agente.py --nome baseline

# 2. cortar o prompt, medir
python -X utf8 tests/evaluation/eval_fluxo_agente.py --nome prompt-curto
python -X utf8 tests/evaluation/eval_fluxo_agente.py --comparar baseline prompt-curto

# 3. trocar o modelo, medir
python -X utf8 tests/evaluation/eval_fluxo_agente.py --nome haiku
python -X utf8 tests/evaluation/eval_fluxo_agente.py --comparar prompt-curto haiku
```

Comece com `--conversas 5` para conferir a mecânica antes de gastar os 226
turnos. A chave sai do SSM sozinha (`/prod/ANTHROPIC_API_KEY`).

O `--comparar` já imprime a variação de `tokens_in`, `tokens_out` e
`chamadas_modelo` — é onde o ganho do caching aparece, junto com
`aproveitamento de cache` no resumo de cada execução.

## Achados de 03/09 que não viraram tarefa

Encontrados olhando log, fora do escopo desta branch:

1. **Cron de lembretes desligado desde 01/02/2026** (commit `3615b37`,
   *"disable reminder cron until ready for testing"*). Regra do EventBridge
   `DISABLED` em dev e prod; `enabled: false` está commitado em
   `sls/functions/reminder/interface.yml`. Sete meses. Decisão de produto
   pendente — não ligar sem avaliar.
2. **Não existe monitoramento.** O crédito acabou e o bot ficou fora do ar para
   clientes reais da `clinicadorods-da7b62` (que não está em piloto); o sinal
   foi alguém testando outra coisa. Mesma lacuna do cron. Falta alarme de erro
   nas Lambdas e de invocação-zero nos agendados.
3. **`DailyReportSender` rodou 2× em 12h** para um cron diário. Não investigado;
   se o relatório chega duplicado na clínica, é por aí.
4. **`CLAUDE.md` documenta `--aws-profile traffic-manager`**, que não existe
   nesta máquina — o perfil real é `dev-andre`. O comando da doc falha.
5. **Preço do Sonnet 5 subiu em 01/09** — o promocional ($2/$10) valia até
   2026-08-31; agora é $3/$15. Contribuiu para o crédito acabar mais rápido do
   que o histórico sugeria.
