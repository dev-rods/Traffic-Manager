# PRD - 043 Alterar agendamento pede confirmação

> Gerado na fase **Research** em 08/11/2026. Use como input para a fase Spec.
> Pedido do André: "alterações em agendamentos feitos precisam de confirmação
> antes de ser executado, para não correr o risco de cancelar sem perceber".

---

## 1. Objetivo

Quem altera um agendamento já marcado precisa **ver o que vai mudar e
confirmar** antes de a mudança valer. Hoje "Salvar" na tela de edição executa
na hora, sem resumo, e algumas dessas alterações não têm desfazer.

---

## 2. O que já é protegido, e o que não é

Levantamento de todas as ações sobre agendamento existente no painel:

| Ação | Confirma hoje? | Desfazer? |
|---|---|---|
| Cancelar agendamento | **sim**, modal com "não pode ser desfeita" | não |
| Marcar falta | não, por decisão de 04/10/2026 | sim, no toast |
| Marcar / desfazer confirmação de presença | não, mesma decisão | sim, no toast |
| **Editar agendamento** (data, hora, serviço, áreas, desconto, duração, obs.) | **não** | **não** |

Ou seja: o cancelamento, que é o medo expresso no pedido, **já tem modal**. O
que não tem é a **edição** - e é nela que moram as consequências sem desfazer.

