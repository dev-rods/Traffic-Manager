# PRD — 016 Comparecimento, para a conversão PURCHASE ser verdade

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Registrar se o paciente **compareceu** à sessão, para que a conversion action
`Agendamento Real (Offline)` (`7699541177`, `PURCHASE`) afirme ao Google Ads uma
compra que de fato aconteceu.

Hoje ela envia todo agendamento `CONFIRMED` cuja data já passou. Isso significa
"ninguém cancelou", não "a pessoa veio" — um no-show é indistinguível de uma
sessão realizada, e sobe como compra de `final_price_cents`.

---

## 2. Contexto

Em 03/10/2026 o André decidiu que esta action é **PURCHASE pura**: só sobe quem
confirmou **e compareceu**. O PR #80 entregou a primeira metade (voltou o guard
`appointment_date < CURRENT_DATE`), e deixou a segunda explicitamente em aberto,
porque o dado de presença não existe.

### O que foi medido em produção (clínica da Essência, 03/10/2026)

| Fonte de presença | Situação |
|---|---|
| `appointments.status` | Só `CONFIRMED` e `CANCELLED`. **604 dos 618** CONFIRMED têm data passada e ficam assim para sempre. |
| `patient_session_records` | 23 registros, cobrindo **4%** das 604 sessões passadas. |

Nenhuma das duas serve. O prontuário não é caminho: levar 4% a uma cobertura
útil é mudança de comportamento da clínica, maior do que o problema que
resolveria.

### O padrão dos cancelamentos (80 casos — amostra útil)

| Quando o cancelamento é registrado | Casos |
|---|---|
| Antes da sessão | 33 (41%) |
| No dia da sessão | 26 (32%) |
| Mais de 7 dias depois | 21 (26%) |
| **Entre 1 e 7 dias depois** | **0** |

Duas conclusões que decidem o desenho:

1. **Carência não compra nada.** Uma espera de 0, 1, 2, 3 ou 7 dias após a
   sessão evita exatamente os mesmos 59 cancelamentos (74%), porque a janela de
   1 a 7 dias está vazia. O guard do PR #80 já captura tudo o que uma carência
   capturaria. **Não implementar carência.**
2. **A clínica já marca no-show, tarde e com o nome errado.** Os 26% que chegam
   após 7 dias são faxina retroativa: alguém passa a limpo agendamentos velhos.
   O comportamento existe — falta distingui-lo de um cancelamento antecipado, que
   é coisa diferente (quem cancela com antecedência libera a agenda; quem não
   aparece queima o horário).

---

## 3. Escopo

### Dentro do escopo

- Status `NO_SHOW` em `scheduler.appointments`, distinto de `CANCELLED`.
- Marcar no-show pelo painel, na agenda, para sessões cuja data já passou.
- `_get_pending_conversions` passa a exigir ausência de `NO_SHOW`.
- `NO_SHOW` descoberto **depois** do upload entra no fluxo que hoje zera o valor
  do cancelado (`restate_cancelled_to_zero`).

### Fora do escopo

- **Confirmação ativa de presença.** Exigir que a recepção marque "compareceu"
  em cada sessão colocaria o ônus nas 604 sessões passadas e nas ~90/mês
  seguintes. Adoção baixa levaria o uploader a não enviar nada, que é pior que
  hoje. O desenho é por **exceção**: presença é o padrão, no-show é marcado.
- **Backfill das 604 sessões passadas.** Vale só daqui para frente. O backlog
  atual sobe sob o proxy do PR #80, que é decisão já tomada.
- **O evento de WhatsApp qualificado.** Fica para o PRD 017 — conta no
  agendamento e **inclui** quem cancelou, em conversion action separada.
- **Integração de pagamento** como prova de compra. Não existe hoje e é escopo
  muito maior.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | modificar | Migration idempotente: `NO_SHOW` no CHECK de `appointments.status`; manter o `CREATE TABLE` em sincronia |
