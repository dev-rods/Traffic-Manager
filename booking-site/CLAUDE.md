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
- **Posse do telefone** é confirmada por um código de 6 dígitos enviado via
  WhatsApp (não SMS) — ver fluxo em `src/components/OtpConfirmModal.tsx` e
  `src/hooks/useBooking.ts`. O token retornado por `/verify/confirm` fica só em
  memória (`CartContext`), nunca em `localStorage`.
- **Carrinho = serviços do mesmo atendimento.** Diferente do site de
  referência (onde cada item do carrinho podia ter data/profissional
  próprios), aqui o carrinho define **quais serviços** entram numa única
  visita; data, horário e profissional são escolhidos uma vez para o
  carrinho inteiro (a duração somada define os horários oferecidos). Isso
  reflete o que `AppointmentService.create_appointment` do backend suporta.
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
