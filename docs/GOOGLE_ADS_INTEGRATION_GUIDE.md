# Guia Completo de Integração com Google Ads API

## Índice
1. [Visão Geral da Integração](#visão-geral-da-integração)
2. [Configuração de Acesso ao Google Ads](#configuração-de-acesso-ao-google-ads)
3. [Autenticação e Tokens](#autenticação-e-tokens)
4. [Modelagem de Dados](#modelagem-de-dados)
5. [Estrutura de Implementação](#estrutura-de-implementação)
6. [Operações de Campanha](#operações-de-campanha)
7. [Fluxo de Integração Completo](#fluxo-de-integração-completo)
8. [Tratamento de Erros](#tratamento-de-erros)
9. [Monitoramento e Logs](#monitoramento-e-logs)
10. [Próximos Passos](#próximos-passos)

---

## Visão Geral da Integração

O sistema de gestão de tráfego automatizada integra com Google Ads API para:

- ✅ **Criar campanhas automaticamente** baseadas em dados do formulário
- ✅ **Otimizar campanhas existentes** usando IA (OpenAI)
- ✅ **Gerenciar múltiplos clientes** com isolamento seguro
- ✅ **Monitorar performance** em tempo real
- ✅ **Automatizar ajustes de lance** baseados em métricas

### Arquitetura Atual

```
Google Forms → Google Sheets → Sistema Lambda → OpenAI → Google Ads API
```

O sistema já possui:
- ✅ Infraestrutura serverless AWS (Lambda, DynamoDB, Step Functions)
- ✅ Gerenciamento de clientes multi-tenant
- ✅ Criptografia de tokens sensíveis
- ✅ Integração com OpenAI para análise inteligente
- ✅ Estrutura base para Google Ads API

---

## Configuração de Acesso ao Google Ads

### 1. Pré-requisitos no Google Cloud Console

#### 1.1 Criar Projeto no Google Cloud Console
```
1. Acesse: https://console.cloud.google.com/
2. Crie um novo projeto ou selecione existente
3. Anote o PROJECT_ID para uso posterior
```

#### 1.2 Habilitar Google Ads API
```
1. Navegue para "APIs & Services" > "Library"
2. Procure por "Google Ads API"
3. Clique em "Enable"
4. Aguarde a ativação (pode levar alguns minutos)
```

#### 1.3 Criar Credenciais OAuth 2.0
```
1. Vá para "APIs & Services" > "Credentials"
2. Clique em "Create Credentials" > "OAuth 2.0 Client IDs"
3. Configure:
   - Application type: Web application
   - Name: Traffic Manager Google Ads
   - Authorized redirect URIs: http://localhost:8080/oauth2callback
4. Baixe o arquivo JSON das credenciais
```

### 2. Obter Developer Token

#### 2.1 Solicitar Acesso à Google Ads API
```
1. Acesse: https://ads.google.com/
2. Entre na conta de administrador do Google Ads
3. Vá para "Tools & Settings" > "API Center"
4. Solicite acesso à API:
   - Preencha formulário de solicitação
   - Descreva o caso de uso (automação de campanhas)
   - Aguarde aprovação (1-3 dias úteis)
```

#### 2.2 Gerar Developer Token
```
1. Após aprovação, retorne ao API Center
2. Gere o Developer Token
3. Anote o token (formato: XXXXXXXXXX)
```

### 3. Configurar Conta de Teste (Sandbox)

Para desenvolvimento e testes:

```
1. Crie uma conta Google Ads de teste
2. Use o Developer Token de teste
3. Configure ambiente sandbox:
   - Endpoint: https://googleads.googleapis.com/
   - Versão: v14 (ou mais recente)
```

---

## Autenticação e Tokens

### 1. Tokens Necessários

O sistema requer 5 tokens por cliente:

```json
{
  "googleAdsConfig": {
    "developerId": "1234567890",           // Customer ID do Google Ads
    "clientId": "xxx.apps.googleusercontent.com",
    "clientSecret": "GOCSPX-xxxxxxxxxxxx",
    "refreshToken": "1//xxxxxxxxxxxx",
    "developerToken": "xxxxxxxxxxxx"
  }
}
```

### 2. Fluxo OAuth 2.0

#### 2.1 Script para Obter Refresh Token

```python
# tools/google_ads_auth.py
import os
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.ads.googleads.client import GoogleAdsClient

SCOPES = ['https://www.googleapis.com/auth/adwords']

def get_refresh_token(client_id, client_secret):
    """
    Obter refresh token via OAuth 2.0
    """
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080"]
            }
        },
        SCOPES
    )
    
    # Inicia o servidor local para callback
    credentials = flow.run_local_server(port=8080)
    
    print(f"Refresh Token: {credentials.refresh_token}")
    return credentials.refresh_token
```

#### 2.2 Validação de Tokens

```python
# src/services/google_ads_validation.py
def validate_google_ads_access(config):
    """
    Valida acesso com os tokens fornecidos
    """
    try:
        client = GoogleAdsClient.load_from_dict({
            'developer_token': config['developerToken'],
            'client_id': config['clientId'],
            'client_secret': config['clientSecret'],
            'refresh_token': config['refreshToken'],
            'use_proto_plus': True
        })
        
        # Teste simples de acesso
        customer_service = client.get_service("CustomerService")
        customer = customer_service.get_customer(
            customer_id=config['developerId']
        )
        
        return {
            'valid': True,
            'customer_info': {
                'id': config['developerId'],
                'name': customer.descriptive_name,
                'currency': customer.currency_code,
                'timezone': customer.time_zone
            }
        }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }
```

### 3. Criptografia de Tokens

O sistema já implementa criptografia automática:

```python
# Já implementado em src/utils/encryption.py
class TokenEncryption:
    def encrypt_google_ads_config(self, config):
        # Criptografa: clientSecret, refreshToken, developerToken
        # Mantém plain text: developerId, clientId
    
    def decrypt_google_ads_config(self, encrypted_config):
        # Descriptografa tokens sensíveis para uso
```

---

## Modelagem de Dados

### 1. Estrutura Atual de Cliente

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

### 2. Novos Modelos Necessários

#### 2.1 Template de Campanha Expandido

```json
{
  "templateId": "ecommerce-search-v1",
  "name": "E-commerce - Pesquisa",
  "description": "Template para campanhas de pesquisa e-commerce",
  "category": "ECOMMERCE",
  "campaignType": "SEARCH",
  "defaultSettings": {
    "budget": {
      "dailyBudgetMicros": 100000000,  // R$ 100.00
      "deliveryMethod": "STANDARD"
    },
    "targeting": {
      "locations": ["2076"],  // Brasil
      "languages": ["1014"],  // Português
      "devices": ["DESKTOP", "MOBILE", "TABLET"]
    },
    "bidding": {
      "strategy": "MAXIMIZE_CLICKS",
      "targetCpa": null,
      "targetRoas": null
    }
  },
  "adGroups": [
    {
      "name": "Produtos Principais",
      "defaultBid": 2000000,  // R$ 2.00
      "keywordCategories": ["product_names", "brand_terms"]
    }
  ],
  "requiredFields": [
    "business_name",
    "productCategories",
    "target_audience",
    "monthlyBudget"
  ]
}
```

#### 2.2 Dados do Formulário (Payload de Entrada)

```json
{
  "formId": "form-123",
  "timestamp": "2024-01-01T10:00:00Z",
  "clientInfo": {
    "business_name": "Loja da Maria",
    "email": "maria@loja.com",
    "phone": "+5511999999999",
    "website": "https://lojadamaria.com.br"
  },
  "businessDetails": {
    "category": "ECOMMERCE",
    "productCategories": ["roupas femininas", "acessórios"],
    "mainProducts": ["vestidos", "bolsas", "sapatos"],
    "target_audience": "mulheres 25-45 anos classe B/C",
    "competitors": ["Renner", "C&A", "Zara"],
    "uniqueSellingPoints": ["entrega rápida", "preços competitivos"]
  },
  "marketingGoals": {
    "primaryGoal": "SALES",
    "monthlyBudget": 5000.00,
    "targetRoas": 4.0,
    "targetConversions": 100,
    "geoTargeting": ["São Paulo", "Rio de Janeiro"]
  },
  "currentMarketing": {
    "hasGoogleAds": false,
    "hasFacebook": true,
    "hasInstagram": true,
    "currentMonthlySpend": 2000.00
  }
}
```

#### 2.3 Resposta da IA Estruturada

```json
{
  "aiAnalysis": {
    "timestamp": "2024-01-01T10:05:00Z",
    "model": "gpt-4",
    "confidence": 0.85,
    "recommendations": {
      "campaignStrategy": "SEARCH_AND_DISPLAY",
      "budgetDistribution": {
        "search": 0.7,
        "display": 0.3
      },
      "keywordRecommendations": [
        {
          "keyword": "vestidos femininos",
          "matchType": "PHRASE",
          "suggestedBid": 3.50,
          "priority": "HIGH"
        }
      ],
      "adCopyRecommendations": [
        {
          "headline1": "Vestidos Femininos Exclusivos",
          "headline2": "Entrega Rápida em SP",
          "description": "Descubra nossa coleção de vestidos. Qualidade e estilo para o seu dia a dia."
        }
      ],
      "targetingRecommendations": {
        "demographics": ["25-45", "FEMALE"],
        "interests": ["fashion", "online_shopping"],
        "locations": ["São Paulo", "Rio de Janeiro"]
      }
    }
  }
}
```

### 3. Estruturas de Campanha Google Ads

#### 3.1 Campanha Criada

```json
{
  "campaignId": "12345678901",
  "clientId": "empresarods-abc123",
  "name": "Loja da Maria - Pesquisa",
  "status": "ACTIVE",
  "type": "SEARCH",
  "budget": {
    "dailyBudgetMicros": 166666667,  // R$ 166.67 (R$ 5000/30)
    "totalBudgetMicros": 5000000000   // R$ 5000.00
  },
  "settings": {
    "startDate": "2024-01-01",
    "endDate": null,
    "biddingStrategy": "MAXIMIZE_CLICKS",
    "targetLocation": ["2076"],
    "targetLanguage": ["1014"]
  },
  "createdAt": "2024-01-01T10:10:00Z",
  "traceId": "trace-abc-123"
}
```

#### 3.2 Histórico de Execução Expandido

```json
{
  "traceId": "trace-abc-123",
  "stageTm": "GOOGLE_ADS_ACTION#2024-01-01T10:10:00Z",
  "stage": "GOOGLE_ADS_ACTION",
  "status": "COMPLETED",
  "runType": "FIRST_RUN",
  "clientId": "empresarods-abc123",
  "campaignId": "12345678901",
  "operations": [
    {
      "type": "CREATE_CAMPAIGN",
      "status": "SUCCESS",
      "resourceId": "12345678901",
      "details": "Campanha criada com sucesso"
    },
    {
      "type": "CREATE_AD_GROUP",
      "status": "SUCCESS", 
      "resourceId": "23456789012",
      "details": "Grupo de anúncios criado"
    }
  ],
  "metrics": {
    "totalOperations": 15,
    "successfulOperations": 14,
    "failedOperations": 1,
    "executionTimeMs": 2500
  }
}
```

---

## Estrutura de Implementação

### 1. Serviços Principais

#### 1.1 Google Ads Client Service (Existente - Melhorar)

```python
# src/services/google_ads_client_service.py
class GoogleAdsClientService:
    def __init__(self):
        # Já implementado - adicionar novos métodos
        
    def create_campaign(self, client_id, campaign_data):
        """Criar nova campanha"""
        
    def update_campaign(self, client_id, campaign_id, updates):
        """Atualizar campanha existente"""
        
    def create_ad_group(self, client_id, campaign_id, ad_group_data):
        """Criar grupo de anúncios"""
        
    def create_keywords(self, client_id, ad_group_id, keywords):
        """Adicionar palavras-chave"""
        
    def create_ads(self, client_id, ad_group_id, ads):
        """Criar anúncios"""
        
    def get_campaign_performance(self, client_id, campaign_id, date_range):
        """Obter métricas de performance"""
```

#### 1.2 Campaign Builder Service (Novo)

```python
# src/services/campaign_builder_service.py
class CampaignBuilderService:
    def build_campaign_from_form_data(self, form_data, ai_analysis, template):
        """
        Constrói estrutura de campanha baseada em:
        - Dados do formulário
        - Análise da IA
        - Template selecionado
        """
        
    def generate_keywords(self, business_data, ai_recommendations):
        """Gera lista de palavras-chave"""
        
    def generate_ad_copy(self, business_data, ai_recommendations):
        """Gera textos de anúncios"""
        
    def calculate_budget_distribution(self, total_budget, campaign_types):
        """Calcula distribuição de orçamento"""
```

#### 1.3 Performance Monitor Service (Novo)

```python
# src/services/performance_monitor_service.py
class PerformanceMonitorService:
    def collect_campaign_metrics(self, client_id, campaign_id):
        """Coleta métricas da campanha"""
        
    def identify_optimization_opportunities(self, metrics):
        """Identifica oportunidades de otimização"""
        
    def generate_performance_report(self, metrics):
        """Gera relatório de performance"""
```

### 2. Funções Lambda

#### 2.1 CampaignOrchestrator (Expandir Existente)

```python
# src/functions/campaign/orchestrator.py - Expandir para receber dados do Forms
def handler(event, context):
    """
    EXPANDIR FUNÇÃO EXISTENTE:
    - Receber dados do Google Forms/Sheets
    - Validar payload de entrada
    - Determinar runType (FIRST_RUN/IMPROVE)
    - Gerar traceId
    - Incluir clientId para multi-tenant
    """
```

#### 2.2 FetchTemplate (Expandir Existente)

```python
# src/functions/templates/fetcher.py - Adaptar para dados do Forms
def handler(event, context):
    """
    EXPANDIR FUNÇÃO EXISTENTE:
    - Selecionar template baseado em dados do formulário
    - Categoria do negócio
    - Objetivos de marketing
    - Orçamento disponível
    - Retornar template + dados do forms combinados
    """
```

#### 2.3 GoogleAdsApiClient (Expandir Existente)

```python
# src/functions/googleads/action.py - Já implementada parcialmente
def handler(event, context):
    """
    EXPANDIR FUNÇÃO EXISTENTE:
    - Usar clientId para autenticação multi-tenant
    - Implementar operações reais do Google Ads
    - Criar campanhas completas (não apenas simular)
    - Gerenciar diferentes tipos de operação
    """
```

### 3. Step Functions Workflow (Existente)

A Step Function `campaign-optimization-flow` já implementa o fluxo completo:

#### 3.1 Estrutura Atual da Step Function

```yaml
# sls/resources/stepfunctions/campaign-optimization-flow.yml (Existente)
CampaignOrchestrator:          # Inicia processo e gera traceId
  ↓
DetermineOptimizationPath:     # Choice: FIRST_RUN ou IMPROVE
  ├─ FIRST_RUN → FetchCampaignTemplate
  └─ IMPROVE → FetchCampaignMetrics
  ↓
CallOpenAI:                    # Análise com OpenAI
  ↓
ParseOpenAIResponse:           # Processa resposta da IA
  ↓
ApplyGoogleAdsChanges:         # Executa no Google Ads
  ↓
FinishCampaignOptimization:    # Registra histórico
```

#### 3.2 Adequação das Implementações Existentes

As funções Lambda já mapeam perfeitamente para a integração Google Ads:

---

## Operações de Campanha

### 1. Criar Campanha Completa

#### 1.1 Estrutura de Operações

```python
operations = [
    {
        "type": "CREATE_CAMPAIGN",
        "data": {
            "name": "Loja da Maria - Pesquisa",
            "advertisingChannelType": "SEARCH",
            "status": "ACTIVE",
            "budget": {
                "dailyBudgetMicros": 166666667
            },
            "biddingStrategy": {
                "type": "MAXIMIZE_CLICKS"
            },
            "geoTargeting": {
                "includedLocations": ["2076"]  # Brasil
            }
        }
    },
    {
        "type": "CREATE_AD_GROUP",
        "data": {
            "name": "Produtos Principais",
            "campaignId": "{CAMPAIGN_ID}",  # Será substituído
            "status": "ACTIVE",
            "cpcBidMicros": 2000000  # R$ 2.00
        }
    },
    {
        "type": "CREATE_KEYWORDS",
        "data": {
            "adGroupId": "{AD_GROUP_ID}",
            "keywords": [
                {
                    "text": "vestidos femininos",
                    "matchType": "PHRASE",
                    "cpcBidMicros": 3500000
                }
            ]
        }
    }
]
```

#### 1.2 Implementação da Criação

```python
# src/services/google_ads_operations.py
class GoogleAdsOperations:
    def execute_campaign_creation(self, client_id, operations):
        """
        Executa criação de campanha completa
        Mantém referências entre recursos criados
        """
        client, customer_id = self.client_service.get_client_for_customer(client_id)
        
        results = []
        resource_map = {}  # Para mapear IDs criados
        
        for operation in operations:
            if operation['type'] == 'CREATE_CAMPAIGN':
                campaign_id = self._create_campaign(
                    client, customer_id, operation['data']
                )
                resource_map['CAMPAIGN_ID'] = campaign_id
                results.append({
                    'type': 'CREATE_CAMPAIGN',
                    'status': 'SUCCESS',
                    'resourceId': campaign_id
                })
                
            elif operation['type'] == 'CREATE_AD_GROUP':
                # Substituir placeholder com ID real
                data = operation['data'].copy()
                data['campaignId'] = resource_map.get('CAMPAIGN_ID')
                
                ad_group_id = self._create_ad_group(client, customer_id, data)
                resource_map['AD_GROUP_ID'] = ad_group_id
                
        return results
```

### 2. Otimizar Campanha Existente

#### 2.1 Análise de Performance

```python
def analyze_campaign_performance(client_id, campaign_id):
    """
    Analisa performance e identifica oportunidades
    """
    # Coletar métricas dos últimos 30 dias
    metrics = collect_campaign_metrics(client_id, campaign_id, days=30)
    
    analysis = {
        'campaign_health': calculate_health_score(metrics),
        'optimization_opportunities': [],
        'budget_recommendations': [],
        'keyword_recommendations': []
    }
    
    # Identificar palavras com baixo CTR
    if metrics['avg_ctr'] < 0.02:  # 2%
        analysis['optimization_opportunities'].append({
            'type': 'LOW_CTR',
            'description': 'CTR abaixo da média',
            'action': 'Revisar anúncios e palavras-chave'
        })
    
    return analysis
```

### 3. Gerenciar Lances Automaticamente

```python
def auto_bid_adjustment(client_id, campaign_id, performance_data):
    """
    Ajusta lances baseado em performance
    """
    adjustments = []
    
    for keyword in performance_data['keywords']:
        current_bid = keyword['bid_micros']
        
        # Aumentar lance se CTR alto e posição baixa
        if keyword['ctr'] > 0.05 and keyword['avg_position'] > 3:
            new_bid = int(current_bid * 1.2)  # Aumentar 20%
            adjustments.append({
                'keyword_id': keyword['id'],
                'old_bid': current_bid,
                'new_bid': new_bid,
                'reason': 'High CTR, low position'
            })
    
    return adjustments
```

---

## Fluxo de Integração Completo

### 1. Fluxo de Criação de Campanha (FIRST_RUN)

```
1. Cliente preenche formulário Google Forms
   ↓
2. Dados são enviados via webhook → CampaignOrchestrator
   ↓
3. CampaignOrchestrator: valida dados, determina runType=FIRST_RUN
   ↓
4. DetermineOptimizationPath: choice → FetchCampaignTemplate
   ↓
5. FetchTemplate: seleciona template baseado no negócio
   ↓
6. CallOpenAI: analisa dados + template com IA
   ↓
7. ParseOpenAIResponse: converte análise → operações Google Ads
   ↓
8. ApplyGoogleAdsChanges: cria campanha completa no Google Ads
   ↓
9. FinishCampaignOptimization: registra histórico
```

### 2. Fluxo de Otimização (IMPROVE)

```
1. CampaignOrchestrator: inicia com runType=IMPROVE
   ↓
2. DetermineOptimizationPath: choice → FetchCampaignMetrics
   ↓
3. FetchMetrics: coleta métricas Google Ads dos últimos 30 dias
   ↓
4. CallOpenAI: analisa performance e gera recomendações
   ↓
5. ParseOpenAIResponse: converte recomendações → ajustes API
   ↓
6. ApplyGoogleAdsChanges: aplica otimizações (lances, palavras, etc)
   ↓
7. FinishCampaignOptimization: registra histórico de otimização
```

### 3. Integração com Google Sheets

```python
# src/services/google_sheets_service.py
class GoogleSheetsService:
    def __init__(self):
        # Configurar credenciais do Google Sheets API
        
    def get_form_responses(self, spreadsheet_id, range_name):
        """
        Obtém respostas do formulário do Google Sheets
        """
        
    def parse_form_data(self, raw_data):
        """
        Converte dados do sheets para formato estruturado
        """
        return {
            'clientInfo': {...},
            'businessDetails': {...},
            'marketingGoals': {...}
        }
```

---

## Tratamento de Erros

### 1. Tipos de Erro Comuns

```python
# src/utils/google_ads_errors.py
GOOGLE_ADS_ERRORS = {
    'AUTHENTICATION_ERROR': {
        'description': 'Erro de autenticação',
        'action': 'Verificar tokens do cliente',
        'retry': False
    },
    'QUOTA_ERROR': {
        'description': 'Limite de quota excedido',
        'action': 'Aguardar reset ou aumentar quota',
        'retry': True,
        'retry_after': 3600  # 1 hora
    },
    'BUDGET_ERROR': {
        'description': 'Erro de orçamento',
        'action': 'Verificar configurações de budget',
        'retry': False
    }
}
```

### 2. Estratégia de Retry

```python
def execute_with_retry(operation, max_retries=3):
    """
    Executa operação com retry automático
    """
    for attempt in range(max_retries):
        try:
            return operation()
        except GoogleAdsException as e:
            error_code = e.error.code().name
            
            if error_code in RETRYABLE_ERRORS and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 60  # Backoff exponencial
                time.sleep(wait_time)
                continue
                
            raise e
```

---

## Monitoramento e Logs

### 1. Métricas Importantes

```python
CAMPAIGN_METRICS = [
    'impressions',
    'clicks', 
    'cost_micros',
    'conversions',
    'conversion_value',
    'ctr',
    'average_cpc',
    'cost_per_conversion'
]

KEYWORD_METRICS = [
    'impressions',
    'clicks',
    'cost_micros', 
    'ctr',
    'average_cpc',
    'quality_score'
]
```

### 2. Alertas e Notificações

```python
# src/services/alert_service.py
class AlertService:
    def check_campaign_health(self, campaign_metrics):
        """
        Verifica saúde da campanha e envia alertas
        """
        alerts = []
        
        # CTR muito baixo
        if campaign_metrics['ctr'] < 0.01:
            alerts.append({
                'type': 'LOW_CTR',
                'severity': 'HIGH',
                'message': 'CTR abaixo de 1%'
            })
            
        # Orçamento esgotado rapidamente
        if campaign_metrics['budget_utilization'] > 0.9:
            alerts.append({
                'type': 'BUDGET_EXHAUSTED',
                'severity': 'MEDIUM', 
                'message': 'Orçamento sendo consumido rapidamente'
            })
            
        return alerts
```

---

## Próximos Passos

### 1. Implementação Imediata (Sprint 1)

- [ ] **Configurar acesso Google Ads API**
  - Obter Developer Token
  - Configurar OAuth 2.0
  - Testar autenticação

- [ ] **Expandir CampaignOrchestrator**
  - Adicionar validação de dados do Forms
  - Implementar detecção automática de runType
  - Incluir suporte a clientId multi-tenant

- [ ] **Expandir templates de campanha**
  - Mapear categorias de negócio → templates
  - Definir configurações padrão por categoria
  - Implementar seleção automática no FetchTemplate

### 2. Desenvolvimento Core (Sprint 2-3)

- [ ] **Implementar FetchMetrics**
  - Integrar com GoogleAdsClientService existente
  - Coletar métricas dos últimos 30 dias
  - Formatar dados para análise da IA

- [ ] **Expandir PayloadParser**
  - Converter recomendações IA → operações Google Ads API
  - Mapear estrutura completa de campanha
  - Suportar tanto FIRST_RUN quanto IMPROVE

- [ ] **Implementar GoogleAdsApiClient real**
  - Substituir simulação por operações reais
  - Usar autenticação multi-tenant existente
  - Criar campanhas completas (campanha + grupos + palavras + anúncios)

- [ ] **Integration Testing**
  - Teste end-to-end da Step Function existente
  - Validação com dados reais do Forms
  - Performance testing com conta sandbox

### 3. Otimização e Monitoramento (Sprint 4-5)

- [ ] **Performance Monitor**
  - Coleta automática de métricas
  - Análise de performance com IA
  - Alertas automáticos

- [ ] **Auto-optimization**
  - Ajustes automáticos de lance
  - Otimização de palavras-chave
  - A/B testing de anúncios

- [ ] **Reporting Dashboard**
  - Interface para visualizar campanhas
  - Relatórios de performance
  - Histórico de otimizações

### 4. Recursos Avançados (Futuro)

- [ ] **Machine Learning**
  - Predição de performance
  - Otimização preditiva de lances
  - Segmentação automática de audiência

- [ ] **Multi-channel Integration**
  - Integração com Facebook Ads
  - Coordenação entre canais
  - Attribution modeling

- [ ] **Advanced Analytics**
  - Customer lifetime value
  - Advanced conversion tracking
  - Cross-device attribution

---

## Checklist de Configuração

### ✅ Configuração Google Cloud

- [ ] Projeto criado no Google Cloud Console
- [ ] Google Ads API habilitada
- [ ] Credenciais OAuth 2.0 configuradas
- [ ] Developer Token obtido e validado

### ✅ Configuração AWS

- [ ] Tokens armazenados no SSM Parameter Store
- [ ] Tabelas DynamoDB atualizadas
- [ ] IAM roles configuradas para Google Ads API
- [ ] Environment variables atualizadas

### ✅ Desenvolvimento

- [ ] Google Ads Python library instalada
- [ ] Novos serviços implementados
- [ ] Webhooks configurados
- [ ] Testes unitários criados

### ✅ Deploy e Teste

- [ ] Deploy em ambiente de desenvolvimento
- [ ] Testes com conta sandbox Google Ads
- [ ] Configuração de monitoramento
- [ ] Documentação atualizada

---

---

## Implementações Detalhadas das Funções Existentes

### 1. Expandir CampaignOrchestrator

**Arquivo:** `src/functions/campaign/orchestrator.py`

```python
def handler(event, context):
    """
    Expandir função existente para:
    1. Receber dados do Google Forms via webhook
    2. Validar estrutura de dados
    3. Determinar runType automaticamente
    4. Incluir clientId no payload
    """
    try:
        # NOVO: Detectar origem dos dados
        if 'formData' in event:
            # Dados vindos do Google Forms
            run_type = 'FIRST_RUN'
            client_id = determine_client_from_email(event['formData']['email'])
        elif 'campaignId' in event:
            # Otimização de campanha existente
            run_type = 'IMPROVE'
            client_id = get_client_from_campaign(event['campaignId'])
        
        # Validar se cliente tem acesso Google Ads
        ads_service = GoogleAdsClientService()
        validation = ads_service.validate_client_access(client_id)
        if not validation['valid']:
            raise Exception(f"Cliente sem acesso Google Ads: {validation['error']}")
        
        # Gerar trace_id e preparar payload (lógica existente)
        trace_id = generate_trace_id()
        
        response = {
            'traceId': trace_id,
            'runType': run_type,
            'clientId': client_id,  # NOVO: Incluir clientId
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Incluir dados específicos do tipo
        if run_type == 'FIRST_RUN':
            response['formData'] = event['formData']
        else:
            response['campaignId'] = event['campaignId']
            
        return response
        
    except Exception as e:
        logger.error(f"Erro no CampaignOrchestrator: {str(e)}")
        raise
```

### 2. Expandir FetchTemplate  

**Arquivo:** `src/functions/templates/fetcher.py`

```python
def handler(event, context):
    """
    Expandir para seleção inteligente baseada em dados do Forms
    """
    try:
        trace_id = event.get('traceId')
        client_id = event.get('clientId')
        form_data = event.get('formData', {})
        
        # NOVO: Mapear categoria do negócio → template
        business_category = form_data.get('businessDetails', {}).get('category')
        monthly_budget = form_data.get('marketingGoals', {}).get('monthlyBudget', 0)
        
        # Seleção de template baseada em regras
        template_id = select_template_by_criteria(
            category=business_category,
            budget=monthly_budget,
            goals=form_data.get('marketingGoals', {})
        )
        
        # Buscar template do DynamoDB (lógica existente)
        template = get_template_from_db(template_id)
        
        # NOVO: Personalizar template com dados do formulário
        customized_template = customize_template_with_form_data(
            template, form_data
        )
        
        response = {
            'traceId': trace_id,
            'clientId': client_id,
            'templateData': customized_template,
            'formData': form_data,  # Passar dados adiante
            'runType': 'FIRST_RUN'
        }
        
        return response
        
    except Exception as e:
        logger.error(f"[{trace_id}] Erro no FetchTemplate: {str(e)}")
        raise
```

### 3. Implementar FetchMetrics

**Arquivo:** `src/functions/metrics/fetcher.py`

```python
def handler(event, context):
    """
    NOVA IMPLEMENTAÇÃO: Coletar métricas Google Ads para otimização
    """
    try:
        trace_id = event.get('traceId')
        client_id = event.get('clientId')
        campaign_id = event.get('campaignId')
        
        # Usar serviço existente
        ads_service = GoogleAdsClientService()
        
        # Coletar métricas dos últimos 30 dias
        metrics = ads_service.get_campaign_performance(
            client_id=client_id,
            campaign_id=campaign_id,
            date_range={'days': 30}
        )
        
        # Buscar dados detalhados
        detailed_metrics = {
            'campaign': metrics,
            'keywords': ads_service.get_keyword_performance(client_id, campaign_id),
            'ads': ads_service.get_ad_performance(client_id, campaign_id)
        }
        
        response = {
            'traceId': trace_id,
            'clientId': client_id,
            'campaignId': campaign_id,
            'metricsData': detailed_metrics,
            'runType': 'IMPROVE'
        }
        
        return response
        
    except Exception as e:
        logger.error(f"[{trace_id}] Erro no FetchMetrics: {str(e)}")
        raise
```

### 4. Expandir PayloadParser

**Arquivo:** `src/functions/parser/payload_parser.py`

```python
def handler(event, context):
    """
    Expandir para converter recomendações IA → operações Google Ads
    """
    try:
        trace_id = event.get('traceId')
        client_id = event.get('clientId')
        run_type = event.get('runType')
        ai_response = event.get('aiResponse')
        
        if run_type == 'FIRST_RUN':
            # Criar operações para nova campanha
            operations = build_campaign_creation_operations(
                ai_response, 
                event.get('templateData'),
                event.get('formData')
            )
        else:
            # Criar operações de otimização
            operations = build_optimization_operations(
                ai_response,
                event.get('metricsData'),
                event.get('campaignId')
            )
        
        google_ads_payload = {
            'operations': operations,
            'clientId': client_id,
            'runType': run_type
        }
        
        response = {
            'traceId': trace_id,
            'clientId': client_id,
            'runType': run_type,
            'googleAdsPayload': google_ads_payload
        }
        
        if 'campaignId' in event:
            response['campaignId'] = event['campaignId']
            
        return response
        
    except Exception as e:
        logger.error(f"[{trace_id}] Erro no PayloadParser: {str(e)}")
        raise
```

### 5. Implementar GoogleAdsApiClient Real

**Arquivo:** `src/functions/googleads/action.py` (expandir existente)

```python
def handler(event, context):
    """
    Expandir função existente para operações reais do Google Ads
    """
    try:
        trace_id = event.get('traceId')
        client_id = event.get('clientId')  # NOVO: usar clientId
        run_type = event.get('runType')
        google_ads_payload = event.get('googleAdsPayload')
        
        # Usar serviço de cliente multi-tenant
        ads_service = GoogleAdsClientService()
        google_ads_client, customer_id = ads_service.get_client_for_customer(client_id)
        
        if not google_ads_client:
            raise Exception(f"Cliente {client_id} não configurado para Google Ads")
        
        operations = google_ads_payload.get('operations', [])
        
        # Executar operações reais (não mais simulação)
        if run_type == 'FIRST_RUN':
            results = execute_campaign_creation_real(google_ads_client, customer_id, operations)
        else:
            results = execute_campaign_optimization_real(google_ads_client, customer_id, operations)
        
        response = {
            'traceId': trace_id,
            'clientId': client_id,
            'runType': run_type,
            'googleAdsResults': {
                'success_count': len(results['success']),
                'failure_count': len(results['failure']),
                'operations': results
            }
        }
        
        return response
        
    except Exception as e:
        logger.error(f"[{trace_id}] Erro no GoogleAdsApiClient: {str(e)}")
        raise
```

---

**Data de Criação:** 2024-01-20  
**Versão:** 1.1 - Adequado à Step Function Existente  
**Autor:** Sistema de Gestão de Tráfego Automatizada  
**Próxima Revisão:** Após implementação Sprint 1