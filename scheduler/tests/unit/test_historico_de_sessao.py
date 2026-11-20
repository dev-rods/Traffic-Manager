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
    exige_aplicacoes,
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

    def test_area_composta_vira_tres_aplicacoes_com_nome_por_parte(self):
        """No catálogo é uma área; no protocolo são três (PRD 052). Cada parte
        leva o nome do protocolo e guarda a origem comercial."""
        aps = aplicacoes_do_agendamento(db_com_areas([
            area("Virilha Completa + ânus", "virilha_completa", ordem=0),
            area("Virilha Completa + ânus", "interno_virilha", ordem=1),
            area("Virilha Completa + ânus", "regiao_perianal", ordem=2),
        ]), APPT, "BRANCA")

        self.assertEqual([a["area_name"] for a in aps],
                         ["Virilha completa", "Grandes lábios", "Perianal"])
        self.assertEqual({a["source_area_name"] for a in aps}, {"Virilha Completa + ânus"})
        self.assertEqual(aps[0]["method"], "SHR")
        self.assertEqual(aps[0]["fluence_j"], 7)
        self.assertIsNone(aps[1]["method"], "três métodos no protocolo: ela escolhe")
        self.assertIsNone(aps[1]["fluence_j"])
        self.assertEqual(aps[2]["method"], "SHR_STACKING")
        self.assertEqual(aps[2]["stacks"], 3)
        self.assertEqual(aps[2]["passes"], 2)

    def test_virilha_cavada_traz_grandes_labios(self):
        aps = aplicacoes_do_agendamento(db_com_areas([
            area("Virilha Cavada", "virilha_cavada", ordem=0),
            area("Virilha Cavada", "interno_virilha", ordem=1),
        ]), APPT, "BRANCA")

        self.assertEqual([a["area_name"] for a in aps], ["Virilha cavada", "Grandes lábios"])
        self.assertEqual([a["source_area_name"] for a in aps], ["Virilha Cavada"] * 2)

    def test_area_de_uma_chave_nao_tem_origem(self):
        """Uma chave só: nome comercial (PRD 051), sem origem."""
        aps = aplicacoes_do_agendamento(db_com_areas([
            area("Perna Completa", "meia_perna", area_id="a1"),
            area("Axilas", "axilas", area_id="a2", ordem=1),
        ]), APPT, "BRANCA")

        self.assertEqual([a["area_name"] for a in aps], ["Perna Completa", "Axilas"])
        self.assertEqual([a["source_area_name"] for a in aps], [None, None])

    def test_duas_areas_diferentes_nao_sao_confundidas_com_composta(self):
        """Contar chaves por área, não por posição: duas áreas de uma chave cada
        não podem virar "desmembrada"."""
        aps = aplicacoes_do_agendamento(db_com_areas([
            area("Axilas", "axilas", area_id="a1", ordem=0),
            area("Lombar", "lombar", area_id="a2", ordem=1),
        ]), APPT, "BRANCA")
        self.assertEqual([a["source_area_name"] for a in aps], [None, None])

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

    def test_meio_gluteo_tem_valor_proprio_em_cada_pele(self):
        """Ficou sem linha na pele negra entre 19/09 e a resposta do André,
        justamente porque copiar os 8 J da branca sugeriria acima do protocolo
        dela - o glúteo inteiro na negra é 7 J."""
        for pele, fluencia, energia in (("BRANCA", 8, 7), ("NEGRA", 7, 6)):
            with self.subTest(pele=pele):
                aps = aplicacoes_do_agendamento(
                    db_com_areas([area("1/2 Glúteo", "meio_gluteo")]), APPT, pele)

                self.assertEqual(aps[0]["method"], "SHR")
                self.assertEqual(aps[0]["fluence_j"], fluencia)
                self.assertEqual(aps[0]["energy_kj"], energia)

    def test_agendamento_sem_area(self):
        self.assertEqual(aplicacoes_do_agendamento(db_com_areas([]), APPT, "BRANCA"), [])

    def test_perna_completa_mantem_o_nome_comercial(self):
        """PRD 051: a perna inteira herda o PARAMETRO da metade, não o nome.
        Até 19/11/2026 a tela trocava e o registro dizia "Meia perna" numa
        sessão que depilou a perna inteira."""
        aps = aplicacoes_do_agendamento(
            db_com_areas([area("Perna Completa", "meia_perna")]), APPT, "BRANCA")

        self.assertEqual(aps[0]["area_name"], "Perna Completa")
        self.assertEqual(aps[0]["protocol_area_name"], "Meia perna")
        self.assertEqual(aps[0]["method"], "SHR")
        self.assertIsNotNone(aps[0]["fluence_j"])

    def test_sem_mapa_nao_ha_nome_de_protocolo(self):
        aps = aplicacoes_do_agendamento(db_com_areas([area("Área nova")]), APPT, "BRANCA")
        self.assertIsNone(aps[0]["protocol_area_name"])


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
                with self.assertRaises(RegistroInvalido) as ctx:
                    valida_aplicacoes([{"area_name": "Axilas", "method": "SHR",
                                        "fluence_j": valor, "energy_kj": 8}])
                self.assertEqual(str(ctx.exception),
                                 "Axilas: Fluência (J) precisa ser maior que zero.")

    def test_texto_no_lugar_de_numero_e_recusado(self):
        with self.assertRaises(RegistroInvalido):
            valida_aplicacoes([{"area_name": "Axilas", "method": "SHR",
                                "fluence_j": "muito", "energy_kj": 8}])

    def test_metodo_sem_sugestao_no_protocolo_e_aceito(self):
        """O protocolo diz qual método COMEÇAR, não qual é permitido.

        Axilas só tem SHR e HR no material. A profissional pode aplicar
        Stacking nela e registrar - decisão do André em 19/09/2026, depois de a
        tela ter transformado "sem sugestão" em "proibido".
        """
        limpa = valida_aplicacoes([{
            "area_name": "Axilas", "protocol_area_key": "axilas",
            "method": "SHR_STACKING", "fluence_j": 6, "stacks": 3, "passes": 2,
        }])[0]

        self.assertEqual(limpa["method"], "SHR_STACKING")
        self.assertEqual(limpa["fluence_j"], 6)
        self.assertEqual(limpa["stacks"], 3)

    # ── PRD 051: nenhum registro incompleto ─────────────────────────────
    # Antes nada era obrigatório e a sessão inteira ia ao banco como "sem
    # parâmetro registrado". Quem não aplicou numa área a remove.

    def test_aplicacao_sem_metodo_e_recusada(self):
        for ap in ({"area_name": "Costeleta"}, {"area_name": "Costeleta", "method": ""},
                   {"area_name": "Costeleta", "method": None, "fluence_j": 6}):
            with self.subTest(ap=ap):
                with self.assertRaises(RegistroInvalido) as ctx:
                    valida_aplicacoes([ap])
                self.assertEqual(str(ctx.exception), "Costeleta: escolha o método.")

    def test_shr_sem_energia_e_recusado(self):
        """O caso do relato: Fluência preenchida, Energia vazia, e salvava."""
        for energia in (None, ""):
            with self.subTest(energia=energia):
                with self.assertRaises(RegistroInvalido) as ctx:
                    valida_aplicacoes([{"area_name": "Axilas", "method": "SHR",
                                        "fluence_j": 8, "energy_kj": energia}])
                self.assertEqual(str(ctx.exception), "Axilas: informe Energia (kJ).")

    def test_stacking_exige_fluencia_stacks_e_passadas(self):
        base = {"area_name": "Buço", "method": "SHR_STACKING",
                "fluence_j": 6, "stacks": 3, "passes": 2}
        for campo, rotulo in (("fluence_j", "Fluência (J)"), ("stacks", "Stacks"),
                              ("passes", "Passadas")):
            with self.subTest(campo=campo):
                ap = {**base, campo: None}
                with self.assertRaises(RegistroInvalido) as ctx:
                    valida_aplicacoes([ap])
                self.assertEqual(str(ctx.exception), f"Buço: informe {rotulo}.")

    def test_hr_exige_fluencia_e_energia(self):
        with self.assertRaises(RegistroInvalido):
            valida_aplicacoes([{"area_name": "Buço", "method": "HR", "fluence_j": 17}])
        limpa = valida_aplicacoes([{"area_name": "Buço", "method": "HR",
                                    "fluence_j": 17, "energy_kj": 1}])[0]
        self.assertEqual(limpa["energy_kj"], 1.0)

    def test_origem_passa_cortada_e_vazia_vira_nulo(self):
        limpa = valida_aplicacoes([{"area_name": "Perianal", "method": "SHR_STACKING",
                                    "fluence_j": 6, "stacks": 3, "passes": 2,
                                    "source_area_name": "  Virilha Completa + ânus  "}])[0]
        self.assertEqual(limpa["source_area_name"], "Virilha Completa + ânus")
        limpa = valida_aplicacoes([{"area_name": "Axilas", "method": "SHR",
                                    "fluence_j": 7, "energy_kj": 8, "source_area_name": ""}])[0]
        self.assertIsNone(limpa["source_area_name"])

    def test_completa_passa_e_descarta_o_que_o_metodo_nao_usa(self):
        limpa = valida_aplicacoes([{"area_name": "Área nova", "method": "SHR",
                                    "fluence_j": 7, "energy_kj": 8, "stacks": 3}])[0]
        self.assertEqual((limpa["fluence_j"], limpa["energy_kj"]), (7.0, 8.0))
        self.assertIsNone(limpa["stacks"])

    def test_o_nome_e_cortado_no_tamanho_da_coluna(self):
        limpa = valida_aplicacoes([{"area_name": "x" * 300, "method": "SHR",
                                    "fluence_j": 7, "energy_kj": 8}])[0]
        self.assertEqual(len(limpa["area_name"]), 160)

    def test_a_ordem_e_preservada(self):
        shr = {"method": "SHR", "fluence_j": 7, "energy_kj": 8}
        limpas = valida_aplicacoes([
            {"area_name": "Axilas", **shr}, {"area_name": "Buço", **shr}, {"area_name": "Nuca", **shr},
        ])
        self.assertEqual([l["display_order"] for l in limpas], [0, 1, 2])

    def test_lista_vazia_valida_mas_nao_se_grava(self):
        self.assertEqual(valida_aplicacoes([]), [])
        self.assertEqual(valida_aplicacoes(None), [])
        for vazio in ([], None):
            with self.assertRaises(RegistroInvalido) as ctx:
                exige_aplicacoes(vazio)
            self.assertEqual(str(ctx.exception), "Informe ao menos uma área aplicada.")

    def test_exige_aplicacoes_devolve_a_lista_cheia(self):
        lista = [{"area_name": "Axilas"}]
        self.assertIs(exige_aplicacoes(lista), lista)

    def test_o_fallback_pelo_agendamento_nao_volta_ao_create(self):
        """A montagem é do GET session-applications; o POST só grava o que a
        profissional conferiu. Com a validação nova, o fallback antigo daria
        400 em toda área de dois métodos."""
        import os
        caminho = os.path.join(os.path.dirname(__file__), "..", "..", "src",
                               "functions", "patient_record", "create.py")
        with open(caminho, encoding="utf-8") as f:
            fonte = f.read()
        self.assertNotIn("aplicacoes_do_agendamento(", fonte)
        self.assertIn("exige_aplicacoes(", fonte)


