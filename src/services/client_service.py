"""
Serviço para gerenciamento de clientes no DynamoDB
"""
import os
import boto3
import hashlib
from datetime import datetime
from typing import Dict, Optional, Any, List


DEFAULT_OPTIMIZATION_CONFIG = {
    # Valores padrão baseados no racional fornecido
    # Ticket médio (R$)
    "average_ticket": 270.0,
    # LTV em meses
    "ltv_months": 6.0,
    # Margem líquida (0–1)
    "net_margin": 0.60,
    # Taxa de conversão de lead em venda (0–1)
    "lead_to_sale_conversion_rate": 0.20,
    # Fator de segurança (0–1)
    "safety_factor": 0.70,
}


def build_optimization_config_from_payload(payload: Dict[str, Any]) -> Dict[str, float]:
    """
    Constrói um bloco de configuração de otimização a partir de um payload
    (body da API ou formData), aplicando defaults quando necessário.
    """
    def _get_num(keys: List[str], default: float) -> float:
        for key in keys:
            if key in payload and payload[key] not in (None, ""):
                try:
                    return float(payload[key])
                except (TypeError, ValueError):
                    continue
        return default

    cfg = {
        "average_ticket": _get_num(
            ["average_ticket", "averageTicket", "ticket_medio"], DEFAULT_OPTIMIZATION_CONFIG["average_ticket"]
        ),
        "ltv_months": _get_num(
            ["ltv_months", "ltvMonths", "ltv"], DEFAULT_OPTIMIZATION_CONFIG["ltv_months"]
        ),
        "net_margin": _get_num(
            ["net_margin", "netMargin", "margem_liquida"], DEFAULT_OPTIMIZATION_CONFIG["net_margin"]
        ),
        "lead_to_sale_conversion_rate": _get_num(
            [
                "lead_to_sale_conversion_rate",
                "leadToSaleConversionRate",
                "taxa_conversao_lead",
            ],
            DEFAULT_OPTIMIZATION_CONFIG["lead_to_sale_conversion_rate"],
        ),
        "safety_factor": _get_num(
            ["safety_factor", "safetyFactor", "fator_seguranca"],
            DEFAULT_OPTIMIZATION_CONFIG["safety_factor"],
        ),
    }

    # Receita líquida = Ticket médio x LTV x Margem líquida
    revenue = cfg["average_ticket"] * cfg["ltv_months"] * cfg["net_margin"]
    # CPA máximo = Receita líquida x Taxa de conversão lead→venda
    cpa_max = revenue * cfg["lead_to_sale_conversion_rate"]
    # CPA saudável = CPA máximo x Fator de segurança
    healthy_cpa = cpa_max * cfg["safety_factor"]

    cfg["healthy_cpa"] = healthy_cpa
    return cfg


