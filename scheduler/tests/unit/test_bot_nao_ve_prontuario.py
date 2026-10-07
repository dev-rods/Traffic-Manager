# -*- coding: utf-8 -*-
"""O bot não enxerga o prontuário. Nem o tipo de pele.

Pedido explícito do André em 17/09/2026: o tipo de pele é marcado pela
profissional, manualmente, e **não deve de maneira alguma fazer parte do fluxo
automático do bot**.

Isso não se garante com intenção. O agente ganha tools novas com frequência, e
basta alguém expor `patients.*` numa consulta genérica para o campo vazar para
o prompt - e daí para a conversa, que é o pior lugar possível: "vi aqui que sua
pele é negra" numa mensagem de WhatsApp.

Por isso o teste mira a FIAÇÃO, no mesmo espírito de
[test_trava_de_areas_ligada] e [test_superficie_de_tools]: o que ele afirma é
que as tabelas e o campo não aparecem em lugar nenhum do caminho do agente.
"""
import inspect
import unittest

TABELAS_DO_PRONTUARIO = (
    "patient_session_records",
    "patient_session_applications",
    "patient_session_record_audit",
    "laser_protocol_parameters",
    "area_protocol_map",
)

# Módulos que o agente de fato executa. Prontuário não pode aparecer em nenhum.
def _fontes_do_agente():
    import src.services.ai_tools as ai_tools
    import src.services.conversation_agent as agent
    import src.services.conversation_engine as engine
    return {
        "ai_tools": inspect.getsource(ai_tools),
        "conversation_agent": inspect.getsource(agent),
        "conversation_engine": inspect.getsource(engine),
    }


class TestAsTabelasNaoAparecemNoAgente(unittest.TestCase):
    def test_nenhum_modulo_do_bot_cita_as_tabelas(self):
        for modulo, fonte in _fontes_do_agente().items():
            for tabela in TABELAS_DO_PRONTUARIO:
                with self.subTest(modulo=modulo, tabela=tabela):
                    self.assertNotIn(
                        tabela, fonte,
                        f"{modulo} cita {tabela}: o prontuário vazou para o "
                        f"caminho do bot.",
                    )


class TestOTipoDePeleNaoVazaParaAConversa(unittest.TestCase):
    """O campo mais sensível desta feature. Ele descreve a pessoa, e o bot
    conversa com ela."""

    def test_nenhum_modulo_do_bot_cita_skin_type(self):
        for modulo, fonte in _fontes_do_agente().items():
            with self.subTest(modulo=modulo):
                self.assertNotIn("skin_type", fonte)

    def test_nenhuma_tool_do_agente_declara_o_campo(self):
        """A superfície declarada ao modelo, não só o código."""
        import json

        from src.services.ai_tools import TOOL_DEFINITIONS, get_tool_definitions

        # As duas formas: a constante e o que de fato e entregue ao modelo.
        declarado = json.dumps(
            [TOOL_DEFINITIONS, get_tool_definitions()], ensure_ascii=False
        ).lower()
        for proibido in ("skin_type", "skintype", "tipo de pele",
                         "fluencia", "fluência", "prontuario", "prontuário"):
            with self.subTest(termo=proibido):
                self.assertNotIn(proibido, declarado)

    def test_o_executor_nao_tem_handler_de_prontuario(self):
        """Tool só existe se houver `_tool_<nome>`. Nenhum pode ser disto."""
        from src.services.ai_tools import ToolExecutor

        suspeitos = [
            nome for nome in dir(ToolExecutor)
            if nome.startswith("_tool_")
            and any(t in nome for t in ("record", "session_record", "protocol",
                                        "skin", "prontuario"))
        ]
        self.assertEqual(suspeitos, [])


class TestOProntuarioNaoImportaOBot(unittest.TestCase):
    """A outra direção. Se o prontuário passar a importar o agente, abre-se um
    caminho de volta que ninguém está olhando."""

    def test_os_modulos_do_prontuario_sao_independentes(self):
        import src.services.historico_de_sessao as historico
        import src.services.protocolo_laser as protocolo

        for modulo in (historico, protocolo):
            fonte = inspect.getsource(modulo)
            for proibido in ("ai_tools", "conversation_agent", "anthropic",
                             "openai_service"):
                with self.subTest(modulo=modulo.__name__, termo=proibido):
                    self.assertNotIn(proibido, fonte)


if __name__ == "__main__":
    unittest.main()
