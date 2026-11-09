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

### 3.3 O caso que eu achei que existia, e não existe

**RETIRADO em 08/11/2026.** Esta seção afirmava que um agendamento PENDENTE
chegaria pelo atalho sem estar na lista, deixando a tela muda, e que "hoje isso
já acontece, calado". **Está errado, e a origem do erro foi minha:** eu li
"Pendente" na agenda e assumi que era status de agendamento, sem conferir o
modelo de dados.

O que a conferência mostrou:

1. O status de agendamento admite `CONFIRMED`, `CANCELLED`, `NO_SHOW` e `NULL`
   (`appointments_status_check`). **Não existe PENDENTE.**
2. "Pendente" na agenda é a **presença** (PRD 027): o lembrete saiu e a pessoa
   ainda não confirmou. Nada a ver com o status do agendamento, e ortogonal a
   registrar sessão.
3. Em produção há **848 CONFIRMED, 153 CANCELLED, 29 NO_SHOW e nenhum com
   status nulo**. Não há um único agendamento "sem status" para incluir.
4. O atalho só aparece para agendamento que não está cancelado nem como falta
   (`AppointmentPopover.tsx:216`). Ou seja, todo agendamento que oferece o
   atalho é `CONFIRMED` - e portanto **já está** na lista.

Conclusão: o filtro `status = 'CONFIRMED'` não exclui nada que devesse entrar.
Incluir "pendentes" é mudança sem alvo. `CANCELLED` e `NO_SHOW` seguem fora por
motivo correto: a sessão não aconteceu.

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

### 5.2 Agendamento pendente - SEM OBJETO

O André decidiu em 08/11/2026 **incluir os pendentes**. Ao preparar a mudança
descobri que **não há pendentes a incluir**: a pergunta nasceu de uma premissa
minha errada sobre o modelo de dados (ver §3.3). Nenhum agendamento em produção
fica fora da lista por causa de status.

A decisão fica registrada e sem efeito. Se um dia existir um estado
intermediário de agendamento, esta seção é o lugar de reabrir.

## 6. Arquivos impactados

| Arquivo | Mudança |
|---|---|
| `frontend/src/pages/documentos/components/HistoricoDeSessao.tsx` | não abrir o modal pelo parâmetro; `agendamentoInicial` sai |
| `frontend/src/pages/documentos/DocumentosPage.tsx` | para de ler `?agendamento=` |
| `frontend/src/pages/documentos/components/RegistroDeSessaoModal.tsx` | `agendamentoInicial` sai; a escolha passa a ser só pelo rádio |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | o link perde o `?agendamento=` |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | só o comentário, que hoje descreve um comportamento que vai mudar |
| `scheduler/src/functions/patient_record/list.py` | **nenhuma** (ver §3.3); só um teste que sustenta a ordem da lista |

**Entrega só de frontend.** Nenhuma migration, nenhuma mudança de contrato de
API, nenhum deploy de backend. Duas das três mudanças são remoção de código.

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
- [ ] Agendamento cancelado ou com falta não aparece na lista (a sessão não
      aconteceu), e todo agendamento que oferece o atalho na agenda aparece.
- [ ] A aplicadora não precisa adicionar nenhuma área à mão no caso comum.
- [ ] `npm run build`, `npm run lint` e `npm run test` verdes.

---

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Dois cliques a mais no caminho de todo dia (histórico, "Novo registro", escolher a sessão) | O primeiro põe o parâmetro anterior na frente dela, que é o pedido. Os outros dois são a escolha explícita que substitui a pré-seleção silenciosa - foi ela que gerou o defeito |
| Ela escolher a sessão errada na lista | A lista traz data, hora e áreas de cada uma, e vem da mais recente para a mais antiga; o registro é editável e tem trilha (`edit_count`) |
| Eu voltar a inventar estado que o banco não tem | O status real é `CONFIRMED`/`CANCELLED`/`NO_SHOW`/`NULL`, e "Pendente" na agenda é presença (PRD 027). §3.3 guarda a medição |

---

## 9. Referências

- `0bb308c` (19/09/2026): o histórico por sessão e o atalho da agenda.
- PRD 027 (lembrete de sessão): o que "confirmado" significa, para a §5.2.
- `src/services/protocolo_laser.py`: fonte única do protocolo e do mapa de áreas.

---

## Status

- [x] Aprovado: §5.1 decidida em 08/11/2026; §5.2 sem objeto (ver §3.3)
- [ ] Spec gerada: `spec/042-registrar-sessao-pela-agenda.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
