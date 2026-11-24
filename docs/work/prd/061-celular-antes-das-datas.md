# PRD - 061 Site identifica a pessoa antes do preço e das datas

> Gerado na fase **Research** em 23/11/2026. Use como input para a fase Spec.

---

## 1. Objetivo

No site de agendamento, pedir o celular logo depois da escolha das áreas e, a
partir daí, mostrar o preço da própria pessoa (primeira sessão, desconto
personalizado) antes de ela ver o resumo e escolher data e horário. Quem já é
paciente confirma o código do WhatsApp nesse momento, vê o nome preenchido
("Olá, Edna, é você?") e completa só o que falta no cadastro. Quem não é
paciente preenche o cadastro, confirma o código e já fica cadastrado, mesmo
que não termine o agendamento. Depois disso, escolher a data e confirmar não
pede mais nada.

---

## 2. Contexto

Em 21/11/2026 uma paciente da Nobre Laser com desconto personalizado de 26%
entrou no site, escolheu 3 áreas e viu R$ 238,00 (tabela R$ 280,00 menos os
15% da faixa por quantidade de áreas). Mandou no WhatsApp que "as 3 áreas
está dando 238" e a recepção agendou pelo painel. Nos logs da Lambda
`PublicBooking` as seis cotações dela foram sem telefone (`tel=-`): o site só
manda o celular para a cotação quando ele é digitado na etapa "Seus dados",
que vem depois de áreas, data e horário. Ela nunca chegou lá.

O cálculo está certo: com o celular, `carrinho.cota` aplica o desconto
personalizado e a criação grava `custom` (o agendamento dela de outubro, pelo
site, saiu com 26%). O defeito é de jornada: quem tem desconto combinado vê o
preço de tabela até a penúltima etapa, sem aviso de que o valor ainda cai.

Números de prod (14 dias até 23/11):

| Medida | Valor |
|---|---|
| Cotações sem telefone | 280 |
| Cotações com telefone | 112 |
| Agendamentos criados pelo site | 67 |
| Pacientes com desconto personalizado | Nobre 8 de 47; Essência 33 de 352 |
| Pacientes com cadastro incompleto (CPF, nascimento ou e-mail) | Essência 194; Nobre 1 |

Fluxo de hoje: `cart` -> `areas` -> `schedule` -> `customer` (nome, celular e
campos que faltam) -> `verify` (código) -> criação -> `success`. O código é
exigido na criação desde o PRD 056; a cotação pública aceita o celular sem
código e devolve `cadastro.faltam` (PRD 032), mas nunca nome nem motivo do
desconto, para quem digita um número qualquer não descobrir quem é paciente.

---

## 3. Decisões (confirmadas com o André em 23/11)

1. **Momento:** o celular é pedido logo depois das áreas, antes do resumo com
   preço e das datas. É uma etapa na mesma trilha, não página nem pop-up: a
   lateral de preço fica visível e a pessoa vê o valor mudar ao digitar.
2. **Nome só depois do código.** A cotação com celular continua sem nome e sem
   motivo. "Olá, Edna, é você?" só aparece depois de o código ser confirmado.
3. **Um código só, movido para esse ponto.** A etapa `verify` sai do fim e vai
   para depois do celular. Depois de verificado, escolher data e confirmar
   não pede nada. Não existe segundo código.
4. **Código cedo só para quem já é paciente.** Celular conhecido: código na
   hora, depois a confirmação de identidade e os campos que faltam. Celular
   desconhecido: cadastro completo primeiro (nome, CPF, nascimento, e-mail),
   e o código vem em seguida, antes das datas.
5. **Quem abandona depois do código fica cadastrado** como paciente sem
   agendamento. Para isso o cadastro pelo site passa a existir como ação
   própria, com o mesmo preenchimento que a criação faz hoje
   (`_get_or_create_patient`: nunca sobrescreve o que a clínica já tem).

Interpretação registrada: no item 4, "só para quem já é paciente" vale para o
instante do código (logo após o celular). Quem não é paciente também confirma
o código antes das datas, mas depois do formulário; é o que torna o item 5
possível.

---

## 4. Jornada proposta

```
cart -> areas -> phone -> [paciente] verify -> identity (+ campos que faltam) -> schedule -> success
                       -> [novo]     register -> verify (cadastra) ---------> schedule -> success
```

