# -*- coding: utf-8 -*-
"""O job: regras + modelo por lead, grava so quando muda, dryRun nao escreve,
uma clinica com erro nao bloqueia a proxima, remarcacao nao e CANCELOU."""
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "t")

from src.functions.lead import classifica_estagios as job
from src.services import estagio_do_lead as e
from src.services.classificador_de_lead import TetoAtingido, Veredito
from src.services.transcricao import Mensagem

AGORA = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)
CLINIC = {"clinic_id": "c1", "name": "Essencia", "crm_dias_parado": 7, "active": True}


class BancoFalso:
    def __init__(self, leads, agendamentos=(), chats=()):
        self.leads, self.agendamentos, self.chats = leads, list(agendamentos), list(chats)
        self.escritas = []
        self.consultas = []

    def execute_query(self, sql, params=None):
        s = " ".join(sql.split())
        self.consultas.append(s)
        if "FROM scheduler.leads" in s:
            return self.leads
        if "FROM scheduler.appointments" in s:
            return self.agendamentos
        if "FROM scheduler.whatsapp_chats" in s:
            return self.chats
        return []

    def execute_write(self, sql, params=None):
        self.escritas.append((" ".join(sql.split()), params))
        return 1


def lead(**kw):
    base = {"id": "11111111-1111-1111-1111-111111111111", "clinic_id": "c1", "phone": "5511999990000",
            "source": "landing-page", "stage": None, "stage_source": None, "stage_reason": None,
            "stage_updated_at": None, "first_contact_at": None, "triagem_feita_em": None,
            "desfecho_tentado_em": None}
    base.update(kw)
    return base


class ClassificadorFalso:
    chamadas = 0

    def triagem(self, *_):
        return None

    def desfecho(self, *_):
        return None


def roda(db, classificador=None, dry_run=False, mensagens=()):
    with mock.patch.object(job, "ultimas_mensagens", return_value=list(mensagens)):
        return job.processa_clinica(db, None, CLINIC, classificador or ClassificadorFalso(), AGORA, dry_run=dry_run)


