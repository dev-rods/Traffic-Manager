# -*- coding: utf-8 -*-
"""O espelho da lista de conversas do WhatsApp.

É o que torna visível o atendimento humano: a atendente responde pelo celular, a
mensagem chega com LID sem vínculo e o webhook descarta. Sem este espelho, 17
dos 37 leads do site apareciam como sem contato tendo conversa.
"""
import unittest
from datetime import timezone

from src.services.sincroniza_conversas import grava, linhas_do_zapi


def chat(phone, **extra):
    d = {"phone": phone, "name": "Fulana", "lid": "123@lid",
         "lastMessageTime": "1787845479000", "messagesUnread": "0",
         "isGroup": False}
    d.update(extra)
    return d


class TestLinhasDoZapi(unittest.TestCase):
    def test_converte_o_essencial(self):
        linha = linhas_do_zapi([chat("554797053940", name="Julia Dalcoquio")])[0]

        self.assertEqual(linha["phone"], "554797053940")
        self.assertEqual(linha["name"], "Julia Dalcoquio")
        self.assertEqual(linha["last_message_at"].tzinfo, timezone.utc)

    def test_grupo_nao_e_lead(self):
        for marca in (True, "true"):
            with self.subTest(marca=marca):
                self.assertEqual(linhas_do_zapi([chat("5511999990000", isGroup=marca)]), [])

    def test_conversa_sem_telefone_sai(self):
        """Só LID não casa com lead nenhum e viraria linha órfã."""
        self.assertEqual(linhas_do_zapi([chat("")]), [])
        self.assertEqual(linhas_do_zapi([chat("123")]), [])

    def test_telefone_repetido_entra_uma_vez(self):
        """A chave da tabela é (clinic_id, phone): duplicata quebraria o insert."""
        linhas = linhas_do_zapi([chat("554797053940"), chat("554797053940")])

        self.assertEqual(len(linhas), 1)

    def test_horario_ausente_ou_zerado(self):
        """O z-api devolve 0 em conversa sem mensagem; virar 1970 seria pior que
        vazio, porque a tela ordena por recência."""
        for valor in (None, 0, "0", "", "abc"):
            with self.subTest(valor=valor):
                self.assertIsNone(
                    linhas_do_zapi([chat("554797053940", lastMessageTime=valor)])[0]
                    ["last_message_at"])

    def test_lista_vazia(self):
        self.assertEqual(linhas_do_zapi([]), [])
        self.assertEqual(linhas_do_zapi(None), [])


class DbFalso:
    def __init__(self):
        self.escritas = []

    def execute_write(self, sql, params=None):
        self.escritas.append((sql.strip().split()[0], params))


class TestGrava(unittest.TestCase):
    def test_apaga_e_reinsere(self):
        db = DbFalso()
        n = grava(db, "clinica-1", linhas_do_zapi([chat("554797053940")]))

        self.assertEqual(n, 1)
        self.assertEqual(db.escritas[0][0], "DELETE")
        self.assertEqual(db.escritas[1][0], "INSERT")

    def test_zero_conversas_nao_apaga_o_espelho(self):
        """Lista vazia quase sempre é instância desconectada. Zerar apagaria
        informação boa por causa de uma falha passageira."""
        db = DbFalso()
        n = grava(db, "clinica-1", [])

        self.assertEqual(n, 0)
        self.assertEqual(db.escritas, [])


if __name__ == "__main__":
    unittest.main()
