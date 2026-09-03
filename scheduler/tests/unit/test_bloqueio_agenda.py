"""Data e horário sem respaldo não saem para a paciente.

Em 02/09/2026, à pergunta "E horários à tarde?", o agente listou dez horários
com `tools=0`: extrapolou da lista da noite que ele mesmo dera minutos antes. O
verificador viu e apenas registrou, porque estava em modo observação.

Agora derruba a mensagem. Só data e horário: são os fatos em torno dos quais a
pessoa organiza o dia. Preço ou duração errados constrangem; um horário
inventado faz alguém atravessar a cidade à toa.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.providers.whatsapp_provider import IncomingMessage
from src.services.conversation_agent import ConversationAgent
from src.services.proveniencia import fatos_de_agenda

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"


class TestFatosDeAgenda(unittest.TestCase):
    def test_data_e_horario_bloqueiam(self):
        self.assertEqual(
            fatos_de_agenda({"2026-09-23", "18:00"}), {"2026-09-23", "18:00"}
        )

    def test_preco_duracao_e_status_nao_bloqueiam(self):
        self.assertEqual(
            fatos_de_agenda({"R$250.00", "duracao:35", "status:cancelado"}), set()
        )

    def test_mistura_devolve_so_o_que_bloqueia(self):
        self.assertEqual(
            fatos_de_agenda({"18:00", "R$50.00", "duracao:35"}), {"18:00"}
        )

    def test_vazio_e_none(self):
        self.assertEqual(fatos_de_agenda(set()), set())
        self.assertEqual(fatos_de_agenda(None), set())


class ToolExecutorFalso:
    def __init__(self, resultado=None):
        self.chamadas = []
        self._resultado = resultado if resultado is not None else {"ok": True}

    def execute(self, nome, args, context=None):
        self.chamadas.append(nome)
        return self._resultado


class AnthropicFalso:
    def __init__(self, texto):
        self._texto = texto
        self.chamadas = 0
        self.forcados = []

    def create_message(self, system, messages, tools, max_tokens, tool_choice=None):
        self.chamadas += 1
        self.forcados.append(tool_choice)
        return {"content": [{"type": "text", "text": self._texto}], "stop_reason": "end_turn"}


def monta_agente(texto_do_modelo, resultado_da_tool=None):
    agente = object.__new__(ConversationAgent)
    agente.tool_executor = ToolExecutorFalso(resultado_da_tool)
    agente.anthropic = AnthropicFalso(texto_do_modelo)
    agente.sessao_salva = {}
    agente._load_session = lambda c, p: {}
    agente._is_attendant_active = lambda s: False
    agente._build_system_prompt = lambda c, p: "PROMPT"
    agente._save_session = lambda c, p, s: agente.sessao_salva.update(s)
    return agente


def mensagem(texto):
    return IncomingMessage(
        message_id="m1", phone=PHONE, sender_name="Fulana", timestamp=0,
        message_type="TEXT", content=texto,
    )


class TestBloqueio(unittest.TestCase):
    INVENTADA = "Para 23/09, tenho 13:00, 13:30 e 14:00. Qual fica melhor?"

    def test_horario_inventado_nao_chega_na_paciente(self):
        agente = monta_agente(self.INVENTADA)

        saida = agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        texto = " ".join(m.content for m in saida)
        self.assertNotIn("13:00", texto)
        self.assertNotIn("13:30", texto)

    def test_bloqueio_transfere_para_especialista(self):
        """Não adianta insistir: ele inventou com o prompt inteiro mandando consultar."""
        agente = monta_agente(self.INVENTADA)

        agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")
        self.assertTrue(agente.sessao_salva.get("attendant_active_until"))

    def test_a_pessoa_recebe_uma_resposta_e_nao_silencio(self):
        agente = monta_agente(self.INVENTADA)

        saida = agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertTrue(saida)
        self.assertTrue(saida[0].content.strip())


class TestNaoBloqueiaDemais(unittest.TestCase):
    def test_horario_vindo_da_tool_passa(self):
        """O caso comum: os horários que a tool devolveu, listados como estão."""
        agente = monta_agente(
            "Tenho 18:00 e 18:15 nesse dia.",
            resultado_da_tool={"available_slots": ["18:00", "18:15"]},
        )

        saida = agente.process_message(CLINIC, mensagem("quais horarios tem?"))

        self.assertIn("18:00", " ".join(m.content for m in saida))
        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")

    def test_conversa_sem_data_nem_horario_passa(self):
        agente = monta_agente("Claro! O laser é praticamente indolor 😊")

        saida = agente.process_message(CLINIC, mensagem("dói muito?"))

        self.assertIn("indolor", " ".join(m.content for m in saida))
        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")

    def test_preco_sem_respaldo_registra_mas_nao_bloqueia(self):
        """Preço errado constrange; não faz ninguém perder a tarde."""
        agente = monta_agente("Fica R$ 250,00 no total.")

        saida = agente.process_message(CLINIC, mensagem("quanto custa?"))

        self.assertIn("250", " ".join(m.content for m in saida))
        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")


class AnthropicRoteirizado:
    """Responde uma coisa diferente a cada chamada, na ordem do roteiro."""

    def __init__(self, roteiro):
        self._roteiro = list(roteiro)
        self.forcados = []
        self.correcoes = []

    def create_message(self, system, messages, tools, max_tokens, tool_choice=None):
        self.forcados.append(tool_choice)
        ultima = messages[-1].get("content") if messages else ""
        if isinstance(ultima, str) and ultima.startswith("PARE."):
            self.correcoes.append(ultima)
        return self._roteiro.pop(0) if self._roteiro else {
            "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
        }


def texto(t):
    return {"content": [{"type": "text", "text": t}], "stop_reason": "end_turn"}


def usa_tool(nome, args):
    return {
        "content": [{"type": "tool_use", "id": "t1", "name": nome, "input": args}],
        "stop_reason": "tool_use",
    }


class TestConsultaObrigatoria(unittest.TestCase):
    """Pergunta sobre agenda não sai sem consulta: o modelo escolhe QUAL tool,
    não escolhe SE consulta. Deixar isso com ele produziu tools=0 duas vezes."""

    def test_intencao_de_agenda_forca_tool_na_primeira_rodada(self):
        anthropic = AnthropicRoteirizado([texto("Claro!")])
        agente = monta_agente("ignorado")
        agente.anthropic = anthropic

        agente.process_message(CLINIC, mensagem("quais horarios tem?"))

        self.assertEqual(anthropic.forcados[0], {"type": "any"})

    def test_conversa_comum_nao_forca_nada(self):
        """Forçar sempre gastaria uma tool em "oi, tudo bem?"."""
        anthropic = AnthropicRoteirizado([texto("Oi! Tudo ótimo 😊")])
        agente = monta_agente("ignorado")
        agente.anthropic = anthropic

        agente.process_message(CLINIC, mensagem("oi, tudo bem?"))

        self.assertIsNone(anthropic.forcados[0])


class TestSeCorrigeAntesDeTransferir(unittest.TestCase):
    """Inventar uma vez não pode custar a conversa.

    A primeira versão transferia direto, e transformava um erro recuperável em
    trabalho manual para a clínica.
    """

    def test_inventou_e_depois_consultou_responde_normalmente(self):
        anthropic = AnthropicRoteirizado([
            texto("Para 23/09 tenho 13:00 e 13:30."),          # inventou
            usa_tool("get_time_slots", {"date": "2026-09-23"}),  # foi mandado consultar
            texto("Nesse dia tenho 18:00 e 18:15."),            # respondeu com o que voltou
        ])
        agente = monta_agente("ignorado", resultado_da_tool={"available_slots": ["18:00", "18:15"]})
        agente.anthropic = anthropic

        saida = agente.process_message(CLINIC, mensagem("e horários à tarde?"))
        enviado = " ".join(m.content for m in saida)

        self.assertIn("18:00", enviado)
        self.assertNotIn("13:00", enviado)
        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")

    def test_a_correcao_e_explicita_para_o_modelo(self):
        anthropic = AnthropicRoteirizado([
            texto("Para 23/09 tenho 13:00."),
            texto("Nesse dia tenho 18:00."),
        ])
        agente = monta_agente("ignorado", resultado_da_tool={"available_slots": ["18:00"]})
        agente.anthropic = anthropic

        agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertTrue(anthropic.correcoes)
        self.assertIn("Chame agora a tool", anthropic.correcoes[0])

    def test_insistiu_em_inventar_ai_sim_transfere(self):
        anthropic = AnthropicRoteirizado([
            texto("Para 23/09 tenho 13:00."),
            texto("Para 23/09 tenho 13:00 mesmo."),
        ])
        agente = monta_agente("ignorado")
        agente.anthropic = anthropic

        saida = agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")
        self.assertNotIn("13:00", " ".join(m.content for m in saida))

    def test_refaz_no_maximo_uma_vez(self):
        """Sem teto, uma conversa ruim viraria cinco chamadas de modelo."""
        anthropic = AnthropicRoteirizado([
            texto("Para 23/09 tenho 13:00."),
            texto("Para 23/09 tenho 13:00."),
            texto("Para 23/09 tenho 13:00."),
        ])
        agente = monta_agente("ignorado")
        agente.anthropic = anthropic

        agente.process_message(CLINIC, mensagem("e horários à tarde?"))

        self.assertEqual(len(anthropic.forcados), 2)


if __name__ == "__main__":
    unittest.main()
