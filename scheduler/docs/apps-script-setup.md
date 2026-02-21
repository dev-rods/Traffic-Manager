# Google Apps Script - Sync Bidirecional (Planilha → Sistema)

## Como configurar

1. Abra a planilha "Agenda - {Nome da Clínica}" no Google Sheets
2. Menu: **Extensões > Apps Script**
3. Apague o conteúdo padrão e cole o código abaixo
4. Substitua as variáveis `WEBHOOK_URL` e `WEBHOOK_TOKEN` pelos valores corretos
5. Salve o projeto (Ctrl+S)
6. No editor do Apps Script, vá em **Acionadores (Triggers)** no menu lateral esquerdo (ícone de relógio)
7. Clique em **+ Adicionar acionador**:
   - Função: `onEditTrigger`
   - Evento: `Ao editar`
   - Planilha: selecione a planilha atual
8. Autorize as permissões quando solicitado

## Código do Apps Script

```javascript
// ============================================================
// CONFIGURAÇÃO - Altere estes valores
// ============================================================
var WEBHOOK_URL = "https://SEU-API-GATEWAY.execute-api.us-east-1.amazonaws.com/prod/sheets/webhook";
var WEBHOOK_TOKEN = "SEU_TOKEN_AQUI"; // Mesmo valor do SSM /${stage}/SHEETS_WEBHOOK_TOKEN

// ============================================================
// Colunas da planilha (1-indexed)
// A=1 Data, B=2 Horário, C=3 Paciente, D=4 Telefone, E=5 Serviço
// F=6 Áreas, G=7 Status, H=8 Observações, I=9 AppointmentId, J=10 UltimaAtualização
// ============================================================
var COL_DATA = 1;
var COL_HORARIO = 2;
var COL_PACIENTE = 3;
var COL_TELEFONE = 4;
var COL_SERVICO = 5;
var COL_AREAS = 6;
var COL_STATUS = 7;
var COL_OBSERVACOES = 8;
var COL_APPOINTMENT_ID = 9;
var COL_ULTIMA_ATUALIZACAO = 10;

// Colunas que devem ser ignoradas (escritas pelo sistema)
var IGNORED_COLUMNS = [COL_APPOINTMENT_ID, COL_ULTIMA_ATUALIZACAO];

// ============================================================
// TRIGGER - Detecta edições e dispara ações
// ============================================================
function onEditTrigger(e) {
  try {
    var sheet = e.source.getActiveSheet();
    var range = e.range;
    var col = range.getColumn();
    var row = range.getRow();

    // Ignorar header (row 1)
    if (row <= 1) return;

    // Ignorar edições nas colunas de sistema (I, J)
    if (IGNORED_COLUMNS.indexOf(col) !== -1) return;

    // Só processar edições nas colunas relevantes
    var actionColumns = [COL_DATA, COL_HORARIO, COL_AREAS, COL_STATUS];
    if (actionColumns.indexOf(col) === -1) return;

    var spreadsheetId = e.source.getId();
    var sheetName = sheet.getName();

    // Ler a row inteira
    var rowData = sheet.getRange(row, 1, 1, 10).getValues()[0];

    var dateValue = rowData[COL_DATA - 1];
    var timeValue = rowData[COL_HORARIO - 1];
    var patientName = rowData[COL_PACIENTE - 1] || "";
    var phone = rowData[COL_TELEFONE - 1] || "";
    var serviceName = rowData[COL_SERVICO - 1] || "";
    var areas = rowData[COL_AREAS - 1] || "";
    var status = (rowData[COL_STATUS - 1] || "").toString().toUpperCase().trim();
    var notes = rowData[COL_OBSERVACOES - 1] || "";
    var appointmentId = (rowData[COL_APPOINTMENT_ID - 1] || "").toString().trim();

    // Formatar data
    var formattedDate = formatDate(dateValue);
    var formattedTime = formatTime(timeValue);

    if (!formattedDate || !formattedTime) {
      Logger.log("Data ou horário vazio/invalido na linha " + row);
      return;
    }

    var payload = null;

    // Dispatch por coluna editada
    if (col === COL_STATUS) {
      payload = dispatchByStatus(status, appointmentId, formattedDate, formattedTime, phone, serviceName, areas, notes);
    } else if (col === COL_DATA || col === COL_HORARIO) {
      // Mudança de data ou horário = RESCHEDULE
      if (!appointmentId) {
        Logger.log("RESCHEDULE ignorado: sem AppointmentId na linha " + row);
        return;
      }
      payload = {
        action: "RESCHEDULE",
        appointment_id: appointmentId,
        date: formattedDate,
        time: formattedTime
      };
    } else if (col === COL_AREAS) {
      // Mudança de áreas = UPDATE_AREAS
      if (!appointmentId) {
        Logger.log("UPDATE_AREAS ignorado: sem AppointmentId na linha " + row);
        return;
      }
      if (!areas) {
        Logger.log("UPDATE_AREAS ignorado: areas vazio na linha " + row);
        return;
      }
      payload = {
        action: "UPDATE_AREAS",
        appointment_id: appointmentId,
        areas: areas.toString()
      };
    }

    if (!payload) return;

    // Adicionar campos comuns
    payload.spreadsheet_id = spreadsheetId;
    payload.sheet_name = sheetName;
    payload.row_number = row;
    payload.token = WEBHOOK_TOKEN;

    sendWebhook(payload, row);

  } catch (error) {
    Logger.log("Erro no trigger onEdit: " + error.toString());
  }
}

// ============================================================
// Dispatch por status
// ============================================================
function dispatchByStatus(status, appointmentId, date, time, phone, serviceName, areas, notes) {
  var blockStatuses = ["BLOQUEADO", "OCUPADO", "BLOCKED"];
  var cancelStatuses = ["CANCELADO", "CANCELLED"];
  var confirmStatuses = ["CONFIRMADO", "CONFIRMED"];

  if (blockStatuses.indexOf(status) !== -1) {
    return {
      action: "BLOCK",
      date: date,
      time: time,
      notes: notes || "Bloqueado via planilha"
    };
  }

  if (cancelStatuses.indexOf(status) !== -1) {
    if (!appointmentId) {
      Logger.log("CANCEL ignorado: sem AppointmentId");
      return null;
    }
    return {
      action: "CANCEL",
      appointment_id: appointmentId
    };
  }

  if (confirmStatuses.indexOf(status) !== -1 && !appointmentId) {
    // Nova row com status CONFIRMADO e sem AppointmentId = CREATE
    if (!phone || !serviceName) {
      Logger.log("CREATE ignorado: Telefone e Serviço são obrigatórios");
      return null;
    }
    return {
      action: "CREATE",
      date: date,
      time: time,
      phone: phone.toString(),
      service_name: serviceName.toString(),
      areas: areas ? areas.toString() : "",
      notes: notes ? notes.toString() : ""
    };
  }

  return null;
}

// ============================================================
// Helpers
// ============================================================
function formatDate(dateValue) {
  if (!dateValue) return null;
  if (dateValue instanceof Date) {
    return Utilities.formatDate(dateValue, Session.getScriptTimeZone(), "yyyy-MM-dd");
  }
  return dateValue.toString();
}

function formatTime(timeValue) {
  if (!timeValue) return null;
  if (timeValue instanceof Date) {
    return Utilities.formatDate(timeValue, Session.getScriptTimeZone(), "HH:mm");
  }
  return timeValue.toString();
}

function sendWebhook(payload, row) {
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch(WEBHOOK_URL, options);
  var responseCode = response.getResponseCode();
  var responseBody = response.getContentText();

  if (responseCode >= 200 && responseCode < 300) {
    Logger.log("Sucesso [" + payload.action + "] linha " + row + ": HTTP " + responseCode);

    // Se foi CREATE, tentar ler o appointmentId da resposta e escrever na planilha
    if (payload.action === "CREATE") {
      try {
        var data = JSON.parse(responseBody);
        if (data.appointmentId) {
          var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
          sheet.getRange(row, COL_APPOINTMENT_ID).setValue(data.appointmentId);
          sheet.getRange(row, COL_ULTIMA_ATUALIZACAO).setValue(new Date());
        }
      } catch (e) {
        Logger.log("Erro ao parsear resposta CREATE: " + e.toString());
      }
    }
  } else {
    Logger.log("Erro [" + payload.action + "] linha " + row + ": HTTP " + responseCode + " - " + responseBody);
  }
}
```

