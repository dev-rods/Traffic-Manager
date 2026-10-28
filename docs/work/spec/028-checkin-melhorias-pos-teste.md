# Spec — 028 Check-in: melhorias depois do primeiro teste gravado

> Gerado na fase **Spec**. Use como input para a fase Code.

- **PRD de origem:** `prd/028-checkin-melhorias-pos-teste.md`
- **Branch:** `feat/028-checkin-melhorias-pos-teste`
- **Deploy:** só dev.

## Backend (`scheduler/`)

| Arquivo | Alteração |
|---|---|
| `src/utils/booking_verification.py` | Em dev, `generate_and_send_code` devolve o código sempre (M4). |
| `src/providers/payment_provider.py` | Status `REFUNDED` já existe; interface ganha `estorna(cobranca_id)`. |
| `src/providers/asaas_provider.py` | `estorna`: `POST /payments/{id}/refund`. |
| `src/providers/simulated_payment_provider.py` | `estorna` sem efeito. |
| `src/services/checkin.py` | `estorna(db, provider, clinic_id, payment_id)`: só `PAID` de sessão `CANCELLED`; dinheiro (`CASH`) não chama o provedor; marca `REFUNDED`. |
| `src/services/caixa.py` | `pagamentos` traz `appointmentCancelled`; `resumo` ganha `refundsPending` (pagos de sessões canceladas, sem filtro de período) e `totals.refundsPendingCents`. |
| `src/functions/caixa/router.py` | `POST pagamentos/{id}/estorno` com `require_api_key` (dinheiro saindo: só admin). |

## App do iPad (`checkin/`)

| Arquivo | Alteração |
|---|---|
| `steps/AppointmentStep.tsx` | Selo de estado em cada item (M1); pago → `onAlreadyPaid`; check-in feito → botão "Continuar para o pagamento". |
| `pages/CheckinPage.tsx` | Cabeçalho com logo e "Recomeçar" com ícone (M3); trata o pago direto. |
| `steps/DoneStep.tsx` + `index.css` | Animação de conclusão (M2), com `prefers-reduced-motion`. |
| `steps/PaymentStep.tsx` | Duas colunas em `landscape` largo (M6); dica completa do cartão de teste (M5). |

## Painel (`frontend/`)

| Arquivo | Alteração |
|---|---|
| `services/caixa.service.ts`, `hooks/useCaixa.ts` | `refundsPending`, `appointmentCancelled`, mutation `estornar`. |
| `pages/relatorios/components/CaixaPanel.tsx` | Seção "Estornos pendentes" com "Estornar" (confirmação), selo "sessão cancelada" nos recebimentos (M7). |
| `pages/agenda/components/CancelAppointmentModal.tsx` | Aviso quando o agendamento já está pago (M7). |

## Testes

Unitários de backend para estorno (serviço, provedor, rota), código em dev,
caixa com cancelados; front do check-in (selos, pago direto) e do painel
(estornos pendentes, aviso no cancelamento).
