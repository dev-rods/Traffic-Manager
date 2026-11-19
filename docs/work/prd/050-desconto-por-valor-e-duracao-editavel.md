# PRD - 050 Desconto por valor ou percentual (com centavos) e duração editável no pop-up da agenda

> Gerado na fase **Research**. Use como input para a fase Spec.
> Fluxo: PRD → spec → PR → deploy **dev** → validação → deploy prod.

---

## 1. Objetivo

Dois ajustes no modal "Editar agendamento" (o pop-up da tela de agenda), e por
tabela no "Novo agendamento", que usa os mesmos campos:

1. **Desconto personalizado por percentual OU por valor em reais.** Os dois
   aceitam até duas casas decimais (`12,5%`, `R$ 37,90`), com vírgula ou ponto.
   Hoje o campo só aceita percentual inteiro: o `<input type="number">` deixa
   digitar `12.5`, mas o backend faz `int()` e grava 12. O preço final tem de
   bater ao centavo com o que a recepção combinou.
2. **A duração fixada pode ser apagada enquanto se digita.** Hoje, apagar o
   campo chama `onChange(null)`, o estado volta a "calculada pelas áreas" e o
   input some debaixo do dedo. A obrigação de não estar vazio vale só ao salvar.

---

## 2. Contexto

- **Desconto.** A recepção fecha acordos em reais ("tira R$ 20") e em
  percentual fracionário ("12,5% da indicação"). Converter valor em percentual
  não serve: R$ 10 sobre R$ 195 é 5,128...%, e com duas casas o preço final sai
  R$ 184,99 em vez de R$ 185,00. O banco já está pronto para percentual com
  centavos: `appointments.discount_pct` e `patients.custom_discount_pct` são
  `NUMERIC(5,2)` desde o desconto personalizado por paciente, que já aceita
  `12,5` (`desconto_personalizado.normaliza_entrada`, `cadastroSchema`). O
  que falta é o pop-up da agenda e o handler de edição acompanharem, e existir
  um jeito de registrar o desconto em reais.
- **Duração.** `DuracaoField` guarda o valor como `number | null`, e `null`
  significa "seguindo o cálculo". O input converte string vazia em `null`, então
  apagar para redigitar derruba o modo fixado. A validação de faixa (5 a 480)
  já é só visual até salvar; o vazio precisa seguir a mesma regra.

---

## 3. Escopo

### Dentro do escopo

**Desconto**
- Modo "Personalizado" ganha um seletor **% / R$**. Um campo só, com máscara
  leve: aceita dígitos, vírgula ou ponto, até duas casas.
- Percentual: 0,01 a 100,00. Valor: R$ 0,01 até o subtotal das áreas (desconto
  maior que o preço é recusado na tela e no servidor).
- Resumo de preço do modal mostra a linha "Desconto (12,5%)" ou
  "Desconto (R$ 20,00)" e o total ao centavo, com a MESMA conta do servidor.
- Resumo de confirmação (PRD 043) e `textoDoDesconto` mostram o desconto no
  formato escolhido.
- Popover da agenda e "Hoje" do dashboard mostram `-R$ 20,00 (personalizado)`
  quando o desconto foi por valor, `-12,5%` quando percentual.
- Backend `PUT appointments/{id}` e `POST appointments` aceitam
  `discountPct` decimal (2 casas) **ou** `discountCents` inteiro; os dois juntos
  é 400. Validação centralizada em `desconto_personalizado` (a função
  `normaliza_entrada` já existe; ganha a irmã para centavos).
- Persistência: nova coluna `appointments.discount_cents INTEGER NULL`. Nulo =
  desconto percentual (comportamento atual). Preenchido = o desconto é este
  valor, e `discount_pct` guarda o percentual EQUIVALENTE arredondado a duas
  casas, só para leitura (relatórios, filtros `discount_pct > 0`, check-in).
  A fonte de verdade quando `discount_cents` existe é ele; todo recálculo de
  `final_price_cents` (troca de áreas, edição do desconto, criação) passa por
  `desconto_personalizado.aplica`, que passa a receber o valor em centavos.