class TestProcessaClinica(unittest.TestCase):
    def test_lead_sem_nada_vira_sem_conversa_e_grava(self):
        db = BancoFalso([lead()])
        r = roda(db)
        self.assertEqual(r["por_estagio"], {e.SEM_CONVERSA: 1})
        self.assertEqual(r["mudaram"], 1)
        self.assertTrue(any("UPDATE scheduler.leads SET stage" in s for s, _ in db.escritas))

    def test_dry_run_nao_escreve(self):
        db = BancoFalso([lead()])
        r = roda(db, dry_run=True)
        self.assertEqual(r["por_estagio"], {e.SEM_CONVERSA: 1})
        self.assertEqual(r["mudaram"], 1)
        self.assertEqual(db.escritas, [])

    def test_segunda_rodada_nao_muda_nada(self):
        db = BancoFalso([lead(stage=e.SEM_CONVERSA, stage_source=e.REGRA)])
        r = roda(db)
        self.assertEqual(r["mudaram"], 0)
        self.assertFalse(any("lead_stage_events" in s for s, _ in db.escritas))

    def test_agendamento_do_paciente_com_mesmo_telefone_conta(self):
        db = BancoFalso([lead()], agendamentos=[{"phone": "5511999990000", "status": "CONFIRMED",
                                                 "appointment_date": AGORA.date() + timedelta(days=3), "start_time": "10:00"}])
        self.assertEqual(roda(db, dry_run=True)["por_estagio"], {e.AGENDOU: 1})

    def test_consulta_da_agenda_exclui_remarcacao(self):
        db = BancoFalso([lead()])
        roda(db, dry_run=True)
        sql = next(s for s in db.consultas if "FROM scheduler.appointments" in s)
        self.assertIn("rescheduled_to_id IS NULL", sql)
        self.assertIn("deleted_at IS NULL", sql)

    def test_o_mais_recente_decide(self):
        ags = [
            {"phone": "5511999990000", "status": "NO_SHOW", "appointment_date": date(2026, 10, 1), "start_time": "10:00"},
            {"phone": "5511999990000", "status": "CONFIRMED", "appointment_date": date(2026, 12, 1), "start_time": "09:00"},
        ]
        self.assertEqual(roda(BancoFalso([lead()], agendamentos=ags), dry_run=True)["por_estagio"], {e.AGENDOU: 1})
        ags[1]["appointment_date"] = date(2026, 9, 1)
        self.assertEqual(roda(BancoFalso([lead()], agendamentos=ags), dry_run=True)["por_estagio"], {e.FALTOU: 1})

    def test_cancelou_e_escreveu_depois_do_horario_e_aguardando_nos(self):
        ags = [{"phone": "5511999990000", "status": "CANCELLED", "appointment_date": date(2026, 11, 15), "start_time": "10:00"}]
        msgs = [Mensagem("NOS", AGORA - timedelta(days=10), "Confirmado dia 15"),
                Mensagem("LEAD", AGORA - timedelta(days=1), "Consigo remarcar pra semana que vem?")]
        r = roda(BancoFalso([lead()], agendamentos=ags), dry_run=True, mensagens=msgs)
        self.assertEqual(r["por_estagio"], {e.AGUARDANDO_NOS: 1})

    def test_horario_do_agendamento_vai_para_utc_pelo_fuso_da_clinica(self):
        ag = {"status": "CANCELLED", "appointment_date": date(2026, 11, 15), "start_time": "10:00"}
        self.assertEqual(job._quando(ag, CLINIC), datetime(2026, 11, 15, 13, 0, tzinfo=timezone.utc))
        self.assertEqual(job._quando(dict(ag, appointment_date="2026-11-15", start_time="10:00:00"), CLINIC),
                         datetime(2026, 11, 15, 13, 0, tzinfo=timezone.utc))

    def test_variante_do_telefone_casa_no_espelho(self):
        db = BancoFalso([lead(phone="5547997053940")],
                        chats=[{"phone": "554797053940", "name": "x", "last_message_at": AGORA - timedelta(days=2), "unread_count": 1}])
        self.assertEqual(roda(db, dry_run=True)["por_estagio"], {e.AGUARDANDO_NOS: 1})

    def test_so_espelho_grava_a_data_do_espelho_sem_direcao(self):
        quando = AGORA - timedelta(days=20)
        db = BancoFalso([lead()], chats=[{"phone": "5511999990000", "name": "x", "last_message_at": quando, "unread_count": 0}])
        r = roda(db)
        self.assertEqual(r["por_estagio"], {e.SUMIU: 1})
        upd = [p for s, p in db.escritas if "UPDATE scheduler.leads SET stage" in s][0]
        self.assertEqual((upd[3], upd[4]), (quando, None))

    def test_triagem_nao_e_lead_grava_com_fonte_modelo(self):
        ms = [Mensagem("LEAD", AGORA - timedelta(days=1, hours=h), "venda de insumos") for h in (3, 2, 1)]

        class Cl(ClassificadorFalso):
            def triagem(self, *_):
                return Veredito("NAO_E_LEAD", "fornecedor")

        db = BancoFalso([lead(source="whatsapp")])
        r = roda(db, Cl(), mensagens=ms)
        self.assertEqual(r["por_estagio"], {e.NAO_E_LEAD: 1})
        upd = [p for s, p in db.escritas if "UPDATE scheduler.leads SET stage" in s][0]
        self.assertEqual((upd[0], upd[1], upd[2]), (e.NAO_E_LEAD, "fornecedor", e.MODELO))
        self.assertTrue(any("triagem_feita_em" in s for s, _ in db.escritas))

    def test_triagem_lead_so_marca_e_segue_a_regra(self):
        ms = [Mensagem("LEAD", AGORA - timedelta(hours=h), "quero agendar") for h in (3, 2, 1)]

        class Cl(ClassificadorFalso):
            def triagem(self, *_):
                return Veredito("LEAD", "quer agendar")

        db = BancoFalso([lead(source="whatsapp")])
        r = roda(db, Cl(), mensagens=ms)
        self.assertEqual(r["por_estagio"], {e.AGUARDANDO_NOS: 1})
        self.assertTrue(any("triagem_feita_em" in s for s, _ in db.escritas))

    def test_desfecho_ainda_aberto_registra_tentativa_e_nao_muda(self):
        ms = [Mensagem("LEAD", AGORA - timedelta(days=12), "oi"), Mensagem("NOS", AGORA - timedelta(days=11), "ola")]

        class Cl(ClassificadorFalso):
            def desfecho(self, *_):
                return Veredito("AINDA_ABERTO", "sem decisao")

        db = BancoFalso([lead()])
        r = roda(db, Cl(), mensagens=ms)
        self.assertEqual(r["por_estagio"], {e.SUMIU: 1})
        self.assertTrue(any("lead_stage_events" in s and "ainda_aberto" in (p or ()) for s, p in db.escritas))
        self.assertTrue(any("desfecho_tentado_em" in s for s, _ in db.escritas))

    def test_desfecho_nao_agendou_grava_motivo(self):
        ms = [Mensagem("LEAD", AGORA - timedelta(days=12), "achei caro"), Mensagem("NOS", AGORA - timedelta(days=11), "ok")]

        class Cl(ClassificadorFalso):
            def desfecho(self, *_):
                return Veredito("NAO_AGENDOU", "achou caro")

        db = BancoFalso([lead()])
        r = roda(db, Cl(), mensagens=ms)
        self.assertEqual(r["por_estagio"], {e.NAO_AGENDOU: 1})
        upd = [p for s, p in db.escritas if "UPDATE scheduler.leads SET stage" in s][0]
        self.assertEqual((upd[0], upd[1], upd[2]), (e.NAO_AGENDOU, "achou caro", e.MODELO))

    def test_descarte_do_modelo_conta_e_nao_marca(self):
        ms = [Mensagem("LEAD", AGORA - timedelta(days=12), "oi"), Mensagem("NOS", AGORA - timedelta(days=11), "ola")]
        db = BancoFalso([lead()])
        r = roda(db, ClassificadorFalso(), mensagens=ms)
        self.assertEqual(r["descartes"], 1)
        self.assertFalse(any("desfecho_tentado_em" in s for s, _ in db.escritas))

    def test_teto_atingido_segue_so_com_as_regras(self):
        ms = [Mensagem("LEAD", AGORA - timedelta(days=12), "oi"), Mensagem("NOS", AGORA - timedelta(days=11), "ola")]

        class Cl(ClassificadorFalso):
            def desfecho(self, *_):
                raise TetoAtingido("2")

        db = BancoFalso([lead(), lead(id="22222222-2222-2222-2222-222222222222"),
                         lead(id="33333333-3333-3333-3333-333333333333")])
        cl = Cl()
        cl.chamadas = 2
        r = roda(db, cl, mensagens=ms)
        self.assertEqual(r["por_estagio"], {e.SUMIU: 3})
        self.assertEqual(r["leads"], 3)
        # O primeiro estourou o teto; os outros dois ficaram para amanha, e isso
        # nao e descarte nem zera a contagem de chamadas feitas.
        self.assertEqual((r["chamadas_modelo"], r["descartes"], r["adiados"]), (2, 0, 2))

    def test_max_chamadas_vem_do_payload(self):
        with mock.patch.object(job, "PostgresService"), mock.patch.object(job, "_tabela_de_eventos"), \
                mock.patch.object(job, "_clinicas", return_value=[CLINIC]), \
                mock.patch.object(job, "Classificador") as Cl, mock.patch.object(job, "processa_clinica", return_value={}):
            job.handler({"clinicId": "c1", "dryRun": True, "maxChamadasModelo": 900}, None)
            self.assertEqual(Cl.call_args.kwargs["max_chamadas"], 900)

    def test_manual_nao_vai_ao_modelo(self):
        ms = [Mensagem("LEAD", AGORA - timedelta(days=12), "oi"), Mensagem("NOS", AGORA - timedelta(days=11), "ola")]

        class Cl(ClassificadorFalso):
            def desfecho(self, *_):
                raise AssertionError("nao devia perguntar")

        db = BancoFalso([lead(stage=e.EM_ANDAMENTO, stage_source=e.MANUAL, stage_updated_at=AGORA - timedelta(days=1))])
        self.assertEqual(roda(db, Cl(), mensagens=ms)["por_estagio"], {e.EM_ANDAMENTO: 1})


