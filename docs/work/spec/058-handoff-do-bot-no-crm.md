# Spec - 058 Handoff do bot no CRM

> Gerado na fase **Spec** em 22/11/2026. PRD de origem: `prd/058-handoff-do-bot-no-crm.md`.

## 1. Resumo

Três camadas, todas no scheduler: a transcrição passa a carregar o autor do
OUTBOUND; as regras puras ganham o sinal "entrega do bot pendente" e o usam em
três pontos de `decide`; o job lê as sessões da clínica em lote, monta o sinal
e pula o desfecho do modelo enquanto a entrega estiver pendente. No painel só
muda a descrição do chip. Sem migração, sem endpoint novo.

Ordem: 2 → 3 → 4 → 5 → 6. Cada tarefa fecha com pytest verde.

## 2. `transcricao.py`

- `Mensagem` ganha `autor: Optional[str] = None` (último campo, com default:
  os testes e o classificador constroem `Mensagem(de, em, texto)`).
- `ultimas_mensagens`: `autor=autor_da_mensagem(item)` (None para INBOUND).
- `resumo` devolve também `ultima_fala_humana_em`: `em` da última mensagem com
  `autor == HUMANO`, ou None.

## 3. `estagio_do_lead.py`

- `Sinais`: `bot_entregou_em: Optional[datetime] = None` e
  `ultima_fala_humana_em: Optional[datetime] = None`.
- `entrega_pendente(s) -> bool` (público, o job usa para pular o desfecho).
- `_a_bola_esta_conosco(s, marco)`: `_lead_falou_depois(s, marco)` ou entrega
  pendente com `bot_entregou_em > marco`. `_pela_agenda` usa isso no lugar de
  `_lead_falou_depois`.
- `decide`: o bloco de NAO_AGENDOU/MODELO só mantém o veredito se **não** há
  mensagem nova **e não** há entrega pendente. NAO_E_LEAD segue como está.
- `_pela_conversa`: antes de olhar a direção, `if entrega_pendente(s): return
  Decisao(AGUARDANDO_NOS, REGRA, "bot pediu ajuda em {dd/mm} e ninguém assumiu")`.
  Vale também sem transcrição (sessão existe, eventos venceram): a entrega é
  prova de conversa.
- Docstring do módulo: parágrafo "Entrega do bot".

## 4. `classifica_estagios.py`

- `_tabela_de_sessoes()` (lazy, `CONVERSATION_SESSIONS_TABLE`), passada por
  `handler` para `processa_clinica(db, tabela_eventos, tabela_sessoes, ...)`.
- `processa_clinica`: `sessoes = sessoes_por_telefone(tabela_sessoes, clinic_id,
  [v for lead in leads for v in variantes_do_numero(lead.phone)])`; por lead,
  `sessao = next((sessoes.get(v) for v in variantes if sessoes.get(v)), None)`.
- `_entregue_em(sessao, clinic, agora)`: `aguarda_especialista(sessao, agora_epoch)`
  e `bloco["entregue_em"]` → datetime no fuso da clínica; senão None.
- `_sinais(lead, mensagens, chat, agendamentos, clinic, sessao, agora)` preenche
  os dois campos novos.
- `_pergunta_ao_modelo(..., sinais)`: `if ... and not estagio.entrega_pendente(sinais)
  and precisa_de_desfecho(...)`.
- Testes: `roda()` recebe `sessoes={}` e faz `mock.patch.object(job,
  "sessoes_por_telefone", return_value=sessoes)`.

## 5. `sls/functions/lead/interface.yml`

ClassificaLeads: statement `dynamodb:BatchGetItem` em
`table/${resourcePrefix}-conversation-sessions`. Sem recurso novo no stack.

## 6. Frontend

`estagios.ts`: AGUARDANDO_NOS → "A última mensagem é do lead, ou o bot pediu
ajuda e ninguém assumiu."

## 7. Testes

- `test_transcricao.py`: item OUTBOUND com `metadata.autor = HUMANO` → `autor`
  HUMANO; com `providerMessageId` → BOT; `metadata.origem` → SISTEMA; resumo
  com `ultima_fala_humana_em`.
- `test_estagio_do_lead.py`: oito casos da seção 8 do PRD.
- `test_classifica_estagios.py`: sessão HANDOFF pendente → AGUARDANDO_NOS com
  motivo e `desfecho` não chamado; sessão com fala humana depois → regra normal
  (SUMIU + desfecho chamado); variante do telefone casa na sessão; sem sessão
  nada muda.

## 8. Roteiro em dev

`scheduler/tests/integration/058-handoff-do-bot-no-crm.md` + script
`smoke_058_dev.py` (scratchpad): semeia seis conversas fictícias na Essência de
dev (telefones `5511999990061..66`), grava as sessões com o bloco
`atendimento` certo, roda a Lambda (dryRun e real), confere `stage`,
`stage_reason`, `chamadas_modelo` e limpa.

## Autorrevisão

- `Mensagem` com default no fim: sem quebra em quem constrói posicional.
- `aguarda_especialista` exige estado com pessoa: sessão vencida sem tarefa não
  gera sinal (decidido no PRD, fora do escopo).
- Comparação `ultima_fala_humana_em < bot_entregou_em`: ambos aware (UTC e fuso
  da clínica); Python compara por instante.
- A sessão é lida por `sessoes_por_telefone`, que já engole falha do batch_get
  (log e segue): uma clínica sem tabela não derruba o job.
