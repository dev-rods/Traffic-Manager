# -*- coding: utf-8 -*-
"""O agente não afirma fato sem ter consultado.

Um invariante, quatro defesas, na ordem em que agem numa mensagem:

  1. PRÉ-CARGA          consulta o que dá para consultar antes de o modelo ler
  2. CONSULTA OBRIGATÓRIA  força uma tool na primeira rodada
  3. CORREÇÃO           afirmou sem respaldo? manda consultar e refaz
  4. BLOQUEIO           insistiu? a resposta não sai e vai para especialista

Cada defesa nasceu de uma falha real em 02-03/09/2026, e as quatro juntas são
o que impede a próxima. Os testes ficam aqui juntos porque testam o mesmo
comportamento em camadas - antes estavam espalhados por arquivo-do-dia
(precarga / bloqueio / efeito), que é organização por data de incidente, não
por comportamento.

Classificação de mensagem está em test_roteador.py e extração de fato em
test_proveniencia.py: são funções puras, testadas sem agente.
"""
import unittest

from tests.unit.dublagem_agente import (
    CLINIC,
    AnthropicFalso,
    AnthropicRoteiro,
    ToolExecutorFalso,
    mensagem,
    monta_agente,
    texto_do_modelo,
    usa_tool,
)
from src.services.conversation_agent import TOOLS_COM_EFEITO


class TestPreCarga(unittest.TestCase):
    """1. Consultar antes de o modelo escrever.

    Em 02/09 o bot afirmou que um agendamento cancelado estava confirmado:
    releu a própria mensagem de três dias antes e não chamou tool nenhuma.
    """

    def test_pergunta_de_preco_consulta_antes_de_chamar_o_modelo(self):
        ordem = []
        agente = monta_agente(
            resultado_da_tool={"services": [{"name": "Virilha", "price": 150}]},
            registro_de_ordem=ordem,
        )

        agente.process_message(CLINIC, mensagem("quanto custa a virilha?"))

        self.assertEqual(ordem, ["list_services", "list_areas", "MODELO"])

    def test_pergunta_de_agendamento_consulta_lookup_appointments(self):
        executor = ToolExecutorFalso()
        agente = monta_agente(tool_executor=executor)

        agente.process_message(CLINIC, mensagem("quando é minha sessão?"))

        self.assertEqual(executor.chamadas, ["lookup_appointments"])

    def test_resultado_chega_ao_modelo_como_fonte_unica(self):
        anthropic = AnthropicFalso()
        agente = monta_agente(anthropic, resultado_da_tool={"appointments": [{"status": "CANCELLED"}]})

        agente.process_message(CLINIC, mensagem("meu agendamento está confirmado?"))

        turno = anthropic.conversas[0][-1]["content"]
        self.assertIn("DADOS CONSULTADOS AGORA", turno)
        self.assertIn("CANCELLED", turno)
        self.assertIn("ÚNICA fonte válida", turno)
        self.assertIn("meu agendamento está confirmado?", turno)

    def test_gatilho_sintetico_nao_dispara_precarga(self):
        """Ninguém perguntou nada: é a clínica iniciando a conversa."""
        executor = ToolExecutorFalso()
        agente = monta_agente(tool_executor=executor)

        agente.process_message(CLINIC, mensagem("__INICIAR_CONVERSA__"))

        self.assertEqual(executor.chamadas, [])

    def test_tool_que_falha_nao_derruba_a_resposta(self):
        """Banco fora do ar degrada a resposta, não cala o bot."""
        anthropic = AnthropicFalso()
        executor = ToolExecutorFalso(erro=RuntimeError("conexão recusada"))
        agente = monta_agente(anthropic, tool_executor=executor)

        saida = agente.process_message(CLINIC, mensagem("quanto custa?"))

        self.assertTrue(saida)
        self.assertNotIn("DADOS CONSULTADOS AGORA", anthropic.prompts[0])


class TestPrefixoCacheavel(unittest.TestCase):
    """O prefixo cacheado é tools + system. Dado volátil ali dentro invalida
    tudo depois dele, e voltamos a pagar os ~17k chars por mensagem."""

    def test_system_prompt_nao_carrega_dado_volatil(self):
        anthropic = AnthropicFalso()
        agente = monta_agente(anthropic, resultado_da_tool={"appointments": [{"status": "CANCELLED"}]})

        agente.process_message(CLINIC, mensagem("meu agendamento está confirmado?"))

        self.assertNotIn("DADOS CONSULTADOS AGORA", anthropic.prompts[0])
        self.assertNotIn("CANCELLED", anthropic.prompts[0])

    def test_prefixo_identico_entre_as_chamadas_da_mesma_mensagem(self):
        """2 a 4 chamadas por mensagem: da segunda em diante tem que ser leitura."""
        anthropic = AnthropicRoteiro([
            usa_tool("list_areas"),
            texto_do_modelo("Pronto!"),
        ])
        agente = monta_agente(anthropic)

        agente.process_message(CLINIC, mensagem("quais áreas vocês atendem?"))

        self.assertGreaterEqual(len(anthropic.prompts), 2)
        self.assertEqual(anthropic.prompts[0], anthropic.prompts[1])


