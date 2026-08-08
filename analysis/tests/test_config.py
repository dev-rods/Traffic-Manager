from unittest.mock import MagicMock, patch

from analysis.config import load_google_ads_config, load_supabase_config

SSM_VALUES = {
    "/dev/MCC_DEVELOPER_TOKEN": "dev-token-123",
    "/dev/OAUTH2_CLIENT_ID": "client-id-abc",
    "/dev/OAUTH2_CLIENT_SECRET": "client-secret-xyz",
    "/dev/GOOGLE_ADS_REFRESH_TOKEN": "refresh-token-456",
    "/dev/MCC_ACCOUNT_ID": "123-456-7890",
    "/dev/SUPABASE_DB_HOST": "db.example.com",
    "/dev/SUPABASE_DB_PORT": "5432",
    "/dev/SUPABASE_DB_NAME": "postgres",
    "/dev/SUPABASE_DB_USER": "scheduler_app",
    "/dev/SUPABASE_DB_PASSWORD": "s3cr3t",
}


def _fake_ssm_client():
    def get_parameter(Name, WithDecryption=True):
        return {"Parameter": {"Value": SSM_VALUES[Name]}}

    client = MagicMock()
    client.get_parameter.side_effect = get_parameter
    return client


@patch("analysis.config.boto3.Session")
def test_load_google_ads_config_reads_mcc_params_from_ssm(mock_session_cls):
    mock_session = MagicMock()
    mock_session.client.return_value = _fake_ssm_client()
    mock_session_cls.return_value = mock_session

    config = load_google_ads_config("dev")

    mock_session_cls.assert_called_once_with(profile_name="dev-andre")
    assert config == {
        "developer_token": "dev-token-123",
        "client_id": "client-id-abc",
        "client_secret": "client-secret-xyz",
        "refresh_token": "refresh-token-456",
        "use_proto_plus": True,
        "login_customer_id": "1234567890",
    }


@patch("analysis.config.boto3.Session")
def test_load_supabase_config_reads_db_params_from_ssm(mock_session_cls):
    mock_session = MagicMock()
    mock_session.client.return_value = _fake_ssm_client()
    mock_session_cls.return_value = mock_session

    config = load_supabase_config("dev")

    assert config == {
        "host": "db.example.com",
        "port": "5432",
        "dbname": "postgres",
        "user": "scheduler_app",
        "password": "s3cr3t",
    }
