"""
Serviço para gerenciar clientes do Google Ads

Este serviço cria e gerencia clientes autenticados do Google Ads
baseado nos tokens específicos de cada cliente.
"""
import os
import sys
import boto3
import logging
from typing import Dict, List, Optional, Tuple, Any
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from src.utils.encryption import TokenEncryption

# Configurar logging seguindo a documentação do Google Ads
logger = logging.getLogger('google.ads.googleads.client')
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

class GoogleAdsClientService:
    """
    Serviço para interagir com a API do Google Ads
    
    Fornece métodos para autenticação, busca de dados e execução de operações
    seguindo as melhores práticas da documentação oficial do Google Ads.
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.clients_table = self.dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
        self.encryption = TokenEncryption()
        self._client_cache = {}
    
    def get_client_for_customer(self, client_id: str) -> Tuple[Optional[GoogleAdsClient], Optional[str]]:
        """
        Obtém um cliente autenticado do Google Ads para um cliente específico
        
        Args:
            client_id (str): ID do cliente no sistema
            
        Returns:
            tuple: (GoogleAdsClient, customer_id) ou (None, None) se não configurado
        """
        try:
            # Verificar cache primeiro
            if client_id in self._client_cache:
                return self._client_cache[client_id]
            
            # Buscar dados do cliente
            response = self.clients_table.get_item(Key={"clientId": client_id})
            
            if "Item" not in response:
                logger.error(f"Cliente não encontrado: {client_id}")
                return None, None
            
            client_data = response["Item"]
            
            # Verificar se tem configuração do Google Ads
            if "googleAdsConfig" not in client_data:
                logger.warning(f"Cliente {client_id} não tem configuração do Google Ads")
                return None, None
            
            # Descriptografar configuração
            encrypted_config = client_data["googleAdsConfig"]
            config = self.encryption.decrypt_google_ads_config(encrypted_config)
            
            # Criar cliente do Google Ads seguindo a documentação
            google_ads_config = {
                'developer_token': config['developerToken'],
                'client_id': config['clientId'],
                'client_secret': config['clientSecret'],
                'refresh_token': config['refreshToken'],
                'use_proto_plus': True,
                'login_customer_id': config.get('loginCustomerId')  # Opcional
            }
            
            google_ads_client = GoogleAdsClient.load_from_dict(google_ads_config)
            customer_id = config['developerId']
            
            # Armazenar no cache
            self._client_cache[client_id] = (google_ads_client, customer_id)
            
            logger.info(f"Cliente Google Ads criado com sucesso para {client_id}")
            return google_ads_client, customer_id
            
        except Exception as e:
            logger.error(f"Erro ao criar cliente Google Ads para {client_id}: {str(e)}")
            return None, None
    
    def validate_client_access(self, client_id: str) -> Dict[str, Any]:
        """
        Valida se o cliente tem acesso válido ao Google Ads
        
        Args:
            client_id (str): ID do cliente no sistema
            
        Returns:
            dict: Resultado da validação
                - valid (bool): Se o acesso é válido
                - error (str): Mensagem de erro se inválido
                - customer_info (dict): Informações do cliente se válido
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)
            
            if not google_ads_client:
                return {
                    'valid': False,
                    'error': 'Cliente não configurado para Google Ads'
                }
            
            # Fazer uma chamada simples para validar o acesso
            customer_service = google_ads_client.get_service("CustomerService")
            customer = customer_service.get_customer(customer_id=customer_id)
            
            customer_info = {
                'customer_id': customer_id,
                'currency_code': customer.currency_code,
                'time_zone': customer.time_zone,
                'descriptive_name': customer.descriptive_name if customer.descriptive_name else 'N/A'
            }
            
            return {
                'valid': True,
                'customer_info': customer_info
            }
            
        except GoogleAdsException as ex:
            error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
            if ex.error.message:
                error_msg += f" - {ex.error.message}"
            
            return {
                'valid': False,
                'error': error_msg
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Erro na validação: {str(e)}"
            }
    
    def get_campaigns(self, client_id: str, limit: int = 50, include_metrics: bool = True) -> List[Dict[str, Any]]:
        """
        Obtém campanhas do cliente no Google Ads seguindo a documentação oficial
        
        Args:
            client_id (str): ID do cliente no sistema
            limit (int): Limite de campanhas a retornar
            include_metrics (bool): Se deve incluir métricas nas campanhas
            
        Returns:
            list: Lista de campanhas ou lista vazia se erro
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)
            
            if not google_ads_client:
                logger.error(f"Cliente {client_id} não configurado para Google Ads")
                return []
            
            # Buscar campanhas usando GoogleAdsService seguindo a documentação
            ga_service = google_ads_client.get_service("GoogleAdsService")
            
            # Query base sempre incluindo campos essenciais
            base_fields = """
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                campaign.advertising_channel_sub_type,
                campaign.start_date,
                campaign.end_date,
                campaign_budget.amount_micros
            """
            
            # Adicionar métricas se solicitado
            metrics_fields = ""
            if include_metrics:
                metrics_fields = """,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.ctr,
                    metrics.average_cpc
                """
            
            query = f"""
                SELECT 
                    {base_fields}{metrics_fields}
                FROM campaign 
                WHERE campaign.status != 'REMOVED'
                ORDER BY campaign.id
                LIMIT {limit}
            """
            
            logger.info(f"Executando query para campanhas do cliente {client_id}")
            
            # Usar search_stream para otimizar performance conforme documentação
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            
            campaigns = []
            for batch in stream:
                for row in batch.results:
                    campaign_data = {
                        'id': row.campaign.id,
                        'name': row.campaign.name,
                        'status': row.campaign.status.name,
                        'type': row.campaign.advertising_channel_type.name,
                        'sub_type': row.campaign.advertising_channel_sub_type.name if row.campaign.advertising_channel_sub_type else None,
                        'start_date': row.campaign.start_date if row.campaign.start_date else None,
                        'end_date': row.campaign.end_date if row.campaign.end_date else None,
                        'budget_micros': row.campaign_budget.amount_micros if hasattr(row, 'campaign_budget') else None
                    }
                    
                    # Adicionar métricas se incluídas
                    if include_metrics and hasattr(row, 'metrics'):
                        campaign_data['metrics'] = {
                            'impressions': row.metrics.impressions,
                            'clicks': row.metrics.clicks,
                            'cost': row.metrics.cost_micros / 1000000,  # Converter de micros para unidade
                            'conversions': row.metrics.conversions,
                            'ctr': round(row.metrics.ctr * 100, 2),  # Converter para porcentagem
                            'average_cpc': row.metrics.average_cpc / 1000000 if row.metrics.average_cpc else 0
                        }
                    
                    campaigns.append(campaign_data)
            
            logger.info(f"Encontradas {len(campaigns)} campanhas para cliente {client_id}")
            return campaigns
            
        except GoogleAdsException as ex:
            logger.error(f"Erro da API do Google Ads ao buscar campanhas para cliente {client_id}: {ex.error.code().name}")
            return []
            
        except Exception as e:
            logger.error(f"Erro ao buscar campanhas para cliente {client_id}: {str(e)}")
            return []
    
    def get_ad_groups(self, client_id: str, campaign_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtém grupos de anúncios do cliente
        
        Args:
            client_id (str): ID do cliente no sistema
            campaign_id (str, opcional): ID da campanha específica
            limit (int): Limite de grupos a retornar
            
        Returns:
            list: Lista de grupos de anúncios
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)
            
            if not google_ads_client:
                logger.error(f"Cliente {client_id} não configurado para Google Ads")
                return []
            
            ga_service = google_ads_client.get_service("GoogleAdsService")
            
            # Construir query com filtro opcional de campanha
            where_clause = "WHERE ad_group.status != 'REMOVED'"
            if campaign_id:
                where_clause += f" AND campaign.id = {campaign_id}"
            
            query = f"""
                SELECT 
                    ad_group.id,
                    ad_group.name,
                    ad_group.status,
                    ad_group.type,
                    ad_group.cpc_bid_micros,
                    campaign.id,
                    campaign.name
                FROM ad_group 
                {where_clause}
                ORDER BY ad_group.id
                LIMIT {limit}
            """
            
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            
            ad_groups = []
            for batch in stream:
                for row in batch.results:
                    ad_group_data = {
                        'id': row.ad_group.id,
                        'name': row.ad_group.name,
                        'status': row.ad_group.status.name,
                        'type': row.ad_group.type_.name,
                        'cpc_bid_micros': row.ad_group.cpc_bid_micros,
                        'campaign': {
                            'id': row.campaign.id,
                            'name': row.campaign.name
                        }
                    }
                    ad_groups.append(ad_group_data)
            
            logger.info(f"Encontrados {len(ad_groups)} grupos de anúncios para cliente {client_id}")
            return ad_groups
            
        except Exception as e:
            logger.error(f"Erro ao buscar grupos de anúncios para cliente {client_id}: {str(e)}")
            return []
    
    def get_keywords(self, client_id: str, ad_group_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Obtém palavras-chave do cliente

        Args:
            client_id (str): ID do cliente no sistema
            ad_group_id (str, opcional): ID do grupo de anúncios específico
            limit (int): Limite de palavras-chave a retornar

        Returns:
            list: Lista de palavras-chave
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)

            if not google_ads_client:
                logger.error(f"Cliente {client_id} não configurado para Google Ads")
                return []

            ga_service = google_ads_client.get_service("GoogleAdsService")

            # Construir query com filtro opcional de grupo de anúncios
            where_clause = "WHERE ad_group_criterion.status != 'REMOVED' AND ad_group_criterion.type = 'KEYWORD'"
            if ad_group_id:
                where_clause += f" AND ad_group.id = {ad_group_id}"

            query = f"""
                SELECT
                    ad_group_criterion.criterion_id,
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    ad_group_criterion.status,
                    ad_group_criterion.cpc_bid_micros,
                    ad_group.id,
                    ad_group.name,
                    campaign.id,
                    campaign.name,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros
                FROM keyword_view
                {where_clause}
                ORDER BY ad_group_criterion.criterion_id
                LIMIT {limit}
            """

            stream = ga_service.search_stream(customer_id=customer_id, query=query)

            keywords = []
            for batch in stream:
                for row in batch.results:
                    keyword_data = {
                        'id': row.ad_group_criterion.criterion_id,
                        'text': row.ad_group_criterion.keyword.text,
                        'match_type': row.ad_group_criterion.keyword.match_type.name,
                        'status': row.ad_group_criterion.status.name,
                        'cpc_bid_micros': row.ad_group_criterion.cpc_bid_micros,
                        'ad_group': {
                            'id': row.ad_group.id,
                            'name': row.ad_group.name
                        },
                        'campaign': {
                            'id': row.campaign.id,
                            'name': row.campaign.name
                        }
                    }

                    # Adicionar métricas se disponíveis
                    if hasattr(row, 'metrics'):
                        keyword_data['metrics'] = {
                            'impressions': row.metrics.impressions,
                            'clicks': row.metrics.clicks,
                            'cost': row.metrics.cost_micros / 1000000
                        }

                    keywords.append(keyword_data)

            logger.info(f"Encontradas {len(keywords)} palavras-chave para cliente {client_id}")
            return keywords

        except Exception as e:
            logger.error(f"Erro ao buscar palavras-chave para cliente {client_id}: {str(e)}")
            return []

    def get_search_terms(
        self,
        client_id: str,
        campaign_id: str,
        ad_group_id: Optional[str] = None,
        days: int = 30,
        min_impressions: int = 10,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Obtem termos de pesquisa com metricas dos ultimos N dias.

        Args:
            client_id: ID do cliente no sistema
            campaign_id: ID da campanha
            ad_group_id: ID do grupo de anuncios (opcional)
            days: Periodo em dias (default: 30)
            min_impressions: Minimo de impressoes para filtrar (default: 10)
            limit: Limite de resultados (default: 500)

        Returns:
            list: Lista de termos de pesquisa com metricas
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)

            if not google_ads_client:
                logger.error(f"Cliente {client_id} nao configurado para Google Ads")
                return []

            ga_service = google_ads_client.get_service("GoogleAdsService")

            # Construir filtro de ad_group se especificado
            ad_group_filter = ""
            if ad_group_id:
                ad_group_filter = f"AND ad_group.id = {ad_group_id}"

            # Query para search terms - usando LAST_30_DAYS ou periodo customizado
            date_range = f"LAST_{days}_DAYS" if days in [7, 14, 30, 90] else "LAST_30_DAYS"

            query = f"""
                SELECT
                    search_term_view.search_term,
                    search_term_view.status,
                    campaign.id,
                    campaign.name,
                    ad_group.id,
                    ad_group.name,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions,
                    metrics.cost_micros,
                    metrics.ctr,
                    metrics.average_cpc
                FROM search_term_view
                WHERE campaign.id = {campaign_id}
                    AND segments.date DURING {date_range}
                    AND metrics.impressions >= {min_impressions}
                    {ad_group_filter}
                ORDER BY metrics.impressions DESC
                LIMIT {limit}
            """

            stream = ga_service.search_stream(customer_id=customer_id, query=query)

            search_terms = []
            for batch in stream:
                for row in batch.results:
                    cost = row.metrics.cost_micros / 1000000 if row.metrics.cost_micros else 0
                    conversions = row.metrics.conversions if row.metrics.conversions else 0

                    term_data = {
                        'search_term': row.search_term_view.search_term,
                        'status': row.search_term_view.status.name,
                        'campaign': {
                            'id': row.campaign.id,
                            'name': row.campaign.name
                        },
                        'ad_group': {
                            'id': row.ad_group.id,
                            'name': row.ad_group.name
                        },
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'conversions': conversions,
                        'cost': cost,
                        'ctr': round(row.metrics.ctr * 100, 2) if row.metrics.ctr else 0,
                        'cpc': row.metrics.average_cpc / 1000000 if row.metrics.average_cpc else 0,
                        'cpa': round(cost / conversions, 2) if conversions > 0 else None
                    }
                    search_terms.append(term_data)

            logger.info(f"Encontrados {len(search_terms)} termos de pesquisa para cliente {client_id}")
            return search_terms

        except GoogleAdsException as ex:
            logger.error(f"Erro da API do Google Ads ao buscar search terms: {ex.error.code().name}")
            return []
        except Exception as e:
            logger.error(f"Erro ao buscar search terms para cliente {client_id}: {str(e)}")
            return []

    def get_negative_keywords(
        self,
        client_id: str,
        campaign_id: str,
        ad_group_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtem negative keywords existentes de uma campanha ou ad group.

        Args:
            client_id: ID do cliente no sistema
            campaign_id: ID da campanha
            ad_group_id: ID do grupo de anuncios (opcional)

        Returns:
            list: Lista de negative keywords
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)

            if not google_ads_client:
                logger.error(f"Cliente {client_id} nao configurado para Google Ads")
                return []

            ga_service = google_ads_client.get_service("GoogleAdsService")

            negative_keywords = []

            # 1. Buscar negative keywords a nivel de campanha
            campaign_query = f"""
                SELECT
                    campaign_criterion.criterion_id,
                    campaign_criterion.keyword.text,
                    campaign_criterion.keyword.match_type,
                    campaign_criterion.negative,
                    campaign.id,
                    campaign.name
                FROM campaign_criterion
                WHERE campaign.id = {campaign_id}
                    AND campaign_criterion.type = 'KEYWORD'
                    AND campaign_criterion.negative = TRUE
            """

            stream = ga_service.search_stream(customer_id=customer_id, query=campaign_query)

            for batch in stream:
                for row in batch.results:
                    negative_keywords.append({
                        'id': row.campaign_criterion.criterion_id,
                        'text': row.campaign_criterion.keyword.text,
                        'match_type': row.campaign_criterion.keyword.match_type.name,
                        'level': 'campaign',
                        'campaign': {
                            'id': row.campaign.id,
                            'name': row.campaign.name
                        }
                    })

            # 2. Buscar negative keywords a nivel de ad group (se especificado)
            if ad_group_id:
                ad_group_query = f"""
                    SELECT
                        ad_group_criterion.criterion_id,
                        ad_group_criterion.keyword.text,
                        ad_group_criterion.keyword.match_type,
                        ad_group_criterion.negative,
                        ad_group.id,
                        ad_group.name,
                        campaign.id,
                        campaign.name
                    FROM ad_group_criterion
                    WHERE ad_group.id = {ad_group_id}
                        AND ad_group_criterion.type = 'KEYWORD'
                        AND ad_group_criterion.negative = TRUE
                """

                stream = ga_service.search_stream(customer_id=customer_id, query=ad_group_query)

                for batch in stream:
                    for row in batch.results:
                        negative_keywords.append({
                            'id': row.ad_group_criterion.criterion_id,
                            'text': row.ad_group_criterion.keyword.text,
                            'match_type': row.ad_group_criterion.keyword.match_type.name,
                            'level': 'ad_group',
                            'ad_group': {
                                'id': row.ad_group.id,
                                'name': row.ad_group.name
                            },
                            'campaign': {
                                'id': row.campaign.id,
                                'name': row.campaign.name
                            }
                        })

            logger.info(f"Encontradas {len(negative_keywords)} negative keywords para cliente {client_id}")
            return negative_keywords

        except GoogleAdsException as ex:
            logger.error(f"Erro da API do Google Ads ao buscar negative keywords: {ex.error.code().name}")
            return []
        except Exception as e:
            logger.error(f"Erro ao buscar negative keywords para cliente {client_id}: {str(e)}")
            return []

    def add_negative_keywords(
        self,
        client_id: str,
        campaign_id: str,
        negative_keywords: List[Dict[str, str]],
        ad_group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Adiciona negative keywords a uma campanha ou ad group.

        Args:
            client_id: ID do cliente no sistema
            campaign_id: ID da campanha
            negative_keywords: Lista de keywords [{text: str, matchType: BROAD|PHRASE|EXACT}]
            ad_group_id: ID do grupo de anuncios (opcional, se omitido aplica a nivel de campanha)

        Returns:
            dict: Resultado da operacao
                - success (bool)
                - applied (list): Keywords aplicadas com sucesso
                - errors (list): Erros por keyword
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)

            if not google_ads_client:
                return {
                    'success': False,
                    'error': f'Cliente {client_id} nao configurado para Google Ads'
                }

            applied = []
            errors = []

            # Mapear match types
            match_type_enum = google_ads_client.enums.KeywordMatchTypeEnum
            match_type_map = {
                'BROAD': match_type_enum.BROAD,
                'PHRASE': match_type_enum.PHRASE,
                'EXACT': match_type_enum.EXACT
            }

            if ad_group_id:
                # Aplicar a nivel de ad group
                ad_group_criterion_service = google_ads_client.get_service("AdGroupCriterionService")
                operations = []

                for kw in negative_keywords:
                    try:
                        operation = google_ads_client.get_type("AdGroupCriterionOperation")
                        criterion = operation.create

                        criterion.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
                        criterion.negative = True
                        criterion.keyword.text = kw.get("text")
                        criterion.keyword.match_type = match_type_map.get(
                            kw.get("matchType", "BROAD").upper(),
                            match_type_enum.BROAD
                        )

                        operations.append(operation)
                    except Exception as e:
                        errors.append({
                            'keyword': kw.get("text"),
                            'error': str(e)
                        })

                if operations:
                    response = ad_group_criterion_service.mutate_ad_group_criteria(
                        customer_id=customer_id,
                        operations=operations
                    )

                    for result in response.results:
                        applied.append(result.resource_name)
            else:
                # Aplicar a nivel de campanha
                campaign_criterion_service = google_ads_client.get_service("CampaignCriterionService")
                operations = []

                for kw in negative_keywords:
                    try:
                        operation = google_ads_client.get_type("CampaignCriterionOperation")
                        criterion = operation.create

                        criterion.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
                        criterion.negative = True
                        criterion.keyword.text = kw.get("text")
                        criterion.keyword.match_type = match_type_map.get(
                            kw.get("matchType", "BROAD").upper(),
                            match_type_enum.BROAD
                        )

                        operations.append(operation)
                    except Exception as e:
                        errors.append({
                            'keyword': kw.get("text"),
                            'error': str(e)
                        })

                if operations:
                    response = campaign_criterion_service.mutate_campaign_criteria(
                        customer_id=customer_id,
                        operations=operations
                    )

                    for result in response.results:
                        applied.append(result.resource_name)

            logger.info(
                f"Negative keywords aplicadas para cliente {client_id}: "
                f"{len(applied)} sucesso, {len(errors)} erros"
            )

            return {
                'success': len(errors) == 0,
                'applied': applied,
                'errors': errors if errors else None
            }

        except GoogleAdsException as ex:
            error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
            if ex.error.message:
                error_msg += f" - {ex.error.message}"

            logger.error(f"Erro ao adicionar negative keywords para cliente {client_id}: {error_msg}")

            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            logger.error(f"Erro ao adicionar negative keywords para cliente {client_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def pause_campaign(self, client_id: str, campaign_id: str) -> Dict[str, Any]:
        """
        Pausa uma campanha no Google Ads

        Args:
            client_id: ID do cliente no sistema
            campaign_id: ID da campanha no Google Ads

        Returns:
            dict: Resultado da operação com campos:
                - success (bool): Se a operação foi bem sucedida
                - campaign_id (str): ID da campanha
                - previous_status (str): Status anterior
                - new_status (str): Novo status (PAUSED)
                - error (str): Mensagem de erro se falhou
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)

            if not google_ads_client:
                return {
                    'success': False,
                    'campaign_id': campaign_id,
                    'error': f'Cliente {client_id} não configurado para Google Ads'
                }

            campaign_service = google_ads_client.get_service("CampaignService")

            # Construir resource name da campanha
            campaign_resource_name = f"customers/{customer_id}/campaigns/{campaign_id}"

            # Criar operação de mutação
            campaign_operation = google_ads_client.get_type("CampaignOperation")
            campaign = campaign_operation.update
            campaign.resource_name = campaign_resource_name
            campaign.status = google_ads_client.enums.CampaignStatusEnum.PAUSED

            # Definir field mask para atualizar apenas o status
            google_ads_client.copy_from(
                campaign_operation.update_mask,
                google_ads_client.get_type("FieldMask")(paths=["status"])
            )

            # Executar mutação
            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )

            logger.info(f"Campanha {campaign_id} pausada com sucesso para cliente {client_id}")

            return {
                'success': True,
                'campaign_id': campaign_id,
                'resource_name': response.results[0].resource_name,
                'new_status': 'PAUSED'
            }

        except GoogleAdsException as ex:
            error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
            if ex.error.message:
                error_msg += f" - {ex.error.message}"

            logger.error(f"Erro ao pausar campanha {campaign_id} para cliente {client_id}: {error_msg}")

            return {
                'success': False,
                'campaign_id': campaign_id,
                'error': error_msg
            }

        except Exception as e:
            logger.error(f"Erro ao pausar campanha {campaign_id} para cliente {client_id}: {str(e)}")
            return {
                'success': False,
                'campaign_id': campaign_id,
                'error': str(e)
            }

    def update_ad_group_cpc(self, client_id: str, ad_group_id: str, new_cpc_micros: int) -> Dict[str, Any]:
        """
        Atualiza o CPC de um grupo de anúncios

        Args:
            client_id: ID do cliente no sistema
            ad_group_id: ID do grupo de anúncios
            new_cpc_micros: Novo valor de CPC em micros (1 unidade = 1.000.000 micros)

        Returns:
            dict: Resultado da operação com campos:
                - success (bool): Se a operação foi bem sucedida
                - ad_group_id (str): ID do grupo de anúncios
                - new_cpc_micros (int): Novo CPC em micros
                - error (str): Mensagem de erro se falhou
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)

            if not google_ads_client:
                return {
                    'success': False,
                    'ad_group_id': ad_group_id,
                    'error': f'Cliente {client_id} não configurado para Google Ads'
                }

            ad_group_service = google_ads_client.get_service("AdGroupService")

            # Construir resource name do ad group
            ad_group_resource_name = f"customers/{customer_id}/adGroups/{ad_group_id}"

            # Criar operação de mutação
            ad_group_operation = google_ads_client.get_type("AdGroupOperation")
            ad_group = ad_group_operation.update
            ad_group.resource_name = ad_group_resource_name
            ad_group.cpc_bid_micros = new_cpc_micros

            # Definir field mask para atualizar apenas o CPC
            google_ads_client.copy_from(
                ad_group_operation.update_mask,
                google_ads_client.get_type("FieldMask")(paths=["cpc_bid_micros"])
            )

            # Executar mutação
            response = ad_group_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[ad_group_operation]
            )

            logger.info(
                f"CPC do ad group {ad_group_id} atualizado para {new_cpc_micros} micros "
                f"para cliente {client_id}"
            )

            return {
                'success': True,
                'ad_group_id': ad_group_id,
                'resource_name': response.results[0].resource_name,
                'new_cpc_micros': new_cpc_micros
            }

        except GoogleAdsException as ex:
            error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
            if ex.error.message:
                error_msg += f" - {ex.error.message}"

            logger.error(
                f"Erro ao atualizar CPC do ad group {ad_group_id} para cliente {client_id}: {error_msg}"
            )

            return {
                'success': False,
                'ad_group_id': ad_group_id,
                'error': error_msg
            }

        except Exception as e:
            logger.error(
                f"Erro ao atualizar CPC do ad group {ad_group_id} para cliente {client_id}: {str(e)}"
            )
            return {
                'success': False,
                'ad_group_id': ad_group_id,
                'error': str(e)
            }

    def clear_cache(self, client_id: Optional[str] = None):
        """
        Limpa o cache de clientes
        
        Args:
            client_id (str, opcional): ID específico para limpar, ou None para limpar tudo
        """
        if client_id:
            self._client_cache.pop(client_id, None)
            logger.info(f"Cache limpo para cliente: {client_id}")
        else:
            self._client_cache.clear()
            logger.info("Cache de clientes Google Ads limpo completamente")
    
    # Método mantido para compatibilidade com código existente
    def get_customer_campaigns(self, client_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Método mantido para compatibilidade. Use get_campaigns() para nova implementação.
        """
        return self.get_campaigns(client_id, limit, include_metrics=True) 