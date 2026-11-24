# SPEC - 062 Check-in: a assinatura libera o pagamento na hora

> PRD: `docs/work/prd/062-assinatura-libera-pagamento-na-hora.md`

## 1. `scheduler/src/services/consentimento.py`

- Constantes:
  - `EVENTOS_ASSINADO = ("sign", "signed", "signer.signed")`
  - `EVENTOS_PDF_PRONTO = ("document_closed", "document.closed")`
- `PdfPendente(Exception)`: documento fechado, PDF ainda não baixou.
- `_marca_assinado(db, row)`: `UPDATE ... SET status='SIGNED',
  signed_at=COALESCE(signed_at, NOW()) WHERE id AND status='SIGNING'
  RETURNING *`. Sem RETURNING (corrida), relê a linha.
- `_sem_pdf(row, provider)`: SIGNED, sem `pdf_s3_key`, do provedor ativo,
  com envelope.
- `_arquiva(db, provider, row)`: só se `_sem_pdf`. Baixa PDF (falha →
  devolve a linha sem PDF, log INFO), grava no S3, tenta o zip, `UPDATE ...
  SET pdf_s3_key, pdf_sha256, audit_s3_key WHERE id AND status='SIGNED' AND
  pdf_s3_key IS NULL RETURNING *`.
- `_fecha(db, provider, row)` = `_arquiva(_marca_assinado(row))`, com as
  mesmas guardas de antes (SIGNING e provedor igual).
- `_sincroniza`: SIGNED sem PDF → `_arquiva`; o resto igual (envelope
  `closed` → `_fecha`, que já não espera o PDF).
- `_processa_evento`, para `EVENTOS_ASSINADO` + `EVENTOS_FECHADO`:
  - linha SIGNING → `_fecha`; linha SIGNED → `_arquiva`;
  - com PDF → `"SIGNED"`; sem PDF e evento em `EVENTOS_PDF_PRONTO` → levanta
    `PdfPendente`; sem PDF nos outros → `"SIGNED: PDF pendente"`;
  - outro status (CANCELLED, EXPIRED, REVOKED, PAPER) → `"ignorado: já X"`.
- `aplica_evento` não muda: o evento só é gravado depois de processado, então
  o `PdfPendente` não marca o evento como visto e o reenvio é processado.

## 2. `scheduler/src/functions/public_booking/clicksign_webhook.py`

- `except consentimento.PdfPendente`: warning (sem traceback) e 500.

## 3. `checkin/`

- `useConsentStatus`: comentário do polling rápido (1,5 s) atualizado.

## 4. Testes

- `test_consentimento.py`: fake do banco com os dois UPDATEs; casos
  `sign` → `auto_close` → `document_closed`; `document_closed` sem PDF levanta
  e não grava o evento; SIGNED com PDF não baixa de novo; `sign` depois de
  cancelado é ignorado; polling sem PDF marca SIGNED e arquiva no polling
  seguinte.
- `test_clicksign_webhook.py`: `PdfPendente` → 500.

## 5. Ordem

1. Serviço e webhook + testes unitários.
2. Check-in: só o comentário (sem deploy do front).
3. Deploy scheduler dev, conferir a sequência de webhooks e a linha.
4. Prod: scheduler.
