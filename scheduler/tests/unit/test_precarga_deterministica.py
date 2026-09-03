"""A consulta ao banco acontece antes de o modelo escrever.

Em 02/09/2026 o bot afirmou que um agendamento cancelado estava confirmado:
releu a própria mensagem de três dias antes e não chamou tool nenhuma. Deixar a
decisão de consultar com o modelo é o defeito - quando ele erra, erra em
silêncio e com a confiança de quem lembra.

A pré-carga tira essa decisão dele. Estes testes cobrem o caminho dentro de
`process_message`, que é onde o `NameError` dos imports faltantes passou
despercebido: o roteador tinha teste próprio, a costura com o agente não tinha.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.providers.whatsapp_provider import IncomingMessage
from src.services.conversation_agent import ConversationAgent

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"


class ToolExecutorFalso:
    """Registra o que foi chamado, na ordem em que foi chamado."""

    def __init__(self, resultado=None, erro=None):
        self.chamadas = []
        self._resultado = resultado if resultado is not None else {"ok": True}
        self._erro = erro

    def execute(self, nome, args, context=None):
        self.chamadas.append(nome)
        if self._erro:
            raise self._erro
        return self._resultado


class AnthropicFalso:
    """Responde texto puro, sem pedir tool - o cenário do incidente."""

    def __init__(self, texto="Sua sessão está confirmada para amanhã."):
        self.prompts = []
        self.forcados = []
        self._texto = texto

    def create_message(self, system, messages, tools, max_tokens, tool_choice=None):
        self.prompts.append(system)
        self.forcados.append(tool_choice)
        return {
            "content": [{"type": "text", "text": self._texto}],
            "stop_reason": "end_turn",
        }


def monta_agente(tool_executor, anthropic, registro_de_ordem=None):
    """Um ConversationAgent sem AWS, sem banco e sem rede.

    `__init__` abre DynamoDB e Anthropic de verdade, então o objeto é criado
    direto e só o que a pré-carga toca é preenchido.
    """
    agente = object.__new__(ConversationAgent)
    agente.tool_executor = tool_executor
    agente.anthropic = anthropic
    agente._load_session = lambda clinic_id, phone: {}
    agente._is_attendant_active = lambda session: False
    agente._build_system_prompt = lambda clinic_id, phone: "PROMPT BASE"
    agente._save_session = lambda clinic_id, phone, session: None

    if registro_de_ordem is not None:
        tool_executor.chamadas = registro_de_ordem

        original = anthropic.create_message

        def create_message(system, messages, tools, max_tokens, tool_choice=None):
            registro_de_ordem.append("MODELO")
            return original(system, messages, tools, max_tokens, tool_choice)

        anthropic.create_message = create_message

    return agente


def mensagem(texto):
    return IncomingMessage(
        message_id="m1",
        phone=PHONE,
        sender_name="Fulana",
        timestamp=0,
        message_type="TEXT",
        content=texto,
    )


class TestPreCarga(unittest.TestCase):
    def test_pergunta_sobre_preco_consulta_antes_de_chamar_o_modelo(self):
        ordem = []
        executor = ToolExecutorFalso(resultado={"services": [{"name": "Virilha", "price": 150}]})
        agente = monta_agente(executor, AnthropicFalso(), registro_de_ordem=ordem)

        agente.process_message(CLINIC, mensagem("quanto custa a virilha?"))

        self.assertEqual(ordem, ["list_services", "list_areas", "MODELO"])

    def test_pergunta_sobre_agendamento_consulta_lookup_appointments(self):
        executor = ToolExecutorFalso()
        agente = monta_agente(executor, AnthropicFalso())

        agente.process_message(CLINIC, mensagem("quando é minha sessão?"))

        self.assertEqual(executor.chamadas, ["lookup_appointments"])

    def test_resultado_entra_no_prompt_como_fonte_unica(self):
        anthropic = AnthropicFalso()
        executor = ToolExecutorFalso(resultado={"appointments": [{"status": "CANCELLED"}]})
        agente = monta_agente(executor, anthropic)

        agente.process_message(CLINIC, mensagem("meu agendamento está confirmado?"))

        prompt = anthropic.prompts[0]
        self.assertIn("DADOS CONSULTADOS AGORA", prompt)
        self.assertIn("CANCELLED", prompt)
        self.assertIn("ÚNICA fonte válida", prompt)

    def test_conversa_comum_nao_consulta_nem_polui_o_prompt(self):
        """Sem intenção que exija dado, nenhuma latência extra."""
        anthropic = AnthropicFalso()
        executor = ToolExecutorFalso()
        agente = monta_agente(executor, anthropic)

        agente.process_message(CLINIC, mensagem("oi, tudo bem?"))

        self.assertEqual(executor.chamadas, [])
        self.assertNotIn("DADOS CONSULTADOS AGORA", anthropic.prompts[0])

    def test_gatilho_sintetico_nao_dispara_precarga(self):
        """Ninguém perguntou nada: é a clínica iniciando a conversa."""
        executor = ToolExecutorFalso()
        agente = monta_agente(executor, AnthropicFalso())

        agente.process_message(CLINIC, mensagem("__INICIAR_CONVERSA__"))

        self.assertEqual(executor.chamadas, [])

    def test_tool_que_falha_nao_derruba_a_resposta(self):
        """Banco fora do ar degrada a resposta, não cala o bot."""
        anthropic = AnthropicFalso()
        executor = ToolExecutorFalso(erro=RuntimeError("conexão recusada"))
        agente = monta_agente(executor, anthropic)

        saida = agente.process_message(CLINIC, mensagem("quanto custa?"))

        self.assertTrue(saida)
        self.assertNotIn("DADOS CONSULTADOS AGORA", anthropic.prompts[0])


class TestImportsDaCostura(unittest.TestCase):
    """O defeito que passou: os símbolos usados em `process_message` existiam
    em seus módulos, mas não estavam importados no agente."""

    def test_simbolos_estao_ligados_no_modulo_do_agente(self):
        import src.services.conversation_agent as agente

        self.assertTrue(callable(agente.intencoes))
        self.assertTrue(callable(agente.tools_obrigatorias))
        self.assertTrue(callable(agente.fatos_sem_origem))


if __name__ == "__main__":
    unittest.main()
