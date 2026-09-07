# -*- coding: utf-8 -*-
"""A duração é a mesma quer o par venha em camelCase ou snake_case.

Em 07/09/2026 a Viviane teve o agendamento editado pelo painel: quatro áreas
somando 35 minutos, salvo com 15 e terminando 15 minutos depois do início.

A criação normalizava `serviceId/areaId` para `service_id/area_id`; a edição
passava o corpo HTTP cru. O filtro de `soma_das_areas` exigia snake_case e
descartava TODOS os pares - em silêncio, porque par descartado não levanta, só
soma zero. Com soma zero, o piso de 15 assumia e parecia um número plausível.

As duas metades do mesmo fluxo discordando, e o sintoma sendo um valor válido:
é o modo de falha mais caro desta base.
"""
import unittest
from unittest import mock

from src.services.duration_rules import (
    calcula_duracao,
    normaliza_pares,
    soma_das_areas,
)

CLINIC = "clinica-teste-0001"
REGRAS = {"floor_minutes": 15, "ceiling_minutes": 50, "step_minutes": 5, "is_active": True}

# As quatro áreas da Viviane: 5 + 8 + 2 + 20 = 35.
PARES_CAMEL = [
    {"serviceId": "s1", "areaId": "a-axilas"},
    {"serviceId": "s1", "areaId": "a-gluteo"},
    {"serviceId": "s1", "areaId": "a-mao"},
    {"serviceId": "s1", "areaId": "a-perna"},
]
PARES_SNAKE = [{"service_id": p["serviceId"], "area_id": p["areaId"]} for p in PARES_CAMEL]


def db_com_soma(total):
    db = mock.MagicMock()
    db.execute_query.side_effect = lambda sql, params=None: (
        [dict(REGRAS)] if "duration_rules" in sql else [{"total": total}]
    )
    return db


class TestNormalizaPares(unittest.TestCase):
    def test_camel_vira_snake(self):
        self.assertEqual(normaliza_pares(PARES_CAMEL), PARES_SNAKE)

    def test_snake_passa_intacto(self):
        self.assertEqual(normaliza_pares(PARES_SNAKE), PARES_SNAKE)

    def test_par_incompleto_sai(self):
        """Área removida do catálogo chega assim. Derrubar o agendamento por
        isso seria pior que ignorar o par."""
        self.assertEqual(normaliza_pares([{"serviceId": "s1"}, {"areaId": "a1"}, {}]), [])

    def test_lixo_nao_explode(self):
        self.assertEqual(normaliza_pares(None), [])
        self.assertEqual(normaliza_pares([]), [])
        self.assertEqual(normaliza_pares(["texto", 42, None]), [])


class TestSomaIgualNasDuasGrafias(unittest.TestCase):
    def test_camel_soma_o_mesmo_que_snake(self):
        self.assertEqual(soma_das_areas(db_com_soma(35), PARES_CAMEL), 35)
        self.assertEqual(soma_das_areas(db_com_soma(35), PARES_SNAKE), 35)

    def test_a_consulta_recebe_os_ids(self):
        """Antes o filtro esvaziava a lista e a consulta nem chegava a rodar."""
        db = db_com_soma(35)
        soma_das_areas(db, PARES_CAMEL)

        params = db.execute_query.call_args[0][1]
        self.assertIn("a-perna", params)


class TestOCasoDaViviane(unittest.TestCase):
    def test_quatro_areas_somando_35_nao_viram_15(self):
        """O piso é para sessão curta de verdade, não para lista descartada."""
        self.assertEqual(calcula_duracao(db_com_soma(35), CLINIC, PARES_CAMEL), 35)

    def test_o_piso_continua_valendo_quando_a_soma_e_curta(self):
        """O guardrail não pode ter sido desligado junto."""
        self.assertEqual(calcula_duracao(db_com_soma(6), CLINIC, PARES_CAMEL), 15)

    def test_sem_area_nenhuma_cai_no_piso(self):
        self.assertEqual(calcula_duracao(db_com_soma(0), CLINIC, []), 15)


if __name__ == "__main__":
    unittest.main()
