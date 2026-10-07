# -*- coding: utf-8 -*-
"""Quem está pisando na clínica pela primeira vez, e o que acontece se cancelar.

A marca fica gravada no agendamento porque a atendente precisa poder desmarcar -
a pessoa pode ter vindo antes por fora do sistema. Campo gravado exige cuidado
com a conta que o gera: era feita em dois lugares (desconto de primeira sessão e
mais nada), e duas contas para a mesma pergunta divergem em silêncio.
"""
import unittest
from unittest import mock

from src.services.primeira_visita import e_primeira_visita, passa_a_marca_adiante

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"


def db_com(total):
    db = mock.MagicMock()
    db.execute_query.return_value = [{"total": total}]
    return db


class TestEhPrimeiraVisita(unittest.TestCase):
    def test_sem_sessao_anterior(self):
        self.assertTrue(e_primeira_visita(db_com(0), CLINIC, PHONE))

    def test_com_sessao_anterior(self):
        self.assertFalse(e_primeira_visita(db_com(3), CLINIC, PHONE))

    def test_cancelada_nao_conta(self):
        """Quem marcou, desmarcou e voltou continua estreando: a sessão que não
        aconteceu não é uma visita."""
        db = db_com(0)
        e_primeira_visita(db, CLINIC, PHONE)

        self.assertIn("status = 'CONFIRMED'", db.execute_query.call_args[0][0])

    def test_ignora_o_proprio_agendamento(self):
        """A pergunta é feita depois do INSERT - sem isso ele contaria a si
        mesmo e nenhuma estreia seria marcada."""
        db = db_com(0)
        e_primeira_visita(db, CLINIC, PHONE, ignorar_id="ap1")

        sql, params = db.execute_query.call_args[0]
        self.assertIn("a.id <> %s::uuid", sql)
        self.assertIn("ap1", params)

    def test_falha_no_banco_nao_marca(self):
        """Falha fechada: marcar "primeira vez" em cliente antigo constrange na
        recepção mais do que deixar de marcar uma estreia."""
        db = mock.MagicMock()
        db.execute_query.side_effect = RuntimeError("banco fora")

        self.assertFalse(e_primeira_visita(db, CLINIC, PHONE))


class TestCancelarPassaAMarca(unittest.TestCase):
    """Decisão do André: cancelou a estreia, a próxima sessão vira a estreia."""

    def _db(self, era_primeira=True, tem_herdeiro=True):
        db = mock.MagicMock()
        db.execute_query.return_value = [
            {"patient_id": "p1", "clinic_id": CLINIC, "is_first_visit": era_primeira}]
        db.execute_write_returning.return_value = {"id": "ap2"} if tem_herdeiro else None
        return db

    def test_a_proxima_sessao_herda(self):
        db = self._db()

        self.assertTrue(passa_a_marca_adiante(db, "ap1"))
        sql = db.execute_write_returning.call_args[0][0]
        self.assertIn("is_first_visit = TRUE", sql)

    def test_o_cancelado_perde_a_marca(self):
        """Ela ficaria numa linha cancelada, que ninguém olha."""
        db = self._db()
        passa_a_marca_adiante(db, "ap1")

        self.assertIn("is_first_visit = FALSE", db.execute_write.call_args[0][0])

    def test_herda_quem_vem_antes_na_agenda_e_nao_quem_foi_criado_antes(self):
        """Quem estreia é quem chega primeiro na clínica."""
        db = self._db()
        passa_a_marca_adiante(db, "ap1")

        self.assertIn("ORDER BY appointment_date, start_time",
                      db.execute_write_returning.call_args[0][0])

    def test_cancelar_sessao_comum_nao_mexe_em_nada(self):
        db = self._db(era_primeira=False)

        self.assertFalse(passa_a_marca_adiante(db, "ap1"))
        db.execute_write.assert_not_called()

    def test_sem_proxima_sessao_ninguem_herda(self):
        db = self._db(tem_herdeiro=False)

        self.assertFalse(passa_a_marca_adiante(db, "ap1"))

    def test_falha_nao_derruba_o_cancelamento(self):
        """A paciente pediu para cancelar. Falhar por causa de uma marca visual
        seria trocar o essencial pelo enfeite."""
        db = mock.MagicMock()
        db.execute_query.side_effect = RuntimeError("banco fora")

        self.assertFalse(passa_a_marca_adiante(db, "ap1"))


class TestFonteUnica(unittest.TestCase):
    def test_o_desconto_usa_a_mesma_funcao(self):
        """Eram duas contas para a mesma pergunta. Uma marca a agenda, a outra
        dá desconto - divergindo, a paciente ganha desconto de estreia numa
        sessão que a agenda não marca como estreia."""
        import inspect
        from src.services.ai_tools import ToolExecutor

        fonte = inspect.getsource(ToolExecutor._tool_calculate_discount)
        self.assertIn("e_primeira_visita(", fonte)
        self.assertNotIn("SELECT COUNT(*) as cnt FROM scheduler.appointments", fonte)


