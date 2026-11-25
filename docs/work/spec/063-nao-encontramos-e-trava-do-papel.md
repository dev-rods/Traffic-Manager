# Spec - 063 "Não encontramos" na página de documentos e trava no termo em papel

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/063-nao-encontramos-e-trava-do-papel.md`

---

## 1. Resumo

Só front. No app `checkin/`, a página de documentos ganha o estado
`not-found` para lista vazia, com tela própria e volta ao celular. No painel
`frontend/`, o `RegistrarPapelModal` recebe `patientName`, mostra o nome no
título e só habilita "Registrar" com o checkbox de afirmação marcado; os três
chamadores passam o nome.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `checkin/src/steps/NotFoundStep.tsx` | "Não encontramos sessão para este número" + "Tentar outro número" |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `checkin/src/pages/DocumentosPage.tsx` | `State` ganha `{ step: 'not-found' }`; no efeito pós-código, lista vazia vai para `not-found`; render do passo; cabeçalho sem "Sair" nesse passo |
| `checkin/src/pages/DocumentosPage.test.tsx` | novo caso "número sem sessão"; o caso "nada a fazer" continua com sessão |
| `frontend/src/components/RegistrarPapelModal.tsx` | prop `patientName`; título com o nome; checkbox `confirmado`; `Registrar` desabilitado sem ele; `fechar` zera o checkbox |
| `frontend/src/components/RegistrarPapelModal.test.tsx` | nome no título; botão travado até marcar; cancelar limpa |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` | `patientName={a.patient_name}` |
| `frontend/src/pages/documentos/components/TermoDeConsentimento.tsx` | prop `patientName`, repassa ao modal |
| `frontend/src/pages/documentos/DocumentosPage.tsx` | `patientName={paciente.name}` |
| `frontend/src/pages/pacientes/PacientesPage.tsx` | `patientName={papelPatient.name}` |
| testes de `TermoDoAgendamento` e `TermoDeConsentimento` | marcam o checkbox antes de clicar "Registrar" |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. `checkin/`: `NotFoundStep`, estado e teste.
2. `frontend/`: modal e teste; depois os chamadores e seus testes.
3. Testes, lint e build nos dois apps.
4. PR; `checkin-prod` pela CLI da Vercel; painel pela Vercel no merge.

---

## 6. Detalhes por arquivo

### `checkin/src/steps/NotFoundStep.tsx` (criar)

- Mesma moldura do `NothingToDoStep`, ícone neutro (não o check verde).
- Título "Não encontramos sessão para este número". Texto: "Confira o
  celular digitado ou fale com a recepção." Botão secundário "Tentar outro
  número" que chama `onRestart`.

### `checkin/src/pages/DocumentosPage.tsx` (modificar)

- `State`: `| { step: 'not-found' }`.
- Efeito pós-código: lista vazia vai para `not-found`; senão, sessão com
  termo pendente vai para `welcome`; senão, `nothing` (como hoje).
- Render: `state.step === 'not-found'` mostra `NotFoundStep` com
  `onRestart` chamando `entrarDeNovo(null)`.
- Botão "Sair" do cabeçalho: também escondido em `not-found` (não há sessão
  para sair; o botão da tela já volta ao celular).

### `frontend/src/components/RegistrarPapelModal.tsx` (modificar)

- Props: `patientName?: string | null`.
- Título: "Termo assinado em papel - {nome}" quando há nome; sem nome, o
  título de hoje.
- Estado `confirmado` (false). Checkbox com label ligado ao input:
  "Confirmo que a paciente assinou o termo impresso e ele está na pasta."
- `Registrar` desabilitado sem data ou sem o checkbox.
- `fechar()` zera data e checkbox.
- Texto de apoio atual ("Guarde o papel na pasta...") fica.

### Chamadores

- `TermoDoAgendamento`: `patientName={a.patient_name}`.
- `TermoDeConsentimento`: nova prop `patientName?: string | null`, passada
  pelo `DocumentosPage` do painel como `paciente.name`.
- `PacientesPage`: `patientName={papelPatient.name}`.

---

## 7. Convenções a respeitar

- `frontend/CLAUDE.md`: named exports, 4 estados, Impeccable; checkbox com
  label acessível e foco visível.
- `checkin/CLAUDE.md`: copy em português claro para a paciente; nada de
  jargão.
- Nunca nome ou telefone real de paciente em código, teste ou doc.
