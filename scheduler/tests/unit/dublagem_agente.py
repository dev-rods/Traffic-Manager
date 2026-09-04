# -*- coding: utf-8 -*-
"""Dublês para exercitar o ConversationAgent sem AWS, sem banco e sem rede.

Estavam copiados em quatro arquivos de teste, cada cópia com uma diferença
pequena - um registrava os prompts, outro os `tool_choice`, outro nenhum dos
dois. Quando o agente ganhou o parâmetro `tool_choice`, seis testes quebraram
de uma vez por causa da assinatura repetida em lugares diferentes.

Aqui é um dublê só, com tudo que os testes precisam observar.
"""
import os

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
    """Responde sempre a mesma coisa e guarda tudo que recebeu.

    As listas são o que os testes inspecionam:
      prompts    o system prompt de cada chamada (invariante de cache)
      conversas  cópia das mensagens no momento da chamada
      forcados   o tool_choice de cada chamada (consulta obrigatória)
      correcoes  as mensagens PARE. que o agente injetou
    """

    def __init__(self, texto="Sua sessão está confirmada para amanhã."):
        self.prompts = []
        self.conversas = []
        self.forcados = []
        self.correcoes = []
        self.chamadas = 0
        self._texto = texto

    def _registra(self, system, messages, tool_choice):
        self.chamadas += 1
        self.prompts.append(system)
        # Cópia: o agente anexa turnos DEPOIS da chamada, e guardar a referência
        # faria o teste ler a conversa do futuro.
        self.conversas.append(list(messages))
        self.forcados.append(tool_choice)
        ultima = messages[-1].get("content") if messages else ""
        if isinstance(ultima, str) and ultima.startswith("PARE."):
            self.correcoes.append(ultima)

    def create_message(self, system, messages, tools, max_tokens, tool_choice=None):
        self._registra(system, messages, tool_choice)
        return texto_do_modelo(self._texto)


class AnthropicRoteiro(AnthropicFalso):
    """Responde uma coisa diferente por chamada, na ordem do roteiro."""

    def __init__(self, roteiro):
        super().__init__()
        self._roteiro = list(roteiro)

    def create_message(self, system, messages, tools, max_tokens, tool_choice=None):
        self._registra(system, messages, tool_choice)
        return self._roteiro.pop(0) if self._roteiro else texto_do_modelo("ok")


def texto_do_modelo(t):
    return {"content": [{"type": "text", "text": t}], "stop_reason": "end_turn"}


def usa_tool(nome, args=None):
    return {
        "content": [{"type": "tool_use", "id": "t1", "name": nome, "input": args or {}}],
        "stop_reason": "tool_use",
    }


def monta_agente(anthropic=None, tool_executor=None, resultado_da_tool=None,
                 registro_de_ordem=None):
    """Um ConversationAgent pronto para `process_message`.

    `__init__` abre DynamoDB e o cliente HTTP de verdade, então o objeto é
    criado direto e só o que o fluxo toca é preenchido. A sessão vive num dict
    em `agente.sessao_salva`, que os testes leem para conferir handoff.
    """
    agente = object.__new__(ConversationAgent)
    agente.tool_executor = tool_executor or ToolExecutorFalso(resultado_da_tool)
    agente.anthropic = anthropic or AnthropicFalso()
    agente.sessao_salva = {}
    # Devolve a sessão salva, não um dict novo: sem isso nada sobrevive entre
    # turnos e um teste de conversa multi-turno mediria três conversas de um
    # turno. Foi o que escondeu a janela curta de respaldo.
    agente._load_session = lambda c, p: dict(agente.sessao_salva)
    agente._is_attendant_active = lambda s: False
    agente._build_system_prompt = lambda c, p: "PROMPT BASE"
    agente._save_session = lambda c, p, s: agente.sessao_salva.update(s)

    if registro_de_ordem is not None:
        agente.tool_executor.chamadas = registro_de_ordem
        original = agente.anthropic.create_message

        def create_message(system, messages, tools, max_tokens, tool_choice=None):
            registro_de_ordem.append("MODELO")
            return original(system, messages, tools, max_tokens, tool_choice)

        agente.anthropic.create_message = create_message

    return agente


def mensagem(texto):
    return IncomingMessage(
        message_id="m1", phone=PHONE, sender_name="Fulana", timestamp=0,
        message_type="TEXT", content=texto,
    )
