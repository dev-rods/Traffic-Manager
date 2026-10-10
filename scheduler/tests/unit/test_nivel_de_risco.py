# -*- coding: utf-8 -*-
"""Nível 3: o que vai para uma pessoa antes de o modelo ler (PRD 020 §4.3).

Duas camadas: a lista (aqui) e o fluxo no agente (abaixo, TestNoFluxo). As
frases são do tipo que chega no WhatsApp da Essência, não frases de teste.
"""
import json
import os
import pathlib
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at
from src.services import nivel_de_risco as nr
from src.services import policy_do_faq as pf
from src.services.bot_policy import (
    MOTIVO_AMEACA, MOTIVO_FORA_DO_ESCOPO, MOTIVO_MEDICO, MOTIVO_POS_SESSAO, MOTIVO_RECLAMACAO,
    MOTIVO_REEMBOLSO, MOTIVOS_DO_MODELO, MOTIVOS_LEGIVEIS, TEXTO_DE_RISCO,
)
from src.services.busca_no_faq import busca
from tests.unit.dublagem_agente import CLINIC, AnthropicFalso, ToolExecutorFalso, mensagem, monta_agente

# O FAQ real da Essência (prod, 10/10/2026): a regra de colisão é medida
# contra o que a clínica de fato escreveu, não contra um item inventado.
FAQ_ESSENCIA = json.loads(
    (pathlib.Path(__file__).parent / "faq_essencia.json").read_text(encoding="utf-8"))


class TestALista(unittest.TestCase):

    def test_reclamacao(self):
        for frase in ["Isso é um absurdo, fiquei 40 minutos esperando",
                      "vou no procon", "já falei com meu advogado",
                      "atendimento péssimo", "vou reclamar no reclame aqui"]:
            with self.subTest(frase=frase):
                self.assertEqual(nr.detecta(frase)[0], MOTIVO_RECLAMACAO)

    def test_reembolso_e_dinheiro_que_ja_saiu(self):
        for frase in ["quero meu dinheiro de volta", "preciso do estorno",
                      "fiz o pix e não caiu", "quero o reembolso da sessão",
                      "me cobraram duas vezes"]:
            with self.subTest(frase=frase):
                self.assertEqual(nr.detecta(frase)[0], MOTIVO_REEMBOLSO)

    def test_pagamento_nao_e_risco(self):
        """Decisão do André (09/10): pix, parcelamento e forma de pagamento são FAQ."""
        for frase in ["posso pagar no pix?", "dá pra parcelar em 3x?",
                      "aceita cartão?", "qual a forma de pagamento?"]:
            with self.subTest(frase=frase):
                self.assertIsNone(nr.detecta(frase))

    def test_problema_depois_da_sessao(self):
        for frase in ["a axila ficou toda queimada depois da sessão",
                      "apareceu bolha na virilha", "ficou uma mancha escura",
                      "está doendo muito ainda", "a pele ficou com ferida"]:
            with self.subTest(frase=frase):
                self.assertEqual(nr.detecta(frase)[0], MOTIVO_POS_SESSAO)

    def test_questao_medica_traz_a_consulta_ao_faq(self):
        for frase in ["estou grávida de 4 meses, posso fazer?",
                      "tomo roacutan", "estou amamentando",
                      "uso anticoagulante", "tenho epilepsia"]:
            with self.subTest(frase=frase):
                motivo, consulta = nr.detecta(frase)
                self.assertEqual(motivo, MOTIVO_MEDICO)
                self.assertIn("gestante", consulta)

    def test_ameaca(self):
        for frase in ["vou expor vocês", "vou postar isso no instagram",
                      "vou denunciar a clínica"]:
            with self.subTest(frase=frase):
                self.assertEqual(nr.detecta(frase)[0], MOTIVO_AMEACA)

    def test_conversa_normal_nao_casa(self):
        for frase in ["quero marcar axila e virilha dia 21", "quanto custa o buço?",
                      "dói?", "posso fazer menstruada?", "tem horário sábado?",
                      "obrigada!", "a sessão foi ótima"]:
            with self.subTest(frase=frase):
                self.assertIsNone(nr.detecta(frase))

    def test_ameaca_e_reclamacao_vencem_o_medico(self):
        """'Vou processar porque fiquei queimada' é reclamação, não dúvida médica."""
        self.assertEqual(nr.detecta("vou processar vocês, fiquei queimada e tomo remédio")[0], MOTIVO_AMEACA)
        self.assertEqual(nr.detecta("absurdo, fiquei com bolha e estou grávida")[0], MOTIVO_RECLAMACAO)

    def test_so_o_grupo_medico_tem_colisao_com_o_faq(self):
        """'Ficou com ferida' é problema real mesmo que o FAQ de
        contraindicações cite 'feridas': vai a pessoa sempre."""
        for frase in ["ficou com ferida", "vou no procon", "quero estorno", "vou expor"]:
            with self.subTest(frase=frase):
                self.assertIsNone(nr.detecta(frase)[1])

    def test_termos_da_clinica(self):
        clinic = {"bot_termos_de_risco": ["gerente", "Dona Clara", "("]}
        self.assertEqual(nr.detecta("quero falar com a gerente", clinic)[0], MOTIVO_RECLAMACAO)
        self.assertEqual(nr.detecta("a dona clara prometeu", clinic)[0], MOTIVO_RECLAMACAO)
        self.assertIsNone(nr.detecta("(", clinic))
        self.assertEqual(nr.termos_da_clinica(clinic), ["gerente", "Dona Clara", "("])

    def test_acentos_e_maiusculas(self):
        self.assertEqual(nr.detecta("ABSURDO!!! Péssimo")[0], MOTIVO_RECLAMACAO)
        self.assertEqual(nr.detecta("Estou GRÁVIDA")[0], MOTIVO_MEDICO)


