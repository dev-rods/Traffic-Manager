# PRD - 065 Falta a assinatura: a última etapa do link e os rótulos do painel

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Na jornada do link de documentos (PRD 048), a paciente passa por celular,
dados, ficha de anamnese e só então chega ao widget da ClickSign. É nesse
ponto que ela se sente "pronta" e fecha a página, e o termo fica "assinando"
para sempre. Do outro lado, a recepção vê na agenda o selo "Assinando", que difere de
"Assinado" por uma letra e usa a mesma cor de atenção.

Este PRD deixa explícito, para as duas pontas, o que falta: na jornada do
link, antes e durante o widget, que a assinatura é a última etapa e que sem
ela nada vale; no painel, rótulos que começam com "Falta" para todo estado
pendente. Só front-end (`checkin/` e `frontend/`); o iPad não muda.

---

## 2. Contexto

**Caso real (Essência, 26/11/2026, paciente de final 7306).** Link enviado
pelo painel às 11:34. A paciente entrou, respondeu a ficha e os dados em um
minuto e meio, o envelope foi criado às 11:35:58 e a ClickSign registrou o
widget aberto às 11:35:59. Em menos de 10 segundos ela fechou a página: o
polling de 3 s da tela de assinatura fez 2 chamadas em 11:36 e nenhuma
depois. Na ClickSign não há evento `sign`; o envelope vence sozinho em 48 h.
A paciente disse à clínica que "concluiu". Pelo lado dela, concluiu mesmo:
a parte longa estava feita, e a tela seguinte era um iframe carregando.

O sistema refletiu com fidelidade o que aconteceu. O defeito é de jornada:
nada diz "faltam N etapas" nem "a assinatura é a última e obrigatória". O
botão da última tela da ficha diz "Continuar para a assinatura", e a tela do
widget diz "Leia, digite o código do WhatsApp e assine na tela". Nenhuma
frase diz que fechar agora perde o trabalho.

**No painel (reportado pela Essência em 26/11).** Os rótulos do termo em
`frontend/src/utils/termo.ts` são "Assinado", "Em papel", "Assinando",
"Preenchendo pelo link", "Pendente". "Assinando" e "Assinado" não se
distinguem de relance, e SIGNING e FILLING usam o tom de atenção, o mesmo do
"Dispensado", que é um estado resolvido. A recepção lê "assinando" como
quase pronto, quando é o oposto: a paciente parou antes do passo que vale.

---

## 3. Escopo

### Dentro do escopo

**A. Jornada no link de documentos (`checkin/`)**

- Indicador de etapas no cabeçalho das telas de dados, ficha e assinatura:
  "Etapa 1 de 3 - Seus dados", "Etapa 2 de 3 - Ficha de saúde",
  "Etapa 3 de 3 - Assinatura". Só no modo remoto (`DocumentosPage`).
- Na última tela da ficha, acima do botão "Continuar para a assinatura":
  "Falta só a assinatura. Sem ela, a ficha e o termo não valem."
- Na tela do widget (`ConsentSignStep`), o subtítulo passa a dizer
  "Última etapa. Digite o código que chega no WhatsApp e assine na tela.
  Não feche antes de ver 'Documento assinado'." O `aria-live` continua.
**B. Rótulos do termo no painel (`frontend/`)**

Estado concluído é particípio; estado pendente começa com "Falta" e diz o
que falta. Decidido pelo André em 26/11, com o parêntese.

| Estado | Hoje | Novo | Tom |
|---|---|---|---|
| SIGNED | Assinado | Assinado | ok |
| PAPER | Em papel | Assinado em papel | ok |
| SIGNING | Assinando | Falta assinar (abriu o link) | pendente |
| FILLING | Preenchendo pelo link | Falta a ficha (abriu o link) | pendente |
| nenhum | Pendente | Falta o termo | pendente |
| dispensado | Dispensado por X em ... | mantém | atencao |
| sem versão | Não configurado | mantém | nada |

- A mudança vive em `situacaoDoTermo` (`frontend/src/utils/termo.ts`), fonte
  única do selo da agenda, do pop-up do termo e da pasta da paciente.
- "(abriu o link)" vale também para termo iniciado no iPad, porque o front
  não sabe a origem; aceito, porque SIGNING no iPad dura segundos e
  raramente é visto na agenda. Distinguir a origem é dado novo do backend e
  fica fora.
- Textos de ação ("Enviar link", "Registrar papel", "Dispensar") não mudam.

### Fora do escopo

- Lembrete pelo WhatsApp quando o termo fica "assinando": retirado deste
  PRD por decisão do André em 26/11; fica para PRD próprio, se voltar.
