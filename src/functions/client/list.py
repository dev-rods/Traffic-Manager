import json
from src.utils.auth import ClientAuth
from src.services.client_service import ClientService


def handler(event, context):
    """
    Handler para listagem de clientes via API
    
    Query Parameters opcionais:
    - activeOnly: true/false - Se true, lista apenas clientes ativos (padrão: false)
    """
    try:
        print(f"Requisição recebida para listagem de clientes: {json.dumps(event)}")
        
        # Validar API key
        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event.get("body", {})
        api_key = get_api_key(event, body)
        if not api_key:
            print("API key não fornecida na requisição")
            return response(401, {"message": "API key não fornecida"})
        
        client_auth = ClientAuth()
        valid_api_key = client_auth.validate_api_key(api_key)
        if not valid_api_key:
            print(f"API key inválida: {api_key}")
            return response(401, {"message": "Cliente não autorizado"})
        
        # Obter parâmetro activeOnly dos query parameters
        query_params = event.get("queryStringParameters") or {}
        active_only = False
        if query_params and "activeOnly" in query_params:
            active_only = query_params["activeOnly"].lower() in ("true", "1", "yes")
        
        # Listar clientes
        client_service = ClientService()
        result = client_service.list_clients(active_only=active_only)
        
        return response(200, result)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Erro no processamento da listagem de clientes: {error_msg}")
        return response(500, {"message": "Erro interno no servidor", "error": error_msg})


def get_api_key(event, body):
    """
    Extrai a API key da requisição
    Verifica headers (Authorization Bearer ou x-api-key) e query parameters
    """
    if "headers" in event and event["headers"]:
        headers = event["headers"]
        if "Authorization" in headers:
            auth_header = headers["Authorization"]
            if auth_header.startswith("Bearer "):
                return auth_header[7:]
        if "x-api-key" in headers:
            return headers["x-api-key"]
    
    if "queryStringParameters" in event and event["queryStringParameters"]:
        query_params = event["queryStringParameters"]
        if "apiKey" in query_params:
            return query_params["apiKey"]
    
    if body and isinstance(body, dict):
        if "apiKey" in body:
            return body["apiKey"]
    
    return None


def response(status_code, body):
    """
    Cria resposta HTTP padronizada
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True
        },
        'body': json.dumps(body) if isinstance(body, dict) else json.dumps({"message": body})
    }
