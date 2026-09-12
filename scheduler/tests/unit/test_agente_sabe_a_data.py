# -*- coding: utf-8 -*-
"""O agente recebe o calendário, e a data resolvida não cai no bloqueio.

O fix tem duas metades e as duas falham em silêncio se soltas:

  - se o bloco CALENDÁRIO não chegar ao modelo, ele volta a dizer que não sabe
    calcular "amanhã", sem erro nenhum;
  - se as datas do calendário não entrarem no respaldo, dizer "amanhã (05/09)
    não temos vaga" vira data sem origem e a resposta é BLOQUEADA - trocaríamos
    uma falha visível por uma pior.
"""
import os
import unittest
from datetime import date
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.conversation_agent import ConversationAgent
from tests.unit.dublagem_agente import (
    CLINIC,
    AnthropicFalso,
    AnthropicRoteiro,
    mensagem,
    monta_agente,
    texto_do_modelo,
    usa_tool,
)

SEXTA = date(2026, 9, 4)


def com_data_fixa():
    return mock.patch("src.services.calendario.hoje_brt", return_value=SEXTA)


def conversa(texto, resposta="Certo!"):
    modelo = AnthropicFalso(resposta)
    agente = monta_agente(anthropic=modelo)
    with com_data_fixa():
        saida = agente.process_message(CLINIC, mensagem(texto))
    return modelo, agente, saida


def turno_enviado(modelo):
    """O conteúdo do último turno da pessoa, como o modelo o viu."""
    return modelo.conversas[0][-1]["content"]


class TestOCalendarioChegaAoModelo(unittest.TestCase):
    def test_a_data_de_hoje_vai_em_toda_mensagem(self):
        modelo, _, _ = conversa("quanto custa?")

        self.assertIn("HOJE é sexta-feira, 04/09/2026", turno_enviado(modelo))

    def test_a_referencia_da_pessoa_vem_traduzida(self):
        modelo, _, _ = conversa("gostaria de agendar para amanhã")

        enviado = turno_enviado(modelo)
        self.assertIn('"amanhã" = sábado, 05/09/2026', enviado)
        self.assertIn("gostaria de agendar para amanhã", enviado)

    def test_o_calendario_nao_se_confunde_com_a_agenda(self):
        """Saber que dia é não é saber que há vaga - e o modelo precisa ler
        isso, senão o calendário vira fonte de disponibilidade."""
        modelo, _, _ = conversa("tem amanhã?")

        self.assertIn("não a agenda", turno_enviado(modelo))

    def test_a_regra_de_data_esta_no_prompt(self):
        agente = object.__new__(ConversationAgent)
        agente.db = mock.MagicMock()
        agente.db.execute_query.return_value = []
        agente.template_service = mock.MagicMock()
        agente.template_service.get_and_render.return_value = "BASE"

        prompt = agente._build_system_prompt(CLINIC, "5511999990000")

        self.assertIn("CALENDÁRIO", prompt)
        self.assertIn("Nunca diga que não consegue calcular uma data", prompt)


class TestDataResolvidaNaoEBloqueada(unittest.TestCase):
    """A metade que protege contra o próprio guardrail."""

    def test_citar_a_data_de_amanha_passa_na_proveniencia(self):
        resposta = "Amanhã (05/09) não temos horário."
        modelo, agente, saida = conversa("tem amanhã?", resposta)

        self.assertIn("05/09", saida[0].content)
        self.assertEqual(modelo.correcoes, [], "a resposta foi mandada refazer")

    def test_data_que_o_calendario_nao_resolveu_continua_bloqueada(self):
        """O guardrail segue de pé para o que o modelo inventar sozinho."""
        _, _, saida = conversa("tem amanhã?", "Consegui encaixar dia 30/11 às 14:00.")

        self.assertNotIn("30/11", saida[0].content)

    def test_hoje_entra_no_respaldo_mesmo_sem_referencia(self):
        _, agente, _ = conversa("quanto custa?", "Hoje, 04/09, atendemos até 20h.")

        salvo = agente.sessao_salva.get("respaldo_anterior") or []
        datas = [d for item in salvo for d in (item.get("calendario") or [])]
        self.assertIn("2026-09-04", datas)


class TestGatilhoNaoGanhaCalendario(unittest.TestCase):
    def test_mensagem_sintetica_nao_produz_bloco(self):
        """Gatilho não é fala de ninguém: não há referência a resolver."""
        modelo = AnthropicFalso("Oi!")
        agente = monta_agente(anthropic=modelo)
        with com_data_fixa():
            agente.process_message(CLINIC, mensagem("__INICIAR_CONVERSA__"))

        self.assertNotIn("CALENDÁRIO", str(turno_enviado(modelo)))


class TestRespostaNaoSomeAtrasDasOpcoes(unittest.TestCase):
    """`display_text = text or button_message` engolia a resposta.

    O modelo escreve em dois lugares quando oferece opções: a mensagem que
    acompanha a lista e o texto final. Só o segundo era entregue, e é o que
    costuma ser enfeite ("alguma dessas serve?"). A resposta - "amanhã não
    temos horário" - vinha no primeiro e sumia.
    """

    def _junta(self, opcoes, final):
        return ConversationAgent._junta_texto(opcoes, final)

    def test_as_duas_falas_diferentes_sao_entregues(self):
        junto = self._junta("Amanhã (05/09) não temos horário.",
                            "Alguma dessas fica boa?")

        self.assertIn("05/09", junto)
        self.assertIn("Alguma dessas fica boa?", junto)

    def test_frase_repetida_nao_vai_duas_vezes(self):
        """O caso comum: o modelo repete a mesma frase nos dois lugares."""
        self.assertEqual(self._junta("Escolha uma data:", "Escolha uma data:"),
                         "Escolha uma data:")

    def test_texto_que_contem_o_outro_nao_duplica(self):
        junto = self._junta("Escolha uma data:",
                            "Escolha uma data: temos vagas em setembro.")

        self.assertEqual(junto.count("Escolha uma data:"), 1)

    def test_so_uma_das_falas(self):
        self.assertEqual(self._junta("", "só o final"), "só o final")
        self.assertEqual(self._junta("só as opções", ""), "só as opções")
        self.assertEqual(self._junta("", ""), "")

    def test_no_fluxo_completo_a_resposta_chega(self):
        """O caminho de verdade: o modelo chama present_options e depois fala."""
        modelo = AnthropicRoteiro([
            usa_tool("present_options"),
            texto_do_modelo("Alguma dessas fica boa?"),
        ])
        agente = monta_agente(
            anthropic=modelo,
            resultado_da_tool={"presented": True,
                               "message": "Amanhã (05/09) não temos horário.",
                               "options": [{"id": "2026-09-23", "label": "Qua, 23/09"}]},
        )
        with com_data_fixa():
            saida = agente.process_message(CLINIC, mensagem("tem amanhã?"))

        entregue = saida[0].content
        self.assertIn("05/09", entregue)
        self.assertIn("Alguma dessas fica boa?", entregue)


if __name__ == "__main__":
    unittest.main()
