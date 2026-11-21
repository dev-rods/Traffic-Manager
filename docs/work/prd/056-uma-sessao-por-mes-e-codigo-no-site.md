# PRD - 056 Uma sessão por mês: código sempre no site e troca do agendamento existente

> Gerado na fase **Research** em 21/11/2026. Use como input para a fase Spec.

---

## 1. Objetivo

Impedir que a mesma paciente tenha **dois agendamentos futuros no mesmo mês**
na mesma clínica, por qualquer porta (site, bot, painel), e fazer o site
tratar esse caso como o bot já trata: a sessão existente é **remarcada** para
a data e os serviços escolhidos agora, com aviso claro à pessoa e o WhatsApp da
clínica para dúvidas.

Para o site poder mexer no agendamento existente sem risco, **todo agendamento
pelo site passa a exigir o código do WhatsApp** antes de confirmar. A regra do
mês só é avaliada depois do código.

Mês diferente não bloqueia: a paciente pode estar antecipando a reserva da
próxima sessão.

---

## 2. Contexto

### 2.1 O que o sistema faz hoje

| Porta | Regra atual | Origem |
|---|---|---|
| Site (`booking-site/`) | Criar não exige código. Se o número já tem **qualquer** agendamento futuro, a API devolve 409 `HAS_FUTURE_APPOINTMENT` só com a contagem e o site pergunta "Quer manter os dois?". Com `confirmDuplicate: true` cria. Não mostra data nem serviço do existente, porque o número pode ser de outra pessoa. | PRD 024 (`create_appointment.py`, `DuplicateBookingDialog.tsx`) |
| Bot (WhatsApp) | Quem tem sessão futura e pede mudança é **alteração** (`alterar_agendamento`: áreas, data, hora). `book_appointment` é recusado pela tool (`_recusa_segunda_sessao`) a menos que venha `segunda_sessao=true`, que o modelo só manda se a pessoa disser com todas as letras que quer duas. Não olha mês. | PRD 045 (`ai_tools.py`), skill `paciente_com_horario` |
| Painel (`frontend/`) | Nenhuma verificação: a recepção cria quantos quiser para o mesmo paciente. | `appointment/create.py` |

Em código, "agendamento futuro" é `status = 'CONFIRMED' AND appointment_date >=
hoje` na clínica (`get_active_appointments_by_phone`, pelas variantes do
número).

### 2.2 Por que mudar

- Sessão de depilação a laser é a cada ~30 dias. Duas sessões futuras no mesmo
  mês são, na prática, engano ou remarcação mal feita. 81% dos cancelamentos
  vindos do site eram remarcações (PRD 035).
- "Manter os dois" no site produz exatamente isso: linha nova, antiga de pé,
  duas sessões na agenda. O bot já foi corrigido em 09/11 (PRD 045); o site e
  o painel não.
- Hoje o site não pode substituir o agendamento existente porque criar não
  exige posse do número: digitar o celular de outra pessoa apagaria a sessão
  dela. Exigir o código antes de confirmar fecha essa porta e permite mostrar
  o agendamento existente na tela.

### 2.3 Decisões anteriores que este PRD toca

- **PRD 024**: "Manter os dois" e `confirmDuplicate` saem.
- **PRD 035/054**: remarcar é "antigo encerrado com vínculo + novo". Trocar o
  agendamento existente pelo site **não é cancelar**: usa o mesmo caminho de
  alteração (áreas, data, hora) que bot e painel usam. Cancelar de verdade
  gravaria um cancelamento falso no relatório e, no próprio dia, uma falta
  (regra da 054).
- **PRD 032**: o cadastro faltante continua sendo pedido na mesma etapa de
  dados; o código entra depois dela.
- **PRD 048**: o OTP já tem `scope` (`sessao` 15 min, `documentos` 2 h). O
  token de `sessao` já autoriza criar/listar/cancelar/remarcar.

---

## 3. Escopo

### Dentro do escopo

**A. Regra do mês no backend (fonte única)**

- Em `AppointmentService`: ao **criar** ou ao **mover a data** de um
  agendamento, se o paciente (pelas variantes do número, mesma clínica) já tem
  outro agendamento `CONFIRMED` futuro **no mesmo ano-mês** da data alvo,
  recusar com erro próprio (ex.: `SessaoNoMesmoMes`), levando o agendamento
  existente (id, data, hora, áreas). O próprio agendamento sendo movido não
  conta.
- "Futuro" e "mês" no fuso da clínica (`relogio.agora_na_clinica`).
- A verificação **não** tem flag para pular. Mês diferente passa sempre.
- Guarda de teste: a regra em um lugar só; handlers do site, do bot e do
  painel não reimplementam a consulta.

