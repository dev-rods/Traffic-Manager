# PRD — 017 "Agendou pelo WhatsApp", a conversão que vai guiar o lance

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Criar uma **segunda** conversion action offline — "Agendou pelo WhatsApp" — que
conta **todo agendamento vindo de anúncio, independente do que acontece depois**:
confirmado, cancelado ou falta.

Ela nasce **secundária**, acumula 4-6 semanas de histórico, e só então é
promovida a biddable — **despromovendo a `Lead - Formulário`**, não somando a
ela.

A action de compra (`Agendamento Real (Offline)`, `7699541177`) permanece
**secundária e indefinidamente**: ela mede receita, não guia lance.

Um evento otimiza, o outro mede.

---

## 2. Contexto

### 2.1 Hoje a campanha aprende com UM sinal, e ele é fraco

A campanha `[Gestor]Depilacao_primeira_jardins` (`MAXIMIZE_CONVERSIONS` com tCPA
de R$78) declara duas metas biddable, e apenas uma produz:

| Meta biddable | Ação | Volume |
|---|---|---|
| `SUBMIT_LEAD_FORM` | `Lead - Formulário` | ~35/mês |
| `REQUEST_QUOTE` | `Lead - Whatsapp` | **0** — morreu em 12/04/2026 |

A `Lead - Whatsapp` foi `REMOVED` em 04/10/2026 e `REQUEST_QUOTE` deixou de ser
biddable. Então o Smart Bidding otimiza com **uma única ação**: uma tag de
formulário na landing page. Se ela quebrar, o bidding fica cego — foi o que
aconteceu com a de WhatsApp, invisível por 6 meses porque a `Lead jardins`
duplicada mantinha o total parecendo saudável.

### 2.2 Preencher formulário é intenção; agendar é compromisso

O evento de agendamento é um sinal de **qualidade melhor**: tem data, serviço e
preço. O formulário é o topo do funil.

### 2.3 Dimensionamento medido (04/10/2026)

**Ressalva que vale mais que os números: a amostra é de UM mês útil.** O rastreio
da LP entrou em 05/08/2026 e a cadeia de conversão só passou a funcionar em
27/09. Agosto tem 3 conversões; setembro é o primeiro mês com tudo no ar.

Por mês da **sessão** — o único denominador não contaminado (`created_at` está
poluído por um import de 520 agendamentos em setembro):

| Mês | Agendou | Compra (confirmados) |
|---|---|---|
| ago | 3 | 3 |
| **set** | **19** | **12** |
| out (parcial, 4 dias) | 7 | 5 |

```
Lead - Formulario (unico biddable vivo)   ~35/mes
Agendou pelo WhatsApp                     ~19/mes
Compra (confirmado + sessao passada)      ~12/mes
```

O funil, que é o número mais sólido:

```
83 leads com gclid -> 24 agendaram (29%) -> 16 confirmados (19% dos leads)
```

Dos 30 agendamentos, **10 caem** (33%). "Agendou" é **~1,5x** o volume de
"Compra".

### 2.4 Por que o de agendamento, e não o de compra, guia o lance

- **Volume.** Nenhum dos dois chega aos ~30/mês que o tCPA pede para aprender
  bem. O de agendamento chega mais perto.
- **Chega mais cedo.** Carimbo na data do agendamento, não da sessão: pior caso
  medido de **41 dias** do clique, contra **69** da compra. Mais folga na janela
  de 90 dias, e aprendizado mais rápido.
- **Cancelamento é ruído inerente, não erro.** Quem marcou e desmarcou agendou
  de verdade — o lead era qualificado. É a semântica que dissolve o problema que
  consumiu o dia 03/10: **este evento não precisa de retratação nem de zerar
  valor**, e a Data Manager API não oferece retratação de todo jeito.
- **A compra depende de adoção de `NO_SHOW`.** Com ~12/mês e a presença ainda
  por se provar (PRD 016), pedir que ela guie o leilão é pedir demais de pouco
  dado.

### 2.5 A armadilha: não deixar dois biddable

Um lead preenche o formulário (conversão 1) e depois agenda (conversão 2) —
**mesma jornada, duas contagens**. O tCPA de R$78 viraria efetivamente R$39 por
"conversão", e o algoritmo pagaria mais caro do que se pediu.

É o mesmo defeito que a `Lead jardins` duplicada causava nos relatórios, e que
mascarou por 6 meses a morte do único outro sinal de lance.

**O estado final é UM sinal biddable.**

---

## 3. Escopo

### Dentro do escopo

- Conversion action nova no Google Ads: categoria de lead/agendamento (**não**
  `PURCHASE`), `UPLOAD_CLICKS`, janela de 90 dias, criada como **secundária**.
- `eventSource: MESSAGE` para ela — o agendamento acontece numa conversa de
  WhatsApp. A de compra usa `IN_STORE`, porque a compra acontece na clínica.
- Coluna para o ID da action nova em `scheduler.clinics`.
- Coluna para marcar o envio dela em `scheduler.lead_conversions` — o
  `uploaded_at` atual é do evento de compra.
- `ConversionUploader` passa a enviar para **dois destinos**, com regra de
  elegibilidade própria para cada.
- Regra do evento de agendamento: **todos**, dentro dos 90 dias do clique, sem
  filtro de status.

### Fora do escopo

