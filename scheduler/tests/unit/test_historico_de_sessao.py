# -*- coding: utf-8 -*-
"""O registro nasce do agendamento, e o que ele aceita gravar.

O valor da feature está em preencher quase sozinho: a profissional acabou de
atender, abre o registro e as áreas já estão lá com o parâmetro do protocolo.
Se isso não funcionar, ela volta para o caderno.
"""
import unittest
from unittest import mock

from src.services.historico_de_sessao import (
    RegistroInvalido,
    aplicacoes_do_agendamento,
    grava_trilha,
    valida_aplicacoes,
)

APPT = "11111111-1111-1111-1111-111111111111"


def db_com_areas(areas):
    """`areas` são as linhas que o JOIN com o mapa devolveria."""
    db = mock.MagicMock()
    db.execute_query.return_value = areas
    return db


def area(nome, chave=None, area_id="a1", ordem=0):
    return {"area_id": area_id, "area_name": nome,
            "protocol_area_key": chave, "map_order": ordem, "created_at": ordem}


class TestONascimentoDoRegistro(unittest.TestCase):
    def test_area_simples_vem_com_metodo_e_parametro(self):
        """Lombar só existe no SHR, então a tela já deixa escolhido."""
        aps = aplicacoes_do_agendamento(
            db_com_areas([area("Lombar", "lombar")]), APPT, "BRANCA")

        self.assertEqual(len(aps), 1)
        self.assertEqual(aps[0]["method"], "SHR")
        self.assertEqual(aps[0]["fluence_j"], 7)
        self.assertEqual(aps[0]["energy_kj"], 8)

    def test_o_tipo_de_pele_muda_o_parametro(self):
        """É o motivo de skin_type existir."""
        db = db_com_areas([area("Lombar", "lombar")])
        branca = aplicacoes_do_agendamento(db, APPT, "BRANCA")[0]
        negra = aplicacoes_do_agendamento(db, APPT, "NEGRA")[0]

        self.assertEqual((branca["fluence_j"], branca["energy_kj"]), (7, 8))
        self.assertEqual((negra["fluence_j"], negra["energy_kj"]), (5, 7))

    def test_area_de_mais_de_um_metodo_fica_em_branco(self):
        """Buço tem Stacking e HR; Axilas tem SHR e HR. Escolher por ela seria
        decidir conduta clínica, e a diferença entre 7 J no SHR e 17 J no HR não
        é detalhe."""
        for nome, chave in (("Buço", "buco"), ("Axilas", "axilas")):
            with self.subTest(area=nome):
                aps = aplicacoes_do_agendamento(
                    db_com_areas([area(nome, chave)]), APPT, "BRANCA")

                self.assertIsNone(aps[0]["method"])
                self.assertIsNone(aps[0]["fluence_j"])

    def test_area_composta_vira_duas_aplicacoes(self):
        """No catálogo é uma área; no protocolo são duas, com métodos
        diferentes. É o que ela de fato aplica."""
        aps = aplicacoes_do_agendamento(db_com_areas([
            area("Virilha Completa + ânus", "virilha_completa", ordem=0),
            area("Virilha Completa + ânus", "regiao_perianal", ordem=1),
        ]), APPT, "BRANCA")

        self.assertEqual(len(aps), 2)
        self.assertEqual(aps[0]["method"], "SHR")
        self.assertEqual(aps[0]["fluence_j"], 7)
        self.assertEqual(aps[1]["method"], "SHR_STACKING")
        self.assertEqual(aps[1]["stacks"], 3)
        self.assertEqual(aps[1]["passes"], 2)

    def test_area_sem_mapa_entra_sem_parametro(self):
        """Sem sugestão é resposta válida. O que não pode é inventar."""
        aps = aplicacoes_do_agendamento(
            db_com_areas([area("Área que ela inventou", None)]), APPT, "BRANCA")

        self.assertEqual(aps[0]["area_name"], "Área que ela inventou")
        self.assertIsNone(aps[0]["method"])
        self.assertIsNone(aps[0]["fluence_j"])

    def test_sem_tipo_de_pele_nao_ha_sugestao(self):
        """Paciente sem tipo de pele marcado: a tela pede, não chuta."""
        aps = aplicacoes_do_agendamento(
            db_com_areas([area("Lombar", "lombar")]), APPT, None)

        self.assertEqual(aps[0]["method"], "SHR")
        self.assertIsNone(aps[0]["fluence_j"])

    def test_meio_gluteo_na_pele_negra_fica_sem_sugestao(self):
        """O protocolo só tem a linha da pele branca, de propósito. Cair para
        ela sugeriria 8 J numa pele cujo glúteo inteiro é 7."""
        aps = aplicacoes_do_agendamento(
            db_com_areas([area("1/2 Glúteo", "meio_gluteo")]), APPT, "NEGRA")

        self.assertEqual(aps[0]["method"], "SHR")
        self.assertIsNone(aps[0]["fluence_j"])

    def test_agendamento_sem_area(self):
        self.assertEqual(aplicacoes_do_agendamento(db_com_areas([]), APPT, "BRANCA"), [])


