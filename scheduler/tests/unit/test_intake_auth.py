"""Unit tests for the dedicated lead-intake API key validation."""
import os
import unittest

from src.utils.auth import SchedulerAuth


class TestIntakeApiKey(unittest.TestCase):

    def setUp(self):
        self.auth = SchedulerAuth()
        self._saved = {
            "LEADS_INTAKE_API_KEY": os.environ.get("LEADS_INTAKE_API_KEY"),
            "SCHEDULER_API_KEY": os.environ.get("SCHEDULER_API_KEY"),
        }

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_intake_key_accepted(self):
        os.environ["LEADS_INTAKE_API_KEY"] = "intake-123"
        os.environ["SCHEDULER_API_KEY"] = "master-xyz"
        self.assertTrue(self.auth.validate_intake_api_key("intake-123"))

    def test_master_key_also_accepted(self):
        os.environ["LEADS_INTAKE_API_KEY"] = "intake-123"
        os.environ["SCHEDULER_API_KEY"] = "master-xyz"
        self.assertTrue(self.auth.validate_intake_api_key("master-xyz"))

    def test_wrong_key_rejected(self):
        os.environ["LEADS_INTAKE_API_KEY"] = "intake-123"
        os.environ["SCHEDULER_API_KEY"] = "master-xyz"
        self.assertFalse(self.auth.validate_intake_api_key("errada"))

    def test_empty_key_rejected(self):
        os.environ["LEADS_INTAKE_API_KEY"] = "intake-123"
        self.assertFalse(self.auth.validate_intake_api_key(None))
        self.assertFalse(self.auth.validate_intake_api_key(""))

    def test_master_only_when_intake_unset(self):
        os.environ.pop("LEADS_INTAKE_API_KEY", None)
        os.environ["SCHEDULER_API_KEY"] = "master-xyz"
        self.assertTrue(self.auth.validate_intake_api_key("master-xyz"))
        self.assertFalse(self.auth.validate_intake_api_key("intake-123"))

    def test_intake_key_does_not_authorize_master_endpoints(self):
        # A chave de intake NÃO deve validar no fluxo mestre (validate_api_key)
        os.environ["LEADS_INTAKE_API_KEY"] = "intake-123"
        os.environ["SCHEDULER_API_KEY"] = "master-xyz"
        self.assertFalse(self.auth.validate_api_key("intake-123"))
        self.assertTrue(self.auth.validate_api_key("master-xyz"))


if __name__ == "__main__":
    unittest.main()
