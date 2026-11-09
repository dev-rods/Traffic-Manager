# Spec - 042 "Registrar sessão" pela agenda

> Gerada em 08/11/2026 a partir de `docs/work/prd/042-registrar-sessao-pela-agenda.md`,
> com as decisões do André de 08/11 (§5.1, §5.2 e a recusa de cancelado/falta).

---

## 0. O que muda, em uma tela

```
  ANTES                                    DEPOIS
  agenda                                   agenda
    "Registrar sessão"                       "Registrar sessão"
      -> /documentos?agendamento=<id>          -> /documentos
         modal ABRE sozinho                       histórico (parâmetros à vista)
         radio marcado, areas VAZIAS              "Novo registro"
                                                    sessões recentes -> antigas
                                                    escolher -> areas prontas
```

Duas das três mudanças são **remoção**. O pré-preenchimento de áreas e a ordem
da lista já funcionam; o que existia era um caminho que os contornava.

A terceira é uma trava no backend, que o PRD não previa e o André pediu em
08/11: cancelado e falta não podem virar registro de sessão.

---

## 1. Frontend: tirar a pré-seleção

A regra passa a ser uma só - **quem escolhe a sessão é o rádio do modal** -
porque era a existência de um segundo caminho que produzia o defeito.

### 1.1 `pages/agenda/components/AppointmentPopover.tsx`

O link perde a query:

```diff
- to={`/pacientes/${a.patient_id}/documentos?agendamento=${a.id}`}
+ to={`/pacientes/${a.patient_id}/documentos`}
```

O comentário de 19/09/2026 que defende o atalho curto é **reescrito**, não
apagado: ele explica uma decisão que acabou de mudar, e deixar o texto antigo
sobre o código novo é pior que não ter comentário. O novo diz que o atalho leva
ao histórico de propósito, porque é lá que está o parâmetro da última sessão.

### 1.2 `pages/documentos/DocumentosPage.tsx`

Sai a leitura de `?agendamento=` (`const agendamentoInicial = searchParams.get('agendamento')`),
a prop passada ao `HistoricoDeSessao`, e o comentário sobre "manter
`?agendamento=` vivo" na troca de aba. `?doc=termo` **fica**: é outra coisa.

### 1.3 `pages/documentos/components/HistoricoDeSessao.tsx`

```diff
- const [criando, setCriando] = useState(Boolean(agendamentoInicial))
+ const [criando, setCriando] = useState(false)
```

A prop `agendamentoInicial` sai da interface e do repasse ao modal.

### 1.4 `pages/documentos/components/RegistroDeSessaoModal.tsx`

Sai a prop `agendamentoInicial` e com ela o estado inicial que mentia:

```diff
- const [appointmentId, setAppointmentId] = useState(registro?.appointment_id ?? agendamentoInicial ?? null)
- const [sessionDate, setSessionDate]     = useState(registro?.session_date ?? sessaoPorId(agendamentoInicial)?.appointment_date ?? '')
+ const [appointmentId, setAppointmentId] = useState(registro?.appointment_id ?? null)
+ const [sessionDate, setSessionDate]     = useState(registro?.session_date ?? '')
```

`escolheSessao` **não muda**. A função `sessaoPorId` deixa de ser chamada no
corpo do componente (só dentro de `escolheSessao`), o que remove de passagem um
uso de função antes da sua declaração.

Nada muda na ordem da lista: ela chega do backend
`ORDER BY a.appointment_date DESC` e nenhuma das duas telas reordena.

---

## 2. Backend: cancelado e falta não viram sessão

### 2.1 O furo

`functions/patient_record/create.py` nunca olha o status do agendamento. A
única consulta que ele faz é para **buscar a data**, e só quando o corpo não
manda `sessionDate`:

```python
if appointment_id and not session_date:
    linhas = db.execute_query(
        "SELECT appointment_date FROM scheduler.appointments WHERE id = %s::uuid AND clinic_id = %s", ...)
```

Então hoje é possível criar registro de sessão para agendamento `CANCELLED` ou
`NO_SHOW` - a tela não oferece, mas a rota aceita. Basta a aba estar aberta
quando a recepção cancela, e o registro entra.

