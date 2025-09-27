# Sistema de Associação MCC - Google Ads

## Visão Geral

Este sistema permite associar automaticamente contas de clientes do Google Ads à sua conta MCC (My Client Center), eliminando a necessidade de intervenção manual no processo de convite e aceitação.

## Como Funciona

### 1. Processo de Associação MCC

1. **Envio do Convite**: O sistema envia automaticamente um convite de associação para a conta do cliente
2. **Notificação ao Cliente**: O cliente recebe uma notificação no Google Ads para aceitar o convite
3. **Aceitação**: Após o cliente aceitar, a associação fica ativa
4. **Gerenciamento**: Você pode gerenciar a conta do cliente através do seu MCC

### 2. Status das Associações

- **NOT_LINKED**: Nenhuma associação existente
- **PENDING**: Convite enviado, aguardando aceitação do cliente
- **APPROVED**: Associação aprovada e ativa
- **REJECTED**: Convite rejeitado pelo cliente
- **CANCELLED**: Convite cancelado
- **ERROR**: Erro no processo de associação

## Configuração

### Variáveis de Ambiente Necessárias

```bash
# Configurações do MCC
export MCC_CUSTOMER_ID="1234567890"  # ID da sua conta MCC
export GOOGLE_ADS_DEVELOPER_TOKEN="seu_developer_token"
export GOOGLE_ADS_CLIENT_ID="seu_client_id"
export GOOGLE_ADS_CLIENT_SECRET="seu_client_secret"
export GOOGLE_ADS_REFRESH_TOKEN="seu_refresh_token"

# Configurações do DynamoDB (já configuradas no serverless.yml)
export CLIENTS_TABLE="traffic-manager-dev-clients"
export EXECUTION_HISTORY_TABLE="traffic-manager-dev-execution-history"
```

### Configuração no serverless.yml

Adicione a variável MCC_CUSTOMER_ID ao seu serverless.yml:

```yaml
provider:
  environment:
    MCC_CUSTOMER_ID: ${ssm:/MCC_CUSTOMER_ID}
```

## Uso

### 1. Criar Cliente com Associação MCC Automática

```bash
# Via script manager
serverless invoke local -s dev -f ScriptManager -p '{
  "script": "create_client",
  "params": {
    "name": "Empresa ABC",
    "email": "contato@empresaabc.com",
    "googleAdsCustomerId": "9876543210",
    "sendMccInvitation": true
  }
}' --aws-profile traffic-manager
```

### 2. Gerenciar Associações MCC

```bash
# Executar script interativo
python src/scripts/manage_mcc_links.py

# Ou via linha de comando
python src/scripts/manage_mcc_links.py --operation send_invitation --client-customer-id 9876543210 --client-name "Empresa ABC"
```

### 3. Monitorar Status das Associações

```bash
# Executar monitoramento
python src/scripts/monitor_mcc_status.py

# Ou via script manager
serverless invoke local -s dev -f ScriptManager -p '{
  "script": "monitor_mcc_status",
  "params": {
    "check_all": true,
    "update_status": true
  }
}' --aws-profile traffic-manager
```

### 4. Executar Testes

```bash
# Executar testes do sistema MCC
python src/scripts/test_mcc_system.py
```

## Scripts Disponíveis

### manage_mcc_links.py

Script principal para gerenciar associações MCC:

- **Enviar convite**: Envia convite de associação para uma conta de cliente
- **Verificar status**: Verifica o status atual de uma associação
- **Listar associações**: Lista todas as associações do MCC
- **Cancelar convite**: Cancela um convite pendente

### monitor_mcc_status.py

Script para monitoramento automático:

- **Verificar todos os clientes**: Atualiza status de todos os clientes
- **Verificar cliente específico**: Atualiza status de um cliente específico
- **Verificar convites pendentes**: Identifica convites há mais de 24h
- **Mostrar estatísticas**: Exibe estatísticas das associações

### create_client.py (Modificado)

Script de criação de clientes agora inclui:

- **Associação MCC automática**: Envia convite automaticamente
- **Status tracking**: Rastreia status da associação MCC
- **Error handling**: Trata erros de associação MCC

## Integração com o Fluxo Existente

### 1. Criação de Clientes

Quando um novo cliente é criado:

1. Cliente é salvo no DynamoDB
2. Convite MCC é enviado automaticamente
3. Status é atualizado conforme resposta
4. Histórico é registrado

### 2. Monitoramento Contínuo

O sistema pode ser configurado para:

