# Spec - 056 Uma sessão por mês: código sempre no site e troca do agendamento existente

> Gerado na fase **Spec** em 21/11/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/056-uma-sessao-por-mes-e-codigo-no-site.md`

---

## 1. Resumo

A regra "um agendamento futuro por mês-calendário por paciente" entra em um
lugar só, `AppointmentService`, e é aplicada em criar (`create_appointment`) e
em mover a data (`remarca`). Quem chama recebe o conflito como exceção
`SessaoNoMesmoMes`, com a sessão existente, e cada tela monta o aviso. A troca
confirmada é um parâmetro `substituir_mesmo_mes=True` na mesma chamada: o
serviço cancela a sessão existente com o desfecho da 054 (falta nas últimas
24 h), cria a nova e leva vínculo, pagamento vivo, link dos documentos e
conversão, exatamente como `remarca` já faz. A exceção "manter as duas" é um
segundo parâmetro, `permitir_duas=True`, que só o handler do painel aceita, só
de ADMIN e só com motivo, gravado no agendamento novo.

No site, criar passa a exigir o token do código do WhatsApp; o fluxo ganha a
etapa "verify" entre "Seus dados" e a confirmação; "Manter os dois"
(`confirmDuplicate`/`HAS_FUTURE_APPOINTMENT`) sai. No bot, `segunda_sessao`
sai do schema e a recusa passa a ser por mês. No painel, criar e editar mostram
a confirmação inline com "Confirmar" (substituir) e, para ADMIN, "Manter as
duas" com motivo.

Por que `substituir` na criação e não o endpoint de remarcação: o agendamento
novo nasce com o carrinho, a cotação e o cadastro que a pessoa acabou de
preencher, e `vincula_antecessor` (já dentro do create) liga o cancelado ao
novo e move a conversão. Só falta levar pagamento e link dos documentos, que
hoje estão em `remarca`; isso vira um helper compartilhado.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `booking-site/src/components/RemarcacaoDialog.tsx` | Substitui `DuplicateBookingDialog`: aviso curto, botão do WhatsApp (`wa.me`), "Confirmar remarcação" / "Voltar" |
| `booking-site/src/components/RemarcacaoDialog.test.tsx` | Texto, link `wa.me` presente/ausente, botões |
| `frontend/src/pages/agenda/components/ConflitoDoMes.tsx` | Bloco inline do painel: aviso, "Confirmar", "Voltar" e, para ADMIN, "Manter as duas" com campo de motivo |
| `frontend/src/pages/agenda/components/ConflitoDoMes.test.tsx` | STAFF não vê "Manter as duas"; ADMIN precisa de motivo |
| `scheduler/tests/unit/test_sessao_no_mesmo_mes.py` | Regra no serviço: mesmo mês, mês seguinte, virada de ano, próprio id excluído, status não confirmado, `substituir`, `permitir_duas`, `remarca` com terceira sessão |
| `scheduler/tests/unit/test_bot_mesmo_mes.py` | Substitui `test_book_recusa_segunda_sessao.py`: recusa só no mesmo mês, sem saída; outro mês cria e avisa; `alterar_agendamento` com conflito |
| `scheduler/tests/unit/test_site_cria_com_codigo.py` | Público: sem token 401; token inválido 401; conflito 409 `SAME_MONTH_APPOINTMENT` com `existing`; `substituir: true` passa ao serviço |
| `scheduler/tests/unit/test_painel_manter_as_duas.py` | STAFF com `manterAsDuas` 403; ADMIN sem motivo 400; ADMIN com motivo passa `permitir_duas` |
| `scheduler/tests/mocks/public_booking/create_appointment_substituir.json` | Substitui `create_appointment_confirma_repetido.json` |
| `scheduler/tests/integration/056-uma-sessao-por-mes.md` | Roteiro dev/prod |
| `scheduler/tests/postman/056-uma-sessao-por-mes.postman_requests.json` | verify/send, verify/confirm, create (401, 409, substituir), painel create (409, substituir, manterAsDuas) |

---

## 3. Arquivos a modificar

### 3.1 Backend: regra e troca

| Arquivo | Alterações |
|---|---|
| `scheduler/src/services/appointment_service.py` | **`class SessaoNoMesmoMes(Exception)`** com `.existente` (dict: `id`, `appointment_date`, `start_time`, `areas_display`, `patient_name`). **`sessao_no_mesmo_mes(clinic_id, phone, data, excluir_id=None)`**: a sessão `CONFIRMED` futura (`appointment_date >= HOJE_SQL`) do mesmo paciente (variantes do número, `p.deleted_at IS NULL`, mesma clínica) com `date_trunc('month', appointment_date) = date_trunc('month', %s::date)`, excluindo `excluir_id`, `ORDER BY appointment_date, start_time LIMIT 1` (a mais próxima, decisão 6). **`create_appointment(..., substituir_mesmo_mes=False, permitir_duas=False, autor=None, motivo_das_duas=None)`**: depois do paciente (passo 1) e antes do conflito de horário (passo 4): `existente = None if permitir_duas else self.sessao_no_mesmo_mes(...)`; se existente e não substituir → `raise SessaoNoMesmoMes(existente)`; se existente e substituir → `encerrado = self.cancel_appointment(existente_id, autor=autor)` e guarda. Depois do INSERT e do `vincula_antecessor`: se substituiu, `self._leva_para_o_novo(antigo_id, encerrado, novo_id)` (vínculo nos dois sentidos + pagamentos + `consent_link_sent_at`, extraído de `remarca`) e `result["rescheduled_from_id"] = antigo_id`. Se `permitir_duas` e havia conflito (consultar mesmo assim para saber), grava `second_in_month_by`/`second_in_month_reason` no novo. **`remarca(..., substituir_mesmo_mes=False, permitir_duas=False)`**: antes do passo 1, `terceira = None if permitir_duas else self.sessao_no_mesmo_mes(clinic, phone, nova_data, excluir_id=appointment_id)`; se terceira e não substituir → raise; conflito de horário (passo 1) continua antes de qualquer escrita; se terceira e substituir → `cancel_appointment(terceira, autor)` logo antes do passo 2. O `create_appointment` interno recebe `permitir_duas=True` (o antigo acabou de ser cancelado e a terceira já foi tratada). Passos 4 e 5 viram `_leva_para_o_novo`. |
| `scheduler/src/scripts/setup_database.py` | `MIGRATIONS`: `ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS second_in_month_by VARCHAR(100)` e `... second_in_month_reason VARCHAR(200)`; mesmas colunas no `CREATE TABLE` de appointments |

### 3.2 Backend: site

| Arquivo | Alterações |
|---|---|
| `scheduler/src/functions/public_booking/create_appointment.py` | Importa `verify_token` e `SessaoNoMesmoMes`. Body ganha `token` (obrigatório) e `substituir` (bool). Depois de validar o telefone: `if not verify_token(clinic_id, phone, token): 401 "Verificação por WhatsApp expirada. Confirme o código novamente."` (mesma frase do cancelar). Remove `HAS_FUTURE_APPOINTMENT`, o bloco `confirmDuplicate` e `get_active_appointments_by_phone` daqui. `create_appointment(..., substituir_mesmo_mes=body.get("substituir") is True, autor="site")`. `except SessaoNoMesmoMes as e: 409 {"code": "SAME_MONTH_APPOINTMENT", "existing": {"id", "date", "time", "areas"}, "message": "Você já tem uma sessão nesta clínica neste mês."}` (pode revelar: o número foi verificado). Docstring atualizada. |
| `scheduler/src/functions/public_booking/bootstrap.py` | Nada (já devolve `phone`); conferir no roteiro |

### 3.3 Backend: painel

| Arquivo | Alterações |
|---|---|
| `scheduler/src/functions/appointment/create.py` | Lê `substituir`, `manterAsDuas`, `motivoDasDuas`. `manterAsDuas` com `not identidade.e_admin` → 403 "Só o administrador pode manter duas sessões no mesmo mês"; ADMIN sem motivo → 400. Passa `substituir_mesmo_mes`, `permitir_duas`, `autor=_autor(identidade)` (copiar o helper do update), `motivo_das_duas`. `except SessaoNoMesmoMes` → 409 `{"code": "SAME_MONTH_APPOINTMENT", "existing": {"id", "date", "time", "areas", "patientName"}}` |
| `scheduler/src/functions/appointment/update.py` | Mesmos três campos; `remarca(..., substituir_mesmo_mes=..., permitir_duas=...)`; mesma validação de ADMIN/motivo; mesmo 409. `motivoDasDuas` é gravado no novo pelo create interno: `remarca` repassa `motivo_das_duas`/`autor` ao `create_appointment`. |

### 3.4 Backend: bot

| Arquivo | Alterações |
|---|---|
| `scheduler/src/services/ai_tools.py` | Schema de `book_appointment`: remove `segunda_sessao`. `_recusa_segunda_sessao` → **`_recusa_mesmo_mes(args, phone, ctx)`**: `futuro = self._sessao_futura(ctx)`; se `futuro` e `str(futuro["data"])[:7] == str(args.get("date"))[:7]` → `{"error": "ja_tem_sessao_marcada", "sessao": {...}, "o_que_fazer": "Esta pessoa já tem sessão em {data} às {hora} neste mês e não pode ter duas no mesmo mês. Diga a ela que essa sessão será cancelada e remarcada para a data pedida, confirme, e chame alterar_agendamento com appointment_id={id}, new_date e new_time (e as áreas, se mudaram). Nunca book_appointment."}`; outro mês → `None`. `_agenda`: `try create_appointment ... except SessaoNoMesmoMes as e: return` o mesmo erro montado a partir de `e.existente` (legado: a mais próxima pode estar noutro mês e a do mesmo mês ser outra). Sucesso com `futuro` em outro mês devolve `"sessao_anterior_mantida": {"date", "time"}` para o modelo dizer que a anterior continua. `_tool_alterar_agendamento`: `except SessaoNoMesmoMes as e: {"error": "ja_tem_sessao_nesse_mes", "sessao": {...}, "o_que_fazer": "Ela já tem outra sessão em {data} nesse mês. Ofereça remarcar aquela ou escolher uma data em outro mês."}` |
| `scheduler/src/services/skills/__init__.py` | Skill `paciente_com_horario`, item 3: "Ela não pode ter duas sessões no mesmo mês. Pedido de outra data no mesmo mês é remarcação: avise que a sessão marcada será cancelada e remarcada, confirme e use alterar_agendamento. Em outro mês pode marcar outra; diga que a anterior continua." |
| `scheduler/tests/unit/test_link_primeiro.py` | Remover referência a `segunda_sessao` (ver grep) |

### 3.5 Site

| Arquivo | Alterações |
|---|---|
| `booking-site/src/types/index.ts` | `WizardStep` += `'verify'`. `CreateAppointmentPayload`: remove `confirmDuplicate`; adiciona `token: string` e `substituir?: boolean`. Novo `SessaoExistente { id; date; time; areas: string \| null }`. |
| `booking-site/src/pages/Booking.tsx` | Constantes: remove `HAS_FUTURE_APPOINTMENT`; adiciona `SAME_MONTH_APPOINTMENT`. Estado: `pendingPayload: Omit<CreateAppointmentPayload,'token'> \| null`, `verified: { phone; token } \| null`, `conflito: { payload; existing } \| null`, `remarcado: boolean`. `handleCustomerSubmit`: monta o payload sem token; se `verified?.phone === phone` → `submitAppointment({...payload, token})`; senão `setPendingPayload(payload); setStep('verify')`. Etapa `verify`: `<SectionTitle>Confirme seu celular</SectionTitle>` + `<OtpCodeForm clinicId phone={formatPhoneDisplay(pendingPayload.phone)} onVerified={(token) => { setVerified({phone, token}); setStep('customer'); submitAppointment({...pendingPayload, token}) }} />`. `OtpCodeForm` recebe o telefone já normalizado para a API (`useSendOtp` manda o que recebe; "Meus agendamentos" passa `apiPhone`): passar `pendingPayload.phone` e exibir formatado dentro do form (ver 3.5 OtpCodeForm). `goBack` em `verify` → `customer`. `submitAppointment.onError`: `code === SAME_MONTH_APPOINTMENT` → `setConflito({ payload, existing: err.body.existing })`; 401 → `setVerified(null); setStep('verify')` (token venceu). `RemarcacaoDialog` com `onConfirm={() => { setRemarcado(true); submitAppointment({...conflito.payload, substituir: true}) }}`. Sucesso: título `remarcado ? 'Agendamento remarcado!' : 'Agendamento confirmado!'`. |
| `booking-site/src/components/OtpCodeForm.tsx` | Prop opcional `phoneLabel?: string` para exibir formatado quando `phone` vem normalizado; sem ela, mostra `phone` como hoje |
| `booking-site/src/components/DuplicateBookingDialog.tsx` | Remover |
| `booking-site/src/pages/Booking.test.tsx` | Mocks de `sendOtp`/`confirmOtp`; o `describe` "agendamento futuro no mesmo número" vira "código antes de confirmar" (vai para a etapa do código; confirma; cria com `token`) e "sessão no mesmo mês" (409 → diálogo com a data existente; "Confirmar remarcação" reenvia com `substituir: true`; sucesso "Agendamento remarcado!"; "Voltar" não cria). Teste do 401: volta à etapa do código. |
| `booking-site/CLAUDE.md` | Trocar os parágrafos "Criar agendamento não exige verificação" e "Agendamento repetido pede confirmação" pelo fluxo novo (código sempre; mesmo mês substitui; PRD 056) |
| `docs/work/prd/024-booking-site-meus-agendamentos-aviso-nome.md` | Nota no topo: "Manter os dois" substituído pelo PRD 056 |

### 3.6 Painel

| Arquivo | Alterações |
|---|---|
| `frontend/src/types/index.ts` | `CreateAppointmentPayload` e `UpdateAppointmentPayload` += `substituir?: boolean; manterAsDuas?: boolean; motivoDasDuas?: string`. Novo `SessaoExistente { id; date; time; areas: string \| null; patientName: string \| null }` |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | `ehAdmin` de `useAuth`. Estado `conflito: SessaoExistente \| null`. No `catch` do `handleSubmit`: `response.status === 409 && response.data?.code === 'SAME_MONTH_APPOINTMENT'` → `setConflito(response.data.existing)`. Extrai `montaPayload()` para reenviar com `substituir`/`manterAsDuas`. Renderiza `<ConflitoDoMes>` no lugar do rodapé de botões enquanto `conflito` |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` | Mesmo tratamento no `catch` de `executa`; o aviso diz "{nome} já tem sessão em {data} às {hora}. Ao confirmar, essa sessão será cancelada e esta remarcada para {nova data} às {nova hora}". Confirmar → `executa({ substituir: true })` |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.test.tsx` | Mock de `useAuth` passa a expor `ehAdmin`; teste do 409 → confirmação; reenvio com `substituir: true` |

---

## 4. Arquivos a remover

| Arquivo | Motivo |
|---|---|
| `booking-site/src/components/DuplicateBookingDialog.tsx` | "Manter os dois" sai (decisão 3) |
| `scheduler/tests/unit/test_book_recusa_segunda_sessao.py` | Substituído por `test_bot_mesmo_mes.py` |
| `scheduler/tests/mocks/public_booking/create_appointment_confirma_repetido.json` | Substituído por `create_appointment_substituir.json` |

---

## 5. Contratos

**409 do mesmo mês** (site e painel):

```json
{ "status": "ERROR", "code": "SAME_MONTH_APPOINTMENT",
  "message": "...",
  "existing": { "id": "uuid", "date": "2026-11-25", "time": "14:00",
                "areas": "Axilas, Buço", "patientName": "Ana" } }
