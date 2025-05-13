# Traffic Manager - Otimização de Campanhas do Google Ads

Sistema serverless para otimização automatizada de campanhas do Google Ads utilizando a API da OpenAI.

## Visão Geral

Este projeto implementa uma arquitetura serverless na AWS que utiliza inteligência artificial (OpenAI) para otimizar campanhas do Google Ads. O sistema pode tanto criar novas campanhas quanto melhorar campanhas existentes com base em métricas de desempenho.

### Fluxo de Execução

1. **Orquestração**: Determina o tipo de execução (FIRST_RUN ou IMPROVE) e gera um ID de trace.
2. **Coleta de Dados**: Busca um template para novas campanhas ou coleta métricas de campanhas existentes.
3. **Análise com IA**: Utiliza a OpenAI para analisar os dados e gerar recomendações.
4. **Processamento**: Transforma as recomendações da IA em um payload estruturado para o Google Ads.
5. **Execução**: Aplica as alterações na API do Google Ads.
6. **Registro**: Mantém um histórico completo de todas as execuções e alterações.

## Arquitetura

O projeto utiliza os seguintes serviços AWS:

- **AWS Lambda**: Para processamento serverless.
- **Step Functions**: Para orquestração do fluxo de trabalho.
- **DynamoDB**: Para armazenamento de dados e histórico.
- **EventBridge**: Para agendamento das execuções.
- **SNS**: Para notificações de erro (opcional).

### Bancos de Dados (DynamoDB)

- **CampaignTemplates**: Armazena templates para criação de novas campanhas.
- **ExecutionHistory**: Mantém um registro detalhado de cada execução e seus estágios.
- **CampaignMetadata**: Armazena metadados para as campanhas gerenciadas.

## Implantação

### Pré-requisitos

- Node.js 14+ e NPM
- Serverless Framework (`npm install -g serverless`)
- AWS CLI configurado com credenciais
- Conta na OpenAI com API key
- Conta no Google Ads com acesso à API

### Configuração

1. Clone o repositório
2. Instale as dependências:
   ```
   npm install
   pip install -r requirements.txt
   ```

3. Configure os parâmetros no AWS Systems Manager Parameter Store:
   - `/traffic/openai-key`
   - `/traffic/google-ads-client-id`
   - `/traffic/google-ads-client-secret`
   - `/traffic/google-ads-refresh-token`
   - `/traffic/google-ads-developer-token`

4. Implante a aplicação:
   ```
   serverless deploy --stage dev
   ```

## Uso

### Execução Manual

Para acionar manualmente o processo de otimização:

```bash
aws lambda invoke --function-name traffic-manager-infra-dev-triggerCampaignOptimization --payload '{}' response.json
```

Para otimizar uma campanha específica:

```bash
aws lambda invoke --function-name traffic-manager-infra-dev-triggerCampaignOptimization --payload '{"campaignId": "1234567890", "storeId": "store123"}' response.json
```

### Monitoramento

Os logs são registrados no CloudWatch Logs e cada execução mantém um registro detalhado no DynamoDB (tabela ExecutionHistory).

Para consultar o histórico de uma execução específica:

```bash
aws dynamodb query --table-name traffic-manager-infra-dev-execution-history --key-condition-expression "traceId = :tid" --expression-attribute-values '{":tid":{"S":"TRACE_ID_AQUI"}}'
```

## Desenvolvimento

### Estrutura do Projeto

```
├── serverless.yml       # Configuração principal do Serverless Framework
├── src/                 # Código-fonte
│   ├── functions/       # Funções Lambda organizadas por contexto
│   ├── models/          # Modelos de domínio
│   ├── utils/           # Utilitários
│   └── services/        # Serviços compartilhados
├── sls/                 # Configurações do Serverless Framework
│   ├── functions/       # Definições de funções
│   └── resources/       # Recursos AWS (DynamoDB, Step Functions, etc.)
└── tests/               # Testes automatizados
```

### Ambiente Local

Para desenvolvimento local, é recomendado utilizar o SAM CLI ou o plugin serverless-offline.

## Licença

Este projeto é proprietário. Todos os direitos reservados.

## Integrações

### Google Sheets

O sistema agora suporta integração com o Google Sheets, permitindo que formulários do Google Forms iniciem automaticamente fluxos de otimização de campanhas. 

Recursos da integração:
- Autenticação via API Key
- Multitenancy (suporte a múltiplos clientes)
- Processamento automático de novos registros de formulários
- Documentação detalhada para configuração

Para configurar a integração, consulte o [guia detalhado](docs/GOOGLE_SHEETS_INTEGRATION.md).

### Gerenciamento de Clientes

Para gerenciar clientes (criar novos, listar existentes, regenerar API keys), utilize o script CLI:

```bash
# Listar todos os clientes
python src/scripts/client_manager.py list

# Criar um novo cliente
python src/scripts/client_manager.py create --name "Nome do Cliente" --email "email@cliente.com"

# Regenerar API key
python src/scripts/client_manager.py regenerate-key --id "client-id"

# Desativar um cliente
python src/scripts/client_manager.py deactivate --id "client-id"

# Ativar um cliente
python src/scripts/client_manager.py activate --id "client-id"
```

## Modelo de Dados

O sistema agora inclui as seguintes tabelas adicionais:
- `clients`: Armazena informações de clientes e suas API keys
- `execution-history`: Inclui campo storeId para rastrear execuções por cliente