class TestConsultaObrigatoria(unittest.TestCase):
    """2. O modelo escolhe QUAL tool, não escolhe SE consulta.

    Deixar a decisão com ele produziu tools=0 duas vezes no mesmo dia, a
    segunda já com a regra em caixa alta no prompt.
    """

    def test_mensagem_factual_forca_tool_na_primeira_rodada(self):
        anthropic = AnthropicRoteiro([texto_do_modelo("Claro!")])
        agente = monta_agente(anthropic)

        agente.process_message(CLINIC, mensagem("quais horarios tem?"))

        self.assertEqual(anthropic.forcados[0], {"type": "any"})

    def test_conversa_comum_nao_forca_nada(self):
        """Forçar sempre gastaria uma tool em "oi, tudo bem?"."""
        anthropic = AnthropicRoteiro([texto_do_modelo("Oi! Tudo ótimo 😊")])
        agente = monta_agente(anthropic)

        agente.process_message(CLINIC, mensagem("oi, tudo bem?"))

        self.assertIsNone(anthropic.forcados[0])

    def test_conversa_comum_nao_consulta_nem_polui_o_prompt(self):
        anthropic = AnthropicFalso()
        executor = ToolExecutorFalso()
        agente = monta_agente(anthropic, tool_executor=executor)

        agente.process_message(CLINIC, mensagem("oi, tudo bem?"))

        self.assertEqual(executor.chamadas, [])
        self.assertNotIn("DADOS CONSULTADOS AGORA", anthropic.prompts[0])


class TestSeCorrigeAntesDeTransferir(unittest.TestCase):
    """3. Inventar uma vez não pode custar a conversa.

    A primeira versão transferia direto e transformava erro recuperável em
    trabalho manual para a clínica.
    """

    def test_inventou_e_depois_consultou_responde_normalmente(self):
        anthropic = AnthropicRoteiro([
            texto_do_modelo("Para 23/09 tenho 13:00 e 13:30."),      # inventou
            usa_tool("get_time_slots", {"date": "2026-09-23"}),      # foi mandado consultar
            texto_do_modelo("Nesse dia tenho 18:00 e 18:15."),       # respondeu com o que voltou
        ])
        agente = monta_agente(anthropic, resultado_da_tool={"available_slots": ["18:00", "18:15"]})

        saida = agente.process_message(CLINIC, mensagem("e horários à tarde?"))
        enviado = " ".join(m.content for m in saida)

        self.assertIn("18:00", enviado)
        self.assertNotIn("13:00", enviado)
        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")

    def test_a_correcao_e_explicita_para_o_modelo(self):
        anthropic = AnthropicRoteiro([
            texto_do_modelo("Para 23/09 tenho 13:00."),
            texto_do_modelo("Nesse dia tenho 18:00."),
        ])
        agente = monta_agente(anthropic, resultado_da_tool={"available_slots": ["18:00"]})

        agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertTrue(anthropic.correcoes)
        self.assertIn("Chame agora a tool", anthropic.correcoes[0])

    def test_refaz_no_maximo_uma_vez(self):
        """Sem teto, uma conversa ruim viraria cinco chamadas de modelo."""
        anthropic = AnthropicRoteiro([texto_do_modelo("Para 23/09 tenho 13:00.")] * 3)
        agente = monta_agente(anthropic)

        agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertEqual(len(anthropic.forcados), 2)


class TestBloqueio(unittest.TestCase):
    """4. Data e horário sem respaldo não chegam na paciente.

    Só data e horário derrubam a mensagem. Preço, duração e status são
    registrados: erram para o lado do constrangimento, não o da paciente que
    atravessa a cidade para um horário que não existe.
    """

    ROTEIRO_TEIMOSO = [
        texto_do_modelo("Para 23/09 tenho 13:00 e 13:30."),
        texto_do_modelo("Para 23/09 tenho 13:00 e 13:30 mesmo."),
    ]

    def test_horario_inventado_nao_chega_na_paciente(self):
        agente = monta_agente(AnthropicRoteiro(list(self.ROTEIRO_TEIMOSO)))

        saida = agente.process_message(CLINIC, mensagem("e horários à tarde?"))
        enviado = " ".join(m.content for m in saida)

        self.assertNotIn("13:00", enviado)
        self.assertNotIn("13:30", enviado)

    def test_bloqueio_transfere_para_especialista(self):
        agente = monta_agente(AnthropicRoteiro(list(self.ROTEIRO_TEIMOSO)))

        agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")
        self.assertTrue(agente.sessao_salva.get("attendant_active_until"))

    def test_a_pessoa_recebe_uma_resposta_e_nao_silencio(self):
        agente = monta_agente(AnthropicRoteiro(list(self.ROTEIRO_TEIMOSO)))

        saida = agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertTrue(saida)
        self.assertTrue(saida[0].content.strip())


