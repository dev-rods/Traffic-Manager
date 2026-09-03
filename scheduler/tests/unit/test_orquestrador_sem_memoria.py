"""O agente não responde de memória: consulta é o padrão, não a exceção.

O desenho anterior forçava consulta só quando um regex reconhecia o assunto, e
a lista de assuntos factuais não tem fim - "E horários à tarde?" não casava com
nada e o bot listou dez horários inventados. Aqui a lista curta é a de conversa
fiada, e errar para o lado de consultar custa uma tool, não uma paciente
esperando num dia que não existe.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.proveniencia import fatos_sem_origem, fatos_sensiveis
from src.services.roteador import exige_consulta


class TestConsultaEhOPadrao(unittest.TestCase):
    def test_a_frase_que_escapou_do_regex_agora_exige_consulta(self):
        self.assertTrue(exige_consulta("E horários à tarde?"))

    def test_duvidas_de_faq_exigem_consulta(self):
        """Antes iam direto para a memória: o FAQ inteiro estava no prompt."""
        for frase in [
            "dói muito?",
            "quantas sessões preciso?",
            "posso fazer bronzeada?",
            "pode parcelar?",
            "vocês atendem sábado?",
        ]:
            with self.subTest(frase=frase):
                self.assertTrue(exige_consulta(frase))

    def test_frase_afirmativa_sobre_assunto_factual_exige_consulta(self):
        for frase in ["quero agendar", "buço e axilas", "pode ser 14h"]:
            with self.subTest(frase=frase):
                self.assertTrue(exige_consulta(frase))


class TestExcecoes(unittest.TestCase):
    """A lista curta: saudação, agradecimento, confirmação e dado de cadastro."""

    def test_social(self):
        for frase in ["oi", "bom dia", "tudo bem?", "obrigado!", "valeu", "tchau",
                      "sim", "ok", "perfeito", "beleza", "entendi"]:
            with self.subTest(frase=frase):
                self.assertFalse(exige_consulta(frase))

    def test_social_emendado(self):
        """"oi, tudo bem?" são duas expressões sociais, não uma pergunta."""
        for frase in ["oi, tudo bem?", "bom dia, tudo bem?", "obrigado, valeu!"]:
            with self.subTest(frase=frase):
                self.assertFalse(exige_consulta(frase))

    def test_social_mais_pergunta_exige_consulta(self):
        """Basta um pedaço não ser conversa fiada."""
        self.assertTrue(exige_consulta("oi, quanto custa?"))

    def test_dado_de_cadastro(self):
        for frase in ["André Felipe", "1999", "12/05/1990", "andre@gmail.com",
                      "123.456.789-00"]:
            with self.subTest(frase=frase):
                self.assertFalse(exige_consulta(frase))

    def test_nome_em_minusculo_erra_para_o_lado_de_consultar(self):
        """Custa uma tool. O erro contrário custa uma alucinação."""
        self.assertTrue(exige_consulta("andre felipe"))

    def test_vazio_nao_consulta(self):
        self.assertFalse(exige_consulta(""))
        self.assertFalse(exige_consulta(None))


class TestFalsosPositivosCorrigidos(unittest.TestCase):
    """Os três que apareceram numa única conversa de produção em 02/09/2026."""

    def test_tempo_de_caminhada_nao_e_duracao_de_sessao(self):
        """O endereço diz "13 minutos a pé"; não é a duração do atendimento."""
        texto = "Estação Oscar Freire, cerca de 13 minutos a pé."

        self.assertNotIn("duracao:13", fatos_sensiveis(texto))

    def test_duracao_de_sessao_continua_sendo_extraida(self):
        self.assertIn("duracao:35", fatos_sensiveis("A sessão dura 35 minutos."))

    def test_outros_meios_de_transporte(self):
        for texto in ["10 minutos de carro", "5 min de metrô", "20 minutos de ônibus"]:
            with self.subTest(texto=texto):
                self.assertEqual(fatos_sensiveis(texto), set())

    def test_confirmado_como_interjeicao_nao_e_status(self):
        """"Confirmado: o horário 07:45 está disponível" é concordância."""
        achados = fatos_sensiveis("Confirmado: o horário 07:45 está disponível.")

        self.assertNotIn("status:confirmado", achados)
        self.assertIn("07:45", achados)

    def test_status_de_verdade_continua_sendo_extraido(self):
        self.assertIn("status:confirmado", fatos_sensiveis("Sua sessão está confirmada."))

    def test_valor_consultado_na_rodada_anterior_tem_respaldo(self):
        """A confirmação repete o preço que calculate_discount deu antes.

        O respaldo era por execução, então repetir o que acabou de ser
        consultado era acusado de invenção.
        """
        # As chaves são as que calculate_discount devolve de verdade.
        rodada_anterior = [{
            "discount_pct": 10,
            "original_price_cents": 24500,
            "discounted_price_cents": 22050,
        }]

        self.assertEqual(
            fatos_sem_origem("Total: R$ 220,50", rodada_anterior), set()
        )


if __name__ == "__main__":
    unittest.main()
