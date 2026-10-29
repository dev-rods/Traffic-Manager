# PRD 029 — Link de cobrança pelo WhatsApp

**Data:** 2026-10-28
**Origem:** pedido do Rodrigo depois do teste do check-in (PRD 026/028): "para
quem não conseguir pagar no momento do check-in, vale um fluxo de disparar
pelo painel um link de cobrança pelo WhatsApp".

## 1. Problema

O check-in do iPad cobra na hora. Quando a paciente não consegue pagar ali
(sem celular, sem saldo, com pressa, ou nem passou pelo iPad), a sessão fica
em "Falta receber" no Caixa e a única saída é cobrar em mão. Não há como
mandar a cobrança para ela pagar depois.

## 2. O que muda

1. **Botão "Enviar link pelo WhatsApp"** no detalhe do agendamento (agenda) e
   em cada linha de "Falta receber" (Relatórios → Caixa). Quem pode: quem
   escreve na agenda (recepção e admin), como a baixa em dinheiro.
2. **A cobrança é do Asaas com forma livre** (`billingType: UNDEFINED`): na
   fatura a paciente escolhe Pix, cartão ou boleto. No nosso registro o
   método é `LINK` ("Link (WhatsApp)" no Caixa), porque quem escolheu foi
   ela, depois. Vencimento: 7 dias.
3. **A mensagem** vai do número de WhatsApp da clínica (z-api), para o
   telefone do agendamento: nome, data e hora da sessão, valor e o link da
   fatura.
4. **Um pagamento vivo por agendamento** continua valendo:
   - já existe link pendente: reenvia o MESMO link, sem nova cobrança;
   - existe outra cobrança pendente (Pix do iPad abandonado, "pagar em
     dinheiro" que não aconteceu): é cancelada no Asaas e o link a substitui;
     se o Asaas disser que ela foi paga nesse meio-tempo, nada é enviado;
   - já pago: não envia.
5. **CPF:** o Asaas exige. Usa o do cadastro quando a pessoa do agendamento é
   a titular (mesma regra do iPad). Sem CPF, o painel pede antes de enviar e
   o CPF vai para o cadastro (só se estiver vazio).
6. **WhatsApp falhou** (instância desligada, número inválido): a cobrança fica
   criada e o painel mostra o link para copiar e mandar à mão. Nunca uma
   cobrança criada sem a recepção saber o link.
7. **Pagou:** o webhook do Asaas marca como pago e a agenda e o Caixa mostram
   "Pago · Link (WhatsApp)", como já acontece com o iPad.
8. **iPad:** se a paciente com link pendente fizer check-in, o iPad mostra o
   mesmo link (QR da fatura) ou deixa trocar a forma de pagamento.

## 3. Fora do escopo

- Lembrete automático de link não pago.
- Texto da mensagem editável por clínica (templates).
- Distinguir no Caixa se o link foi pago por Pix, cartão ou boleto.

## 4. Status

- [x] Spec gerada (28/10/2026)
- [x] Implementado (28/10/2026)
- [x] Deploy dev (28/10/2026)
- [ ] Prod (junto com a 028)