**E há um segundo furo na mesma consulta:** ela confere `clinic_id` e **não
confere `patient_id`**. Um registro da paciente A pode apontar para o
agendamento da paciente B, dentro da mesma clínica. Nada na tela produz isso
hoje, mas é a mesma linha de código e o custo de fechar é uma cláusula.

`update.py` não permite trocar `appointment_id` (só data, profissional, pele
bronzeada e observações), então a trava no `create` é suficiente.

### 2.2 A trava

A consulta passa a ser sempre feita quando há `appointment_id` - não só quando
falta a data - e valida as três coisas de uma vez:

```python
if appointment_id:
    linhas = db.execute_query(
        """SELECT appointment_date, status FROM scheduler.appointments
            WHERE id = %s::uuid AND clinic_id = %s AND patient_id = %s::uuid""",
        (appointment_id, clinic_id, patient_id))
    if not linhas:
        return 404 "Agendamento nao encontrado para esta paciente"
    status = (linhas[0].get("status") or "").upper()
    if status in ("CANCELLED", "NO_SHOW"):
        return 409 "<Cancelado|Falta> nao pode virar registro de sessao"
    session_date = session_date or str(linhas[0]["appointment_date"])
```

- **409, não 400:** o pedido está bem formado; o estado do agendamento é que
  recusa. É o mesmo código que o painel já usa para "já contatada".
- **Mensagem por status**, porque as causas são diferentes na cabeça de quem
  está na tela: cancelado é agendamento que não existe mais; falta é sessão que
  não houve.
- `status` nulo **passa**. O banco permite nulo e prod não tem nenhum (medição
  na §3.3 do PRD); barrar o nulo seria inventar regra para um caso que não
  existe, e falharia fechado para dado histórico se um dia existir.

A listagem (`list.py`) **não muda**: `status = 'CONFIRMED'` já deixa os dois
fora. A trava é para o caminho que não passa pela tela.

---

## 3. Testes

**Backend** (`scheduler/tests/unit/`):

- `test_registro_recusa_cancelado_e_falta.py` (novo): criar registro para
  agendamento `CANCELLED` devolve 409, para `NO_SHOW` devolve 409, para
  `CONFIRMED` cria, para status nulo cria; agendamento de **outra paciente**
  devolve 404; e a data continua vindo do agendamento quando o corpo não manda.
  Dublê de banco que responde por SQL, nunca `return_value` fixo - o dublê que
  responde a tudo igual é o que já me enganou hoje.
- A listagem já tem cobertura; acrescentar o caso que sustenta a **ordem**
  (mais recente primeiro), hoje garantida só pelo `ORDER BY`.

**Frontend**:

- `HistoricoDeSessao.test.tsx` (novo): a tela abre **sem** modal; "Novo
  registro" abre; a lista de sessões sem registro aparece dentro do modal na
  ordem recebida.
- `RegistroDeSessaoModal.test.tsx` (novo): escolher uma sessão no rádio cria
  uma caixa por área, e área composta vira duas aplicações; escolher outra
  sessão **substitui** as caixas, não acumula.

O teste do modal é o que de fato prova o pedido do André, e nenhum existe hoje
para esse componente.

---

## 4. Ordem de implementação

1. Backend: a trava e seus testes (independente do frontend).
2. Frontend: as remoções, de fora para dentro (popover, página, histórico,
   modal), guiadas pelo `tsc` - cada prop removida acusa o próximo lugar.
3. Testes de frontend.
4. `pytest`, `npm run build`, `npm run lint`, `npm run test`.
5. Deploy dev (`--aws-profile dev-andre`; `traffic-manager` não existe nesta
   máquina e o serverless sai com código 0 mesmo falhando).
6. Conferir em dev **pela tela**, não só pelo teste: clicar em "Registrar
   sessão" na agenda de uma paciente com sessão passada, ver o histórico com os
   parâmetros, abrir "Novo registro", escolher a sessão e ver as áreas prontas.

Sem migration. O frontend sobe pela Vercel no merge.

---

## 5. O que esta spec não faz

- Registrar sessão de dentro do popover da agenda (PRD próprio; é a ideia que
  economizaria mais movimento da aplicadora).
- Mostrar a última sessão resumida dentro do modal (opção C do PRD, recusada
  agora, registrada lá).
- Mexer no formulário, no protocolo ou na sugestão de parâmetro.
- Resolver registro que já existe apontando para agendamento depois cancelado:
  fica como está, e nenhuma tela o produz.