class DbRoteado:
    """Responde por conteúdo do SQL. `MagicMock` puro devolve mock onde o código
    espera int, e o teste morre longe do que se quer medir."""

    def __init__(self):
        self.escritas = []

    def execute_query(self, sql, params=None):
        if "FROM scheduler.patients" in sql:
            return [{"id": "p1", "deleted_at": None, "name": "Maria"}]
        if "FROM scheduler.services" in sql:
            return [{"id": "s1", "duration_minutes": 20, "name": "Laser",
                     "price_cents": 9500}]
        if "duration_rules" in sql:
            return [{"floor_minutes": 15, "ceiling_minutes": 50,
                     "step_minutes": 5, "is_active": True}]
        if "SUM(COALESCE(sa.duration_minutes" in sql or "AS total" in sql:
            return [{"total": 15}]
        if "total_price" in sql:
            return [{"total_price": 9500}]
        return []          # sem conflito

    def execute_write(self, sql, params=None):
        self.escritas.append(sql)
        return 1

    def execute_write_returning(self, sql, params=None):
        self.escritas.append(sql)
        if "INSERT INTO scheduler.appointments" in sql:
            return {"id": "ap-novo"}
        return {"id": "ap-novo"}


class TestIntegracaoComOAgendamento(unittest.TestCase):
    """As funções existirem não basta: o fluxo precisa chamá-las."""

    def test_criar_agendamento_marca_a_estreia(self):
        from src.services.appointment_service import AppointmentService

        db = DbRoteado()
        service = AppointmentService(db)
        with mock.patch("src.services.appointment_service.e_primeira_visita",
                        return_value=True) as pergunta:
            service.create_appointment(
                clinic_id=CLINIC, phone=PHONE, service_id="s1",
                date="2026-09-23", time="14:00",
                service_area_pairs=[{"service_id": "s1", "area_id": "a1"}])

        pergunta.assert_called_once()
        self.assertTrue(any("is_first_visit = TRUE" in s for s in db.escritas),
                        "o agendamento foi criado sem marcar a estreia")

    def test_quem_ja_veio_nao_e_marcado(self):
        from src.services.appointment_service import AppointmentService

        db = DbRoteado()
        with mock.patch("src.services.appointment_service.e_primeira_visita",
                        return_value=False):
            AppointmentService(db).create_appointment(
                clinic_id=CLINIC, phone=PHONE, service_id="s1",
                date="2026-09-23", time="14:00",
                service_area_pairs=[{"service_id": "s1", "area_id": "a1"}])

        self.assertFalse(any("is_first_visit = TRUE" in s for s in db.escritas))

    def test_painel_desmarcado_nao_marca_nem_pergunta(self):
        """Decisao do Andre em 09/09/2026: pelo painel o padrao e desmarcado.

        Nao basta nao gravar - a contagem nem deve ser feita, senao um dia
        alguem a religa "porque ja estava calculada" e o padrao volta sozinho.
        """
        from src.services.appointment_service import AppointmentService

        db = DbRoteado()
        with mock.patch("src.services.appointment_service.e_primeira_visita",
                        return_value=True) as pergunta:
            AppointmentService(db).create_appointment(
                clinic_id=CLINIC, phone=PHONE, service_id="s1",
                date="2026-09-23", time="14:00",
                service_area_pairs=[{"service_id": "s1", "area_id": "a1"}],
                is_first_visit=False)

        pergunta.assert_not_called()
        self.assertFalse(any("is_first_visit = TRUE" in s for s in db.escritas),
                         "o painel marcou estreia com a caixinha desmarcada")

    def test_painel_marcado_vence_o_historico_do_banco(self):
        """Quem esta na recepcao sabe o que o banco nao sabe.

        A clinica atende desde antes do sistema existir: a contagem automatica
        diria "ja veio" para quem esta estreando no sistema, e vice-versa.
        """
        from src.services.appointment_service import AppointmentService

        db = DbRoteado()
        with mock.patch("src.services.appointment_service.e_primeira_visita",
                        return_value=False) as pergunta:
            AppointmentService(db).create_appointment(
                clinic_id=CLINIC, phone=PHONE, service_id="s1",
                date="2026-09-23", time="14:00",
                service_area_pairs=[{"service_id": "s1", "area_id": "a1"}],
                is_first_visit=True)

        pergunta.assert_not_called()
        self.assertTrue(any("is_first_visit = TRUE" in s for s in db.escritas))

    def test_o_bot_continua_decidindo_sozinho(self):
        """O outro lado da mesma regra: sem opiniao, conta.

        Sem isto, trocar o default do painel para False silenciosamente
        desligaria a marcacao do bot tambem, e ninguem notaria - a agenda so
        pararia de ter estreias.
        """
        from src.services.appointment_service import AppointmentService

        db = DbRoteado()
        with mock.patch("src.services.appointment_service.e_primeira_visita",
                        return_value=True) as pergunta:
            AppointmentService(db).create_appointment(
                clinic_id=CLINIC, phone=PHONE, service_id="s1",
                date="2026-09-23", time="14:00",
                service_area_pairs=[{"service_id": "s1", "area_id": "a1"}])

        pergunta.assert_called_once()
        self.assertTrue(any("is_first_visit = TRUE" in s for s in db.escritas))

    def test_cancelar_passa_a_marca_adiante(self):
        from src.services.appointment_service import AppointmentService

        db = mock.MagicMock()
        db.execute_write_returning.return_value = {"id": "ap1"}
        with mock.patch("src.services.appointment_service.passa_a_marca_adiante") as passa:
            AppointmentService(db).cancel_appointment("ap1")

        passa.assert_called_once_with(db, "ap1")


if __name__ == "__main__":
    unittest.main()

