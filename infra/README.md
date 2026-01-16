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

- **AWS Lambda**: Para processamento serverless (usando Docker images via ECR).
- **ECR (Elastic Container Registry)**: Para armazenar imagens Docker das funções Lambda.
- **Step Functions**: Para orquestração do fluxo de trabalho.
- **DynamoDB**: Para armazenamento de dados e histórico.
- **EventBridge**: Para agendamento das execuções.
- **SNS**: Para notificações de erro (opcional).
- **Systems Manager (SSM)**: Para armazenamento seguro de chaves de criptografia.

### Docker Images para Lambda

As funções Lambda utilizam Docker images hospedadas no ECR devido ao tamanho das dependências Python (excedendo o limite de 250MB para layers). Isso permite:

- **Maior flexibilidade**: Sem limitações de tamanho de pacote
- **Controle total**: Gerenciamento completo do ambiente de execução
- **Performance**: Imagens otimizadas para Lambda

### Bancos de Dados (DynamoDB)

- **CampaignTemplates**: Armazena templates para criação de novas campanhas.
- **ExecutionHistory**: Mantém um registro detalhado de cada execução e seus estágios.
- **CampaignMetadata**: Armazena metadados para as campanhas gerenciadas.
- **Clients**: Armazena informações dos clientes e suas configurações do Google Ads (criptografadas).

## Gestão de Clientes e Tokens do Google Ads

Cada cliente do sistema possui seus próprios tokens do Google Ads, permitindo operações multi-tenant seguras.

### Sistema de Associação MCC (My Client Center)

O sistema agora inclui funcionalidade completa para associar automaticamente contas de clientes à sua conta MCC:

- **Envio automático de convites**: Convites são enviados automaticamente ao criar novos clientes
- **Monitoramento de status**: Acompanhamento em tempo real do status das associações
- **Gerenciamento centralizado**: Interface unificada para gerenciar todas as associações MCC
- **Integração transparente**: Funciona automaticamente no fluxo existente de criação de clientes

Para mais detalhes, consulte a [documentação completa do sistema MCC](docs/MCC_SYSTEM_GUIDE.md).

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

### Scripts de Gerenciamento MCC

O sistema inclui scripts especializados para gerenciar associações MCC:

```bash
# Gerenciar associações MCC (modo interativo)
python src/scripts/manage_mcc_links.py

# Monitorar status das associações
python src/scripts/monitor_mcc_status.py

# Executar testes do sistema MCC
python src/scripts/test_mcc_system.py

# Exemplos práticos de uso
python src/scripts/exemplo_uso_mcc.py

# Enviar convite MCC via linha de comando
python src/scripts/manage_mcc_links.py --operation send_invitation --client-customer-id 1234567890 --client-name "Empresa ABC"
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
3. Docker (para build de imagens)
4. Serverless Framework
5. Credenciais AWS configuradas (via `--aws-profile` ou variáveis de ambiente)

**Nota**: Você não precisa do AWS CLI instalado! O Serverless Framework usa as credenciais AWS diretamente.

### Dependências

```bash
# Instalar dependências Node.js
npm install

# Instalar dependências Python
pip install -r requirements.txt
```

### Deploy

O Serverless Framework faz build e push da imagem Docker automaticamente durante o deploy. Você **não precisa** executar scripts separados!

#### Deploy Automático (Recomendado)

```bash
# Deploy para desenvolvimento
serverless deploy --stage dev --aws-profile traffic-manager

# Deploy para produção
serverless deploy --stage prod --aws-profile traffic-manager
```

O Serverless Framework irá automaticamente:
1. ✅ Criar o repositório ECR (se não existir)
2. ✅ Fazer build da imagem Docker
3. ✅ Fazer push para o ECR
4. ✅ Deploy das funções Lambda

**Pronto!** Tudo em um comando. Você só precisa ter Docker instalado e credenciais AWS configuradas.

#### Testar uma Função

```bash
serverless invoke -f CampaignOrchestrator --stage dev --aws-profile traffic-manager

# Ver logs
serverless logs -f CampaignOrchestrator --stage dev --aws-profile traffic-manager
```

#### Atualizando a Imagem

Quando você atualizar código ou dependências, apenas execute:

```bash
serverless deploy --stage dev --aws-profile traffic-manager
```

O Serverless Framework detectará mudanças e fará build/push automaticamente.

### Estrutura Docker

- **Dockerfile**: Baseado na imagem oficial AWS Lambda Python 3.8
- **.dockerignore**: Otimiza o build excluindo arquivos desnecessários
- **Imagem**: Contém todas as dependências Python do `requirements.txt` e o código fonte
- **Build Automático**: Configurado via `provider.ecr.images` no `serverless.yml`

### Abordagem Manual (Opcional)

Se preferir fazer build e push manualmente (requer AWS CLI):

**Windows (PowerShell):**
```powershell
.\scripts\build-and-push-image.ps1 -stage dev -region us-east-1
```

**Linux/Mac (Bash):**
```bash
chmod +x scripts/build-and-push-image.sh
./scripts/build-and-push-image.sh dev us-east-1
```

Veja [docs/ECR_OPTIONS.md](docs/ECR_OPTIONS.md) para comparação das abordagens.

### Atualizando a Imagem

Sempre que você atualizar o código ou dependências:

1. Atualize o `requirements.txt` se necessário
2. Execute o build e push novamente: `.\scripts\build-and-push-image.ps1 -stage dev`
3. Faça o deploy: `serverless deploy --stage dev`