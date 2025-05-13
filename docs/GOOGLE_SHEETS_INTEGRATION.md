# Integração com Google Sheets

Este documento descreve como configurar a integração entre seu formulário do Google Sheets e a plataforma de otimização de campanhas.

## Visão Geral

O sistema permite que você conecte um formulário do Google Forms com o Google Sheets e, automaticamente, inicie um fluxo de otimização de campanha toda vez que um novo registro for adicionado à planilha.

## Pré-requisitos

1. Uma conta de cliente ativa na plataforma (solicite ao administrador)
2. API Key para autenticação (fornecida durante a criação da conta)
3. Um formulário do Google Forms conectado a uma planilha do Google Sheets
4. Google Sheets com permissões para usar Google Apps Script

## Configuração do Google Sheets

### Passo 1: Crie o Formulário e a Planilha

1. Crie um formulário no Google Forms com os campos necessários para sua campanha:
   - Nome da empresa
   - Indústria/Setor
   - Orçamento mensal
   - Objetivos da campanha
   - Público-alvo
   - Outros campos relevantes para seu negócio

2. Configure o formulário para enviar respostas para uma planilha do Google Sheets

### Passo 2: Configurar um Trigger do Google Apps Script

1. No Google Sheets que recebe as respostas, clique em **Extensões > Apps Script**
2. Crie um novo script com o seguinte código (substitua `SUA_API_KEY` pela chave fornecida):

```javascript
// Configurações
const API_ENDPOINT = 'https://[seu-endpoint-da-api].execute-api.us-east-1.amazonaws.com/dev/webhook/campaign';
const API_KEY = 'SUA_API_KEY'; // Substituir pela API key fornecida

/**
 * Função que é acionada quando uma nova linha é adicionada à planilha
 */
function onFormSubmit(e) {
  // Obter os dados do formulário
  const formData = processFormResponse(e);
  
  // Enviar dados para a API
  sendToAPI(formData);
}

/**
 * Função para processar os dados do formulário
 */
function processFormResponse(e) {
  // Se o trigger for configurado pelo script, usamos evento
  if (e && e.namedValues) {
    const formData = {};
    
    // Processar cada campo do formulário
    for (const key in e.namedValues) {
      // Remover espaços extras e pegar o primeiro valor (geralmente só tem um)
      formData[normalizeKey(key)] = e.namedValues[key][0].trim();
    }
    
    return formData;
  } 
  // Caso contrário, pegar da linha ativa (útil para testes manuais)
  else {
    const sheet = SpreadsheetApp.getActiveSheet();
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    const lastRow = sheet.getLastRow();
    const values = sheet.getRange(lastRow, 1, 1, headers.length).getValues()[0];
    
    const formData = {};
    for (let i = 0; i < headers.length; i++) {
      formData[normalizeKey(headers[i])] = values[i];
    }
    
    return formData;
  }
}

/**
 * Normaliza uma chave para uso na API
 */
function normalizeKey(key) {
  // Remover caracteres especiais, espaços e converter para camelCase
  return key
    .toLowerCase()
    .replace(/[^\w ]/g, '')
    .replace(/ +(.)/g, function(match, group) {
      return group.toUpperCase();
    });
}

/**
 * Envia os dados para a API
 */
function sendToAPI(formData) {
  // Adicione a timestamp
  formData.timestamp = new Date().toISOString();
  
  // Preparar o payload
  const payload = {
    apiKey: API_KEY,
    formData: formData
  };
  
  // Configurar a requisição HTTP
  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    // Enviar a requisição
    Logger.log('Enviando dados para a API: ' + JSON.stringify(payload));
    const response = UrlFetchApp.fetch(API_ENDPOINT, options);
    
    // Processar a resposta
    const responseCode = response.getResponseCode();
    const responseBody = response.getContentText();
    
    Logger.log('Resposta da API: ' + responseCode + ' - ' + responseBody);
    
    if (responseCode >= 200 && responseCode < 300) {
      Logger.log('Sucesso: ' + responseBody);
      return true;
    } else {
      Logger.log('Erro: ' + responseBody);
      return false;
    }
  } catch (error) {
    Logger.log('Exceção: ' + error.toString());
    return false;
  }
}

/**
 * Função para testar o envio com a última linha
 */
function testSendLastRow() {
  const formData = processFormResponse();
  return sendToAPI(formData);
}
```

3. Clique em **Salvar** e dê um nome ao projeto (ex: "Integração com Campanha")

### Passo 3: Configurar o Trigger para Execução Automática

1. No editor do Apps Script, clique em **Triggers** (ícone de relógio) no menu lateral esquerdo
2. Clique em **+ Add Trigger** no canto inferior direito
3. Configure o trigger com as seguintes opções:
   - **Choose which function to run**: `onFormSubmit`
   - **Choose which deployment should run**: `Head`
   - **Select event source**: `From spreadsheet`
   - **Select event type**: `On form submit`
4. Clique em **Save**
5. Authorize o script quando solicitado

### Passo 4: Teste a Integração

1. Submeta um novo formulário de teste
2. Acesse o Google Apps Script e clique em **Execution** no menu lateral
3. Você deve ver uma execução bem-sucedida
4. Verifique no painel da plataforma se a campanha foi iniciada corretamente

## Considerações de Segurança

- Nunca compartilhe sua API Key com terceiros
- Se você suspeitar que sua API Key foi exposta, solicite uma nova imediatamente
- O Google Apps Script está executando em seu contexto de segurança, não em um servidor externo

## Resolução de Problemas

Se você encontrar problemas na integração, verifique:

1. A API Key está correta e válida
2. O formato dos dados está de acordo com o esperado pela API
3. Os logs do Google Apps Script para identificar erros específicos
4. O status da plataforma para verificar se há algum problema no servidor

## Suporte

Caso encontre dificuldades na configuração ou tenha dúvidas, entre em contato com o suporte técnico. 