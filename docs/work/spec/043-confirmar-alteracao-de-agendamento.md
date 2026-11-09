# Spec - 043 Alterar agendamento pede confirmação

> Gerada em 08/11/2026 a partir de `docs/work/prd/043-confirmar-alteracao-de-agendamento.md`.
> Decisões do André em 08/11: §7.1 só o que tem efeito fora da tela; §7.2 sim,
> remarcar limpa a confirmação de presença.

---

## 1. O desenho

A confirmação é um **segundo passo dentro do mesmo modal**, não um modal por
cima de outro: dois overlays empilhados é feio e some com o contexto do
formulário. O título muda para "Confirmar alteração", o formulário dá lugar ao
resumo, e "Voltar" devolve o formulário com tudo preenchido.

```
  [ Editar agendamento ]                 [ Confirmar alteração ]
    ...campos...                           Ana Clara - 12/11 09:00
    [Cancelar] [Salvar alterações]  --->   Data    12/11 -> 14/11
                                           Horário 09:00 -> 15:00
                                           ! avisos
                                           [Voltar] [Confirmar alteração]
```

### 1.1 Quais campos pedem confirmação

Só os que têm efeito fora da tela (decisão §7.1):

| Campo | Pede? | Por quê |
|---|---|---|
| data, horário | sim | libera o horário antigo, cancela o lembrete do dia antigo |
| serviço, áreas | sim | muda preço e duração, e o tamanho do bloco na agenda |
| desconto | sim | muda o valor que a paciente paga |
| **duração manual** | sim | muda o tamanho do bloco, podendo invadir outro horário |
| observação, primeira visita | **não** | nada fora da tela |

A duração manual não estava na lista do PRD §7.1, e entra pelo mesmo critério
que ela aprova: o bloco muda de tamanho na agenda de todo mundo. Fica
registrado aqui para o André discordar se quiser.

### 1.2 Os avisos

| Quando | Texto |
|---|---|
| data ou hora mudam | "O horário anterior fica livre para outra pessoa." |
| data ou hora mudam | "A paciente não será avisada automaticamente." (§5.2 do PRD) |
| data/hora mudam e `confirmado_em` existe | "A presença estava confirmada para o horário anterior e voltará a Pendente." |
| desconto muda e o agendamento está pago | "Este agendamento já foi pago. Mudar o valor não altera o que foi cobrado." |

---

## 2. Frontend

`frontend/src/pages/agenda/components/EditAppointmentModal.tsx`

- estado novo `confirmando`;
- `mudancaComEfeito` = `dateChanged || timeChanged || serviceChanged ||
  areasChanged || discountChanged || manualChanged`;
- no `handleSubmit`: se `mudancaComEfeito && !confirmando`, `setConfirmando(true)`
  e **retorna sem chamar a mutation**;
- `confirmando` troca o corpo do modal pelo resumo e o título;
- "Voltar" faz `setConfirmando(false)`; `onClose` zera tudo pelo remount
  (`key={editing.id}` já existe no `AgendaPage`).

`frontend/src/pages/agenda/components/ResumoDaAlteracao.tsx` (novo)

Recebe as linhas já prontas (`{ rotulo, de, para }[]`), os avisos e os dois
botões. Puro, sem hook: dá para testar sem montar o formulário inteiro.

`frontend/src/lib/alteracaoDeAgendamento.ts` (novo)

A função que monta as linhas e os avisos a partir do agendamento e do estado do
formulário. Separada do componente porque é a regra - o que conta como mudança
com efeito, e o que se diz sobre cada uma - e é o que o teste precisa fixar.

Rótulos legíveis, não ids: nome do serviço pela lista de `useServices`, nomes
das áreas por `useServiceAreas`, desconto como texto ("sem desconto",
"parceria 100%", "20%").

---

## 3. Backend

`scheduler/src/services/appointment_service.py`, em `reschedule_appointment`:
o `UPDATE` que move data/hora passa a limpar a confirmação de presença.

```diff
- SET appointment_date = %s, start_time = %s, end_time = %s, total_duration_minutes = %s, ...
+ SET appointment_date = %s, start_time = %s, end_time = %s, total_duration_minutes = %s,
+     confirmado_em = NULL, confirmado_por = NULL, ...
```

Quem confirmou confirmou **um horário**, não um agendamento (decisão §7.2). Sem
isto a agenda exibe "Confirmada" num horário que a paciente nunca viu - e, como
ninguém a avisa da mudança, a recepção acredita numa confirmação que não existe.

O lembrete do dia antigo já é cancelado hoje (`cancel_reminder`), então
`lembrete_enviado_em` continua como está: ele registra que o lembrete **saiu**,
que é verdade, e é o que faz o badge "Pendente" aparecer.

---

## 4. Testes

**Frontend**

- `lib/alteracaoDeAgendamento.test.ts`: cada campo sensível produz linha;
  observação e primeira visita **não** produzem; os quatro avisos aparecem só
  nas condições certas; nenhuma linha quando nada mudou.
- `EditAppointmentModal.test.tsx` (novo): mudar a data e salvar **não** chama a
  mutation, mostra o resumo; "Voltar" devolve o formulário com a data alterada;
  "Confirmar" chama a mutation uma vez; mudar só a observação salva direto.

O "não chama a mutation" é o coração do pedido: é o que garante que nada
executa antes de a pessoa ver.

**Backend**

- `test_reagendar_limpa_confirmacao.py`: o SQL do reschedule zera
  `confirmado_em` e `confirmado_por`. Por comportamento com dublê que responde
  por SQL, e conferindo os parâmetros gravados - não por `assertIn` no fonte,
  que casa com comentário.

---

## 5. Ordem

1. `lib/alteracaoDeAgendamento.ts` + teste.
2. `ResumoDaAlteracao.tsx`.
3. Fiação no `EditAppointmentModal` + teste.
4. Backend + teste.
5. `pytest`, `npm run build`, `npm run lint`, `npm run test`.
6. Deploy dev (`--aws-profile dev-andre`) e conferência pela tela.

Sem migration.

---

## 6. Fora

- Mandar a mensagem de remarcação à paciente (PRD próprio).
- Confirmação em cancelar, falta e presença: já estão certas.
- Trilha de auditoria de alterações.
