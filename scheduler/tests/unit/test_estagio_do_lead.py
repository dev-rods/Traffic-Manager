# -*- coding: utf-8 -*-
"""Uma linha por estagio da secao 5 do PRD 057, mais os conflitos de precedencia."""
import unittest
from datetime import datetime, timedelta, timezone

from src.services import estagio_do_lead as e

AGORA = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def D(dias, horas=0):
    return AGORA - timedelta(days=dias, hours=horas)


def sinais(**kw):
    base = dict(stage=None, stage_source=None, stage_updated_at=None, first_contact_at=None,
                ultima_mensagem_de=None, ultima_mensagem_em=None, lead_ja_falou=False,
                tem_transcricao=False, chat_espelho_em=None, chat_espelho_nao_lidas=0,
                ultimo_agendamento=None)
    base.update(kw)
    return e.Sinais(**base)


class TestEntregaDoBot(unittest.TestCase):
    """PRD 058: o aviso do bot ("vou confirmar com uma especialista") nao e
    resposta. Sem fala humana depois dele, a bola esta conosco."""

    def _entregue(self, **kw):
        base = dict(tem_transcricao=True, ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(13),
                    lead_ja_falou=True, bot_entregou_em=D(13))
        base.update(kw)
        return sinais(**base)

    def test_ninguem_assumiu_e_aguardando_nos_com_motivo_e_data(self):
        d = e.decide(self._entregue(), AGORA)
        self.assertEqual((d.stage, d.source), (e.AGUARDANDO_NOS, e.REGRA))
        self.assertEqual(d.reason, "bot pediu ajuda em {:%d/%m} e ninguem assumiu".format(D(13)))

    def test_parado_ha_muito_continua_aguardando_nos_e_nao_sumiu(self):
        self.assertEqual(e.decide(self._entregue(ultima_mensagem_em=D(30), bot_entregou_em=D(30)), AGORA).stage,
                         e.AGUARDANDO_NOS)

    def test_pessoa_respondeu_depois_desliga_o_sinal(self):
        # Essencia 17/11: handoff e a atendente respondeu no dia seguinte.
        s = self._entregue(ultima_mensagem_em=D(2), bot_entregou_em=D(3), ultima_fala_humana_em=D(2))
        self.assertEqual(e.decide(s, AGORA).stage, e.EM_ANDAMENTO)
        # Nobre 06/11: respondeu e o lead sumiu.
        s = self._entregue(ultima_mensagem_em=D(16), bot_entregou_em=D(16), ultima_fala_humana_em=D(16, horas=-1))
        self.assertEqual(e.decide(s, AGORA).stage, e.SUMIU)

    def test_pessoa_respondeu_antes_da_entrega_nao_conta(self):
        s = self._entregue(ultima_fala_humana_em=D(20))
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_mensagem_do_sistema_depois_nao_e_resposta(self):
        # Lembrete ou link depois do aviso: a direcao e NOS, o autor nao e pessoa.
        s = self._entregue(ultima_mensagem_em=D(1), bot_entregou_em=D(3))
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_sem_transcricao_a_entrega_ainda_vale(self):
        # Eventos vencidos (60 d) mas a tarefa segue aberta: a sessao prova a conversa.
        s = sinais(bot_entregou_em=D(70), chat_espelho_em=D(70))
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_manual_vence_a_entrega(self):
        s = self._entregue(stage=e.NAO_AGENDOU, stage_source=e.MANUAL, stage_updated_at=D(1))
        self.assertEqual(e.decide(s, AGORA).stage, e.NAO_AGENDOU)

    def test_nao_e_lead_vence_a_entrega(self):
        s = self._entregue(stage=e.NAO_E_LEAD, stage_source=e.MODELO, stage_updated_at=D(1))
        self.assertEqual(e.decide(s, AGORA).stage, e.NAO_E_LEAD)

    def test_sem_entrega_nada_muda(self):
        self.assertFalse(e.entrega_pendente(sinais()))
        self.assertEqual(e.decide(sinais(tem_transcricao=True, ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(2),
                                         lead_ja_falou=True), AGORA).stage, e.EM_ANDAMENTO)


