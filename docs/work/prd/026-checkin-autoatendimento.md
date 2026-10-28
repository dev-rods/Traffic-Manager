# PRD — 026 Check-in de autoatendimento com pagamento (iPad na recepção)

> Gerado na fase **Research**. Use como input para a fase Spec.
> Origem: conversa Rodrigo + André (18/10/2026), depois da reunião sobre
> pagamentos. Primeira fase só em **dev**: a ferramenta é para validar com o
> público antes de ir para as clínicas.

---

## 1. Objetivo

Tirar a cobrança das mãos da recepção. A paciente chega, faz o check-in num
iPad, confirma o agendamento e paga sozinha. A recepção só orienta e entrega
o tablet.

> "Tira a necessidade de contratar 2 pessoas (uma para atender e outra para
> cobrar) e/ou ganhar tempo de quem atende." — André

A inspiração é o totem do McDonald's, com uma diferença: o sistema já sabe o
que a pessoa agendou. Não há cardápio, só confirmação e pagamento.

## 2. Fluxo (fase 1)

1. A recepção orienta a paciente a fazer o check-in no iPad.
2. **Login**: celular + código pelo WhatsApp. São o mesmo `verify/send` e
   `verify/confirm` de "Meus agendamentos" (task 015).
3. **Resumo do agendamento futuro mais próximo**: data, horário, áreas,
   preço e nome de quem agendou. Se o número tiver mais de um agendamento
   futuro (ex.: mãe e filha), a pessoa escolhe qual. Toca em **Confirmar**,
   o que registra o check-in.
4. **CPF**, só quando o sistema não tem o CPF de quem paga. O Asaas exige
   CPF do pagador.
