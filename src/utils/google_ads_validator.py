"""
Validador para tokens do Google Ads

Este módulo valida se os tokens fornecidos pelo cliente são válidos
e podem ser usados para acessar a API do Google Ads.
"""
import logging
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class GoogleAdsTokenValidator:
    
    def __init__(self):
        pass
    
    def validate_tokens(self, google_ads_config):
        """
        Valida se os tokens do Google Ads são válidos
        
        Args:
            google_ads_config (dict): Configuração com tokens do Google Ads
                - developerId (str): ID do desenvolvedor (Customer ID)
                - clientId (str): Client ID do OAuth2
                - clientSecret (str): Client Secret do OAuth2
                - refreshToken (str): Refresh Token
                - developerToken (str): Developer Token
        
        Returns:
            dict: Resultado da validação
                - valid (bool): Se os tokens são válidos
                - error (str): Mensagem de erro se inválidos
                - customer_info (dict): Informações do cliente se válidos
        """
        try:
            # Verificar campos obrigatórios
            required_fields = ['developerId', 'clientId', 'clientSecret', 'refreshToken', 'developerToken']
            missing_fields = [field for field in required_fields if not google_ads_config.get(field)]
            
            if missing_fields:
                return {
                    'valid': False,
                    'error': f"Campos obrigatórios ausentes: {', '.join(missing_fields)}"
                }
            
            # Criar configuração temporária para testar
            config = {
                'developer_token': google_ads_config['developerToken'],
                'client_id': google_ads_config['clientId'],
                'client_secret': google_ads_config['clientSecret'],
                'refresh_token': google_ads_config['refreshToken'],
                'use_proto_plus': True
            }
            
            # Tentar criar cliente e fazer uma chamada básica
            client = GoogleAdsClient.load_from_dict(config)
            customer_id = google_ads_config['developerId']
            
            # Fazer uma chamada simples para validar o acesso
            customer_service = client.get_service("CustomerService")
            
            # Buscar informações básicas do cliente
            customer = customer_service.get_customer(customer_id=customer_id)
            
            customer_info = {
                'customer_id': customer_id,
                'currency_code': customer.currency_code,
                'time_zone': customer.time_zone,
                'descriptive_name': customer.descriptive_name if customer.descriptive_name else 'N/A'
            }
            
            logger.info(f"Tokens validados com sucesso para cliente: {customer_info['descriptive_name']}")
            
            return {
                'valid': True,
                'customer_info': customer_info
            }
            
        except GoogleAdsException as ex:
            error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
            if ex.error.message:
                error_msg += f" - {ex.error.message}"
            
            logger.error(f"Falha na validação dos tokens: {error_msg}")
            
            return {
                'valid': False,
                'error': error_msg
            }
            
        except Exception as e:
            error_msg = f"Erro na validação: {str(e)}"
            logger.error(f"Erro inesperado na validação dos tokens: {error_msg}")
            
            return {
                'valid': False,
                'error': error_msg
            }
    
    def validate_basic_format(self, google_ads_config):
        """
        Validação básica de formato dos tokens (sem chamada à API)
        
        Args:
            google_ads_config (dict): Configuração com tokens do Google Ads
        
        Returns:
            dict: Resultado da validação de formato
                - valid (bool): Se o formato está correto
                - errors (list): Lista de erros encontrados
        """
        errors = []
        
        # Verificar campos obrigatórios
        required_fields = {
            'developerId': 'ID do Desenvolvedor (Customer ID)',
            'clientId': 'Client ID',
            'clientSecret': 'Client Secret',
            'refreshToken': 'Refresh Token',
            'developerToken': 'Developer Token'
        }
        
        for field, description in required_fields.items():
            if not google_ads_config.get(field):
                errors.append(f"{description} é obrigatório")
            elif not isinstance(google_ads_config[field], str) or len(google_ads_config[field].strip()) == 0:
                errors.append(f"{description} deve ser uma string não vazia")
        
        # Validações específicas de formato
        if google_ads_config.get('developerId'):
            developer_id = google_ads_config['developerId'].replace('-', '')
            if not developer_id.isdigit() or len(developer_id) != 10:
                errors.append("ID do Desenvolvedor deve ter 10 dígitos (formato: 1234567890)")
        
        if google_ads_config.get('clientId'):
            if not google_ads_config['clientId'].endswith('.apps.googleusercontent.com'):
                errors.append("Client ID deve terminar com '.apps.googleusercontent.com'")
        
        if google_ads_config.get('developerToken'):
            if len(google_ads_config['developerToken']) < 20:
                errors.append("Developer Token parece ser muito curto")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        } 