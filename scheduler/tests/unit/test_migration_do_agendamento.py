# -*- coding: utf-8 -*-
"""As colunas do segundo evento de conversão (PRD 017).

Duas colunas, não uma tabela `clinic_conversion_actions`: há dois eventos, e o
segundo acabou de ser decidido. Tabela normalizada é o que fazer **se** aparecer
um terceiro.

Dívida que isso cria, e que está nomeada no PRD: `uploaded_at` sem qualificador
passa a significar "compra enviada", por acidente histórico - ele nasceu quando
havia um evento só. Renomear exigiria mexer no uploader e no
`resumo_de_conversoes` do PR #74 ao mesmo tempo, em produção.
"""
import os
import unittest

SETUP = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "scripts", "setup_database.py"))


def fonte():
    with open(SETUP, encoding="utf-8") as f:
        return f.read()


class TestAsColunasExistem(unittest.TestCase):
    def test_a_action_do_agendamento(self):
        texto = fonte()

        self.assertIn(
            "ADD COLUMN IF NOT EXISTS booking_conversion_action_id VARCHAR(30)",
            texto)

    def test_o_marcador_de_envio_do_agendamento(self):
        """Coluna própria: marcar `uploaded_at` faria uma conversão parecer
        enviada ao evento de compra sem ter sido."""
        texto = fonte()

        self.assertIn(
            "ADD COLUMN IF NOT EXISTS booking_uploaded_at TIMESTAMPTZ", texto)

    def test_o_tipo_acompanha_a_coluna_irma(self):
        """`VARCHAR(30)` é o que `offline_conversion_action_id` usa. Tipos
        diferentes para a mesma coisa é divergência esperando acontecer."""
        texto = fonte()

        self.assertIn("offline_conversion_action_id VARCHAR(30)", texto)
        self.assertIn("booking_conversion_action_id VARCHAR(30)", texto)

    def test_tem_indice_parcial_como_o_da_retratacao(self):
        """Serve à pergunta que a Lambda faz todo mês: o que ainda não subiu."""
        texto = fonte()

        self.assertIn("idx_lead_conversions_agendamento_a_subir", texto)
        self.assertIn("WHERE booking_uploaded_at IS NULL", texto)


class TestOCreateTableEstaEmSincronia(unittest.TestCase):
    """Convenção do `CLAUDE.md`. As três colunas de Ads nunca estiveram no
    `CREATE TABLE` de `clinics` - entraram só por migration. Numa base nova as
    migrations as acrescentariam de todo jeito, então listar não muda
    comportamento: muda o que o arquivo diz existir."""

    def test_clinics_lista_as_tres_colunas_de_ads(self):
        texto = fonte()
        i = texto.index("CREATE TABLE IF NOT EXISTS scheduler.clinics")
        bloco = texto[i:i + 3000]

        for coluna in ("google_ads_customer_id",
                       "offline_conversion_action_id",
                       "booking_conversion_action_id"):
            with self.subTest(coluna):
                self.assertIn(coluna, bloco)

    def test_lead_conversions_lista_as_duas_colunas_de_envio(self):
        texto = fonte()
        i = texto.index("CREATE TABLE IF NOT EXISTS scheduler.lead_conversions")
        bloco = texto[i:i + 1500]

        self.assertIn("uploaded_at TIMESTAMPTZ", bloco)
        self.assertIn("booking_uploaded_at TIMESTAMPTZ", bloco)


class TestSaoIdempotentes(unittest.TestCase):
    def test_tudo_com_IF_NOT_EXISTS(self):
        """O script é reexecutável por convenção do projeto."""
        texto = fonte()

        for trecho in ("ADD COLUMN IF NOT EXISTS booking_conversion_action_id",
                       "ADD COLUMN IF NOT EXISTS booking_uploaded_at",
                       "CREATE INDEX IF NOT EXISTS idx_lead_conversions_agendamento"):
            with self.subTest(trecho[:40]):
                self.assertIn(trecho, texto)


if __name__ == "__main__":
    unittest.main()
