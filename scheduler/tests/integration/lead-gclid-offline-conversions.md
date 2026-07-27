# Lead GCLID Tracking + Offline Conversions — Integration

Rastreamento ponta-a-ponta: anúncio → LP (gclid) → lead → agendamentos recorrentes → upload de conversões pro Google Ads.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/leads` | Cria/atualiza lead com gclid (chamado pela landing page) |

Identidade do lead: `clinic_id + phone + first_name` (nome normalizado: minúsculas, sem acento, primeiro token).

## Fluxo

1. **LP (Lovable):** JS lê `?gclid=` da URL, guarda em `localStorage`, envia no submit para `POST /leads`.
2. **Agendamento:** ao criar appointment (`AppointmentService.create_appointment`), `record_conversion` insere uma linha em `scheduler.lead_conversions` por agendamento (recorrência), casando o telefone+nome ao lead com gclid.
3. **Upload diário:** Lambda `ConversionUploader` (infra, cron 7h BRT) envia ao Google Ads cada agendamento elegível.

### Elegibilidade para upload (delay anti-cancelamento + janela gclid)
- `uploaded_at IS NULL`
- `appointments.status = 'CONFIRMED'` (não CANCELLED)
- `appointment_date < CURRENT_DATE` (sessão já ocorreu — não existe status COMPLETED)
- `conversion_date <= click_date + 90 days` (validade do gclid)

## Test Cases

| # | Caso | Status esperado | Resposta |
|---|------|-----------------|----------|
| 1 | POST lead válido com gclid | 201 | `{ status: SUCCESS, lead: {..., first_name: "maria", gclid: "..."} }` |
| 2 | POST sem `phone` | 400 | Campos obrigatórios ausentes |
| 3 | POST sem `x-api-key` | 401 | Não autorizado |
| 4 | POST mesmo telefone+nome 2x | 201 | Atualiza o mesmo lead (não duplica) |

## Test Commands

```bash
source scheduler/.env

# Caso 1 — lead válido
curl -X POST "$SCHEDULER_API_BASE/dev/leads" \
  -H "x-api-key: $SCHEDULER_API_KEY" -H "Content-Type: application/json" \
  -d '{"clinicId":"laser-beauty-sp-abc123","phone":"5511999990000","name":"Maria Silva","gclid":"TEST_GCLID_123","source":"landing-page"}'

# Local (mock)
cd scheduler && serverless invoke local -s dev -f CreateLead -p tests/mocks/lead/create_lead.json --aws-profile traffic-manager
```

## Verificação do ciclo completo
1. Migration: `python -m src.scripts.setup_database` → confere `leads.first_name`, constraint `leads_clinic_id_phone_first_name_key`, tabela `lead_conversions`, colunas `clinics.google_ads_customer_id` / `offline_conversion_action_id`.
2. Recorrência: 2 agendamentos do mesmo telefone+nome → 2 linhas em `lead_conversions`.
3. Delay: agendamento futuro/CANCELLED não entra em `get_pending_conversions`.
4. Uploader: `cd infra && serverless invoke local -s dev -f ConversionUploader` (usar gclid real de clique de teste).
5. Google Ads: validar via MCP `search` em `conversion_action` / `offline_conversion_upload_conversion_action_summary`.

## Pré-requisitos manuais (Google Ads)
- Conversion Action offline com **Count = "Every"** (recorrência), janela 90 dias → ID em `clinics.offline_conversion_action_id`.
- Auto-tagging ON.
- `clinics.google_ads_customer_id` preenchido (conta da clínica sob o MCC).
