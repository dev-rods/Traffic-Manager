# -*- coding: utf-8 -*-
"""Com o WhatsApp fora, o código de verificação só volta na resposta em DEV.

A clínica de teste não tem instância do z-api (conferido em 19/10/2026:
"Instance not found"), e sem isso ninguém consegue testar o login do check-in
do iPad (PRD 026). Em prod, devolver o código na resposta deixaria qualquer um
entrar como o dono de qualquer número - por isso o teste fixa os dois lados.
"""
import os
import unittest
from unittest import mock

from src.utils import booking_verification as bv

CLINIC = {"clinic_id": "c1", "zapi_instance_id": "i", "zapi_instance_token": "t"}


class TestCodigoDeTeste(unittest.TestCase):
    def setUp(self):
        self.tabela = mock.MagicMock()
        self.tabela.get_item.return_value = {}
        self.provider = mock.MagicMock()
        for p in (
            mock.patch.object(bv, "_table", return_value=self.tabela),
            mock.patch.object(bv, "ZApiProvider", return_value=self.provider),
        ):
            p.start()
            self.addCleanup(p.stop)

    def codigo_gravado(self):
        return self.tabela.put_item.call_args.kwargs["Item"]["code"]

    def test_dev_com_whatsapp_fora_devolve_o_codigo(self):
        self.provider.send_text.return_value = mock.MagicMock(success=False, error="Instance not found")
        with mock.patch.dict(os.environ, {"STAGE": "dev"}):
            self.assertEqual(bv.generate_and_send_code(CLINIC, "5511999990000"), self.codigo_gravado())

    def test_prod_com_whatsapp_fora_levanta(self):
        self.provider.send_text.return_value = mock.MagicMock(success=False, error="x")
        with mock.patch.dict(os.environ, {"STAGE": "prod"}):
            with self.assertRaises(bv.SendFailedError):
                bv.generate_and_send_code(CLINIC, "5511999990000")

    def test_dev_devolve_mesmo_com_o_whatsapp_aceitando(self):
        """O z-api de dev aceita o envio e não entrega (teste gravado de
        28/10/2026): em dev o código vem sempre (PRD 028, M4)."""
        self.provider.send_text.return_value = mock.MagicMock(success=True)
        with mock.patch.dict(os.environ, {"STAGE": "dev"}):
            self.assertEqual(bv.generate_and_send_code(CLINIC, "5511999990000"), self.codigo_gravado())

    def test_prod_nunca_devolve(self):
        self.provider.send_text.return_value = mock.MagicMock(success=True)
        with mock.patch.dict(os.environ, {"STAGE": "prod"}):
            self.assertIsNone(bv.generate_and_send_code(CLINIC, "5511999990000"))


class TestSemLimiteDeEnvios(unittest.TestCase):
    """Até 19/10/2026 eram 3 códigos a cada 15 min por número; no check-in do
    iPad a paciente travava em "Muitos códigos solicitados". Saiu (PRD 026)."""

    def test_pedir_muitas_vezes_nao_trava(self):
        tabela = mock.MagicMock()
        tabela.get_item.return_value = {"Item": {"send_count": 99, "window_started_at": 10 ** 12}}
        provider = mock.MagicMock()
        provider.send_text.return_value = mock.MagicMock(success=True)
        with mock.patch.object(bv, "_table", return_value=tabela),                 mock.patch.object(bv, "ZApiProvider", return_value=provider):
            for _ in range(10):
                bv.generate_and_send_code(CLINIC, "5511999990000")
        self.assertEqual(provider.send_text.call_count, 10)
        self.assertFalse(hasattr(bv, "RateLimitedError"))


if __name__ == "__main__":
    unittest.main()
