# Spec - 065 Falta a assinatura: a última etapa do link e os rótulos do painel

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/065-falta-a-assinatura.md`

---

## 1. Resumo

Só front, nos dois apps. No `checkin/`, as três telas do link de documentos
ganham a linha "Etapa N de 3" acima do título, a última tela da ficha avisa
que falta a assinatura e o widget diz para não fechar antes de "Documento
assinado". Quem volta pelo link segue como hoje (dados e ficha preenchidos,
envelope reaproveitado pelo backend); D3 foi adiado para o PRD do lembrete. No `frontend/`, os rótulos do termo deixam de usar
"Assinando": todo estado pendente começa com "Falta", em três lugares que
hoje decidem o texto por conta própria.

---

## 2. Arquivos a criar

Nenhum.

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `checkin/src/components/StepHeader.tsx` | prop opcional `etapa?: string`, renderizada acima do `h1` |
| `checkin/src/steps/ConsentDataStep.tsx` | prop `etapa?: string` repassada ao `StepHeader` |
| `checkin/src/steps/AnamneseStep.tsx` | prop `etapa?: string`; prop `avisoFinal?: boolean`: aviso acima do botão na última tela |
| `checkin/src/steps/ConsentSignStep.tsx` | prop `remoto?: boolean`; linha de etapa; subtítulo novo |
| `checkin/src/pages/DocumentosPage.tsx` | passa `etapa`, `avisoFinal` e `remoto` |
| `checkin/src/pages/DocumentosPage.test.tsx` | etapas visíveis; aviso na última tela; subtítulo do widget |
| `checkin/src/pages/CheckinPage.test.tsx` | iPad: sem "Etapa", sem o aviso, subtítulo antigo |
| `frontend/src/utils/termo.ts` | rótulos e tons novos em `situacaoDoTermo`; campo `semNada: boolean` |
| `frontend/src/pages/agenda/components/TermoPendenteBadge.tsx` | `title` pelo `semNada`, não pela string "Pendente" |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.tsx` | estado otimista `emPapel` usa "Assinado em papel" |
| `frontend/src/pages/documentos/components/TermoDeConsentimento.tsx` | mapa `SITUACAO` com os rótulos novos |
| `frontend/src/pages/agenda/components/TermoDoAgendamento.test.tsx` | asserções com "Falta assinar (abriu o link)", "Falta a ficha (abriu o link)", "Falta o termo", "Assinado em papel" |
| `frontend/src/pages/agenda/components/TermoPendenteBadge.test.tsx` | `title` dos três pendentes |
| `frontend/src/pages/documentos/components/TermoDeConsentimento.test.tsx` | rótulos novos na aba |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. `frontend/`: `termo.ts` e os três componentes; testes; lint e build.
   Independente do resto, pode ir em PR próprio se o André preferir.
2. `checkin/`: `StepHeader`, passos, página; testes; lint e build.
3. Conferência em `checkin-dev` na largura de celular (headless ou no
   aparelho do André): as três telas e o widget.
4. PR; `checkin-prod` e `checkin-dev` pela CLI da Vercel; painel sobe no
   merge. Scheduler não sobe.

---

## 6. Detalhes por arquivo

### 6.1 `checkin/src/components/StepHeader.tsx` (modificar)

- Prop `etapa?: string`. Quando presente, antes do `h1`:
  ```tsx
  <p className="font-display text-sm font-semibold uppercase tracking-wide text-ink-500">{etapa}</p>
  ```
  Mesmo alinhamento do bloco (`text-center`). Sem `etapa`, nada muda: o
  iPad nunca passa a prop.

### 6.2 Passos (`checkin/src/steps/`)

**`ConsentDataStep.tsx`**: prop `etapa?: string`, repassada:
`<StepHeader title="Confira seus dados" etapa={etapa}>`.

