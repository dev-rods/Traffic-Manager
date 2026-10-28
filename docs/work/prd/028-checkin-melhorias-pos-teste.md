# PRD — 028 Check-in: melhorias depois do primeiro teste gravado

> Gerado na fase **Research**. Use como input para a fase Spec.
> Origem: dois vídeos do Rodrigo testando a 026 em dev (28/10/2026),
> transcritos e cruzados com os quadros da tela.

---

## 1. O que o teste mostrou

| # | Observação | Onde |
|---|---|---|
| M1 | Na lista "Qual é o seu agendamento?" o agendamento já pago aparece igual aos outros. Ao tocar nele, a tela pede "Está certo, confirmar" de novo, e pareceu um duplo check-in. | vídeo 2, 05:10 |
| M2 | A conclusão é só um ✓: "poderia ter uma telinha de sucesso, tipo uma comemoração". | vídeo 2, 04:09 |
| M3 | Cabeçalho "feiozão": só o nome da clínica em texto e o "Recomeçar" solto. | vídeo 1, 03:36 |
| M4 | Em dev o código não chegou no WhatsApp; foi preciso buscar no DynamoDB. O z-api de dev aceita o envio e não entrega, então o código de teste (026) não aparecia. | vídeo 1, 04:17 |
| M5 | Na fatura do cartão, não ficou claro o que pôr em nome do titular e nos outros campos. A dica só falava do número do cartão. | vídeo 2, 07:08 |
| M6 | A tela de pagamento rola numa janela mais baixa: o título ficou cortado e foi preciso rolar até "Trocar forma de pagamento". | quadros do vídeo 2 |
| M7 | O caixa conta como "Recebido" pagamentos de sessões que depois foram canceladas, sem aviso. É dinheiro que entrou e precisa de estorno. | quadros do vídeo 2 |

## 2. O que muda

1. **M1:** cada item da lista mostra o estado: "Pago · Pix" ou "Check-in feito
   às 19:06". Agendamento pago vai direto para "Seu pagamento está confirmado",
   sem pedir confirmação. Agendamento com check-in feito e pagamento pendente
   segue para o pagamento, com o botão "Continuar para o pagamento".
2. **M2:** a conclusão ganha uma animação curta (o check se desenhando e um
   confete leve). Com `prefers-reduced-motion`, só o estado final.
3. **M3:** o cabeçalho mostra logo e nome da clínica; o "Recomeçar" vira botão
   com ícone e borda.
4. **M4:** **só em dev**, o código volta sempre na resposta e aparece na tela,
   entregue ou não pelo WhatsApp. Em prod, nunca.
5. **M5:** a dica de teste lista todos os campos da fatura: o cartão, CVV 123,
   validade futura, qualquer nome, o CPF de teste e quaisquer e-mail, CEP e
   telefone válidos.
6. **M6:** em tela deitada e larga (iPad em paisagem, computador), a tela de
   pagamento fica em duas colunas: QR à esquerda, instruções e botões à
   direita. Em pé continua em uma coluna, mais compacta.
7. **M7:** no **caixa**, a seção "Estornos pendentes" lista os pagamentos de
   sessões canceladas, com o botão **Estornar** (só admin), que estorna no
   Asaas; em dinheiro, só registra, e a devolução é feita em mão. Em
   "Recebimentos", essas linhas ganham o selo "sessão cancelada". **No
   painel**, cancelar um agendamento já pago avisa que o dinheiro não volta
   sozinho e aponta para o caixa.

## 3. Fora do escopo

- Estorno parcial.
- Estorno automático ao cancelar: é decisão humana (pode virar crédito para
  outra sessão).

## 4. Status

- [x] Spec gerada (28/10/2026)
- [x] Implementado (28/10/2026), branch `feat/028-checkin-melhorias-pos-teste`
- [x] Deploy dev (28/10/2026): scheduler em dev e `checkin-dev`
- [ ] Prod: só quando decidirmos subir a branch (inclui o fim do limite de envio de código)

**Achado no teste do estorno (sandbox):** o Asaas aceita o pedido, mas o estorno
fica em `AWAITING_CRITICAL_ACTION_AUTHORIZATION`, porque a proteção de "eventos
críticos" da conta está ligada (é o padrão). O dinheiro só volta depois que o
dono da conta autoriza com token no app ou no painel do Asaas. Por isso a rota
devolve `refundNeedsAuthorization` e o painel avisa. Em produção, a conta do
André vai pedir a mesma autorização a cada estorno de Pix ou cartão.
