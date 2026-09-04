"""Efeito colateral já cometido não pode ser escondido da paciente.

O bloqueio de proveniência troca a mensagem por "vou confirmar com uma
especialista". Se `book_appointment` já rodou, a sessão existe no banco e a
mensagem estaria mentindo por omissão: a pessoa fica com um horário marcado que
não sabe que tem.

"Efeito só no fim" é o desenho certo. Enquanto o efeito acontece no meio do
loop, a mensagem tem que contá-lo.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.providers.whatsapp_provider import IncomingMessage
from src.services.conversation_agent import TOOLS_COM_EFEITO, ConversationAgent

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"


class ToolExecutorFalso:
    def __init__(self, resultado=None):
        self.chamadas = []
        self._resultado = resultado if resultado is not None else {"ok": True}

    def execute(self, nome, args, context=None):
        self.chamadas.append(nome)
        return self._resultado


class AnthropicRoteirizado:
    def __init__(self, roteiro):
        self._roteiro = list(roteiro)
        self.chamadas = 0

    def create_message(self, system, messages, tools, max_tokens, tool_choice=None):
        self.chamadas += 1
        return self._roteiro.pop(0) if self._roteiro else {
            "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
        }


def texto(t):
    return {"content": [{"type": "text", "text": t}], "stop_reason": "end_turn"}


def usa_tool(nome, args=None):
    return {
        "content": [{"type": "tool_use", "id": "t1", "name": nome, "input": args or {}}],
        "stop_reason": "tool_use",
    }


def monta_agente(anthropic, resultado_da_tool=None):
    agente = object.__new__(ConversationAgent)
    agente.tool_executor = ToolExecutorFalso(resultado_da_tool)
    agente.anthropic = anthropic
    agente.sessao_salva = {}
    agente._load_session = lambda c, p: {}
    agente._is_attendant_active = lambda s: False
    agente._build_system_prompt = lambda c, p: "PROMPT"
    agente._save_session = lambda c, p, s: agente.sessao_salva.update(s)
    return agente


def mensagem(t):
    return IncomingMessage(
        message_id="m1", phone=PHONE, sender_name="Fulana", timestamp=0,
        message_type="TEXT", content=t,
    )


class TestQuaisToolsMudamOMundo(unittest.TestCase):
    def test_as_tres_de_agendamento(self):
        self.assertEqual(
            TOOLS_COM_EFEITO,
            frozenset({"book_appointment", "reschedule_appointment", "cancel_appointment"}),
        )

    def test_consulta_nao_e_efeito(self):
        for nome in ["get_time_slots", "list_areas", "calculate_duration",
                     "calculate_discount", "get_faq_answer"]:
            with self.subTest(tool=nome):
                self.assertNotIn(nome, TOOLS_COM_EFEITO)


class TestBloqueioDepoisDoEfeito(unittest.TestCase):
    """O agendamento aconteceu e a resposta final tem horário sem respaldo."""

    ROTEIRO = [
        usa_tool("book_appointment", {"date": "2026-09-23"}),
        texto("Pronto! Sua sessão é 23/09 às 09:15."),  # 09:15 nao veio de tool
    ]
    RESULTADO = {"success": True, "appointment_id": "abc", "date": "2026-09-23",
                 "time": "07:45", "status": "CONFIRMED"}

    def test_horario_inventado_nao_sai(self):
        agente = monta_agente(AnthropicRoteirizado(self.ROTEIRO), self.RESULTADO)

        saida = agente.process_message(CLINIC, mensagem("confirma pra mim"))

        self.assertNotIn("09:15", " ".join(m.content for m in saida))

    def test_mensagem_avisa_que_algo_foi_registrado(self):
        """Nunca "vou confirmar" puro: isso esconderia o agendamento criado."""
        agente = monta_agente(AnthropicRoteirizado(self.ROTEIRO), self.RESULTADO)

        saida = agente.process_message(CLINIC, mensagem("confirma pra mim"))
        enviado = " ".join(m.content for m in saida).lower()

        self.assertIn("registrei", enviado)

    def test_transfere_para_especialista(self):
        agente = monta_agente(AnthropicRoteirizado(self.ROTEIRO), self.RESULTADO)

        agente.process_message(CLINIC, mensagem("confirma pra mim"))

        self.assertEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")

    def test_nao_refaz_depois_do_efeito(self):
        """Refazer convidaria o modelo a chamar book_appointment de novo."""
        anthropic = AnthropicRoteirizado(self.ROTEIRO)
        agente = monta_agente(anthropic, self.RESULTADO)

        agente.process_message(CLINIC, mensagem("confirma pra mim"))

        # Uma chamada para a tool, outra para o texto. Sem terceira.
        self.assertEqual(anthropic.chamadas, 2)


class TestSemEfeitoSegueComoAntes(unittest.TestCase):
    def test_sem_efeito_a_mensagem_e_a_de_confirmar_horarios(self):
        """Sem efeito ele ganha a segunda chance; insistindo, cai no bloqueio."""
        agente = monta_agente(AnthropicRoteirizado([
            texto("Tenho 13:00 e 13:30."),
            texto("Tenho 13:00 e 13:30 mesmo."),
        ]))

        saida = agente.process_message(CLINIC, mensagem("e de tarde?"))
        enviado = " ".join(m.content for m in saida).lower()

        self.assertIn("confirmar os horários", enviado)
        self.assertNotIn("registrei", enviado)


if __name__ == "__main__":
    unittest.main()
