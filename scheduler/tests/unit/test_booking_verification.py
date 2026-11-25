# -*- coding: utf-8 -*-
"""Token de sessão do OTP (PRD 026) com escopo (PRD 048).

O token é stateless: o que se testa é o conteúdo assinado. `SESSAO` é o de
sempre (15 min); `DOCUMENTOS` dura 2 h e só passa onde a rota o aceita.
Tokens de 4 partes, emitidos antes do escopo existir, valem como `SESSAO`.
"""
import base64
import hashlib
import hmac
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.utils import booking_verification as bv

CLINIC = "clinica-teste-0001"
FONE = "5511999990000"


class TestEscopo(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"BOOKING_VERIFICATION_SECRET": "segredo-de-teste"})
        p.start()
        self.addCleanup(p.stop)

    def test_sessao_e_o_padrao_e_dura_30_min(self):
        agora = int(time.time())
        token = bv._issue_token(CLINIC, FONE)
        clinic, fone, expira, escopo = bv._abre(token)
        self.assertEqual((clinic, fone, escopo), (CLINIC, FONE, bv.SESSAO))
        self.assertAlmostEqual(expira - agora, 30 * 60, delta=5)
        self.assertTrue(bv.verify_token(CLINIC, FONE, token))
        self.assertFalse(bv.verify_token(CLINIC, FONE, token, scopes=(bv.DOCUMENTOS,)))
        self.assertEqual(bv.escopo_do_token(token), bv.SESSAO)

    def test_documentos_dura_2h_e_so_passa_onde_a_rota_aceita(self):
        agora = int(time.time())
        token = bv._issue_token(CLINIC, FONE, bv.DOCUMENTOS)
        self.assertAlmostEqual(bv._abre(token)[2] - agora, 2 * 60 * 60, delta=5)
        self.assertFalse(bv.verify_token(CLINIC, FONE, token), "o padrão das rotas de hoje recusa")
        self.assertTrue(bv.verify_token(CLINIC, FONE, token, scopes=(bv.SESSAO, bv.DOCUMENTOS)))
        self.assertEqual(bv.escopo_do_token(token), bv.DOCUMENTOS)

    def test_token_antigo_de_4_partes_vale_como_sessao(self):
        expira = int(time.time()) + 60
        payload = f"{CLINIC}|{FONE}|{expira}"
        assinatura = hmac.new(b"segredo-de-teste", payload.encode(), hashlib.sha256).hexdigest()
        token = base64.urlsafe_b64encode(f"{payload}|{assinatura}".encode()).decode()
        self.assertTrue(bv.verify_token(CLINIC, FONE, token))
        self.assertEqual(bv.escopo_do_token(token), bv.SESSAO)
        self.assertFalse(bv.verify_token(CLINIC, FONE, token, scopes=(bv.DOCUMENTOS,)))

    def test_assinatura_clinica_telefone_e_prazo(self):
        token = bv._issue_token(CLINIC, FONE, bv.DOCUMENTOS)
        todos = (bv.SESSAO, bv.DOCUMENTOS)
        self.assertFalse(bv.verify_token("outra-clinica", FONE, token, scopes=todos))
        self.assertFalse(bv.verify_token(CLINIC, "5511988887777", token, scopes=todos))
        # Escopo trocado no conteúdo invalida a assinatura.
        raw = base64.urlsafe_b64decode(token.encode()).decode().split("|")
        raw[3] = bv.SESSAO
        forjado = base64.urlsafe_b64encode("|".join(raw).encode()).decode()
        self.assertFalse(bv.verify_token(CLINIC, FONE, forjado, scopes=todos))
        self.assertIsNone(bv.escopo_do_token(forjado))
        with mock.patch.object(bv.time, "time", return_value=time.time() + 3 * 60 * 60):
            self.assertFalse(bv.verify_token(CLINIC, FONE, token, scopes=todos))
        self.assertFalse(bv.verify_token(CLINIC, FONE, "", scopes=todos))
        self.assertFalse(bv.verify_token(CLINIC, FONE, "nao-e-base64!", scopes=todos))

    def test_confirm_code_recusa_escopo_desconhecido(self):
        with self.assertRaises(ValueError):
            bv.confirm_code(CLINIC, FONE, "123456", scope="admin")
