"""Quais afirmações de uma resposta precisam ter vindo do banco.

Em 02/09/2026 o bot respondeu "Sim, está confirmada!" sobre um agendamento
cancelado dois dias antes. Ele não inventou: releu a própria mensagem de 29/08,
quando a informação ainda era verdadeira. O prompt já proibia "informação de
memória própria" - e o modelo entendeu, corretamente, que reler a conversa não
é memória.

Instrução não segura esse caso. Conferência sim.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services.proveniencia import fatos_sensiveis, fatos_sem_origem


class TestDatas(unittest.TestCase):
    def test_data_curta(self):
        self.assertIn("2026-09-23", fatos_sensiveis("Sua sessão é 23/09/2026"))

    def test_data_sem_ano_assume_o_corrente(self):
        self.assertIn("2026-09-23", fatos_sensiveis("Sua sessão é 23/09", ano=2026))

    def test_data_por_extenso(self):
        self.assertIn("2026-09-23", fatos_sensiveis("quarta, 23 de setembro", ano=2026))

    def test_data_com_ano_por_extenso(self):
        self.assertIn("2027-03-08", fatos_sensiveis("8 de março de 2027"))


class TestHorarios(unittest.TestCase):
    def test_formato_com_h(self):
        self.assertIn("16:44", fatos_sensiveis("às 16h44"))

    def test_formato_com_dois_pontos(self):
        self.assertIn("16:44", fatos_sensiveis("às 16:44"))

    def test_hora_cheia(self):
        self.assertIn("07:00", fatos_sensiveis("às 7h"))


class TestDinheiro(unittest.TestCase):
    def test_reais_com_centavos(self):
        self.assertIn("R$250.00", fatos_sensiveis("Fica R$ 250,00"))

    def test_reais_sem_centavos(self):
        self.assertIn("R$250.00", fatos_sensiveis("Fica R$250"))


class TestStatusDeAgendamento(unittest.TestCase):
    def test_confirmada(self):
        self.assertIn("status:confirmado", fatos_sensiveis("Sim, está confirmada!"))

    def test_cancelada(self):
        self.assertIn("status:cancelado", fatos_sensiveis("Sua sessão foi cancelada"))


class TestTextoSemFato(unittest.TestCase):
    """O guardrail não pode disparar em conversa comum."""

    def test_saudacao(self):
        self.assertEqual(fatos_sensiveis("Oi! Como posso ajudar?"), set())

    def test_agradecimento(self):
        self.assertEqual(fatos_sensiveis("Que bom que gostou 😊"), set())

    def test_numero_de_sessoes_e_conteudo_de_faq(self):
        """'8 a 12 sessões' vem do FAQ, não do banco: não é fato de agenda."""
        self.assertEqual(fatos_sensiveis("Em média são de 8 a 12 sessões"), set())

    def test_pergunta_sobre_horario_nao_afirma_horario(self):
        """Perguntar não é afirmar - só afirmação precisa de origem."""
        self.assertEqual(fatos_sensiveis("Qual horário prefere?"), set())


class TestConferencia(unittest.TestCase):
    def test_o_caso_de_02_09(self):
        """A resposta que motivou este plano precisa ser barrada."""
        resposta = "Sim, está confirmada! Depilação a Laser, quarta, 23/09/2026 às 16h44."
        sem_origem = fatos_sem_origem(resposta, [])
        self.assertTrue(sem_origem, "resposta sem nenhuma tool tem que ser barrada")
        self.assertIn("status:confirmado", sem_origem)

    def test_dado_que_veio_da_tool_passa(self):
        tools = [{"appointment_date": "2026-09-23", "start_time": "16:44",
                  "status": "CONFIRMED"}]
        resposta = "Sua sessão é 23/09/2026 às 16h44, confirmada."
        self.assertEqual(fatos_sem_origem(resposta, tools), set())

    def test_status_divergente_e_barrado(self):
        """A tool disse CANCELLED e a resposta afirmou confirmada."""
        tools = [{"appointment_date": "2026-09-23", "status": "CANCELLED"}]
        self.assertIn("status:confirmado", fatos_sem_origem("Está confirmada!", tools))

    def test_data_diferente_da_tool_e_barrada(self):
        tools = [{"appointment_date": "2026-09-23"}]
        self.assertIn("2026-10-15", fatos_sem_origem("Sua sessão é 15/10/2026", tools))

    def test_preco_que_veio_da_tool_passa(self):
        tools = [{"price_cents": 25000}]
        self.assertEqual(fatos_sem_origem("Fica R$ 250,00", tools), set())

    def test_conversa_sem_fato_nao_precisa_de_tool(self):
        self.assertEqual(fatos_sem_origem("Oi! Como posso ajudar?", []), set())

    def test_tool_aninhada_e_lida(self):
        """Os resultados chegam embrulhados; o valor pode estar em qualquer nível."""
        tools = [{"appointments": [{"appointment_date": "2026-09-23", "status": "CONFIRMED"}]}]
        self.assertEqual(fatos_sem_origem("Dia 23/09/2026, confirmada", tools), set())
