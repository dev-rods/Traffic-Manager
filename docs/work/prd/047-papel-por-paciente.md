# PRD - 047 Termo e anamnese em papel, registrados pelo paciente

> Gerado na fase **Research** em 10/11/2026. Use como input para a fase Spec.
> Pedido do André: "somente na agenda nós temos como marcar que termo e
> anamnese foram assinados em papel. Quero essa feature também por paciente,
> para indicar quando já possui assinatura em papel sem a necessidade de ir em
> agenda por agenda".

---

## 1. Objetivo

A recepção registra "assinado em papel" **na pasta do paciente**, sem precisar
de uma sessão marcada na agenda, e enxerga **na lista de pacientes** quem ainda
não tem termo vigente, para fazer o acerto da base antiga de uma vez.

---

## 2. Contexto

### 2.1 O que já existe

O registro em papel **já é por paciente no servidor** desde o PRD 036:

| Peça | Onde | Observação |
|---|---|---|
| `POST clinics/{clinicId}/consents/patients/{patientId}/paper` `{signedAt}` | `src/functions/consent/router.py` | exige `agenda.escrever`; grava `patient_consents` com `status='PAPER'`, `term_version` vigente, `paper_signed_at`, `paper_registered_by` |
| `consentimento.registra_papel` | `src/services/consentimento.py` | idempotente pelo índice `uq_patient_consents_vigente` (devolve o vigente se já houver) |
| `useRegistrarPapel` + `consentsService.registrarPapel` | `frontend/src/hooks/useConsents.ts`, `services/consents.service.ts` | já recebem `patientId`, não `appointmentId` |

O que falta é **só a porta de entrada no painel**: o único lugar que chama
essa rota é o popover da agenda (`pages/agenda/components/TermoDoAgendamento.tsx`,
modal "Termo assinado em papel" com a data). Quem não tem sessão marcada não
tem onde ser registrado.

### 2.2 Onde dói

- A pasta do paciente (`/pacientes/:id/documentos`, aba "Termo e anamnese",
  `TermoDeConsentimento.tsx`) **lista** os documentos e tem "Pedir nova
  assinatura", mas não tem "Assinado em papel". O estado vazio ainda manda
  esperar o check-in: "A paciente assina o termo e responde a ficha de anamnese
  no check-in do iPad, na próxima sessão."
- A lista de pacientes (`PatientsPage`) não mostra se há termo vigente, então
  não há como saber quem falta sem abrir cada pasta ou esperar a sessão aparecer
  na agenda com o selo `DOCS`.
- Resultado: a base antiga de uma clínica (quem assinou em papel ao longo dos
  anos) só é regularizada sessão a sessão, na véspera, pela agenda.

### 2.3 Semântica que vale hoje (e continua)

- Desde o PRD 038 termo e ficha de anamnese são **um documento só**. `PAPER`
  vale pelos dois: quem está em papel não assina nem responde a ficha no iPad
  (`consentimento.precisa_assinar` -> `vigente` aceita `SIGNED` ou `PAPER`).
- O papel fica preso à `term_version` vigente (`TCLE_VERSION`). Se o texto do
  termo mudar de versão, o papel antigo deixa de valer e o registro precisa ser
  refeito - igual ao digital.
- O painel só esconde botões; a permissão (`agenda.escrever`) vale no servidor.

---

## 3. Escopo

### Dentro do escopo

1. **"Assinado em papel" na pasta do paciente** (aba "Termo e anamnese"): o
   mesmo modal da agenda (data, máximo hoje, texto "guarde o papel na pasta"),
   extraído para um componente compartilhado para agenda e pasta usarem a
   mesma peça. Aparece quando há versão configurada e **não há** vigente
   (`SIGNED`/`PAPER` da versão atual); some depois de registrar. O estado vazio
   passa a oferecer o botão em vez de só mandar esperar o check-in.
