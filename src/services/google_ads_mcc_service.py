import os
import boto3
from typing import Dict, List, Optional, Any
from datetime import datetime
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v20.services.services.customer_client_link_service.client import CustomerClientLinkServiceClient
from google.ads.googleads.v20.services.types.customer_client_link_service import CustomerClientLinkOperation, MutateCustomerClientLinkResponse
from google.ads.googleads.v20.resources.types.customer_client_link import CustomerClientLink
from src.utils.encryption import TokenEncryption
from src.services.google_ads_config import GoogleAdsConfig


class GoogleAdsMCCService:
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.clients_table = self.dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
        self.execution_history_table = self.dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))
        self.encryption = TokenEncryption()
        self.ads_config = GoogleAdsConfig()
        self._mcc_client_cache = None
    
    def get_mcc_client(self) -> Optional[GoogleAdsClient]:
        try:
            if self._mcc_client_cache:
                return self._mcc_client_cache
            mcc_customer_id = os.environ.get('MCC_CUSTOMER_ID')
            if mcc_customer_id:
                mcc_customer_id = mcc_customer_id.replace("-", "")
            if not mcc_customer_id:
                print("MCC_CUSTOMER_ID não configurado")
                return None
            
            print(f"Criando cliente MCC para customer: {mcc_customer_id}")
            
            config = self.ads_config.get_google_ads_config(mcc_customer_id)
            
            # Criar cliente seguindo o mesmo padrão da action.py
            google_ads_client = GoogleAdsClient.load_from_dict(config, version="v20")
            self._mcc_client_cache = google_ads_client
            
            print("Cliente MCC criado com sucesso usando GoogleAdsConfig")
            return google_ads_client
            
        except Exception as e:
            print(f"Erro ao criar cliente MCC: {str(e)}")
            return None
    
    def send_link_invitation(self, client_customer_id: str, client_name: str = None) -> Dict[str, Any]:
        try:
            mcc_client = self.get_mcc_client()
            if not mcc_client:
                return {
                    'success': False,
                    'error': 'Cliente MCC não configurado'
                }            
            clean_customer_id = client_customer_id.replace('-', '')
            manager_customer_id = os.environ.get('MCC_CUSTOMER_ID')
            if manager_customer_id:
                manager_customer_id = manager_customer_id.replace("-", "")
            print(f"Enviando convite MCC do manager '{manager_customer_id}' para cliente '{clean_customer_id}'")            
            customer_client_link_service: CustomerClientLinkServiceClient = (
                mcc_client.get_service("CustomerClientLinkService")
            )
            client_link_operation: CustomerClientLinkOperation = mcc_client.get_type(
                "CustomerClientLinkOperation"
            )
            client_link: CustomerClientLink = client_link_operation.create
            client_link.client_customer = customer_client_link_service.customer_path(clean_customer_id)
            client_link.status = mcc_client.enums.ManagerLinkStatusEnum.PENDING.value
            response: MutateCustomerClientLinkResponse = (
                customer_client_link_service.mutate_customer_client_link(
                    customer_id=manager_customer_id, 
                    operation=client_link_operation
                )
            )
            resource_name = response.result.resource_name
            link_id = resource_name.split('/')[-1]
            print(f"Convite MCC enviado com sucesso!")
            print(f'Convite enviado do manager "{manager_customer_id}" para cliente "{clean_customer_id}" com resource_name "{resource_name}"')
            self._log_mcc_operation(
                operation="SEND_INVITATION",
                client_customer_id=clean_customer_id,
                client_name=client_name,
                link_id=link_id,
                status="PENDING",
                success=True
            )
            return {
                'success': True,
                'link_id': link_id,
                'resource_name': resource_name,
                'status': 'PENDING',
                'message': f'Convite enviado do MCC para cliente {clean_customer_id}',
                'manager_customer_id': manager_customer_id,
                'client_customer_id': clean_customer_id
            }
        except GoogleAdsException as ex:
            error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
            if ex.error.message:
                error_msg += f" - {ex.error.message}"
            print(f"Erro ao enviar convite MCC para {client_customer_id}: {error_msg}")
            self._log_mcc_operation(
                operation="SEND_INVITATION",
                client_customer_id=client_customer_id.replace('-', ''),
                client_name=client_name,
                status="ERROR",
                success=False,
                error=error_msg
            )
            return {
                'success': False,
                'error': error_msg
            }
            
        except Exception as e:
            error_msg = f"Erro inesperado: {str(e)}"
            print(f"Erro ao enviar convite MCC para {client_customer_id}: {error_msg}")
            self._log_mcc_operation(
                operation="SEND_INVITATION",
                client_customer_id=client_customer_id.replace('-', ''),
                client_name=client_name,
                status="ERROR",
                success=False,
                error=error_msg
            )
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_link_status(self, client_customer_id: str) -> Dict[str, Any]:
        try:
            mcc_client = self.get_mcc_client()
            if not mcc_client:
                return {
                    'found': False,
                    'error': 'Cliente MCC não configurado'
                }
            print("⚠️  FUNCIONALIDADE MCC EM DESENVOLVIMENTO")
            print(f"Simulação: Verificando status para cliente {client_customer_id}")
            if client_customer_id.endswith('0'):
                status = 'PENDING'
                found = True
            elif client_customer_id.endswith('1'):
                status = 'APPROVED'
                found = True
            elif client_customer_id.endswith('2'):
                status = 'REJECTED'
                found = True
            else:
                status = 'NOT_LINKED'
                found = False
            if found:
                link_id = f"simulated_link_{client_customer_id}"
                created_date = datetime.utcnow().isoformat()
                return {
                    'found': True,
                    'status': status,
                    'link_id': link_id,
                    'created_date': created_date,
                    'client_customer_id': client_customer_id,
                    'simulation': True,
                    'note': 'Esta é uma simulação. Para funcionalidade real, configure a versão correta da API'
                }
            else:
                return {
                    'found': False,
                    'status': 'NOT_LINKED',
                    'message': 'Nenhuma associação encontrada (simulação)',
                    'simulation': True,
                    'note': 'Esta é uma simulação. Para funcionalidade real, configure a versão correta da API'
                }
        except Exception as e:
            print(f"Erro ao verificar status MCC para {client_customer_id}: {str(e)}")
            return {
                'found': False,
                'error': str(e)
            }
  
    def cancel_link_invitation(self, client_customer_id: str) -> Dict[str, Any]:
        try:
            mcc_client = self.get_mcc_client()
            if not mcc_client:
                return {
                    'success': False,
                    'error': 'Cliente MCC não configurado'
                }
            
            print("⚠️  FUNCIONALIDADE MCC EM DESENVOLVIMENTO")
            print(f"Simulação: Cancelando convite para cliente {client_customer_id}")
            
            # Por enquanto, vamos simular o cancelamento
            # Em produção, você precisaria implementar usando a versão correta da API
            
            print(f"📤 Simulação: Convite MCC cancelado para cliente {client_customer_id}")
            
            # Registrar no histórico
            self._log_mcc_operation(
                operation="CANCEL_INVITATION",
                client_customer_id=client_customer_id,
                status="CANCELLED",
                success=True
            )
            
            return {
                'success': True,
                'message': f'Convite simulado cancelado para cliente {client_customer_id} (funcionalidade em desenvolvimento)',
                'simulation': True,
                'note': 'Esta é uma simulação. Para funcionalidade real, configure a versão correta da API'
            }
            
        except Exception as e:
            error_msg = f"Erro ao cancelar convite MCC: {str(e)}"
            print(error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _log_mcc_operation(self, operation: str, client_customer_id: str, 
                          client_name: str = None, link_id: str = None, 
                          status: str = None, success: bool = True, error: str = None):
        try:
            timestamp = datetime.utcnow().isoformat()
            
            record = {
                'traceId': f"mcc-{operation.lower()}-{client_customer_id}-{timestamp}",
                'stageTm': f"MCC_{operation}#{timestamp}",
                'stage': f"MCC_{operation}",
                'status': 'COMPLETED' if success else 'FAILED',
                'timestamp': timestamp,
                'clientId': client_customer_id,
                'googleAdsCustomerId': client_customer_id,
                'payload': {
                    'operation': operation,
                    'client_customer_id': client_customer_id,
                    'client_name': client_name,
                    'link_id': link_id,
                    'status': status,
                    'success': success,
                    'error': error
                }
            }
            
            self.execution_history_table.put_item(Item=record)
            
        except Exception as e:
            print(f"Erro ao registrar operação MCC no histórico: {str(e)}")
    
    def clear_cache(self):
        """Limpa o cache do cliente MCC"""
        self._mcc_client_cache = None
        print("Cache do cliente MCC limpo")
