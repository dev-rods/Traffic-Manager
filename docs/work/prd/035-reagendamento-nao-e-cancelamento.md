# PRD - 035 Reagendamento não é cancelamento

> Gerado na fase **Research** em 01/11/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Fazer o sistema distinguir, no dado e nos relatórios, três desfechos que hoje se confundem:

- **Cancelamento**: a pessoa desmarcou e não remarcou.
- **Reagendamento**: a pessoa mudou dia ou horário e continua com uma sessão marcada.
- **Falta**: não compareceu e não avisou (já existe: `NO_SHOW`).

O agendamento original e o novo devem ficar vinculados, para que se saiba se a pessoa compareceu depois de remarcar, e para que a troca não conte como cancelamento no dia antigo.

---

## 2. Contexto

### O relato da clínica

> Se o paciente muda do dia 21 para o dia 22, isso é um reagendamento, mas está aparecendo como cancelamento no dia 21.

### Causa raiz (investigação em 01/11/2026)

Não é um bug de classificação de status. O sistema **tem** reagendamento em lugar: `AppointmentService.reschedule_appointment` muda data e hora do mesmo registro, sem cancelar nada. O problema é que dois dos caminhos usados pelo paciente **não chegam** a ele e caem em "cancelar + criar outro", sem vínculo:

| Caminho | Comportamento | Resultado |
|---|---|---|
| Painel, modal de edição | Muda data no mesmo registro | Correto |
| Bot, fora da janela de lembrete | Tool `reschedule_appointment` | Correto |
| **Site "Meus agendamentos"** | Só existe "Cancelar agendamento". Não há endpoint nem tela de remarcar em `public_booking/` | CANCELLED no dia 21 + CONFIRMED novo no dia 22 |
| **Bot na janela de lembrete, clínica com site** | PRD 027 remove as tools de remarcar e cancelar e manda o link do site (`lembrete.py`) | A pessoa cai no caso acima |
| **Painel, recepção** | Em vez de editar, cancela e recria | Mesmo resultado, por hábito |

### Medição em prod (60 dias até 01/11/2026)

Critério: `CANCELLED` cujo paciente ganhou outro agendamento na mesma clínica entre 10 min antes e 24 h depois do cancelamento. Origem obtida cruzando o banco com os logs do CloudWatch (`UpdateAppointment`/`CreateAppointment` = painel, `PublicBooking` = site, `WhatsAppWebhook` = bot). Excluídos 12 pares de 08 e 09/09 que são importação de histórico.

| Origem do cancelamento | Cancelamentos | Com novo agendamento | % reagendamento |
|---|---|---|---|
| Site | 21 | 17 | 81% |
| Painel | 84 | 20 | 24% |
| Bot | 4 | 0 | 0% |
| Sem log | 8 | 0 | - |
| **Total** | **117** | **37** | **32%** |

Observações:

- Os 17 pares do site começam em 20/10, quando o site da Essência entrou no ar. Quase todos têm 0 a 1 minuto entre cancelar e criar. O lembrete do PRD 027 só aumenta o volume ao empurrar para o link.
- 16 pares são painel para painel, vários com 0 a 8 minutos de intervalo: a recepção cancela e recria apesar de o modal de edição já remarcar em lugar.
- Em 12 dos 37 pares o agendamento novo também acabou `CANCELLED`: a pessoa remarcou duas ou três vezes seguidas e cada etapa conta como cancelamento.
- Praticamente todo o volume é da Essência (122 cancelamentos e 27 faltas no período). Nobre tem 6 cancelamentos.

### O que o modelo não tem

- `status` aceita só `CONFIRMED | CANCELLED | NO_SHOW` (`appointments_status_check`).
- Nenhuma coluna liga um agendamento ao que o substituiu. Sem isso, nem um site com botão "Remarcar" resolveria os casos em que a troca exige registro novo (mudança de áreas junto com a data, por exemplo), nem é possível corrigir o histórico.

### Efeito colateral nas conversões

Ao virar `CANCELLED`, o agendamento antigo deixa a conversão do Google Ads parada em "aguardando" (`lead_service` só sobe `CONFIRMED`), e o novo gera uma conversão nova. Um reagendamento legítimo passa a parecer um lead que agendou duas vezes. Ver comentário em `setup_database.py` sobre `appointments_status_check` e os PRDs 016/017.

---

## 3. Escopo

### Dentro do escopo

**A. Vínculo no modelo**

- Coluna `rescheduled_to_id UUID NULL REFERENCES scheduler.appointments(id)` em `scheduler.appointments`, preenchida no registro **antigo** quando ele é substituído. Índice parcial para `rescheduled_to_id IS NOT NULL`.
- Regra de leitura única, num lugar só (service ou view): **reagendado = `status = 'CANCELLED' AND rescheduled_to_id IS NOT NULL`**; cancelado = `CANCELLED` sem vínculo; falta = `NO_SHOW`. Não criar um quarto status: `CANCELLED` continua governando motor de horários, lembretes e conversão, o que evita reauditar todos os `WHERE status = 'CONFIRMED'`.
- Encadeamento: ao remarcar um agendamento que já é destino de outro, o vínculo anda. O comparecimento é o do **último** elo; os relatórios devem seguir a cadeia (CTE recursiva ou função) ao responder "compareceu depois de remarcar?".

