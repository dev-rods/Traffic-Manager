# -*- coding: utf-8 -*-
"""O cron de vencimento: pendência fica com pessoa, sem pendência avalia a
retomada, e tudo grava com a escrita condicional. PRD 020 §3.11.
"""
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services import atendimento as at
from src.services import retomada

H = 3600
AGORA = int(time.mktime(time.strptime("2026-10-08T15:00:00", "%Y-%m-%dT%H:%M:%S")) - time.timezone)
CLINICA = {"clinic_id": "c1", "timezone": "America/Sao_Paulo", "active": True}


def _iso(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def evento(direction, content, ha_horas):
    return {"direction": direction, "content": content, "sk": f"MSG#{_iso(AGORA - ha_horas * H)}#x"}


def roda(sessao, eventos, efeitos=0, veredito='{"pendente": true, "o_que": "horário"}', falar_ok=(True, 1)):
    from src.functions.atendimento import expira as modulo

    item = {"pk": "CLINIC#c1", "sk": "PHONE#5511999990000", "clinicId": "c1", "phone": "5511999990000"}
    tabela = mock.MagicMock()
    tabela.query.return_value = {"Items": [item]}
    tabela.get_item.return_value = {"Item": {**item, "session": dict(sessao)}}
    gravadas = []

    def grava(t, c, p, s, **kw):
        gravadas.append(dict(s)); tabela.get_item.return_value = {"Item": {**item, "session": dict(s)}}; return True

    db = mock.MagicMock()
    db.execute_query.side_effect = lambda sql, params=None: (
        [CLINICA] if "clinics" in sql else [{"n": efeitos}] if "COUNT" in sql else [{"id": "t1"}])
    tracker = mock.MagicMock(); tracker.get_conversation_messages.return_value = eventos
    anthropic = mock.MagicMock(); anthropic.create_message.return_value = {"content": [{"type": "text", "text": veredito}]}

    with mock.patch.object(modulo, "_tabela", return_value=tabela), \
         mock.patch.object(modulo, "grava_atendimento", side_effect=grava), \
         mock.patch("src.services.db.postgres.PostgresService", return_value=db), \
         mock.patch("src.services.message_tracker.MessageTracker", return_value=tracker), \
         mock.patch("src.services.anthropic_service.AnthropicService", return_value=anthropic), \
         mock.patch("src.providers.whatsapp_provider.get_provider"), \
         mock.patch("src.services.agent_runner.falar", return_value=falar_ok) as falar, \
         mock.patch.object(modulo, "_agora", return_value=AGORA):
        resultado = modulo.handler({}, None)
    return resultado, gravadas, falar


class TestPendencia(unittest.TestCase):
    def test_handoff_com_pendencia_vira_human_pending_e_abre_tarefa(self):
        s = at.entrega_a_humano({}, por=at.POR_HANDOFF, motivo="faq_sem_resposta", agora=AGORA - 25 * H,
                                pending_intent="faq_sem_resposta")
        resultado, gravadas, falar = roda(s, [evento("INBOUND", "tem horário?", 25)])
        self.assertEqual(resultado["pendentes"], 1)
        self.assertEqual(at.estado(gravadas[-1], AGORA), at.HUMAN_PENDING)
        self.assertEqual(gravadas[-1][at.CAMPO]["pending_task_id"], "t1")
        falar.assert_not_called()


class TestRetomada(unittest.TestCase):
    def test_pergunta_em_aberto_e_respondida_uma_vez_e_cai_em_cooldown(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 30 * H)
        ev = [evento("OUTBOUND", "Oi!", 40), evento("INBOUND", "tem horário sábado?", 30)]
        resultado, gravadas, falar = roda(s, ev)
        self.assertEqual(resultado["retomados"], 1)
        falar.assert_called_once()
        final = gravadas[-1]
        self.assertEqual(at.estado(final, AGORA), at.COOLDOWN)
        self.assertEqual(final[at.CAMPO]["handler"], at.COOLDOWN, "gravado, nao so derivado: a GSI le o handler")
        self.assertEqual(final[at.CAMPO]["retomada_em"], AGORA)
        self.assertIsNone(final[at.CAMPO]["retomada_contexto"])
        # O contexto chegou a ser gravado ANTES de o agente rodar.
        self.assertTrue(any((g.get(at.CAMPO) or {}).get("retomada_contexto") for g in gravadas))

    def test_modelo_disse_nao_cala_e_alerta(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 30 * H)
        ev = [evento("INBOUND", "tem horário sábado?", 30)]
        resultado, gravadas, falar = roda(s, ev, veredito='{"pendente": false}')
        falar.assert_not_called()
        self.assertEqual(resultado["calados"], 1)
        self.assertEqual(gravadas[-1][at.CAMPO]["alerta"], retomada.MODELO_DISSE_NAO)
        self.assertEqual(gravadas[-1][at.CAMPO]["retomada_em"], AGORA, "uma vez por pendência, mesmo calando")
        self.assertEqual(gravadas[-1][at.CAMPO]["handler"], at.COOLDOWN, "calar tambem encerra, senao volta a cada ciclo")

    def test_fecho_social_cala_sem_chamar_o_modelo(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 30 * H)
        resultado, gravadas, falar = roda(s, [evento("INBOUND", "obrigada!", 30)])
        falar.assert_not_called()
        self.assertEqual(resultado["calados"], 1)
        self.assertEqual(at.estado(gravadas[-1], AGORA), at.COOLDOWN)
        self.assertEqual(gravadas[-1][at.CAMPO]["handler"], at.COOLDOWN)
        # Fecho social da pessoa nao e pergunta sem resposta: sem alerta?
        # E alerta sim: a ultima fala era dela, e a fila decide se importa.
        self.assertEqual(gravadas[-1][at.CAMPO]["alerta"], retomada.FECHO_SOCIAL)

    def test_resolvido_fora_cala(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 30 * H)
        resultado, gravadas, falar = roda(s, [evento("INBOUND", "tem horário sábado?", 30)], efeitos=1)
        falar.assert_not_called()
        self.assertEqual(gravadas[-1][at.CAMPO]["alerta"], retomada.RESOLVIDO_FORA)
        self.assertEqual(gravadas[-1][at.CAMPO]["handler"], at.COOLDOWN)

    def test_ultima_fala_do_bot_cala_sem_alerta(self):
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 30 * H)
        ev = [evento("INBOUND", "tem horário?", 31), evento("OUTBOUND", "Tenho 10h.", 30)]
        resultado, gravadas, falar = roda(s, ev)
        self.assertEqual(resultado["calados"], 1)
        self.assertIsNone(gravadas[-1][at.CAMPO]["alerta"])
        self.assertEqual(at.estado(gravadas[-1], AGORA), at.COOLDOWN)
        self.assertEqual(gravadas[-1][at.CAMPO]["handler"], at.COOLDOWN)


