# PRD — 022 Booking-site: preço certo, fluxo enxuto e calendário do mês

> Gerado na fase **Research**. Use como input para a fase Spec.
> Origem: reunião Rodrigo + André sobre melhorias do agendamento (out/2026).
> Login no início do fluxo, pagamento (Asaas) e tablet de recepção ficam em
> PRDs próprios — ver §3 "Fora do escopo".

---

## 1. Objetivo

Fazer o booking-site cobrar e mostrar **o mesmo preço** que o bot de WhatsApp
cobraria pelo mesmo agendamento, oferecer **só horários que de fato podem ser
gravados**, e tirar do caminho do cliente o que não é decisão dele (duração,
profissional, dias sem vaga, meses futuros).

Ao final, o cliente vê no resumo: total pela tabela, desconto aplicado (com o
motivo) e valor final — e recebe no WhatsApp a mesma confirmação, com as
mesmas orientações pré-sessão, que o bot mandaria.

---

## 2. Contexto

### 2.1 Divergências encontradas no código (bugs)

O booking-site se apresenta como "segunda porta para o mesmo motor do bot"
(`booking-site/docs/visao-geral.md` §4), mas três peças não são as mesmas:

| # | O que o bot faz | O que o site faz | Efeito |
|---|---|---|---|
| D1 | `ai_tools._calcula_desconto`: personalizado > melhor entre primeira sessão e faixas por nº de áreas (`discount_rules`) | `create_appointment` não passa desconto; `AppointmentService` só aplica o **personalizado** | Mesmo agendamento custa mais pelo site do que pelo WhatsApp. O valor gravado diverge da política da clínica. |
| D2 | Duração via `duration_rules.calcula_duracao` (soma das áreas + piso, teto, passo) para **pedir** horário e para **gravar** | Pede horário com a soma crua do front (`utils/cartTotals.ts` → `totalDuration`); o backend grava com `calcula_duracao` | Grade oferecida não é a grade gravável: horário pode dar 409 na criação ou gravar sessão maior que a janela checada. Provável parte do "agendamento que não chega no banco". |
| D3 | Confirmação = template `BOOKED` (preço com desconto) + `orientacoes_pos_sessao.texto` | Só o `BOOKED`, com `final_price_cents` formatado sem mostrar desconto, e sem orientações | Cliente do site não recebe as recomendações pré-sessão que a clínica escreveu. |

Além disso, `AvailabilityEngine.get_days_status` (usado só pelo site) reescreve
as mesmas queries de `janelas_livres` (regras → exceções → agendamentos) em vez
de chamá-la — duas cópias da regra de agenda que vão divergir na próxima
mudança. A reunião pediu explicitamente "reutilizar funções de cálculo de
horário para evitar redundância".

### 2.2 Decisões da reunião aplicadas aqui

- Remover a exibição de durações para o cliente final (continuam valendo
  internamente para a agenda).
- Profissional não é escolhido pelo cliente — o sistema escolhe.
- Mostrar apenas datas/horários disponíveis.
- Limitar a marcação ao mês vigente; o próximo mês abre na virada.
- Exibir no fluxo final total, desconto aplicado e preço final.
- Preço exibido continua sendo a tabela padrão; o desconto aparece **no
  resumo final**, não no catálogo.
- Mobile first: ~90% dos acessos vêm do celular.

---

## 3. Escopo

### Dentro do escopo

**A. Preço e desconto (backend + front)**

1. Extrair o cálculo de desconto de `ai_tools._calcula_desconto` para um
   serviço de domínio compartilhado (ex.: `services/politica_de_desconto.py`),
   chamado pelo bot **e** pelo site. Regras idênticas às de hoje:
   personalizado vence; senão maior entre `first_session` e `tier_2`/`tier_3`;
   `aplica_desconto` (trunca) para o valor final. O que é específico do bot
   (`_barra_areas_nao_conversadas`, mensagens de display) fica no bot.
2. Nova rota pública `POST /public/clinics/{clinicId}/quote` (dentro da Lambda
   `PublicBooking`, via `router.py` — regra do PRD 013) recebendo
   `serviceIds`, `serviceAreaPairs` e `phone` opcional; devolve
   `originalPriceCents`, `discountPct`, `discountReason`, `finalPriceCents`.
   Sem telefone, só as regras que não dependem da pessoa (faixas de áreas);
   com telefone, também primeira sessão e personalizado.
3. `create_appointment` público passa a gravar o desconto calculado pelo mesmo
   serviço — o valor exibido no resumo é o valor gravado.
