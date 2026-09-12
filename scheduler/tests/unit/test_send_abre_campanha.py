# -*- coding: utf-8 -*-
"""O disparo abre a campanha - e só o disparo.

`/send` é o mesmo endpoint que a atendente usa para responder à mão. Se abrir
campanha em toda mensagem, o bot passa a falar por cima dela. Por isso o campo é
opcional e nada acontece sem ele.

A ordem também é regra, não acaso: a campanha só abre DEPOIS de a mensagem sair.
Invertida, uma falha de entrega deixa o bot esperando resposta de algo que
ninguém recebeu.
"""
import json
import unittest
from unittest import mock

from src.services.campanha import MAX_DATAS, MODO_REAGENDAMENTO

CLINIC = "clinicaessenciaestetica-9668a4"
FONE = "5511970522647"
DATAS = ["2026-10-07", "2026-10-14", "2026-10-21"]


def dispara(corpo, envio_ok=True, gravacao_ok=True, use_agent=True):
    """Roda o handler de verdade. Devolve (resposta, chamadas_de_abertura)."""
    from src.functions.send import handler as modulo

    evento = {"headers": {"x-api-key": "k"}, "body": json.dumps(corpo)}

    envio = mock.MagicMock()
    envio.success = envio_ok
    envio.provider_message_id = "pmid-1"
    envio.raw_response = {}
    provider = mock.MagicMock()
    provider.send_text.return_value = envio

    db = mock.MagicMock()
    db.execute_query.return_value = [
        {"clinic_id": CLINIC, "name": "Essencia", "use_agent": use_agent}]

    with mock.patch.object(modulo, "require_api_key", return_value=("k", None)), \
         mock.patch.object(modulo, "PostgresService", return_value=db), \
         mock.patch.object(modulo, "get_provider", return_value=provider), \
         mock.patch.object(modulo, "MessageTracker"), \
         mock.patch.object(modulo, "_tabela_de_sessoes"), \
         mock.patch.object(modulo, "abre_campanha",
                           return_value=gravacao_ok) as abertura:
        resposta = modulo.handler(evento, None)

    return resposta, abertura


BASE = {"clinicId": CLINIC, "phone": FONE, "type": "text", "content": "Datas abertas!"}


class TestSemCampanha(unittest.TestCase):
    """O comportamento de hoje não pode mudar em nada."""

    def test_mensagem_manual_nao_encosta_na_sessao(self):
        resposta, abertura = dispara(dict(BASE))

        self.assertEqual(resposta["statusCode"], 200)
        abertura.assert_not_called()

    def test_resposta_nao_ganha_campo_novo(self):
        resposta, _ = dispara(dict(BASE))
        self.assertNotIn("campanhaAberta", json.loads(resposta["body"]))


class TestComCampanha(unittest.TestCase):
    def test_abre_com_as_datas_e_o_modo(self):
        _, abertura = dispara({**BASE, "campanha": {"datas": DATAS}})

        abertura.assert_called_once()
        campanha = abertura.call_args[0][3]
        self.assertEqual(campanha["modo"], MODO_REAGENDAMENTO)
        self.assertEqual(campanha["datas"], DATAS)
        self.assertIn("expira_em", campanha)

    def test_abre_para_o_telefone_certo(self):
        _, abertura = dispara({**BASE, "campanha": {"datas": DATAS}})
        self.assertEqual(abertura.call_args[0][2], FONE)

    def test_reporta_que_abriu(self):
        resposta, _ = dispara({**BASE, "campanha": {"datas": DATAS}})
        self.assertIs(json.loads(resposta["body"])["campanhaAberta"], True)

    def test_falha_ao_gravar_nao_derruba_o_envio_mas_aparece(self):
        """A mensagem já saiu - não dá para desfazer. Mas a paciente recebeu as
        datas e o bot não vai responder, então alguém precisa saber."""
        resposta, _ = dispara({**BASE, "campanha": {"datas": DATAS}}, gravacao_ok=False)

        self.assertEqual(resposta["statusCode"], 200)
        self.assertIs(json.loads(resposta["body"])["campanhaAberta"], False)


class TestOrdem(unittest.TestCase):
    def test_envio_falhou_nao_abre_campanha(self):
        """Campanha aberta sem mensagem entregue deixa o bot esperando no vazio."""
        resposta, abertura = dispara({**BASE, "campanha": {"datas": DATAS}},
                                     envio_ok=False)

        abertura.assert_not_called()
        self.assertNotEqual(resposta["statusCode"], 200)


class TestExigeOAgente(unittest.TestCase):
    def test_clinica_na_engine_antiga_nao_abre_campanha(self):
        """O bloco de modo só existe no ConversationAgent. Na engine antiga a
        paciente receberia o fluxo de lead: boas-vindas e pedido de CPF."""
        resposta, abertura = dispara({**BASE, "campanha": {"datas": DATAS}},
                                     use_agent=False)

        self.assertEqual(resposta["statusCode"], 400)
        abertura.assert_not_called()

    def test_mensagem_manual_segue_funcionando_na_engine_antiga(self):
        resposta, _ = dispara(dict(BASE), use_agent=False)
        self.assertEqual(resposta["statusCode"], 200)


class TestValidacao(unittest.TestCase):
    def test_campanha_sem_datas_e_400(self):
        for ruim in ({"datas": []}, {}, "sim", {"dias": 7}):
            with self.subTest(ruim=ruim):
                resposta, abertura = dispara({**BASE, "campanha": ruim})
                self.assertEqual(resposta["statusCode"], 400)
                abertura.assert_not_called()

    def test_datas_demais_e_400(self):
        muitas = DATAS + ["2026-10-28"]
        resposta, abertura = dispara({**BASE, "campanha": {"datas": muitas}})

        self.assertEqual(resposta["statusCode"], 400)
        self.assertGreater(len(muitas), MAX_DATAS)
        abertura.assert_not_called()

    def test_validacao_acontece_antes_do_envio(self):
        """400 por campanha inválida não pode ter mandado mensagem antes."""
        from src.functions.send import handler as modulo

        evento = {"headers": {"x-api-key": "k"},
                  "body": json.dumps({**BASE, "campanha": {"datas": []}})}
        provider = mock.MagicMock()

        with mock.patch.object(modulo, "require_api_key", return_value=("k", None)), \
             mock.patch.object(modulo, "PostgresService"), \
             mock.patch.object(modulo, "get_provider", return_value=provider), \
             mock.patch.object(modulo, "MessageTracker"):
            modulo.handler(evento, None)

        provider.send_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
