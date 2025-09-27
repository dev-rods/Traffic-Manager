# Sistema de Associação MCC - Fluxo de Funcionamento

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    SISTEMA MCC - GOOGLE ADS                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Criação de    │    │   Envio de      │    │   Monitoramento │
│    Cliente      │───▶│   Convite       │───▶│   de Status     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  DynamoDB       │    │  Google Ads     │    │  Atualização    │
│  (Clients)      │    │  API            │    │  Automática     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Fluxo Detalhado

### 1. Criação de Cliente
```
Cliente → ScriptManager → create_client.py → GoogleAdsMCCService
    │
    ▼
DynamoDB (Clients Table)
    │
    ▼
Status: NOT_LINKED → PENDING → APPROVED/REJECTED
```

### 2. Envio de Convite MCC
```
GoogleAdsMCCService → CustomerClientLinkService → Google Ads API
    │
    ▼
Convite enviado para conta do cliente
    │
    ▼
Cliente recebe notificação no Google Ads
    │
    ▼
Cliente aceita/rejeita convite
```

### 3. Monitoramento
```
monitor_mcc_status.py → GoogleAdsMCCService → Google Ads API
    │
    ▼
Verificação de status de todas as associações
    │
    ▼
Atualização automática no DynamoDB
```

## Componentes Principais

### Serviços
- **GoogleAdsMCCService**: Serviço principal para gerenciar associações MCC
- **GoogleAdsClientService**: Serviço existente para interação com Google Ads API

### Scripts
- **manage_mcc_links.py**: Interface para gerenciar associações MCC
- **monitor_mcc_status.py**: Monitoramento automático de status
- **create_client.py**: Criação de clientes com integração MCC
- **test_mcc_system.py**: Testes do sistema MCC
- **exemplo_uso_mcc.py**: Exemplos práticos de uso

### Tabelas DynamoDB
- **Clients**: Armazena dados dos clientes e status MCC
- **ExecutionHistory**: Registra histórico de operações MCC

## Status das Associações

```
NOT_LINKED ──┐
             │
             ▼
         PENDING ──┐
                   │
                   ▼
              APPROVED
                   │
                   ▼
              REJECTED
                   │
                   ▼
              CANCELLED
```

## Integração com Fluxo Existente

O sistema MCC se integra perfeitamente ao fluxo existente:

1. **Criação de Cliente**: Automática ao criar novo cliente
2. **Monitoramento**: Pode ser executado periodicamente
3. **Gerenciamento**: Interface unificada para todas as operações
4. **Histórico**: Todas as operações são registradas

## Configuração Necessária

### Variáveis de Ambiente
- MCC_CUSTOMER_ID: ID da conta MCC
- GOOGLE_ADS_DEVELOPER_TOKEN: Token de desenvolvedor
- GOOGLE_ADS_CLIENT_ID: Client ID OAuth2
- GOOGLE_ADS_CLIENT_SECRET: Client Secret OAuth2
- GOOGLE_ADS_REFRESH_TOKEN: Refresh Token OAuth2

### Permissões Necessárias
- Acesso à API do Google Ads
- Permissões para gerenciar associações MCC
- Acesso às tabelas DynamoDB

## Benefícios

1. **Automação Completa**: Elimina intervenção manual
2. **Integração Transparente**: Funciona com fluxo existente
3. **Monitoramento**: Acompanhamento em tempo real
4. **Escalabilidade**: Suporta múltiplos clientes
5. **Confiabilidade**: Tratamento robusto de erros
6. **Auditoria**: Histórico completo de operações
