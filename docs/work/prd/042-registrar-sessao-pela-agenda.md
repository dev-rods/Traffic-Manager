# PRD - 042 "Registrar sessão" pela agenda: histórico primeiro, áreas prontas

> Gerado na fase **Research** em 08/11/2026. Use como input para a fase Spec.
> Pedido do André a partir do uso real da aplicadora na agenda do dia.

---

## 1. Objetivo

Deixar o registro de sessão prático para quem está com a paciente na maca, em
dois pontos:

1. **"Registrar sessão" abre o histórico**, não um formulário em branco. A
   aplicadora precisa ver o parâmetro da última sessão antes de decidir o desta.
2. **Escolher a sessão já traz as caixas das áreas preenchidas**, para ela só
   conferir valores em vez de adicionar área por área.

---

## 2. O que acontece hoje, e por que

Os dois pedidos têm **a mesma causa**, e isso muda o tamanho do trabalho: o
pré-preenchimento **já existe e funciona** - o atalho da agenda simplesmente
passa por cima dele.

**O atalho** (`AppointmentPopover.tsx:298`) leva para
`/pacientes/{id}/documentos?agendamento={id}`. Na página, `HistoricoDeSessao`
faz:

```tsx
const [criando, setCriando] = useState(Boolean(agendamentoInicial))
```

Com o parâmetro na URL, o modal **nasce aberto**: o histórico existe atrás dele
e nunca é visto. Foi construído assim de propósito, em 19/09/2026 (commit
`0bb308c`), e o comentário no código explica o raciocínio:

> "O caminho curto do caso mais comum: ela acabou de atender e a paciente está
> na tela. Ir até Pacientes, buscar pelo nome e abrir Documentos seria o caminho
> longo para o que acontece todo dia."

O raciocínio continua válido - o que estava errado era o **destino** do caminho
curto. Pular o histórico economiza um clique e tira da tela exatamente a
informação que faz a aplicadora decidir o parâmetro.

**O pré-preenchimento das áreas** mora em `escolheSessao`
(`RegistroDeSessaoModal.tsx:84`): escolhida a sessão, ela lê `sessao.areas`,
expande a área composta pela tabela do protocolo (`Virilha Completa + ânus` vira
duas aplicações) e já põe a sugestão de fluência conforme o tipo de pele.

Essa função é chamada **só pelo `onChange` do rádio** (linha 203). Pelo atalho,
o estado inicial é:

```tsx
const [appointmentId, setAppointmentId] = useState(registro?.appointment_id ?? agendamentoInicial ?? null)
const [aplicacoes, setAplicacoes]       = useState(registro?.applications ?? [])   // -> []
```

O rádio aparece **marcado** e a lista de áreas vem **vazia**. Para a aplicadora
é a pior combinação possível: a tela afirma que a sessão está escolhida e, ainda
assim, cobra as áreas uma a uma. Clicar em outro rádio e voltar faria a
expansão rodar - ninguém descobre isso sozinho.

> Entrando pelo botão **"+ Novo registro"** dentro do histórico e clicando no
> rádio, o pré-preenchimento funciona hoje. O defeito é exclusivo do atalho da
> agenda, que é justamente o caminho de todo dia.

---

## 3. O que muda

### 3.1 O atalho leva ao histórico, e nada é destacado lá

`?agendamento=<id>` para de abrir o modal. A aplicadora cai na lista de
registros - que já mostra o parâmetro de cada sessão anterior sem expandir nada.

**Decidido (André, 08/11/2026):** o histórico **não destaca** a sessão do
atalho. Ele mostra só os registros, como hoje. Quem escolhe a sessão é o modal,
num clique em "Novo registro". O rótulo do botão também não muda.

Consequência que simplifica o trabalho: com a escolha sempre passando pelo
rádio, o parâmetro `?agendamento=` **deixa de ter função**. Ele existia para
pré-selecionar, e pré-seleção foi justamente o que produziu o defeito (§2).
Sai da URL e do componente - ver §5.1, que agora é só a confirmação disso.

### 3.2 Escolhida a sessão, as áreas vêm prontas

As sessões sem registro aparecem no modal **da mais recente para a mais
antiga**, e escolher uma cria as caixas das áreas já com a sugestão de
parâmetro.

A ordem **já está correta** hoje: o backend ordena
`ORDER BY a.appointment_date DESC` (`patient_record/list.py:88`) e nem o
histórico nem o modal reordenam. Nada a fazer aqui além de um teste que
sustente a ordem, para ela não se perder num refactor.

E a expansão de áreas **já funciona** por esse caminho (`escolheSessao` no
`onChange` do rádio). Com a decisão de §3.1, o único defeito era a
pré-seleção silenciosa - que deixa de existir.

### 3.3 O caso que a lista não cobre

`appointments_without_record` (`patient_record/list.py:77`) só traz
`status = 'CONFIRMED'`. Um agendamento **PENDENTE** chega pelo atalho com um id
que não está na lista: o rádio não marca nada e a aplicadora não entende por
quê. Hoje isso já acontece, calado.

A tela precisa dizer o que houve, em vez de parecer quebrada. Qual a regra
correta - mostrar o pendente na lista, ou explicar que ele precisa ser
confirmado primeiro - é decisão §5.2.