class TestHandler(unittest.TestCase):
    def test_clinica_com_erro_nao_bloqueia_a_proxima(self):
        clinicas = [dict(CLINIC, clinic_id="c1"), dict(CLINIC, clinic_id="c2")]
        resultados = iter([RuntimeError("boom"), {"leads": 0, "mudaram": 0, "por_estagio": {}, "chamadas_modelo": 0, "descartes": 0}])

        def processa(*a, **k):
            r = next(resultados)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(job, "_clinicas", return_value=clinicas), \
             mock.patch.object(job, "processa_clinica", side_effect=processa), \
             mock.patch.object(job, "PostgresService"), mock.patch.object(job, "_tabela_de_eventos"), \
             mock.patch.object(job, "Classificador"):
            r = job.handler({"dryRun": True}, None)
        self.assertEqual(r["clinics"], 2)
        self.assertIn("erro", r["por_clinica"]["c1"])
        self.assertNotIn("erro", r["por_clinica"]["c2"])
        self.assertTrue(r["dryRun"])

    def test_clinic_id_limita(self):
        db = mock.MagicMock()
        db.execute_query.return_value = []
        job._clinicas(db, "c9")
        self.assertIn("clinic_id = %s", db.execute_query.call_args[0][0])
        self.assertEqual(db.execute_query.call_args[0][1], ("c9",))


if __name__ == "__main__":
    unittest.main()
