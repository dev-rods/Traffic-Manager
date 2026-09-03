"""O agente não pode afirmar duração sem consultar.

Em 02/09/2026, já com a duração unificada no agendamento, a pergunta "Quanto
tempo dura mesmo a sessão para essas áreas?" foi respondida em 2 segundos com
`tools=0`: nenhuma tool chamada, resposta tirada da memória. Quatro coisas
falharam ao mesmo tempo, e cada teste aqui prende uma delas.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.proveniencia import fatos_sem_origem, fatos_sensiveis
from src.services.roteador import DURACAO, intencoes, tools_obrigatorias


class TestRoteadorReconheceDuracao(unittest.TestCase):
    """1. O roteador não tinha intenção de duração: a frase caía em NENHUMA."""

    def test_a_frase_que_falhou_em_producao(self):
        self.assertIn(DURACAO, intencoes("Quanto tempo dura mesmo a sessão para essas áreas?"))

    def test_variantes_reais(self):
        for frase in [
            "qual a duração da sessão?",
            "quanto tempo demora",
            "quantos minutos leva",
            "quanto tempo dura",
            "quanto duram as sessões",
        ]:
            with self.subTest(frase=frase):
                self.assertIn(DURACAO, intencoes(frase))

    def test_nao_dispara_em_conversa_comum(self):
        for frase in ["oi, tudo bem?", "quanto custa a virilha", "obrigado!"]:
            with self.subTest(frase=frase):
                self.assertNotIn(DURACAO, intencoes(frase))


class TestPreCargaSoUsaToolSemArgumento(unittest.TestCase):
    """4. Regressão: check_availability passou a exigir as áreas.

    A pré-carga chama as tools com argumento vazio. Pré-carregar
    check_availability agora devolveria os dias de uma sessão de 15 minutos - o
    piso - apresentado ao modelo como dado consultado. Mentira com cara de fato.
    """

    SEM_ARGUMENTO = {"lookup_appointments", "list_services", "list_areas"}

    def test_nenhuma_tool_precarregada_exige_argumento(self):
        for nome in [DURACAO, "PRECO", "DISPONIBILIDADE", "AGENDAMENTO_PROPRIO"]:
            for tool in tools_obrigatorias({nome}):
                with self.subTest(intencao=nome, tool=tool):
                    self.assertIn(tool, self.SEM_ARGUMENTO)

    def test_check_availability_saiu_da_precarga(self):
        todas = set()
        for nome in [DURACAO, "PRECO", "DISPONIBILIDADE", "AGENDAMENTO_PROPRIO"]:
            todas.update(tools_obrigatorias({nome}))

        self.assertNotIn("check_availability", todas)
        self.assertNotIn("calculate_duration", todas)


class TestProvenienciaEnxergaDuracao(unittest.TestCase):
    """3. Duração era o único fato sensível sem extrator.

    O verificador logou `ok | tools=0` numa resposta inventada. Falso negativo é
    pior que falso positivo: parece sucesso.
    """

    RESPOSTA = "A sessão dura 35 minutos."

    def test_extrai_duracao_da_resposta(self):
        self.assertIn("duracao:35", fatos_sensiveis(self.RESPOSTA))

    def test_aceita_min_abreviado(self):
        self.assertIn("duracao:50", fatos_sensiveis("Reservei 50 min para você."))

    def test_sem_tool_e_acusado(self):
        self.assertIn("duracao:35", fatos_sem_origem(self.RESPOSTA, []))

    def test_com_a_tool_certa_fica_limpo(self):
        self.assertEqual(fatos_sem_origem(self.RESPOSTA, [{"total_duration_minutes": 35}]), set())

    def test_duracao_divergente_da_tool_e_acusada(self):
        """O modelo disse 35, a tool devolveu 50: continua sem respaldo."""
        self.assertIn("duracao:35", fatos_sem_origem(self.RESPOSTA, [{"total_duration_minutes": 50}]))

    def test_pergunta_sobre_minutos_nao_e_afirmacao(self):
        self.assertEqual(fatos_sem_origem("Quantos minutos você tem disponível?", []), set())


class TestToolDeDuracaoExiste(unittest.TestCase):
    """2. Não havia tool nenhuma que devolvesse a duração da sessão.

    Mesmo querendo obedecer o prompt, o agente não tinha o que chamar.
    """

    def test_tool_esta_exposta_ao_modelo(self):
        from src.services.ai_tools import get_tool_definitions

        nomes = {t["name"] for t in get_tool_definitions(format="anthropic")}

        self.assertIn("calculate_duration", nomes)

    def test_executor_responde_pelo_nome(self):
        from src.services.ai_tools import ToolExecutor

        self.assertTrue(hasattr(ToolExecutor, "_tool_calculate_duration"))

    def test_list_areas_nao_expoe_duracao_por_area(self):
        """Ver a duração de cada área convida o modelo a somar sozinho."""
        import inspect

        from src.services.ai_tools import ToolExecutor

        corpo = inspect.getsource(ToolExecutor._tool_list_areas)
        depois_do_select = corpo.split("areas.append")[1]

        self.assertNotIn('"duration_minutes"', depois_do_select)


if __name__ == "__main__":
    unittest.main()
