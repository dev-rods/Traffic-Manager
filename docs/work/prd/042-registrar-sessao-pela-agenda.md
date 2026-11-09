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

### 3.1 O atalho leva ao histórico

`?agendamento=<id>` para de abrir o modal. A aplicadora cai na lista de
registros - que já mostra o parâmetro de cada sessão anterior sem precisar
expandir nada - com a ação de registrar aquela sessão em destaque.

Fica a decidir **como** destacar (ver §5.1): um botão com rótulo específico
("Registrar a sessão de hoje") ou a linha daquele agendamento marcada na lista
de sessões sem registro.

### 3.2 Escolhida a sessão, as áreas vêm prontas

Ao abrir o modal com uma sessão já escolhida - pelo atalho ou por qualquer
caminho futuro - a expansão de áreas roda igual ao clique no rádio. A regra
passa a valer **uma vez só, no mesmo lugar**, em vez de depender de qual evento
disparou.

Isso é uma correção de defeito, não feature nova: a função existe, está testada
e só não é chamada nesse caminho.

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

- O atalho da agenda passa a abrir o histórico, com a sessão do agendamento em
  destaque.
- Abrir o modal com sessão pré-escolhida pré-preenche as áreas, com a mesma
  expansão de área composta e a mesma sugestão de parâmetro do clique no rádio.
- Mensagem honesta quando o agendamento do atalho não está na lista.
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

### 5.1 Como a sessão do atalho aparece no histórico

| Opção | Como fica | Custo |
|---|---|---|
| **A. Botão com rótulo específico** (recomendada) | O histórico abre normal e o botão diz "Registrar a sessão de 08/11", em vez de "+ Novo registro". Um clique leva ao modal já preenchido. | baixo |
| B. Linha destacada na lista | A sessão sem registro aparece realçada na própria lista, e clicar nela abre o modal. | médio; mexe no desenho da lista |
| C. Abrir o modal, mas com a última sessão resumida dentro dele | Mantém zero cliques e traz o parâmetro anterior para dentro do formulário. | médio; é outra tela |

Recomendo **A**: resolve o pedido com o menor movimento, mantém um clique de
distância do formulário e não inventa um componente novo. A opção C merece ser
registrada porque é a que mais economiza movimento da aplicadora - se o
histórico inteiro for mais do que ela precisa ver, vale virar o caminho padrão
depois.

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
| `frontend/src/pages/documentos/components/HistoricoDeSessao.tsx` | não abrir o modal pelo parâmetro; botão com rótulo da sessão |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx` | pré-preencher as áreas quando a sessão já vem escolhida |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | só o comentário, que hoje descreve um comportamento que vai mudar |
| `scheduler/src/functions/patient_record/list.py` | somente se a decisão §5.2 for a opção 1 |

Nenhuma migration. Nenhuma mudança de contrato de API, exceto na §5.2 opção 1.

---

## 7. Critérios de aceite

- [ ] Clicar em "Registrar sessão" na agenda abre o **histórico** daquela
      paciente, com os parâmetros das sessões anteriores visíveis sem expandir.
- [ ] Dali, um clique abre o registro **com as áreas do agendamento já
      preenchidas** e com a sugestão de parâmetro do protocolo.
- [ ] Área composta expande em duas aplicações pelo atalho, igual ao clique no
      rádio.
- [ ] Agendamento que não está na lista produz mensagem clara, não tela muda.
- [ ] A aplicadora não precisa adicionar nenhuma área à mão no caso comum.
- [ ] `npm run build`, `npm run lint` e `npm run test` verdes.

---

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Um clique a mais no caminho de todo dia | É o clique que põe o parâmetro anterior na frente dela, que é o pedido; o rótulo do botão diz exatamente qual sessão será registrada |
| A expansão rodar duas vezes e duplicar aplicações | A expansão substitui a lista (`setAplicacoes(novas)`), não acrescenta; o teste cobre abrir pelo atalho e trocar de rádio em seguida |
| Pendente entrar na lista e alguém registrar sessão que não ocorreu | O registro é editável e tem trilha de edição (`edit_count`); e hoje o risco oposto - não conseguir registrar o que ocorreu - é o que acontece |

---

## 9. Referências

- `0bb308c` (19/09/2026): o histórico por sessão e o atalho da agenda.
- PRD 027 (lembrete de sessão): o que "confirmado" significa, para a §5.2.
- `src/services/protocolo_laser.py`: fonte única do protocolo e do mapa de áreas.

---

## Status

- [ ] Pendente (aguardando as decisões de §5.1 e §5.2)
- [ ] Spec gerada: `spec/042-registrar-sessao-pela-agenda.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