**B. Site: código sempre, depois a regra**

- Fluxo: carrinho -> áreas -> data/hora -> dados (com cadastro faltante, PRD
  032) -> **código do WhatsApp** (`verify/send` + `verify/confirm`, mesmo
  `OtpCodeForm` de "Meus agendamentos") -> confirmar.
- `POST public/.../appointments` passa a exigir `token` (401 sem ele, como
  `cancel` e `reschedule`). `confirmDuplicate` e `HAS_FUTURE_APPOINTMENT`
  saem.
- Se a criação cair na regra do mês, a API devolve 409 com código próprio
  (ex.: `SAME_MONTH_APPOINTMENT`) e o agendamento existente (data, hora,
  áreas), que agora pode ser mostrado porque o número foi verificado.
- O site mostra um diálogo: "Você já tem uma sessão nesta clínica em
  **{data} às {hora}**. Ao confirmar, ela será remarcada para **{nova data}
  às {nova hora}** com os serviços escolhidos agora. Qualquer dúvida, fale com
  a clínica pelo WhatsApp **{telefone}**." Botões: **Remarcar** / Voltar.
- "Remarcar" chama o endpoint de remarcação pública estendido para receber o
  carrinho novo (`serviceIds`/`serviceAreaPairs`), que usa o mesmo caminho de
  alteração do bot e do painel: áreas antes, data e hora depois, conflito
  conferido contra a data final. Mesma data: só move o horário.
- Telefone da clínica vem do bootstrap (`clinics.phone`). Sem telefone
  cadastrado, a frase termina em "fale com a clínica pelo WhatsApp".
- Tela de sucesso diz "Agendamento remarcado" nesse caso.
- Mais de um agendamento futuro no mesmo mês (dado legado): o diálogo troca o
  **mais próximo**; os demais continuam como estão e a regra impede novos.

**C. Bot**

- `_recusa_segunda_sessao`: sessão futura **no mesmo mês** da data pedida
  recusa sempre, sem a saída `segunda_sessao=true`, apontando
  `alterar_agendamento`. Mês diferente: comportamento atual (recusa, a menos
  que a pessoa tenha pedido duas).
