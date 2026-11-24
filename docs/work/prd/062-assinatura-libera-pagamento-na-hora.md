# PRD - 062 Check-in: a assinatura libera o pagamento na hora

> Gerado na fase **Research** em 24/11/2026. Use como input para a fase Spec.
> Card do Notion: "Check-in: Tempo de espera muito longo entre assinatura e
> início do pagamento".

---

## 1. Objetivo

Depois que a paciente assina o termo no iPad, a tela de conferir o
agendamento e pagar aparece em ~1 a 2 s, e não mais em 25 a 30 s.

---

## 2. Contexto

### 2.1 O que acontece hoje (medido nos logs de prod, 18/11/2026)

O termo só vira `SIGNED` depois que o backend **baixa o PDF assinado da
ClickSign e grava no S3** (`consentimento._fecha`). Até lá o iPad fica em
"Assinatura recebida! Aguarde alguns segundos". A sequência de webhooks de
cada assinatura em prod:

| Evento ClickSign | Depois do toque em "Assinar" | O que fazíamos |
|---|---|---|
| `sign` | ~0,3 s | ignorado |
| `auto_close` (envelope fechado) | ~8 a 12 s | tentava o PDF: "ainda sem PDF assinado" |
| `document_closed` (PDF pronto) | ~20 a 30 s | baixava, gravava, marcava SIGNED |

Exemplos: 01:59:52 → 02:00:17 (25 s), 10:25:57 → 10:26:21 (24 s),
12:06:36 → 12:07:03 (27 s), 12:57:13 → 12:57:43 (30 s). Em 14 dias, 71 avisos
"PDF ainda não disponível" do polling e dos webhooks.

### 2.2 Por que dá para liberar antes

- O envelope tem **um signatário só** e `auto_close: true`
  (`clicksign_provider.cria_termo`). O evento `sign` dessa signatária é o termo
  assinado; o `auto_close` é consequência.
- O webhook é autenticado por HMAC do corpo cru (`clicksign_webhook`), então
  o `sign` tem a mesma confiança do `document_closed`.
- O PDF é registro para o prontuário, não condição para atender: termo em
  papel (`PAPER`) já é vigente sem PDF nenhum.

---

## 3. Escopo

### Dentro do escopo
- `sign` (e variantes `signed`, `signer.signed`) marca o termo `SIGNED` na
  hora, com `signed_at = NOW()`.
- Marcar assinado e arquivar o PDF viram dois passos independentes. Falha do
  PDF não segura mais a paciente.
- O PDF (e o zip) são arquivados no próximo evento de fechamento ou polling
  que encontrar o termo SIGNED sem `pdf_s3_key`.
- `document_closed` com o PDF ainda indisponível responde **500**, para a
  ClickSign reenviar: é a garantia de que todo SIGNED ganha o PDF.
- Polling (fallback sem webhook): envelope `closed` marca SIGNED sem esperar o
  PDF.
- Vale também para a assinatura pelo celular (`/:clinicId/documentos`, PRD
  048), que usa o mesmo `ConsentSignStep` e o mesmo backend.

### Fora do escopo
- Tempo de preparar o envelope antes da assinatura (`ESPERA_DOCUMENTO_S`).
- Tempo de criar a cobrança no Asaas (sem cobrança pelo iPad em prod no
  período medido).
- Texto da faixa "Assinatura recebida" (fica ~1 s na tela agora; a PR #207
  já trata o texto pelo celular).
- Painel: o botão "Abrir PDF" continua desabilitado até o PDF chegar
  (`has_pdf`), o que hoje dura ~20 s.

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/consentimento.py` | modificar | `_marca_assinado`, `_arquiva`, `_fecha` em dois passos, `EVENTOS_ASSINADO`, `EVENTOS_PDF_PRONTO`, `PdfPendente` |
| `scheduler/src/functions/public_booking/clicksign_webhook.py` | modificar | `PdfPendente` vira 500 com warning |
| `scheduler/tests/unit/test_consentimento.py` | modificar | sequência real sign → auto_close → document_closed |
| `scheduler/tests/unit/test_clicksign_webhook.py` | modificar | 500 no PDF pendente |
| `checkin/src/hooks/useCheckin.ts` | modificar | comentário do polling rápido |

---

## 5. Dependências e riscos

- **Sem migration, sem rota nova, sem env var.**
- **Risco: SIGNED que nunca ganha PDF.** Mitigado pelo 500 no
  `document_closed` (reenvio da ClickSign) e pelo polling que arquiva. Se
  acontecer, o log `[ClicksignWebhook] ... PDF de X indisponível` aparece a
  cada reenvio.
- **Risco: `sign` de envelope com mais de um signatário.** Não existe hoje
  (um envelope por termo, um signatário). Se um dia houver, o `sign` deixa de
  significar "termo assinado" e esta regra precisa mudar.

---

## 6. Critérios de aceite

- [ ] Webhook `sign` deixa o termo `SIGNED` com `pdf_s3_key` nulo, e o iPad
      sai da tela de assinatura em até ~2 s depois de assinar.
- [ ] `document_closed` arquiva PDF (e zip) e grava `pdf_s3_key`/`pdf_sha256`.
- [ ] `document_closed` sem PDF responde 500 e não grava o evento.
- [ ] Termo cancelado não volta a SIGNED por um `sign` atrasado.
- [ ] Painel mostra o PDF assim que arquivado.

---

## 7. Referências

- PRD 036 (termo de consentimento), PRD 026 (check-in)
- `scheduler/tests/integration/036-termo-de-consentimento.md`

---

## Status (preencher após conclusão)

- Spec: `docs/work/spec/062-assinatura-libera-pagamento-na-hora.md`