**B. Operação "substituir" no service**

- Nova operação em `AppointmentService` que cancela o antigo e cria o novo numa única transação, gravando `rescheduled_to_id`. Reaproveita `cancel_appointment` e `create_appointment`. É o caminho para toda remarcação que precisa de registro novo.
- `reschedule_appointment` (em lugar) continua sendo o caminho padrão quando só data e hora mudam.
- Conversão: a nova operação move a `lead_conversion` para o agendamento novo (mesma lógica de `update_conversion_date`), em vez de deixar uma órfã e criar outra.

**C. Site: botão "Remarcar"**

- Novo endpoint `POST /public/clinics/{clinicId}/appointments/{appointmentId}/reschedule` com o mesmo contrato de segurança do `cancel` (phone + token OTP, mesmas `variantes_do_numero`). Chama `reschedule_appointment` em lugar.
- Em `MyAppointmentsModal`, botão "Remarcar" ao lado de "Cancelar", reaproveitando o seletor de data e horário já existente no fluxo de agendamento. Edição inline na própria lista, mesmo padrão do cancelar inline.
- Texto do lembrete (PRD 027, `lembrete.py`) passa a dizer que a pessoa **remarca** pelo link, não só cancela.

**D. Painel**

- No `CancelAppointmentModal`, pergunta "A pessoa vai remarcar?" com atalho que abre o `EditAppointmentModal` em vez de cancelar. Objetivo: tirar a recepção do hábito de cancelar e recriar.
- Se a recepção cria um agendamento para um paciente que teve um cancelamento nos últimos N minutos (sugestão: 30), o `CreateAppointment` vincula automaticamente (`rescheduled_to_id` no antigo). Mesma heurística que validou os 37 pares; em produção ela ficou entre 0 e 8 minutos.

**E. Relatórios e dashboard**

- `clinic/dashboard.py` e `clinic/reports.py`: `cancelled_appointments` passa a excluir reagendados; novo campo `rescheduled_appointments`. `cancellation_rate` acompanha.
- `AgendaPorData`: coluna "Cancelam." e "Perdido em cancelamentos" não contam reagendados. A perda em reais de um reagendamento é zero.
- `KpiCards`: card "Cancelamentos" sem reagendados; reagendamentos como `detail` do card ou card próprio, a decidir na Spec pelo espaço no grid de 4.
- Agenda do dia: um agendamento reagendado aparece com rótulo "Remarcado para dd/mm" e link para o novo, não como "Cancelado".
- `lead_service.resumo_de_conversoes`: `canceladas` deixa de incluir reagendados.

**F. Backfill do histórico**

- Script idempotente em `src/scripts/` que aplica a heurística (mesmo paciente, mesma clínica, novo criado entre 10 min antes e 24 h depois do cancelamento, elo mais próximo no tempo) e grava `rescheduled_to_id` nos pares de prod. Roda em dry-run por padrão, imprime a lista para conferência do André, e só grava com flag. Ignorar os pares de importação (data do agendamento anterior a 09/2026 com cancelamento em 08 e 09/09).

### Fora do escopo

