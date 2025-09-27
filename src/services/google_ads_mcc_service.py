"""
Serviço para gerenciar associações de contas do Google Ads ao MCC (My Client Center)

Este serviço permite enviar convites de associação e monitorar o status
das associações entre contas de clientes e a conta MCC.

Baseado no exemplo oficial do Google Ads: link_manager_to_client
"""

import os
import sys
import boto3
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# Imports baseados no exemplo oficial v20
from google.ads.googleads.v20.services.services.customer_client_link_service.client import (
    CustomerClientLinkServiceClient,
)
from google.ads.googleads.v20.services.types.customer_client_link_service import (
    CustomerClientLinkOperation,
    MutateCustomerClientLinkResponse,
)
from google.ads.googleads.v20.resources.types.customer_client_link import (
    CustomerClientLink,
)
from google.ads.googleads.v20.services.services.google_ads_service.client import (
    GoogleAdsServiceClient,
)
from google.ads.googleads.v20.services.types.google_ads_service import (
    SearchGoogleAdsResponse,
)

try:
    from src.utils.encryption import TokenEncryption
    from src.services.google_ads_config import GoogleAdsConfig
except ImportError:
    # Para execução direta, usar import relativo
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from utils.encryption import TokenEncryption
    from services.google_ads_config import GoogleAdsConfig

# Configurar logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

