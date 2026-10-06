# -*- coding: utf-8 -*-
"""O bot não usa área que não foi conversada.

Regressão do piloto de 11/09/2026: perguntado "quais horários para 24/09?", o
bot devolveu horários e fechou com "Costas total + ombros, Lombar e Axilas" -
áreas que ninguém citou, R$ 400,50, a um "sim" de agendar. O prompt já mandava
confirmar. Instrução não segurou; a trava segura.
"""
import unittest

from src.services.confirmacao_de_areas import (
    areas_conversadas,
    recado_de_recusa,
    separa,
)

AREAS = [
    {"id": "a-axilas", "name": "Axilas"},
    {"id": "a-buco", "name": "Buço"},
    {"id": "a-costas", "name": "Costas total + ombros"},
    {"id": "a-lombar", "name": "Lombar"},
    {"id": "a-barba", "name": "Barba contorno"},
]


def conversa(*turnos):
    return [{"role": r, "content": c} for r, c in turnos]


class TestOCasoQueAconteceu(unittest.TestCase):
    def test_a_conversa_do_piloto_nao_libera_nada(self):
        """As 4 mensagens reais do André, sem nenhuma área citada."""
        turnos = conversa(
            ("assistant", "Estamos com novas datas: 23/09, 24/09, 29/09."),
            ("user", "Sim, quais horários disponíveis para 24/09?"),
            ("assistant", "Para quinta, 24 de setembro pela manhã: 07:30, 09:15..."),
            ("user", "Tem à noite?"),
            ("user", "Pode ser 18:10"),
        )
        self.assertEqual(areas_conversadas(turnos, AREAS), set())

    def test_e_por_isso_os_pares_inventados_sao_barrados(self):
        liberadas = areas_conversadas(conversa(("user", "quais horários para 24/09?")), AREAS)
        pares = [{"service_id": "s1", "area_id": "a-costas"},
                 {"service_id": "s1", "area_id": "a-lombar"},
                 {"service_id": "s1", "area_id": "a-axilas"}]

        ok, barrados = separa(pares, liberadas)

        self.assertEqual(ok, [])
        self.assertEqual(len(barrados), 3)


class TestAPacienteNomeia(unittest.TestCase):
    def test_vale_na_hora(self):
        turnos = conversa(("user", "quero fazer axilas"))
        self.assertEqual(areas_conversadas(turnos, AREAS), {"a-axilas"})

    def test_sem_acento_e_em_caixa_baixa(self):
        """'Buço' e 'buco' são a mesma área - ninguém digita cedilha no WhatsApp."""
        self.assertEqual(areas_conversadas(conversa(("user", "buco por favor")), AREAS),
                         {"a-buco"})

    def test_nome_composto(self):
        turnos = conversa(("user", "costas total + ombros"))
        self.assertIn("a-costas", areas_conversadas(turnos, AREAS))

    def test_varias_de_uma_vez(self):
        turnos = conversa(("user", "axilas e buço")) 
        self.assertEqual(areas_conversadas(turnos, AREAS), {"a-axilas", "a-buco"})

    def test_nao_casa_dentro_de_outra_palavra(self):
        """Palavra inteira: senão qualquer texto longo liberaria área por acaso."""
        self.assertEqual(areas_conversadas(conversa(("user", "lombardia")), AREAS), set())


class TestOBotPropoe(unittest.TestCase):
    def test_proposta_sem_resposta_nao_vale(self):
        """Achar no histórico não é perguntar. Enquanto ela não responde, não vale."""
        turnos = conversa(
            ("user", "oi"),
            ("assistant", "Da última vez foram Buço e Barba contorno. Confirma?"),
        )
        self.assertEqual(areas_conversadas(turnos, AREAS), set())

    def test_proposta_respondida_vale(self):
        turnos = conversa(
            ("user", "oi"),
            ("assistant", "Da última vez foram Buço e Barba contorno. Confirma?"),
            ("user", "isso mesmo"),
        )
        self.assertEqual(areas_conversadas(turnos, AREAS), {"a-buco", "a-barba"})

    def test_a_trava_nao_julga_o_sim_nem_o_nao(self):
        """Ela garante que foi CONVERSADO, não que foi aceito.

        Interpretar 'sim' é justamente o que não se pode terceirizar para quem
        errou. O mínimo verificável é: ninguém agenda área que nunca foi dita.
        """
        turnos = conversa(
            ("assistant", "Seriam Buço e Axilas?"),
            ("user", "não, prefiro outra coisa"),
        )
        self.assertEqual(areas_conversadas(turnos, AREAS), {"a-buco", "a-axilas"})


