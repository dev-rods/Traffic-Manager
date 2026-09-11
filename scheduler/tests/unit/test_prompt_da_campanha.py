# -*- coding: utf-8 -*-
"""O bloco de campanha entra na conversa certa - e só nela.

O modo é lido da sessão, nunca inferido pelo modelo. Estes testes prendem as
duas metades disso: o bloco aparece quando há campanha viva, e NÃO aparece em
nenhuma outra situação. A segunda metade é a que protege o fluxo de leads.
"""
import time
import unittest
from unittest import mock

from src.services.campanha import abre
from src.services.conversation_agent import ConversationAgent

CLINIC = "clinicaessenciaestetica-9668a4"
FONE = "5511970522647"
DATAS = ["2026-10-07", "2026-10-14", "2026-10-21"]
AGORA = int(time.time())

MARCA = "CONVERSA DE CAMPANHA"


def agente(nome_do_paciente="Maria Silva", erro_no_banco=False):
    a = object.__new__(ConversationAgent)
    a.db = mock.MagicMock()

    def consulta(sql, params=None):
        if erro_no_banco and "FROM scheduler.patients" in sql:
            raise Exception("connection pool exhausted")
        if "FROM scheduler.patients" in sql:
            return [{"name": nome_do_paciente}]
        return []

    a.db.execute_query.side_effect = consulta
    a.template_service = mock.MagicMock()
    a.template_service.get_and_render.return_value = "PROMPT BASE"
    return a


def com_campanha():
    return {"campanha": abre(DATAS, agora=AGORA)}


def campanha_vencida():
    return {"campanha": abre(DATAS, agora=AGORA - 8 * 86400)}


class TestNaoVazaParaOFluxoDeLead(unittest.TestCase):
    """A metade que protege o que já funcionava."""

    def test_sem_sessao_nenhuma(self):
        self.assertNotIn(MARCA, agente()._build_system_prompt(CLINIC, FONE))

    def test_sessao_de_lead_nao_recebe_o_bloco(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, {"bot_enabled": True})
        self.assertNotIn(MARCA, prompt)

    def test_campanha_vencida_nao_recebe_o_bloco(self):
        """No 8º dia a paciente volta a ser conversa comum."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, campanha_vencida())
        self.assertNotIn(MARCA, prompt)

    def test_campanha_corrompida_nao_recebe_o_bloco(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, {"campanha": "sim"})
        self.assertNotIn(MARCA, prompt)

    def test_sem_campanha_o_prompt_e_identico_ao_de_antes(self):
        """Nada de sobra no fluxo de lead - nem uma linha."""
        a = agente()
        self.assertEqual(a._build_system_prompt(CLINIC, FONE),
                         a._build_system_prompt(CLINIC, FONE, {"bot_enabled": True}))


class TestBlocoDaCampanha(unittest.TestCase):
    def test_aparece_com_campanha_viva(self):
        self.assertIn(MARCA, agente()._build_system_prompt(CLINIC, FONE, com_campanha()))

    def test_leva_as_datas_anunciadas(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        for d in DATAS:
            self.assertIn(d, prompt)

    def test_leva_o_nome_do_cadastro(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("Maria Silva", prompt)

    def test_manda_nao_pedir_cadastro(self):
        """A instrução que mais importa: é o erro mais visível deste fluxo."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("CPF", prompt)
        self.assertIn("NUNCA peça", prompt)

    def test_manda_usar_a_tool_das_areas(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("ultimas_areas_do_paciente", prompt)

    def test_mantem_o_desconto_obrigatorio_antes_de_agendar(self):
        """Não anunciar preço não é o mesmo que não calcular: o valor gravado
        no agendamento tem de continuar certo."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("calculate_discount", prompt)

    def test_o_bloco_vem_depois_do_prompt_base(self):
        """No fim de propósito: o prefixo compartilhado mantém o cache válido."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertLess(prompt.index("PROMPT BASE"), prompt.index(MARCA))


class TestFalhaFechada(unittest.TestCase):
    def test_banco_fora_do_ar_nao_derruba_a_conversa(self):
        """Sem o nome o bot só deixa de chamá-la pelo nome."""
        prompt = agente(erro_no_banco=True)._build_system_prompt(
            CLINIC, FONE, com_campanha())

        self.assertIn(MARCA, prompt)

    def test_paciente_sem_nome_no_cadastro(self):
        prompt = agente(nome_do_paciente="")._build_system_prompt(
            CLINIC, FONE, com_campanha())

        self.assertIn(MARCA, prompt)
        self.assertNotIn("Nome dela", prompt)


class TestASessaoChegaAoPrompt(unittest.TestCase):
    """O elo que os testes de unidade não veem.

    `_bloco_da_campanha` pode estar perfeito e o fluxo morrer mudo se o
    `process_message` parar de repassar a sessão. Mutação de 09/09/2026: trocar
    `_build_system_prompt(clinic_id, phone, session)` por `(clinic_id, phone)`
    deixou 670 testes verdes e o fluxo de campanha inteiro morto - o bot
    responderia em modo lead, dando boas-vindas e pedindo CPF a paciente antiga.

    Por isso aqui o alvo é o ARGUMENTO, não o efeito.
    """

    def _sessao_recebida(self, sessao_inicial):
        from tests.unit.dublagem_agente import mensagem, monta_agente

        agente = monta_agente()
        agente.sessao_salva.update(sessao_inicial)

        recebidas = []
        agente._build_system_prompt = lambda c, p, sessao=None: (
            recebidas.append(sessao) or "PROMPT BASE")

        agente.process_message(CLINIC, mensagem("oi"))

        self.assertTrue(recebidas, "_build_system_prompt nem foi chamado")
        return recebidas[0]

    def test_a_campanha_da_sessao_chega_ao_prompt(self):
        recebida = self._sessao_recebida(com_campanha())

        self.assertIsNotNone(
            recebida,
            "process_message não repassou a sessão; o bloco de campanha nunca "
            "entra e o bot atende paciente cadastrada em modo lead")
        self.assertIn("campanha", recebida)

    def test_conversa_de_lead_tambem_repassa_a_sessao(self):
        recebida = self._sessao_recebida({"bot_enabled": True})

        self.assertIsNotNone(recebida)
        self.assertNotIn("campanha", recebida)


class TestRegraDeAreasNoPrompt(unittest.TestCase):
    """A regra vale nos DOIS fluxos - o defeito nao era da campanha.

    Em 11/09/2026 o bot escolheu tres areas sozinho numa conversa de campanha,
    mas nada no codigo impedia o mesmo num lead. A trava das tools garante; o
    prompt e quem diz ao modelo o que fazer quando ela recusa.
    """

    def test_a_regra_esta_no_prompt_do_lead(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, {"bot_enabled": True})
        self.assertIn("AREAS", prompt.replace("Á", "A"))
        self.assertIn("NUNCA escolha por ela", prompt)

    def test_a_regra_esta_no_prompt_da_campanha(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("NUNCA escolha por ela", prompt)

    def test_diz_que_achar_no_historico_nao_dispensa_perguntar(self):
        """Pedido explicito do Andre em 11/09/2026."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("achar", prompt)
        self.assertIn("dispensa perguntar", prompt)

    def test_explica_que_horario_depende_de_area(self):
        """A parte menos obvia: os horarios saem errados junto, porque a
        duracao do slot vem das areas."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, {"bot_enabled": True})
        self.assertIn("depende de", prompt)


if __name__ == "__main__":
    unittest.main()
