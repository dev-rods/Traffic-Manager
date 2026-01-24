# SPEC-002: Leads Registration System

**PRD:** [002-leads-registration](../prd/002-leads-registration.md)
**Status:** Ready for Implementation
**Created:** 2025-01-24

---

## Resumo das Mudancas

Esta spec implementa um sistema de registro de leads com:
1. Nova tabela DynamoDB para armazenar leads agrupados por cliente
2. Endpoint para criar novos leads (POST /leads)
3. Endpoint para listar leads de um cliente (GET /leads)
4. Endpoint para buscar um lead especifico (GET /leads/{leadId})

---

## Ordem de Implementacao

1. Criar tabela DynamoDB `leads`
2. Criar `src/functions/leads/__init__.py`
3. Criar `src/functions/leads/create.py`
4. Criar `src/functions/leads/list.py`
5. Criar `src/functions/leads/get.py`
6. Criar `sls/functions/leads/interface.yml`
7. Atualizar `serverless.yml`

---

## Arquivos a Criar

### 1. `sls/resources/dynamodb/leads-table.yml`

```yaml
# Schema da Tabela Leads:
# - leadId (String): UUID unico do lead (PK)
# - clientId (String): ID do cliente que capturou o lead
# - name (String): Nome do lead
# - email (String): Email do lead
# - phone (String): Telefone do lead
# - location (String): Localizacao do lead
# - source (String): Origem do lead (web-form, landing-page, etc.)
# - createdAt (String): ISO timestamp da captura
# - metadata (Map): Dados adicionais opcionais
#
# GSI: clientId-createdAt-index
#   - PK: clientId
#   - SK: createdAt

Resources:
  LeadsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: ${self:custom.resourcePrefix}-leads
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: leadId
          AttributeType: S
        - AttributeName: clientId
          AttributeType: S
        - AttributeName: createdAt
          AttributeType: S
      KeySchema:
        - AttributeName: leadId
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: clientId-createdAt-index
          KeySchema:
            - AttributeName: clientId
              KeyType: HASH
            - AttributeName: createdAt
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
```

### 2. `src/functions/leads/__init__.py`

```python
# Leads module
```

### 3. `src/functions/leads/create.py`

```python
"""
Lambda handler para criar um novo lead.

Endpoint: POST /leads
Body: {
    "clientId": "string (required)",
    "name": "string (required)",
    "email": "string (required)",
    "phone": "string (optional)",
    "location": "string (optional)",
    "source": "string (optional, default: 'web-form')",
    "metadata": {} (optional)
}
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any

import boto3

from src.utils.http import require_api_key, parse_body, http_response


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
leads_table = dynamodb.Table(os.environ.get("LEADS_TABLE"))


def _validate_required_fields(body: Dict[str, Any]) -> tuple[bool, str]:
    """Valida campos obrigatorios do lead."""
    required_fields = ["clientId", "name", "email"]
    missing = [field for field in required_fields if not body.get(field)]

    if missing:
        return False, f"Campos obrigatorios ausentes: {', '.join(missing)}"

    return True, ""


def handler(event, context):
    """
    Lambda handler para criar um novo lead.

    Returns:
        dict: Response com leadId criado e dados do lead
    """
    logger.info(f"Iniciando CreateLead com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    if not body:
        return http_response(400, {
            "status": "ERROR",
            "message": "Request body e obrigatorio"
        })

    # Validar campos obrigatorios
    is_valid, error_msg = _validate_required_fields(body)
    if not is_valid:
        return http_response(400, {
            "status": "ERROR",
            "message": error_msg
        })

    try:
        # Gerar ID e timestamp
        lead_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        # Construir item do lead
        lead_item = {
            "leadId": lead_id,
            "clientId": body["clientId"],
            "name": body["name"],
            "email": body["email"],
            "phone": body.get("phone", ""),
            "location": body.get("location", ""),
            "source": body.get("source", "web-form"),
            "createdAt": created_at,
            "metadata": body.get("metadata", {})
        }

        # Salvar no DynamoDB
        leads_table.put_item(Item=lead_item)

        logger.info(f"Lead criado com sucesso: leadId={lead_id}, clientId={body['clientId']}")

        return http_response(201, {
            "status": "SUCCESS",
            "message": "Lead registrado com sucesso",
            "leadId": lead_id,
            "lead": lead_item
        })

    except Exception as e:
        logger.error(f"Erro ao criar lead: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao criar lead: {str(e)}"
        })
```

### 4. `src/functions/leads/list.py`

