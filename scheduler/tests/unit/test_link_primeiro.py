# -*- coding: utf-8 -*-
"""Para quem já é paciente, o link é o primeiro caminho (PRD 046), decidido
antes do modelo (PRD 064).

Essência, 09/11/2026: o disparo mandou o link; ela perguntou "para influencer
também é por esse link?"; o bot respondeu "pode ser por aqui mesmo, quais
áreas?". Nobre, 24/11/2026: paciente com cadastro e sem sessão feita foi
conduzida até "Confirmo?" e só então ouviu "faça pelo site" (a recusa ficava
na tool). Aqui se mede o ambiente que o modelo recebe por caminho, que a tool
não recusa mais ninguém, que o link sai mesmo se o modelo esquecer, e o que
vira conversa: a insistência.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import caminho_de_agendamento as cam
from src.services.ai_tools import ToolExecutor
from src.services.autoatendimento import (
    CAMPO_LINK_ENVIADO,
    CAMPO_PEDIDOS,
    link_citado,
    link_ja_foi,
    marca_link_enviado,
)
from src.services.prompt_da_campanha import adapta
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

LINK = "https://agendar.clinica-teste.com.br/"
COM_SITE = {"clinic_id": CLINIC, "custom_domain": "agendar.clinica-teste.com.br"}
SEM_SITE = {"clinic_id": CLINIC, "custom_domain": None}

PACIENTE = {"encontrado": True, "nome": "Fulana", "cadastro_completo": True,
            "sessoes_feitas": 2, "ultima_sessao": "2026-09-24", "agendamento_futuro": None}
COM_SESSAO = dict(PACIENTE, agendamento_futuro={"id": "ap-1", "data": "2026-11-25", "hora": "16:30"})
# Cadastro feito (site ou painel), nenhuma sessão: estado NEW_LEAD, skill de
# lead. Era quem caía fora do bloco e dentro da recusa (caso 2 do PRD 064).
CADASTRADA_SEM_SESSAO = dict(PACIENTE, sessoes_feitas=0, ultima_sessao=None)
LEAD = {"encontrado": False}

AREAS = {"service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}


# -- Puros -------------------------------------------------------------------

class TestLinkCitado(unittest.TestCase):
    def test_reconhece_pelo_dominio(self):
        self.assertTrue(link_citado("É por aqui: https://agendar.clinica-teste.com.br/agendar 😊", LINK))
        self.assertTrue(link_citado("agendar.clinica-teste.com.br", LINK))
        self.assertFalse(link_citado("Me conta: quais áreas você quer tratar?", LINK))
        self.assertFalse(link_citado("qualquer coisa", None))


class TestLinkJaFoi(unittest.TestCase):
    def test_sem_campo_ou_ilegivel_e_nao(self):
        self.assertFalse(link_ja_foi({}))
        self.assertFalse(link_ja_foi(None))
        self.assertFalse(link_ja_foi({CAMPO_LINK_ENVIADO: "ontem"}))

    def test_dentro_do_prazo_sim_depois_nao(self):
        s = marca_link_enviado({}, agora=1_000_000)
        self.assertTrue(link_ja_foi(s, agora=1_000_000 + 6 * 86400))
        self.assertFalse(link_ja_foi(s, agora=1_000_000 + 8 * 86400))


# -- O agente ----------------------------------------------------------------

def _roda(paciente, clinic, roteiro=None, sessao=None, texto="oi, quero agendar", executor=None):
    vistas = {}
    anthropic = AnthropicRoteiro(roteiro or [texto_do_modelo("Oi!")])
    original = anthropic.create_message

    def create_message(system, messages, tools, max_tokens, tool_choice=None):
        vistas.setdefault("system", system)
        vistas.setdefault("tools", {t["name"] for t in tools})
        return original(system, messages, tools, max_tokens, tool_choice)

    anthropic.create_message = create_message
    agente = monta_agente(anthropic=anthropic, paciente=paciente,
                          tool_executor=executor or ToolExecutorFalso({"ok": True}))
    agente._clinica = lambda c: dict(clinic)
    if sessao:
        agente.sessao_salva.update(sessao)
    saida = agente.process_message(CLINIC, mensagem(texto))
    return agente, saida, vistas


class TestLinkPrimeiroSemModelo(unittest.TestCase):
    def test_paciente_que_pede_agendar_recebe_o_link_sem_chamar_o_modelo(self):
        agente, saida, v = _roda(PACIENTE, COM_SITE)
        self.assertEqual(len(saida), 1)
        self.assertIn(LINK, saida[0].content)
        self.assertIn("Fulana", saida[0].content)
        self.assertNotIn("marco", saida[0].content.lower())
        self.assertEqual(v, {}, "o modelo nao foi chamado")
        self.assertIn(CAMPO_LINK_ENVIADO, agente.sessao_salva)
        self.assertEqual(agente.sessao_salva.get(CAMPO_PEDIDOS), 1)

    def test_cadastrada_sem_sessao_tambem_e_o_caso_2(self):
        """Antes: skill de lead, sem bloco, e recusa na última tool."""
        _, saida, v = _roda(CADASTRADA_SEM_SESSAO, COM_SITE, texto="Podemos marcar dia 3/12 as 15:30?")
        self.assertIn(LINK, saida[0].content)
        self.assertEqual(v, {})

    def test_paciente_com_horario_tambem(self):
        _, saida, _ = _roda(COM_SESSAO, COM_SITE)
        self.assertIn(LINK, saida[0].content)

    def test_duvida_de_paciente_vai_ao_modelo_sem_link(self):
        agente, saida, v = _roda(PACIENTE, COM_SITE, [texto_do_modelo("A axila é R$ 60.")], texto="quanto custa a axila?")
        self.assertNotIn("AGENDAMENTO:", v["system"])
        self.assertNotIn("agendar.clinica-teste", saida[0].content)
        self.assertNotIn(CAMPO_LINK_ENVIADO, agente.sessao_salva)

    def test_lead_nova_nao_recebe_link(self):
        _, _, v = _roda(LEAD, COM_SITE)
        self.assertIn("system", v)
        self.assertNotIn("AGENDAMENTO:", v["system"])

    def test_sem_site_ninguem_recebe(self):
        _, _, v = _roda(PACIENTE, SEM_SITE)
        self.assertIn("system", v)

    def test_segundo_pedido_vai_ao_modelo_com_o_bloco_da_conversa(self):
        _, _, v = _roda(PACIENTE, COM_SITE, sessao={CAMPO_PEDIDOS: 1}, texto="pode ser dia 3 às 15h?")
        self.assertIn("AGENDAMENTO: NA CONVERSA", v["system"])
        self.assertIn("Nunca mande\no link de novo", v["system"])


class TestOLinkSai(unittest.TestCase):
    def test_o_caso_real_o_link_sai_e_as_areas_nao(self):
        """Essência 09/11: pergunta sobre o link + pedido de agendar."""
        agente, saida, _ = _roda(PACIENTE, COM_SITE, texto="Para influencer também é por esse link? quero agendar")
        enviados = " ".join(m.content for m in saida)
        self.assertIn("agendar.clinica-teste", enviados)
        self.assertNotIn("quais áreas", enviados.lower())
        self.assertIn(CAMPO_LINK_ENVIADO, agente.sessao_salva)


class TestInsistenciaAgendaNaConversa(unittest.TestCase):
    def test_depois_do_link_o_bot_agenda_e_nao_manda_link_no_fim(self):
        """Caso 2 do PRD 064 corrigido: pediu de novo, agenda até o fim."""
        chamadas = []

        class Executor(ToolExecutorFalso):
            def execute(self, nome, args, context=None):
                chamadas.append((nome, (context or {}).get("caminho")))
                if nome == "book_appointment":
                    return {"success": True, "appointment_id": "ap-novo"}
                return {"ok": True}

        sessao = marca_link_enviado({CAMPO_PEDIDOS: 1})
        roteiro = [usa_tool("book_appointment", dict(AREAS, date="2026-12-03", time="15:40")),
                   texto_do_modelo("Pronto, está agendado! Te esperamos 😊")]
        agente, saida, v = _roda(PACIENTE, COM_SITE, roteiro, sessao=sessao,
                                 texto="Isso, pode confirmar", executor=Executor())
        self.assertIn(("book_appointment", cam.CONVERSA), chamadas)
        self.assertFalse(any("agendar.clinica-teste" in m.content for m in saida))
        self.assertEqual(agente.sessao_salva.get(CAMPO_PEDIDOS), 0)


# -- A tool não recusa mais --------------------------------------------------

def executor():
    ex = object.__new__(ToolExecutor)
    ex.db = mock.MagicMock()
    ex.db.execute_query.side_effect = lambda sql, params=None: (
        [{"id": "a1", "name": "Axilas"}] if "FROM scheduler.areas" in sql else mock.MagicMock())
    ex.appointment_service = mock.MagicMock()
    ex.appointment_service.create_appointment.return_value = {"id": "ap-novo"}
    ex.availability_engine = mock.MagicMock()
    ex.availability_engine.get_available_days_multi.return_value = ["2026-11-25"]
    ex._troca_por_combos = lambda args, clinic_id: []
    return ex


def ctx(paciente, link=LINK, sessao=None, caminho=cam.CONVERSA):
    return {"paciente": paciente, "link_de_agendamento": link,
            "session": sessao if sessao is not None else {}, "caminho": caminho,
            "turnos": [{"role": "user", "content": "quero fazer axilas"}]}


class TestATollNaoRecusa(unittest.TestCase):
    def test_check_availability_passa_para_paciente_sem_link(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_check_availability(dict(AREAS), CLINIC, PHONE, ctx(PACIENTE))
        self.assertNotIn("error", r)
        ex.availability_engine.get_available_days_multi.assert_called_once()

    def test_em_link_primeiro_a_chamada_e_violacao_registrada_nao_recusa(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10), \
             self.assertLogs("src.services.ai_tools", level="WARNING") as logs:
            r = ex._tool_check_availability(dict(AREAS), CLINIC, PHONE, ctx(PACIENTE, caminho=cam.LINK_PRIMEIRO))
        self.assertNotIn("error", r)
        self.assertTrue(any("VIOLAÇÃO" in l for l in logs.output))

    def test_alterar_agendamento_nao_e_afetada(self):
        ex = executor()
        ex._agendamento_confirmado = lambda a, c: None
        r = ex._tool_alterar_agendamento({"appointment_id": "ap-1", "new_time": "17:00"}, CLINIC, PHONE, ctx(COM_SESSAO))
        self.assertNotEqual(r.get("error"), "primeiro_o_link")


# -- Campanha ----------------------------------------------------------------

_C = chr(0x2550) * 3
PROMPT = f"{_C} COMO CONDUZIR A CONVERSA {_C}\n1. PRIMEIRO CONTATO\n2. DÚVIDA\n3. ÁREAS\n{_C} TOM {_C}\nTom humano.\n"


class TestCampanha(unittest.TestCase):
    def test_com_link_o_roteiro_comeca_pelo_site(self):
        p = adapta(PROMPT, LINK)
        self.assertIn("1. LINK", p)
        self.assertIn(LINK, p)
        self.assertIn("SE ELA NAO CONSEGUIR PELO SITE", p)
        self.assertNotIn("PRIMEIRO CONTATO", p)

    def test_sem_link_o_roteiro_de_sempre(self):
        p = adapta(PROMPT)
        self.assertIn("1. AREAS", p)
        self.assertNotIn("1. LINK", p)

    def _bloco(self, link):
        import time
        from src.services.conversation_agent import ConversationAgent
        agente = object.__new__(ConversationAgent)
        agente.db = mock.MagicMock()
        agente.db.execute_query.return_value = []
        sessao = {"campanha": {"modo": "REAGENDAMENTO", "datas": ["2026-11-25"],
                               "expira_em": int(time.time()) + 3600}}
        return agente._bloco_da_campanha(CLINIC, PHONE, sessao, link)

    def test_no_agente_a_campanha_com_site_comeca_pelo_link(self):
        b = self._bloco(LINK)
        self.assertIn("Comece pelo LINK", b)
        self.assertIn(LINK, b)
        self.assertNotIn("Comece pelas ÁREAS", b)

    def test_no_agente_a_campanha_sem_site_comeca_pelas_areas(self):
        b = self._bloco(None)
        self.assertIn("Comece pelas ÁREAS", b)
        self.assertNotIn("Comece pelo LINK", b)


if __name__ == "__main__":
    unittest.main()
