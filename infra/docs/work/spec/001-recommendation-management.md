# SPEC-001: Recommendation Management System

**PRD:** [001-recommendation-management](../prd/001-recommendation-management.md)
**Status:** Ready for Implementation
**Created:** 2025-01-24

---

## Resumo das Mudanças

Esta spec implementa um sistema de gerenciamento de recomendações com:
1. Nova tabela DynamoDB para armazenar recomendações com ID único
2. Modificação no gerador para salvar com `recommendationId`
3. Novo endpoint para aplicar recomendação por ID (substitui o antigo)
4. Novo endpoint para listar recomendações por cliente/campanha

---

## Ordem de Implementação

1. Criar tabela DynamoDB `recommendations`
2. Modificar `generate_recommendations.py`
3. Criar `list_recommendations.py`
4. Criar `apply_recommendation.py`
5. Atualizar `serverless.yml` e `interface.yml`
6. Remover handler antigo `apply_recommendations.py`

---

## Arquivos a Criar

### 1. `sls/resources/dynamodb/recommendations-table.yml`

```yaml
# Schema da Tabela Recommendations:
# - recommendationId (String): UUID único da recomendação (PK)
# - clientId (String): ID do cliente
# - campaignId (String): ID da campanha Google Ads
# - status (String): PENDING, APPLIED, SKIPPED
# - action (String): Ação recomendada (INCREASE_CPC_10, etc.)
# - metrics (Map): Métricas no momento da geração
# - payload (Map): Payload completo da recomendação
# - createdAt (String): ISO timestamp da criação
# - appliedAt (String): ISO timestamp da aplicação
# - applicationResult (Map): Resultado da aplicação
#
# GSI: clientId-campaignId-index
#   - PK: clientId
#   - SK: campaignIdCreatedAt (composto: campaignId#createdAt)

Resources:
  RecommendationsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: ${self:custom.resourcePrefix}-recommendations
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: recommendationId
          AttributeType: S
        - AttributeName: clientId
          AttributeType: S
        - AttributeName: campaignIdCreatedAt
          AttributeType: S
      KeySchema:
        - AttributeName: recommendationId
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: clientId-campaignId-index
          KeySchema:
            - AttributeName: clientId
              KeyType: HASH
            - AttributeName: campaignIdCreatedAt
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
```

### 2. `src/functions/recommendations/list_recommendations.py`

```python
"""
Lambda handler para listar recomendações de otimização.

Endpoint: GET /recommendations?clientId={clientId}&campaignId={campaignId}&status={status}
"""
import json
import logging
import os
from typing import Dict, Any, List, Optional
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr

from src.utils.http import require_api_key, parse_body, http_response, extract_query_param
from src.utils.decimal_utils import convert_decimal_to_json_serializable


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
recommendations_table = dynamodb.Table(os.environ.get("RECOMMENDATIONS_TABLE"))


def handler(event, context):
    """
    Lambda handler para listar recomendações.

    Query Params:
        clientId (required): ID do cliente
        campaignId (optional): Filtrar por campanha específica
        status (optional): Filtrar por status (PENDING, APPLIED, SKIPPED)

    Returns:
        dict: Lista de recomendações
    """
    logger.info(f"Iniciando ListRecommendations com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parâmetros
    client_id = extract_query_param(event, "clientId")
    campaign_id = extract_query_param(event, "campaignId")
    status_filter = extract_query_param(event, "status")

    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId é obrigatório como query parameter"
        })

    try:
        # Query usando GSI
        key_condition = Key("clientId").eq(client_id)

        if campaign_id:
            # Filtrar por campaignId usando begins_with no sort key composto
            key_condition = key_condition & Key("campaignIdCreatedAt").begins_with(f"{campaign_id}#")

        query_kwargs = {
            "IndexName": "clientId-campaignId-index",
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": False  # Mais recentes primeiro
        }

        # Adicionar filtro de status se especificado
        if status_filter:
            query_kwargs["FilterExpression"] = Attr("status").eq(status_filter)

        response = recommendations_table.query(**query_kwargs)
        items = response.get("Items", [])

        # Converter Decimals para JSON serializable
        recommendations = [convert_decimal_to_json_serializable(item) for item in items]

        return http_response(200, {
            "status": "SUCCESS",
            "recommendations": recommendations,
            "count": len(recommendations)
        })

    except Exception as e:
        logger.error(f"Erro ao listar recomendações: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao listar recomendações: {str(e)}"
        })
```