1. Verificar status periodicamente
2. Atualizar registros automaticamente
3. Enviar alertas para convites pendentes
4. Gerar relatórios de associações

### 3. Webhooks (Futuro)

Planejado para implementar webhooks que:

1. Notificam quando convites são aceitos
2. Atualizam status automaticamente
3. Disparam ações baseadas em mudanças

## Exemplos de Uso

### Exemplo 1: Criar Cliente e Enviar Convite

```python
from scripts.create_client import execute

params = {
    "name": "Minha Empresa",
    "email": "contato@minhaempresa.com",
    "googleAdsCustomerId": "1234567890",
    "sendMccInvitation": True
}

result = execute(params)
print(f"Cliente criado: {result['clientId']}")
print(f"Status MCC: {result['mccStatus']}")
print(f"Convite enviado: {result['mccInvitation']['success']}")
```

### Exemplo 2: Verificar Status de Associação

```python
from services.google_ads_mcc_service import GoogleAdsMCCService

mcc_service = GoogleAdsMCCService()
status = mcc_service.get_link_status("1234567890")

if status['found']:
    print(f"Status: {status['status']}")
    print(f"Link ID: {status['link_id']}")
else:
    print("Nenhuma associação encontrada")
```

### Exemplo 3: Listar Todas as Associações

```python
from services.google_ads_mcc_service import GoogleAdsMCCService

mcc_service = GoogleAdsMCCService()
links = mcc_service.list_all_links()

for link in links:
    print(f"Cliente: {link['client_customer_id']}")
    print(f"Status: {link['status']}")
    print(f"Criado em: {link['created_date']}")
    print("---")
```

## Troubleshooting

### Problemas Comuns

1. **"Cliente MCC não configurado"**
   - Verifique se todas as variáveis de ambiente estão configuradas
   - Confirme se o MCC_CUSTOMER_ID está correto

2. **"Erro de permissão"**
   - Verifique se o Developer Token tem permissões para MCC
   - Confirme se a conta MCC está configurada corretamente

3. **"Cliente não encontrado"**
   - Verifique se o Customer ID está correto
   - Confirme se a conta do cliente existe

4. **"Refresh token inválido"**
   - Regenere o refresh token usando o script de OAuth2
   - Verifique se as credenciais OAuth2 estão corretas

### Debug

Para debug detalhado:

```bash
# Ativar logs detalhados
export GOOGLE_ADS_DEBUG=1

# Executar com verbose
python src/scripts/manage_mcc_links.py -v
```

## Segurança

### Boas Práticas

1. **Credenciais**: Nunca commite credenciais no código
2. **Variáveis de Ambiente**: Use SSM Parameter Store para credenciais
3. **Permissões**: Use princípio do menor privilégio
4. **Auditoria**: Mantenha logs de todas as operações MCC

### Criptografia

O sistema usa criptografia para:

- Tokens sensíveis do Google Ads
- Dados de configuração dos clientes
- Chaves de acesso

## Monitoramento e Alertas

### Métricas Importantes

- Taxa de aceitação de convites
- Tempo médio para aceitação
- Número de convites pendentes
- Erros de associação

### Alertas Recomendados

- Convites pendentes há mais de 48h
- Taxa de rejeição alta
- Erros de permissão
- Falhas na API do Google Ads

## Roadmap Futuro

### Funcionalidades Planejadas

1. **Webhooks**: Notificações automáticas de mudanças de status
2. **Dashboard**: Interface web para gerenciar associações
3. **Relatórios**: Relatórios detalhados de associações
4. **Automação**: Workflows automáticos baseados em status
5. **Integração**: Integração com outros sistemas de CRM

### Melhorias Técnicas

1. **Cache**: Cache inteligente para reduzir chamadas à API
2. **Retry Logic**: Lógica de retry para falhas temporárias
3. **Rate Limiting**: Controle de taxa para evitar limites da API
4. **Batch Operations**: Operações em lote para eficiência

## Suporte

Para suporte técnico:

1. Verifique os logs de execução
2. Execute os testes do sistema
3. Consulte a documentação da API do Google Ads
4. Verifique as configurações de ambiente

## Conclusão

O sistema de associação MCC automatiza completamente o processo de convite e gerenciamento de contas de clientes, integrando-se perfeitamente ao seu fluxo existente de gestão de tráfego automatizada. Com monitoramento contínuo e tratamento de erros robusto, o sistema garante que todas as associações sejam gerenciadas de forma eficiente e confiável.