- **Retratação ou zeramento do evento de agendamento.** Cancelado continua
  valendo: a pessoa agendou. É o que torna este evento mais simples que o de
  compra, não um esquecimento.
- **Promover a biddable.** É decisão de painel, depois de 4-6 semanas de
  histórico, e vem com a despromoção da `Lead - Formulário`. Não é código.
- **Mostrar os dois eventos na faixa do painel** (PR #74). Ela hoje conta
  `uploaded_at`, que passa a significar "compra enviada". Decidir se a faixa
  mostra um, outro ou os dois é fatia própria — ver 5.3.
- **Recriar o rastreio de clique no WhatsApp na LP.** Problema diferente: a
  `Lead - Whatsapp` era tag de GTM e foi `REMOVED` (irreversível). Este PRD é
  sobre conversão **offline**, que não depende de tag.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | modificar | `clinics.booking_conversion_action_id` e `lead_conversions.booking_uploaded_at`; migrations idempotentes, `CREATE TABLE` em sincronia |
| `scheduler/src/scripts/liga_conversao_offline.py` | modificar | passar a ligar as DUAS actions, ou aceitar qual delas |
| `infra/src/functions/conversions/uploader.py` | modificar | segundo destino, segunda regra de elegibilidade, segundo marcador |
| `infra/src/services/data_manager_service.py` | modificar | `eventSource` deixa de ser constante do módulo e passa a ser por evento |
| `infra/tests/unit/` | modificar | travar que as duas regras são distintas e que a de agendamento NÃO filtra status |

### 4.1 A decisão de modelagem

**Duas colunas, não uma tabela.** `booking_conversion_action_id` em `clinics` e
`booking_uploaded_at` em `lead_conversions`, paralelas às que existem.

Uma tabela `clinic_conversion_actions(clinic_id, kind, action_id)` seria mais
extensível, mas é especulação: há dois eventos, e o segundo acabou de ser
decidido. O caminho direto resolve, e a tabela normalizada é o que fazer **se**
aparecer um terceiro.

**Dívida que isso cria, e vale nomear:** `uploaded_at` sem qualificador passa a
significar "compra enviada", por acidente histórico. Renomear exige mexer no
uploader e no `resumo_de_conversoes` do PR #74 ao mesmo tempo, em produção.
Fica registrado; não se resolve aqui.

---

## 5. Dependências e riscos

**Dependências**

- PRs #78, #80/#83 mergeados e deployados. ✅
- Credencial da Data Manager em `/prod/DATA_MANAGER_REFRESH_TOKEN`. ✅
- A action nova precisa ser criada no Google Ads **antes** do deploy, e o ID
  gravado na coluna nova — senão o uploader sai com `clinics: 0` em silêncio,
  que foi o defeito de 28/09.

**Riscos**

### 5.1 Volume ainda abaixo do ideal

~19/mês contra os ~30 que o tCPA pede. Promover cedo demais entrega ao algoritmo
**menos** sinal do que ele tem hoje (~35 do formulário). É o motivo de nascer
secundária e de a promoção vir com dado na mão, não por calendário.

### 5.2 Trocar o sinal de lance reinicia o aprendizado

Vale fazer **uma vez**, com histórico acumulado. Promover a de agendamento e
despromover a de formulário no mesmo ato, não em dois passos.

### 5.3 A faixa do painel passa a contar só metade

`resumo_de_conversoes` conta `uploaded_at`, que vira "compra enviada". Depois
deste PRD, "aguardando envio" passa a ignorar o evento de agendamento, e o
painel mostraria um retrato parcial sem avisar. **Decidir antes do deploy**:
mostrar os dois, ou rotular explicitamente o que a faixa cobre.

### 5.4 A amostra é de um mês

Todos os números de 2.3 vêm de setembro. Reavaliar com 60-90 dias antes de
promover, e aceitar que o ~19/mês pode se revelar bem diferente.

---

## 6. Critérios de aceite

- [ ] Action nova criada no Google Ads, categoria de lead/agendamento, **não**
      `PURCHASE`, secundária
- [ ] `booking_conversion_action_id` e `booking_uploaded_at` criadas por
      migration idempotente, com `CREATE TABLE` em sincronia
- [ ] `ConversionUploader` envia para os dois destinos numa execução
- [ ] O evento de agendamento sobe **cancelado e falta** também — teste trava que
      a regra dele NÃO filtra status
- [ ] O evento de compra continua filtrando `= 'CONFIRMED'` e sessão passada —
      teste trava que as duas regras seguem distintas
- [ ] O evento de agendamento usa `eventSource: MESSAGE`; o de compra,
      `IN_STORE`
- [ ] Nenhuma retratação ou zeramento para o evento de agendamento
- [ ] Cada evento marca sua própria coluna: enviar um não marca o outro
- [ ] Ensaio `validateOnly` em produção, com os dois destinos, antes do envio
      real
- [ ] Decisão sobre a faixa do painel tomada e registrada (5.3)

---

## 7. Referências

- `docs/work/prd/016-comparecimento-e-compra-real.md` — o evento de compra
- `docs/work/spec/016-comparecimento-e-compra-real.md`
- PR #78 — transporte via Data Manager API
- PR #83 — `NO_SHOW` e o guard da compra
- `infra/src/services/data_manager_service.py` — por que não existe RETRACTION

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada: `spec/017-agendou-pelo-whatsapp.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