**`AnamneseStep.tsx`**: props `etapa?: string` e `avisoFinal?: boolean`.
- `StepHeader` recebe `etapa`.
- Na última tela (`ultima`) e com `avisoFinal`, acima do bloco de botões:
  ```tsx
  <p role="status" className="rounded-2xl border-2 border-accent-200 bg-accent-50 px-5 py-4 text-center text-base text-ink-800">
    Falta só a assinatura. Sem ela, a ficha e o termo não valem.
  </p>
  ```
  Tom de destaque, não de erro (`ErrorMessage` é vermelho e diz "deu
  errado"; aqui nada deu errado).

**`ConsentSignStep.tsx`**: prop `remoto?: boolean`.
- Cabeçalho: com `remoto`, a linha `Etapa 3 de 3 - Assinatura` acima do
  `h1` (mesma classe do `StepHeader`; o cabeçalho aqui é próprio porque a
  tela trava a altura).
- Subtítulo (`<p aria-live="polite">`), nesta ordem:
  - `assinou`: "Assinatura recebida. Estamos registrando o documento…"
    (como hoje).
  - `remoto`: "Última etapa. Digite o código que chega no WhatsApp e assine
    na tela. Não feche antes de ver 'Documento assinado'."
  - iPad: os dois textos atuais, sem mudança.
- A altura do bloco cresce uma linha no celular; a página já usa
  `h-dvh overflow-hidden` neste passo e o iframe ocupa o resto com
  `min-h-0 flex-1`. Conferir em 360 px de largura que o botão "Tela cheia"
  continua visível.

### 6.3 `checkin/src/pages/DocumentosPage.tsx` (modificar)

- Constantes locais:
  ```ts
  const ETAPAS = { dados: 'Etapa 1 de 3 - Seus dados', ficha: 'Etapa 2 de 3 - Ficha de saúde' }
  ```
- Render: `ConsentDataStep etapa={ETAPAS.dados}`; `AnamneseStep
  etapa={ETAPAS.ficha} avisoFinal`; `ConsentSignStep remoto`.
- Estado, efeito pós-código e `onRestart` não mudam.

### 6.4 Testes do `checkin/`

**`DocumentosPage.test.tsx`**, novos casos:
- "mostra Etapa 1 de 3 nos dados e Etapa 2 de 3 na ficha".
- "a última tela da ficha avisa que falta a assinatura" (texto presente só
  em `tela === screens.length`).
- "o widget diz que é a última etapa e para não fechar" (no mock, `Consent`
  SIGNING com `canSimulate: true` para não montar o widget real).

**`CheckinPage.test.tsx`**: um caso "iPad não mostra etapas nem o aviso da
ficha" (`queryByText(/Etapa \d de 3/)` nulo; aviso nulo na última tela).

### 6.5 `frontend/src/utils/termo.ts` (modificar)

- `SituacaoDoTermo` ganha `semNada: boolean` (nenhum termo iniciado) para o
  `title` do badge não comparar string.
- `situacaoDoTermo`:
  ```ts
  if (a.consent_status === 'SIGNED') return { label: 'Assinado', tom: 'ok', pendente: false, semNada: false }
  if (a.consent_status === 'PAPER') return { label: 'Assinado em papel', tom: 'ok', ... }
  // dispensado: igual, tom 'atencao'
  if (a.consent_status === 'SIGNING') return { label: 'Falta assinar (abriu o link)', tom: 'pendente', pendente: true, semNada: false }
  if (a.consent_status === 'FILLING') return { label: 'Falta a ficha (abriu o link)', tom: 'pendente', pendente: true, semNada: false }
  return { label: 'Falta o termo', tom: 'pendente', pendente: a.status === 'CONFIRMED', semNada: true }
  ```
- Comentário no topo da função: "Concluído é particípio; pendente começa
  com 'Falta' e diz o que falta. 'Assinando' saiu em 26/11/2026: a Essência
  não distinguia de 'Assinado'."
- `semTermo` não muda.

### 6.6 Componentes do painel

**`TermoPendenteBadge.tsx`**: `title={situacao.semNada ? 'Termo e anamnese
pendentes' : situacao.label}`.

**`TermoDoAgendamento.tsx`**: o estado otimista `emPapel` passa a
`{ label: 'Assinado em papel', tom: 'ok', pendente: false, semNada: false }`.
Os outros dois estados otimistas ("Dispensado nesta sessão", "Nova
assinatura pedida") ficam. Conferir onde `situacao.tom` vira classe: o tom
`pendente` já existe para "Nova assinatura pedida", então SIGNING e FILLING
herdam a cor certa sem CSS novo.

**`TermoDeConsentimento.tsx`**: mapa `SITUACAO`:
- `FILLING`: "Falta a ficha (abriu o link)", cor do pendente (a mesma de
  `CANCELLED`/`EXPIRED` não serve; usar a classe que o painel usa para
  pendente, ver `Badge variant="warning"`).
- `SIGNING`: "Falta assinar (abriu o link)", mesma cor.
- `PAPER`: "Assinado em papel".
- Demais iguais. Esta aba é histórico por linha, por isso mantém mapa
  próprio; os rótulos é que precisam bater com `termo.ts`. Anotar isso em
  comentário nos dois arquivos.

### 6.7 Testes do `frontend/`

- `TermoDoAgendamento.test.tsx`: trocar "Em papel" -> "Assinado em papel",
  "Pendente" -> "Falta o termo", "Assinando" -> "Falta assinar (abriu o
  link)", "Preenchendo pelo link" -> "Falta a ficha (abriu o link)".
- `TermoPendenteBadge.test.tsx`: `title` de SIGNING é o rótulo novo; de
  "nenhum" continua "Termo e anamnese pendentes".
- `TermoDeConsentimento.test.tsx`: linha SIGNING mostra o rótulo novo.
- `AppointmentPopover.test.tsx`: o "Pendente" ali é presença, não termo;
  não muda.

---

## 7. Convenções a respeitar

- Fonte única: `situacaoDoTermo` decide rótulo e tom para agenda, pop-up e
  pasta; o mapa da aba histórica só repete os textos. Varrer com
  `grep -rn "Assinando\|Em papel\|Preenchendo pelo link"` antes de fechar o PR.
- Nenhum nome real de paciente em testes, commits ou docs.
- Build completo (`npm run build`) nos dois apps depois da última edição.
- Deploy: checkin pela CLI da Vercel com os ids do PRD 048; painel no merge.
- Sem travessão nos textos de tela: hífen simples.

---

## 8. Critérios de aceite (do PRD, com o teste que prova cada um)

| Critério | Prova |
|---|---|
| Etapas nas três telas do link, nada no iPad | `DocumentosPage.test` + `CheckinPage.test` |
| Aviso na última tela da ficha | `DocumentosPage.test` |
| Widget diz "última etapa" e "não feche" | `DocumentosPage.test` |
| Nenhum "Assinando" no painel; PAPER vira "Assinado em papel" | testes do `frontend/` + grep |
| Testes, lint e build verdes nos dois apps | CI local antes do PR |
