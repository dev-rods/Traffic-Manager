# Traffic Manager - Otimização de Campanhas do Google Ads

Sistema serverless para otimização automatizada de campanhas do Google Ads utilizando a API da OpenAI.

## Visão Geral

Este projeto implementa uma arquitetura serverless na AWS que utiliza inteligência artificial (OpenAI) para otimizar campanhas do Google Ads. O sistema pode tanto criar novas campanhas quanto melhorar campanhas existentes com base em métricas de desempenho.

### Fluxo de Execução

1. **Orquestração**: Determina o tipo de execução (FIRST_RUN ou IMPROVE) e gera um ID de trace.
2. **Coleta de Dados**: Busca um template para novas campanhas ou coleta métricas de campanhas existentes.
3. **Análise com IA**: Utiliza a OpenAI para analisar os dados e gerar recomendações.
4. **Processamento**: Transforma as recomendações da IA em um payload estruturado para o Google Ads.
5. **Execução**: Aplica as alterações na API do Google Ads utilizando os tokens específicos do cliente.
6. **Registro**: Mantém um histórico completo de todas as execuções e alterações.

## Arquitetura

O projeto utiliza os seguintes serviços AWS:

- **AWS Lambda**: Para processamento serverless.
- **Step Functions**: Para orquestração do fluxo de trabalho.
- **DynamoDB**: Para armazenamento de dados e histórico.
- **EventBridge**: Para agendamento das execuções.
- **SNS**: Para notificações de erro (opcional).
- **Systems Manager (SSM)**: Para armazenamento seguro de chaves de criptografia.

### Bancos de Dados (DynamoDB)

- **CampaignTemplates**: Armazena templates para criação de novas campanhas.
- **ExecutionHistory**: Mantém um registro detalhado de cada execução e seus estágios.
- **CampaignMetadata**: Armazena metadados para as campanhas gerenciadas.
- **Clients**: Armazena informações dos clientes e suas configurações do Google Ads (criptografadas).

## Gestão de Clientes e Tokens do Google Ads

Cada cliente do sistema possui seus próprios tokens do Google Ads, permitindo operações multi-tenant seguras.

### Estrutura do Cliente

```json
{
  "clientId": "empresarods-abc123",
  "name": "Empresa Rods",
  "email": "rodsebaiano@gmail.com",
  "apiKey": "generated-api-key",
  "active": true,
  "createdAt": "2024-01-01T00:00:00Z",
  "googleAdsConfig": {
    "developerId": "1234567890",
    "clientId": "encrypted-client-id",
    "clientSecret": "encrypted-client-secret",
    "refreshToken": "encrypted-refresh-token",
    "developerToken": "encrypted-developer-token"
  },
  "googleAdsInfo": {
    "customerId": "1234567890",
    "currencyCode": "BRL",
    "timeZone": "America/Sao_Paulo",
    "descriptiveName": "Minha Empresa",
    "validatedAt": "2024-01-01T00:00:00Z"
  }
}
```

### Gerenciamento de Clientes

Para gerenciar clientes (criar novos, listar existentes, regenerar API keys), utilize o script CLI:

```bash
# Listar todos os clientes
serverless invoke local -s dev -f ScriptManager -p tests/mocks/scripts/manager/list_clients.json --aws-profile traffic-manager

# Criar um novo cliente sem Google Ads
serverless invoke local -s dev -f ScriptManager -p tests/mocks/scripts/manager/create_client.json --aws-profile traffic-manager

# Criar um novo cliente com configuração do Google Ads
serverless invoke local -s dev -f ScriptManager -p tests/mocks/scripts/manager/create_client_with_google_ads.json --aws-profile traffic-manager

# Regenerar API key
serverless invoke local -s dev -f ScriptManager -p tests/mocks/scripts/manager/regenerate_key.json --aws-profile traffic-manager
```

### Configuração do Google Ads por Cliente

Quando um cliente é criado com configuração do Google Ads, os seguintes tokens são necessários:

- **Developer ID (Customer ID)**: ID da conta do Google Ads (formato: 1234567890)
- **Client ID**: Client ID do OAuth2 (termina com .apps.googleusercontent.com)
- **Client Secret**: Client Secret do OAuth2
- **Refresh Token**: Token de refresh do OAuth2
- **Developer Token**: Token de desenvolvedor do Google Ads API

### Segurança

- **Criptografia**: Todos os tokens sensíveis são criptografados usando Fernet (symmetric encryption)
- **Chaves de Criptografia**: Armazenadas de forma segura no AWS Systems Manager (SSM)
- **Isolamento**: Cada cliente acessa apenas suas próprias campanhas
- **Validação**: Tokens são validados antes do armazenamento

## Instalação e Configuração

### Pré-requisitos

1. Node.js e npm
2. Python 3.8+
3. AWS CLI configurado
4. Serverless Framework

### Dependências

```bash
# Instalar dependências Node.js
npm install

# Instalar dependências Python
pip install -r requirements.txt
```

### Deploy

```bash
# Deploy para desenvolvimento
serverless deploy --stage dev

# Deploy para produção
serverless deploy --stage prod
```