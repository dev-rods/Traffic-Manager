# -*- coding: utf-8 -*-
"""Gravar template com o endereço de outra clínica é recusado (09/11/2026).

O prompt da Nobre nasceu como cópia do da Essência, endereço literal incluso, e
nada no caminho de escrita reclamou. A guarda vive aqui porque é por onde a
cópia entra - o script `corrige_endereco_no_prompt` conserta o que já está
gravado, e esta recusa impede o próximo.
"""
import json
import unittest
from unittest import mock

from src.functions.template import create, update

ESSENCIA = "clinicaessenciaestetica-9668a4"
NOBRE = "nobrelaser-sjc"
BLOCO_COPIADO = ("Sempre que finalizar um agendamento, passe o endereço:\n\n"
                 "Rua Augusta, 2709\nConj. 26 - CLÍNICA ESSÊNCIA (2º andar)")
LIMPO = "Passe o endereço: {{clinic_address}}"


class Db:
    def __init__(self):
        self.escritas = []

    def execute_query(self, sql, params=None):
        if "clinics" in sql:
            return [{"clinic_id": ESSENCIA, "address": "Rua Augusta, 2709, Conj. 26"},
                    {"clinic_id": NOBRE, "address": "Rua Armando de Oliveira Cobra, 50"}]
        if "message_templates" in sql:
            return [{"clinic_id": NOBRE}]
        return []

    def execute_write_returning(self, sql, params=None):
        self.escritas.append((sql, params))
        return {"id": "t1", "clinic_id": NOBRE, "template_key": "AI_SYSTEM_PROMPT",
                "content": "ok", "buttons": None, "active": True}


def evento_create(content):
    return {"pathParameters": {"clinicId": NOBRE},
            "body": json.dumps({"template_key": "AI_SYSTEM_PROMPT", "content": content})}


def evento_update(content):
    return {"pathParameters": {"templateId": "11111111-1111-1111-1111-111111111111"},
            "body": json.dumps({"content": content})}


class TestCriacao(unittest.TestCase):
    def _chama(self, content):
        db = Db()
        with mock.patch.object(create, "require_api_key", return_value=("k", None)), \
                mock.patch.object(create, "PostgresService", return_value=db):
            return create.handler(evento_create(content), None), db

    def test_recusa_com_422_e_nao_grava(self):
        resp, db = self._chama(BLOCO_COPIADO)
        self.assertEqual(resp["statusCode"], 422)
        self.assertIn(ESSENCIA, json.loads(resp["body"])["message"])
        self.assertEqual(db.escritas, [], "o template foi gravado mesmo assim")

    def test_texto_com_a_variavel_passa(self):
        resp, db = self._chama(LIMPO)
        self.assertEqual(resp["statusCode"], 201)
        self.assertEqual(len(db.escritas), 1)


class TestAtualizacao(unittest.TestCase):
    def _chama(self, content):
        db = Db()
        with mock.patch.object(update, "require_api_key", return_value=("k", None)), \
                mock.patch.object(update, "PostgresService", return_value=db):
            return update.handler(evento_update(content), None), db

    def test_recusa_com_422_e_nao_grava(self):
        """A clínica vem do template, não do path: editar pelo painel não
        informa clinic_id, e sem essa leitura a guarda passaria batido."""
        resp, db = self._chama(BLOCO_COPIADO)
        self.assertEqual(resp["statusCode"], 422)
        self.assertEqual(db.escritas, [])

    def test_texto_limpo_passa(self):
        resp, db = self._chama(LIMPO)
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(len(db.escritas), 1)


if __name__ == "__main__":
    unittest.main()
