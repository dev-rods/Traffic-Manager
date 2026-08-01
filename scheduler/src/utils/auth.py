import os
import logging
import hashlib

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class SchedulerAuth:

    def validate_api_key(self, api_key):
        try:
            expected_api_key = os.environ.get("SCHEDULER_API_KEY")
            if not expected_api_key:
                logger.error("SCHEDULER_API_KEY não configurada no ambiente")
                return False
            return expected_api_key == api_key
        except Exception as e:
            logger.error(f"Erro ao validar API key: {str(e)}")
            return False

    def validate_intake_api_key(self, api_key):
        """Valida a chave para o endpoint público de intake de leads (POST /leads).

        Aceita a chave de intake dedicada (LEADS_INTAKE_API_KEY), restrita a esse
        endpoint e usada pela landing page, OU a chave mestra (SCHEDULER_API_KEY)
        para chamadas internas/administrativas.
        """
        try:
            if not api_key:
                return False
            intake_key = os.environ.get("LEADS_INTAKE_API_KEY")
            master_key = os.environ.get("SCHEDULER_API_KEY")
            if intake_key and api_key == intake_key:
                return True
            if master_key and api_key == master_key:
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao validar intake API key: {str(e)}")
            return False

    @staticmethod
    def generate_clinic_id(clinic_name):
        base = "".join(e for e in clinic_name if e.isalnum()).lower()
        hash_suffix = hashlib.md5(clinic_name.encode()).hexdigest()[:6]
        return f"{base}-{hash_suffix}"
