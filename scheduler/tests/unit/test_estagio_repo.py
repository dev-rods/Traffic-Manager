# -*- coding: utf-8 -*-
"""Escrita do estagio: so grava quando muda, e toda mudanca vira evento."""
import unittest
from datetime import datetime, timezone

from src.services import estagio_do_lead as e
from src.services import estagio_repo as repo

AGORA = datetime(2026, 11, 21, tzinfo=timezone.utc)


class BancoFalso:
    def __init__(self):
        self.escritas = []

    def execute_write(self, sql, params=None):
        self.escritas.append((" ".join(sql.split()), params))
        return 1


def lead(**kw):
    base = {"id": "11111111-1111-1111-1111-111111111111", "clinic_id": "c1",
            "stage": None, "stage_source": None, "stage_reason": None}
    base.update(kw)
    return base


class TestGravaEstagio(unittest.TestCase):
    def test_mudanca_grava_lead_e_evento(self):
        db = BancoFalso()
        ok = repo.grava_estagio(db, lead(), e.Decisao(e.SEM_CONVERSA, e.REGRA))
        self.assertTrue(ok)
        sqls = [s for s, _ in db.escritas]
        self.assertTrue(any("UPDATE scheduler.leads SET stage" in s for s in sqls))
        self.assertTrue(any("INSERT INTO scheduler.lead_stage_events" in s for s in sqls))
        evento = [p for s, p in db.escritas if "lead_stage_events" in s][0]
        self.assertEqual(evento[2], None)            # de
        self.assertEqual(evento[3], e.SEM_CONVERSA)  # para

    def test_igual_nao_grava_evento_mas_atualiza_ultima_mensagem(self):
        db = BancoFalso()
        ok = repo.grava_estagio(db, lead(stage=e.SUMIU, stage_source=e.REGRA),
                                e.Decisao(e.SUMIU, e.REGRA), ultima_em=AGORA, ultima_de="NOS")
        self.assertFalse(ok)
        sqls = [s for s, _ in db.escritas]
        self.assertFalse(any("lead_stage_events" in s for s in sqls))
        self.assertEqual(len(sqls), 1)
        self.assertIn("ultima_mensagem_em", sqls[0])
        self.assertNotIn("stage =", sqls[0])

    def test_manual_preserva_motivo_existente(self):
        db = BancoFalso()
        l = lead(stage=e.NAO_AGENDOU, stage_source=e.MANUAL, stage_reason="achou caro")
        self.assertFalse(repo.grava_estagio(db, l, e.Decisao(e.NAO_AGENDOU, e.MANUAL)))

    def test_motivo_novo_com_mesmo_estagio_grava(self):
        db = BancoFalso()
        l = lead(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_reason="vai pensar")
        self.assertTrue(repo.grava_estagio(db, l, e.Decisao(e.NAO_AGENDOU, e.MODELO, "achou caro")))

    def test_mesmo_estagio_pela_regra_mantem_o_motivo_do_modelo(self):
        # A regra devolve NAO_AGENDOU/MODELO sem motivo quando mantem o veredito;
        # o motivo gravado pelo modelo nao pode sumir.
        db = BancoFalso()
        l = lead(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_reason="achou caro")
        self.assertFalse(repo.grava_estagio(db, l, e.Decisao(e.NAO_AGENDOU, e.MODELO)))

    def test_estagio_novo_pela_regra_limpa_o_motivo(self):
        db = BancoFalso()
        l = lead(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_reason="achou caro")
        repo.grava_estagio(db, l, e.Decisao(e.AGUARDANDO_NOS, e.REGRA))
        upd = [p for s, p in db.escritas if "UPDATE scheduler.leads SET stage" in s][0]
        self.assertIsNone(upd[1])

    def test_manual_leva_usuario_no_evento(self):
        db = BancoFalso()
        repo.grava_estagio(db, lead(), e.Decisao(e.NAO_E_LEAD, e.MANUAL, "fornecedor"), usuario_id="u1")
        evento = [p for s, p in db.escritas if "lead_stage_events" in s][0]
        self.assertIn("u1", evento)
        self.assertIn("fornecedor", evento)


class TestMarcas(unittest.TestCase):
    def test_tentativa_gera_evento_sem_mudar_estagio(self):
        db = BancoFalso()
        repo.registra_tentativa(db, lead(stage=e.SUMIU), "ainda_aberto")
        s, p = db.escritas[0]
        self.assertIn("lead_stage_events", s)
        self.assertIn("ainda_aberto", p)
        self.assertEqual(p[3], e.SUMIU)

    def test_marcas_de_tempo(self):
        db = BancoFalso()
        repo.marca_triagem(db, "id1")
        repo.marca_desfecho_tentado(db, "id1")
        self.assertIn("triagem_feita_em", db.escritas[0][0])
        self.assertIn("desfecho_tentado_em", db.escritas[1][0])


if __name__ == "__main__":
    unittest.main()