## Como funciona

### Ações suportadas

| Edição na planilha | Ação enviada | O que acontece no sistema |
|---|---|---|
| Status → BLOQUEADO/OCUPADO/BLOCKED | `BLOCK` | Cria `availability_exception` (horário bloqueado no WhatsApp) |
| Status → CANCELADO/CANCELLED | `CANCEL` | Cancela o agendamento (requer AppointmentId) |
| Status → CONFIRMADO/CONFIRMED sem AppointmentId | `CREATE` | Cria novo agendamento (requer Telefone, Serviço) |
| Mudança em Data (A) ou Horário (B) | `RESCHEDULE` | Remarca o agendamento (requer AppointmentId) |
| Mudança em Áreas (F) | `UPDATE_AREAS` | Atualiza áreas e recalcula duração (requer AppointmentId) |

### Colunas da planilha

| Coluna | Campo | Editável | Descrição |
|---|---|---|---|
| A | Data | Sim | Data do agendamento (formato: DD/MM/AAAA ou AAAA-MM-DD) |
| B | Horário | Sim | Horário de início (formato: HH:MM) |
| C | Paciente | - | Nome do paciente |
| D | Telefone | Sim | Telefone com DDD (ex: 5511999999999) |
| E | Serviço | Sim | Nome do serviço (deve corresponder ao cadastrado) |
| F | Áreas | Sim | Áreas separadas por vírgula (ex: "Rosto, Tórax") |
| G | Status | Sim | CONFIRMADO, CANCELADO, BLOQUEADO |
| H | Observações | - | Notas adicionais |
| I | AppointmentId | Sistema | Preenchido automaticamente pelo sistema |
| J | UltimaAtualização | Sistema | Timestamp da última sync |

### Prevenção de loop

- Edições nas colunas I e J (escritas pelo sistema) são ignoradas pelo trigger
- O webhook instancia `AppointmentService(sheets_sync=None)`, impedindo que a ação do banco dispare outra escrita na planilha

## Observações

- O token é um shared secret entre o Apps Script e a API. Configure o mesmo valor no SSM (`/${stage}/SHEETS_WEBHOOK_TOKEN`)
- O trigger `onEdit` só funciona para edições manuais (não para edições via API)
- Erros são logados no Apps Script (menu: Execuções)
- Para criar agendamentos pela planilha, preencha Data, Horário, Telefone, Serviço e Áreas, depois mude o Status para CONFIRMADO
