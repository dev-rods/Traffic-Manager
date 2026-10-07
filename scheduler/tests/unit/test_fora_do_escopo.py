# -*- coding: utf-8 -*-
"""Pergunta sobre outro procedimento vai para uma pessoa, não para o FAQ.

A Essência vende preenchimento, toxina botulínica e bioestimulador, e o bot
atende só depilação a laser. Hoje isso dava certo por acidente: "vocês fazem
botox?" não casava nada no FAQ, a tool devolvia vazio, e a instrução de chamar a
especialista saía no lugar certo.

O acidente desmonta quando a pergunta carrega palavra de laser. É o que o
primeiro grupo de testes aqui mede, contra o FAQ REAL: "quanto custa a toxina
botulínica por sessão?" casa "custa" e "sessão" com itens de depilação e passa
do piso de relevância - então, sem a guarda, o bot responderia PREÇO DE LASER a
quem perguntou de injetável. Esse é o erro caro: a pessoa chega na clínica com
um número na cabeça que nunca foi dela.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from faq_real import FAQ_ESSENCIA
from src.services.bot_policy import (
    CAMPO_DE_PAUSA,
    CAMPO_DO_MOTIVO,
    MOTIVOS_DO_MODELO,
    MOTIVOS_LEGIVEIS,
    MOTIVO_FORA_DO_ESCOPO,
    MOTIVO_INSTABILIDADE,
    PAUSA_HANDOFF,
    PAUSA_INSTABILIDADE,
    TTL_DO_ATENDIMENTO,
    entrega_a_humano,
    entrega_por_instabilidade,
    motivo_do_handoff_legivel,
)
from src.services.busca_no_faq import busca
from src.services.fora_do_escopo import PROCEDIMENTOS, detecta


class PorQueOAcidenteNaoBasta(unittest.TestCase):
    """O FAQ de laser responde perguntas de injetável, e com confiança."""

    def test_a_guarda_nao_depende_do_que_o_faq_devolve(self):
        # Esta foi a razão de a guarda existir: em 04/10/2026 esta pergunta
        # CASAVA itens de laser no FAQ ("custa" e "sessão"), e a paciente
        # receberia preço de laser para uma dúvida de injetável. Em 06/10 a
        # cobertura do título (busca_no_faq.PESO_DA_COBERTURA) passou a
        # devolver vazio aqui - e a guarda continua certa, porque a clínica
        # pode cadastrar um item amanhã que volte a casar. O que se fixa é que
        # a decisão é da guarda, qualquer que seja a resposta do FAQ.
        pergunta = "quanto custa a toxina botulinica por sessao?"
        busca(pergunta, FAQ_ESSENCIA)  # pode casar ou não; não muda o veredito
        self.assertEqual(detecta(pergunta), "toxina_botulinica")

    def test_a_guarda_barra_antes_de_chegar_ao_faq(self):
        self.assertEqual(
            detecta("quanto custa a toxina botulinica por sessao?"),
            "toxina_botulinica",
        )


class OQueAGuardaPega(unittest.TestCase):
    def test_procedimentos_nomeados(self):
        casos = {
            "vocês fazem botox?": "toxina_botulinica",
            "queria saber de toxina botulínica": "toxina_botulinica",
            "Fazem preenchimento labial?": "preenchimento",
            "quanto custa o ácido hialurônico": "preenchimento",
            "tem bioestimulador de colágeno?": "bioestimulador",
            "vocês fazem limpeza de pele junto com a sessão?": "limpeza_de_pele",
            "faz peeling químico?": "peeling",
            "queria microagulhamento": "microagulhamento",
            "tem criolipólise aí?": "criolipolise",
            "vocês fazem drenagem linfática?": "massagem",
            "quanto é a extensão de cílios": "micropigmentacao",
            "tem ultraformer?": "ultraformer",
            "o lavieen some com melasma?": "lavieen",
        }
        for pergunta, esperado in casos.items():
            with self.subTest(pergunta=pergunta):
                self.assertEqual(detecta(pergunta), esperado)

    def test_acento_e_caixa_nao_importam(self):
        # A paciente escreve do celular, sem acento e em qualquer caixa.
        for escrita in ("BOTULINICA", "botulínica", "Botulinica", "botulínica"):
            with self.subTest(escrita=escrita):
                self.assertEqual(detecta(f"faz {escrita}?"), "toxina_botulinica")

    def test_mensagem_de_laser_passa_livre(self):
        # O caminho normal não pode sofrer: a guarda roda em TODA mensagem
        # recebida, e um falso positivo aqui manda a conversa de agendamento
        # para uma pessoa sem motivo.
        normais = [
            "oi, queria agendar depilação a laser",
            "quanto custa axila e virilha?",
            "quantas sessões preciso fazer?",
            "posso fazer menstruada?",
            "tem horário amanhã de tarde?",
            "pode pegar sol depois da sessão?",
            "o laser dói muito?",
            "queria remarcar minha sessão de sexta",
            "meu nome é Ana Clara Souza",
            "virilha completa e perianal",
        ]
        for mensagem in normais:
            with self.subTest(mensagem=mensagem):
                self.assertIsNone(detecta(mensagem))

    def test_vazio_e_nulo_nao_quebram(self):
        for entrada in ("", None, "   "):
            with self.subTest(entrada=entrada):
                self.assertIsNone(detecta(entrada))

    def test_fronteira_de_palavra(self):
        # "enzimas" é da lista; "enzimático" não deve casar por prefixo, senão
        # qualquer palavra que comece igual vira handoff.
        self.assertIsNone(detecta("uso um sabonete enzimatico em casa"))

    def test_todo_padrao_da_lista_e_alcancavel(self):
        # Padrão que não casa o próprio nome é padrão morto - e morreria calado,
        # porque ninguém testa o procedimento que a clínica ainda não vendeu.
        for nome, _ in PROCEDIMENTOS:
            with self.subTest(nome=nome):
                legivel = nome.replace("_", " ")
                self.assertEqual(
                    detecta(f"vocês fazem {legivel}?"),
                    nome,
                    f"o padrão de {nome} não casa nem o próprio nome",
                )


class TermosDaClinica(unittest.TestCase):
    """A coluna acrescenta, nunca substitui."""

    def test_termo_da_clinica_casa(self):
        clinic = {"bot_procedimentos_fora_do_escopo": ["jato de plasma"]}
        self.assertEqual(
            detecta("vocês fazem jato de plasma?", clinic), "clinica:jato de plasma"
        )

    def test_lista_do_codigo_continua_valendo_com_a_coluna_preenchida(self):
        clinic = {"bot_procedimentos_fora_do_escopo": ["jato de plasma"]}
        self.assertEqual(detecta("faz botox?", clinic), "toxina_botulinica")

    def test_coluna_vazia_ou_ausente(self):
        for clinic in ({}, None, {"bot_procedimentos_fora_do_escopo": []},
                       {"bot_procedimentos_fora_do_escopo": None}):
            with self.subTest(clinic=clinic):
                self.assertEqual(detecta("faz botox?", clinic), "toxina_botulinica")
                self.assertIsNone(detecta("quero agendar laser", clinic))

    def test_termo_com_caractere_de_regex_nao_derruba(self):
        # Quem preenche a coluna é a recepção, não um programador. Um "(" ali
        # não pode calar o bot para as pacientes dessa clínica.
        clinic = {"bot_procedimentos_fora_do_escopo": ["plasma (jato", "", "  "]}
        self.assertIsNone(detecta("quero agendar laser", clinic))
        self.assertEqual(detecta("faz botox?", clinic), "toxina_botulinica")


class EntregaAHumano(unittest.TestCase):
    """O bloco que estava copiado em sete lugares, agora num só."""

    def test_grava_os_quatro_campos_e_o_motivo(self):
        session = {}
        entrega_a_humano(session, MOTIVO_FORA_DO_ESCOPO, agora=1_000)
        self.assertEqual(session["state"], "HUMAN_HANDOFF")
        self.assertEqual(session["human_handoff_requested_at"], 1_000)
        self.assertEqual(session["attendant_active_until"], 1_000 + TTL_DO_ATENDIMENTO)
        self.assertEqual(session[CAMPO_DE_PAUSA], PAUSA_HANDOFF)
        self.assertEqual(session[CAMPO_DO_MOTIVO], MOTIVO_FORA_DO_ESCOPO)

    def test_preserva_o_resto_da_sessao(self):
        # A conversa não pode perder o histórico ao ser entregue: é justamente
        # ele que a atendente vai ler.
        session = {"agent_history": [{"role": "user", "content": "oi"}], "lead_id": "7"}
        entrega_a_humano(session, MOTIVO_FORA_DO_ESCOPO)
        self.assertEqual(len(session["agent_history"]), 1)
        self.assertEqual(session["lead_id"], "7")

    def test_sessao_nula_devolve_dict(self):
        self.assertEqual(entrega_a_humano(None, MOTIVO_FORA_DO_ESCOPO)["state"],
                         "HUMAN_HANDOFF")

    def test_instabilidade_tem_pausa_e_motivo_proprios(self):
        # Separadas de propósito: HANDOFF é o bot pedindo ajuda, INSTABILIDADE é
        # ele não ter conseguido decidir nada. Só assim dá para medir quanto da
        # transferência é falha nossa.
        session = entrega_por_instabilidade({}, agora=500)
        self.assertEqual(session[CAMPO_DE_PAUSA], PAUSA_INSTABILIDADE)
        self.assertEqual(session[CAMPO_DO_MOTIVO], MOTIVO_INSTABILIDADE)
        self.assertEqual(session["attendant_active_until"], 500 + TTL_DO_ATENDIMENTO)


class MotivosLegiveis(unittest.TestCase):
    def test_todo_motivo_tem_rotulo(self):
        # Motivo sem rótulo chega à tela como string crua tipo
        # "procedimento_fora_do_escopo", que a recepção não deveria ter que ler.
        for nome, valor in sorted(vars(__import__(
                "src.services.bot_policy", fromlist=["x"])).items()):
            if nome.startswith("MOTIVO_") and isinstance(valor, str):
                with self.subTest(motivo=nome):
                    self.assertIn(valor, MOTIVOS_LEGIVEIS)

    def test_motivos_do_modelo_sao_subconjunto(self):
        for motivo in MOTIVOS_DO_MODELO:
            self.assertIn(motivo, MOTIVOS_LEGIVEIS)

    def test_sem_handoff_nao_ha_rotulo(self):
        self.assertEqual(motivo_do_handoff_legivel({}), "")
        self.assertEqual(motivo_do_handoff_legivel(None), "")

    def test_rotulo_do_fora_do_escopo(self):
        session = entrega_a_humano({}, MOTIVO_FORA_DO_ESCOPO)
        self.assertEqual(
            motivo_do_handoff_legivel(session), "Perguntou sobre outro procedimento"
        )

    def test_motivo_desconhecido_vira_o_proprio_valor(self):
        # Não inventa rótulo bonito para o que não está na régua, e também não
        # some com a informação: a atendente vê o valor cru e sabe que há algo
        # para arrumar aqui.
        self.assertEqual(motivo_do_handoff_legivel({CAMPO_DO_MOTIVO: "xpto"}), "xpto")


if __name__ == "__main__":
    unittest.main()
