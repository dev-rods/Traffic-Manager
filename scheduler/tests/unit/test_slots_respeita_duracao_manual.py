# -*- coding: utf-8 -*-
"""Os horários oferecidos usam a duração que a sessão vai ocupar de verdade.

Regressão de 19/09/2026, relatada pelo André: uma sessão com duração fixada em
75 minutos recebia horários calculados para 50, o teto da clínica. O endpoint de
`available-slots` reaplicava `duracao_da_sessao` por cima do número que o painel
mandava - e o painel já manda a duração EFETIVA desde o PR #56.

A tela então oferecia um horário em que a sessão não cabe, e a paciente seguinte
era marcada por cima. O conflito só apareceria ao salvar, ou não apareceria.

É o mesmo defeito do `reschedule_appointment`, do mesmo dia: a regra reaplicada
sobre um valor que já passou por ela. Corrigi um e não fui atrás do outro - e é
por isso que este teste mira o CONTRATO do endpoint, não só a conta.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.functions.availability import slots

CLINIC = "clinicaessenciaestetica-9668a4"

# A regra da Essência. O teto de 50 é o que engolia os 75.
REGRA = {"floor_minutes": 10, "ceiling_minutes": 50, "step_minutes": 5,
         "is_active": True}


def evento(total_duration=None):
    params = {"date": "2026-10-01", "serviceId": "s1"}
    if total_duration is not None:
        params["totalDuration"] = str(total_duration)
    return {
        "headers": {"x-api-key": "chave"},
        "pathParameters": {"clinicId": CLINIC},
        "queryStringParameters": params,
    }


class TestADuracaoChegaInteira(unittest.TestCase):
    """O que o painel manda é o que o motor recebe."""

    def _chama(self, total_duration):
        with mock.patch.object(slots, "require_api_key", return_value=("k", None)), \
             mock.patch.object(slots, "PostgresService"), \
             mock.patch.object(slots, "AvailabilityEngine") as Engine:
            motor = Engine.return_value
            motor.get_available_slots_multi.return_value = ["09:00"]
            resposta = slots.handler(evento(total_duration), None)
            return resposta, motor

    def test_setenta_e_cinco_minutos_chegam_como_setenta_e_cinco(self):
        """O caso do relato. Antes virava 50 no teto da clínica."""
        resposta, motor = self._chama(75)

        self.assertEqual(resposta["statusCode"], 200)
        motor.get_available_slots_multi.assert_called_once_with(CLINIC, "2026-10-01", 75)

    def test_duracao_abaixo_do_piso_tambem_passa_inteira(self):
        """Fixar 7 minutos é decisão de quem está na recepção. O piso de 10 é
        para o cálculo automático, não para a escolha dela."""
        _, motor = self._chama(7)

        motor.get_available_slots_multi.assert_called_once_with(CLINIC, "2026-10-01", 7)

    def test_duracao_dentro_da_regra_nao_muda(self):
        _, motor = self._chama(30)

        motor.get_available_slots_multi.assert_called_once_with(CLINIC, "2026-10-01", 30)

    def test_a_regra_da_clinica_saiu_deste_caminho(self):
        """`duracao_da_sessao` nao e mais importada aqui.

        Confere pela AST e nao pelo texto: o comentario que explica o defeito
        CITA o nome de proposito, para quem ler entender por que ele sumiu.
        """
        import ast
        import inspect

        importados = []
        for no in ast.walk(ast.parse(inspect.getsource(slots))):
            if isinstance(no, ast.ImportFrom):
                importados += [a.name for a in no.names]
            elif isinstance(no, ast.Import):
                importados += [a.name for a in no.names]

        self.assertNotIn("duracao_da_sessao", importados)
        self.assertNotIn("get_duration_rules", importados)


class TestSemDuracaoOCaminhoAntigoContinua(unittest.TestCase):
    def test_sem_totalDuration_usa_a_duracao_do_servico(self):
        """Quem não manda duração continua caindo no cálculo pelo serviço - é o
        caminho de quem ainda não escolheu áreas."""
        with mock.patch.object(slots, "require_api_key", return_value=("k", None)), \
             mock.patch.object(slots, "PostgresService"), \
             mock.patch.object(slots, "AvailabilityEngine") as Engine:
            motor = Engine.return_value
            motor.get_available_slots.return_value = ["09:00"]

            slots.handler(evento(None), None)

            motor.get_available_slots.assert_called_once_with(CLINIC, "2026-10-01", "s1")
            motor.get_available_slots_multi.assert_not_called()


class TestValorRuimE400(unittest.TestCase):
    """Dedo errado na URL é 400, nunca 500 - e nunca uma agenda calculada com
    duração absurda."""

    def _status(self, total_duration):
        with mock.patch.object(slots, "require_api_key", return_value=("k", None)), \
             mock.patch.object(slots, "PostgresService"), \
             mock.patch.object(slots, "AvailabilityEngine"):
            return slots.handler(evento(total_duration), None)["statusCode"]

    def test_valores_recusados(self):
        for valor in ("0", "-30", "abc", "9999", "3.5"):
            with self.subTest(valor=valor):
                self.assertEqual(self._status(valor), 400)


if __name__ == "__main__":
    unittest.main()
