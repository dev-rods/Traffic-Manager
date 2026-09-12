"""Retomada de conversa: o bot responde o que ficou em aberto.

Quando alguém ativa o bot no painel, a conversa pode ter parado numa pergunta
sem resposta. Sem olhar o histórico, o bot ficaria mudo esperando a pessoa
escrever de novo - justamente quem já escreveu e não foi respondido.

Duas decisões distintas são testadas aqui:
  1. QUANDO falar - só se a última mensagem for da pessoa (ninguém respondeu).
  2. COM QUE CONTEXTO - as mensagens recentes, não as antigas.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services.conversation_resume import ha_pergunta_em_aberto


def evento(direction, content, sk="MSG#2026-08-29T10:00:00Z#x"):
    return {"direction": direction, "content": content, "sk": sk}


class TestPerguntaEmAberto(unittest.TestCase):
    """O guard que evita mandar mensagem do nada."""

    def test_ultima_e_da_pessoa_entao_ficou_em_aberto(self):
        eventos = [
            evento("INBOUND", "oi, quanto custa?"),
            evento("OUTBOUND", "Depende das áreas."),
            evento("INBOUND", "e a virilha?"),
        ]
        self.assertTrue(ha_pergunta_em_aberto(eventos))

    def test_ultima_e_do_bot_entao_nao_ha_nada_pendente(self):
        """Conversa encerrada. Ativar o bot não pode gerar mensagem do nada."""
        eventos = [
            evento("INBOUND", "Faz sentido, muito obrigado"),
            evento("OUTBOUND", "Fico feliz em ajudar! Até dia 23 😊"),
        ]
        self.assertFalse(ha_pergunta_em_aberto(eventos))

    def test_ignora_eventos_sem_conteudo(self):
        """Webhooks de status entram no MessageEvents sem texto e não são fala."""
        eventos = [
            evento("INBOUND", "tem horário sábado?"),
            evento("OUTBOUND", ""),
            evento("OUTBOUND", None),
            evento("OUTBOUND", "   "),
        ]
        self.assertTrue(ha_pergunta_em_aberto(eventos))

    def test_conversa_vazia_nao_gera_mensagem(self):
        self.assertFalse(ha_pergunta_em_aberto([]))
        self.assertFalse(ha_pergunta_em_aberto(None))

    def test_so_mensagens_do_bot_nao_gera_mensagem(self):
        """Disparo de campanha que ninguém respondeu: não há dúvida em aberto."""
        eventos = [evento("OUTBOUND", "Oi! Temos horários disponíveis ✨")]
        self.assertFalse(ha_pergunta_em_aberto(eventos))


class FakeTable:
    """Reproduz a ordenação do DynamoDB: sort key ascendente por padrão."""

    def __init__(self, itens):
        self.itens = itens
        self.ultima_chamada = {}

    def query(self, **kwargs):
        self.ultima_chamada = kwargs
        ordenados = sorted(self.itens, key=lambda x: x["sk"])
        if kwargs.get("ScanIndexForward") is False:
            ordenados = list(reversed(ordenados))
        return {"Items": ordenados[: kwargs.get("Limit", 50)]}


class TestJanelaRecente(unittest.TestCase):
    """O histórico tem que vir do fim da conversa, não do começo.

    39% das conversas da Essência passam de 20 eventos. Lendo do começo, o bot
    reconstruía disparos de campanha de meses atrás e não via o que a pessoa
    acabou de perguntar.
    """

    def setUp(self):
        from src.services.message_tracker import MessageTracker

        self.tracker = MessageTracker.__new__(MessageTracker)
        itens = [
            evento("INBOUND", f"mensagem {i}", sk=f"MSG#2026-08-{i+1:02d}T10:00:00Z#{i}")
            for i in range(30)
        ]
        self.tabela = FakeTable(itens)
        self.tracker.table = self.tabela

    def test_devolve_as_mais_recentes(self):
        msgs = self.tracker.get_conversation_messages("c", "5511999999999", limit=5)

        self.assertEqual(
            [m["content"] for m in msgs],
            ["mensagem 25", "mensagem 26", "mensagem 27", "mensagem 28", "mensagem 29"],
        )

    def test_devolve_em_ordem_cronologica(self):
        """Quem lê espera a conversa de cima para baixo, da mais antiga para a nova."""
        msgs = self.tracker.get_conversation_messages("c", "5511999999999", limit=10)

        self.assertEqual(msgs, sorted(msgs, key=lambda m: m["sk"]))

    def test_conversa_menor_que_o_limite_vem_inteira(self):
        msgs = self.tracker.get_conversation_messages("c", "5511999999999", limit=100)

        self.assertEqual(len(msgs), 30)
        self.assertEqual(msgs[0]["content"], "mensagem 0")


class FakeContext:
    invoked_function_arn = "arn:aws:lambda:us-east-1:796000356030:function:teste"


class TestAgendamentoDaResposta(unittest.TestCase):
    """O deactivate decide se vale a pena falar antes de gastar uma invocação.

    O envio sai do request porque o agente leva de 3 a 15s e o API Gateway corta
    em 29: falhar ali mostraria erro na tela com a mensagem já enviada.
    """

    def setUp(self):
        from unittest.mock import MagicMock, patch

        self.patcher_tracker = patch("src.services.message_tracker.MessageTracker")
        self.patcher_boto = patch("src.functions.attendant.handler.boto3")
        self.tracker_cls = self.patcher_tracker.start()
        self.boto = self.patcher_boto.start()
        self.addCleanup(self.patcher_tracker.stop)
        self.addCleanup(self.patcher_boto.stop)
        self.lambda_client = MagicMock()
        self.boto.client.return_value = self.lambda_client

    def _agendar(self, eventos):
        from src.functions.attendant.handler import _agendar_retomada

        self.tracker_cls.return_value.get_conversation_messages.return_value = eventos
        return _agendar_retomada("clinica-x", "5511999999999", FakeContext())

    def test_pergunta_em_aberto_dispara_a_resposta(self):
        agendou = self._agendar([evento("INBOUND", "tem horário sábado?")])

        self.assertTrue(agendou)
        self.lambda_client.invoke.assert_called_once()
        chamada = self.lambda_client.invoke.call_args.kwargs
        self.assertEqual(chamada["InvocationType"], "Event")

    def test_conversa_encerrada_nao_dispara_nada(self):
        """Ativar o bot numa conversa já respondida não pode gerar mensagem."""
        agendou = self._agendar([
            evento("INBOUND", "obrigado!"),
            evento("OUTBOUND", "Imagina! Até dia 23 😊"),
        ])

        self.assertFalse(agendou)
        self.lambda_client.invoke.assert_not_called()

    def test_falha_ao_agendar_nao_derruba_a_ativacao(self):
        """O bot já foi ativado e salvo; responder o pendente é um extra."""
        self.lambda_client.invoke.side_effect = RuntimeError("sem permissão")

        agendou = self._agendar([evento("INBOUND", "e a virilha?")])

        self.assertFalse(agendou)


class TestRoteamentoDaExecucaoAssincrona(unittest.TestCase):
    """O evento assíncrono não tem httpMethod nem chave de API.

    Se caísse no roteamento HTTP, viraria 404 e a resposta nunca sairia — sem
    erro visível, porque ninguém lê o retorno de uma invocação Event.
    """

    def test_payload_interno_chama_a_retomada_e_nao_o_roteador_http(self):
        from unittest.mock import patch

        from src.functions.attendant.handler import TAREFA_RETOMADA, handler

        evento_async = {
            "internal_task": TAREFA_RETOMADA,
            "clinic_id": "clinica-x",
            "phone": "5511999999999",
        }

        with patch(
            "src.services.conversation_resume.responder_se_ficou_em_aberto",
            return_value=True,
        ) as responder:
            resultado = handler(evento_async, FakeContext())

        responder.assert_called_once_with("clinica-x", "5511999999999")
        self.assertEqual(resultado, {"replied": True})

    def test_requisicao_http_normal_continua_roteando(self):
        """A guarda nova não pode engolir o tráfego do painel."""
        from src.functions.attendant.handler import handler

        resposta = handler({"httpMethod": "GET", "path": "/rota-inexistente"}, FakeContext())

        self.assertEqual(resposta["statusCode"], 401)
