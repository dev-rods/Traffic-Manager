# -*- coding: utf-8 -*-
"""A sobreposicao de lembrete: viva ate o fim do dia da sessao, esconde cancelar
e remarcar quando ha site, libera confirm_attendance, e o bloco traz o link."""
import unittest
from datetime import date, datetime, time

import pytz

from src.services import lembrete as L

TZ = pytz.timezone("America/Sao_Paulo")
CLINIC_COM_SITE = {"timezone": "America/Sao_Paulo", "custom_domain": "agendar.x.com.br", "display_name": "X"}
CLINIC_SEM_SITE = {"timezone": "America/Sao_Paulo", "custom_domain": None, "display_name": "X"}
APPT = {"id": "a1", "appointment_date": date(2026, 11, 6), "start_time": time(9, 0), "areas": "Axilas, Virilha Completa"}

# 05/11/2026 12:00 BRT
AGORA = int(TZ.localize(datetime(2026, 11, 5, 12, 0)).timestamp())


def sessao(lembrete):
    return {"lembrete": lembrete}


class TestAbre(unittest.TestCase):
    def test_expira_no_fim_do_dia_da_sessao(self):
        l = L.abre(APPT, CLINIC_COM_SITE, agora=AGORA)
        self.assertEqual(l["appointment_id"], "a1")
        self.assertEqual(l["dia"], "2026-11-06")
        self.assertEqual(l["hora"], "09:00")
        fim = TZ.localize(datetime(2026, 11, 6, 23, 59, 59))
        self.assertEqual(l["expira_em"], int(fim.timestamp()))

    def test_aceita_data_e_hora_como_texto(self):
        l = L.abre({"id": 7, "appointment_date": "2026-11-06", "start_time": "14:30:00"}, CLINIC_SEM_SITE)
        self.assertEqual((l["appointment_id"], l["hora"], l["areas"]), ("7", "14:30", ""))


class TestVivo(unittest.TestCase):
    def test_vivo_antes_de_expirar(self):
        self.assertTrue(L.esta_vivo(sessao(L.abre(APPT, CLINIC_COM_SITE, AGORA)), AGORA))

    def test_morto_depois(self):
        l = L.abre(APPT, CLINIC_COM_SITE, AGORA)
        self.assertFalse(L.esta_vivo(sessao(l), l["expira_em"] + 1))

    def test_falha_fechada(self):
        self.assertFalse(L.esta_vivo({}, AGORA))
        self.assertFalse(L.esta_vivo(sessao({"expira_em": "x"}), AGORA))
        self.assertFalse(L.esta_vivo(sessao("lixo"), AGORA))
        self.assertFalse(L.esta_vivo(None, AGORA))

    def test_appointment_id_so_quando_vivo(self):
        l = L.abre(APPT, CLINIC_COM_SITE, AGORA)
        self.assertEqual(L.appointment_id(sessao(l), AGORA), "a1")
        self.assertIsNone(L.appointment_id(sessao(l), l["expira_em"] + 1))


class TestFerramentas(unittest.TestCase):
    def test_com_site_remove_saida_e_libera_confirmacao(self):
        s = sessao(L.abre(APPT, CLINIC_COM_SITE, AGORA))
        self.assertEqual(L.ferramentas_a_remover(s, CLINIC_COM_SITE, AGORA), L.FERRAMENTAS_DE_SAIDA)
        self.assertEqual(L.ferramentas_a_liberar(s, AGORA), {L.FERRAMENTA_DE_CONFIRMACAO})

    def test_sem_site_nao_remove_nada(self):
        s = sessao(L.abre(APPT, CLINIC_SEM_SITE, AGORA))
        self.assertEqual(L.ferramentas_a_remover(s, CLINIC_SEM_SITE, AGORA), frozenset())
        self.assertEqual(L.ferramentas_a_liberar(s, AGORA), {L.FERRAMENTA_DE_CONFIRMACAO})

    def test_morto_nao_mexe_em_nada(self):
        l = L.abre(APPT, CLINIC_COM_SITE, AGORA)
        depois = l["expira_em"] + 1
        self.assertEqual(L.ferramentas_a_remover(sessao(l), CLINIC_COM_SITE, depois), frozenset())
        self.assertEqual(L.ferramentas_a_liberar(sessao(l), depois), frozenset())


class TestBloco(unittest.TestCase):
    def test_com_site_tem_link_e_proibe_executar(self):
        b = L.bloco_de_prompt(sessao(L.abre(APPT, CLINIC_COM_SITE, AGORA)), CLINIC_COM_SITE, AGORA)
        self.assertIn("https://agendar.x.com.br/", b)
        self.assertIn("NÃO execute", b)
        self.assertIn("confirm_attendance", b)
        self.assertIn("06/11", b)
        self.assertIn("Axilas, Virilha Completa", b)

    def test_sem_site_diz_que_resolve_por_aqui(self):
        b = L.bloco_de_prompt(sessao(L.abre(APPT, CLINIC_SEM_SITE, AGORA)), CLINIC_SEM_SITE, AGORA)
        self.assertNotIn("http", b)
        self.assertIn("por aqui mesmo", b)

    def test_morto_e_vazio(self):
        l = L.abre(APPT, CLINIC_COM_SITE, AGORA)
        self.assertEqual(L.bloco_de_prompt(sessao(l), CLINIC_COM_SITE, l["expira_em"] + 1), "")


if __name__ == "__main__":
    unittest.main()
