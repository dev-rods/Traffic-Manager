# -*- coding: utf-8 -*-
"""POST /leads devolve Access-Control-Allow-Origin em TODA resposta (PRD 066).

A LP da Essencia chama do navegador, de outra origem. Sem o cabecalho, o
POST grava mas o fetch recebe erro de CORS ao ler a resposta.
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from src.functions.lead import create

CHAVE = "chave-de-intake-de-teste"


def _evento(body=None, chave=CHAVE):
    headers = {"Origin": "https://lp.exemplo.com.br", "Content-Type": "application/json"}
    if chave:
        headers["x-api-key"] = chave
    return {"headers": headers, "body": json.dumps(body) if body is not None else None}


class _Contexto:
    aws_request_id = "teste"


@patch.dict("os.environ", {"LEADS_INTAKE_API_KEY": CHAVE, "SCHEDULER_API_KEY": "outra"})
class TestCorsNaRotaDeLeads(unittest.TestCase):
    def _confere(self, resposta, status):
        self.assertEqual(resposta["statusCode"], status)
        self.assertEqual(resposta["headers"]["Access-Control-Allow-Origin"], "*")
        self.assertEqual(resposta["headers"]["Content-Type"], "application/json")

    def test_sem_chave_401(self):
        self._confere(create.handler(_evento({"clinicId": "c"}, chave=None), _Contexto()), 401)

    def test_corpo_vazio_400(self):
        self._confere(create.handler(_evento(None), _Contexto()), 400)

    def test_campo_faltando_400(self):
        self._confere(create.handler(_evento({"clinicId": "c"}), _Contexto()), 400)

    @patch.object(create, "VERIFY_WRITE", False)
    @patch.object(create, "LeadService")
    @patch.object(create, "PostgresService")
    def test_sucesso_201(self, db, servico):
        db.return_value.health_check.return_value = {"status": "healthy"}
        servico.return_value.upsert_lead.return_value = {
            "id": "1", "clinic_id": "c", "phone": "5511900000000", "created_at": None, "updated_at": None,
        }
        corpo = {"clinicId": "c", "phone": "11900000000", "name": "Fulana Teste"}
        self._confere(create.handler(_evento(corpo), _Contexto()), 201)

    @patch.object(create, "LeadService")
    @patch.object(create, "PostgresService")
    def test_erro_interno_500(self, db, servico):
        db.return_value.health_check.return_value = {"status": "healthy"}
        servico.return_value.upsert_lead.side_effect = RuntimeError("falhou")
        corpo = {"clinicId": "c", "phone": "11900000000", "name": "Fulana Teste"}
        self._confere(create.handler(_evento(corpo), _Contexto()), 500)


if __name__ == "__main__":
    unittest.main()
