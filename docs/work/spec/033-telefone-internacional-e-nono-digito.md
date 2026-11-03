# Spec - 033 Telefone internacional e nono dígito

- **PRD de origem:** `prd/033-telefone-internacional-e-nono-digito.md`

## 1. Resumo

Três mudanças: a normalização de telefone passa a reconhecer número que não é
brasileiro; toda consulta de paciente por telefone passa a casar por
`variantes_do_numero`; o site aceita `+código do país`. Mais um script de
limpeza dos dois cadastros duplicados.

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/tests/unit/test_telefone_internacional.py` | normalize/valid/variantes para Holanda, Alemanha, Brasil com e sem `+` |
| `scheduler/src/scripts/une_cadastros_duplicados_033.py` | move agendamentos do duplicado para o original, corrige telefone, soft-delete do duplicado |

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/utils/phone.py` | `_parece_brasileiro(digits)`; `normalize_phone` usa; nova `is_valid_phone`; `variantes_do_numero` só BR; `format_phone_display` devolve `+N` para não-BR |
| `scheduler/src/services/appointment_service.py` | `_get_or_create_patient` e `get_active_appointment_by_phone` por `ANY(variantes)`, preferindo o exato |
| `scheduler/src/services/ai_tools.py` | `_nascimento_do_cadastro` e UPDATE de cadastro por `ANY(variantes)` |
| `scheduler/src/services/conversation_agent.py`, `desconto_personalizado.py`, `menor_de_idade.py`, `primeira_visita.py` | SELECT por `ANY(variantes)` |
| `scheduler/src/functions/send/handler.py` | UPDATE `last_message_at` por `ANY(variantes)` |
| `scheduler/src/functions/patient/create.py` | duplicidade por `ANY(variantes)` |
| `scheduler/src/functions/public_booking/send_otp.py`, `create_appointment.py` | `is_valid_phone` |
| `scheduler/tests/unit/test_nono_digito.py` | `"123"` deixa de ganhar `55` |
| `booking-site/src/utils/format.ts` (+ `.test.ts`) | `formatPhoneInput` preserva `+` e aceita até 15 dígitos; `isValidPhone`; `toApiPhone` não prefixa com `+`; `formatPhoneDisplay` mostra `+N` |
| `booking-site/src/components/CustomerInfoForm.tsx`, `MyAppointmentsModal.tsx` | usam `isValidPhone`; dica "fora do Brasil? comece com +" |

## 4. Ordem

1. `phone.py` + testes. 2. Lookups do backend. 3. Validação do site (backend). 4. Front. 5. Script de limpeza.

## 5. Convenções

Sem `any`, exports nomeados. Logging com o prefixo de módulo que cada arquivo já usa.
