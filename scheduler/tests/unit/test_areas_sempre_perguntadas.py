# -*- coding: utf-8 -*-
"""As areas sao SEMPRE perguntadas - nunca deduzidas do atendimento anterior.

Decisao do Andre em 11/09/2026, revertendo o que ele mesmo pediu dois dias
antes. A ideia original era boa no papel: propor as areas da ultima sessao e
pedir confirmacao, que e o que a atendente faz a mao. O piloto mostrou o
problema - propor e um convite a induzir, e o bot ja tinha demonstrado que
induz. "O que ela fez da ultima vez" nao responde "o que ela quer agora".

A tool foi REMOVIDA, nao desencorajada. Enquanto a capacidade existir alguem a
usa: foi assim com o prompt que mandava confirmar as areas e nao segurou nada.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import TOOL_DEFINITIONS, ToolExecutor


class TestATooolNaoExisteMais(unittest.TestCase):
    def test_nao_esta_exposta_ao_modelo(self):
        nomes = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        self.assertNotIn("ultimas_areas_do_paciente", nomes)

    def test_nao_ha_executor_escondido(self):
        """Schema removido com executor vivo deixaria a porta destrancada para
        quem reexpuser a tool sem pensar."""
        self.assertFalse(hasattr(ToolExecutor, "_tool_ultimas_areas_do_paciente"))

    def test_nenhuma_tool_promete_historico_de_areas(self):
        """Guarda contra a ideia voltar com outro nome."""
        for t in TOOL_DEFINITIONS:
            f = t["function"]
            with self.subTest(tool=f["name"]):
                texto = (f["name"] + " " + f["description"]).lower()
                suspeito = ("area" in texto or "área" in texto)
                historico = any(p in texto for p in ("ultima sess", "last session",
                                                     "previous appointment",
                                                     "ultimo agendamento"))
                self.assertFalse(
                    suspeito and historico,
                    f"{f['name']} promete areas de atendimento anterior; "
                    f"as areas sao sempre perguntadas")


if __name__ == "__main__":
    unittest.main()
