# -*- coding: utf-8 -*-
"""O handler de edição passa a duração para a troca de áreas.

O serviço pode aceitar o parâmetro e o handler não passá-lo - e aí o defeito da
Larissa continua exatamente igual, com o teste do serviço verde. É a mesma
lição de [test_trava_de_areas_ligada]: a função certa, não chamada, não protege
ninguém.

Este teste mira a ORDEM e os ARGUMENTOS das chamadas, que é o que o bug de
20/09/2026 quebrou.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.functions.appointment import update as handler_mod
from src.services.appointment_service import SEM_MUDANCA

# O handler passou a autorizar por PAPEL (21/09/2026). Estes testes cobrem a
# REGRA DE NEGOCIO, entao entram como administrador: quem cobre a autorizacao e
# o test_acesso_por_papel.
from src.utils.acesso import ADMIN, Identidade

_ADMIN = Identidade(papel=ADMIN, chave_mestra=True)


APPT = "11111111-1111-1111-1111-111111111111"
PARES = [{"serviceId": "s1", "areaId": "a1"}]


def chama(corpo):
    """Roda o handler e devolve o AppointmentService dublado."""
    servico = mock.MagicMock()
    servico.update_appointment_services.return_value = {
        "manual_duration_descartada": False
    }
    db = mock.MagicMock()
    db.execute_query.return_value = [
        {"appointment_date": "2026-09-23", "start_time": "12:30:00",
         "original_price_cents": 19500}
    ]

    evento = {
        "headers": {"x-api-key": "k"},
        "pathParameters": {"clinicId": "c", "appointmentId": APPT},
        "body": None,
    }
    with mock.patch.object(handler_mod, "require_acesso", return_value=(_ADMIN, None)), \
         mock.patch.object(handler_mod, "parse_body", return_value=corpo), \
         mock.patch.object(handler_mod, "PostgresService", return_value=db), \
         mock.patch.object(handler_mod, "AppointmentService", return_value=servico):
        resposta = handler_mod.handler(evento, None)
    return servico, resposta


class TestTrocaDeAreaComDuracao(unittest.TestCase):
    """O caso da Larissa: trocar a área e fixar 10 minutos, no mesmo pedido."""

    def test_a_duracao_vai_junto_na_troca_de_areas(self):
        servico, _ = chama({
            "serviceId": "s1", "serviceAreaPairs": PARES,
            "manualDurationMinutes": 10,
        })

        _, kwargs = servico.update_appointment_services.call_args
        self.assertEqual(kwargs.get("manual_duration_minutes"), 10,
                         "sem isto a troca de área confere o conflito com a "
                         "duração recalculada e recusa")

    def test_e_a_duracao_nao_e_aplicada_duas_vezes(self):
        """Repetir refaria a conta e conferiria o conflito de novo, pelo mesmo
        motivo e com o mesmo resultado."""
        servico, _ = chama({
            "serviceId": "s1", "serviceAreaPairs": PARES,
            "manualDurationMinutes": 10,
        })

        servico.set_manual_duration.assert_not_called()

    def test_a_resposta_cita_a_duracao(self):
        _, resposta = chama({
            "serviceId": "s1", "serviceAreaPairs": PARES,
            "manualDurationMinutes": 10,
        })

        import json

        self.assertEqual(resposta["statusCode"], 200)
        # O corpo vem com escape JSON; comparar a string crua procuraria
        # "duração" onde está "dura\u00e7\u00e3o".
        self.assertIn("duração", json.loads(resposta["body"])["message"])


class TestTrocaDeAreaSemDuracao(unittest.TestCase):
    def test_passa_SEM_MUDANCA_e_nao_None(self):
        """`None` significa "volte ao cálculo". Passá-lo aqui transformaria
        toda troca de área num pedido de limpar o override."""
        servico, _ = chama({"serviceId": "s1", "serviceAreaPairs": PARES})

        _, kwargs = servico.update_appointment_services.call_args
        self.assertIs(kwargs.get("manual_duration_minutes"), SEM_MUDANCA)


class TestDuracaoSozinha(unittest.TestCase):
    def test_sem_troca_de_area_usa_set_manual_duration(self):
        servico, _ = chama({"manualDurationMinutes": 10})

        servico.update_appointment_services.assert_not_called()
        servico.set_manual_duration.assert_called_once()

    def test_null_explicito_volta_ao_calculo(self):
        servico, _ = chama({"manualDurationMinutes": None})

        args, _ = servico.set_manual_duration.call_args
        self.assertIsNone(args[1])


class TestConflitoFicaParaAEtapaCerta(unittest.TestCase):
    """Quando um reschedule vem a seguir, a data aqui ainda é a antiga:
    conferir contra ela acusaria conflito num dia que ninguém vai ocupar."""

    def test_com_remarcacao_a_troca_de_areas_nao_confere_conflito(self):
        servico, _ = chama({
            "serviceId": "s1", "serviceAreaPairs": PARES,
            "manualDurationMinutes": 10,
            "date": "2026-09-29", "time": "09:00",
        })

        _, kwargs = servico.update_appointment_services.call_args
        self.assertFalse(kwargs.get("verificar_conflito"))
        servico.reschedule_appointment.assert_called_once()

    def test_sem_remarcacao_confere_na_hora(self):
        servico, _ = chama({
            "serviceId": "s1", "serviceAreaPairs": PARES,
            "manualDurationMinutes": 10,
        })

        _, kwargs = servico.update_appointment_services.call_args
        self.assertTrue(kwargs.get("verificar_conflito"))


if __name__ == "__main__":
    unittest.main()
