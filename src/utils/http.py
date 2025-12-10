"""
Utilitários para processamento de eventos HTTP e respostas padronizadas
"""
import json
from typing import Dict, Any, Optional, Tuple
from src.utils.auth import ClientAuth


def extract_api_key(event: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Extrai a API key da requisição HTTP
    
    Verifica em ordem:
    1. Header Authorization (Bearer token)
    2. Header x-api-key
    3. Query parameter apiKey
    4. Body apiKey
    
    Args:
        event: Evento HTTP do API Gateway
        body: Body já parseado (opcional)
        
    Returns:
        API key encontrada ou None
    """
    # Tentar headers primeiro
    if "headers" in event and event["headers"]:
        headers = event["headers"]
        # API Gateway pode normalizar headers para lowercase
        headers_lower = {k.lower(): v for k, v in headers.items()}
        
        # Authorization Bearer
        if "authorization" in headers_lower:
            auth_header = headers_lower["authorization"]
            if auth_header.startswith("Bearer "):
                return auth_header[7:]
        
        # x-api-key header
        if "x-api-key" in headers_lower:
            return headers_lower["x-api-key"]
    
    # Tentar query parameters
    if "queryStringParameters" in event and event["queryStringParameters"]:
        query_params = event["queryStringParameters"]
        if "apiKey" in query_params:
            return query_params["apiKey"]
    
    # Tentar body (se fornecido ou se estiver no event)
    if body and isinstance(body, dict) and "apiKey" in body:
        return body["apiKey"]
    
    if "body" in event and event["body"]:
        try:
            body_parsed = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
            if isinstance(body_parsed, dict) and "apiKey" in body_parsed:
                return body_parsed["apiKey"]
        except (json.JSONDecodeError, TypeError):
            pass
    
    return None


def validate_api_key(api_key: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Valida uma API key
    
    Args:
        api_key: API key a ser validada
        
    Returns:
        Tupla (is_valid, error_message)
        - is_valid: True se válida, False caso contrário
        - error_message: Mensagem de erro se inválida, None se válida
    """
    if not api_key:
        return False, "API key não fornecida"
    
    try:
        client_auth = ClientAuth()
        is_valid = client_auth.validate_api_key(api_key)
        
        if not is_valid:
            return False, "Cliente não autorizado"
        
        return True, None
    except Exception as e:
        return False, f"Erro ao validar API key: {str(e)}"


def parse_body(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parseia o body do evento HTTP
    
    Args:
        event: Evento HTTP do API Gateway
        
    Returns:
        Body parseado como dicionário ou None se não existir/inválido
    """
    if "body" not in event or not event["body"]:
        return None
    
    try:
        if isinstance(event["body"], str):
            return json.loads(event["body"])
        elif isinstance(event["body"], dict):
            return event["body"]
        else:
            return None
    except (json.JSONDecodeError, TypeError):
        return None


def extract_query_param(event: Dict[str, Any], param_name: str) -> Optional[str]:
    """
    Extrai um parâmetro de query string
    
    Args:
        event: Evento HTTP do API Gateway
        param_name: Nome do parâmetro
        
    Returns:
        Valor do parâmetro ou None
    """
    if "queryStringParameters" in event and event["queryStringParameters"]:
        query_params = event["queryStringParameters"]
        return query_params.get(param_name)
    return None


def extract_path_param(event: Dict[str, Any], param_name: str) -> Optional[str]:
    """
    Extrai um parâmetro do path
    
    Args:
        event: Evento HTTP do API Gateway
        param_name: Nome do parâmetro
        
    Returns:
        Valor do parâmetro ou None
    """
    if "pathParameters" in event and event["pathParameters"]:
        path_params = event["pathParameters"]
        return path_params.get(param_name)
    return None


def http_response(status_code: int, body: Any, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Cria resposta HTTP padronizada com CORS
    
    Args:
        status_code: Código de status HTTP
        body: Corpo da resposta (será convertido para JSON se for dict)
        headers: Headers adicionais (opcional)
        
    Returns:
        Resposta formatada para API Gateway
    """
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
    }
    
    if headers:
        default_headers.update(headers)
    
    # Converter body para JSON se necessário
    if isinstance(body, dict):
        body_str = json.dumps(body)
    elif isinstance(body, str):
        body_str = json.dumps({"message": body})
    else:
        body_str = json.dumps({"message": str(body)})
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': body_str
    }


def require_api_key(event: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Valida e retorna a API key da requisição, ou retorna resposta de erro
    
    Args:
        event: Evento HTTP do API Gateway
        body: Body já parseado (opcional)
        
    Returns:
        Tupla (api_key, error_response)
        - api_key: API key válida ou None
        - error_response: Resposta de erro HTTP se inválida, None se válida
    """
    api_key = extract_api_key(event, body)
    is_valid, error_message = validate_api_key(api_key)
    
    if not is_valid:
        return None, http_response(401, {"message": error_message})
    
    return api_key, None