5. **Método de pagamento**: Pix, Crédito, Débito ou Dinheiro.
   - **Pix**: o iPad mostra o QR code e o "copia e cola". A paciente paga
     pelo celular, e o iPad confirma sozinho quando o pagamento entra.
   - **Crédito / Débito**: o iPad mostra o QR code da fatura do Asaas. A
     paciente abre no celular e paga com cartão (a fatura do Asaas oferece
     crédito e débito). O iPad confirma sozinho.
   - **Dinheiro**: a cobrança é criada como "aguardando recebimento" e o
     iPad orienta a pagar na recepção. A baixa no Asaas ("recebido em
     dinheiro") é feita pela recepção. Endpoint nesta fase; botão no painel
     na fase 2.
6. **Pronto**: tela de confirmação e, depois de alguns segundos, o iPad volta
   ao início sozinho.

### 2.1 Modo quiosque

- App web, não app de iOS: a mesma stack do booking-site, aberta no Safari
  com **Acesso Guiado** e "Adicionar à Tela de Início" (tela cheia).
- Volta ao início depois de **90 s sem toque** e ao terminar, apagando o
  token e os dados da paciente anterior.
- Nada abre outra aba; nenhum link leva para fora.
- Layout para iPad em pé e deitado, com alvos de toque grandes (≥ 56 px).

## 3. Decisões de desenho

| Tema | Decisão | Por quê |
|---|---|---|
| App | Novo app `checkin/` no monorepo, separado do `booking-site/` | O booking-site está em produção e não deve ser tocado. O quiosque tem outro ciclo (dev primeiro), outro layout e outro modo de sessão. |
| Login | OTP por WhatsApp, o mesmo do "Meus agendamentos" | Já existe e prova a posse do número. O token (15 min) autoriza ver o agendamento e pagar. |
| Rotas | Uma rota coringa `public/clinics/{clinicId}/checkin/{proxy+}` (ANY) na Lambda `PublicBooking`, mais `public/asaas/webhook` | A stack está em 438/500 recursos do CloudFormation. Uma rota por endpoint gastaria ~4 recursos cada; a coringa gasta ~4 no total. |
| Débito | Cobrança `CREDIT_CARD` + fatura hospedada (`invoiceUrl`) | A API do Asaas não cria cobrança de débito; a fatura hospedada oferece débito para cobranças de cartão. |
| Cartão no iPad | QR code da fatura, pago no celular da paciente | Digitar cartão num tablet compartilhado expõe o dado e é lento. No celular dela, ela usa o autopreenchimento e a carteira digital. |
| Dinheiro | Cobrança criada e marcada `AWAITING_CASH`; a recepção dá baixa (`receiveInCash`) | Só quem recebe o dinheiro pode confirmar. Assim o caixa fica num lugar só (Asaas + nosso registro). |
| Valor | `appointments.final_price_cents`, o valor gravado com desconto | Mesma regra do site e do bot. Sem valor (a combinar), o iPad manda para a recepção. |
| Provedor | Interface `PaymentProvider` com `asaas` (sandbox/produção) e `simulado` (só dev) | Ainda não há chave do Asaas. O simulado permite validar a experiência em dev agora; com `ASAAS_API_KEY` no SSM, vira o Asaas de verdade. O simulado é recusado fora de dev. |
| Limite de códigos | Removido o limite de 3 códigos a cada 15 min por número; continua o de 5 tentativas erradas por código | O "Muitos códigos solicitados" travou o teste do Rodrigo no iPad (reenviar e recomeçar também contavam). Decisão dele em 19/10/2026: tirar. O efeito chega ao booking-site junto com esta branch. |
| Código em dev | Em dev, se o WhatsApp falhar, o código volta na resposta e aparece na tela | A clínica de teste não tem instância do z-api ("Instance not found"); sem isso ninguém testa o login. Fora de dev, nunca. |
| Conta Asaas | Fase 1: uma conta por stage (`/{stage}/ASAAS_API_KEY`) | Fase 1 é validação em dev. Uma conta por clínica (o dinheiro cai na conta dela) vem na fase de produção. |

## 4. Dados

- **`scheduler.appointment_payments`** (nova): `id`, `clinic_id`,
  `appointment_id`, `method` (`PIX|CREDIT_CARD|DEBIT_CARD|CASH`),
  `amount_cents`, `status` (`PENDING|AWAITING_CASH|PAID|CANCELLED|FAILED`),
  `provider` (`asaas|simulado`), `provider_payment_id`, `invoice_url`,
  `pix_payload`, `pix_qr_image`, `payer_name`, `payer_cpf`, `paid_at`,
  `created_at`, `updated_at`. No máximo **um pagamento ativo** por
  agendamento (índice único parcial): trocar de método cancela o anterior.
- **`scheduler.appointments.checked_in_at`** (nova coluna).
- **`scheduler.payment_webhook_events`** (nova): `event_id` único, para
  descartar entrega repetida (o Asaas entrega "pelo menos uma vez").

## 4.1 Fase 2: o pagamento no painel (19/10/2026, pedido do Rodrigo)

- **Agenda**: o detalhe do agendamento mostra o check-in ("Feito às 08:52") e
  o pagamento ("Pago · Pix às 08:54", "Aguardando dinheiro", "Aguardando
  Pix", "Não pago"). Com "Aguardando dinheiro", aparece o botão **Recebi em
  dinheiro**, que dá a baixa aqui e no Asaas (`receiveInCash`).
- **Relatórios → aba Caixa** (só admin): Recebido, Previsto pelas sessões e
  Falta receber; total por forma de pagamento; lista do que falta receber
  (com o botão de dinheiro) e lista de recebimentos. Períodos: hoje, ontem,
  7 dias, este mês.
- **Duas datas, de propósito**: o previsto é pela data da SESSÃO e o
  recebido pela data em que o dinheiro ENTROU (no fuso da clínica). É isso
  que bate com o extrato do Asaas e com a gaveta. Por isso a diferença entre
  os dois não é "o que falta": o que falta é a lista de pendências (sessão
  confirmada até hoje, com valor, sem pagamento confirmado).
- **Quem pode**: a baixa em dinheiro é da recepção (`agenda.escrever`), que
  é quem recebe a nota. O resumo do caixa é do admin, como os relatórios.
  Funcionário que não vê valores continua sem ver o valor do pagamento (o
  servidor remove), mas vê se está pago.
- **Rotas**: Lambda nova `Caixa` com rota coringa
  `clinics/{clinicId}/caixa/{proxy+}` (`GET resumo`, `POST
  pagamentos/{id}/dinheiro`). A baixa saiu da rota pública do check-in.

## 5. Fora do escopo (fases seguintes)

- Documentos no check-in (termo de consentimento, anamnese) e o envio na
  véspera para preencher pelo celular.
- Conta Asaas por clínica e deploy em produção.
- Reembolso e cancelamento de pagamento já feito.
- Maquininha integrada.

## 6. Critérios de aceite (dev)

1. Login com celular e código; número sem agendamento futuro vê "Não
   encontramos agendamento" e um botão de voltar.
2. Número com dois agendamentos futuros escolhe um; os dois mostram o nome.
3. Confirmar grava `checked_in_at`.
4. Sem CPF conhecido, pede o CPF e valida os dígitos verificadores.
5. Pix: mostra QR e "copia e cola" e confirma sozinho quando pago (no
   simulado, por um botão "simular pagamento" visível só em dev).
6. Crédito/Débito: mostra o QR da fatura e confirma sozinho quando pago.
7. Dinheiro: mostra "pague na recepção"; o pagamento fica `AWAITING_CASH`.
8. Trocar de método antes de pagar cancela a cobrança anterior.
9. Agendamento já pago mostra "pagamento confirmado", sem nova cobrança.
10. Webhook repetido não muda nada; webhook com token errado é recusado.
11. 90 s sem toque volta ao início e apaga os dados.
12. O `booking-site` não muda (nenhum arquivo dele no diff).

## 7. Status

- [x] Spec gerada (`spec/026-checkin-autoatendimento.md`)
- [x] Implementado (2026-10-19)
- [x] Deploy dev (2026-10-19): backend `clinic-scheduler-infra-dev` com
  create-deployment, migrations só da 026 no banco de dev, app no projeto
  Vercel `checkin-dev` (https://checkin-dev-ten.vercel.app/{clinicId}). Ver
  `scheduler/tests/integration/026-checkin-autoatendimento.md`.
- [x] Asaas sandbox em dev (2026-10-28): chave do André em
  `/dev/ASAAS_API_KEY` (SecureString), token gerado em
  `/dev/ASAAS_WEBHOOK_TOKEN` e webhook cadastrado na conta sandbox
  (`PAYMENT_RECEIVED`, `PAYMENT_CONFIRMED`, `PAYMENT_DELETED`,
  `PAYMENT_REFUNDED`, envio sequencial) apontando para
  `/dev/public/asaas/webhook`. Ponta a ponta validado: Pix (QR real,
  "Simular pagamento" pelo `/sandbox/payment/{id}/confirm`, webhook
  `PAYMENT_RECEIVED`), cartão (fatura paga com o cartão de teste
  4444 4444 4444 4444, webhook `PAYMENT_CONFIRMED`) e dinheiro (baixa pela
  recepção com `receiveInCash`). A conta sandbox precisa de chave Pix
  cadastrada para gerar QR, e a de produção também vai precisar.
- [ ] Produção (conta Asaas por clínica)
