# -*- coding: utf-8 -*-
"""Cancelado e falta não viram registro de sessão (PRD 042).

A tela não oferece esses agendamentos - a listagem filtra `CONFIRMED`. Isto
cobre o caminho que NÃO passa pela tela: a aba aberta quando a recepção
cancela, e a chamada direta na rota.
"""
import json
import unittest
from unittest import mock

CLINICA = "clinica-x"
PACIENTE = "11111111-1111-1111-1111-111111111111"
AGENDAMENTO = "22222222-2222-2222-2222-222222222222"


class BancoFalso:
    """Responde por SQL, nunca `return_value` fixo.

    Dublê que responde igual a qualquer consulta foi o que fez três testes
    deste repositório lerem "contato silenciado" onde não havia (PRD 039).
    """

    def __init__(self, status="CONFIRMED", data="2026-11-07", existe=True):
        self.status = status
        self.data = data
        self.existe = existe
        self.inseriu = False

    def execute_query(self, sql, params=None):
        if "FROM scheduler.appointments" in sql:
            if not self.existe:
                return []
            return [{"appointment_date": self.data, "status": self.status}]
        if "skin_type" in sql:
            return [{"skin_type": None}]
        if "patient_session_applications" in sql:
            return []
        return []

    def execute_write_returning(self, sql, params=None):
        self.inseriu = True
        return {"id": "33333333-3333-3333-3333-333333333333",
                "clinic_id": CLINICA, "patient_id": PACIENTE,
                "appointment_id": AGENDAMENTO, "session_date": self.data,
                "version": 1, "edit_count": 0}

    def execute_write(self, sql, params=None):
        return 1

    def execute_many(self, sql, params_list=None):
        return len(params_list or [])


def chama(banco, corpo):
    from src.functions.patient_record import create

    evento = {
        "pathParameters": {"clinicId": CLINICA, "patientId": PACIENTE},
        "body": json.dumps(corpo),
        "headers": {},
    }
    with mock.patch.object(create, "PostgresService", return_value=banco), \
         mock.patch.object(create, "require_acesso", return_value=(mock.MagicMock(), None)), \
         mock.patch.object(create, "grava_aplicacoes"), \
         mock.patch.object(create, "registro_com_aplicacoes",
                           return_value={"id": "33333333-3333-3333-3333-333333333333"}), \
         mock.patch.object(create, "grava_trilha", create=True):
        resposta = create.handler(evento, None)
    return resposta["statusCode"], json.loads(resposta["body"])


class TestRecusa(unittest.TestCase):
    def test_cancelado_recusa_com_409(self):
        banco = BancoFalso(status="CANCELLED")
        codigo, corpo = chama(banco, {"appointmentId": AGENDAMENTO})
        self.assertEqual(codigo, 409)
        self.assertIn("cancelado", corpo["message"].lower())
        self.assertFalse(banco.inseriu, "não pode ter gravado nada")

    def test_falta_recusa_com_409(self):
        banco = BancoFalso(status="NO_SHOW")
        codigo, corpo = chama(banco, {"appointmentId": AGENDAMENTO})
        self.assertEqual(codigo, 409)
        self.assertIn("falta", corpo["message"].lower())
        self.assertFalse(banco.inseriu)

    def test_mandar_a_data_no_corpo_nao_pula_a_trava(self):
        """Era o furo: com `sessionDate` no corpo, o agendamento nunca era lido."""
        banco = BancoFalso(status="CANCELLED")
        codigo, _ = chama(banco, {"appointmentId": AGENDAMENTO,
                                  "sessionDate": "2026-11-07"})
        self.assertEqual(codigo, 409)
        self.assertFalse(banco.inseriu)

    def test_agendamento_de_outra_paciente_e_404(self):
        # O banco falso devolve [] porque a consulta agora exige patient_id.
        banco = BancoFalso(existe=False)
        codigo, corpo = chama(banco, {"appointmentId": AGENDAMENTO})
        self.assertEqual(codigo, 404)
        self.assertIn("paciente", corpo["message"].lower())


class TestAceita(unittest.TestCase):
    def test_confirmado_cria(self):
        banco = BancoFalso(status="CONFIRMED")
        codigo, _ = chama(banco, {"appointmentId": AGENDAMENTO})
        self.assertEqual(codigo, 201)
        self.assertTrue(banco.inseriu)

    def test_status_nulo_cria(self):
        """O banco permite nulo e prod não tem nenhum: barrar inventaria regra
        para um caso que não existe, e falharia fechado para dado histórico."""
        banco = BancoFalso(status=None)
        codigo, _ = chama(banco, {"appointmentId": AGENDAMENTO})
        self.assertEqual(codigo, 201)
        self.assertTrue(banco.inseriu)

    def test_sem_agendamento_cria_sessao_fora_do_sistema(self):
        banco = BancoFalso()
        codigo, _ = chama(banco, {"sessionDate": "2026-11-07"})
        self.assertEqual(codigo, 201)
        self.assertTrue(banco.inseriu)

    def test_a_data_continua_vindo_do_agendamento(self):
        banco = BancoFalso(status="CONFIRMED", data="2026-11-03")
        codigo, _ = chama(banco, {"appointmentId": AGENDAMENTO})
        self.assertEqual(codigo, 201)


if __name__ == "__main__":
    unittest.main()