class GoogleAdsMCCService:
    """
    Serviço para gerenciar associações MCC do Google Ads
    
    Funcionalidades:
    - Enviar convites de associação para contas de clientes
    - Monitorar status das associações
    - Listar associações existentes
    - Cancelar associações pendentes
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.clients_table = self.dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
        self.execution_history_table = self.dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))
        self.encryption = TokenEncryption()
        self.ads_config = GoogleAdsConfig()
        self._mcc_client_cache = None
    
    def get_mcc_client(self) -> Optional[GoogleAdsClient]:
        """
        Obtém cliente autenticado para a conta MCC
        Usando a mesma abordagem da action.py com GoogleAdsConfig
        
        Returns:
            GoogleAdsClient: Cliente autenticado para MCC ou None se erro
        """
        try:
            if self._mcc_client_cache:
                return self._mcc_client_cache
            
            # Obter ID da conta MCC
            mcc_customer_id = os.environ.get('MCC_CUSTOMER_ID')
            if mcc_customer_id:
                mcc_customer_id = mcc_customer_id.replace("-", "")
            if not mcc_customer_id:
                logger.error("MCC_CUSTOMER_ID não configurado")
                return None
            
            logger.info(f"Criando cliente MCC para customer: {mcc_customer_id}")
            
            # Usar a mesma classe GoogleAdsConfig da action.py
            config = self.ads_config.get_google_ads_config(mcc_customer_id)
            
            # Criar cliente seguindo o mesmo padrão da action.py
            google_ads_client = GoogleAdsClient.load_from_dict(config, version="v20")
            self._mcc_client_cache = google_ads_client
            
            logger.info("Cliente MCC criado com sucesso usando GoogleAdsConfig")
            return google_ads_client
            
        except Exception as e:
            logger.error(f"Erro ao criar cliente MCC: {str(e)}")
            return None
    
    def send_link_invitation(self, client_customer_id: str, client_name: str = None) -> Dict[str, Any]:
        """
        Envia convite de associação para uma conta de cliente
        Baseado no exemplo oficial: link_manager_to_client
        
        Args:
            client_customer_id (str): ID da conta do cliente (formato: 910-014-2796)
            client_name (str, opcional): Nome do cliente para referência
            
        Returns:
            dict: Resultado da operação
                - success (bool): Se o convite foi enviado com sucesso
                - link_id (str): ID do link criado
                - status (str): Status atual do link
                - error (str): Mensagem de erro se houver
        """
        try:
            mcc_client = self.get_mcc_client()
            if not mcc_client:
                return {
                    'success': False,
                    'error': 'Cliente MCC não configurado'
                }
            
            # Remover hífens do customer_id se existirem (910-014-2796 -> 9100142796)
            clean_customer_id = client_customer_id.replace('-', '')
            manager_customer_id = os.environ.get('MCC_CUSTOMER_ID')
            if manager_customer_id:
                manager_customer_id = manager_customer_id.replace("-", "")
            
            logger.info(f"Enviando convite MCC do manager '{manager_customer_id}' para cliente '{clean_customer_id}'")
            
            # Obter serviço de CustomerClientLink (baseado no exemplo oficial v20)
            customer_client_link_service: CustomerClientLinkServiceClient = (
                mcc_client.get_service("CustomerClientLinkService")
            )
            
            # Criar operação de link seguindo exatamente o padrão do exemplo oficial
            client_link_operation: CustomerClientLinkOperation = mcc_client.get_type(
                "CustomerClientLinkOperation"
            )
            client_link: CustomerClientLink = client_link_operation.create
            client_link.client_customer = customer_client_link_service.customer_path(clean_customer_id)
            # client_link.status espera um valor enum (int) - PENDING
            client_link.status = mcc_client.enums.ManagerLinkStatusEnum.PENDING.value
            
            # Executar mutação (baseado no exemplo oficial)
            response: MutateCustomerClientLinkResponse = (
                customer_client_link_service.mutate_customer_client_link(
                    customer_id=manager_customer_id, 
                    operation=client_link_operation
                )
            )
            
            # Extrair resultado (campo 'result' na v20, não 'results')
            print(response)
            print(response.result)
            print(response.result.resource_name)
            resource_name = response.result.resource_name
            link_id = resource_name.split('/')[-1]
            
            logger.info(f"Convite MCC enviado com sucesso!")
            logger.info(f'Convite enviado do manager "{manager_customer_id}" para cliente "{clean_customer_id}" com resource_name "{resource_name}"')
            
            # Registrar no histórico
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
            
            logger.error(f"Erro ao enviar convite MCC para {client_customer_id}: {error_msg}")
            
            # Registrar erro no histórico
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
            logger.error(f"Erro ao enviar convite MCC para {client_customer_id}: {error_msg}")
            
            # Registrar erro no histórico
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
        """
        Verifica o status de uma associação MCC
        
        Args:
            client_customer_id (str): ID da conta do cliente
            
        Returns:
            dict: Status da associação
                - found (bool): Se o link foi encontrado
                - status (str): Status atual (PENDING, APPROVED, REJECTED, etc.)
                - link_id (str): ID do link
                - created_date (str): Data de criação
                - error (str): Mensagem de erro se houver
        """
        try:
            mcc_client = self.get_mcc_client()
            if not mcc_client:
                return {
                    'found': False,
                    'error': 'Cliente MCC não configurado'
                }
            
            logger.warning("⚠️  FUNCIONALIDADE MCC EM DESENVOLVIMENTO")
            logger.info(f"Simulação: Verificando status para cliente {client_customer_id}")
            
            # Por enquanto, vamos simular a verificação de status
            # Em produção, você precisaria implementar usando a versão correta da API
            
            # Simular diferentes status baseado no ID do cliente
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
            logger.error(f"Erro ao verificar status MCC para {client_customer_id}: {str(e)}")
            return {
                'found': False,
                'error': str(e)
            }
    
    def list_all_links(self) -> List[Dict[str, Any]]:
        """
        Lista todas as associações MCC existentes
        
        Returns:
            list: Lista de associações com seus status
        """
        try:
            mcc_client = self.get_mcc_client()
            if not mcc_client:
                return []
            
            logger.warning("⚠️  FUNCIONALIDADE MCC EM DESENVOLVIMENTO")
            logger.info("Simulação: Listando associações MCC")
            
            # Por enquanto, vamos simular uma lista de associações
            # Em produção, você precisaria implementar usando a versão correta da API
            
            simulated_links = [
                {
                    'link_id': 'simulated_link_1234567890',
                    'status': 'PENDING',
                    'client_customer_id': '1234567890',
                    'created_date': datetime.utcnow().isoformat()
                },
                {
                    'link_id': 'simulated_link_1234567891',
                    'status': 'APPROVED',
                    'client_customer_id': '1234567891',
                    'created_date': datetime.utcnow().isoformat()
                },
                {
                    'link_id': 'simulated_link_1234567892',
                    'status': 'REJECTED',
                    'client_customer_id': '1234567892',
                    'created_date': datetime.utcnow().isoformat()
                }
            ]
            
            logger.info(f"Simulação: Encontradas {len(simulated_links)} associações MCC")
            return simulated_links
            
        except Exception as e:
            logger.error(f"Erro ao listar associações MCC: {str(e)}")
            return []
    
    def cancel_link_invitation(self, client_customer_id: str) -> Dict[str, Any]:
        """
        Cancela um convite de associação pendente
        
        Args:
            client_customer_id (str): ID da conta do cliente
            
        Returns:
            dict: Resultado da operação
        """
        try:
            mcc_client = self.get_mcc_client()
            if not mcc_client:
                return {
                    'success': False,
                    'error': 'Cliente MCC não configurado'
                }
            
            logger.warning("⚠️  FUNCIONALIDADE MCC EM DESENVOLVIMENTO")
            logger.info(f"Simulação: Cancelando convite para cliente {client_customer_id}")
            
            # Por enquanto, vamos simular o cancelamento
            # Em produção, você precisaria implementar usando a versão correta da API
            
            logger.info(f"📤 Simulação: Convite MCC cancelado para cliente {client_customer_id}")
            
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
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _log_mcc_operation(self, operation: str, client_customer_id: str, 
                          client_name: str = None, link_id: str = None, 
                          status: str = None, success: bool = True, error: str = None):
        """
        Registra operações MCC no histórico de execução
        
        Args:
            operation (str): Tipo de operação (SEND_INVITATION, CANCEL_INVITATION, etc.)
            client_customer_id (str): ID da conta do cliente
            client_name (str, opcional): Nome do cliente
            link_id (str, opcional): ID do link
            status (str, opcional): Status da operação
            success (bool): Se a operação foi bem-sucedida
            error (str, opcional): Mensagem de erro
        """
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
            logger.error(f"Erro ao registrar operação MCC no histórico: {str(e)}")
    
    def clear_cache(self):
        """Limpa o cache do cliente MCC"""
        self._mcc_client_cache = None
        logger.info("Cache do cliente MCC limpo")
