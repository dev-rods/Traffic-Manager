# 061 - Site identifica a pessoa antes do preço e das datas

O site pede o celular logo depois das áreas. A cotação com o celular já é o
preço da pessoa (primeira sessão, desconto personalizado), sem motivo, e diz
se o número é de um paciente (`cadastro.conhecido`). Paciente confirma o
código na hora e a confirmação devolve `paciente` ({primeiro nome, faltam});
quem não é paciente preenche o cadastro, confirma o código e a ficha nasce
pela rota nova `POST /public/clinics/{clinicId}/cadastro`, antes de qualquer
data. O token de sessão passou de 15 para 30 minutos.

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
| 2 | `POST quote` com celular de paciente | `cadastro.conhecido: true`, `faltam` do cadastro dela, preço com o desconto dela, `discountReason: null`, SEM nome |
| 3 | `POST quote` com celular desconhecido | `cadastro.conhecido: false`, `faltam: [birth_date, cpf, email]` |
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

## Roteiro no navegador (dev, Vercel preview do PR ou `npm run dev`)

Clínica Premium dev; celular do André.

**A. Paciente com desconto personalizado**

1. No banco de dev: `UPDATE scheduler.patients SET custom_discount_pct = 26 WHERE clinic_id = '<C>' AND phone = '5511970522647'`.
2. Site: escolher áreas, "Continuar". A etapa "Seu celular" aparece com o preço de tabela na lateral.
3. Digitar o celular: a lateral muda para o valor com 26%, sem dizer o motivo. Nenhum nome na tela.
4. "Continuar" -> "Confirme seu celular"; o código chega no WhatsApp.
5. Código -> "Olá, André! É você?". Se faltar algo no cadastro, "Sou eu" pede só isso.
6. "Sou eu" -> datas e horários, lateral com nome e celular -> "Confirmar agendamento" cria sem novo código.
7. Abrir "Meus agendamentos" no mesmo tab: não pede código; lista o agendamento.
8. Limpar: apagar o agendamento pelo painel e zerar o `custom_discount_pct`.

**B. Celular novo**

1. No banco de dev: soft-delete da ficha do André (`UPDATE scheduler.patients SET deleted_at = NOW() WHERE ...`) ou usar o fluxo após `DELETE patients/{id}` pelo painel.
2. Site: áreas -> celular -> "Seus dados" (sem campo de celular) -> nome, CPF, nascimento, e-mail -> "Continuar".
3. Código -> ao confirmar, a ficha é criada (`[PublicBooking][cadastro] ... novo=True`) e aparece "Escolha o dia".
4. Fechar a aba aqui: no painel, a ficha existe sem agendamento (decisão 5 do PRD).

**C. "Não sou eu"**

1. Fluxo A até "É você?"; clicar "Não sou eu": volta a "Seu celular" com o campo vazio e sem nome na tela.

## Resultado

- dev (23/11, layer 216): smoke de API sem OTP 6/6 (`smoke_061.py`, scratchpad): quote sem celular `cadastro: null`; celular do André `conhecido: true` sem nome e sem motivo; celular sem ficha `conhecido: false` faltando tudo; `/cadastro` sem token e com token inválido 401; confirm com código errado 400 sem `paciente`. A rota nova levou ~1 min para responder depois do deploy (antes: "Missing Authentication Token"). Casos 4, 6, 9 a 16 e o roteiro no navegador dependem do código no WhatsApp do André.
- prod (23/11, layer 171): o mesmo smoke de API sem OTP 6/6 na Nobre (celular do André é paciente com cadastro completo: `conhecido: true, faltam: []`). Site sobe pela Vercel no merge do PR #252.
