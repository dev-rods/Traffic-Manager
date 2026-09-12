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

# O template real traz um roteiro numerado com TEXTO PRONTO. Era dele que saia,
# palavra por palavra, o pedido de CPF que a Camila recebeu em 11/09/2026.
_C = chr(0x2550) * 3
PROMPT_BASE = (
    "PROMPT BASE\n"
    f"{_C} COMO CONDUZIR A CONVERSA {_C}\n"
    "1. PRIMEIRO CONTATO\n"
    "   Confirme as areas, chame calculate_discount e mostre o valor.\n"
    "6. CADASTRO\n"
    "   \"Perfeito! Para finalizar o cadastro, me envia:\n"
    "   Nome completo:\nCPF:\"\n"
    f"{_C} AO FECHAR O AGENDAMENTO {_C}\n"
    "Rua Augusta, 2709.\n"
)


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
    a.template_service.get_and_render.return_value = PROMPT_BASE
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
        """Reforço, NÃO a defesa - e este teste existe para deixar isso claro.

        Em 11/09/2026 esta instrução estava no prompt e o bot pediu CPF a uma
        paciente cadastrada mesmo assim, reproduzindo o roteiro base. Quem
        garante é o roteiro sair do prompt (test_o_roteiro_de_lead_sai_do_prompt)
        e a trava de saída (test_trava_de_cadastro_ligada).

        O teste fica porque a instrução ainda ajuda e ninguém deve removê-la
        sem perceber - mas quem ler não pode achar que ela é o que segura.
        """
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("CPF", prompt)
        self.assertIn("NUNCA peça", prompt)

    def test_manda_perguntar_as_areas_desta_vez(self):
        """Decisao do Andre em 11/09/2026: nunca deduzir do atendimento anterior.

        Ele chegou a pedir o contrario dois dias antes - propor as da ultima
        sessao e confirmar. O piloto mostrou que propor e um convite a induzir,
        entao a pergunta passou a ser sempre aberta.
        """
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("DESTA VEZ", prompt)
        self.assertNotIn("ultimas_areas_do_paciente", prompt)

    def test_mantem_o_desconto_obrigatorio_antes_de_agendar(self):
        """Não anunciar preço não é o mesmo que não calcular: o valor gravado
        no agendamento tem de continuar certo."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("calculate_discount", prompt)

    def test_o_roteiro_de_lead_sai_do_prompt(self):
        """O nucleo da correcao de 11/09/2026.

        Nao basta o bloco de campanha PROIBIR o pedido de cadastro - ele ja
        proibia, e o bot pediu assim mesmo, reproduzindo o texto pronto do
        roteiro base. O que nao esta no prompt nao pode ser reproduzido.
        """
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())

        self.assertNotIn("Para finalizar o cadastro", prompt)
        self.assertNotIn("Nome completo", prompt)
        self.assertNotIn("mostre o valor", prompt)
        self.assertIn("COMO CONDUZIR A CONVERSA (CAMPANHA)", prompt)

    def test_o_que_vale_nos_dois_fluxos_continua(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("Rua Augusta", prompt)

    def test_o_roteiro_de_lead_FICA_na_conversa_de_lead(self):
        """A outra metade: quem e lead precisa do roteiro completo."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, {"bot_enabled": True})

        self.assertIn("Para finalizar o cadastro", prompt)
        self.assertIn("mostre o valor", prompt)
        self.assertNotIn("(CAMPANHA)", prompt)

    def test_campanha_vencida_mantem_o_roteiro_de_lead(self):
        prompt = agente()._build_system_prompt(CLINIC, FONE, campanha_vencida())
        self.assertIn("Para finalizar o cadastro", prompt)

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

    def test_diz_que_nao_ha_consulta_ao_historico_de_areas(self):
        """A tool foi REMOVIDA, nao so desencorajada: enquanto a capacidade
        existir, o modelo a usa."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, com_campanha())
        self.assertIn("NÃO consulta o histórico", prompt)

    def test_explica_que_horario_depende_de_area(self):
        """A parte menos obvia: os horarios saem errados junto, porque a
        duracao do slot vem das areas."""
        prompt = agente()._build_system_prompt(CLINIC, FONE, {"bot_enabled": True})
        self.assertIn("depende de", prompt)


if __name__ == "__main__":
    unittest.main()