Isto não contradiz a decisão de 04/10 ("cerimônia que não compra nada treina a
clicar sem ler"): falta e confirmação têm desfazer no toast, e por isso a
confirmação não se paga. A edição não tem desfazer nenhum.

---

## 3. O que uma edição faz de verdade

Medido no código em 08/11/2026, não suposto.

### 3.1 Mudar data ou hora (`reschedule_appointment`)

1. O agendamento **se move na mesma linha** - não é cancelar e recriar.
2. **O lembrete pendente do dia antigo é cancelado** (`cancel_reminder`). O do
   dia novo só sai pelo lote daquele dia (PRD 027).
3. A marca de estreia passa para a próxima sessão confirmada
   (`passa_a_marca_adiante`).
4. **O horário antigo é liberado** e pode ser ocupado por outra pessoa em
   seguida. É isso que torna a ação irreversível na prática: desfazer depende
   de o horário antigo ainda estar livre.
5. **Ninguém avisa a paciente.** Nem o painel nem o backend mandam mensagem ao
   remarcar - conferido nos dois lados.
6. **`confirmado_em` NÃO é limpo.** Um agendamento que a paciente confirmou
   para quarta às 9h continua marcado como "Confirmada" depois de ser movido
   para sexta às 15h - horário que ela nunca viu. Combinado com o item 5, a
   agenda afirma uma confirmação que não existe.

Os itens 5 e 6 são defeitos próprios, achados ao levantar este PRD. Ver §5.

### 3.2 Mudar serviço ou áreas

Recalcula preço e duração, e **descarta a duração manual** se havia (a premissa
mudou). Muda o tamanho do bloco na agenda, podendo invadir ou liberar horário.

### 3.3 Mudar desconto

Muda o valor que a paciente paga. Se o pagamento já foi feito pelo iPad, o
valor cobrado e o valor do agendamento passam a divergir - e cancelar não
devolve dinheiro (PRD 028, M7), então o mesmo vale para mudar preço depois de
pago.

### 3.4 Observações e "primeira visita"

Sem efeito fora da tela. Não merecem confirmação.

---

## 4. A proposta

**Um resumo do que vai mudar, antes de executar, só quando a mudança tem efeito
fora da tela.**

Ao clicar em Salvar, se a edição toca data, hora, serviço, áreas ou desconto,
aparece uma confirmação com o **de → para** de cada campo alterado, mais os
avisos que o caso pedir:

```
  Confirmar alteração

  Data      quarta, 12/11  ->  sexta, 14/11
  Horário   09:00          ->  15:00

  ! A paciente confirmou presença para o horário antigo. Ela não
    será avisada automaticamente desta mudança.
  ! O horário de quarta 09:00 fica livre para outra pessoa.

  [ Voltar ]            [ Confirmar alteração ]
```

Edição que só toca observações ou primeira visita salva direto, como hoje.

**Por que diff e não "tem certeza?":** o risco do pedido é alterar **sem
perceber**. Um "tem certeza?" genérico não mostra o que está errado; o de → para
mostra. E é o que permite pegar o caso de abrir a tela do agendamento errado -
o nome da paciente entra no cabeçalho do resumo.

---

## 5. Os dois defeitos achados no caminho

Entram neste PRD porque são exatamente o "cancelar sem perceber" que o pedido
teme, só que no lugar errado - e porque consertar um sem o outro deixa a tela
mentindo.

### 5.1 Remarcar mantém a presença confirmada

`reschedule_appointment` muda data, hora, fim e duração, e não toca
`confirmado_em`/`confirmado_por`. Proposta: **limpar a confirmação quando data
ou hora mudam**. Quem confirmou confirmou um horário, não um agendamento.

### 5.2 A paciente não é avisada da mudança

Nem o painel nem o backend mandam mensagem ao remarcar. Hoje a recepção avisa
por fora, se lembrar; e o lembrete do dia antigo é cancelado, então nada chega.

Proposta mínima **dentro** deste PRD: a confirmação diz, em texto, que a
paciente não será avisada. Mandar a mensagem é outro trabalho (template,
horário de silêncio, pausa do bot) e merece PRD próprio - mas a tela não pode
seguir calada sobre isso.

---

## 6. Escopo

### Dentro

- Confirmação com de → para na edição, quando a mudança toca data, hora,
  serviço, áreas ou desconto.
- Avisos no resumo: presença confirmada, horário liberado, agendamento já pago.
- Limpar `confirmado_em` quando data ou hora mudam (§5.1).
- Dizer na tela que a paciente não será avisada (§5.2).
- Testes: cada campo que exige confirmação; os que não exigem; o texto do diff.

### Fora

- Mexer em cancelar, falta e confirmação de presença: as três já estão certas
  (modal onde é irreversível, desfazer onde não é).
- **Mandar mensagem à paciente** ao remarcar. PRD próprio.
- Confirmação na criação de agendamento: não há o que perder.
- Alterações feitas pelo bot ou pelo site de agendamento. Lá quem decide é a
  própria paciente, e o fluxo é outro.
- Trilha de auditoria de quem alterou o quê. Vale um PRD, não este.

---

## 7. Decisões para o André

### 7.1 O alcance da confirmação

| Opção | Confirma | Risco |
|---|---|---|
| **A. Só o que tem efeito fora da tela** (recomendada) | data, hora, serviço, áreas, desconto | nenhum conhecido |
| B. Toda edição, sempre | tudo, inclusive observação | treina a clicar sem ler, contra a decisão de 04/10/2026 |

Recomendo **A**. O seu pedido diz "alterações", e eu entendo o espírito como
"nada com consequência passa calado" - não como "um modal a mais em corrigir
uma vírgula na observação".

### 7.2 Limpar a confirmação de presença ao mudar data/hora (§5.1)

Recomendo **sim**. O custo é a recepção ter de confirmar de novo com a
paciente - que é o trabalho correto, já que ela nem sabe do novo horário.

Se você preferir manter a confirmação, o resumo precisa pelo menos avisar, e aí
a agenda segue exibindo uma confirmação que não corresponde ao horário.

---

## 8. Arquivos impactados

| Arquivo | Mudança |
|---|---|
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` | o Salvar passa pelo resumo quando há campo sensível |
| `frontend/src/pages/agenda/components/` (novo) | o componente do resumo de alterações |
| `scheduler/src/services/appointment_service.py` | `reschedule_appointment` limpa a confirmação (§5.1) |
| `scheduler/tests/unit/` | o reschedule limpando a confirmação |

Nenhuma migration.

---

## 9. Critérios de aceite

- [ ] Mudar data, hora, serviço, áreas ou desconto mostra o resumo com de →
      para antes de executar; "Voltar" não altera nada.
- [ ] Mudar só observação ou primeira visita salva direto.
- [ ] O resumo nomeia a paciente e o agendamento, para pegar a tela errada.
- [ ] Mudança de horário em agendamento com presença confirmada avisa no resumo
      e, confirmada a alteração, a presença volta a "Pendente".
- [ ] Mudança de horário avisa que a paciente não será notificada.
- [ ] Agendamento já pago avisa no resumo quando o desconto muda.
- [ ] `pytest`, `npm run build`, `npm run lint` e `npm run test` verdes.

---

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Mais um modal no caminho da recepção | Só em edição com consequência; o resumo mostra o que mudou, não pergunta genérica |
| O diff mostrar campo que não mudou de fato | O modal de edição já compara com o original por campo (`dateChanged`, `areasChanged`...); o resumo lê os mesmos sinalizadores |
| Limpar a confirmação gerar retrabalho na recepção | É o trabalho que já deveria existir: a paciente não sabe do novo horário |

---

## 11. Referências

- `AppointmentPopover.tsx` (04/10/2026): a decisão de não pedir confirmação
  onde há desfazer.
- `appointment_service.reschedule_appointment`: o que remarcar faz de fato.
- PRD 027 (lembrete), PRD 028 M7 (pago não volta), PRD 035 (remarcar não é
  cancelar).

---

## Status

- [x] Aprovado em 08/11/2026: §7.1 só o que tem efeito fora da tela; §7.2 sim
- [x] Spec gerada em 08/11/2026: `spec/043-confirmar-alteracao-de-agendamento.md`
- [x] Implementado em 09/11/2026 (PR #180, dev e prod)
- [x] Registrado em `TASKS_LOG.md`
