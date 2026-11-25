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
- **A pessoa é identificada antes do preço e das datas** (PRD 061). Etapas:
  `cart -> areas -> phone -> verify -> (identity | register) -> schedule -> success`.
  Em `phone` (`PhoneStep`) só se digita o celular: a lateral segue na tabela,
  porque a cotação só honra o celular junto com o `token` de sessão (senão
  qualquer um veria o desconto de outra pessoa pelo número). O código vem
  logo em seguida (`OtpCodeForm`, um envio por celular) e a confirmação
  devolve `paciente` ({nome, faltam}) ou null: com ficha, o `IdentityConfirm`
  pergunta "Olá, {nome}, é você?" e pede só o que falta; sem ficha,
  `CustomerInfoForm` com `semCelular` pede o cadastro completo e
  `POST /cadastro` cria a ficha ANTES das datas (quem abandona fica
  cadastrado sem agendamento). Verificada, a cotação roda com celular e token
  e a lateral mostra o preço da pessoa com o motivo. `schedule` confirma
  direto com o `token`; 401 (na criação ou na cotação) refaz o código. Nome,
  CPF, e-mail e preço pessoal nunca saem da API antes do código confirmado.
- **Criar agendamento exige o código do WhatsApp** (PRD 056): a criação vai
  com `token`; sem ele a API responde 401. O token vale 30 min para o mesmo
  celular (PRD 061; eram 15). A confirmação chega pelo WhatsApp (template
  `BOOKED`, o mesmo do bot - ver `_send_confirmation_whatsapp` em
  `scheduler/src/functions/public_booking/create_appointment.py`).
- **Cadastro pela mesma régua do bot** (PRD 032): `quote.cadastro.faltam`
  diz o que falta (CPF, nascimento, e-mail); o site exibe, e tanto
  `/cadastro` quanto a criação exigem (`400 CADASTRO_INCOMPLETO`). A régua
  é `identificacao_de_paciente.CAMPOS_DO_CADASTRO`.
- **"Meus agendamentos" continua exigindo verificação** — um código de 6
  dígitos por WhatsApp (não SMS), já que sem isso qualquer pessoa veria/
  cancelaria agendamento de outra só digitando o telefone dela. O par
  celular+token verificado fica em `sessionStorage` (`utils/sessaoVerificada.ts`,
  por aba, 29 min) e é compartilhado entre o fluxo de agendamento e o modal:
  quem confirmou o código num lugar não digita outro no outro. Nunca
  `localStorage`.
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
- **Uma sessão por mês** (PRD 056). Número verificado com sessão confirmada
  futura no mesmo mês recebe 409 `SAME_MONTH_APPOINTMENT` com a sessão
  (`existing`); o `RemarcacaoDialog` avisa "Sua sessão de X será substituída
  por Y. Confirmar?", com o WhatsApp da clínica (`wa.me`), e reenvia com
  `substituir: true`. A regra mora no backend (`AppointmentService`); nunca
  "manter os dois". O 409 sem `code` continua sendo horário ocupado.
- **Sessão futura em outro mês pergunta** (PRD 060). Número verificado com
  sessão confirmada futura em OUTRO mês recebe 409 `OTHER_MONTH_APPOINTMENT`
  com `existing`; o `SessaoFuturaDialog` pergunta "remarcar essa sessão ou
  marcar mais uma?" e reenvia com `remarcarExistente: true` (a troca acima,
  da sessão de outro mês) ou `maisUma: true` (cria a segunda). Até 23/11/2026
  mês diferente criava em silêncio e quem queria remarcar ficava com duas.
- **`?meus=1` abre "Meus agendamentos" direto** (PRD 060, `BookingChrome`).
  É o link que o bot (lembrete) e a recepção mandam para remarcar ou
  cancelar; fechar o modal limpa o parâmetro. A raiz continua sendo o link
  para marcar.
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
público do dono. Env var: `VITE_BOOKING_API_KEY`. A API é chamada em `/api`
no próprio domínio: o `vercel.json` reescreve para o API Gateway (previews ->
dev, produção e domínios das clínicas -> prod, pelo host); em `npm run dev` o
proxy do Vite faz o mesmo (`VITE_API_PROXY_TARGET`). Sem CORS (PRD 055).