class TestColisaoComOFaqReal(unittest.TestCase):
    """A consulta canônica do grupo médico acha o item de contraindicações da
    Essência; sem isso, toda grávida iria para pessoa com o FAQ respondendo."""

    def test_gestante_cai_em_contraindicacoes(self):
        _, consulta = nr.detecta("estou grávida, posso fazer?")
        achados = busca(consulta, FAQ_ESSENCIA)
        self.assertTrue(achados)
        self.assertEqual(achados[0]["question_key"], "CONTRAINDICATIONS")

    def test_clinica_sem_faq_nao_cobre(self):
        _, consulta = nr.detecta("estou grávida, posso fazer?")
        self.assertEqual(busca(consulta, []), [])


class TestMotivos(unittest.TestCase):

    def test_tem_rotulo_e_nao_sao_do_modelo(self):
        for m in (MOTIVO_RECLAMACAO, MOTIVO_REEMBOLSO, MOTIVO_POS_SESSAO, MOTIVO_MEDICO, MOTIVO_AMEACA):
            with self.subTest(motivo=m):
                self.assertIn(m, MOTIVOS_LEGIVEIS)
                self.assertNotIn(m, MOTIVOS_DO_MODELO)


class TestNoFluxo(unittest.TestCase):
    """O agente recebe a mensagem e sai pela pessoa sem chamar o modelo."""

    def _agente(self, faq=None):
        anthropic = AnthropicFalso()
        tools = ToolExecutorFalso()
        agente = monta_agente(anthropic=anthropic, tool_executor=tools)
        agente.db = mock.MagicMock()
        agente.db.execute_query.return_value = [{"id": "tarefa-1"}]
        agente._config_fora_do_escopo = lambda c: {}
        self.patcher = mock.patch.object(pf, "itens", return_value=list(faq or []))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        return agente, anthropic, tools

    def test_queimadura_vai_a_pessoa_sem_modelo(self):
        agente, anthropic, tools = self._agente(FAQ_ESSENCIA)
        saida = agente.process_message(CLINIC, mensagem("a axila ficou toda queimada depois da sessão de ontem"))
        self.assertEqual(anthropic.chamadas, 0, "a mensagem chegou ao modelo")
        self.assertEqual(tools.chamadas, [])
        self.assertEqual([m.content for m in saida], [TEXTO_DE_RISCO])
        sessao = agente.sessao_salva
        self.assertEqual(at.estado(sessao), at.HUMAN_ACTIVE)
        self.assertEqual(sessao[at.CAMPO]["handoff_reason"], MOTIVO_POS_SESSAO)
        self.assertEqual(sessao[at.CAMPO]["pending_intent"], MOTIVO_POS_SESSAO, "a fila vê a pendência")
        self.assertEqual(sessao[at.CAMPO]["pending_task_id"], "tarefa-1")

    def test_gravida_com_faq_de_contraindicacoes_segue_para_o_modelo(self):
        agente, anthropic, _ = self._agente(FAQ_ESSENCIA)
        agente.process_message(CLINIC, mensagem("estou grávida de 4 meses, posso fazer?"))
        self.assertEqual(anthropic.chamadas, 1, "a clínica escreveu sobre isso: o modelo escolhe o item")
        self.assertNotEqual(at.estado(agente.sessao_salva), at.HUMAN_ACTIVE)

    def test_gravida_sem_faq_vai_a_pessoa(self):
        agente, anthropic, _ = self._agente(faq=[])
        saida = agente.process_message(CLINIC, mensagem("estou grávida, posso fazer?"))
        self.assertEqual(anthropic.chamadas, 0)
        self.assertEqual(agente.sessao_salva[at.CAMPO]["handoff_reason"], MOTIVO_MEDICO)
        self.assertEqual(saida[0].content, TEXTO_DE_RISCO)

    def test_reclamacao_vai_a_pessoa_mesmo_com_faq(self):
        agente, anthropic, _ = self._agente(FAQ_ESSENCIA)
        agente.process_message(CLINIC, mensagem("isso é um absurdo, vou no procon"))
        self.assertEqual(anthropic.chamadas, 0)
        self.assertEqual(agente.sessao_salva[at.CAMPO]["handoff_reason"], MOTIVO_RECLAMACAO)

    def test_gatilho_do_sistema_nao_passa_pela_guarda(self):
        """Retomada e lembrete são texto nosso; a guarda lê a fala da pessoa."""
        from src.services.conversation_resume import GATILHO_RETOMADA
        agente, anthropic, _ = self._agente(FAQ_ESSENCIA)
        agente.process_message(CLINIC, mensagem(GATILHO_RETOMADA))
        self.assertEqual(anthropic.chamadas, 1)

    def test_fora_do_escopo_tambem_abre_a_pendencia(self):
        """Mesmo caminho de saída: quem sai antes do modelo deixa tarefa na fila."""
        agente, anthropic, _ = self._agente(FAQ_ESSENCIA)
        agente.process_message(CLINIC, mensagem("vocês fazem botox?"))
        self.assertEqual(anthropic.chamadas, 0)
        sessao = agente.sessao_salva
        self.assertEqual(sessao[at.CAMPO]["handoff_reason"], MOTIVO_FORA_DO_ESCOPO)
        self.assertEqual(sessao[at.CAMPO]["pending_task_id"], "tarefa-1")


class TestMigracao(unittest.TestCase):
    def test_coluna_na_tabela_e_na_migration(self):
        from src.scripts import setup_database as sd
        sql = " ".join(s for s in sd.SQL_STATEMENTS if isinstance(s, str))
        self.assertIn("ADD COLUMN IF NOT EXISTS bot_termos_de_risco TEXT[] NOT NULL DEFAULT '{}'", sql)
        criacao = next(s for s in sd.SQL_STATEMENTS if "CREATE TABLE IF NOT EXISTS scheduler.clinics" in s)
        self.assertIn("bot_termos_de_risco TEXT[]", criacao)


if __name__ == "__main__":
    unittest.main()