---

## 4. Escopo

### Dentro

- O atalho da agenda passa a abrir o histórico, sem destaque nenhum.
- `?agendamento=` sai da URL, da `DocumentosPage` e do `HistoricoDeSessao`:
  sem pré-seleção, não há caminho que pule a expansão de áreas.
- Teste que sustenta a ordem das sessões (mais recente primeiro) e a criação
  das caixas de área ao escolher.
- Testes: o atalho não abre o modal; o modal com `agendamentoInicial`
  pré-preenche as áreas; área composta expande nos dois caminhos.

### Fora

- Mudar o formulário de registro em si (campos, validação, protocolo).
- Mudar a regra de sugestão de parâmetro ou a tabela do protocolo.
- Registrar sessão direto do popover da agenda, sem sair da tela. É uma ideia
  melhor que esta e um PRD próprio: muda onde o prontuário é preenchido.
- Mostrar o histórico dentro do popover da agenda.

---

## 5. Decisões para o André

### 5.1 Como a sessão do atalho aparece no histórico - DECIDIDO

**Decidido (André, 08/11/2026):** não aparece. O histórico mostra só os
registros; a escolha da sessão vive no modal, atrás de "Novo registro", com as
sessões sem registro listadas da mais recente para a mais antiga.

As três opções que este PRD levantou (botão com rótulo da sessão, linha
destacada na lista, resumo da última sessão dentro do modal) foram **recusadas**
em favor do caminho mais simples: nenhuma delas, nenhum componente novo.

O André também reconsiderou e **manteve** o redirecionamento para o histórico -
era a pergunta de fundo do pedido original, e segue de pé.

### 5.2 Agendamento pendente

O atalho aparece no popover para qualquer agendamento não cancelado e sem falta,
mas só os **confirmados** entram na lista de sessões sem registro.

- **Opção 1 (recomendada):** a lista passa a trazer pendentes também. Quem está
  com a paciente na maca atendeu de fato - exigir que a recepção confirme antes
  é burocracia no meio do atendimento, e a aplicadora não tem como resolver.
- Opção 2: a tela explica ("este agendamento ainda não está confirmado") e
  oferece registrar como sessão fora do sistema.

Recomendo a 1, mas isso toca uma regra de negócio que não é minha: confirmar
agendamento tem significado na recepção e no lembrete (PRD 027). **Preciso do
seu aval.**

---

## 6. Arquivos impactados

| Arquivo | Mudança |
|---|---|
| `frontend/src/pages/documentos/components/HistoricoDeSessao.tsx` | não abrir o modal pelo parâmetro; `agendamentoInicial` sai |
| `frontend/src/pages/documentos/DocumentosPage.tsx` | para de ler `?agendamento=` |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx` | `agendamentoInicial` sai; a escolha passa a ser só pelo rádio |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | o link perde o `?agendamento=` |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | só o comentário, que hoje descreve um comportamento que vai mudar |
| `scheduler/src/functions/patient_record/list.py` | somente se a decisão §5.2 for a opção 1 |

Nenhuma migration. Nenhuma mudança de contrato de API, exceto na §5.2 opção 1.

---

## 7. Critérios de aceite

- [ ] Clicar em "Registrar sessão" na agenda abre o **histórico** daquela
      paciente, com os parâmetros das sessões anteriores visíveis sem expandir.
- [ ] "Novo registro" lista as sessões sem registro **da mais recente para a
      mais antiga**, e escolher uma cria as caixas das áreas com a sugestão do
      protocolo.
- [ ] Área composta expande em duas aplicações.
- [ ] Nenhum caminho abre o modal com sessão escolhida sem as áreas montadas -
      a pré-seleção deixou de existir.
- [ ] Agendamento que não está na lista produz mensagem clara, não tela muda.
- [ ] A aplicadora não precisa adicionar nenhuma área à mão no caso comum.
- [ ] `npm run build`, `npm run lint` e `npm run test` verdes.

---

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Dois cliques a mais no caminho de todo dia (histórico, "Novo registro", escolher a sessão) | O primeiro põe o parâmetro anterior na frente dela, que é o pedido. Os outros dois são a escolha explícita que substitui a pré-seleção silenciosa - foi ela que gerou o defeito |
| Ela escolher a sessão errada na lista | A lista traz data, hora e áreas de cada uma, e vem da mais recente para a mais antiga; o registro é editável e tem trilha (`edit_count`) |
| Pendente entrar na lista e alguém registrar sessão que não ocorreu | O registro é editável e tem trilha de edição (`edit_count`); e hoje o risco oposto - não conseguir registrar o que ocorreu - é o que acontece |

---

## 9. Referências

- `0bb308c` (19/09/2026): o histórico por sessão e o atalho da agenda.
- PRD 027 (lembrete de sessão): o que "confirmado" significa, para a §5.2.
- `src/services/protocolo_laser.py`: fonte única do protocolo e do mapa de áreas.

---

## Status

- [ ] §5.1 decidida em 08/11/2026; aguardando a de §5.2 (agendamento pendente)
- [ ] Spec gerada: `spec/042-registrar-sessao-pela-agenda.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
