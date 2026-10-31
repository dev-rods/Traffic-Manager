# CLAUDE.md — booking-site

Site público de agendamento (cliente final, sem login), clone 1:1 do fluxo do
SalonSoft "Agende Online" (ver `../docs/work/prd/009-site-agendamento-publico.md`
e `../docs/work/spec/009-site-agendamento-publico.md`). Consome os endpoints
`public/clinics/{clinicId}/*` do `../scheduler/` backend.

App independente do `../frontend/` (painel autenticado da clínica) — stack e
padrões de código idênticos, ver `../frontend/CLAUDE.md`. Diferenças:

- **Sem autenticação de usuário.** A `x-api-key` (`VITE_BOOKING_API_KEY`) é fixa
  no client e restrita aos endpoints públicos — não é segredo, é só um filtro
  básico contra bots (mesmo padrão do `LEADS_INTAKE_API_KEY` da landing page).
- **Criar agendamento não exige verificação de posse do número** — igual ao
  bot de WhatsApp, que também não pede confirmação (lá o número já é a
  própria identidade da conversa). Ao finalizar, o agendamento é criado
  direto e a confirmação chega pelo WhatsApp do cliente (template `BOOKED`,
  o mesmo que o bot usa — ver `_send_confirmation_whatsapp` em
  `scheduler/src/functions/public_booking/create_appointment.py`).
- **"Meus agendamentos" continua exigindo verificação** — um código de 6
  dígitos por WhatsApp (não SMS), já que sem isso qualquer pessoa veria/
  cancelaria agendamento de outra só digitando o telefone dela. Ver
  `src/components/OtpCodeForm.tsx` (usado só por `MyAppointmentsModal`) e
  `src/hooks/useBooking.ts`. O token de `/verify/confirm` fica só em estado
  local do modal, nunca em `localStorage`.
- **Carrinho = serviços do mesmo atendimento.** Diferente do site de
  referência (onde cada item do carrinho podia ter data/profissional
  próprios), aqui o carrinho define **quais serviços** entram numa única
  visita; data e horário são escolhidos uma vez para o carrinho inteiro.
  Isso reflete o que `AppointmentService.create_appointment` do backend
  suporta. Profissional **não** é escolhido pelo cliente: o backend atribui.
- **Preço, desconto e duração nunca são calculados no front.** O carrinho vai
  para o backend (`toCartPayload`), que responde com as mesmas funções do bot
  de WhatsApp: `/availability` (duração → horários) e `/quote` (total,
  desconto, valor final). Calcular no navegador já fez o site cobrar diferente
  do WhatsApp e oferecer horário que a criação recusava (PRD 023).
- **Agendamento repetido pede confirmação, não bloqueia.** A criação devolve
  409 `HAS_FUTURE_APPOINTMENT` (só a contagem) e o site reenvia com
  `confirmDuplicate: true` se a pessoa quiser manter os dois. O 409 sem `code`
  continua sendo horário ocupado.
- **Agenda = as próximas N datas com horário** (N = "Datas futuras" da
  clínica), no fuso da clínica — a regra mora no backend
  (`scheduler/src/services/janela_do_site.py`); o front só exibe `days`.
- Multi-tenant por `clinic_id` na URL: `/:clinicId` (lista de serviços) e
  `/:clinicId/agendar` (wizard).

## Comandos

```bash
cd booking-site
npm install
npm run dev      # localhost:5174
npm run build    # type check + build
npm run lint      # ESLint (zero warnings)
npm run test      # Vitest
```

## Deploy

Projeto Vercel próprio, independente do `frontend/`, apontado para o domínio
público do dono. Env vars: `VITE_API_BASE_URL`, `VITE_BOOKING_API_KEY`.