class TestSepara(unittest.TestCase):
    def test_deixa_passar_o_que_foi_conversado(self):
        pares = [{"service_id": "s1", "area_id": "a-axilas"},
                 {"service_id": "s1", "area_id": "a-costas"}]

        ok, barrados = separa(pares, {"a-axilas"})

        self.assertEqual(ok, [{"service_id": "s1", "area_id": "a-axilas"}])
        self.assertEqual(barrados, ["a-costas"])

    def test_lista_vazia(self):
        self.assertEqual(separa([], {"a-axilas"}), ([], []))

    def test_par_sem_area(self):
        ok, barrados = separa([{"service_id": "s1"}], {"a-axilas"})
        self.assertEqual(ok, [])
        self.assertEqual(barrados, [""])


class TestRecado(unittest.TestCase):
    def test_diz_ao_modelo_o_que_fazer(self):
        r = recado_de_recusa(["Axilas"])

        self.assertEqual(r["error"], "areas_nao_confirmadas")
        self.assertIn("Axilas", r["o_que_fazer"])
        self.assertIn("pergunte", r["o_que_fazer"].lower())

    def test_manda_perguntar_mesmo_quando_achou_no_historico(self):
        """Pedido explícito do André: achar não dispensa confirmar."""
        self.assertIn("histórico", recado_de_recusa(["Buço"])["o_que_fazer"])


class TestFracaoEDita(unittest.TestCase):
    """06/10/2026: "meia perna" recusada duas vezes porque a área é "1/2 Perna".

    A trava exigia as palavras "1", "2" e "perna". O próprio bot tinha
    perguntado "perna completa ou meia perna?" - e recusou a resposta.
    """

    FRACOES = [
        {"id": "a-meia-perna", "name": "1/2 Perna"},
        {"id": "a-meio-braco", "name": "1/2 Braço"},
        {"id": "a-perna-completa", "name": "Perna Completa"},
        {"id": "a-axilas", "name": "Axilas"},
    ]

    def test_a_conversa_real(self):
        turnos = conversa(
            ("user", "Olá bom dia, gostaria de agendar no dia 28\nDessa vez quero fazer "
                     "mais duas áreas além das axilas, sendo buço e perna\nVc pode me passar os valores ?"),
            ("assistant", "Legal! Só confirmando uma coisa sobre a perna: você quer a "
                          "*perna completa* ou só *meia perna*? 😊"),
            ("user", "Meia perna"),
            ("assistant", "Então, fechando: *axilas*, *buço* e *meia perna*. Confirma essas áreas? 😊"),
            ("user", "Sim, podemos sim"),
        )
        liberadas = areas_conversadas(turnos, self.FRACOES)
        self.assertIn("a-meia-perna", liberadas)
        self.assertIn("a-axilas", liberadas)

    def test_as_tres_formas_faladas(self):
        for frase in ("meia perna", "meio perna", "metade da perna", "quero a perna, meia só"):
            with self.subTest(frase=frase):
                self.assertIn("a-meia-perna",
                              areas_conversadas(conversa(("user", frase)), self.FRACOES))

    def test_o_simbolo_de_meio(self):
        self.assertIn("a-meia-perna",
                      areas_conversadas(conversa(("user", "½ perna")), self.FRACOES))

    def test_a_fracao_digitada_continua_valendo(self):
        self.assertIn("a-meio-braco",
                      areas_conversadas(conversa(("user", "1/2 braço")), self.FRACOES))

    def test_meia_perna_nao_libera_perna_completa(self):
        liberadas = areas_conversadas(conversa(("user", "meia perna")), self.FRACOES)
        self.assertNotIn("a-perna-completa", liberadas)

    def test_perna_completa_nao_libera_meia_perna(self):
        """'completa' não é 'meia': a área vizinha continua fechada."""
        liberadas = areas_conversadas(conversa(("user", "perna completa")), self.FRACOES)
        self.assertNotIn("a-meia-perna", liberadas)

    def test_so_perna_nao_libera_nenhuma(self):
        """Foi exatamente o que o bot fez certo: perguntou qual."""
        liberadas = areas_conversadas(conversa(("user", "quero fazer a perna")), self.FRACOES)
        self.assertNotIn("a-meia-perna", liberadas)
        self.assertNotIn("a-perna-completa", liberadas)


if __name__ == "__main__":
    unittest.main()