2. **Situação do termo na lista de pacientes**: cada linha/cartão mostra se há
   termo vigente (selo discreto "Sem termo", no molde do `DOCS` da agenda) e
   um filtro "Termo e anamnese: sem vigente / com vigente / todos" ao lado dos
   filtros existentes. Servidor: `patient/list.py` ganha `consent_status`
   (mesmo `LEFT JOIN LATERAL` da listagem da agenda, `appointment/list.py`
   linhas 125-131) e o filtro `consent=missing|ok`.
3. **Ação direta na linha**: na lista, quem está "Sem termo" tem a ação
   "Assinado em papel" (mesmo modal), para regularizar a base sem abrir pasta
   por pasta. Depende da decisão §7.1.
4. **Registro em lote** (§7.2 B): na barra de seleção da lista
   (`AcoesEmLote`), "Assinado em papel" para os selecionados, com **uma data
   para todos** e aviso claro disso no modal. Mesmo molde do excluir em lote:
   laço no cliente sobre a rota unitária, progresso e resultado por pessoa.
   Quem já tem vigente é pulado (a rota devolve o vigente; o painel mostra
   "já tinha").
5. Testes: Vitest dos quatro pontos (modal compartilhado, botão na pasta, selo e
   filtro na lista); pytest do `consent_status` e do filtro em
   `patient/list.py`; doc de integração.

### Fora do escopo

- Separar termo de anamnese (um em papel, outro no iPad). Não existe esse
  estado desde o PRD 038 e criar seria desfazer a decisão de documento único.
