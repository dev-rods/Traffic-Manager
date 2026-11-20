# -*- coding: utf-8 -*-
"""GET .../appointments/{id}/session-applications (PRD 051).

A montagem das aplicações a partir do agendamento tem UM lugar, o backend, e
este endpoint é como a tela chega nele. O nome comercial fica; o protocolo vai
como subtítulo. E o POST/PUT não aceitam mais registro vazio ou parcial.
"""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.patient_record import session_applications as handler_mod
from src.functions.patient_record import create as create_mod
from src.functions.patient_record import update as update_mod
from src.utils.acesso import ADMIN, Identidade

CLINICA = "clinica-x"
PACIENTE = "11111111-1111-1111-1111-111111111111"
AGENDAMENTO = "22222222-2222-2222-2222-222222222222"
REGISTRO = "33333333-3333-3333-3333-333333333333"
_ADMIN = Identidade(papel=ADMIN, chave_mestra=True)


class BancoFalso:
    def __init__(self, existe=True, pele="BRANCA", areas=None):
        self.existe = existe
        self.pele = pele
        self.areas = areas if areas is not None else [
            {"area_id": "a1", "area_name": "Perna Completa",
             "protocol_area_key": "meia_perna", "map_order": 0, "created_at": 0},
            {"area_id": "a2", "area_name": "Costeleta",
             "protocol_area_key": "costeleta", "map_order": 0, "created_at": 1},
            {"area_id": "a3", "area_name": "Virilha Completa + ânus",
             "protocol_area_key": "virilha_completa", "map_order": 1, "created_at": 2},
            {"area_id": "a3", "area_name": "Virilha Completa + ânus",
             "protocol_area_key": "regiao_perianal", "map_order": 2, "created_at": 2},
        ]
        self.consultas = []

    def execute_query(self, sql, params=None):
        self.consultas.append((sql, params))
        if "SELECT patient_id FROM scheduler.appointments" in sql:
            return [{"patient_id": PACIENTE}] if self.existe else []
        if "skin_type" in sql:
            return [{"skin_type": self.pele}]
        if "appointment_service_areas" in sql:
            return list(self.areas)
        return []


def _chama(banco, appointment_id=AGENDAMENTO):
    evento = {"headers": {"x-api-key": "k"},
              "pathParameters": {"clinicId": CLINICA, "appointmentId": appointment_id}}
    with mock.patch.object(handler_mod, "require_acesso", return_value=(_ADMIN, None)), \
         mock.patch.object(handler_mod, "PostgresService", return_value=banco):
        resposta = handler_mod.handler(evento, None)
    return resposta["statusCode"], json.loads(resposta["body"])


class TestEndpoint(unittest.TestCase):
    def test_nome_comercial_fica_e_o_protocolo_vai_de_subtitulo(self):
        codigo, corpo = _chama(BancoFalso())
        self.assertEqual(codigo, 200)
        perna = corpo["applications"][0]
        self.assertEqual(perna["area_name"], "Perna Completa")
        self.assertEqual(perna["protocol_area_name"], "Meia perna")
        self.assertEqual(perna["method"], "SHR")
        self.assertIsNotNone(perna["fluence_j"])

    def test_area_de_dois_metodos_entra_sem_metodo(self):
        _, corpo = _chama(BancoFalso())
        costeleta = corpo["applications"][1]
        self.assertEqual(costeleta["area_name"], "Costeleta")
        self.assertIsNone(costeleta["method"])

    def test_composta_vira_duas(self):
        _, corpo = _chama(BancoFalso())
        nomes = [(a["area_name"], a["protocol_area_key"]) for a in corpo["applications"][2:]]
        self.assertEqual(nomes, [("Virilha Completa + ânus", "virilha_completa"),
                                 ("Virilha Completa + ânus", "regiao_perianal")])
        self.assertEqual([a["display_order"] for a in corpo["applications"]], [0, 1, 2, 3])

    def test_pele_da_paciente_do_agendamento(self):
        banco = BancoFalso(pele="NEGRA")
        codigo, corpo = _chama(banco)
        self.assertEqual(corpo["skin_type"], "NEGRA")
        consulta_de_pele = [p for s, p in banco.consultas if "skin_type" in s]
        self.assertEqual(consulta_de_pele, [(PACIENTE,)])

    def test_fora_da_clinica_e_404(self):
        codigo, corpo = _chama(BancoFalso(existe=False))
        self.assertEqual(codigo, 404)

    def test_area_sem_mapa_entra_assim_mesmo(self):
        banco = BancoFalso(areas=[{"area_id": "a9", "area_name": "Costeletas",
                                   "protocol_area_key": None, "map_order": 0, "created_at": 0}])
        _, corpo = _chama(banco)
        ap = corpo["applications"][0]
        self.assertEqual(ap["area_name"], "Costeletas")
        self.assertIsNone(ap["protocol_area_key"])
        self.assertIsNone(ap["protocol_area_name"])


