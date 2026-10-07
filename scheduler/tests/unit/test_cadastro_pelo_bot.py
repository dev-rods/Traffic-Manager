# -*- coding: utf-8 -*-
"""O CPF que a pessoa dita no WhatsApp chega ao cadastro.

O bot pede nome, nascimento, CPF e e-mail antes de agendar, e a pessoa
respondia. Mesmo assim, dos 272 pacientes da Essência, 3 tinham CPF - e os 3
já eram pacientes antes de agendar.

`_salva_cadastro_do_paciente` faz UPDATE e rodava ANTES de `create_appointment`,
que é quem cria o paciente. Para quem agenda pela primeira vez o UPDATE acertava
zero linhas, e os dados sumiam sem erro, sem log e sem teste vermelho.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"


# A trava de areas consulta as areas da clinica e a transcricao da conversa.
# Aqui a paciente pede "axilas" em voz alta, que e o caminho normal - sem isso
# `book_appointment` recusa, e com razao.
AREAS = [{"id": "a1", "name": "Axilas"}]
CONVERSA = {"turnos": [{"role": "user", "content": "quero fazer axilas"}]}


def executor(rowcount=1):
    db = mock.MagicMock()
    db.execute_write.return_value = rowcount
    # So a consulta de areas e roteada; o resto segue MagicMock como antes,
    # senao `duration_rules` recebe a lista de areas no lugar da duracao.
    db.execute_query.side_effect = lambda sql, params=None: (
        AREAS if "FROM scheduler.areas" in sql else mock.MagicMock())
    ex = object.__new__(ToolExecutor)
    ex.db = db
    ex.appointment_service = mock.MagicMock()
    ex.appointment_service.create_appointment.return_value = {"id": "ap1"}
    ex.availability_engine = mock.MagicMock()
    return ex


class TestOrdemDaGravacao(unittest.TestCase):
    """O paciente precisa existir antes do UPDATE que o completa."""

    def test_o_cadastro_e_gravado_depois_de_criar_o_agendamento(self):
        ex = executor()
        ordem = []
        ex.appointment_service.create_appointment.side_effect = (
            lambda **kw: (ordem.append("cria_agendamento"), {"id": "ap1"})[1])
        original = ex._salva_cadastro_do_paciente
        ex._salva_cadastro_do_paciente = (
            lambda *a, **k: (ordem.append("salva_cadastro"), original(*a, **k))[1])

        ex._tool_book_appointment({
            "date": "2026-09-23", "time": "14:00",
            "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}],
            "full_name": "Maria Silva", "cpf": "079.039.845-19",
            "birth_date": "1999-12-29", "email": "m@x.com",
        }, CLINIC, PHONE, dict(CONVERSA))

        self.assertEqual(ordem, ["cria_agendamento", "salva_cadastro"],
                         "o UPDATE do cadastro rodou antes de o paciente existir")


class TestGravacao(unittest.TestCase):
    def test_cpf_vai_so_com_digitos(self):
        """Guardar como veio faria a busca depender de a pessoa ter digitado
        com ponto ou sem."""
        ex = executor()
        ex._salva_cadastro_do_paciente(CLINIC, PHONE, cpf="079.039.845-19")

        params = ex.db.execute_write.call_args[0][1]
        self.assertIn("07903984519", params)

    def test_sem_dado_nenhum_nao_toca_no_banco(self):
        ex = executor()
        ex._salva_cadastro_do_paciente(CLINIC, PHONE)

        ex.db.execute_write.assert_not_called()

    def test_coalesce_preserva_o_que_ja_existe(self):
        """A pessoa pode informar parte numa conversa e o resto em outra."""
        ex = executor()
        ex._salva_cadastro_do_paciente(CLINIC, PHONE, cpf="07903984519")

        sql = ex.db.execute_write.call_args[0][0]
        self.assertEqual(sql.count("COALESCE"), 3)

    def test_update_sem_efeito_vira_aviso(self):
        """Zero linhas era o defeito antigo. Sem o aviso ele volta invisível."""
        ex = executor(rowcount=0)

        with self.assertLogs("src.services.ai_tools", level="WARNING") as log:
            ex._salva_cadastro_do_paciente(CLINIC, PHONE, cpf="07903984519")

        self.assertIn("nao encontrado", " ".join(log.output))

    def test_falha_no_cadastro_nao_derruba_o_agendamento(self):
        """Perder a sessão por causa de um CPF mal formatado seria pior."""
        ex = executor()
        ex.db.execute_write.side_effect = RuntimeError("banco fora")

        ex._salva_cadastro_do_paciente(CLINIC, PHONE, cpf="07903984519")


# -- A Yasmin: cadastrada, e mesmo assim ouviu "me envia CPF" (05/10/2026) --

from tests.unit.dublagem_agente import (  # noqa: E402
    AnthropicRoteiro,
    mensagem,
    monta_agente,
    texto_do_modelo,
)

YASMIN = {
    "encontrado": True, "patient_id": "1ce44d35", "nome": "Yasmin Alves de Souza Lopes",
    "cadastro_completo": True, "sessoes_feitas": 0, "ultima_sessao": None,
    "agendamento_futuro": None,
}
PEDIDO_DE_CADASTRO = (
    "Perfeito! Para finalizar o cadastro, me envia: "
    "Nome completo, Data de nascimento, CPF, E-mail"
)


class TestPacienteCadastradaNaoOuvePedidoDeCadastro(unittest.TestCase):
    """O caso real, de ponta a ponta no agente, sem banco e sem rede."""

    def test_o_modelo_e_mandado_refazer_e_a_resposta_sai_sem_o_pedido(self):
        anthropic = AnthropicRoteiro([
            texto_do_modelo(PEDIDO_DE_CADASTRO),
            texto_do_modelo("Perfeito, Yasmin! Sua sessão está marcada 😊"),
        ])
        agente = monta_agente(anthropic, paciente=YASMIN)

        saida = agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertEqual(len(anthropic.correcoes), 1)
        self.assertIn("JA E PACIENTE CADASTRADA", anthropic.correcoes[0])
        self.assertNotIn("CPF", saida[0].content)
        self.assertIn("Yasmin", saida[0].content)

    def test_se_insistir_a_mensagem_nao_sai_e_vai_para_uma_pessoa(self):
        anthropic = AnthropicRoteiro([
            texto_do_modelo(PEDIDO_DE_CADASTRO),
            texto_do_modelo("Só preciso do seu CPF e data de nascimento 😊"),
        ])
        agente = monta_agente(anthropic, paciente=YASMIN)

        saida = agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertNotIn("CPF", saida[0].content)
        self.assertEqual(agente.sessao_salva.get("bot_pausado_por"), "HANDOFF")
        self.assertEqual(agente.sessao_salva.get("handoff_reason"), "insistiu_em_cadastro")

    def test_lead_desconhecida_continua_ouvindo_o_pedido(self):
        """O caso positivo: a trava não pode calar o fluxo de quem NÃO tem
        cadastro - é dela que o cadastro vem."""
        anthropic = AnthropicRoteiro([texto_do_modelo(PEDIDO_DE_CADASTRO)])
        agente = monta_agente(anthropic, paciente={"encontrado": False})

        saida = agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertEqual(anthropic.correcoes, [])
        self.assertIn("CPF", saida[0].content)

    def test_cadastro_incompleto_tambem_ouve(self):
        """Encontrada mas sem e-mail: ainda há o que perguntar."""
        anthropic = AnthropicRoteiro([texto_do_modelo(PEDIDO_DE_CADASTRO)])
        agente = monta_agente(anthropic, paciente={**YASMIN, "cadastro_completo": False})

        saida = agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertIn("CPF", saida[0].content)

    def test_o_prompt_perde_o_passo_de_cadastro(self):
        """Retirado, não contradito: o modelo não recebe o texto pronto."""
        from tests.unit.test_identificacao_de_paciente import PROMPT_REAL
        from tests.unit.dublagem_agente import AnthropicFalso

        anthropic = AnthropicFalso("ok")
        agente = monta_agente(anthropic, paciente=YASMIN)
        agente._build_system_prompt = lambda c, p, sessao=None: PROMPT_REAL

        agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertNotIn("Para finalizar o cadastro", anthropic.prompts[0])
        self.assertIn("nome: Yasmin Alves de Souza Lopes", anthropic.prompts[0])

    def test_lead_desconhecida_recebe_o_prompt_intacto(self):
        """O prefixo cacheado do fluxo de lead não muda um byte."""
        from tests.unit.test_identificacao_de_paciente import PROMPT_REAL
        from tests.unit.dublagem_agente import AnthropicFalso

        anthropic = AnthropicFalso("ok")
        agente = monta_agente(anthropic, paciente={"encontrado": False})
        agente._build_system_prompt = lambda c, p, sessao=None: PROMPT_REAL

        agente.process_message(CLINIC, mensagem("confirmo"))

        self.assertEqual(anthropic.prompts[0], PROMPT_REAL)

    def test_a_identidade_chega_as_tools(self):
        """book_appointment lê o nome do contexto; a tool nova lê de lá também."""
        contextos = []

        class Executor:
            chamadas = []

            def execute(self, nome, args, context=None):
                contextos.append(context)
                return {"ok": True}

        agente = monta_agente(tool_executor=Executor(), paciente=YASMIN)
        agente.process_message(CLINIC, mensagem("quando é minha sessão?"))

        self.assertTrue(contextos)
        for ctx in contextos:
            self.assertEqual(ctx["paciente"], YASMIN)


class TestBookSemNome(unittest.TestCase):
    """full_name saiu de `required`: quem tem cadastro não o dita de novo."""

    def _agenda(self, paciente, args_extra=None):
        ex = executor()
        args = {"date": "2026-09-23", "time": "14:00",
                "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}
        args.update(args_extra or {})
        ctx = dict(CONVERSA)
        ctx["paciente"] = paciente
        return ex, ex._tool_book_appointment(args, CLINIC, PHONE, ctx)

    def test_paciente_identificada_agenda_com_o_nome_do_cadastro(self):
        ex, r = self._agenda({"encontrado": True, "nome": "Yasmin Alves", "cadastro_completo": True})

        self.assertTrue(r.get("success"), r)
        self.assertEqual(r["full_name"], "Yasmin Alves")
        kw = ex.appointment_service.create_appointment.call_args[1]
        self.assertEqual(kw["full_name"], "Yasmin Alves")

    def test_nome_na_chamada_vence_o_do_cadastro(self):
        ex, r = self._agenda({"encontrado": True, "nome": "Yasmin Alves"},
                             {"full_name": "Yasmin A. de Souza"})
        self.assertEqual(r["full_name"], "Yasmin A. de Souza")

    def test_desconhecida_sem_nome_e_recusada_dizendo_o_que_fazer(self):
        ex, r = self._agenda({"encontrado": False})

        self.assertEqual(r["error"], "full_name_obrigatorio")
        self.assertIn("nome completo", r["o_que_fazer"])
        ex.appointment_service.create_appointment.assert_not_called()

    def test_ambigua_sem_nome_e_recusada(self):
        """Dois cadastros no número: agendar em nome de um deles é chute."""
        ex, r = self._agenda({"encontrado": False, "ambiguo": True, "candidatos": ["A", "B"]})

        self.assertEqual(r["error"], "full_name_obrigatorio")
        ex.appointment_service.create_appointment.assert_not_called()

    def test_sem_contexto_consulta_o_banco_uma_vez(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.identificar_paciente",
                        return_value={"encontrado": True, "nome": "Do Banco"}) as ident:
            r = ex._tool_book_appointment(
                {"date": "2026-09-23", "time": "14:00",
                 "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]},
                CLINIC, PHONE, dict(CONVERSA))
        self.assertEqual(r["full_name"], "Do Banco")
        ident.assert_called_once()


class TestToolIdentificarPaciente(unittest.TestCase):
    def test_le_do_contexto_sem_consultar(self):
        ex = executor()
        r = ex._tool_identificar_paciente({}, CLINIC, PHONE, {"paciente": {"encontrado": True, "nome": "X"}})
        self.assertEqual(r["nome"], "X")
        ex.db.execute_query.assert_not_called()

    def test_sem_contexto_consulta(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.identificar_paciente",
                        return_value={"encontrado": False}) as ident:
            r = ex._tool_identificar_paciente({}, CLINIC, PHONE, {})
        self.assertEqual(r, {"encontrado": False})
        ident.assert_called_once_with(ex.db, CLINIC, PHONE)


if __name__ == "__main__":
    unittest.main()
