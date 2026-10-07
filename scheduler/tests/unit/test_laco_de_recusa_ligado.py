# -*- coding: utf-8 -*-
"""O quebra-laço está LIGADO no agente, não só implementado.

Como em [test_trava_de_areas_ligada], o alvo aqui é a FIAÇÃO. A função pode
estar perfeita e o laço continuar: basta ninguém chamá-la, ou o contador não
sobreviver ao turno - e foi assim que a conversa de 16/09/2026 atravessou cinco
mensagens sem nada acusar.

Duas coisas precisam ser verdade juntas, e cada uma sozinha é inútil:
  1. a segunda recusa igual derruba a conversa para uma pessoa
  2. o contador sobrevive entre mensagens, porque o laço é feito de mensagens
"""
import unittest

from tests.unit.dublagem_agente import (
    CLINIC,
    PHONE,
    AnthropicRoteiro,
    ToolExecutorFalso,
    mensagem,
    monta_agente,
    texto_do_modelo,
    usa_tool,
)

# A recusa real que saiu no log daquela conversa, seis vezes.
RECUSA = {
    "error": "areas_nao_confirmadas",
    "areas_barradas": ["Virilha Comp. + ânus"],
    "o_que_fazer": "Pergunte a ela quais áreas quer tratar...",
}

# "Isso mesmo" é social: não dispara pré-carga, então as únicas chamadas de tool
# no teste são as que o roteiro manda. Foi a resposta real da paciente.
RESPOSTA_DELA = "Isso mesmo"


def turno(agente, roteiro):
    agente.anthropic = AnthropicRoteiro(roteiro)
    return agente.process_message(CLINIC, mensagem(RESPOSTA_DELA))


class TestOLacoQuebra(unittest.TestCase):
    def setUp(self):
        self.executor = ToolExecutorFalso(resultado=RECUSA)
        self.agente = monta_agente(tool_executor=self.executor)

    def test_a_primeira_recusa_deixa_a_conversa_seguir(self):
        """A trava trabalhando não pode virar handoff: a maioria das recusas é
        legítima e a pergunta que ela gera resolve."""
        saida = turno(self.agente, [
            usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
            texto_do_modelo("Na virilha, você quer incluir o ânus?"),
        ])

        self.assertNotEqual(self.agente.sessao_salva.get("state"), "HUMAN_HANDOFF")
        self.assertIn("ânus", saida[0].content)

    def test_a_segunda_recusa_igual_entrega_a_uma_pessoa(self):
        turno(self.agente, [
            usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
            texto_do_modelo("Na virilha, você quer incluir o ânus?"),
        ])

        saida = turno(self.agente, [
            usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
            texto_do_modelo("Confirma que vamos tratar Virilha Completa + Ânus?"),
        ])

        self.assertEqual(self.agente.sessao_salva["state"], "HUMAN_HANDOFF")
        self.assertEqual(len(saida), 1)
        self.assertIn("especialista", saida[0].content)

    def test_e_nao_pergunta_a_mesma_coisa_de_novo(self):
        """O dano da conversa real não foi o handoff, foi o que veio antes dele:
        a mesma pergunta, cinco vezes, a uma paciente que já tinha respondido."""
        turno(self.agente, [
            usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
            texto_do_modelo("Na virilha, você quer incluir o ânus?"),
        ])

        saida = turno(self.agente, [
            usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
            texto_do_modelo("Na virilha, você quer incluir o ânus?"),
        ])

        self.assertNotIn("incluir o ânus", saida[0].content)

    def test_sem_botoes_para_a_paciente_escolher(self):
        """Encurralado, o modelo alcança present_options e a paciente volta a
        clicar em botão. A resposta do handoff não leva botão nenhum."""
        turno(self.agente, [
            usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
            texto_do_modelo("..."),
        ])

        saida = turno(self.agente, [
            usa_tool("present_options", {
                "message": "Confirma essa área?",
                "options": [{"id": "sim", "label": "Sim, confirmo"}],
            }),
            usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
            texto_do_modelo("..."),
        ])

        self.assertEqual(saida[0].message_type, "text")
        self.assertIsNone(saida[0].buttons)


class TestOContadorAtravessaOTurno(unittest.TestCase):
    def test_a_sessao_carrega_a_contagem_adiante(self):
        """Sem isto cada mensagem começaria do zero e o laço nunca fecharia -
        que é exatamente como ele sobreviveu a cinco mensagens em 16/09."""
        agente = monta_agente(tool_executor=ToolExecutorFalso(resultado=RECUSA))

        turno(agente, [
            usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
            texto_do_modelo("..."),
        ])

        self.assertEqual(
            list(agente.sessao_salva["recusas_de_area"].values()), [1]
        )


class TestConversaSadiaNaoEEntregue(unittest.TestCase):
    def test_tool_que_responde_bem_nunca_fecha_laco(self):
        """O quebra-laço só conta recusa de ÁREA. Se contasse qualquer erro,
        uma chamada malformada do modelo entregaria conversa sadia."""
        agente = monta_agente(
            tool_executor=ToolExecutorFalso(resultado={"discount_pct": 10})
        )

        for _ in range(4):
            turno(agente, [
                usa_tool("calculate_discount", {"service_area_pairs": [{"area_id": "v"}]}),
                texto_do_modelo("Fica R$ 463,50 😊"),
            ])

        self.assertNotEqual(agente.sessao_salva.get("state"), "HUMAN_HANDOFF")


if __name__ == "__main__":
    unittest.main()