class ClientService:
    """Serviço para criar e gerenciar clientes"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.clients_table = self.dynamodb.Table(os.environ.get('CLIENTS_TABLE'))
    
    def generate_client_id(self, company_name: str) -> str:
        """
        Gera um ID do cliente baseado no nome da empresa
        
        Args:
            company_name (str): Nome da empresa
            
        Returns:
            str: ID gerado no formato {base}-{hash}
        """
        base = "".join(e for e in company_name if e.isalnum()).lower()
        hash_suffix = hashlib.md5(company_name.encode()).hexdigest()[:6]
        return f"{base}-{hash_suffix}"
    
    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca um cliente pelo ID
        
        Args:
            client_id (str): ID do cliente
            
        Returns:
            Optional[Dict]: Dados do cliente ou None se não encontrado
        """
        try:
            response = self.clients_table.get_item(Key={'clientId': client_id})
            if 'Item' in response:
                return response['Item']
            return None
        except Exception as e:
            print(f"Erro ao buscar cliente {client_id}: {str(e)}")
            return None
    
    def create_or_get_client(self, body: Dict[str, Any], source: str = 'api', form_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        company_name = body.get('companyName') or body.get('company_name')
        google_ads_customer_id = body.get('googleAdsCustomerId') or body.get('google_ads_customer_id')
        email = body.get('email', '')
        try:
            if not company_name:
                print("Nome da empresa não fornecido")
                return None
            
            if not google_ads_customer_id:
                print("Google Ads Customer ID não fornecido")
                return None

            google_ads_customer_id = google_ads_customer_id.replace('-', '')
            client_id = self.generate_client_id(company_name)
            
            # Verificar se cliente já existe
            existing_client = self.get_client(client_id)
            if existing_client:
                print(f"Cliente existente encontrado: {client_id}")
                
                # Atualizar Google Ads Customer ID se não estiver configurado
                if not existing_client.get('googleAdsCustomerId'):
                    self.clients_table.update_item(
                        Key={'clientId': client_id},
                        UpdateExpression="SET googleAdsCustomerId = :customer_id",
                        ExpressionAttributeValues={':customer_id': google_ads_customer_id}
                    )
                    existing_client['googleAdsCustomerId'] = google_ads_customer_id
                
                return existing_client
            
            # Criar novo cliente
            client_data = {
                'clientId': client_id,
                'name': company_name,
                'email': email,
                'active': True,
                'createdAt': datetime.utcnow().isoformat(),
                'source': source,
                'googleAdsCustomerId': google_ads_customer_id,
                'mccStatus': 'NOT_LINKED'
            }
            
            # Adicionar dados do formulário se fornecidos
            if form_data:
                client_data['formData'] = {
                    'business_niche': form_data.get('business_niche', ''),
                    'industry': form_data.get('industry', ''),
                    'address': form_data.get('address', ''),
                    'objectives': form_data.get('objectives', ''),
                    'budget': form_data.get('budget', ''),
                    'target_audience': form_data.get('target_audience', ''),
                    'competitive_advantage': form_data.get('competitive_advantage', ''),
                    'customer_benefit': form_data.get('customer_benefit', ''),
                    'customer_desires': form_data.get('customer_desires', ''),
                    'customer_pains': form_data.get('customer_pains', ''),
                    'cost_per_result': form_data.get('cost_per_result', ''),
                    'average_ticket': form_data.get('average_ticket', ''),
                    'brand_perception': form_data.get('brand_perception', ''),
                    'customer_behavior': form_data.get('customer_behavior', '')
                }

                # Se houver dados econômicos no formulário, usar como base
                optimization_source = {**body, **form_data}
            else:
                optimization_source = body

            # Bloco de configuração econômica por cliente para otimizações
            optimization_config = build_optimization_config_from_payload(optimization_source or {})
            client_data["optimizationConfig"] = optimization_config
            
            self.clients_table.put_item(Item=client_data)
            print(f"Novo cliente criado: {client_id} ({company_name}) com Google Ads ID: {google_ads_customer_id}")
            
            return client_data
            
        except Exception as e:
            print(f"Erro ao criar/obter cliente: {str(e)}")
            return None
    
    def update_client(self, client_id: str, updates: Dict[str, Any]) -> bool:
        try:
            update_expression_parts = []
            expression_attribute_values = {}
            
            for key, value in updates.items():
                update_expression_parts.append(f"{key} = :{key}")
                expression_attribute_values[f":{key}"] = value
            
            if not update_expression_parts:
                return False
            
            update_expression = "SET " + ", ".join(update_expression_parts)
            
            self.clients_table.update_item(
                Key={'clientId': client_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values
            )
            
            print(f"Cliente {client_id} atualizado com sucesso")
            return True
            
        except Exception as e:
            print(f"Erro ao atualizar cliente {client_id}: {str(e)}")
            return False
    
    def list_clients(self, active_only: bool = False) -> Dict[str, Any]:
        try:
            response = self.clients_table.scan()
            clients = response.get("Items", [])
            
            if active_only:
                clients = [client for client in clients if client.get("active", False)]
            
            clients_safe = []
            for client in clients:
                client_safe = {k: v for k, v in client.items() if k != "apiKey"}
                clients_safe.append(client_safe)
                        
            return {
                "clients": clients_safe
            }
        except Exception as e:
            print(f"Erro ao listar clientes: {str(e)}")
            return {
                "clients": []
            }