- Anexar foto/scan do papel. O registro continua "sem PDF".
- Mudar a regra do gatilho do check-in ou o selo `DOCS` da agenda.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `frontend/src/components/RegistrarPapelModal.tsx` (+ test) | criar | o modal de hoje, com `patientId`, `open`, `onClose`, `onRegistrado`; usa `useRegistrarPapel` |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` (+ test) | modificar | passa a usar o modal compartilhado; comportamento igual |
| `frontend/src/pages/documentos/components/TermoDeConsentimento.tsx` (+ test) | modificar | botão "Assinado em papel" quando não há vigente; estado vazio com o botão |
| `scheduler/src/functions/patient/list.py` | modificar | `consent_status` por paciente; filtro `consent` |
| `frontend/src/types/index.ts` | modificar | `Patient.consent_status: ConsentStatus ou null`, `consent_enabled` |
| `frontend/src/services/patients.service.ts`, `hooks/usePatients*.ts` | modificar | parâmetro do filtro |
| `frontend/src/pages/pacientes/components/FiltrosDePacientes.tsx`, `contagemDeFiltros.ts`, `PatientsTable.tsx`, `PatientCard.tsx` (+ tests) | modificar | filtro, selo e ação na linha |
| `frontend/src/pages/pacientes/components/AcoesEmLote.tsx`, `BatchPapelModal.tsx` (+ tests), `hooks/useConsents.ts` (`useRegistrarPapelEmLote`) | modificar/criar | lote com uma data, progresso e resultado por pessoa |
| `scheduler/tests/unit/test_patient_list*.py` | modificar/criar | `consent_status` e filtro |
| `scheduler/tests/integration/047-papel-por-paciente.md` | criar | roteiro de conferência |

Sem migration: `patient_consents` já tem tudo. Sem rota nova: a stack segue
perto do limite do CloudFormation e a rota de papel já existe.

---

## 5. Dependências e riscos

- **Dependências:** `TCLE_VERSION` configurada na clínica (sem ela o botão não
  aparece e a lista mostra "Não configurado", como a agenda); permissão
  `agenda.escrever` para registrar, `prontuario.ler` para ver a pasta.
- **Riscos:**
  - Listagem de pacientes mais pesada com o `LATERAL` por linha. A da agenda
    já faz o mesmo sem problema; o índice `uq_patient_consents_vigente`
    (`clinic_id, patient_id, term_version`) cobre a busca. Conferir o tempo da
    rota em prod com a maior base (Essência) antes de dar por feito.
  - Registro errado por engano na linha (clique em quem não assinou): o modal
    pede a data e confirma; e "Pedir nova assinatura" na pasta desfaz o efeito
    (o vigente vira `REVOKED` e o iPad pede de novo).
  - Dois caminhos para a mesma ação (agenda e pasta): o modal compartilhado
    evita divergência de texto e regra - fonte única.

---

## 6. Critérios de aceite

- [ ] Na pasta do paciente sem termo vigente, "Assinado em papel" abre o modal, grava `PAPER` com a data e a tabela passa a listar a linha "Em papel"; o botão some.
- [ ] Com termo vigente (`SIGNED` ou `PAPER`), o botão não aparece; sem `TCLE_VERSION`, também não.
- [ ] Depois do registro, a sessão futura dessa pessoa na agenda deixa de mostrar `DOCS` e o check-in do iPad pula termo e ficha.
- [ ] A lista de pacientes mostra "Sem termo" para quem não tem vigente e o filtro "sem vigente" traz só essas pessoas; a contagem de filtros ativos considera o novo.
- [ ] A ação na linha grava e atualiza a linha sem recarregar a página.
- [ ] O lote registra os selecionados com a data informada, mostra progresso e resultado por pessoa (registrado / já tinha / erro) e limpa a seleção ao fechar.
- [ ] O popover da agenda continua funcionando igual (mesmo modal, mesmos textos, mesmo toast).
- [ ] Usuário sem `agenda.escrever` não vê o botão e recebe 403 se chamar a rota.
- [ ] Nome ou telefone real de paciente não aparece em teste, commit nem doc.

---

## 7. Decisões

Registradas em 10/11/2026: **§7.1 A**, **§7.2 B**, **§7.3 A**.

### 7.1 Onde fica a ação de registrar

- **A (recomendada):** na pasta do paciente **e** na linha da lista (ação só
  para quem está "Sem termo"). É o caminho mais curto para regularizar a base:
  filtro "sem vigente" -> registrar linha a linha, sem sair da lista.
- **B:** só na pasta do paciente. Menos pontos de entrada; regularizar a base
  pede abrir cada pasta (um clique a mais por pessoa).

### 7.2 Registro em lote

- **A (recomendada):** fora. Cada papel tem a sua data; a seleção em lote
  pediria uma data única e viraria registro inventado.
- **B:** dentro, com uma data por lote e aviso no modal. Só faz sentido se a
  clínica tiver uma leva assinada no mesmo dia (mutirão).

### 7.3 Selo na lista

- **A (recomendada):** só o negativo, "Sem termo" (discreto, âmbar), como o
  `DOCS` da agenda. Quem está em dia não ganha selo: a lista continua limpa.
- **B:** selo em todos ("Assinado", "Em papel", "Sem termo"). Mais informação,
  mais ruído numa linha que já tem silenciado, próxima visita e ações.

---

## 8. Referências

- PRD 036 (`036-termo-de-consentimento.md`) §7 decisão 3 ("quem assinou em papel é registrado no painel")
- PRD 038 (`038-ficha-de-anamnese-no-checkin.md`): documento único termo + ficha
- `src/services/consentimento.py`: `vigente`, `precisa_assinar`, `registra_papel`, `renova`
- `src/functions/appointment/list.py` linhas 118-131: o `LATERAL` de `consent_status` a reaproveitar
- `frontend/src/utils/termo.ts`: `situacaoDoTermo` (a agenda só lê o que o servidor manda; a lista segue o mesmo princípio)

---

## 9. Status

- [x] Decisões §7 registradas em 10/11/2026: **§7.1 A** (pasta e linha da lista), **§7.2 B** (lote com uma data, com aviso), **§7.3 A** (selo só para quem está sem termo)
- [x] Spec gerada em 10/11/2026 (`spec/047-papel-por-paciente.md`)
- [ ] Implementado em dev
- [ ] Em prod
- [ ] Registrado no TASKS_LOG