### 3. `src/functions/recommendations/apply_recommendation.py`

```python
"""
Lambda handler para aplicar uma recomendação de otimização.

Endpoint: POST /recommendations/{recommendationId}/apply
Body: { "clientId": "string", "campaignId": "string" }
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal
import boto3

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response, extract_path_param
from src.utils.decimal_utils import convert_decimal_to_json_serializable


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
recommendations_table = dynamodb.Table(os.environ.get("RECOMMENDATIONS_TABLE"))
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))


# Mapeamento de ações para multiplicadores de CPC
ACTION_CPC_MULTIPLIERS = {
    "INCREASE_CPC_15": 1.15,
    "INCREASE_CPC_10": 1.10,
    "KEEP_CPC": 1.0,
    "REDUCE_CPC_15": 0.85,
}


def _get_recommendation(recommendation_id: str) -> Optional[Dict[str, Any]]:
    """Busca recomendação por ID."""
    try:
        response = recommendations_table.get_item(
            Key={"recommendationId": recommendation_id}
        )
        return response.get("Item")
    except Exception as e:
        logger.error(f"Erro ao buscar recomendação {recommendation_id}: {str(e)}")
        return None


def _update_recommendation_status(
    recommendation_id: str,
    status: str,
    application_result: Dict[str, Any]
) -> None:
    """Atualiza status da recomendação após aplicação."""
    try:
        update_expr = "SET #status = :status, appliedAt = :appliedAt, applicationResult = :result"
        recommendations_table.update_item(
            Key={"recommendationId": recommendation_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":appliedAt": datetime.utcnow().isoformat(),
                ":result": application_result
            }
        )
        logger.info(f"Recomendação {recommendation_id} atualizada para status {status}")
    except Exception as e:
        logger.error(f"Erro ao atualizar recomendação: {str(e)}")


def _log_execution(
    trace_id: str,
    client_id: str,
    campaign_id: str,
    recommendation_id: str,
    action: str,
    operations: List[Dict],
    dry_run: bool,
    status: str
) -> None:
    """Registra a execução na tabela de histórico."""
    try:
        timestamp = datetime.utcnow().isoformat()
        execution_record = {
            "traceId": trace_id,
            "stageTm": f"APPLY_RECOMMENDATION#{timestamp}",
            "stage": "APPLY_RECOMMENDATION",
            "status": status,
            "timestamp": timestamp,
            "clientId": client_id,
            "campaignId": campaign_id,
            "payload": json.dumps({
                "recommendationId": recommendation_id,
                "action": action,
                "operations": operations,
                "dryRun": dry_run
            })
        }
        execution_history_table.put_item(Item=execution_record)
        logger.info(f"[traceId: {trace_id}] Execução registrada com status {status}")
    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao registrar execução: {str(e)}")


def _apply_pause_campaign(
    service: GoogleAdsClientService,
    client_id: str,
    campaign_id: str,
    dry_run: bool
) -> Dict[str, Any]:
    """Aplica ação de pausar campanha."""
    if dry_run:
        return {
            "type": "PAUSE_CAMPAIGN",
            "success": True,
            "dryRun": True,
            "details": {
                "campaign_id": campaign_id,
                "message": "Campanha seria pausada (dry run)"
            }
        }

    result = service.pause_campaign(client_id, campaign_id)
    return {
        "type": "PAUSE_CAMPAIGN",
        "success": result.get("success", False),
        "dryRun": False,
        "details": result
    }


def _apply_cpc_update(
    service: GoogleAdsClientService,
    client_id: str,
    ad_groups: List[Dict],
    multiplier: float,
    dry_run: bool
) -> List[Dict[str, Any]]:
    """Aplica ajuste de CPC em todos os ad groups."""
    operations = []

    for ad_group in ad_groups:
        ad_group_id = ad_group.get("id") or ad_group.get("ad_group_id")
        current_cpc = ad_group.get("cpc_bid_micros") or ad_group.get("cpc_micros", 0)

        if not ad_group_id:
            continue

        if isinstance(current_cpc, Decimal):
            current_cpc = int(current_cpc)

        new_cpc = int(current_cpc * multiplier)

        if dry_run:
            operations.append({
                "type": "UPDATE_CPC",
                "success": True,
                "dryRun": True,
                "details": {
                    "ad_group_id": str(ad_group_id),
                    "current_cpc_micros": current_cpc,
                    "new_cpc_micros": new_cpc,
                    "multiplier": multiplier,
                    "message": f"CPC seria atualizado de {current_cpc} para {new_cpc} micros (dry run)"
                }
            })
        else:
            result = service.update_ad_group_cpc(client_id, str(ad_group_id), new_cpc)
            operations.append({
                "type": "UPDATE_CPC",
                "success": result.get("success", False),
                "dryRun": False,
                "details": {
                    **result,
                    "previous_cpc_micros": current_cpc,
                    "multiplier": multiplier
                }
            })

    return operations


def handler(event, context):
    """
    Lambda handler para aplicar uma recomendação específica.

    Endpoint: POST /recommendations/{recommendationId}/apply
    Body: { "clientId": "string", "campaignId": "string", "dryRun": bool }
    """
    logger.info(f"Iniciando ApplyRecommendation com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parâmetros
    recommendation_id = extract_path_param(event, "recommendationId")
    if not recommendation_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "recommendationId é obrigatório no path"
        })

    request_client_id = (body or {}).get("clientId")
    request_campaign_id = (body or {}).get("campaignId")
    dry_run = (body or {}).get("dryRun", False)

    if not request_client_id or not request_campaign_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e campaignId são obrigatórios no body"
        })

    # Buscar recomendação
    recommendation = _get_recommendation(recommendation_id)
    if not recommendation:
        return http_response(404, {
            "status": "NOT_FOUND",
            "recommendationId": recommendation_id,
            "message": "Recomendação não encontrada"
        })

    # Validar que clientId e campaignId correspondem
    rec_client_id = recommendation.get("clientId")
    rec_campaign_id = recommendation.get("campaignId")

    if rec_client_id != request_client_id or rec_campaign_id != request_campaign_id:
        return http_response(400, {
            "status": "MISMATCH",
            "message": "clientId ou campaignId não correspondem à recomendação"
        })

    # Verificar se já foi aplicada
    if recommendation.get("status") == "APPLIED" and not dry_run:
        return http_response(409, {
            "status": "ALREADY_APPLIED",
            "recommendationId": recommendation_id,
            "appliedAt": recommendation.get("appliedAt"),
            "message": "Esta recomendação já foi aplicada"
        })

    # Extrair dados da recomendação
    action = recommendation.get("action")
    metrics = recommendation.get("metrics", {})
    ad_groups = metrics.get("ad_groups", [])
    campaign_name = recommendation.get("campaignName", "")

    if not action:
        return http_response(400, {
            "status": "ERROR",
            "message": "action não encontrada na recomendação"
        })

    # Gerar trace ID
    trace_id = f"apply-rec-{recommendation_id[:8]}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    logger.info(f"[traceId: {trace_id}] Aplicando recomendação {recommendation_id}, ação={action}, dryRun={dry_run}")

    # Inicializar serviço do Google Ads
    service = GoogleAdsClientService()
    operations = []

    try:
        if action == "PAUSE_CAMPAIGN":
            operation_result = _apply_pause_campaign(
                service, rec_client_id, rec_campaign_id, dry_run
            )
            operations.append(operation_result)

        elif action == "KEEP_CPC":
            operations.append({
                "type": "KEEP_CPC",
                "success": True,
                "dryRun": dry_run,
                "details": {"message": "CPC mantido conforme recomendação"}
            })

        elif action in ACTION_CPC_MULTIPLIERS:
            multiplier = ACTION_CPC_MULTIPLIERS[action]

            if not ad_groups:
                ad_groups = service.get_ad_groups(rec_client_id, campaign_id=rec_campaign_id)

            if ad_groups:
                cpc_operations = _apply_cpc_update(
                    service, rec_client_id, ad_groups, multiplier, dry_run
                )
                operations.extend(cpc_operations)
            else:
                operations.append({
                    "type": "UPDATE_CPC",
                    "success": False,
                    "dryRun": dry_run,
                    "details": {"message": "Nenhum ad group encontrado para atualizar CPC"}
                })

        else:
            return http_response(400, {
                "status": "ERROR",
                "message": f"Ação desconhecida: {action}"
            })

        # Verificar sucesso
        all_success = all(op.get("success", False) for op in operations)
        status = "SUCCESS" if all_success else "PARTIAL_SUCCESS"

        # Atualizar status da recomendação (se não for dry run)
        if not dry_run and all_success:
            _update_recommendation_status(
                recommendation_id,
                "APPLIED",
                {"operations": operations, "traceId": trace_id}
            )

        # Registrar execução
        _log_execution(
            trace_id=trace_id,
            client_id=rec_client_id,
            campaign_id=rec_campaign_id,
            recommendation_id=recommendation_id,
            action=action,
            operations=operations,
            dry_run=dry_run,
            status=status
        )

        response_data = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "recommendationId": recommendation_id,
            "clientId": rec_client_id,
            "campaignId": rec_campaign_id,
            "campaignName": campaign_name,
            "action": action,
            "dryRun": dry_run,
            "operations": operations
        }

        logger.info(f"[traceId: {trace_id}] Aplicação concluída com status {status}")
        return http_response(200, response_data)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id}] Erro ao aplicar recomendação: {error_msg}", exc_info=True)

        _log_execution(
            trace_id=trace_id,
            client_id=rec_client_id,
            campaign_id=rec_campaign_id,
            recommendation_id=recommendation_id,
            action=action,
            operations=operations,
            dry_run=dry_run,
            status="ERROR"
        )

        return http_response(500, {
            "status": "ERROR",
            "recommendationId": recommendation_id,
            "message": f"Erro ao aplicar recomendação: {error_msg}"
        })
```

