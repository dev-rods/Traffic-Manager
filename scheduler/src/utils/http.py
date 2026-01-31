import json
from typing import Dict, Any, Optional, Tuple
from src.utils.auth import SchedulerAuth
from src.utils.decimal_utils import convert_decimal_to_json_serializable


def extract_api_key(event: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if "headers" in event and event["headers"]:
        headers = event["headers"]
        headers_lower = {k.lower(): v for k, v in headers.items()}

        if "authorization" in headers_lower:
            auth_header = headers_lower["authorization"]
            if auth_header.startswith("Bearer "):
                return auth_header[7:]

        if "x-api-key" in headers_lower:
            return headers_lower["x-api-key"]

    if "queryStringParameters" in event and event["queryStringParameters"]:
        query_params = event["queryStringParameters"]
        if "apiKey" in query_params:
            return query_params["apiKey"]

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
    if not api_key:
        return False, "API key não fornecida"

    try:
        auth = SchedulerAuth()
        is_valid = auth.validate_api_key(api_key)

        if not is_valid:
            return False, "Não autorizado"

        return True, None
    except Exception as e:
        return False, f"Erro ao validar API key: {str(e)}"


def parse_body(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
    if "queryStringParameters" in event and event["queryStringParameters"]:
        return event["queryStringParameters"].get(param_name)
    return None


def extract_path_param(event: Dict[str, Any], param_name: str) -> Optional[str]:
    if "pathParameters" in event and event["pathParameters"]:
        return event["pathParameters"].get(param_name)
    return None


def http_response(status_code: int, body: Any, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
    }

    if headers:
        default_headers.update(headers)

    if isinstance(body, dict):
        body_serializable = convert_decimal_to_json_serializable(body)
        body_str = json.dumps(body_serializable)
    elif isinstance(body, str):
        body_str = json.dumps({"message": body})
    else:
        body_serializable = convert_decimal_to_json_serializable(body)
        body_str = json.dumps({"message": str(body_serializable)})

    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': body_str
    }


def require_api_key(event: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    api_key = extract_api_key(event, body)
    is_valid, error_message = validate_api_key(api_key)

    if not is_valid:
        return None, http_response(401, {"status": "ERROR", "message": error_message})

    return api_key, None