4. Confirmação do site igual à do bot: `BOOKED` com o preço já com desconto
   (mesmo formato de `_format_price_with_discount`) + orientações pré-sessão
   de `orientacoes_pos_sessao.texto`.
5. Resumo final (`CartSummary` na etapa de dados): linhas "Total", "Desconto
   (motivo legível)" e "Valor final". A cotação é refeita quando o telefone é
   informado no formulário (primeira sessão/personalizado só existem com
   telefone).

**B. Fluxo enxuto (front)**

6. Remover duração de `ServiceCard`, `AreaPicker`, `CartSummary` e da tela de
   sucesso. Ícone de relógio sai junto.
7. Remover a etapa `professional` do wizard e o `ProfessionalPicker`. O
   backend já escolhe o profissional quando não recebe `professionalId` e a
   checagem de conflito é da clínica inteira — nada muda na agenda. O aviso
   bloqueante de "nenhum profissional cadastrado" continua.
8. Revisão visual mobile/desktop: ícones faltando no deploy (dinheiro,
   relógio etc.), alinhamentos, tamanhos de toque (≥44px), seguindo as
   regras do Impeccable em `frontend/CLAUDE.md`.

**C. Agenda e calendário (backend + front)**

9. Disponibilidade calcula a duração **no backend**: a rota `/availability`
   passa a aceitar `serviceIds` + `serviceAreaPairs` e usa
   `calcula_duracao`/`duracao_da_sessao` — a mesma conta da criação. O
   parâmetro `totalDuration` deixa de ser lido (mantido aceito, ignorado e
   logado, por compatibilidade com front em cache).
10. `get_days_status` reaproveita `janelas_livres` em vez de repetir as
    queries.
11. Calendário mostra **só dias com horário** (fechados e lotados não
    aparecem como opção) e só dentro do mês vigente, no fuso da clínica
    (`clinic.timezone`). Horários que já passaram hoje não são oferecidos.
12. A regra do mês é validada também na criação (backend), não só na tela.

### Fora do escopo

- **Login no início do fluxo**, seleção entre pacientes com o mesmo telefone,
  pré-preenchimento e histórico — PRD próprio (023), alinhado com o André.