| `scheduler/src/functions/appointment/` | modificar | Endpoint para marcar/desmarcar `NO_SHOW`, só para data passada |
| `scheduler/src/services/appointment_service.py` | modificar | Transição de status; `NO_SHOW` **não** deve disparar `record_conversion` nem apagar a linha existente |
| `scheduler/sls/functions/appointment/interface.yml` | modificar | Rota nova — **atenção ao limite do CloudFormation** (452/500) |
| `frontend/src/pages/agenda/` | modificar | Ação de marcar no-show; os 4 estados; distinguir visualmente de cancelado |
| `frontend/src/types/` | modificar | `NO_SHOW` no tipo de status |
| `infra/src/functions/conversions/uploader.py` | modificar | Elegibilidade exige não-`NO_SHOW`; zerar valor passa a cobrir `NO_SHOW` pós-upload |
| `infra/tests/unit/test_conversao_e_retracao.py` | modificar | Travar a regra nova e remover o aviso "não prova presença" quando deixar de ser verdade |

---

## 5. Dependências e riscos

**Dependências**

- PR #78 (transporte via Data Manager) e #80 (guard + PURCHASE) mergeados.
- Deploy do `scheduler` **e** do `infra` — a regra de elegibilidade vive no
  `infra`, o status vive no `scheduler`.
- **Prod está atrás do `setup_database.py`** em um número desconhecido de
  migrations. Já derrubou o uploader em 03/10 (`retracted_at` não existia).
  Reconciliar antes, ou a migration nova entra num schema desconhecido.

**Riscos**

- **Adoção.** Se a recepção não marcar no-show, nada muda: o evento continua
  afirmando compras não verificadas. Diferente de hoje, porém, o sistema passa a
  ter onde registrar — e os 26% de faxina retroativa sugerem que a prática já
  existe. Vale medir a cobertura de `NO_SHOW` após 60 dias antes de confiar no
  evento.
- **A cauda de correção é inerente.** Presença registrada após o upload sempre
  vai existir (26% dos casos chegam 7+ dias depois), e para esses só há zerar o
  valor — a Data Manager não retrata, e a **contagem permanece**. O evento
  PURCHASE nunca será perfeito; será honesto.
- **Limite do CloudFormation.** O `scheduler` está em 452/500 e uma rota custa
  ~6-7 recursos. Cabe, mas aproxima o teto — ver PRD 013.
- **Promover a primária.** Só depois de a cobertura de `NO_SHOW` se provar. Hoje
  a meta `PURCHASE` está `biddable: false`, o que dá folga para acertar antes de
  o bidding depender disso.

---

## 6. Critérios de aceite

- [ ] `NO_SHOW` aceito pelo banco, por migration idempotente, com o
      `CREATE TABLE` em sincronia
- [ ] Painel marca e desmarca no-show, só para sessão com data passada
- [ ] No-show é visualmente distinto de cancelado na agenda
- [ ] `NO_SHOW` não gera conversão nova nem remove a linha de `lead_conversions`
- [ ] Agendamento `NO_SHOW` **não** aparece em `_get_pending_conversions`
- [ ] `NO_SHOW` marcado após o upload tem o valor zerado no Google
- [ ] Teste trava: sessão passada + `NO_SHOW` não é elegível
- [ ] O aviso "não prova presença" sai do `uploader.py` só quando deixar de ser
      verdade — e o teste que o exige é atualizado no mesmo commit
- [ ] Ensaio `validateOnly` em produção antes do envio real

---

## 7. Referências

- `CLAUDE.md` — padrões do projeto
- PR #78 — transporte via Data Manager API
- PR #80 — guard restaurado e PURCHASE pura
- `docs/work/prd/013-limite-do-cloudformation.md` — orçamento de recursos
- `infra/src/services/data_manager_service.py` — por que não existe RETRACTION

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada: `spec/016-comparecimento-e-compra-real.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
