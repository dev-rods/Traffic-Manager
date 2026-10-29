# Spec 029 — Link de cobrança pelo WhatsApp

PRD: `docs/work/prd/029-link-de-cobranca-whatsapp.md`. Branch
`feat/029-cobranca-whatsapp`, a partir da `feat/028-checkin-melhorias-pos-teste`.

## Backend (`scheduler/`)

| Arquivo | Alteração |
|---|---|
| `src/scripts/setup_database.py` | Migration idempotente: o CHECK de `appointment_payments.method` passa a aceitar `LINK` (drop/add da constraint dentro de `DO $$`). `CREATE TABLE` em sincronia. |
| `src/providers/payment_provider.py` | `LINK = "LINK"`; `METODOS_DO_CAIXA = METODOS + (LINK,)`. `METODOS` (escolhas do iPad) não muda. |
| `src/providers/asaas_provider.py` | `TIPO_DE_COBRANCA[LINK] = "UNDEFINED"`. |
| `src/services/checkin.py` | `envia_link(db, provider, whatsapp_de, clinic_id, appointment_id, cpf=None)`: agendamento CONFIRMED da clínica, valor > 0; reaproveita link pendente ainda no prazo (vencido gera outro); descarta outra cobrança pendente (`_descarta`); CPF do cadastro ou do corpo (`PrecisaDeCpf` sem nenhum); cria a cobrança `LINK` com vencimento em 7 dias; grava; manda a mensagem; devolve `{payment, invoiceUrl, sent}`. Falha do WhatsApp não desfaz a cobrança. |
| `src/services/caixa.py` | `byMethod` com `METODOS_DO_CAIXA`. |
| `src/functions/caixa/router.py` | `POST agendamentos/{id}/link` (`agenda.escrever`), corpo `{cpf?}`. `PrecisaDeCpf` → 409 `{code: "CPF_REQUIRED"}`. |

A mensagem (texto fixo):

```
Olá, {primeiro nome}! Segue o link para pagar a sua sessão de {dd/mm} às {hh:mm} na {clínica}:

Valor: R$ {valor}
{invoiceUrl}

No link você escolhe Pix, cartão ou boleto.
```

## Painel (`frontend/`)

| Arquivo | Alteração |
|---|---|
| `src/types/index.ts`, `utils/pagamento.ts` | `PaymentMethod` ganha `LINK` ("Link (WhatsApp)"); pendente de link = "Link enviado". |
| `services/caixa.service.ts`, `hooks/useCaixa.ts` | `enviarLink(appointmentId, cpf?)` e `useEnviarLink` (invalida caixa e agenda). |
| `pages/agenda/components/EnviarLinkDePagamento.tsx` (novo) | Botão, campo de CPF quando o backend pede, link para copiar quando o WhatsApp falha. |
| `PagamentoDoAgendamento.tsx`, `CaixaPanel.tsx` | Usam o componente quando não está pago. |

## iPad (`checkin/`)

`PaymentMethod` ganha `LINK`; pagamento `LINK` pendente mostra o QR da fatura
como o cartão ("Pague no seu celular"), com "Trocar forma de pagamento".

## Testes

Unitários do `envia_link` (reaproveita, substitui, já pago, CPF, falha do
WhatsApp, valor ausente), da rota, do Asaas `UNDEFINED`; painel (botão, CPF,
fallback do link); iPad (LINK pendente).