class BancoDeEscrita:
    def __init__(self):
        self.escreveu = False

    def execute_query(self, sql, params=None):
        if "FROM scheduler.appointments" in sql:
            return [{"appointment_date": "2026-11-07", "status": "CONFIRMED"}]
        if "patient_session_records" in sql:
            return [{"id": REGISTRO, "version": 1, "clinic_id": CLINICA}]
        if "skin_type" in sql:
            return [{"skin_type": None}]
        return []

    def execute_write_returning(self, sql, params=None):
        self.escreveu = True
        return {"id": REGISTRO, "version": 1}

    def execute_write(self, sql, params=None):
        self.escreveu = True
        return 1

    def execute_many(self, sql, params_list=None):
        self.escreveu = True
        return len(params_list or [])


def _post(corpo):
    banco = BancoDeEscrita()
    evento = {"headers": {"x-api-key": "k"},
              "pathParameters": {"clinicId": CLINICA, "patientId": PACIENTE},
              "body": json.dumps(corpo)}
    with mock.patch.object(create_mod, "require_acesso", return_value=(_ADMIN, None)), \
         mock.patch.object(create_mod, "PostgresService", return_value=banco):
        r = create_mod.handler(evento, None)
    return r["statusCode"], json.loads(r["body"]), banco


def _put(corpo):
    banco = BancoDeEscrita()
    evento = {"headers": {"x-api-key": "k"},
              "pathParameters": {"clinicId": CLINICA, "recordId": REGISTRO},
              "body": json.dumps(corpo)}
    with mock.patch.object(update_mod, "require_acesso", return_value=(_ADMIN, None)), \
         mock.patch.object(update_mod, "PostgresService", return_value=banco):
        r = update_mod.handler(evento, None)
    return r["statusCode"], json.loads(r["body"]), banco


class TestNenhumRegistroIncompleto(unittest.TestCase):
    def test_post_sem_applications_e_400(self):
        codigo, corpo, banco = _post({"appointmentId": AGENDAMENTO})
        self.assertEqual(codigo, 400)
        self.assertIn("applications", corpo["message"])
        self.assertFalse(banco.escreveu)

    def test_post_com_lista_vazia_e_400(self):
        codigo, corpo, banco = _post({"appointmentId": AGENDAMENTO, "applications": []})
        self.assertEqual(codigo, 400)
        self.assertEqual(corpo["message"], "Informe ao menos uma área aplicada.")
        self.assertFalse(banco.escreveu)

    def test_post_sem_metodo_cita_a_area(self):
        codigo, corpo, _ = _post({"appointmentId": AGENDAMENTO,
                                  "applications": [{"areaName": "Costeleta"}]})
        self.assertEqual(codigo, 400)
        self.assertEqual(corpo["message"], "Costeleta: escolha o método.")

    def test_post_shr_sem_energia_cita_o_campo(self):
        codigo, corpo, _ = _post({"appointmentId": AGENDAMENTO, "applications": [
            {"areaName": "Axilas", "method": "SHR", "fluenceJ": 8}]})
        self.assertEqual(codigo, 400)
        self.assertEqual(corpo["message"], "Axilas: informe Energia (kJ).")

    def test_post_completo_grava(self):
        codigo, _, banco = _post({"appointmentId": AGENDAMENTO, "applications": [
            {"areaName": "Perna Completa", "protocolAreaKey": "meia_perna",
             "method": "SHR", "fluenceJ": 8, "energyKj": 8}]})
        self.assertEqual(codigo, 201)
        self.assertTrue(banco.escreveu)

    def test_put_com_lista_vazia_e_400(self):
        codigo, corpo, _ = _put({"applications": []})
        self.assertEqual(codigo, 400)
        self.assertEqual(corpo["message"], "Informe ao menos uma área aplicada.")

    def test_put_incompleto_e_400(self):
        codigo, corpo, _ = _put({"applications": [
            {"areaName": "Buço", "method": "SHR_STACKING", "fluenceJ": 6, "stacks": 3}]})
        self.assertEqual(codigo, 400)
        self.assertEqual(corpo["message"], "Buço: informe Passadas.")


if __name__ == "__main__":
    unittest.main()