class TestEstagiosDeConversa(unittest.TestCase):
    def test_sem_nada_e_sem_conversa(self):
        self.assertEqual(e.decide(sinais(), AGORA), e.Decisao(e.SEM_CONVERSA, e.REGRA))

    def test_so_nos_falamos_ha_mais_de_n_dias_e_sumiu(self):
        s = sinais(tem_transcricao=True, ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(8), lead_ja_falou=False)
        self.assertEqual(e.decide(s, AGORA).stage, e.SUMIU)

    def test_first_contact_antigo_sem_evento_e_sumiu(self):
        self.assertEqual(e.decide(sinais(first_contact_at=D(8)), AGORA).stage, e.SUMIU)

    def test_so_nos_falamos(self):
        s = sinais(ultima_mensagem_de="NOS", ultima_mensagem_em=D(1), tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.INICIADA_SEM_RESPOSTA)

    def test_first_contact_sem_evento_e_iniciada(self):
        self.assertEqual(e.decide(sinais(first_contact_at=D(2)), AGORA).stage, e.INICIADA_SEM_RESPOSTA)

    def test_ultima_e_do_lead(self):
        s = sinais(ultima_mensagem_de="LEAD", ultima_mensagem_em=D(10), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_nossa_recente_depois_de_ele_falar_e_em_andamento(self):
        s = sinais(ultima_mensagem_de="NOS", ultima_mensagem_em=D(3), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.EM_ANDAMENTO)

    def test_nossa_antiga_depois_de_ele_falar_e_sumiu(self):
        s = sinais(ultima_mensagem_de="NOS", ultima_mensagem_em=D(8), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.SUMIU)

    def test_dias_parado_vem_da_clinica(self):
        s = sinais(ultima_mensagem_de="NOS", ultima_mensagem_em=D(8), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA, dias_parado=10).stage, e.EM_ANDAMENTO)


class TestFallbackDoEspelho(unittest.TestCase):
    def test_nao_lidas_e_aguardando_nos(self):
        s = sinais(chat_espelho_em=D(1), chat_espelho_nao_lidas=2)
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.AGUARDANDO_NOS, e.REGRA))

    def test_recente_lido_e_em_andamento(self):
        self.assertEqual(e.decide(sinais(chat_espelho_em=D(2)), AGORA).stage, e.EM_ANDAMENTO)

    def test_antigo_dentro_de_60_dias_e_sumiu_por_regra(self):
        self.assertEqual(e.decide(sinais(chat_espelho_em=D(20)), AGORA), e.Decisao(e.SUMIU, e.REGRA))

    def test_mais_de_60_dias_e_historico(self):
        self.assertEqual(e.decide(sinais(chat_espelho_em=D(90)), AGORA), e.Decisao(e.SUMIU, e.HISTORICO))

    def test_transcricao_vence_o_espelho(self):
        s = sinais(ultima_mensagem_de="LEAD", ultima_mensagem_em=D(1), lead_ja_falou=True, tem_transcricao=True,
                   chat_espelho_em=D(90))
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.AGUARDANDO_NOS, e.REGRA))


