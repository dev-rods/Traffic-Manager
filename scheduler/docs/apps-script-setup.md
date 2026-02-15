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
// TRIGGER - Detecta edições na coluna "Status" (coluna G)
// ============================================================
function onEditTrigger(e) {
  try {
    var sheet = e.source.getActiveSheet();
    var range = e.range;

    // Coluna G = 7 (Status)
    if (range.getColumn() !== 7) return;

    // Ignorar header (row 1)
    if (range.getRow() <= 1) return;

    var newValue = (range.getValue() || "").toString().toUpperCase().trim();

    // Só dispara para status de bloqueio
    var blockStatuses = ["BLOQUEADO", "OCUPADO", "BLOCKED"];
    if (blockStatuses.indexOf(newValue) === -1) return;

    var row = range.getRow();

    // Ler dados da linha: Data (A), Horário (B), Observações (H)
    var dateValue = sheet.getRange(row, 1).getValue();
    var timeValue = sheet.getRange(row, 2).getValue();
    var notes = sheet.getRange(row, 8).getValue() || "Bloqueado via planilha";

    if (!dateValue || !timeValue) {
      Logger.log("Data ou horário vazio na linha " + row);
      return;
    }

    // Formatar data como YYYY-MM-DD
    var formattedDate;
    if (dateValue instanceof Date) {
      formattedDate = Utilities.formatDate(dateValue, Session.getScriptTimeZone(), "yyyy-MM-dd");
    } else {
      formattedDate = dateValue.toString();
    }

    // Formatar horário como HH:mm
    var formattedTime;
    if (timeValue instanceof Date) {
      formattedTime = Utilities.formatDate(timeValue, Session.getScriptTimeZone(), "HH:mm");
    } else {
      formattedTime = timeValue.toString();
    }

    var spreadsheetId = e.source.getId();

    var payload = {
      spreadsheet_id: spreadsheetId,
      action: "BLOCK",
      date: formattedDate,
      time: formattedTime,
      notes: notes.toString(),
      token: WEBHOOK_TOKEN
    };

    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(WEBHOOK_URL, options);
    var responseCode = response.getResponseCode();

    if (responseCode === 201) {
      Logger.log("Bloqueio criado com sucesso: " + formattedDate + " " + formattedTime);
    } else {
      Logger.log("Erro ao criar bloqueio: HTTP " + responseCode + " - " + response.getContentText());
    }

  } catch (error) {
    Logger.log("Erro no trigger onEdit: " + error.toString());
  }
}
```

## Como funciona

1. Quando alguém edita a coluna **Status** (G) de uma linha e coloca "Bloqueado", "Ocupado" ou "Blocked"
2. O Apps Script lê a **Data** (coluna A) e o **Horário** (coluna B) da mesma linha
3. Envia um POST para o webhook do sistema com esses dados
4. O sistema cria uma `availability_exception` do tipo `BLOCKED` para aquele horário
5. O horário não aparecerá mais como disponível no WhatsApp

## Observações

- O token é um shared secret entre o Apps Script e a API. Configure o mesmo valor no SSM (`/${stage}/SHEETS_WEBHOOK_TOKEN`)
- O trigger `onEdit` só funciona para edições manuais (não para edições via API)
- Erros são logados no Apps Script (menu: Execuções)