**phone.** Campo único de celular com o preço na lateral. Ao digitar um número
válido o site cota com o celular: o valor na lateral passa a ser o da pessoa
(primeira sessão ou desconto personalizado), sem dizer por quê. A cotação
devolve `cadastro.conhecido` e o site escolhe o ramo. Texto de apoio: "Já é
paciente? Seu desconto aparece aqui." Botão "Continuar".

**verify (paciente).** Mesmo `OtpCodeForm` de hoje; o código é enviado ao
entrar na etapa. A confirmação do código passa a devolver, além do token, o
primeiro nome e os campos que faltam. Isso só sai depois do código, logo não
abre nada para quem digitou um número que não é dele.

**identity.** "Olá, Edna, é você?" com o nome vindo do cadastro. "Sou eu":
se faltar CPF, nascimento ou e-mail, os campos aparecem aqui (mesmo
`CadastroFields`) e são gravados pela ação de cadastro; se não faltar nada,
segue direto. "Não sou eu": volta para `phone` e limpa o celular. O nome não
é editável aqui: quem está no sistema foi conferido pela clínica.

**register (novo).** Formulário completo: nome, CPF, nascimento, e-mail
(`CustomerInfoForm` sem o campo de celular, com todos os campos de cadastro).
"Continuar" leva ao código. Ao confirmar o código o site chama a ação de
cadastro com os dados e o token: a pessoa nasce como paciente ali, antes de
escolher data. Se abandonar, fica cadastrada sem agendamento (decisão 5).

**schedule.** Como hoje (dias e horários), já com o preço pessoal na lateral.
Botão "Confirmar agendamento" cria direto com o token. O `CartSummary` mostra
nome e celular confirmados.

**success.** Como hoje.

Regras de borda:

- **Token vencido ao confirmar** (criar devolve 401): o site volta para
  `verify`, reenvia o código e, confirmado, repete a criação com o mesmo
  pedido. O prazo do token de sessão sobe de 15 para 30 minutos, porque agora
  ele precisa cobrir a escolha de data; cancelar e remarcar pelo "Meus
  agendamentos" usam o mesmo escopo e ganham o mesmo prazo.
- **Token compartilhado com "Meus agendamentos".** O par celular+token
  verificado fica em `sessionStorage` (por aba, some ao fechar) e o modal de
  "Meus agendamentos" o reaproveita quando o celular é o mesmo, sem pedir
  código de novo. Vale também no sentido inverso.
- **Celular ambíguo** (duas fichas casam pelas variantes do número):
  `paciente_do_telefone` já devolve None; o site trata como novo, e a criação
  continua resolvendo como hoje.
- **CPF de outro paciente** no cadastro: 409 `CPF_EM_USO`, mostrado no
  formulário, como a criação já faz.
- **Mudar as áreas depois de verificado:** o token continua válido (é do
  celular, não do carrinho); a cotação re-roda com o celular.
- **Voltar:** de `verify` volta para `phone` (paciente) ou `register` (novo);
  de `identity` volta para `phone`; de `schedule` volta para `identity` ou
  `register` conforme o ramo, sem novo código.
- **WhatsApp da clínica fora do ar:** o envio do código falha com 502 e a
  etapa mostra o erro e o telefone da clínica, como hoje. Em prod não há
  `devCode`.

---

## 5. Escopo

### Dentro do escopo
- Nova ordem das etapas do site (`booking-site`), com as etapas `phone`,
  `identity` e `register`; `customer` deixa de existir.
- Cotação pública devolve `cadastro.conhecido`.
- Confirmação do código devolve `paciente` (`nome`, `faltam`) para o escopo
  de sessão.
- Nova ação pública de cadastro sem agendamento, com token, reaproveitando
  o preenchimento de `_get_or_create_patient`.
- Token de sessão de 15 para 30 minutos; renovação transparente no 401 da
  criação.
- Token compartilhado entre o fluxo e o "Meus agendamentos" na mesma aba.
- Testes unitários do backend e do site; roteiro de validação em dev.

### Fora do escopo
- Mudar a regra de preço, faixas ou desconto personalizado.
- Mostrar o motivo do desconto na cotação pública (continua escondido).
- Fluxos do bot e do painel.
- Check-in (`/checkin`), que tem o próprio escopo de token.
- Login persistente entre abas ou dias (o token continua de curta duração).

---

