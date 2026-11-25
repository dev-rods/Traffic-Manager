# PRD - 063 "Não encontramos" na página de documentos e trava no termo em papel

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Duas correções de UX nascidas do mesmo caso: a página de documentos pelo
celular (PRD 048) nunca mais diz "Tudo certo" para um número que não tem
sessão marcada, e o registro "Termo assinado em papel" no painel passa a
exigir uma afirmação explícita, com o nome da paciente no título, antes de
gravar.

---

## 2. Contexto

**Caso real (Essência, 25/11/2026, paciente de final 1532).** A recepção
mandou o link de documentos pelo painel às 08:44. Trinta segundos depois
alguém pediu o código na página de documentos para um número de final 1344,
que não é de paciente nenhuma da clínica. A página, sem sessão para esse
número, mostrou "Tudo certo, não há nada para preencher agora". Com essa
tela na mão, a recepcionista entendeu que o termo estava em dia e, às 08:46,
registrou "assinado em papel" na ficha da paciente. Resultado: a paciente
está sem termo válido (nenhum SIGNED, nenhum evento da ClickSign) e a ficha
afirma uma assinatura que não aconteceu.

Dois defeitos, um em cada ponta:

1. `checkin/src/pages/DocumentosPage.tsx`: depois do código, procura na lista
   de sessões uma com termo pendente; se não acha, vai para `nothing` ("Tudo
   certo"). Lista vazia cai no mesmo ramo. A tela do iPad trata o caso
   ("Não encontramos seu agendamento"); a de documentos não.
2. `frontend/src/components/RegistrarPapelModal.tsx`: o modal tem data e
   "Registrar", mas não diz o que está sendo afirmado nem de quem. Um clique a
   mais grava um termo em papel que vale como assinatura (PRD 036/047).

---

## 3. Escopo

### Dentro do escopo
- Página de documentos (`checkin/`): lista vazia mostra "Não encontramos
  sessão para este número. Confira o celular ou fale com a recepção." com
  "Tentar outro número", que volta ao celular. "Tudo certo" só quando há
  sessão e nenhum termo pendente.
- Modal do papel (`frontend/`): título "Termo assinado em papel - {nome}",
  checkbox obrigatório "Confirmo que a paciente assinou o termo impresso e
  ele está na pasta", "Registrar" desabilitado até marcar. Os três lugares
  que abrem o modal (agenda, pasta do paciente, lista de pacientes) passam o
  nome.

### Fora do escopo
- Registro em lote (`BatchPapelModal`): já tem aviso próprio e lista de
  resultado; fica como está.
- Backend: nenhuma rota muda. Log do "nada a fazer" com a contagem de
  sessões fica anotado como melhoria de diagnóstico, não entra aqui.
- Regularizar a paciente do caso: operacional, pelo painel ("Pedir nova
  assinatura" no registro em papel e reenviar o link).

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `checkin/src/pages/DocumentosPage.tsx` | modificar | estado `not-found`; lista vazia não vira `nothing` |
| `checkin/src/steps/NotFoundStep.tsx` | criar | tela "Não encontramos sessão para este número" |
| `checkin/src/pages/DocumentosPage.test.tsx` | modificar | caso lista vazia; `nothing` só com sessão |
| `frontend/src/components/RegistrarPapelModal.tsx` | modificar | `patientName`, checkbox, botão travado |
| `frontend/src/components/RegistrarPapelModal.test.tsx` | modificar | trava, nome no título |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` | modificar | passa `a.patient_name` |
| `frontend/src/pages/documentos/components/TermoDeConsentimento.tsx` | modificar | recebe e passa `patientName` |
| `frontend/src/pages/documentos/DocumentosPage.tsx` | modificar | passa `paciente.name` |
| `frontend/src/pages/pacientes/PacientesPage.tsx` | modificar | passa `papelPatient.name` |
| testes dos chamadores | modificar | marcam o checkbox antes de "Registrar" |

---

## 5. Dependências e riscos

- **Dependências:** nenhuma de backend. Deploy: `checkin-prod` pela CLI da
  Vercel (token em `/prod/VERCEL_API_TOKEN`), painel pela Vercel no merge.
- **Riscos:** baixos. A trava acrescenta um clique a quem registra papel de
  verdade; é o custo pedido. A tela nova do check-in só aparece quando a
  lista vem vazia, caso que hoje mostra a mensagem errada.

---

## 6. Critérios de aceite

- [ ] Página de documentos com número sem sessão: "Não encontramos sessão
      para este número", sem "Tudo certo", com volta ao celular.
- [ ] Página de documentos com sessão e termo já resolvido: "Tudo certo"
      como antes.
- [ ] Modal do papel: título com o nome, "Registrar" desabilitado até
      marcar "Confirmo que a paciente assinou o termo impresso e ele está
      na pasta"; cancelar limpa o checkbox.
- [ ] Testes de `checkin/` e `frontend/`, lint e build limpos.
- [ ] `checkin-prod` publicado e painel no ar; caso do número sem sessão
      conferido na página de documentos de prod com o celular do André.

---

## 7. Referências

- PRD 036 (termo pela ClickSign), 047 (papel por paciente), 048 (documentos
  pelo celular), 053 (confirmação inline nas ações da agenda).
- `checkin/CLAUDE.md`, `frontend/CLAUDE.md`.

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/063-nao-encontramos-e-trava-do-papel.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
