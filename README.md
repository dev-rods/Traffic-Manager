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