- Relatórios e dashboard: `total_discount_cents` já é `original - final`, não
  muda. Os filtros `discount_pct > 0` passam a cobrir também `discount_cents`
  (um desconto de R$ 0,01 sobre R$ 1.000 arredonda para 0,00%).
- Criação pelo painel (`CreateAppointmentModal`) usa o mesmo componente de
  desconto: os dois modais hoje têm a seção duplicada, e a regra nova nasceria
  em dois lugares. Componente `DescontoField` compartilhado.

**Duração**
- `DuracaoField` guarda o texto digitado; vazio ou inválido mantém o modo
  fixado e mostra o aviso de faixa. O pai só recebe `null` pelo botão "Voltar
  ao cálculo".
- Salvar com a duração fixada vazia ou fora de 5 a 480 bloqueia com mensagem no
  modal ("Informe a duração fixada ou volte ao cálculo"); o botão continua
  habilitado para a mensagem aparecer.
- Busca de horários (`useAvailableSlots`) usa a duração calculada enquanto o
  texto fixado está vazio ou inválido, para não disparar pedido com `NaN`.
- O mesmo vale no "Novo agendamento", que usa o mesmo `DuracaoField`.

### Fora do escopo
- Desconto por valor no **cadastro da paciente** (`custom_discount_pct` segue
  só percentual; é um combinado permanente, e valor fixo não faz sentido com
  carrinhos diferentes).
- Bot e site: continuam com a política de desconto automática; a
  `calculate_discount` não muda.
- Regras de desconto da clínica (`discount_rules`, inteiras): intocadas.
- Desconto acumulado (parceria + valor): continua um desconto por sessão.

---

## 4. Decisões (para o André confirmar ou derrubar no spec)

| # | Decisão | Alternativa descartada |
|---|---|---|
| 1 | Coluna nova `discount_cents` e `discount_pct` derivado quando o desconto é por valor | Converter valor em percentual na tela: perde centavos (R$ 184,99 em vez de R$ 185,00) |
| 2 | Percentual derivado é gravado, arredondado a 2 casas, para os leitores atuais não mudarem | Deixar `discount_pct` NULL: quebra `discount_pct > 0` em 4 consultas e o `float(...)` do check-in |
| 3 | Criação pelo painel entra no escopo, pelo componente compartilhado | Só edição: a seção de desconto duplicada divergiria (fonte única de verdade) |
| 4 | Valor maior que o subtotal é recusado (400) | Aceitar e zerar o preço: igual à parceria, e silencioso |
| 5 | `discount_reason` continua `custom` para os dois formatos | Razão nova `custom_value`: o relatório agruparia o mesmo acordo em duas linhas |

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | modificar | migration idempotente `discount_cents INTEGER` + CHECK (NULL ou > 0) + `CREATE TABLE` em sincronia |
| `scheduler/src/services/desconto_personalizado.py` | modificar | `aplica(total, pct, cents=None)`, `normaliza_centavos`, `pct_equivalente(total, cents)` |
| `scheduler/src/services/appointment_service.py` | modificar | `create_appointment` e `update_appointment_services` carregam e reaplicam `discount_cents`; INSERT grava a coluna |
| `scheduler/src/functions/appointment/update.py` | modificar | aceita `discountPct` decimal ou `discountCents`; sem `int()`; recalcula `final_price_cents` pela fonte certa |
| `scheduler/src/functions/appointment/create.py` | modificar | repassa `discountCents` |
| `scheduler/src/functions/appointment/list.py` | modificar | devolve `discount_cents` |
| `scheduler/src/functions/clinic/dashboard.py`, `reports.py` | modificar | filtros `discount_pct > 0` passam a `(discount_pct > 0 OR discount_cents > 0)`; `today` devolve `discount_cents` |
| `scheduler/src/services/checkin.py` | conferir | `discountPct` continua float do derivado; nada a mudar se o iPad só exibe |
| `frontend/src/types/index.ts` | modificar | `discount_cents: number \| null`; payloads com `discountCents?` |
| `frontend/src/pages/agenda/components/DescontoField.tsx` (+test) | criar | modo none/parceria/personalizado + seletor %/R$ + campo com máscara |
| `frontend/src/lib/desconto.ts` (+test) | criar/modificar | parse do texto (vírgula/ponto, 2 casas), `precoComDesconto` com centavos, texto do desconto |
| `frontend/src/lib/cadastroPaciente.ts` | modificar | `precoComDesconto` muda de casa (ou reexporta) |
| `frontend/src/lib/alteracaoDeAgendamento.ts` (+test) | modificar | `textoDoDesconto` com valor |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` (+test) | modificar | usa `DescontoField` e `DuracaoField` novo; validação no submit |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | modificar | idem |
| `frontend/src/pages/agenda/components/DuracaoField.tsx` (+test) | modificar | texto local; vazio não derruba o modo fixado |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx`, `dashboard/components/TodayAppointments.tsx` | modificar | exibição `-R$ x` quando `discount_cents` |
| `scheduler/tests/unit/` | criar | `test_desconto_por_valor.py` (aplica, normaliza, pct equivalente, handler 400s, recálculo ao trocar áreas) |
| `scheduler/tests/integration/050-desconto-por-valor.md` | criar | roteiro curl em dev |