class TestNaoBloqueiaDemais(unittest.TestCase):
    """O outro lado: bloquear demais calaria o bot na resposta mais comum."""

    def test_horario_vindo_da_tool_passa(self):
        anthropic = AnthropicFalso("Tenho 18:00 e 18:15 nesse dia.")
        agente = monta_agente(anthropic, resultado_da_tool={"available_slots": ["18:00", "18:15"]})

        saida = agente.process_message(CLINIC, mensagem("quais horarios tem?"))

        self.assertIn("18:00", " ".join(m.content for m in saida))
        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")

    def test_conversa_sem_data_nem_horario_passa(self):
        agente = monta_agente(AnthropicFalso("Claro! O laser é praticamente indolor 😊"))

        saida = agente.process_message(CLINIC, mensagem("dói muito?"))

        self.assertIn("indolor", " ".join(m.content for m in saida))
        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")

    def test_preco_sem_respaldo_registra_mas_nao_bloqueia(self):
        """Preço errado constrange; não faz ninguém perder a tarde."""
        agente = monta_agente(AnthropicFalso("Fica R$ 250,00 no total."))

        saida = agente.process_message(CLINIC, mensagem("quanto custa?"))

        self.assertIn("250", " ".join(m.content for m in saida))
        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")


class TestEfeitoJaCometido(unittest.TestCase):
    """"Efeito só no fim" - e quando o efeito escapa para o meio, a mensagem
    tem que contá-lo.

    book_appointment roda dentro do loop. Bloquear depois dele trocando a
    mensagem por "vou confirmar" deixaria a pessoa com uma sessão marcada que
    ela não sabe que tem.
    """

    ROTEIRO = [
        usa_tool("book_appointment", {"date": "2026-09-23"}),
        texto_do_modelo("Pronto! Sua sessão é 23/09 às 09:15."),  # 09:15 nao veio de tool
    ]
    RESULTADO = {"success": True, "appointment_id": "abc", "date": "2026-09-23",
                 "time": "07:45", "status": "CONFIRMED"}

    def test_as_tres_tools_que_mudam_o_mundo(self):
        self.assertEqual(
            TOOLS_COM_EFEITO,
            frozenset({"book_appointment", "reschedule_appointment", "cancel_appointment"}),
        )

    def test_consulta_nao_e_efeito(self):
        for nome in ["get_time_slots", "list_areas", "calculate_duration",
                     "calculate_discount", "get_faq_answer"]:
            with self.subTest(tool=nome):
                self.assertNotIn(nome, TOOLS_COM_EFEITO)

    def test_horario_inventado_nao_sai(self):
        agente = monta_agente(AnthropicRoteiro(list(self.ROTEIRO)), resultado_da_tool=self.RESULTADO)

        saida = agente.process_message(CLINIC, mensagem("confirma pra mim"))

        self.assertNotIn("09:15", " ".join(m.content for m in saida))

    def test_mensagem_avisa_que_algo_foi_registrado(self):
        """Nunca "vou confirmar" puro: isso esconderia o agendamento criado."""
        agente = monta_agente(AnthropicRoteiro(list(self.ROTEIRO)), resultado_da_tool=self.RESULTADO)

        saida = agente.process_message(CLINIC, mensagem("confirma pra mim"))

        self.assertIn("registrei", " ".join(m.content for m in saida).lower())

    def test_transfere_para_especialista(self):
        agente = monta_agente(AnthropicRoteiro(list(self.ROTEIRO)), resultado_da_tool=self.RESULTADO)

        agente.process_message(CLINIC, mensagem("confirma pra mim"))

        self.assertEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")

    def test_nao_refaz_depois_do_efeito(self):
        """Refazer convidaria o modelo a chamar book_appointment de novo."""
        anthropic = AnthropicRoteiro(list(self.ROTEIRO))
        agente = monta_agente(anthropic, resultado_da_tool=self.RESULTADO)

        agente.process_message(CLINIC, mensagem("confirma pra mim"))

        self.assertEqual(anthropic.chamadas, 2)

    def test_sem_efeito_a_mensagem_e_a_de_confirmar_horarios(self):
        anthropic = AnthropicRoteiro([
            texto_do_modelo("Tenho 13:00 e 13:30."),
            texto_do_modelo("Tenho 13:00 e 13:30 mesmo."),
        ])
        agente = monta_agente(anthropic)

        saida = agente.process_message(CLINIC, mensagem("e de tarde?"))
        enviado = " ".join(m.content for m in saida).lower()

        self.assertIn("confirmar os horários", enviado)
        self.assertNotIn("registrei", enviado)


if __name__ == "__main__":
    unittest.main()
