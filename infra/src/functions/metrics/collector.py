import json
import boto3
import os
import logging
from datetime import datetime, timedelta
from src.services.google_ads_client_service import GoogleAdsClientService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))
campaign_metadata_table = dynamodb.Table(os.environ.get("CAMPAIGN_METADATA_TABLE"))

def handler(event, context):
    try:
        trace_id = event.get("traceId")
        client_id = event.get("clientId")
        stage = "FETCH_METRICS"
        timestamp = datetime.utcnow().isoformat()
        
        if "campaignId" not in event or not event["campaignId"]:
            raise Exception("campaignId é obrigatório para coleta de métricas")
        
        campaign_id = event["campaignId"]
        store_id = event.get("storeId", "unknown")
        
        logger.info(f"[traceId: {trace_id}] Coletando métricas para campanha {campaign_id}")
        
        ads_service = GoogleAdsClientService()
        
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        
        metrics = collect_campaign_metrics(ads_service, client_id, campaign_id, start_date, end_date)
        campaign_structure = get_campaign_structure(ads_service, client_id, campaign_id)
        
        detailed_metrics = {
            "campaign": metrics,
            "keywords": get_keyword_performance(ads_service, client_id, campaign_id),
            "ads": get_ad_performance(ads_service, client_id, campaign_id),
            "demographics": get_demographic_performance(ads_service, client_id, campaign_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": 30
            }
        }
        
        execution_record = {
            "traceId": trace_id,
            "stageTm": f"{stage}#{timestamp}",
            "stage": stage,
            "status": "COMPLETED",
            "timestamp": timestamp,
            "campaignId": campaign_id,
            "storeId": store_id,
            "payload": json.dumps({
                "metrics_summary": detailed_metrics["campaign"]
            })
        }
        
        if "runType" in event:
            execution_record["runType"] = event["runType"]
        if "clientId" in event:
            execution_record["clientId"] = event["clientId"]
            
        execution_history_table.put_item(Item=execution_record)
        
        response = {
            "traceId": trace_id,
            "timestamp": timestamp,
            "runType": event.get("runType", "IMPROVE"),
            "campaignId": campaign_id,
            "clientId": client_id,
            "metricsData": detailed_metrics,
            "campaignStructure": campaign_structure
        }
        
        if "storeId" in event:
            response["storeId"] = event["storeId"]
        
        logger.info(f"[traceId: {trace_id}] Métricas coletadas com sucesso para campanha {campaign_id}")
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro ao coletar métricas: {error_msg}")
        if 'trace_id' in locals():
            try:
                error_record = {
                    'traceId': trace_id,
                    'stageTm': f"{stage}#{timestamp}",
                    'stage': stage,
                    'status': 'ERROR',
                    'timestamp': timestamp,
                    'errorMsg': error_msg,
                    'payload': json.dumps(event)
                }
                
                if 'campaign_id' in locals():
                    error_record['campaignId'] = campaign_id
                
                if 'store_id' in locals():
                    error_record['storeId'] = store_id
                    
                execution_history_table.put_item(Item=error_record)
            except Exception as inner_e:
                logger.error(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        
        raise Exception(f"Erro ao coletar métricas da campanha: {error_msg}")


def collect_campaign_metrics(ads_service, client_id, campaign_id, start_date, end_date):
    try:
        google_ads_client, customer_id = ads_service.get_client_for_customer(client_id)
        
        if not google_ads_client:
            raise Exception(f"Cliente {client_id} não configurado para Google Ads")
        
        ga_service = google_ads_client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT 
                campaign.id,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversion_value_micros,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_per_conversion
            FROM campaign 
            WHERE campaign.id = {campaign_id}
            AND segments.date BETWEEN '{start_date}' AND '{end_date}'
        """
        
        search_request = google_ads_client.get_type("SearchGoogleAdsRequest")
        search_request.customer_id = customer_id
        search_request.query = query
        
        response = ga_service.search(request=search_request)
        
        total_impressions = 0
        total_clicks = 0
        total_cost = 0
        total_conversions = 0
        total_conversion_value = 0
        
        for row in response:
            total_impressions += row.metrics.impressions
            total_clicks += row.metrics.clicks
            total_cost += row.metrics.cost_micros / 1000000
            total_conversions += row.metrics.conversions
            total_conversion_value += row.metrics.conversion_value_micros / 1000000
        
        ctr = (total_clicks / total_impressions) if total_impressions > 0 else 0
        avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
        cost_per_conversion = (total_cost / total_conversions) if total_conversions > 0 else 0
        conversion_rate = (total_conversions / total_clicks) if total_clicks > 0 else 0
        roas = (total_conversion_value / total_cost) if total_cost > 0 else 0
        
        return {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "cost": total_cost,
            "conversions": total_conversions,
            "conversion_value": total_conversion_value,
            "ctr": ctr,
            "average_cpc": avg_cpc,
            "cost_per_conversion": cost_per_conversion,
            "conversion_rate": conversion_rate,
            "roas": roas
        }
        
    except Exception as e:
        logger.error(f"Erro ao coletar métricas da campanha {campaign_id}: {str(e)}")
        return create_fallback_metrics()


def get_keyword_performance(ads_service, client_id, campaign_id):
    try:
        google_ads_client, customer_id = ads_service.get_client_for_customer(client_id)
        
        if not google_ads_client:
            return []
        
        ga_service = google_ads_client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT 
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_micros,
                ad_group_criterion.quality_info.quality_score
            FROM keyword_view 
            WHERE campaign.id = {campaign_id}
            AND metrics.impressions > 0
            ORDER BY metrics.clicks DESC
            LIMIT 50
        """
        
        search_request = google_ads_client.get_type("SearchGoogleAdsRequest")
        search_request.customer_id = customer_id
        search_request.query = query
        
        response = ga_service.search(request=search_request)
        
        keywords = []
        for row in response:
            keywords.append({
                "text": row.ad_group_criterion.keyword.text,
                "match_type": row.ad_group_criterion.keyword.match_type.name,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "ctr": row.metrics.ctr,
                "average_cpc": row.metrics.average_cpc,
                "cost": row.metrics.cost_micros / 1000000,
                "quality_score": row.ad_group_criterion.quality_info.quality_score
            })
        
        return keywords
        
    except Exception as e:
        logger.error(f"Erro ao coletar performance de keywords: {str(e)}")
        return []


def get_ad_performance(ads_service, client_id, campaign_id):
    try:
        google_ads_client, customer_id = ads_service.get_client_for_customer(client_id)
        
        if not google_ads_client:
            return []
        
        ga_service = google_ads_client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT 
                ad_group_ad.ad.responsive_search_ad.headlines,
                ad_group_ad.ad.responsive_search_ad.descriptions,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.cost_micros
            FROM ad_group_ad 
            WHERE campaign.id = {campaign_id}
            AND ad_group_ad.status = 'ENABLED'
            ORDER BY metrics.impressions DESC
            LIMIT 20
        """
        
        search_request = google_ads_client.get_type("SearchGoogleAdsRequest")
        search_request.customer_id = customer_id
        search_request.query = query
        
        response = ga_service.search(request=search_request)
        
        ads = []
        for row in response:
            headlines = [asset.text for asset in row.ad_group_ad.ad.responsive_search_ad.headlines]
            descriptions = [asset.text for asset in row.ad_group_ad.ad.responsive_search_ad.descriptions]
            
            ads.append({
                "headlines": headlines,
                "descriptions": descriptions,
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "ctr": row.metrics.ctr,
                "cost": row.metrics.cost_micros / 1000000
            })
        
        return ads
        
    except Exception as e:
        logger.error(f"Erro ao coletar performance de anúncios: {str(e)}")
        return []


def get_demographic_performance(ads_service, client_id, campaign_id):
    try:
        return {
            "age_groups": [],
            "genders": [],
            "devices": []
        }
        
    except Exception as e:
        logger.error(f"Erro ao coletar dados demográficos: {str(e)}")
        return {"age_groups": [], "genders": [], "devices": []}


def get_campaign_structure(ads_service, client_id, campaign_id):
    try:
        google_ads_client, customer_id = ads_service.get_client_for_customer(client_id)
        
        if not google_ads_client:
            return create_fallback_structure(campaign_id)
        
        ga_service = google_ads_client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT 
                campaign.name,
                campaign.advertising_channel_type,
                campaign.target_spend.target_spend_micros,
                ad_group.name,
                ad_group.id
            FROM ad_group 
            WHERE campaign.id = {campaign_id}
        """
        
        search_request = google_ads_client.get_type("SearchGoogleAdsRequest")
        search_request.customer_id = customer_id
        search_request.query = query
        
        response = ga_service.search(request=search_request)
        
        campaign_name = ""
        ad_groups = []
        
        for row in response:
            if not campaign_name:
                campaign_name = row.campaign.name
            
            ad_groups.append({
                "id": row.ad_group.id,
                "name": row.ad_group.name
            })
        
        return {
            "campaign_name": campaign_name,
            "campaign_id": campaign_id,
            "ad_groups": ad_groups
        }
        
    except Exception as e:
        logger.error(f"Erro ao coletar estrutura da campanha: {str(e)}")
        return create_fallback_structure(campaign_id)


def create_fallback_metrics():
    return {
        "impressions": 0,
        "clicks": 0,
        "cost": 0,
        "conversions": 0,
        "conversion_value": 0,
        "ctr": 0,
        "average_cpc": 0,
        "cost_per_conversion": 0,
        "conversion_rate": 0,
        "roas": 0
    }


def create_fallback_structure(campaign_id):
    return {
        "campaign_name": f"Campanha {campaign_id}",
        "campaign_id": campaign_id,
        "ad_groups": []
    } 