class TestVariosMetodosNaMesmaArea(unittest.TestCase):
    """PRD 030: 1 área -> N métodos -> N parâmetros, uma linha por método.

    Não houve migração: o banco já era uma linha por área + método. Este teste
    trava que a validação continua aceitando a mesma área repetida, que é o
    que a tela manda agora.
    """

    def test_axilas_com_shr_e_hr(self):
        limpas = valida_aplicacoes([
            {"area_id": "a1", "area_name": "Axilas", "protocol_area_key": "axilas",
             "method": "SHR", "fluence_j": 8, "energy_kj": 8, "display_order": 0},
            {"area_id": "a1", "area_name": "Axilas", "protocol_area_key": "axilas",
             "method": "HR", "fluence_j": 20, "energy_kj": 1, "display_order": 1},
        ])
        self.assertEqual(len(limpas), 2)
        self.assertEqual([l["area_name"] for l in limpas], ["Axilas", "Axilas"])
        self.assertEqual([l["method"] for l in limpas], ["SHR", "HR"])
        self.assertEqual([(l["fluence_j"], l["energy_kj"]) for l in limpas],
                         [(8.0, 8.0), (20.0, 1.0)])
        self.assertEqual([l["display_order"] for l in limpas], [0, 1])

    def test_mesmo_metodo_duas_vezes_e_aceito(self):
        # Duas passadas de SHR com fluências diferentes: conduta é de quem aplica.
        limpas = valida_aplicacoes([
            {"area_name": "Axilas", "method": "SHR", "fluence_j": 8, "energy_kj": 8},
            {"area_name": "Axilas", "method": "SHR", "fluence_j": 6, "energy_kj": 8},
        ])
        self.assertEqual([l["fluence_j"] for l in limpas], [8.0, 6.0])

    def test_interno_de_virilha_sem_area_do_catalogo(self):
        limpas = valida_aplicacoes([
            {"area_id": None, "area_name": "Interno de Virilha",
             "protocol_area_key": "interno_virilha", "method": "SHR",
             "fluence_j": 6, "energy_kj": 3},
        ])
        self.assertIsNone(limpas[0]["area_id"])
        self.assertEqual(limpas[0]["protocol_area_key"], "interno_virilha")


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
