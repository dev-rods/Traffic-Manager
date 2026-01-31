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

    @staticmethod
    def generate_clinic_id(clinic_name):
        base = "".join(e for e in clinic_name if e.isalnum()).lower()
        hash_suffix = hashlib.md5(clinic_name.encode()).hexdigest()[:6]
        return f"{base}-{hash_suffix}"