class TestFatosDaAgenda(unittest.TestCase):
    """PRD 054: o agendamento mais recente que nao e remarcacao decide."""

    def test_confirmado_e_agendou(self):
        self.assertEqual(e.decide(sinais(ultimo_agendamento="CONFIRMED"), AGORA).stage, e.AGENDOU)

    def test_ultimo_cancelado_e_cancelou(self):
        self.assertEqual(e.decide(sinais(ultimo_agendamento="CANCELLED"), AGORA).stage, e.CANCELOU)

    def test_ultimo_e_falta(self):
        # Se tivesse remarcado, o NO_SHOW teria rescheduled_to_id e ficaria de
        # fora; o mais recente seria o CONFIRMED novo.
        self.assertEqual(e.decide(sinais(ultimo_agendamento="NO_SHOW"), AGORA).stage, e.FALTOU)

    def test_cancelou_e_escreveu_depois_do_horario_volta_para_a_conversa(self):
        s = sinais(ultimo_agendamento="CANCELLED", ultimo_agendamento_em=D(5), tem_transcricao=True,
                   ultima_mensagem_de=e.LEAD, ultima_mensagem_em=D(1), lead_ja_falou=True)
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.AGUARDANDO_NOS, e.REGRA))

    def test_faltou_e_escreveu_depois_do_horario_volta_para_a_conversa(self):
        s = sinais(ultimo_agendamento="NO_SHOW", ultimo_agendamento_em=D(5), tem_transcricao=True,
                   ultima_mensagem_de=e.LEAD, ultima_mensagem_em=D(1), lead_ja_falou=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_cancelou_e_escreveu_antes_do_horario_segue_cancelou(self):
        s = sinais(ultimo_agendamento="CANCELLED", ultimo_agendamento_em=D(1), tem_transcricao=True,
                   ultima_mensagem_de=e.LEAD, ultima_mensagem_em=D(3), lead_ja_falou=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.CANCELOU)

    def test_cancelou_e_nos_falamos_depois_segue_cancelou(self):
        s = sinais(ultimo_agendamento="CANCELLED", ultimo_agendamento_em=D(5), tem_transcricao=True,
                   ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(1), lead_ja_falou=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.CANCELOU)

    def test_agendou_nao_cai_por_mensagem_do_lead(self):
        s = sinais(ultimo_agendamento="CONFIRMED", ultimo_agendamento_em=D(5), tem_transcricao=True,
                   ultima_mensagem_de=e.LEAD, ultima_mensagem_em=D(1), lead_ja_falou=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.AGENDOU)

    def test_sem_agendamento_segue_para_a_conversa(self):
        self.assertEqual(e.decide(sinais(ultimo_agendamento=None), AGORA).stage, e.SEM_CONVERSA)

    def test_status_desconhecido_nao_e_fato(self):
        self.assertEqual(e.decide(sinais(ultimo_agendamento="PENDING"), AGORA).stage, e.SEM_CONVERSA)

    def test_cancelou_e_o_bot_pediu_ajuda_depois_do_horario_volta_para_a_conversa(self):
        s = sinais(ultimo_agendamento="CANCELLED", ultimo_agendamento_em=D(5), tem_transcricao=True,
                   ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(2), lead_ja_falou=True, bot_entregou_em=D(2))
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_cancelou_e_o_bot_pediu_ajuda_antes_do_horario_segue_cancelou(self):
        s = sinais(ultimo_agendamento="CANCELLED", ultimo_agendamento_em=D(1), tem_transcricao=True,
                   ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(3), lead_ja_falou=True, bot_entregou_em=D(3))
        self.assertEqual(e.decide(s, AGORA).stage, e.CANCELOU)

    def test_agendou_nao_cai_por_entrega_do_bot(self):
        s = sinais(ultimo_agendamento="CONFIRMED", ultimo_agendamento_em=D(5), tem_transcricao=True,
                   ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(2), lead_ja_falou=True, bot_entregou_em=D(2))
        self.assertEqual(e.decide(s, AGORA).stage, e.AGENDOU)

    def test_agendou_vence_manual(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MANUAL, stage_updated_at=D(1), ultimo_agendamento="CONFIRMED")
        self.assertEqual(e.decide(s, AGORA).stage, e.AGENDOU)

    def test_agendou_vence_nao_e_lead(self):
        s = sinais(stage=e.NAO_E_LEAD, stage_source=e.MODELO, stage_updated_at=D(1), ultimo_agendamento="CONFIRMED")
        self.assertEqual(e.decide(s, AGORA).stage, e.AGENDOU)

    def test_fato_da_agenda_vem_sem_motivo(self):
        self.assertIsNone(e.decide(sinais(ultimo_agendamento="NO_SHOW"), AGORA).reason)


class TestJulgamentos(unittest.TestCase):
    def test_manual_trava_a_regra(self):
        s = sinais(stage=e.EM_ANDAMENTO, stage_source=e.MANUAL, stage_updated_at=D(1),
                   ultima_mensagem_de="NOS", ultima_mensagem_em=D(20), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.EM_ANDAMENTO, e.MANUAL))

    def test_manual_sai_sem_motivo_para_o_repo_manter_o_gravado(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MANUAL, stage_updated_at=D(1))
        d = e.decide(s, AGORA)
        self.assertEqual((d.stage, d.source, d.reason), (e.NAO_AGENDOU, e.MANUAL, None))

    def test_nao_agendou_do_modelo_fica_sem_mensagem_nova(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="NOS", ultima_mensagem_em=D(10), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.NAO_AGENDOU)

    def test_mensagem_nova_do_lead_derruba_nao_agendou_do_modelo(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="LEAD", ultima_mensagem_em=D(1), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_nao_agendou_do_modelo_cai_com_entrega_do_bot_pendente(self):
        # Caso da Nobre em prod (22/11): handoff em 09/11, veredito em 22/11.
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_updated_at=D(0), tem_transcricao=True,
                   ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(13), lead_ja_falou=True, bot_entregou_em=D(13))
        d = e.decide(s, AGORA)
        self.assertEqual((d.stage, d.source), (e.AGUARDANDO_NOS, e.REGRA))
        self.assertIn("ninguem assumiu", d.reason)

    def test_nao_agendou_do_modelo_fica_se_uma_pessoa_respondeu_depois_da_entrega(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_updated_at=D(0), tem_transcricao=True,
                   ultima_mensagem_de=e.NOS, ultima_mensagem_em=D(12), lead_ja_falou=True,
                   bot_entregou_em=D(13), ultima_fala_humana_em=D(12))
        self.assertEqual(e.decide(s, AGORA), e.Decisao(e.NAO_AGENDOU, e.MODELO))

    def test_nao_e_lead_do_modelo_fica(self):
        s = sinais(stage=e.NAO_E_LEAD, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="LEAD", ultima_mensagem_em=D(10), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.NAO_E_LEAD)

    def test_mensagem_nova_derruba_nao_e_lead_do_modelo(self):
        s = sinais(stage=e.NAO_E_LEAD, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="LEAD", ultima_mensagem_em=D(1), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.AGUARDANDO_NOS)

    def test_nossa_mensagem_depois_do_veredito_nao_derruba(self):
        s = sinais(stage=e.NAO_AGENDOU, stage_source=e.MODELO, stage_updated_at=D(2),
                   ultima_mensagem_de="NOS", ultima_mensagem_em=D(1), lead_ja_falou=True, tem_transcricao=True)
        self.assertEqual(e.decide(s, AGORA).stage, e.NAO_AGENDOU)


class TestConstantes(unittest.TestCase):
    def test_editaveis_nao_incluem_agenda(self):
        self.assertFalse(e.ESTAGIOS_EDITAVEIS & e.ESTAGIOS_DA_AGENDA)

    def test_ordem_da_fila_cobre_os_nove_visiveis(self):
        self.assertEqual(len(e.ORDEM_DA_FILA), 9)
        self.assertNotIn(e.NAO_E_LEAD, e.ORDEM_DA_FILA)
        self.assertEqual(set(e.ORDEM_DA_FILA) | {e.NAO_E_LEAD}, set(e.ESTAGIOS))


if __name__ == "__main__":
    unittest.main()
