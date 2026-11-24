# 061 - Site identifica a pessoa antes do preço e das datas

O site pede o celular logo depois das áreas e o código em seguida. A
confirmação devolve `paciente` ({primeiro nome, faltam}) ou null; só então a
cotação roda com celular E token e vira o preço da pessoa (primeira sessão,
desconto personalizado), com o motivo. Sem token o celular é ignorado e a
cotação é a de tabela (revisão de 24/11: antes bastava o celular, e qualquer
um via o desconto de outra pessoa). Quem não tem ficha preenche o cadastro e
a ficha nasce pela rota `POST /public/clinics/{clinicId}/cadastro`, antes de
qualquer data. O token de sessão passou de 15 para 30 minutos.

## Pré-requisitos

```bash
API=https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev
BKEY=$(aws ssm get-parameter --name /dev/BOOKING_INTAKE_API_KEY --with-decryption --query Parameter.Value --output text)
C=clinicadepilacaopremium-3fbce9
```

**O código de verificação é enviado pelo WhatsApp de verdade, também em dev.**
Só usar o celular do André (`5511970522647`). Nunca número inventado.

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | `POST quote` sem `phone` | `quote.cadastro` = null; preço de tabela com a faixa por áreas |
| 2 | `POST quote` com celular SEM token (site antigo) | 200, cotação cega: preço de tabela, `cadastro: null` (24/11) |
| 2b | `POST quote` com celular e token inválido | 401 `TOKEN_INVALIDO` (24/11) |
| 2c | `POST quote` com celular de paciente e token válido | `cadastro.conhecido: true`, `faltam` do cadastro dela, preço com o desconto dela, `discountReason` presente, SEM nome |
| 3 | `POST quote` com celular desconhecido e token válido | `cadastro.conhecido: false`, `faltam: [birth_date, cpf, email]` |
| 4 | `POST verify/send` com o celular do André | 200; código chega no WhatsApp |
| 5 | `POST verify/confirm` com código errado | 400; corpo sem `paciente` |
| 6 | `POST verify/confirm` com o código certo | 200 `token` + `paciente: {nome: "<primeiro nome>", faltam: [...]}` (ou null se não há ficha) |
| 7 | `POST verify/confirm` com `scope: documentos` | 200 sem `paciente` |
| 8 | `POST cadastro` sem token | 401 |
| 9 | `POST cadastro` com token e só `phone` | 200 `paciente` com o estado da ficha; nada gravado |
| 10 | `POST cadastro` celular novo sem `fullName` | 400 `CADASTRO_INCOMPLETO` `faltam: ["name"]` |
| 11 | `POST cadastro` celular novo faltando campo | 400 `CADASTRO_INCOMPLETO` com os que faltam |
| 12 | `POST cadastro` com CPF de outro paciente | 409 `CPF_EM_USO` |
| 13 | `POST cadastro` completo para celular novo | 200; ficha em `scheduler.patients` sem agendamento; resposta só com primeiro nome e `faltam: []` |
| 14 | `POST cadastro` de novo com os mesmos dados | 200; `updated_at` não muda (COALESCE) |
| 15 | `POST appointments` com token emitido há 20 min | 201 (token vale 30 min) |
| 16 | Painel: `GET clinics/{C}/patients` | a ficha do caso 13 aparece, sem agendamentos |

## Roteiro no navegador (dev)

Os previews da Vercel ficam atrás de SSO (PRD 055), então o caminho é o site
local: `cd booking-site && npm run dev` com `.env` apontando o proxy para a
API de dev e a `VITE_BOOKING_API_KEY` de dev (SSM `/dev/BOOKING_INTAKE_API_KEY`).
Clínica Premium dev (`/clinicadepilacaopremium-3fbce9`); celular do André.

**A. Paciente com desconto personalizado**

1. No banco de dev: `UPDATE scheduler.patients SET custom_discount_pct = 26 WHERE clinic_id = '<C>' AND phone = '5511970522647'`.
2. Site: escolher áreas, "Continuar". A etapa "Seu celular" aparece com o preço de tabela na lateral.
3. Digitar o celular: a lateral NÃO muda (24/11). Nenhum nome na tela.
4. "Continuar" -> "Confirme seu celular"; UM código chega no WhatsApp.
5. Código -> "Olá, André! É você?" e a lateral passa ao valor com 26%, com "Desconto especial". Se faltar algo no cadastro, "Sou eu" pede só isso.
6. "Sou eu" -> datas e horários, lateral com nome e celular -> "Confirmar agendamento" cria sem novo código.
7. Abrir "Meus agendamentos" no mesmo tab: não pede código; lista o agendamento.
8. Limpar: apagar o agendamento pelo painel e zerar o `custom_discount_pct`.

**B. Celular novo**

1. No banco de dev: soft-delete da ficha do André (`UPDATE scheduler.patients SET deleted_at = NOW() WHERE ...`) ou usar o fluxo após `DELETE patients/{id}` pelo painel.
2. Site: áreas -> celular -> "Confirme seu celular" -> código -> "Seus dados" (sem campo de celular) -> nome, CPF, nascimento, e-mail -> "Continuar".
3. Ao enviar, a ficha é criada (`[PublicBooking][cadastro] ... novo=True`) e aparece "Escolha o dia".
4. Fechar a aba aqui: no painel, a ficha existe sem agendamento (decisão 5 do PRD).

**C. "Não sou eu"**

1. Fluxo A até "É você?"; clicar "Não sou eu": volta a "Seu celular" com o campo vazio e sem nome na tela.

## Resultado

- dev (23/11, layer 216): smoke de API sem OTP 6/6 (`smoke_061.py`, scratchpad): quote sem celular `cadastro: null`; celular do André `conhecido: true` sem nome e sem motivo; celular sem ficha `conhecido: false` faltando tudo; `/cadastro` sem token e com token inválido 401; confirm com código errado 400 sem `paciente`. A rota nova levou ~1 min para responder depois do deploy (antes: "Missing Authentication Token"). Casos 4, 6, 9 a 16 e o roteiro no navegador dependem do código no WhatsApp do André.
- prod (23/11, layer 171): o mesmo smoke de API sem OTP 6/6 na Nobre (celular do André é paciente com cadastro completo: `conhecido: true, faltam: []`). Site sobe pela Vercel no merge do PR #252.
- dev (24/11, roteiro A no site local, versão de 23/11): fluxo inteiro ok. Logs `PublicBooking`: cotação com o celular já a R$ 114,70 (26%) antes do código; `verify/send` 2x no mesmo segundo (StrictMode em dev; o André recebeu dois códigos); `confirm` 1x escopo sessão; `cadastro` completou cpf, birth_date, email; `create` 25/11 16:00 com pct=26; depois uma chamada silenciosa (Meus agendamentos) sem novo código. Também saiu uma cotação para um número de 10 dígitos digitado pela metade. Resultado: decisão 6 do PRD (cotação só com token) e guarda contra o envio duplo.
