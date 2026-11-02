# -*- coding: utf-8 -*-
"""O backfill liga o passado com a MESMA função do create (PRD 035).

Dry-run não escreve; `--aplicar` escreve uma vez; a segunda execução é no-op;
importação fica de fora.
"""
import os
import unittest
from datetime import date, datetime, timedelta

os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.scripts import backfill_reagendamentos as mod

CLINIC = "clinica-1"
T0 = datetime(2026, 10, 21, 12, 30)


class BancoDeMentira:
    """Guarda agendamentos num dicionário e responde às três consultas que o
    script e `reagendamento.py` fazem. O vínculo é gravado de verdade, para
    a idempotência ser medida e não presumida."""

    def __init__(self, linhas):
        self.linhas = {l["id"]: dict(l) for l in linhas}
        self.escritas = 0

    def _candidato(self, p):
        cands = [
            c for c in self.linhas.values()
            if c["clinic_id"] == p["clinic"] and str(c["patient_id"]) == p["patient"]
            and c["status"] == "CANCELLED" and c.get("rescheduled_to_id") is None
            and c["id"] != p["novo"]
            and p["criado_em"] - timedelta(minutes=p["janela"]) <= c["updated_at"]
            <= p["criado_em"] + timedelta(minutes=p["folga"])
        ]
        cands.sort(key=lambda c: c["updated_at"], reverse=True)
        return cands[:1]

    def execute_query(self, sql, params=None):
        if "ORDER BY created_at" in sql:
            return sorted(
                (dict(l) for l in self.linhas.values() if l["clinic_id"] == params[0]),
                key=lambda l: l["created_at"])
        if "ORDER BY c.updated_at DESC LIMIT 1" in sql:
            return self._candidato(params)
        raise AssertionError(sql)

    def execute_write_returning(self, sql, params=None):
        assert "SET rescheduled_to_id" in sql
        self.escritas += 1
        cand = self._candidato(params)
        if not cand:
            return None
        self.linhas[cand[0]["id"]]["rescheduled_to_id"] = params["novo"]
        return {"id": cand[0]["id"]}


def ag(id, status, data, created, updated=None, patient="p1", clinic=CLINIC):
    return {"id": id, "clinic_id": clinic, "patient_id": patient, "status": status,
            "appointment_date": data, "created_at": created,
            "updated_at": updated or created, "rescheduled_to_id": None}


def cenario():
    return BancoDeMentira([
        # Remarcação clássica: cancelou 12:30, criou 12:31.
        ag("antigo", "CANCELLED", date(2026, 10, 21), T0 - timedelta(days=3), updated=T0),
        ag("novo", "CONFIRMED", date(2026, 10, 22), T0 + timedelta(minutes=1)),
        # Cancelamento de verdade: ninguém criou nada depois.
        ag("so-cancelou", "CANCELLED", date(2026, 10, 23), T0 - timedelta(days=2),
           updated=T0 + timedelta(hours=5)),
        # Importação: cancelado em 09/09 com data de 2025.
        ag("import-antigo", "CANCELLED", date(2025, 10, 29), datetime(2026, 9, 8, 23, 0),
           updated=datetime(2026, 9, 8, 23, 4)),
        ag("import-novo", "CONFIRMED", date(2026, 3, 25), datetime(2026, 9, 8, 23, 5)),
    ])


class TestBackfill(unittest.TestCase):

    def test_dry_run_lista_e_nao_escreve(self):
        db = cenario()
        pares = mod.roda(db, CLINIC, aplicar=False, saida=lambda *_: None)
        self.assertEqual(pares, [("antigo", "novo")])
        self.assertEqual(db.escritas, 0)
        self.assertIsNone(db.linhas["antigo"]["rescheduled_to_id"])

    def test_aplicar_grava_uma_vez_e_a_segunda_e_no_op(self):
        db = cenario()
        pares = mod.roda(db, CLINIC, aplicar=True, saida=lambda *_: None)
        self.assertEqual(pares, [("antigo", "novo")])
        self.assertEqual(db.linhas["antigo"]["rescheduled_to_id"], "novo")
        self.assertIsNone(db.linhas["so-cancelou"]["rescheduled_to_id"])
        self.assertIsNone(db.linhas["import-antigo"]["rescheduled_to_id"])

        de_novo = mod.roda(db, CLINIC, aplicar=True, saida=lambda *_: None)
        self.assertEqual(de_novo, [])

    def test_importacao_fica_de_fora(self):
        db = cenario()
        pares = mod.roda(db, CLINIC, aplicar=False, saida=lambda *_: None)
        self.assertNotIn(("import-antigo", "import-novo"), pares)

    def test_saida_diz_o_que_faria(self):
        linhas = []
        mod.roda(cenario(), CLINIC, aplicar=False, saida=linhas.append)
        self.assertTrue(any(l.startswith("LIGARIA 2026-10-21 -> 2026-10-22") for l in linhas))
        self.assertIn("a ligar: 1  (dry-run; use --aplicar para gravar)", linhas[-1])

    def test_argumentos(self):
        self.assertEqual(mod._argumentos(["c1"]), (["c1"], False, mod.DESDE_PADRAO))
        self.assertEqual(mod._argumentos(["c1", "--aplicar", "--desde", "2026-10-01"]),
                         (["c1"], True, "2026-10-01"))


if __name__ == "__main__":
    unittest.main()