class TestNadaVencido(unittest.TestCase):
    def test_calada_nao_volta_no_ciclo_seguinte(self):
        """O que a GSI le e o `handler` gravado: calar sem encerrar fazia a
        mesma conversa voltar a cada ciclo (visto em prod em 08/10)."""
        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 30 * H)
        _, gravadas, _ = roda(s, [evento("INBOUND", "obrigada!", 30)])
        final = gravadas[-1]
        self.assertEqual(final[at.CAMPO]["handler"], at.COOLDOWN)
        self.assertNotEqual(final[at.CAMPO]["handler"], at.HUMAN_ACTIVE)
        self.assertEqual(at.estado(final, AGORA + 3600), at.COOLDOWN)

    def test_cala_e_grava_de_verdade_contra_a_condicao_de_versao(self):
        """Sem mock do grava_atendimento: a tabela falsa aplica a condição de
        versão como o DynamoDB. Alerta + encerra (duas transições) precisam
        caber numa escrita só. Em prod (08/10, 17:34 e 19:34 UTC) isto dava
        'Conflito de versao ... transicao descartada' em todo cala."""
        from src.functions.atendimento import expira as modulo

        class Tabela:
            def __init__(self, sessao):
                self.item = {"pk": "CLINIC#c1", "sk": "PHONE#5511999990000", "clinicId": "c1",
                             "phone": "5511999990000", "session": dict(sessao),
                             "handler": at.HUMAN_ACTIVE, "humanUntil": sessao[at.CAMPO]["human_until"]}
                self.escritas = 0
            def query(self, **kw):
                return {"Items": [self.item]} if self.item["handler"] == at.HUMAN_ACTIVE else {"Items": []}
            def get_item(self, Key):
                return {"Item": self.item}
            def update_item(self, Key, UpdateExpression, ConditionExpression, ExpressionAttributeNames, ExpressionAttributeValues):
                gravada = int(self.item["session"][at.CAMPO]["versao"])
                if gravada != int(ExpressionAttributeValues[":v"]):
                    raise type("ConditionalCheckFailedException", (Exception,), {})("versao")
                bloco = ExpressionAttributeValues[":a"]
                self.item["session"][at.CAMPO] = bloco
                self.item["handler"] = ExpressionAttributeValues[":h"]
                self.item["humanUntil"] = ExpressionAttributeValues.get(":hu")
                self.escritas += 1

        s = at.entrega_a_humano({}, por=at.POR_ATENDENTE, agora=AGORA - 30 * H)
        s[at.CAMPO]["versao"] = 4  # como em prod: ja houve escritas antes
        tabela = Tabela(s)
        db = mock.MagicMock()
        db.execute_query.side_effect = lambda sql, params=None: [CLINICA] if "clinics" in sql else [{"n": 0}]
        tracker = mock.MagicMock()
        tracker.get_conversation_messages.return_value = [evento("INBOUND", "obrigada!", 30)]
        with mock.patch.object(modulo, "_tabela", return_value=tabela),              mock.patch("src.services.db.postgres.PostgresService", return_value=db),              mock.patch("src.services.message_tracker.MessageTracker", return_value=tracker),              mock.patch.object(modulo, "_agora", return_value=AGORA):
            primeiro = modulo.handler({}, None)
            segundo = modulo.handler({}, None)

        self.assertEqual(primeiro["conflitos"], 0)
        self.assertEqual(primeiro["calados"], 1)
        self.assertEqual(tabela.escritas, 1, "duas transicoes, uma escrita")
        self.assertEqual(tabela.item["handler"], at.COOLDOWN, "o espelho que a GSI le")
        self.assertEqual(tabela.item["session"][at.CAMPO]["versao"], 5)
        self.assertEqual(tabela.item["session"][at.CAMPO]["alerta"], retomada.FECHO_SOCIAL)
        self.assertEqual(segundo["vencidos"], 0, "nao volta no ciclo seguinte")

    def test_sem_itens_nao_toca_em_nada(self):
        from src.functions.atendimento import expira as modulo
        tabela = mock.MagicMock(); tabela.query.return_value = {"Items": []}
        with mock.patch.object(modulo, "_tabela", return_value=tabela):
            r = modulo.handler({}, None)
        self.assertEqual(r["vencidos"], 0)


if __name__ == "__main__":
    unittest.main()
