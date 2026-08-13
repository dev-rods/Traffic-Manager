"""Carrega credenciais do Google Ads (MCC) e do Supabase via SSM."""
import boto3

AWS_PROFILE = "dev-andre"


def _ssm_client(stage: str):
    session = boto3.Session(profile_name=AWS_PROFILE)
    return session.client("ssm")


def _get_parameter(ssm, stage: str, name: str) -> str:
    response = ssm.get_parameter(Name=f"/{stage}/{name}", WithDecryption=True)
    return response["Parameter"]["Value"]


def load_google_ads_config(stage: str) -> dict:
    """Mesmo formato do infra/ (CLAUDE.md "Google Ads client initialization"),
    usando as credenciais do MCC — o mesmo caminho usado por
    infra/src/services/google_ads_config.py e pelo upload de conversões offline.
    """
    ssm = _ssm_client(stage)
    login_customer_id = _get_parameter(ssm, stage, "MCC_ACCOUNT_ID").replace("-", "")
    return {
        "developer_token": _get_parameter(ssm, stage, "MCC_DEVELOPER_TOKEN"),
        "client_id": _get_parameter(ssm, stage, "OAUTH2_CLIENT_ID"),
        "client_secret": _get_parameter(ssm, stage, "OAUTH2_CLIENT_SECRET"),
        "refresh_token": _get_parameter(ssm, stage, "GOOGLE_ADS_REFRESH_TOKEN"),
        "use_proto_plus": True,
        "login_customer_id": login_customer_id,
    }


def load_supabase_config(stage: str) -> dict:
    """Mesmos parâmetros SSM usados por scheduler/serverless.yml (SUPABASE_DB_*)."""
    ssm = _ssm_client(stage)
    return {
        "host": _get_parameter(ssm, stage, "SUPABASE_DB_HOST"),
        "port": _get_parameter(ssm, stage, "SUPABASE_DB_PORT"),
        "dbname": _get_parameter(ssm, stage, "SUPABASE_DB_NAME"),
        "user": _get_parameter(ssm, stage, "SUPABASE_DB_USER"),
        "password": _get_parameter(ssm, stage, "SUPABASE_DB_PASSWORD"),
    }
