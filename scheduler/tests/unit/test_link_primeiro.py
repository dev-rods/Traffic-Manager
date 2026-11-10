# -*- coding: utf-8 -*-
"""Para quem já é paciente, o link é o primeiro caminho (PRD 046).

Essência, 09/11/2026: o disparo mandou o link; ela perguntou "para influencer
também é por esse link?"; o bot respondeu "pode ser por aqui mesmo, quais
áreas?". A clínica escolheu o site e o bot puxou para a conversa. Aqui se mede
o ambiente que o modelo recebe, a recusa que segura a tool, e o que libera a
segunda tentativa: o BOT ter mandado o link.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import skills
from src.services.ai_tools import ToolExecutor
from src.services.autoatendimento import (
    CAMPO_LINK_ENVIADO,
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


# -- O bloco no prompt -------------------------------------------------------

class TestBlocoDoSite(unittest.TestCase):
    def test_sem_link_nao_ha_bloco(self):
        self.assertEqual(skills.bloco_do_site(None), "")
        self.assertEqual(skills.bloco_do_site(""), "")

    def test_com_link_manda_o_link_e_segura_a_consulta(self):
        b = skills.bloco_do_site(LINK)
        self.assertIn(LINK, b)
        self.assertIn("NÃO chame check_availability", b)
        self.assertIn("não consegue", b)


def _roda(paciente, clinic, roteiro=None, sessao=None, texto="oi, quero agendar"):
    vistas = {}
    anthropic = AnthropicRoteiro(roteiro or [texto_do_modelo("Oi!")])
    original = anthropic.create_message

    def create_message(system, messages, tools, max_tokens, tool_choice=None):
        vistas.setdefault("system", system)
        vistas.setdefault("tools", {t["name"] for t in tools})
        return original(system, messages, tools, max_tokens, tool_choice)

    anthropic.create_message = create_message
    agente = monta_agente(anthropic=anthropic, paciente=paciente,
                          tool_executor=ToolExecutorFalso({"ok": True}))
    agente._clinica = lambda c: dict(clinic)
    if sessao:
        agente.sessao_salva.update(sessao)
    saida = agente.process_message(CLINIC, mensagem(texto))
    return agente, saida, vistas


class TestOBlocoNoAgente(unittest.TestCase):
    def test_paciente_sem_proxima_com_site_ve_o_bloco(self):
        _, _, v = _roda(PACIENTE, COM_SITE)
        self.assertIn("PRIMEIRA TENTATIVA É O SITE", v["system"])
        self.assertIn(LINK, v["system"])

    def test_paciente_com_horario_tambem(self):
        """§7.3 A: segunda sessão também começa pelo link."""
        _, _, v = _roda(COM_SESSAO, COM_SITE)
        self.assertIn("PRIMEIRA TENTATIVA É O SITE", v["system"])

    def test_lead_nova_nao_ve(self):
        _, _, v = _roda(LEAD, COM_SITE)
        self.assertNotIn("PRIMEIRA TENTATIVA É O SITE", v["system"])

    def test_sem_site_ninguem_ve(self):
        _, _, v = _roda(PACIENTE, SEM_SITE)
        self.assertNotIn("PRIMEIRA TENTATIVA É O SITE", v["system"])


# -- A recusa nas tools ------------------------------------------------------

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


def ctx(paciente, link=LINK, sessao=None):
    return {"paciente": paciente, "link_de_agendamento": link,
            "session": sessao if sessao is not None else {},
            "turnos": [{"role": "user", "content": "quero fazer axilas"}]}


class TestRecusa(unittest.TestCase):
    def test_check_availability_e_recusada_antes_do_link(self):
        ex = executor()
        r = ex._tool_check_availability(dict(AREAS), CLINIC, PHONE, ctx(PACIENTE))
        self.assertEqual(r["error"], "primeiro_o_link")
        self.assertEqual(r["link"], LINK)
        self.assertIn("Não pergunte as áreas", r["o_que_fazer"])
        ex.availability_engine.get_available_days_multi.assert_not_called()

    def test_book_appointment_e_recusado_antes_do_link_e_nada_e_gravado(self):
        ex = executor()
        r = ex._tool_book_appointment(dict(AREAS, date="2026-11-25", time="16:30"), CLINIC, PHONE, ctx(PACIENTE))
        self.assertEqual(r["error"], "primeiro_o_link")
        ex.appointment_service.create_appointment.assert_not_called()

    def test_a_recusa_vem_antes_da_de_segunda_sessao(self):
        """Quem tem sessão futura e quer outra: primeiro o link (§7.3 A)."""
        ex = executor()
        r = ex._tool_book_appointment(dict(AREAS, date="2026-11-25", time="18:00"), CLINIC, PHONE, ctx(COM_SESSAO))
        self.assertEqual(r["error"], "primeiro_o_link")

    def test_alterar_agendamento_nao_e_afetada(self):
        """Alterar a sessão que existe continua pela conversa (PRD 045)."""
        ex = executor()
        ex._agendamento_confirmado = lambda a, c: None
        r = ex._tool_alterar_agendamento({"appointment_id": "ap-1", "new_time": "17:00"}, CLINIC, PHONE, ctx(COM_SESSAO))
        self.assertNotEqual(r.get("error"), "primeiro_o_link")


class TestLiberacao(unittest.TestCase):
    def test_depois_do_link_as_tools_passam(self):
        ex = executor()
        sessao = marca_link_enviado({})
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_check_availability(dict(AREAS), CLINIC, PHONE, ctx(PACIENTE, sessao=sessao))
        self.assertNotIn("error", r)
        ex.availability_engine.get_available_days_multi.assert_called_once()

    def test_link_velho_nao_libera(self):
        ex = executor()
        sessao = marca_link_enviado({}, agora=1)   # há muito tempo
        r = ex._tool_check_availability(dict(AREAS), CLINIC, PHONE, ctx(PACIENTE, sessao=sessao))
        self.assertEqual(r["error"], "primeiro_o_link")

    def test_lead_nova_passa_sempre(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_check_availability(dict(AREAS), CLINIC, PHONE, ctx(LEAD))
        self.assertNotIn("error", r)

    def test_sem_site_passa_sempre(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_check_availability(dict(AREAS), CLINIC, PHONE, ctx(PACIENTE, link=None))
        self.assertNotIn("error", r)


# -- O campo da sessão: só mensagem do bot conta -----------------------------

class TestOLinkSaiu(unittest.TestCase):
    def test_texto_do_bot_com_o_link_grava_o_campo(self):
        agente, saida, _ = _roda(PACIENTE, COM_SITE, [
            texto_do_modelo(f"É por lá mesmo 😊 {LINK}agendar - qualquer dúvida, me chama."),
        ])
        self.assertIn(CAMPO_LINK_ENVIADO, agente.sessao_salva)
        self.assertTrue(any("agendar.clinica-teste" in m.content for m in saida))

    def test_texto_sem_o_link_nao_grava(self):
        agente, _, _ = _roda(PACIENTE, COM_SITE, [texto_do_modelo("Oi! Tudo bem?")])
        self.assertNotIn(CAMPO_LINK_ENVIADO, agente.sessao_salva)

    def test_o_caso_real_o_link_sai_e_as_areas_nao(self):
        """O roteiro do modelo tenta consultar; a recusa o manda ao link; a
        mensagem que sai leva o link e não pergunta áreas."""
        chamadas = []

        class Executor(ToolExecutorFalso):
            def execute(self, nome, args, context=None):
                chamadas.append(nome)
                if nome == "check_availability":
                    return {"error": "primeiro_o_link", "link": LINK,
                            "o_que_fazer": "Mande o link e pergunte se ela consegue por lá."}
                return {"ok": True}

        anthropic = AnthropicRoteiro([
            usa_tool("check_availability", AREAS),
            texto_do_modelo(f"É por esse link sim, para todas as pacientes: {LINK} Qualquer dificuldade, me chama 😊"),
        ])
        agente = monta_agente(anthropic=anthropic, paciente=PACIENTE, tool_executor=Executor())
        agente._clinica = lambda c: dict(COM_SITE)
        saida = agente.process_message(CLINIC, mensagem("Para influencer também é por esse link?"))
        enviados = " ".join(m.content for m in saida)
        self.assertIn("agendar.clinica-teste", enviados)
        self.assertNotIn("quais áreas", enviados.lower())
        self.assertIn(CAMPO_LINK_ENVIADO, agente.sessao_salva)


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
        """`_build_system_prompt` e dublado no agente de teste; o bloco de
        campanha e montado em codigo e e conferido direto."""
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