```
(`patientName` só no painel.)

**Site, `POST public/clinics/{c}/appointments`**: body += `token` (obrigatório),
`substituir` (opcional). 401 sem token válido. Sem `confirmDuplicate`.

**Painel, `POST /appointments` e `PUT /appointments/{id}`**: body +=
`substituir`, `manterAsDuas`, `motivoDasDuas`. `manterAsDuas` por STAFF → 403;
por ADMIN sem motivo → 400.

**Bot**: `book_appointment` sem `segunda_sessao`; erros `ja_tem_sessao_marcada`
(mesmo mês) e `ja_tem_sessao_nesse_mes` (alterar para mês ocupado); sucesso
com `sessao_anterior_mantida` quando havia sessão em outro mês.

---

## 6. Ordem de implementação

1. `setup_database.py` (colunas) e `appointment_service.py` (exceção, consulta,
   `_leva_para_o_novo`, parâmetros em `create_appointment` e `remarca`) +
   `test_sessao_no_mesmo_mes.py`.
2. `public_booking/create_appointment.py` (token, 409, substituir) +
   `test_site_cria_com_codigo.py`; mock novo; remover mock antigo.
3. `appointment/create.py` e `update.py` + `test_painel_manter_as_duas.py`.
4. `ai_tools.py` e skill + `test_bot_mesmo_mes.py`; apagar o teste antigo;
   ajustar `test_link_primeiro.py`.
5. `pytest` completo.
6. Site: types, `OtpCodeForm`, `RemarcacaoDialog`, `Booking.tsx`, testes,
   remover `DuplicateBookingDialog`; build, lint, vitest.
7. Painel: types, `ConflitoDoMes`, os dois modais, testes; build, lint, vitest.
8. Docs: roteiro 056, Postman, `booking-site/CLAUDE.md`, nota no PRD 024.
9. PR; depois do merge: migração em dev, `serverless deploy --stage dev`,
   smoke pelo roteiro (site de dev com `devCode`), PRD/TASKS_LOG.

---

## 7. Testes manuais (roteiro 056, resumo)

| # | Caso | Esperado |
|---|---|---|
| 1 | Site: criar sem `token` | 401 |
| 2 | Site: `verify/send` em dev devolve `devCode`; `verify/confirm` dá token; criar com token em mês livre | 201 |
| 3 | Site: criar com token em mês com sessão | 409 `SAME_MONTH_APPOINTMENT` com `existing` |
| 4 | Site: mesmo pedido com `substituir: true` | 201; antigo `CANCELLED`/`NO_SHOW` com `rescheduled_to_id`; novo com `rescheduled_from_id` |
| 5 | Site: mês seguinte com sessão neste mês | 201, nada cancelado |
| 6 | Painel STAFF: criar no mesmo mês | 409; `manterAsDuas` → 403 |
| 7 | Painel ADMIN: `manterAsDuas` sem motivo | 400; com motivo → 201 e colunas gravadas |
| 8 | Painel: mover data para mês ocupado | 409; `substituir` cancela a outra e remarca |
| 9 | Bot (unit): mesmo mês recusa sem saída; outro mês cria com aviso | |
| 10 | Browser: site de dev completo com código; painel com conflito | sem erro |
| 11 | Relatório: a troca aparece como remarcação; antigo < 24 h = falta | |