```python
"""
Lambda handler para listar leads de um cliente.

Endpoint: GET /leads?clientId={clientId}&startDate={startDate}&endDate={endDate}&limit={limit}
"""
import json
import logging
import os
from typing import Dict, Any, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

from src.utils.http import require_api_key, parse_body, http_response, extract_query_param
from src.utils.decimal_utils import convert_decimal_to_json_serializable


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
leads_table = dynamodb.Table(os.environ.get("LEADS_TABLE"))


def handler(event, context):
    """
    Lambda handler para listar leads de um cliente.

    Query Params:
        clientId (required): ID do cliente
        startDate (optional): Filtrar leads a partir desta data (ISO)
        endDate (optional): Filtrar leads ate esta data (ISO)
        limit (optional): Limite de resultados (default: 100, max: 1000)

    Returns:
        dict: Lista de leads do cliente
    """
    logger.info(f"Iniciando ListLeads com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    client_id = extract_query_param(event, "clientId")
    start_date = extract_query_param(event, "startDate")
    end_date = extract_query_param(event, "endDate")
    limit_str = extract_query_param(event, "limit")

    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e obrigatorio como query parameter"
        })

    # Parse limit
    try:
        limit = min(int(limit_str), 1000) if limit_str else 100
    except ValueError:
        limit = 100

    try:
        # Construir query
        key_condition = Key("clientId").eq(client_id)

        # Adicionar filtro de data se especificado
        if start_date and end_date:
            key_condition = key_condition & Key("createdAt").between(start_date, end_date)
        elif start_date:
            key_condition = key_condition & Key("createdAt").gte(start_date)
        elif end_date:
            key_condition = key_condition & Key("createdAt").lte(end_date)

        query_kwargs = {
            "IndexName": "clientId-createdAt-index",
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": False,  # Mais recentes primeiro
            "Limit": limit
        }

        response = leads_table.query(**query_kwargs)
        items = response.get("Items", [])

        # Converter Decimals para JSON serializable
        leads = [convert_decimal_to_json_serializable(item) for item in items]

        return http_response(200, {
            "status": "SUCCESS",
            "leads": leads,
            "count": len(leads),
            "clientId": client_id
        })

    except Exception as e:
        logger.error(f"Erro ao listar leads: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao listar leads: {str(e)}"
        })
```

### 5. `src/functions/leads/get.py`

```python
"""
Lambda handler para buscar um lead especifico por ID.

Endpoint: GET /leads/{leadId}
"""
import json
import logging
import os

import boto3

from src.utils.http import require_api_key, parse_body, http_response, extract_path_param
from src.utils.decimal_utils import convert_decimal_to_json_serializable


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
leads_table = dynamodb.Table(os.environ.get("LEADS_TABLE"))


def handler(event, context):
    """
    Lambda handler para buscar um lead especifico.

    Path Params:
        leadId (required): ID unico do lead

    Returns:
        dict: Dados do lead
    """
    logger.info(f"Iniciando GetLead com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair leadId do path
    lead_id = extract_path_param(event, "leadId")

    if not lead_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "leadId e obrigatorio no path"
        })

    try:
        # Buscar lead por ID
        response = leads_table.get_item(Key={"leadId": lead_id})
        item = response.get("Item")

        if not item:
            return http_response(404, {
                "status": "NOT_FOUND",
                "message": "Lead nao encontrado",
                "leadId": lead_id
            })

        # Converter Decimals para JSON serializable
        lead = convert_decimal_to_json_serializable(item)

        return http_response(200, {
            "status": "SUCCESS",
            "lead": lead
        })

    except Exception as e:
        logger.error(f"Erro ao buscar lead: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao buscar lead: {str(e)}"
        })
```

### 6. `sls/functions/leads/interface.yml`

```yaml
CreateLead:
  image:
    name: lambdaimage
    command: ["src.functions.leads.create.handler"]
  memorySize: 512
  timeout: 30
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-CreateLead-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:PutItem
      Resource: !GetAtt LeadsTable.Arn
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: leads
        method: post
        cors: true

ListLeads:
  image:
    name: lambdaimage
    command: ["src.functions.leads.list.handler"]
  memorySize: 512
  timeout: 30
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ListLeads-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:Query
      Resource:
        - !GetAtt LeadsTable.Arn
        - !Sub "${LeadsTable.Arn}/index/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: leads
        method: get
        cors: true

GetLead:
  image:
    name: lambdaimage
    command: ["src.functions.leads.get.handler"]
  memorySize: 512
  timeout: 30
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-GetLead-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:GetItem
      Resource: !GetAtt LeadsTable.Arn
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: leads/{leadId}
        method: get
        cors: true
```

---

## Arquivos a Modificar

### 7. `serverless.yml`

**Adicionar** na secao `provider.environment`:
```yaml
LEADS_TABLE: ${self:custom.resourcePrefix}-leads
```

