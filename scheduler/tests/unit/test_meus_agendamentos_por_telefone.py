# -*- coding: utf-8 -*-
""""Meus agendamentos" encontra quem acabou de agendar.

Em 18/10/2026 o André agendou pelo site, recebeu a confirmação no WhatsApp,
viu o agendamento no painel e abriu "Meus agendamentos": "Nenhum agendamento
encontrado". O site mandava o telefone como o campo mostra, `(11) 99999-0000`,
e a listagem comparava isso por igualdade com `patients.phone`, gravado
`5511999990000`. O token passava (normaliza) e o cancelamento também
(normaliza), só a listagem não.

As consultas abaixo são respondidas pelo telefone que CHEGA ao SQL: se a
normalização sumir, o teste volta a ver lista vazia.
"""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.appointment_service import AppointmentService

CLINIC = "clinica-teste-0001"
APPT = "cccccccc-0000-0000-0000-000000000001"
SP = "5511999990000"
# Santa Catarina: fora dos DDDs 11-28 o WhatsApp entrega muito número sem o 9,
# e é assim que o bot grava o paciente.
SC_SEM_NOVE = "554797053940"


class Db:
    def __init__(self, gravado):
        self.gravado = gravado
        self.params = []

    def execute_query(self, sql, params=None):
        self.params.append(params)
        if "FROM scheduler.appointments" in sql and "p.phone = ANY(%s)" in sql:
            telefones = next(p for p in params if isinstance(p, list))
            if self.gravado not in telefones:
                return []
            return [{"id": APPT, "full_name": "Maria Silva", "appointment_date": "2026-10-25",
                     "start_time": "10:00:00", "status": "CONFIRMED", "service_name": "Laser"}]
        return []


class TestListagem(unittest.TestCase):
    def lista(self, gravado, digitado):
        return AppointmentService(Db(gravado)).get_active_appointments_by_phone(CLINIC, digitado)

    def test_telefone_como_o_site_manda(self):
        r = self.lista(SP, "(11) 99999-0000")
        self.assertEqual([a["full_name"] for a in r], ["Maria Silva"])

    def test_telefone_normalizado_continua_funcionando(self):
        self.assertEqual(len(self.lista(SP, SP)), 1)

    def test_paciente_do_bot_sem_o_nono_digito(self):
        self.assertEqual(len(self.lista(SC_SEM_NOVE, "(47) 99705-3940")), 1)

    def test_em_sao_paulo_tirar_o_nove_seria_outra_pessoa(self):
        self.assertEqual(self.lista("551199990000", "(11) 99999-0000"), [])

    def test_vazio_nao_consulta(self):
        db = Db(SP)
        self.assertEqual(AppointmentService(db).get_active_appointments_by_phone(CLINIC, ""), [])
        self.assertEqual(db.params, [])


def evento(body):
    return {"pathParameters": {"clinicId": CLINIC, "appointmentId": APPT},
            "headers": {}, "body": json.dumps(body)}


class TestCancelamento(unittest.TestCase):
    """O que a listagem mostra, a pessoa consegue cancelar."""

    modulo = "src.functions.public_booking.cancel_appointment"

    def setUp(self):
        self.db = mock.MagicMock()
        self.service = mock.MagicMock()
        self.service.cancel_appointment.return_value = {"id": APPT, "status": "CANCELLED"}
        for p in (
            mock.patch(f"{self.modulo}.require_booking_intake_api_key", return_value=("k", None)),
            mock.patch(f"{self.modulo}.verify_token", return_value=True),
            mock.patch(f"{self.modulo}.PostgresService", return_value=self.db),
            mock.patch(f"{self.modulo}.AppointmentService.completo", return_value=self.service),
        ):
            p.start()
            self.addCleanup(p.stop)

    def cancela(self, gravado, digitado):
        from src.functions.public_booking.cancel_appointment import handler

        def consulta(sql, params):
            return [{"id": APPT}] if gravado in params[2] else []

        self.db.execute_query.side_effect = consulta
        return handler(evento({"phone": digitado, "token": "t"}), None)

    def test_paciente_do_bot_sem_o_nono_digito(self):
        self.assertEqual(self.cancela(SC_SEM_NOVE, "(47) 99705-3940")["statusCode"], 200)
        self.service.cancel_appointment.assert_called_once_with(APPT)

    def test_outro_numero_nao_cancela(self):
        self.assertEqual(self.cancela(SP, "(47) 99705-3940")["statusCode"], 404)
        self.service.cancel_appointment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