## 6. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/functions/public_booking/quote.py` | modificar | `cadastro.conhecido` |
| `scheduler/src/services/carrinho.py` | modificar | `cadastro_para_o_site` ganha `conhecido` |
| `scheduler/src/functions/public_booking/confirm_otp.py` | modificar | devolve `paciente` no escopo de sessão |
| `scheduler/src/functions/public_booking/cadastro.py` | criar | `POST /public/clinics/{clinicId}/cadastro` |
| `scheduler/src/functions/public_booking/router.py`, `scheduler/sls/functions/public_booking/interface.yml` | modificar | rota nova |
| `scheduler/src/services/appointment_service.py` | modificar | extrair o preenchimento do paciente para reuso |
| `scheduler/src/utils/booking_verification.py` | modificar | TTL do escopo sessão 30 min |
| `booking-site/src/pages/Booking.tsx` | modificar | nova máquina de etapas |
| `booking-site/src/components/PhoneStep.tsx`, `IdentityConfirm.tsx` | criar | etapas novas |
| `booking-site/src/components/CustomerInfoForm.tsx` | modificar | modo sem celular (cadastro) |
| `booking-site/src/components/MyAppointmentsModal.tsx`, `src/hooks/useBooking.ts`, `src/services/booking.service.ts`, `src/types/index.ts` | modificar | token compartilhado, ação de cadastro, tipos |
| `booking-site/src/utils/sessaoVerificada.ts` | criar | guarda do token por aba |
| testes de ambos | criar/modificar | ver Spec |

---

## 7. Dependências e riscos

- **Mais códigos enviados.** Hoje o código sai só de quem chegou ao fim; passa
  a sair de todo paciente que digita o celular, inclusive quem só olha preço.
  Em 14 dias foram 112 cotações com telefone para 67 criações; o teto do
  aumento é dessa ordem. Não é risco de infra (o z-api cobra por instância,
  não por mensagem, e não há limite de taxa no envio); é custo de jornada:
  o paciente que só pesquisa preço passa a digitar um código para ver as
  datas. Métrica a acompanhar: cotações com celular conhecido que não
  chegam à confirmação do código.
  **Plano B (decidido em 23/11):** se a desistência na etapa do código
  subir, o paciente conhecido passa a ver as datas antes do código e o
  código volta a ser exigido só ao confirmar, mantendo o preço pessoal
  desde o celular. O ramo novo não muda. Recuo barato: a etapa `verify`
  volta para antes da criação só no ramo paciente.
- **Cadastro sem agendamento** cria fichas de quem desistiu. É a decisão 5;
  o painel de pacientes passa a ter fichas sem sessão, e a recepção pode
  aproveitá-las para chamar a pessoa.
- **CloudFormation:** uma rota nova no API Gateway (prod em 418/500 após o
  PRD 055). Cabe; conferir o total no deploy de dev.
- **Mudança grande no `Booking.tsx`** e nos testes dele; o fluxo de
  remarcação pelo "Meus agendamentos" não muda, mas compartilha o token.
- **Compatibilidade:** o site antigo em cache continua funcionando com o
  backend novo (campos novos são aditivos; a rota de cadastro é nova).

---

## 8. Critérios de aceite

- [ ] Paciente com desconto personalizado vê o preço com o desconto assim que
      digita o celular, antes de qualquer data.
- [ ] Paciente conhecido: código logo após o celular; "Olá, {nome}, é você?";
      só os campos que faltam; data e confirmação sem novo código.
- [ ] "Não sou eu" volta ao celular sem deixar rastro do nome.
- [ ] Novo: cadastro completo, código, ficha criada ao confirmar o código;
      abandono depois disso deixa o paciente cadastrado sem agendamento.
- [ ] Nome ou dados nunca saem da API antes do código confirmado.
- [ ] Token vencido na confirmação pede o código de novo e conclui o mesmo
      pedido.
- [ ] "Meus agendamentos" não pede código a quem já verificou na mesma aba.
- [ ] Suite do scheduler e do site verdes; lint e build do site limpos.
- [ ] Roteiro em dev com o celular do André (Premium dev): paciente com
      desconto personalizado e número novo.

---

## 9. Referências

- PRD 032 (cadastro pelo site), PRD 056 (código antes de criar), PRD 060
  (`?meus=1`), `booking-site/CLAUDE.md`.
- Caso real: conversa da Nobre em 21/11/2026 (eventos e logs `PublicBooking`).

---

## Status

- [x] Pendente
- [x] Spec gerada: `spec/061-celular-antes-das-datas.md`
- [ ] Implementado em:
- [ ] Registrado em `TASKS_LOG.md`
