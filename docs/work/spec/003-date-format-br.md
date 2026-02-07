# Spec — 003 Formatacao de datas no padrao brasileiro (DD/MM/YYYY)

> Gerado na fase **Spec**. Use como input para a fase Code (implementacao).

- **PRD de origem:** `prd/003-date-format-br.md`

---

## 1. Resumo

Adicionar uma funcao helper `_format_date_br` em `conversation_engine.py` que converte datas de YYYY-MM-DD (string ou `date` object) para DD/MM/YYYY. Usar essa funcao em todos os pontos onde datas sao exibidas ao usuario (labels de botoes e variaveis de template), mantendo os dados internos (btn_id, session, API calls) em YYYY-MM-DD.

---

## 2. Arquivos a criar

Nenhum.

---

## 3. Arquivos a modificar

| Arquivo | Alteracoes |
|---------|------------|
| `scheduler/src/services/conversation_engine.py` | Adicionar import `from datetime import date, datetime`; adicionar metodo helper `_format_date_br`; usar helper em 8 pontos de exibicao de datas |

---

## 4. Arquivos a remover (se aplicavel)

Nenhum.

---

## 5. Ordem de implementacao sugerida

1. Adicionar `from datetime import date, datetime` nos imports
2. Adicionar metodo statico `_format_date_br(date_value)` na classe `ConversationEngine`
3. Aplicar `_format_date_br` nos 8 pontos de exibicao (detalhados abaixo)

---

## 6. Detalhes por arquivo

### `scheduler/src/services/conversation_engine.py`

#### 6.1 Import (linha 1-7)

- Adicionar: `from datetime import date, datetime`

#### 6.2 Helper `_format_date_br` (novo metodo statico na classe ConversationEngine)

```python
@staticmethod
def _format_date_br(date_value) -> str:
    if isinstance(date_value, date):
        return date_value.strftime("%d/%m/%Y")
    if isinstance(date_value, str) and date_value:
        try:
            return datetime.strptime(date_value, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return date_value
    return str(date_value)
```

- Aceita `date`, `datetime`, ou string YYYY-MM-DD
- Retorna string DD/MM/YYYY
- Em caso de formato inesperado, retorna o valor original (sem quebrar)

#### 6.3 `_on_enter_available_days` (~linha 497-510)

- **Linha 500 (label do botao):** trocar `"label": day` por `"label": self._format_date_br(day)`
- **Linha 508 (days_list):** trocar `{d}` por `{self._format_date_br(d)}`

#### 6.4 `_on_enter_select_time` (~linha 534)

- Trocar `"date": selected_date` por `"date": self._format_date_br(selected_date)`

#### 6.5 `_on_enter_confirm_booking` (~linha 542)

- Trocar `"date": session.get("selected_date", "")` por `"date": self._format_date_br(session.get("selected_date", ""))`

#### 6.6 `_on_enter_booked` (~linha 570)

- Trocar `"date": session.get("selected_date", "")` por `"date": self._format_date_br(session.get("selected_date", ""))`

#### 6.7 `_on_enter_reschedule_lookup` (~linha 588 e 605)

- **Linha 588 (variavel {{date}}):** trocar `"date": str(appointment.get("appointment_date", ""))` por `"date": self._format_date_br(appointment.get("appointment_date", ""))`
- **Linha 605 (label do botao):** trocar `"label": day` por `"label": self._format_date_br(day)`

#### 6.8 `_on_enter_select_new_time` (~linha 646)

- Trocar `"date": selected_date` por `"date": self._format_date_br(selected_date)`

#### 6.9 `_on_enter_confirm_reschedule` (~linha 652)

- Trocar `"date": session.get("selected_new_date", "")` por `"date": self._format_date_br(session.get("selected_new_date", ""))`

#### 6.10 `_on_enter_rescheduled` (~linha 673)

- Trocar `"date": session.get("selected_new_date", "")` por `"date": self._format_date_br(session.get("selected_new_date", ""))`

---

## 7. Convencoes a respeitar

- Logging: `[traceId: {trace_id}]` (ver `CLAUDE.md`)
- Naming: metodos privados com prefixo `_`; helper statico pois nao depende de estado da instancia
- Dados internos (btn_id como `day_2025-02-10`, session keys, chamadas a `appointment_service` e `availability_engine`) NAO devem ser alterados