### 4. `src/functions/recommendations/__init__.py`

```python
# Recommendations module
```

---

## Arquivos a Modificar

### 5. `serverless.yml`

**Adicionar** na seção `provider.environment`:
```yaml
RECOMMENDATIONS_TABLE: ${self:custom.resourcePrefix}-recommendations
```

**Adicionar** na seção `functions`:
```yaml
- ${file(sls/functions/recommendations/interface.yml)}
```

**Adicionar** na seção `resources`:
```yaml
- ${file(sls/resources/dynamodb/recommendations-table.yml)}
```

### 6. `sls/functions/optimizer/interface.yml`

**Remover** todo o bloco `ApplyRecommendations` (linhas 34-58).

### 7. `sls/functions/recommendations/interface.yml` (NOVO)

```yaml
ListRecommendations:
  image:
    name: lambdaimage
    command: ["src.functions.recommendations.list_recommendations.handler"]
  memorySize: 512
  timeout: 30
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ListRecommendations-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:Query
      Resource:
        - !GetAtt RecommendationsTable.Arn
        - !Sub "${RecommendationsTable.Arn}/index/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: recommendations
        method: get
        cors: true

ApplyRecommendation:
  image:
    name: lambdaimage
    command: ["src.functions.recommendations.apply_recommendation.handler"]
  memorySize: 1024
  timeout: 300
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ApplyRecommendation-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:GetItem
        - dynamodb:UpdateItem
      Resource: !GetAtt RecommendationsTable.Arn
    - Effect: Allow
      Action:
        - dynamodb:PutItem
      Resource: !GetAtt ExecutionHistoryTable.Arn
    - Effect: Allow
      Action:
        - dynamodb:GetItem
      Resource: !GetAtt ClientsTable.Arn
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: recommendations/{recommendationId}/apply
        method: post
        cors: true
```