class TestValidacao(unittest.TestCase):
    def test_o_nome_da_area_e_obrigatorio(self):
        """É o snapshot que sobrevive ao catálogo. Sem ele o histórico não diz
        o que foi tratado."""
        for ap in ({"area_name": ""}, {"area_name": "  "}, {}):
            with self.subTest(ap=ap):
                with self.assertRaises(RegistroInvalido):
                    valida_aplicacoes([ap])

    def test_metodo_desconhecido_e_recusado(self):
        with self.assertRaises(RegistroInvalido):
            valida_aplicacoes([{"area_name": "Axilas", "method": "LASER_MAGICO"}])

    def test_campo_que_o_metodo_nao_usa_vira_nulo(self):
        """Tela desatualizada mandando stacks num SHR sujaria a consulta que
        justifica a tabela existir."""
        limpa = valida_aplicacoes([{
            "area_name": "Axilas", "method": "SHR",
            "fluence_j": 7, "energy_kj": 8, "stacks": 3, "passes": 2,
        }])[0]

        self.assertEqual(limpa["fluence_j"], 7)
        self.assertEqual(limpa["energy_kj"], 8)
        self.assertIsNone(limpa["stacks"])
        self.assertIsNone(limpa["passes"])

    def test_o_stacking_guarda_stacks_e_nao_energia(self):
        limpa = valida_aplicacoes([{
            "area_name": "Buço", "method": "SHR_STACKING",
            "fluence_j": 6, "stacks": 3, "passes": 2, "energy_kj": 99,
        }])[0]

        self.assertEqual(limpa["stacks"], 3)
        self.assertIsNone(limpa["energy_kj"])

    def test_valor_zero_ou_negativo_e_recusado(self):
        for valor in (0, -5):
            with self.subTest(valor=valor):
                with self.assertRaises(RegistroInvalido):
                    valida_aplicacoes([{"area_name": "Axilas", "method": "SHR",
                                        "fluence_j": valor}])

    def test_texto_no_lugar_de_numero_e_recusado(self):
        with self.assertRaises(RegistroInvalido):
            valida_aplicacoes([{"area_name": "Axilas", "method": "SHR",
                                "fluence_j": "muito"}])

    def test_aplicacao_sem_metodo_e_valida(self):
        """Área fora do protocolo: ela escreve o que fez sem método."""
        limpa = valida_aplicacoes([{"area_name": "Área nova"}])[0]

        self.assertIsNone(limpa["method"])
        self.assertIsNone(limpa["fluence_j"])

    def test_o_nome_e_cortado_no_tamanho_da_coluna(self):
        limpa = valida_aplicacoes([{"area_name": "x" * 300}])[0]
        self.assertEqual(len(limpa["area_name"]), 160)

    def test_a_ordem_e_preservada(self):
        limpas = valida_aplicacoes([
            {"area_name": "Axilas"}, {"area_name": "Buço"}, {"area_name": "Nuca"},
        ])
        self.assertEqual([l["display_order"] for l in limpas], [0, 1, 2])

    def test_lista_vazia(self):
        self.assertEqual(valida_aplicacoes([]), [])
        self.assertEqual(valida_aplicacoes(None), [])


class TestTrilha(unittest.TestCase):
    def test_grava_o_estado_completo(self):
        db = mock.MagicMock()
        grava_trilha(db, "r1", "clinica", "CREATE",
                     {"id": "r1", "applications": [{"area_name": "Axilas"}]}, "Ana")

        sql, params = db.execute_write.call_args[0]
        self.assertIn("patient_session_record_audit", sql)
        self.assertIn("CREATE", params)
        self.assertIn("Axilas", params[3])

    def test_acao_desconhecida_e_recusada(self):
        with self.assertRaises(RegistroInvalido):
            grava_trilha(mock.MagicMock(), "r1", "c", "APAGAR_TUDO", {})

    def test_falhar_a_trilha_nao_derruba_o_atendimento(self):
        """A profissional não pode ficar sem registrar porque a auditoria
        falhou. Mas o log é ERROR: trilha que para de receber em silêncio é
        defeito grave num prontuário."""
        db = mock.MagicMock()
        db.execute_write.side_effect = Exception("banco fora")

        with self.assertLogs("src.services.historico_de_sessao", "ERROR") as log:
            grava_trilha(db, "r1", "c", "UPDATE", {})

        self.assertIn("FALHA ao gravar a trilha", log.output[0])


if __name__ == "__main__":
    unittest.main()
