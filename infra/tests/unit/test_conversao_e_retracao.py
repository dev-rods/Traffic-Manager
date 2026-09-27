# -*- coding: utf-8 -*-
"""A conversão sobe no agendamento, e é desfeita se a pessoa cancela.

Decisão do André em 27/09/2026. Antes, o uploader tinha
`a.appointment_date < CURRENT_DATE`: só subia depois da sessão acontecer,
como proteção contra cancelamento.

O custo era alto demais. A conversão comercial acontece quando a pessoa
AGENDA; segurar o sinal até a sessão atrasava o aprendizado do Google em
semanas. Medido na Essência: 3 conversões elegíveis contra 7 com a regra nova.

O cancelamento passa a ser tratado onde deve - por RETRACTION, depois. E isso
não é detalhe: 5 das 12 conversões da Essência estavam CANCELLED (42%). Sem
retratar, o algoritmo aprenderia a perseguir quem cancela.
"""
import ast
import os
import unittest

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "src")
UPLOADER = os.path.join(RAIZ, "functions", "conversions", "uploader.py")
CLIENTE = os.path.join(RAIZ, "services", "google_ads_client_service.py")


def fonte(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


class TestSessaoFuturaSobe(unittest.TestCase):
    def test_o_filtro_de_sessao_passada_saiu(self):
        """Era ele que segurava a conversão até a sessão acontecer.

        Procura `AND a.appointment_date`, e não a expressão solta: o docstring
        da função menciona o filtro para explicar por que ele saiu, e uma busca
        crua no arquivo inteiro acha a explicação e reprova o código correto.
        """
        texto = fonte(UPLOADER)

        self.assertNotIn("AND a.appointment_date < CURRENT_DATE", texto)
        # e o docstring CONTINUA podendo falar dele
        self.assertIn("appointment_date", texto,
                      "a explicação da mudança não deveria sumir")

    def test_o_carimbo_enviado_nunca_e_futuro(self):
        """O Google recusa conversão com data no futuro. Sessão marcada para
        daqui a duas semanas sobe com o carimbo de agora."""
        texto = fonte(UPLOADER)

        self.assertIn("LEAST(lc.conversion_date, NOW())", texto)

    def test_a_janela_de_90_dias_continua(self):
        """O Google recusa clique com mais de 90 dias. Esse filtro não era
        sobre cancelamento e não podia sair junto."""
        self.assertIn("INTERVAL '90 days'", fonte(UPLOADER))

    def test_so_agendamento_confirmado_sobe(self):
        self.assertIn("a.status = 'CONFIRMED'", fonte(UPLOADER))


class TestRetratacao(unittest.TestCase):
    def test_o_servico_tem_o_metodo(self):
        self.assertIn("def retract_offline_conversions", fonte(CLIENTE))

    def test_usa_o_tipo_RETRACTION(self):
        texto = fonte(CLIENTE)

        self.assertIn("ConversionAdjustmentTypeEnum.RETRACTION", texto)
        self.assertIn("ConversionAdjustmentUploadService", texto)

    def test_identifica_a_conversao_pelo_par_gclid_data(self):
        """É o par (gclid, conversion_date_time) que acha a conversão original
        no Google. Carimbo diferente devolve CONVERSION_NOT_FOUND."""
        texto = fonte(CLIENTE)

        self.assertIn("gclid_date_time_pair", texto)

    def test_o_uploader_so_retrata_o_que_subiu(self):
        """`uploaded_at IS NOT NULL` é a condição que importa: só há o que
        desfazer se chegou a existir no Google."""
        texto = fonte(UPLOADER)

        self.assertIn("lc.uploaded_at IS NOT NULL", texto)
        self.assertIn("lc.retracted_at IS NULL", texto)
        self.assertIn("a.status = 'CANCELLED'", texto)

    def test_a_retratacao_roda_mesmo_sem_nada_a_subir(self):
        """Uma clínica sem conversão nova pode ter muito o que desfazer.

        O `if not pending: continue` pulava a clínica inteira - a retratação
        precisa vir ANTES dele.
        """
        texto = fonte(UPLOADER)

        pos_retratacao = texto.index("_retract_for_clinic(db, ads_service")
        pos_continue = texto.index("if not pending:")

        self.assertLess(pos_retratacao, pos_continue,
                        "a retratação tem de rodar antes do continue")

    def test_nao_marca_retratado_quando_o_lote_falha(self):
        """Marcar como retratado o que talvez não tenha sido deixaria a
        conversão viva no Google para sempre: ninguém tentaria de novo."""
        texto = fonte(CLIENTE)
        trecho = texto[texto.index("def retract_offline_conversions"):]

        self.assertIn('"retracted_identifiers": []', trecho)
        self.assertIn("tratando lote como falho", trecho)


class TestAColunaExiste(unittest.TestCase):
    def test_migration_cria_retracted_at(self):
        caminho = os.path.join(
            RAIZ, "..", "..", "scheduler", "src", "scripts", "setup_database.py")
        texto = fonte(os.path.normpath(caminho))

        self.assertIn("retracted_at", texto)
        self.assertIn("ADD COLUMN IF NOT EXISTS retracted_at", texto)


class TestOUploaderCompila(unittest.TestCase):
    def test_ast_valido(self):
        for caminho in (UPLOADER, CLIENTE):
            with self.subTest(os.path.basename(caminho)):
                ast.parse(fonte(caminho))


if __name__ == "__main__":
    unittest.main()