### 8. `src/functions/optimizer/generate_recommendations.py`

**Modificações:**

1. **Importar uuid:**
```python
import uuid
```

2. **Adicionar variável para nova tabela:**
```python
recommendations_table = dynamodb.Table(os.environ.get("RECOMMENDATIONS_TABLE"))
```

3. **Modificar `_store_recommendation()`** para usar nova tabela e gerar ID:

```python
def _store_recommendation(
    client_id: str,
    campaign_id: str,
    campaign_name: str,
    optimization_config: Dict[str, Any],
    metrics: Dict[str, Any],
    action: str,
) -> str:
    """
    Salva recomendação na tabela Recommendations com ID único.

    Returns:
        str: recommendationId gerado
    """
    recommendation_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    healthy_cpa = optimization_config.get("healthy_cpa")
    current_cpa = metrics.get("cost_per_conversion")

    # Converter valores numéricos para Decimal
    optimization_config_decimal = convert_dict_to_decimal(optimization_config)
    metrics_decimal = convert_dict_to_decimal(metrics)
    healthy_cpa_decimal = convert_to_decimal(healthy_cpa) if healthy_cpa is not None else None
    current_cpa_decimal = convert_to_decimal(current_cpa) if current_cpa is not None else None

    item = {
        "recommendationId": recommendation_id,
        "clientId": client_id,
        "campaignId": str(campaign_id),
        "campaignIdCreatedAt": f"{campaign_id}#{timestamp}",  # Sort key para GSI
        "status": "PENDING",
        "campaignName": campaign_name,
        "createdAt": timestamp,
        "optimizationConfig": optimization_config_decimal,
        "metrics": metrics_decimal,
        "healthyCpa": healthy_cpa_decimal,
        "currentCpa": current_cpa_decimal,
        "action": action,
        "period": {"days": 30},
    }

    logger.info(
        f"[clientId={client_id}][campaignId={campaign_id}][recommendationId={recommendation_id}] "
        f"Ação recomendada: {action} | CPA atual={current_cpa} | CPA saudável={healthy_cpa}"
    )

    recommendations_table.put_item(Item=item)
    return recommendation_id
```

