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
- **Teste em dev = Asaas sandbox.** Dev usa a conta sandbox do Asaas
  (`/dev/ASAAS_API_KEY`). Pix: o botão "Simular pagamento (teste)" confirma a
  cobrança pelo sandbox e o webhook chega como num pagamento real. Cartão: a
  tela mostra o cartão de teste aprovado (4444 4444 4444 4444, validade
  futura, CVV 123) para pagar a fatura pelo QR. Sem chave, dev cai no
  provedor simulado; prod sem chave responde 503 (nunca simula).
- **Termo de consentimento (PRD 036).** Entre confirmar o agendamento e
  escolher o pagamento, quem ainda não assinou a versão vigente do TCLE
  passa por `ConsentDataStep` (confere nome, CPF, nascimento, e-mail, uso de
  imagem; menor de idade informa o responsável, que é quem assina) e
  `ConsentSignStep` (widget embedded da ClickSign, `lib/clicksignWidget.ts`:
  código no WhatsApp e assinatura manuscrita na tela). Quem decide "precisa
  assinar" é o backend (`consentRequired` na resposta de `confirm`); o iPad
  nunca pula o termo, só a recepção dispensa pelo painel. O "assinado" vem do
  backend (webhook ou polling de 3 s), nunca do evento do widget. Em dev sem
  `CLICKSIGN_API_KEY` o provedor simulado troca o widget por "Simular
  assinatura (teste)". Os campos do termo usam o teclado do iPad
  (`TextField`), não o `Keypad`: são cinco a dez campos numa tela só.
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

Dois projetos Vercel, **sem integração com o Git** (deploy só pela CLI, nunca
automático no merge):

- **`checkin-dev`** → API de dev (Asaas sandbox). É o que `.vercel/` desta
  pasta aponta.
- **`checkin-prod`** → API de prod (https://checkin-prod.vercel.app/{clinicId}).
  Para publicar: `VERCEL_ORG_ID=team_ZLFt6HlpGbYXZsEloIbOVq96
  VERCEL_PROJECT_ID=prj_5DMFqCPTYk7bFZFYAKCikdPfUaol npx vercel deploy --prod --yes`.
  Sem `/prod/ASAAS_API_KEY`, o pagamento responde "indisponível" (503).

Dev. Sem login interativo: o token é o `/dev/VERCEL_API_TOKEN` do SSM (o
mesmo do domínio customizado, PRD 021), e o projeto vai pelo id. Nunca
`--yes` sem o id: em 04/11/2026 a CLI criou um projeto `checkin` novo em vez
de publicar no `checkin-dev`.

```bash
cd checkin && MSYS_NO_PATHCONV=1   VERCEL_TOKEN=$(aws ssm get-parameter --name /dev/VERCEL_API_TOKEN --with-decryption --query Parameter.Value --output text --profile dev-andre)   VERCEL_ORG_ID=team_ZLFt6HlpGbYXZsEloIbOVq96 VERCEL_PROJECT_ID=prj_SJRfcdvZvjCcxFcZccTgfUy0rJg7   npx vercel deploy --prod --yes --scope team_ZLFt6HlpGbYXZsEloIbOVq96
```

Para o `checkin-prod`, o mesmo comando com `/prod/VERCEL_API_TOKEN` e o
`VERCEL_PROJECT_ID` de cima. Conferir depois: a URL serve o bundle novo
(`curl` no `index-*.js` procurando um texto da tela nova).

URL: https://checkin-dev-ten.vercel.app/{clinicId}. Env vars do projeto:
`VITE_API_BASE_URL` (dev) e `VITE_BOOKING_API_KEY` (a mesma chave pública do
booking-site de dev). O que falta para ligar o pagamento em prod está no
PRD 026 (§7).