- `alterar_agendamento` para outro mês em que já há sessão: a regra do
  backend recusa e a tool devolve o que fazer ("já tem sessão em {data}
  nesse mês; alterar aquela ou escolher outro mês").
- Skill `paciente_com_horario`: uma linha explicando que duas sessões só em
  meses diferentes. Conferir se o prompt da clínica em prod (tabela) fala do
  assunto, porque o default do código não é o prompt de prod.

**D. Painel**

- Criar ou editar data para um mês em que o paciente já tem sessão futura
  devolve 409 com o agendamento existente; o modal mostra "{nome} já tem
  sessão em {data} às {hora}. Remarque essa sessão em vez de criar outra" com
  atalho para a edição dela. Sem sobreposição: a recepção remarca a existente.

**E. Docs e testes**

- Roteiro `scheduler/tests/integration/056-...md`; Postman do endpoint de
  remarcação estendido; unit tests da regra (mesmo mês, mês seguinte, virada
  de ano, próprio agendamento excluído, status não confirmado não conta);
  teste do site para o fluxo com código e o diálogo.
- Atualizar `booking-site/CLAUDE.md` (hoje diz que criar não exige código e
  que repetido pede confirmação) e `docs/work/prd/024` com ponteiro para este.

### Fora do escopo

- Limitar por **serviço** (duas áreas diferentes no mesmo mês continuam
  sendo uma sessão só, pela regra de hoje).
- Intervalo mínimo em dias entre sessões (30 dias) em vez de mês-calendário.
  O André escolheu mês-calendário: simples de explicar e permite antecipar a
  reserva do mês seguinte.
- Mudar quem pode agendar duas no mesmo mês por exceção médica: não há
  override, nem no painel.

---

## 4. Decisões (confirmadas pelo André em 21/11/2026)

1. **Código do WhatsApp sempre, antes de confirmar o agendamento pelo site.**
   A regra do mês só roda depois do código. Custo: uma mensagem de WhatsApp a
   mais por agendamento e uma etapa a mais no fluxo.
2. **Mesmo mês-calendário bloqueia em todas as portas**; mês diferente nunca
   bloqueia (antecipar reserva é legítimo).
3. **No site, o caso é tratado como remarcação da sessão existente**, com
   aviso explícito e o WhatsApp da clínica para dúvidas. Nunca "manter os
   dois".
4. **Trocar é alterar, não cancelar + criar** (PRD 054): sem cancelamento
   falso nem falta no relatório.

### Pendências (propostas, aguardando confirmação)

- Painel: bloqueio com atalho para editar a existente (proposta), ou
  sobreposição com motivo como na 054. *Proposta: bloquear.*
- Mais de uma sessão futura no mesmo mês (legado): trocar a mais próxima.
  *Proposta: a mais próxima.*
- Texto exato do diálogo e do sucesso ("Agendamento remarcado").

---

## 5. Áreas / arquivos impactados

| Área | Arquivo | Mudança |
|---|---|---|
| Regra | `scheduler/src/services/appointment_service.py` | verificação do mesmo mês em criar e mover data; erro próprio com o existente |
| Site API | `scheduler/src/functions/public_booking/create_appointment.py` | exige `token`; remove `confirmDuplicate`/`HAS_FUTURE_APPOINTMENT`; 409 do mês com o existente |
| Site API | `scheduler/src/functions/public_booking/reschedule_appointment.py` | aceita carrinho novo; usa o caminho de alteração (áreas + data/hora) |
| Site API | `scheduler/src/functions/public_booking/bootstrap.py` | já devolve `phone`; conferir |
| Bot | `scheduler/src/services/ai_tools.py` | `_recusa_segunda_sessao` por mês; tratamento do erro em `alterar_agendamento` |
| Bot | `scheduler/src/services/skills/__init__.py` | linha na skill `paciente_com_horario` |
| Painel API | `scheduler/src/functions/appointment/create.py`, `update.py` | 409 com o existente |
| Site | `booking-site/src/pages/Booking.tsx` | etapa de código; diálogo de remarcação; sucesso |
| Site | `booking-site/src/components/DuplicateBookingDialog.tsx` | vira diálogo de remarcação (ou novo componente) |
| Site | `booking-site/src/services/booking.service.ts`, `types/index.ts`, `hooks/useBooking.ts` | `token` na criação; payload da remarcação |
| Painel | `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` e edição | mensagem do 409 com atalho |
| Testes | `scheduler/tests/unit/...`, `booking-site/src/**/*.test.tsx` | regra, fluxo com código, diálogo |
| Docs | `booking-site/CLAUDE.md`, `tests/integration/056-...md`, `tests/postman/...` | |

---

## 6. Dependências e riscos

- **OTP em dev**: com o WhatsApp de dev fora, `verify/send` devolve `devCode`;
  o fluxo continua testável.
- **Conversão**: agendamento criado com código a mais no caminho pode derrubar
  a conversão do site. Medir no relatório de origem antes e depois (semana).
- **Prompt em prod**: a skill é código, mas o prompt da clínica mora no banco;
  conferir se precisa de ajuste em prod.
- **Dado legado**: pacientes que já têm duas sessões no mesmo mês não são
  tocados; a regra só impede novos.
- **Stack**: nenhuma rota nova (o endpoint de remarcação já existe). 418/500
  depois da 055.

---

## 7. Critérios de aceite

1. Site: não há mais confirmação sem código; `POST appointments` sem `token`
   responde 401.
2. Site: número verificado com sessão futura no mesmo mês vê o diálogo com a
   data da sessão existente e o WhatsApp da clínica; "Remarcar" encerra a
   antiga com vínculo e cria a nova com o carrinho escolhido; a agenda do
   painel mostra uma só.
3. Site: sessão futura em **outro** mês não interfere; o agendamento é criado.
4. Bot: pedido de outra sessão no mesmo mês vira alteração; em outro mês,
   comportamento atual.
5. Painel: criar ou mover para um mês com sessão futura do mesmo paciente
   responde 409 e a tela aponta a sessão existente.
6. Relatório: a troca pelo site não aparece como cancelamento nem como falta.
7. `pytest`, build, lint e vitest dos apps verdes; `confirmDuplicate` e
   `HAS_FUTURE_APPOINTMENT` não existem mais no código.

---

## 8. Referências

- PRD 024 (meus agendamentos e aviso), 032 (cadastro no site), 035
  (remarcação), 045 (bot: alteração x segunda sessão), 048 (OTP com escopo),
  054 (desfecho e remarcação com vínculo).
- `scheduler/src/utils/booking_verification.py` (código, token, escopos).

---

## Status (preencher após conclusão)

- [ ] Spec gerada: `docs/work/spec/056-uma-sessao-por-mes-e-codigo-no-site.md`
- [ ] Implementado em dev: (data)
- [ ] Implementado em prod: (data)
- [ ] Registrado em `TASKS_LOG.md`
