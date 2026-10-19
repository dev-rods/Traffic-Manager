# CLAUDE.md — checkin

Check-in de autoatendimento com pagamento, no iPad da recepção (PRD/Spec
026: `../docs/work/prd/026-checkin-autoatendimento.md`). A paciente chega,
entra com o celular e o código do WhatsApp, confirma o agendamento e paga
(Pix, crédito, débito ou dinheiro) sem passar pela pessoa do caixa.

App independente do `../booking-site/` (site público, em produção) e do
`../frontend/` (painel). Stack e padrões de código são os mesmos, ver
`../frontend/CLAUDE.md`, mas não há código compartilhado: o booking-site não
pode ser afetado por mudanças daqui.

- **Web, não app de iOS.** Roda no Safari do iPad com Acesso Guiado e
  "Adicionar à Tela de Início" (tela cheia). Nada abre outra aba nem leva
  para fora.
- **Quiosque.** Teclado numérico na própria tela (`Keypad`), alvos de toque
  ≥ 64px, volta ao início após 90 s sem toque (5 min esperando pagamento) e
  15 s depois de concluir, limpando token e cache. Ver `useIdleReset` e
  `CheckinPage`.
- **Login = o de "Meus agendamentos".** `verify/send` e `verify/confirm`;
  o token (15 min) autoriza ver o agendamento e pagar. Tudo sob
  `public/clinics/{clinicId}/checkin/*` exige a chave do booking E o token.
- **Valor e pagamento vêm do backend.** O front nunca calcula preço nem decide
  status: o valor é o gravado no agendamento, e o "pago" vem do provedor
  (webhook do Asaas, ou a consulta que o backend faz a cada polling de 3 s).
- **Cartão no celular da paciente.** Crédito e débito mostram o QR da fatura
  do Asaas; ninguém digita cartão no tablet compartilhado. Dinheiro termina o
  check-in e manda para a recepção, que dá a baixa.
- **Provedor simulado em dev.** Sem `ASAAS_API_KEY` no SSM, o backend de dev
  usa o provedor simulado e a tela mostra "Simular pagamento (teste)". Em
  prod sem chave, o pagamento responde 503 (nunca simula).
- Rota: `/:clinicId`.

## Comandos

```bash
cd checkin
npm install
npm run dev      # localhost:5175
npm run build
npm run lint     # zero warnings
npm run test
```

## Deploy

Projeto Vercel **`checkin-dev`** (sem integração com o Git: deploy só pela
CLI, nunca automático no merge), apontado para a API de **dev**:

```bash
cd checkin && npx vercel deploy --prod --yes --scope team_ZLFt6HlpGbYXZsEloIbOVq96
```

URL: https://checkin-dev-ten.vercel.app/{clinicId}. Env vars do projeto:
`VITE_API_BASE_URL` (dev) e `VITE_BOOKING_API_KEY` (a mesma chave pública do
booking-site de dev). Produção é uma fase própria (conta Asaas por clínica).