- **Campo de cupom** — decisão da reunião: depois da primeira versão.
- **Pagamento (Asaas)**, conciliação, maquininhas — PRD próprio.
- **Tablet de recepção** (termo, anamnese, assinatura) — PRD próprio.
- **Teste A/B** login-primeiro vs catálogo público — depende do 023.
- Carrinho misto (serviço com e sem área) no backend — limitação conhecida
  da visão geral §7, não muda aqui. A nova cotação herda o comportamento
  atual da criação.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/politica_de_desconto.py` | criar | Cálculo de desconto compartilhado (extraído de `ai_tools`) |
| `scheduler/src/services/ai_tools.py` | modificar | `_calcula_desconto` delega ao serviço novo |
| `scheduler/src/services/availability_engine.py` | modificar | `get_days_status` usa `janelas_livres`; filtro de horário passado e limite do mês |
| `scheduler/src/functions/public_booking/quote.py` | criar | `POST /quote` |
| `scheduler/src/functions/public_booking/availability.py` | modificar | Duração calculada no backend a partir do carrinho |
| `scheduler/src/functions/public_booking/create_appointment.py` | modificar | Grava desconto da política; confirmação com desconto + orientações; valida mês |
| `scheduler/src/functions/public_booking/router.py` | modificar | Rota `quote` |
| `scheduler/sls/functions/public_booking/interface.yml` | modificar | Evento HTTP da rota nova (sem função nova) |
| `booking-site/src/pages/Booking.tsx` | modificar | Sem etapa de profissional; cotação no resumo |
| `booking-site/src/components/{ServiceCard,AreaPicker,CartSummary}.tsx` | modificar | Sem duração; linhas de desconto |
| `booking-site/src/components/ProfessionalPicker.tsx` | remover | Etapa eliminada |
| `booking-site/src/components/WeekPicker.tsx` | modificar | Só dias disponíveis, limite do mês vigente |
| `booking-site/src/hooks/useBooking.ts`, `services/booking.service.ts`, `types/index.ts` | modificar | `useQuote`, payload novo de disponibilidade |
| `booking-site/src/utils/cartTotals.ts` | modificar | Deixa de ser fonte de duração para a agenda |
| `booking-site/docs/visao-geral.md` | modificar | Atualizar §2, §5, §7 |
| `scheduler/tests/mocks/public_booking/`, `tests/postman/` | criar/modificar | Mocks e requests de `quote` e `availability` |

---

## 5. Dependências e riscos

- **Dependências:** nenhuma infra nova — rota entra na Lambda `PublicBooking`
  existente (PRD 013). Sem migration.
- **Risco — mudança de preço do bot:** a extração de D1 não pode mudar
  nenhum valor que o bot calcula hoje. Mitigação: testes de caracterização do
  `_calcula_desconto` atual **antes** de extrair, rodando depois contra o
  serviço novo.
- **Risco — front em cache durante o deploy:** front antigo manda
  `totalDuration` e `professionalId`. Backend continua aceitando os dois.
  Ordem: deploy do backend primeiro, front depois.
- **Risco — fim do mês sem vaga:** com o mês vigente literal, no dia 29/10
  com agenda cheia o cliente não tem nenhum dia. Comportamento proposto:
  estado vazio explicando que a agenda do próximo mês abre no dia 1º, com
  botão de contato (WhatsApp da clínica). **Validar com o André** se a regra
  literal é a desejada ou se prefere "abre o próximo mês a partir do dia X".
- **Risco — profissional:** remover a escolha vale para todas as clínicas.
  **Validar** que nenhuma clínica ativa depende dela (hoje o conflito já é
  checado na clínica inteira, então a escolha não reservava a agenda de
  ninguém).
- **Risco — expor desconto por telefone:** `/quote` com telefone revela se
  aquele número tem desconto personalizado ou já foi à clínica. Mitigação:
  resposta só traz o percentual e um motivo genérico, sem nome nem
  histórico; mesmo nível do que o bot já diz a qualquer número na conversa.

---

## 6. Critérios de aceite

- [ ] Para o mesmo carrinho e telefone, preço e desconto gravados pelo site
      são idênticos aos que o bot calcularia (teste automatizado cobrindo
      sem regra, primeira sessão, tier 2, tier 3, personalizado, personalizado 0%).
- [ ] Testes de caracterização do desconto do bot passam antes e depois da
      extração.
- [ ] Todo horário oferecido pelo site é aceito pelo `create_appointment`
      (mesma duração nos dois lados — teste com `duration_rules` com piso,
      teto e passo).
- [ ] `get_days_status` não tem query própria de regras/exceções/agendamentos.
- [ ] Resumo final mostra Total, Desconto (quando houver) e Valor final; o
      valor final é o `final_price_cents` gravado.
- [ ] Confirmação no WhatsApp tem o preço com desconto e as orientações
      pré-sessão da clínica.
- [ ] Nenhuma duração visível ao cliente em nenhuma tela.
- [ ] Wizard não tem etapa de profissional; agendamento grava profissional.
- [ ] Calendário não oferece dia fechado, lotado, passado, horário que já
      passou hoje, nem dia fora do mês vigente; backend recusa (400) data fora
      do mês.
- [ ] Fim de mês sem vaga mostra estado vazio com explicação e contato.
- [ ] 4 estados (loading, erro, vazio, sucesso) na cotação e no calendário.
- [ ] `npm run lint`, `npm run test`, `npm run build` limpos no booking-site;
      testes do scheduler passando.
- [ ] Testes manuais via curl em dev, mocks em `tests/mocks/`, doc em
      `tests/integration/`, Postman em `tests/postman/`.
- [ ] `booking-site/docs/visao-geral.md` atualizado.

---

## 7. Referências

- `booking-site/docs/visao-geral.md` — estado atual do produto
- `docs/work/prd/009-site-agendamento-publico.md` — origem do booking-site
- `docs/work/prd/013-limite-do-cloudformation.md` — rotas públicas numa Lambda só
- `docs/plans/2026-02-21-discount-system-design.md` — política de desconto
- `scheduler/src/services/ai_tools.py` (`_calcula_desconto`, `_resultado_de_desconto`)
- `scheduler/src/services/duration_rules.py`, `desconto_personalizado.py`,
  `primeira_visita.py`, `orientacoes_pos_sessao.py`
- `frontend/CLAUDE.md` — Design Principles (Impeccable)

---

## Status (preencher após conclusão)

- [x] PRD gerado (2026-10-17)
- [x] Spec gerada: `spec/022-booking-site-preco-fluxo-calendario.md` (2026-10-17)
- [x] Implementado em: 2026-10-17 (branch `feat/022-booking-site-preco-fluxo-calendario`; deploy pendente)
- [x] Registrado em `TASKS_LOG.md`
