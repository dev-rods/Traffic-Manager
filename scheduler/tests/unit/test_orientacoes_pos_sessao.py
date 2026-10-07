# -*- coding: utf-8 -*-
"""O aviso pré-sessão chega inteiro, e não passa pelo modelo.

Antes disto, um filtro por palavra-chave escolhia itens do FAQ. Contra o FAQ
real da Essência ele puxava "O resultado é definitivo?" como se fosse
orientação e deixava de fora "Precisa levar algo para a sessão?", porque o texto
diz "gilete" e o filtro procurava "lâmina". O André então escreveu o aviso
exato - e exato quer dizer que ninguém reescreve, nem o modelo.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.conversation_agent import TOOLS_QUE_MARCAM_SESSAO
from src.services.orientacoes_pos_sessao import CHAVE_DO_TEMPLATE, TEXTO, texto


class TemplateFake:
    def __init__(self, conteudo="", erro=None):
        self.conteudo = conteudo
        self.erro = erro
        self.chaves_pedidas = []

    def get_and_render(self, clinic_id, chave, variables=None):
        self.chaves_pedidas.append(chave)
        if self.erro:
            raise self.erro
        return self.conteudo


class TestOTexto(unittest.TestCase):
    def test_tem_as_tres_partes_do_aviso(self):
        self.assertIn("IMPORTANTE SABER ANTES DA SUA SESSÃO DE LASER", TEXTO)
        self.assertIn("Antes da sessão:", TEXTO)
        self.assertIn("Nos avise antes de vir caso:", TEXTO)
        self.assertIn("Após a sessão:", TEXTO)

    def test_as_contraindicacoes_que_nao_podem_sumir(self):
        """Cada uma dessas é um motivo de a sessão não poder ser feita."""
        for termo in ("Roacutan", "gestante", "herpes ativa", "tatuagem",
                      "peeling", "ácidos", "cera, pinça"):
            with self.subTest(termo=termo):
                self.assertIn(termo, TEXTO)


class TestDeOndeVem(unittest.TestCase):
    def test_sem_template_proprio_usa_o_padrao(self):
        fake = TemplateFake(conteudo="")
        self.assertEqual(texto(fake, "c1"), TEXTO)
        self.assertEqual(fake.chaves_pedidas, [CHAVE_DO_TEMPLATE])

    def test_clinica_pode_ter_o_seu(self):
        self.assertEqual(texto(TemplateFake("Aviso da casa"), "c1"), "Aviso da casa")

    def test_template_so_com_espacos_nao_apaga_o_aviso(self):
        self.assertEqual(texto(TemplateFake("   \n  "), "c1"), TEXTO)

    def test_banco_fora_do_ar_ainda_avisa(self):
        """Sem isto, um erro de consulta manda a paciente para a sessão sem preparo."""
        self.assertEqual(texto(TemplateFake(erro=RuntimeError("timeout")), "c1"), TEXTO)


class TestQuandoSai(unittest.TestCase):
    def test_agendar_e_remarcar_avisam(self):
        self.assertIn("book_appointment", TOOLS_QUE_MARCAM_SESSAO)
        self.assertIn("reschedule_appointment", TOOLS_QUE_MARCAM_SESSAO)

    def test_cancelar_nao_avisa(self):
        """Quem cancelou não tem preparo a fazer."""
        self.assertNotIn("cancel_appointment", TOOLS_QUE_MARCAM_SESSAO)


class TestOFluxoDeterministico(unittest.TestCase):
    """A clinica antiga, sem agente, fecha agendamento pelo mesmo aviso."""

    def test_booked_anexa_o_aviso(self):
        from src.services.conversation_engine import ConversationEngine

        engine = object.__new__(ConversationEngine)
        engine.db = None
        engine.appointment_service = None
        engine.template_service = TemplateFake(conteudo="")
        engine._format_date_br = lambda d: "23/09/2026"
        engine._format_price_with_discount = lambda s: "R$ 175,00"
        engine._get_clinic = lambda c: {}

        sessao = {"appointment_id": "a-1", "selected_date": "2026-09-23",
                  "selected_time": "14:00", "total_duration_minutes": 10}
        _, conteudo = engine._on_enter_booked("c1", "5511999999999", sessao)

        self.assertIn(TEXTO, conteudo)
        self.assertEqual(
            [b["id"] for b in sessao["dynamic_buttons"]],
            ["confirm_read", "human"],
        )


if __name__ == "__main__":
    unittest.main()
