# 059 - Cancelamento pela conversa: o bot cancela e responde com o texto da clínica

Partes A e B do PRD 059. Quando a paciente pede para cancelar ou diz que não
vai, o bot cancela na conversa (também em resposta ao lembrete, onde antes só
mandava o link), e a resposta é o texto da clínica com o convite a remarcar
pelo site. O desfecho segue o PRD 054 (menos de 24 h é falta).

## Pré-requisitos

Os mesmos dos roteiros anteriores (`API`, `KEY`). Sem migração. Os templates
`CANCELADO_PELA_CONVERSA` e `CANCELADO_PELA_CONVERSA_LINK` são opcionais: sem
eles vale o texto padrão do código.

Semear em dev: `smoke_059_dev.py` (scratchpad da sessão), na Premium de dev,
com três telefones fictícios (`5511999990071..73`). O domínio da clínica é
setado só durante os casos 2 e 3 e zerado no fim. `--limpa` apaga paciente,
agendamentos, sessão e eventos semeados.

## Casos

| # | Caso | Semeadura | Esperado |
|---|---|---|---|
| 1 | Bot ativo, fora do lembrete, clínica sem domínio: "preciso cancelar, não vou conseguir ir" | sessão em 5 dias | `CANCELLED` sem pergunta; resposta começa com "Obrigada por nos avisar", sem link, convida a remarcar por aqui |
| 2 | Lembrete vivo, com domínio: "não vou conseguir ir amanhã, imprevisto" | sessão amanhã, bloco `lembrete` na sessão | fora da agenda (`CANCELLED` ou `NO_SHOW` pela antecedência); resposta com o texto da clínica e o link |
| 3 | Lembrete vivo, com domínio: "gostaria de remarcar" | idem | nada cancelado; o bot manda o link; sem o texto de cancelamento |
| 4 | Tool de cancelar devolve erro | unitário | a fala do modelo sai; a confirmação não |
| 5 | Prod | conferir uma conversa real em cada clínica | status e texto |

## Resultado

**Dev, 23/11/2026** (layer 211, `smoke_059_dev.py`): casos 1 a 3 ok, 8 de 8
asserções. Caso 1: `CANCELLED` sem pergunta e texto sem link ("Quando quiser
remarcar, é só me chamar por aqui"). Caso 2: `CANCELLED` (mais de 24 h até a
abertura da agenda do dia) e texto com o link do domínio de teste. Caso 3:
agendamento intacto, bot mandou o link para remarcar. Caso 4 coberto por
`test_cancelamento_pela_conversa.py`. Dados de dev apagados com `--limpa` e
domínio da Premium de dev zerado. Prod (caso 5): pendente.
