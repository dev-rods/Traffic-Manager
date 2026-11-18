# Spec - 049 Edição pelo painel tolera até 15 min de sobreposição

> Gerada em 17/11/2026 a partir de `prd/049-edicao-pelo-painel-tolera-15-min-de-sobreposicao.md`.

---

## 1. O que muda, em uma frase

Um helper `_conflitos` com `tolerancia_minutos` substitui as quatro cópias
do SQL de conflito; os três métodos de edição aceitam a tolerância (padrão
0) e só `update.py`, o handler do painel, passa 15.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/services/appointment_service.py` | **novo** `_conflitos(...)`; `tolerancia_minutos: int = 0` em `reschedule_appointment`, `update_appointment_services`, `set_manual_duration`; `create_appointment` chama o helper com 0; mensagens |
| `scheduler/src/functions/appointment/update.py` | `TOLERANCIA_DO_PAINEL_MIN = 15`; passa nas três chamadas |
| `scheduler/tests/unit/test_tolerancia_de_sobreposicao.py` | **novo** |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` (+ test) | texto do aviso |
| `scheduler/tests/integration/049-tolerancia-de-sobreposicao.md` | **novo** - roteiro curl |

---

## 3. `appointment_service.py`

### 3.1 Helper

```python
def _conflitos(self, clinic_id, data, inicio, fim, excluir_id=None, tolerancia_minutos=0):
    """Sessões CONFIRMED do dia que a janela [inicio, fim) invade em mais de
    `tolerancia_minutos`. Com 0, qualquer sobreposição conta; encostar não.
    A sobreposição é medida por vizinha: LEAST(fim) - GREATEST(inicio)."""
    sql = (
        "SELECT id FROM scheduler.appointments "
        "WHERE clinic_id = %s AND appointment_date = %s AND status = 'CONFIRMED' "
    )
    params = [clinic_id, data]
    if excluir_id:
        sql += "AND id != %s::uuid "
        params.append(excluir_id)
    sql += (
        "AND start_time < %s::time AND end_time > %s::time "
        "AND (LEAST(end_time, %s::time) - GREATEST(start_time, %s::time)) > (%s * interval '1 minute')"
    )
    params += [fim, inicio, fim, inicio, int(tolerancia_minutos)]
    return self.db.execute_query(sql, tuple(params))
```

Ordem dos parâmetros preservada para os fakes dos testes atuais
(`clinic, data, [id], fim, inicio, ...`): eles leem `params[3]` como o fim
quando há `id`, e `params[2]`/`params[3]` na criação. Conferir ao rodar a
suíte; ajustar o fake, nunca a ordem.

### 3.2 Métodos

- `create_appointment`: troca o bloco "4. Check for conflicts" por
  `self._conflitos(clinic_id, date, time, end_time)`. Mensagem igual.
- `reschedule_appointment(self, appointment_id, new_date, new_time, tolerancia_minutos=0)`:
  `self._conflitos(clinic_id, new_date, new_time, new_end_time, excluir_id=appointment_id, tolerancia_minutos=...)`.
  Mensagem: com tolerância 0 a de hoje; com tolerância > 0,
  `f"Conflito de horário: a sessão invadiria a vizinha em mais de {t} minutos ({new_date} {new_time}-{new_end_time})"`.
- `update_appointment_services(..., verificar_conflito=True, tolerancia_minutos=0)`: idem,
  preservando "a consulta roda, o raise é condicionado por `verificar_conflito`".
- `set_manual_duration(..., verificar_conflito=True, tolerancia_minutos=0)`: idem.
- Uma função `_mensagem_de_conflito(padrao, tolerancia, data, inicio, fim)` monta o texto.

## 4. `update.py`

```python
TOLERANCIA_DO_PAINEL_MIN = 15  # PRD 049: só a edição manual pelo painel tolera encaixe
```

Nas três chamadas: `tolerancia_minutos=TOLERANCIA_DO_PAINEL_MIN`. Comentário
de duas linhas explicando que bot e site não passam por aqui.

## 5. Testes

`test_tolerancia_de_sobreposicao.py`, com um fake de banco que **calcula**
a sobreposição a partir dos parâmetros (`fim`, `inicio`, `tolerancia`) sobre
uma agenda fixa (vizinha 12:40-13:00; outra 13:30-13:45):

1. tolerância 0: 12:30-12:45 conflita; 12:30-12:40 não (encosta).
2. tolerância 15: 12:30-12:55 passa (15 min); 12:30-12:56 recusa.
3. vizinha curta inteira dentro da invasão: 13:20-13:50 com tolerância 15
   passa (13:30-13:45 = 15 min); 13:20-13:46 passa também (sobreposição 15);
   13:00-14:00 recusa (15 min de 13:30-13:45? não: 15, passa) → usar vizinha
   de 20 min no fake para o caso de recusa.
4. `update.py` passa `tolerancia_minutos=15` nas três chamadas (mock do
   serviço, como em `test_update_passa_a_duracao_adiante.py`).
5. `ai_tools._tool_alterar_agendamento` e `public_booking/reschedule_appointment`
   não passam tolerância (kwargs sem a chave ou igual a 0).
6. SQL do helper contém `LEAST` e `GREATEST` e não contém a terceira
   cláusula redundante.

Frontend: `EditAppointmentModal.test.tsx` ganha uma asserção do texto novo.

## 6. Roteiro em dev (`049-tolerancia-de-sobreposicao.md`)

Clínica `clinicadepilacaopremium-3fbce9` (fixtures do 045). Criar A às 16:30
(10 min) e B às 16:40 (15 min) num dia futuro. `PUT A manualDurationMinutes=20`
→ 200 (invade 10). `PUT A manualDurationMinutes=30` → 409 com "15 minutos".
`PUT A manualDurationMinutes=null` → volta. Criar C às 16:45 pelo painel
(`POST`) → 409 (criação sem tolerância). Apagar as três.

## 7. Ordem

1. Serviço + handler + testes; `pytest`.
2. Painel: texto + teste; `npm run build`, `lint`, `test`.
3. PR, merge.
4. `serverless deploy --stage dev`; roteiro curl em dev.
5. `serverless deploy --stage prod`; smoke (um 409 real com a mensagem nova
   numa sessão de teste, ou só o stack `UPDATE_COMPLETE` se não houver
   sessão de teste disponível).