---

## 6. Dependências e riscos

- **Migration** em dev e prod (`setup_database.py`, idempotente). Dev já está
  alinhado com prod desde o 049.
- **Risco de divergência de conta**: o preço mostrado no modal e o gravado
  precisam ser a mesma função. A tela trunca como o servidor (`aplica` TRUNCA
  por decisão antiga; valor em centavos é subtração exata, sem arredondamento).
- **Risco do derivado**: `discount_pct` gravado a partir de `discount_cents`
  é cópia; ao trocar as áreas, o recálculo tem de partir de `discount_cents`
  e reescrever o percentual. Teste de unidade cobre esse caminho (regra
  reaplicada sobre valor pronto: varrer todos os pontos de recálculo).
- **Compatibilidade**: `discountPct` inteiro continua aceito; agendamentos
  antigos têm `discount_cents NULL` e nada muda para eles.
- Deploy: `serverless deploy --stage dev`, roteiro curl, depois prod. Painel
  sobe pela Vercel no merge (serve dev e prod ao mesmo tempo: o front precisa
  tolerar `discount_cents` ausente até o prod subir).

---

## 7. Critérios de aceite

- [ ] Editar: "Personalizado" → `%` → `12,5` → total do modal = `trunc(subtotal * 0,875)`; salvar grava `discount_pct = 12.50`, `final_price_cents` igual ao mostrado.
- [ ] Editar: "Personalizado" → `R$` → `20` sobre R$ 195 → total R$ 175,00; grava `discount_cents = 2000`, `discount_pct = 10.26`, `final_price_cents = 17500`.
- [ ] `R$ 250` sobre R$ 195 → mensagem na tela; `PUT` direto com `discountCents: 25000` → 400.
- [ ] `discountPct` e `discountCents` no mesmo pedido → 400.
- [ ] Trocar áreas de um agendamento com desconto de R$ 20 → novo `final = novo subtotal - 2000`, `discount_pct` reescrito.
- [ ] Popover e "Hoje" mostram `-R$ 20,00 (personalizado)`; relatório soma o desconto no total e na quebra por razão.
- [ ] Criar agendamento com desconto por valor funciona igual.
- [ ] Duração: "Ajustar" → apagar o campo → o input continua na tela, com aviso; digitar `45` → horários buscados com 45; salvar vazio → mensagem e nada enviado.
- [ ] Agendamento antigo (sem `discount_cents`) abre e salva sem mudança de comportamento.
- [ ] `pytest tests/unit`, `vitest`, `build`, `lint` verdes; roteiro curl em dev registrado.

---

## 8. Referências

- `scheduler/src/services/desconto_personalizado.py` (regra de centavos e NULO vs ZERO)
- `frontend/src/lib/cadastroPaciente.ts` (`cadastroSchema.custom_discount_pct`, máscara já aceita)
- PRD 047 (percentual com duas casas no cadastro), PRD 043 (confirmação da alteração), PRD 049 (fluxo dev → prod)

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/050-desconto-por-valor-e-duracao-editavel.md` (19/11/2026)
- [x] Implementado em dev: 19/11/2026 (PR #214, layer 199; roteiro curl verde)
- [ ] Implementado em prod: (data)
- [ ] Registrado em `TASKS_LOG.md`