**Adicionar** na secao `functions`:
```yaml
- ${file(sls/functions/leads/interface.yml)}
```

**Adicionar** na secao `resources`:
```yaml
- ${file(sls/resources/dynamodb/leads-table.yml)}
```

---

## Endpoints Resultantes

| Metodo | Path | Descricao |
|--------|------|-----------|
| POST | /leads | Cria um novo lead |
| GET | /leads?clientId=X&startDate=Y&endDate=Z&limit=N | Lista leads de um cliente |
| GET | /leads/{leadId} | Busca um lead especifico |

---

## Exemplos de Uso

### Criar Lead (POST /leads)

**Request:**
```bash
# Load API key from .env file first
source .env

curl -X POST https://api.example.com/leads \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "meu-cliente-123",
    "name": "Joao Silva",
    "email": "joao@example.com",
    "phone": "+55 11 99999-9999",
    "location": "Sao Paulo, SP",
    "source": "landing-page"
  }'
```

**Response (201):**
```json
{
  "status": "SUCCESS",
  "message": "Lead registrado com sucesso",
  "leadId": "550e8400-e29b-41d4-a716-446655440000",
  "lead": {
    "leadId": "550e8400-e29b-41d4-a716-446655440000",
    "clientId": "meu-cliente-123",
    "name": "Joao Silva",
    "email": "joao@example.com",
    "phone": "+55 11 99999-9999",
    "location": "Sao Paulo, SP",
    "source": "landing-page",
    "createdAt": "2025-01-24T15:30:00.000000",
    "metadata": {}
  }
}
```

### Listar Leads (GET /leads)

**Request:**
```bash
source .env

curl -X GET "https://api.example.com/leads?clientId=meu-cliente-123&limit=50" \
  -H "x-api-key: $API_KEY"
```

**Response (200):**
```json
{
  "status": "SUCCESS",
  "leads": [
    {
      "leadId": "550e8400-e29b-41d4-a716-446655440000",
      "clientId": "meu-cliente-123",
      "name": "Joao Silva",
      "email": "joao@example.com",
      "phone": "+55 11 99999-9999",
      "location": "Sao Paulo, SP",
      "source": "landing-page",
      "createdAt": "2025-01-24T15:30:00.000000"
    }
  ],
  "count": 1,
  "clientId": "meu-cliente-123"
}
```

### Buscar Lead (GET /leads/{leadId})

**Request:**
```bash
source .env

curl -X GET "https://api.example.com/leads/550e8400-e29b-41d4-a716-446655440000" \
  -H "x-api-key: $API_KEY"
```

**Response (200):**
```json
{
  "status": "SUCCESS",
  "lead": {
    "leadId": "550e8400-e29b-41d4-a716-446655440000",
    "clientId": "meu-cliente-123",
    "name": "Joao Silva",
    "email": "joao@example.com",
    "phone": "+55 11 99999-9999",
    "location": "Sao Paulo, SP",
    "source": "landing-page",
    "createdAt": "2025-01-24T15:30:00.000000",
    "metadata": {}
  }
}
```

---

## Integracao no Frontend (Lovable)

```javascript
// IMPORTANT: Store API_KEY in environment variables, never hardcode!
// In Lovable, use Settings > Environment Variables
const TRAFFIC_MANAGER_API = import.meta.env.VITE_TRAFFIC_MANAGER_API;
const API_KEY = import.meta.env.VITE_TRAFFIC_MANAGER_API_KEY;

const sendToTrafficManager = async (data) => {
  try {
    const response = await fetch(`${TRAFFIC_MANAGER_API}/leads`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
      },
      body: JSON.stringify({
        clientId: "meu-cliente-123",  // Seu clientId
        name: data.name,
        email: data.email,
        phone: data.phone,
        location: data.location,
        source: "landing-page"
      })
    });

    const result = await response.json();
    console.log("Lead registrado:", result.leadId);
    return result;
  } catch (error) {
    console.error("Erro ao enviar para Traffic Manager:", error);
    return null;
  }
};
```

---

## Checklist de Implementacao

- [ ] Criar `sls/resources/dynamodb/leads-table.yml`
- [ ] Criar diretorio `src/functions/leads/`
- [ ] Criar `src/functions/leads/__init__.py`
- [ ] Criar `src/functions/leads/create.py`
- [ ] Criar `src/functions/leads/list.py`
- [ ] Criar `src/functions/leads/get.py`
- [ ] Criar diretorio `sls/functions/leads/`
- [ ] Criar `sls/functions/leads/interface.yml`
- [ ] Atualizar `serverless.yml` (environment, functions, resources)
- [ ] Deploy e teste dos endpoints
