# -*- coding: utf-8 -*-
"""Pelo painel, quem decide a estreia é a recepção - nunca o banco.

Decisão do André em 09/09/2026, revertendo a de 07/09. A contagem automática só
enxerga os agendamentos deste banco, e a Essência atende desde antes dele
existir: ela diria "primeira vez" para cliente antiga, na frente dela.

O elo frágil é o handler passar `None` por descuido - `None` é justamente o
valor que devolve a decisão ao sistema, então o padrão voltaria sozinho e em
silêncio. Por isso o teste olha o argumento, não só o efeito.
"""
import json
import unittest
from unittest import mock

CLINIC = "clinicaessenciaestetica-9668a4"


def chama_o_handler(corpo):
    """Roda o handler de verdade e devolve o kwargs que chegou ao service."""
    from src.functions.appointment import create as modulo

    evento = {
        "pathParameters": {"clinicId": CLINIC},
        "headers": {"x-api-key": "k"},
        "body": json.dumps(corpo),
    }
    service = mock.MagicMock()
    service.create_appointment.return_value = {"id": "ap1"}

    with mock.patch.object(modulo, "require_api_key", return_value=("k", None)), \
         mock.patch.object(modulo, "PostgresService"), \
         mock.patch.object(modulo, "AppointmentService", return_value=service), \
         mock.patch.object(modulo, "_serialize_row", side_effect=lambda r: r):
        modulo.handler(evento, None)

    service.create_appointment.assert_called_once()
    return service.create_appointment.call_args.kwargs


BASE = {
    "clinicId": CLINIC,
    "phone": "5511970522647",
    "serviceId": "s1",
    "date": "2026-09-23",
    "time": "14:00",
    "fullName": "Maria",
}


class TestEstreiaPeloPainel(unittest.TestCase):
    def test_sem_o_campo_o_padrao_e_desmarcado(self):
        kwargs = chama_o_handler(dict(BASE))
        self.assertIs(kwargs["is_first_visit"], False)

    def test_nunca_manda_none(self):
        """`None` devolveria a decisão ao sistema, que é o que se reverteu."""
        for corpo in (dict(BASE), {**BASE, "isFirstVisit": None}):
            with self.subTest(corpo=corpo):
                self.assertIsNotNone(chama_o_handler(corpo)["is_first_visit"])

    def test_marcada_vai_marcada(self):
        kwargs = chama_o_handler({**BASE, "isFirstVisit": True})
        self.assertIs(kwargs["is_first_visit"], True)

    def test_desmarcada_explicita_vai_desmarcada(self):
        kwargs = chama_o_handler({**BASE, "isFirstVisit": False})
        self.assertIs(kwargs["is_first_visit"], False)


if __name__ == "__main__":
    unittest.main()
