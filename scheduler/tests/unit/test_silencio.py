# -*- coding: utf-8 -*-
"""O registro do silêncio por contato (PRD 039)."""
import unittest
from unittest import mock

from src.services import silencio

CLINICA = "clinica-x"
FONE = "5511999990000"


class BancoFalso:
    """Dublê que responde por SQL e guarda o que foi escrito."""

    def __init__(self, vivos=None, estoura=False):
        self.vivos = dict(vivos or {})
        self.estoura = estoura
        self.escritas = []

    def execute_query(self, sql, params=None):
        if self.estoura:
            raise RuntimeError("banco fora do ar")
        assert "contatos_silenciados" in sql, sql
        if "SELECT phone" in sql:
            return [{"phone": p} for p in self.vivos]
        fone = params[1]
        vivo = self.vivos.get(fone)
        if not vivo:
            return []
        if "SELECT 1" in sql:
            return [{"?column?": 1}]
        return [dict(vivo)]

    def execute_write_returning(self, sql, params=None):
        clinic_id, fone, motivo, autor = params
        if fone in self.vivos:
            return None          # o índice único parcial recusa
        linha = {"motivo": motivo, "silenciado_por": autor,
                 "silenciado_em": "2026-11-08T12:00:00+00:00"}
        self.vivos[fone] = linha
        self.escritas.append(("silencia", clinic_id, fone, motivo, autor))
        return dict(linha)

    def execute_write(self, sql, params=None):
        autor, clinic_id, fone = params
        if fone not in self.vivos:
            return 0
        del self.vivos[fone]
        self.escritas.append(("reativa", clinic_id, fone, autor))
        return 1


class TestMotivoObrigatorio(unittest.TestCase):
    """Silenciar sem motivo é o que produz o número calado e esquecido."""

    def test_motivo_vazio_recusa(self):
        for ruim in (None, "", "   ", "ok"):
            with self.subTest(motivo=ruim):
                with self.assertRaises(ValueError):
                    silencio.silencia(CLINICA, FONE, ruim, "ana", BancoFalso())

    def test_motivo_longo_e_cortado_nao_recusado(self):
        banco = BancoFalso()
        r = silencio.silencia(CLINICA, FONE, "x" * 900, "ana", banco)
        self.assertEqual(len(r["motivo"]), silencio.MOTIVO_MAX)


class TestTelefoneNormalizado(unittest.TestCase):
    """O mesmo número em três formatos tem de ser UM registro."""

    def test_formatos_equivalentes(self):
        banco = BancoFalso()
        silencio.silencia(CLINICA, "+55 (11) 99999-0000", "atendimento manual", "ana", banco)
        for variante in ("5511999990000", "11999990000", "+55 11 99999-0000"):
            with self.subTest(variante=variante):
                self.assertTrue(silencio.esta_silenciado(CLINICA, variante, banco))


class TestIdempotencia(unittest.TestCase):
    def test_silenciar_duas_vezes_mantem_o_primeiro_motivo(self):
        banco = BancoFalso()
        silencio.silencia(CLINICA, FONE, "atendimento manual", "ana", banco)
        segundo = silencio.silencia(CLINICA, FONE, "outro motivo", "bia", banco)
        self.assertTrue(segundo["ja_estava"])
        self.assertEqual(segundo["motivo"], "atendimento manual")
        self.assertEqual(segundo["silenciado_por"], "ana")
        # Uma escrita só: a segunda chamada não duplicou linha.
        self.assertEqual([e[0] for e in banco.escritas], ["silencia"])

    def test_reativar_sem_silencio_nao_e_erro(self):
        banco = BancoFalso()
        self.assertFalse(silencio.reativa(CLINICA, FONE, "ana", banco))

    def test_corrida_no_insert_devolve_o_vigente(self):
        """Outra pessoa silenciou entre o detalhe e o insert."""
        banco = BancoFalso()

        original = banco.execute_write_returning

        def insere_depois_de_alguem(sql, params=None):
            banco.vivos[params[1]] = {"motivo": "da outra", "silenciado_por": "bia",
                                      "silenciado_em": "2026-11-08T12:00:00+00:00"}
            return original(sql, params)

        banco.execute_write_returning = insere_depois_de_alguem
        r = silencio.silencia(CLINICA, FONE, "minha", "ana", banco)
        self.assertTrue(r["ja_estava"])
        self.assertEqual(r["motivo"], "da outra")


class TestCicloCompleto(unittest.TestCase):
    def test_silencia_reativa_silencia(self):
        banco = BancoFalso()
        silencio.silencia(CLINICA, FONE, "primeiro", "ana", banco)
        self.assertTrue(silencio.esta_silenciado(CLINICA, FONE, banco))
        self.assertTrue(silencio.reativa(CLINICA, FONE, "bia", banco))
        self.assertFalse(silencio.esta_silenciado(CLINICA, FONE, banco))
        silencio.silencia(CLINICA, FONE, "segundo", "ana", banco)
        self.assertTrue(silencio.esta_silenciado(CLINICA, FONE, banco))
        self.assertEqual([e[0] for e in banco.escritas],
                         ["silencia", "reativa", "silencia"])

    def test_detalhe_traz_quem_quando_e_por_que(self):
        banco = BancoFalso()
        silencio.silencia(CLINICA, FONE, "atendimento manual", "ana", banco)
        d = silencio.detalhe(CLINICA, FONE, banco)
        self.assertEqual(d["motivo"], "atendimento manual")
        self.assertEqual(d["silenciado_por"], "ana")
        self.assertTrue(d["silenciado_em"])

    def test_lista_da_clinica(self):
        banco = BancoFalso()
        silencio.silencia(CLINICA, FONE, "conversa manual", "ana", banco)
        silencio.silencia(CLINICA, "5511888880000", "pediu para parar", "ana", banco)
        self.assertEqual(silencio.silenciados_da_clinica(CLINICA, banco),
                         {FONE, "5511888880000"})


class TestFalhaFechadaParaOSilencio(unittest.TestCase):
    """Banco fora do ar não pode calar o bot de todas as clínicas: o sintoma
    seria invisível, porque ninguém percebe mensagem que não foi enviada."""

    def test_leitura_que_estoura_libera_o_bot(self):
        banco = BancoFalso(estoura=True)
        self.assertFalse(silencio.esta_silenciado(CLINICA, FONE, banco))
        self.assertEqual(silencio.silenciados_da_clinica(CLINICA, banco), set())
        self.assertIsNone(silencio.detalhe(CLINICA, FONE, banco))

    def test_escrita_que_estoura_sobe(self):
        """No gesto humano é o contrário: quem clicou precisa saber que falhou."""
        banco = BancoFalso()
        banco.execute_write_returning = mock.Mock(side_effect=RuntimeError("x"))
        with self.assertRaises(RuntimeError):
            silencio.silencia(CLINICA, FONE, "motivo bom", "ana", banco)

    def test_sem_clinica_ou_telefone_nao_consulta(self):
        banco = mock.Mock()
        self.assertFalse(silencio.esta_silenciado("", FONE, banco))
        self.assertFalse(silencio.esta_silenciado(CLINICA, "", banco))
        banco.execute_query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