- Quem volta pelo link com envelope vivo cair direto no widget (D3):
  adiado em 26/11 para o PRD do lembrete, que é quem cria o caminho de
  volta. Exigiria a lista de sessões devolver o termo SIGNING em andamento
  (backend). Hoje a pessoa passa por dados e ficha já preenchidos com um
  toque em cada, e `inicia` reaproveita o envelope de até 24 h.
- Selo na agenda distinguindo "abriu e não assinou" de "nem abriu", com
  botão de reenviar: proposta 3 do diagnóstico de 26/11, PRD próprio.
- Selo "nem abriu o link" (exigiria `started_via` no backend): PRD próprio.
- Backend: nenhuma rota, coluna ou Lambda muda.
- iPad (`CheckinPage`): sem etapas, sem textos novos.
- Mudar o prazo de 24 h de reaproveitamento do SIGNING.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `checkin/src/components/StepHeader.tsx` | modificar | prop opcional `etapa` ("Etapa 2 de 3 - Ficha de saúde"), acima do título |
| `checkin/src/steps/ConsentDataStep.tsx`, `AnamneseStep.tsx`, `ConsentSignStep.tsx` | modificar | recebem `remoto`; etapa no cabeçalho; aviso acima do último "Continuar"; subtítulo do widget |
| `checkin/src/pages/DocumentosPage.tsx` | modificar | passa `remoto` aos passos |
| `checkin/src/pages/DocumentosPage.test.tsx` | modificar | etapas visíveis, aviso na última tela, subtítulo do widget |
| `checkin/src/pages/CheckinPage.test.tsx` | modificar | garante que o iPad não mostra etapas nem o aviso |
| `frontend/src/utils/termo.ts` | modificar | novos rótulos e tons em `situacaoDoTermo` |
| `frontend/src/utils/termo.test.ts`, `TermoPendenteBadge.test.tsx`, `TermoDoAgendamento.test.tsx`, `SeloSemTermo.test.tsx` | modificar | asserções com os rótulos novos |

---

## 5. Dependências e riscos

- **Deploy:** `checkin-prod` e `checkin-dev` pela Vercel CLI (receita do
  PRD 048); o painel sobe sozinho no merge. Scheduler não sobe.
- **Risco baixo:** só textos e um indicador; nenhuma lógica nova.
- **Layout do iPad:** `ConsentSignStep` trava a altura da página nesse passo;
  a linha de etapa só aparece no remoto, então a altura do iPad não muda.

---

## 6. Critérios de aceite

- [ ] No link de documentos, dados, ficha e assinatura mostram "Etapa N de
      3"; no iPad nada aparece.
- [ ] A última tela da ficha mostra o aviso de que falta a assinatura.
- [ ] A tela do widget diz que é a última etapa e para não fechar antes de
      "Documento assinado".
- [ ] Na agenda, pop-up e pasta da paciente, nenhum selo diz "Assinando";
      SIGNING mostra "Falta assinar (abriu o link)" no tom pendente, PAPER
      mostra "Assinado em papel".
- [ ] Testes de `checkin/` e `frontend/` verdes, lint e build limpos nos dois.
- [ ] Conferido em prod na largura de celular (headless) e, se possível, no
      aparelho do André.

---

## 7. Referências

- Diagnóstico de 26/11/2026 nesta sessão (envelope `e619f0ca...`, só
  `signature_started`).
- PRD 036 (ClickSign), 038 (anamnese), 048 (link de documentos), 062
  (SIGNED no `sign`).
- `scheduler/src/services/consentimento.py` (`REAPROVEITA_SIGNING_ATE`,
  `resumo_para_o_ipad`).

---

## Decisões (todas fechadas em 26/11/2026)

- Rótulos do painel com o parêntese "(abriu o link)" e dentro deste PRD
  (André, 26/11).
- D1: os textos da jornada ficam como propostos na seção 3-A (etapas
  numeradas, "Falta só a assinatura. Sem ela, a ficha e o termo não valem.",
  "Última etapa... Não feche antes de ver 'Documento assinado'."). Tom
  direto, com a consequência, em vez de incentivo (André, 26/11).
- D3: "volta pelo link cai no widget" retirado (André, 26/11); ver Fora do
  escopo.
- D2: indicador de etapas como linha de texto acima do título, sem barra
  de progresso (André, 26/11).

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/065-falta-a-assinatura.md` (26/11/2026)
- [x] Implementado em: 2026-11-26 (PR #280; checkin-prod e checkin-dev pela CLI, painel pela Vercel)
- [x] Registrado em `TASKS_LOG.md`
