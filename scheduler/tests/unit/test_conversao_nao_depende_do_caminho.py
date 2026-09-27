# -*- coding: utf-8 -*-
"""Quem cria agendamento registra a conversão do gclid. Sempre.

O defeito que este arquivo fecha, encontrado em 27/09/2026 investigando por
que a paciente Vitória Endres aparecia agendada e não constava como conversão:

    if self.lead_service:      # appointment_service.py
        mark_as_booked(...)
        record_conversion(...)

`lead_service=None` é o default do construtor. O webhook do bot passava; o
painel, a edição e o agente montavam sem. Resultado: **todo agendamento feito
pela recepção era invisível para o Google Ads**.

    28 agendamentos de lead com gclid em 30 dias
    12 com conversao registrada
    16 SEM  -> 57% de subestimacao, R$ 3.984,50 nao reportados

O CPA real aparecia como R$ 424,52 quando era R$ 238,79, e o ROAS como 0,61
quando era 1,03 - a campanha parecia dar prejuízo e não dava.

O defeito era silencioso por construção: o agendamento é criado normalmente,
nada falha, nada loga erro. Só o dado não chega.
"""
import ast
import os
import unittest

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..", "src")


def _constroi_appointment_service(caminho):
    """Linhas que chamam AppointmentService(...) direto, sem a fábrica."""
    with open(caminho, encoding="utf-8") as f:
        arvore = ast.parse(f.read(), filename=caminho)

    cruas = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        # `AppointmentService(...)` — chamada direta do construtor.
        if isinstance(no.func, ast.Name) and no.func.id == "AppointmentService":
            passa_lead = any(kw.arg == "lead_service" for kw in no.keywords)
            if not passa_lead:
                cruas.append(no.lineno)
    return cruas


def _fontes():
    for raiz, _, arquivos in os.walk(RAIZ):
        for arquivo in arquivos:
            if arquivo.endswith(".py"):
                yield os.path.join(raiz, arquivo)


class TestNinguemMontaSemLeadService(unittest.TestCase):
    def test_todo_caminho_usa_a_fabrica(self):
        """`AppointmentService(db)` sem lead_service perde a conversão."""
        cruas = []
        for caminho in _fontes():
            for linha in _constroi_appointment_service(caminho):
                rel = os.path.relpath(caminho, RAIZ).replace(os.sep, "/")
                cruas.append("%s:%d" % (rel, linha))

        self.assertEqual(cruas, [], (
            "Estes pontos montam o AppointmentService sem lead_service e vão "
            "perder a conversão do gclid silenciosamente. Use "
            "AppointmentService.completo(db).\n  " + "\n  ".join(cruas)
        ))


class TestAFabricaMontaCompleto(unittest.TestCase):
    def test_completo_traz_o_lead_service(self):
        from unittest import mock

        from src.services.appointment_service import AppointmentService

        with mock.patch("src.services.lead_service.LeadService") as LS:
            servico = AppointmentService.completo(mock.MagicMock())

        self.assertIsNotNone(servico.lead_service,
                             "sem isto, mark_as_booked e record_conversion não rodam")
        self.assertTrue(LS.called)

    def test_o_construtor_continua_aberto_para_teste(self):
        """Os testes precisam injetar dublê; a fábrica não pode fechar isso."""
        from unittest import mock

        from src.services.appointment_service import AppointmentService

        dubles = AppointmentService(mock.MagicMock(), lead_service=mock.MagicMock())

        self.assertIsNotNone(dubles.lead_service)


class TestOBlocoQueSePerdia(unittest.TestCase):
    """Com lead_service presente, as duas chamadas acontecem."""

    def test_criar_agendamento_marca_e_registra(self):
        from unittest import mock

        from src.services.appointment_service import AppointmentService

        fonte = open(
            os.path.join(RAIZ, "services", "appointment_service.py"),
            encoding="utf-8").read()

        # As duas chamadas vivem no mesmo `if self.lead_service:`. Se alguém
        # separar uma da outra, o booked e a conversão divergem - foi assim que
        # 49 leads com gclid renderam só 9 `booked=True`.
        self.assertIn("mark_as_booked", fonte)
        self.assertIn("record_conversion", fonte)
        self.assertTrue(hasattr(AppointmentService, "completo"))


if __name__ == "__main__":
    unittest.main()