4. **Modificar retorno no loop** para incluir `recommendationId`:

```python
# Dentro do loop for campaign_data in campaigns:
recommendation_id = _store_recommendation(...)

recommendations.append({
    "recommendationId": recommendation_id,  # NOVO
    "clientId": client_id,
    "campaignId": str(campaign_id),
    "campaignName": campaign_name,
    "action": action,
    "currentCpa": current_cpa,
    "healthyCpa": healthy_cpa,
})
```

---

## Arquivos a Remover

### 9. `src/functions/optimizer/apply_recommendations.py`

Remover este arquivo após a migração, pois será substituído pelo novo `apply_recommendation.py`.

---

## Endpoints Resultantes

| Método | Path | Descrição |
|--------|------|-----------|
| POST | /optimizer | Gera recomendações (existente, modificado) |
| GET | /recommendations?clientId=X&campaignId=Y&status=Z | Lista recomendações |
| POST | /recommendations/{recommendationId}/apply | Aplica recomendação específica |

---

## Validações Implementadas

1. **Ao aplicar:**
   - Verifica se recomendação existe (404)
   - Valida clientId e campaignId correspondem (400)
   - Verifica se já foi aplicada (409)
   - Registra execução no ExecutionHistory

2. **Ao listar:**
   - clientId obrigatório
   - Suporta filtros por campaignId e status

---

## Checklist de Implementação

- [ ] Criar `sls/resources/dynamodb/recommendations-table.yml`
- [ ] Criar diretório `src/functions/recommendations/`
- [ ] Criar `src/functions/recommendations/__init__.py`
- [ ] Criar `src/functions/recommendations/list_recommendations.py`
- [ ] Criar `src/functions/recommendations/apply_recommendation.py`
- [ ] Criar `sls/functions/recommendations/interface.yml`
- [ ] Atualizar `serverless.yml` (environment, functions, resources)
- [ ] Atualizar `src/functions/optimizer/generate_recommendations.py`
- [ ] Remover bloco ApplyRecommendations de `sls/functions/optimizer/interface.yml`
- [ ] Remover `src/functions/optimizer/apply_recommendations.py`
