import json
from src.utils.auth import ClientAuth
from src.services.client_service import ClientService
from src.services.google_ads_mcc_service import GoogleAdsMCCService
from datetime import datetime


def handler(event, context):
    """
    Handler para criação de clientes via API
    
    Body esperado:
    {
        "companyName": "Nome da Empresa",
        "googleAdsCustomerId": "123-456-7890",
        "email": "email@exemplo.com" (opcional),
        "sendMccInvitation": true (opcional, padrão: false)
    }
    """
    try:
        print(f"Requisição recebida para criação de cliente: {json.dumps(event)}")
        
        if "body" not in event or not event["body"]:
            return response(400, {"message": "Corpo da requisição vazio ou inválido"})
        
        body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        
        # Validar API key
        api_key = get_api_key(event, body)
        if not api_key:
            print("API key não fornecida na requisição")
            return response(401, {"message": "API key não fornecida"})
        
        client_auth = ClientAuth()
        valid_api_key = client_auth.validate_api_key(api_key)
        if not valid_api_key:
            print(f"API key inválida: {api_key}")
            return response(401, {"message": "Cliente não autorizado"})
                
        # Criar ou obter cliente
        client_service = ClientService()
        client = client_service.create_or_get_client(body=body, source='api')
        
        if not client:
            return response(500, {"message": "Erro ao criar/obter cliente"})
        
        client_id = client['clientId']
        
        print(f"Cliente processado: {client_id} ({client['name']})")
        
        # Enviar convite MCC se solicitado
        company_name = client['name']
        google_ads_customer_id = client['googleAdsCustomerId']
        send_mcc_invitation = client['mccStatus'] == 'NOT_LINKED'
        mcc_result = None
        if send_mcc_invitation:
            print(f"Enviando convite MCC para cliente {google_ads_customer_id}...")
            try:
                mcc_service = GoogleAdsMCCService()
                mcc_result = mcc_service.send_link_invitation(google_ads_customer_id, company_name)
                if mcc_result['success']:
                    print(f"✅ Convite MCC enviado com sucesso!")
                    print(f"   Link ID: {mcc_result['link_id']}")
                    print(f"   Status: {mcc_result['status']}")
                    
                    # Atualizar status MCC no cliente
                    client_service.update_client(client_id, {
                        'mccStatus': mcc_result['status'],
                        'mccLinkId': mcc_result['link_id'],
                        'mccInvitationSentAt': datetime.utcnow().isoformat()
                    })
                    client['mccStatus'] = mcc_result['status']
                    client['mccLinkId'] = mcc_result['link_id']
                else:
                    print(f"⚠️  Erro ao enviar convite MCC: {mcc_result['error']}")
                    client_service.update_client(client_id, {
                        'mccStatus': 'ERROR',
                        'mccError': mcc_result['error']
                    })
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️  Erro inesperado ao enviar convite MCC: {error_msg}")
                mcc_result = {
                    'success': False,
                    'error': error_msg
                }
        
        # Preparar resposta
        response_data = {
            "message": "Cliente criado/obtido com sucesso",
            "clientId": client_id,
            "name": client['name'],
            "email": client.get('email', ''),
            "googleAdsCustomerId": client.get('googleAdsCustomerId'),
            "mccStatus": client.get('mccStatus', 'NOT_LINKED'),
            "active": client.get('active', True),
            "createdAt": client.get('createdAt')
        }
        
        if mcc_result:
            response_data["mccInvitation"] = mcc_result
        
        return response(200, response_data)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Erro no processamento da criação de cliente: {error_msg}")
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