- Quarto valor de `status` (`RESCHEDULED`). Decisão: vínculo + `CANCELLED`, pelos motivos acima.
- Exportação para Google Sheets (`sheets_sync`): não faz parte do desfecho do relato. Se a planilha da clínica mostrar "Cancelado", fica para PRD próprio.
- Reagendamento pelo bot na janela de lembrete sem site: já funciona em lugar.
- Mudar o fluxo de check-in e pagamento (PRD 026) para agendamento reagendado: o pagamento segue o agendamento novo, como já ocorre.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | modificar | Coluna `rescheduled_to_id`, índice parcial, `CREATE TABLE` sincronizado |
| `scheduler/src/services/appointment_service.py` | modificar | Operação "substituir" transacional; vínculo automático no create; mover conversão |
| `scheduler/src/services/lead_service.py` | modificar | Mover conversão para o agendamento novo; `canceladas` sem reagendados |
| `scheduler/src/functions/public_booking/reschedule_appointment.py` | criar | Endpoint público de remarcar, mesmo guard do cancel |
| `scheduler/src/functions/public_booking/router.py` | modificar | Rota `POST .../appointments/{appointmentId}/reschedule` |
| `scheduler/src/functions/public_booking/list_appointments.py` | modificar | Expor `rescheduled_to_id` se a UI precisar |
| `scheduler/src/functions/appointment/create.py` | modificar | Vínculo automático por janela de tempo |
| `scheduler/src/functions/appointment/update.py` | modificar | Resposta do cancel informa se virou reagendamento |
| `scheduler/src/functions/clinic/dashboard.py`, `clinic/reports.py` | modificar | Contagens separadas |
| `scheduler/src/services/lembrete.py` | modificar | Texto do bloco de prompt: remarcar pelo link |
| `scheduler/src/scripts/backfill_reagendamentos.py` | criar | Backfill com dry-run |
| `scheduler/tests/...` | criar | Testes da operação, do endpoint, do backfill e das contagens |
| `booking-site/src/components/MyAppointmentsModal.tsx` | modificar | Botão e fluxo "Remarcar" |
| `booking-site/src/services/booking.service.ts`, `hooks/useBooking.ts` | modificar | `rescheduleAppointment` |
| `frontend/src/pages/agenda/components/CancelAppointmentModal.tsx` | modificar | Atalho "vai remarcar? editar em vez de cancelar" |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` e agenda | modificar | Rótulo "Remarcado para" com link |
| `frontend/src/pages/dashboard/components/KpiCards.tsx`, `AgendaPorData.tsx` | modificar | Contagens separadas |
| `frontend/src/services/reports.service.ts`, `frontend/src/types/` | modificar | Novos campos tipados |
| `scheduler/tests/integration/035-reagendamento.md`, `tests/postman/035-*.json` | criar | Documentação pós-task |

---

## 5. Dependências e riscos

- **Dependências:** migration em prod (idempotente, `ADD COLUMN IF NOT EXISTS`); deploy do scheduler (zip) e do booking-site e frontend (Vercel). Backfill roda contra prod e é o André quem executa.
- **Riscos:**
  - A heurística de vínculo automático no painel pode ligar dois agendamentos de pessoas diferentes que usam o mesmo telefone (o site já admite isso). Mitigação: só vincular quando o `patient_id` é o mesmo e deixar a recepção desfazer o vínculo no modal.
  - Mover a conversão do Google Ads para o agendamento novo muda a data enviada; é o mesmo comportamento do `reschedule_appointment` hoje, mas precisa de teste junto com os PRDs 016/017.
  - Todo lugar que conta `CANCELLED` é candidato a divergir. Varrer `grep -rn CANCELLED scheduler/src frontend/src booking-site/src` antes de fechar o PR (ver memória "Regra reaplicada sobre valor pronto").
  - Encadeamento de remarcações: relatório que não segue a cadeia conta o elo do meio como cancelamento. Testar com cadeia de 3.

---

## 6. Critérios de aceite

- [ ] Pelo site, com OTP válido, a pessoa remarca um agendamento sem cancelar: mesmo `id`, nova data, nenhum `CANCELLED` gerado.
- [ ] Pelo painel, cancelar e recriar para o mesmo paciente em até 30 min grava `rescheduled_to_id` no antigo.
- [ ] Operação "substituir" é transacional: falha na criação não deixa o antigo cancelado.
- [ ] Dashboard e relatórios: um reagendamento não entra em "Cancelamentos" nem em "Perdido em cancelamentos"; aparece em "Reagendamentos".
- [ ] Agenda do dia mostra "Remarcado para dd/mm" com link para o novo, em vez de "Cancelado".
- [ ] Cadeia de 3 remarcações: só o último elo conta como comparecimento ou falta; os anteriores contam como reagendamento.
- [ ] Conversão do Google Ads acompanha o agendamento novo; nenhuma conversão órfã fica em "aguardando" por causa de reagendamento.
- [ ] Backfill em dry-run reproduz os 37 pares medidos em 01/11 (menos os de importação) e, após gravar, o relatório de outubro da Essência mostra os cancelamentos reduzidos na mesma proporção.
- [ ] Texto do lembrete (PRD 027) fala em remarcar pelo link.
- [ ] `grep CANCELLED` nos três projetos revisado linha a linha; nenhuma contagem ficou com a regra antiga.

---

## Ajustes feitos pela Spec

- A operação "substituir" transacional (item B) não é viável: os métodos do service abrem e commitam conexões próprias. A Spec troca por **criar primeiro, vincular depois**, dentro de `create_appointment`, com a janela de 30 min como regra única para painel, site e bot.
- A conversão do Google Ads é **movida** para o agendamento novo (`move_conversion`), não re-datada e duplicada: o uploader sobe o evento de agendamento sem filtro de status e retrataria a compra do antigo.
- Critério "operação transacional" dos aceites fica substituído por: falha na criação não cancela nada; falha no vínculo deixa o estado de hoje e o backfill corrige.

---

## 7. Referências

- `CLAUDE.md` (padrões do projeto, migrations idempotentes)
- PRD 027 (lembrete de sessão; remove tools de remarcar e cancelar quando há site)
- PRD 032 (cadastro do paciente pelo site)
- PRDs 016/017 (conversões offline do Google Ads)
- `scheduler/src/services/appointment_service.py` (`reschedule_appointment`, `cancel_appointment`, `marca_no_show`)
- `scheduler/src/functions/public_booking/cancel_appointment.py` (contrato de segurança a copiar)
- Memória: "Regra reaplicada sobre valor pronto", "Fonte única de verdade"

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/035-reagendamento-nao-e-cancelamento.md` (01/11/2026)
- [x] Implementado em: 02/11/2026 (branch `docs/035-reagendamento-nao-e-cancelamento`, dev pendente de deploy)
- [x] Registrado em `TASKS_LOG.md`
