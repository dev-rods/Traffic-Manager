# -*- coding: utf-8 -*-
"""O funcionário alcança o que foi aberto, e nada além.

O risco caro aqui não é o funcionário reclamar que não consegue algo - isso
aparece no mesmo dia. É ele alcançar o relatório financeiro, a configuração da
clínica ou a conversa de WhatsApp sem ninguém perceber, porque esconder o menu
no React não fecha rota nenhuma.

Por isso o padrão é NEGAR: `require_api_key`, que as 76 rotas chamam, recusa
quem não é admin. Esquecer de abrir uma rota tranca o funcionário de fora;
esquecer de fechar uma rota o deixaria dentro. Estes testes travam esse lado.
"""
import os
import unittest
from datetime import date, timedelta
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ["SCHEDULER_API_KEY"] = "chave-mestra-de-teste"

from src.utils.acesso import (
    ADMIN,
    STAFF,
    DIAS_PADRAO_A_FRENTE,
    Identidade,
    janela_da_agenda,
    require_acesso,
)
from src.utils.http import require_api_key
from src.services.visao_do_staff import (
    dentro_da_janela,
    limita_intervalo,
    para_o_staff,
    sem_segredos,
    sem_valores,
)

HOJE = date(2026, 9, 21)

MESTRE = Identidade(papel=ADMIN, chave_mestra=True)
FUNCIONARIA = Identidade(
    papel=STAFF, user_id="u1", clinic_id="essencia", nome="Clara",
    dias_a_frente=14,
)


def evento(token, clinic_id=None):
    e = {"headers": {"x-api-key": token}}
    if clinic_id:
        e["pathParameters"] = {"clinicId": clinic_id}
    return e


def com_identidade(identidade):
    """Troca quem o `identifica` devolve, sem precisar de banco."""
    return mock.patch("src.utils.acesso.identifica", return_value=identidade)


class TestAChaveMestraNaoMudou(unittest.TestCase):
    """A conta que já funciona não pode sentir nada disto."""

    def test_a_chave_mestra_passa_em_rota_de_admin(self):
        chave, erro = require_api_key(evento("chave-mestra-de-teste"))

        self.assertIsNone(erro)
        self.assertEqual(chave, "chave-mestra-de-teste")

    def test_a_chave_mestra_nao_toca_o_banco(self):
        """Todo o tráfego de hoje passa por aqui. Uma consulta a mais por
        request seria custo novo em cima de quem não pediu nada."""
        with mock.patch("src.utils.acesso._sessao") as sessao:
            require_api_key(evento("chave-mestra-de-teste"))

        sessao.assert_not_called()

    def test_admin_alcanca_qualquer_permissao(self):
        with com_identidade(MESTRE):
            identidade, erro = require_acesso(evento("x"), "qualquer.coisa")

        self.assertIsNone(erro)
        self.assertTrue(identidade.e_admin)

    def test_token_invalido_continua_401(self):
        with com_identidade(None):
            _, erro = require_api_key(evento("lixo"))

        self.assertEqual(erro["statusCode"], 401)


class TestONegarEOPadrao(unittest.TestCase):
    def test_funcionaria_e_barrada_em_rota_de_admin(self):
        """Este é o teste que sustenta as 76 rotas de uma vez."""
        with com_identidade(FUNCIONARIA):
            _, erro = require_api_key(evento("token-da-clara"))

        self.assertEqual(erro["statusCode"], 403)

    def test_permissao_fora_da_lista_e_negada(self):
        with com_identidade(FUNCIONARIA):
            _, erro = require_acesso(evento("token-da-clara"), "relatorios.ler")

        self.assertEqual(erro["statusCode"], 403)

    def test_permissao_da_lista_e_liberada(self):
        with com_identidade(FUNCIONARIA):
            identidade, erro = require_acesso(evento("token-da-clara"), "agenda.ler")

        self.assertIsNone(erro)
        self.assertEqual(identidade.papel, STAFF)

    def test_sem_token_e_401_e_nao_403(self):
        with com_identidade(None):
            _, erro = require_acesso(evento(""), "agenda.ler")

        self.assertEqual(erro["statusCode"], 401)


class TestUmaClinicaSo(unittest.TestCase):
    """As três clínicas dividem o mesmo banco: trocar o id na URL não pode
    virar acesso à agenda da vizinha."""

    def test_a_propria_clinica_passa(self):
        with com_identidade(FUNCIONARIA):
            _, erro = require_acesso(evento("t", "essencia"), "agenda.ler")

        self.assertIsNone(erro)

    def test_a_clinica_da_vizinha_e_barrada(self):
        with com_identidade(FUNCIONARIA):
            _, erro = require_acesso(evento("t", "nobre-laser"), "agenda.ler")

        self.assertEqual(erro["statusCode"], 403)

    def test_admin_alcanca_qualquer_clinica(self):
        with com_identidade(MESTRE):
            _, erro = require_acesso(evento("t", "nobre-laser"), "agenda.ler")

        self.assertIsNone(erro)


class TestAJanelaDaAgenda(unittest.TestCase):
    def test_comeca_hoje_e_nao_no_passado(self):
        inicio, _ = janela_da_agenda(FUNCIONARIA, HOJE)

        self.assertEqual(inicio, HOJE)

    def test_dias_a_frente_definem_o_fim(self):
        _, fim = janela_da_agenda(FUNCIONARIA, HOJE)

        self.assertEqual(fim, HOJE + timedelta(days=14))

    def test_o_mais_restritivo_vence(self):
        """Com os dois controles ligados, travar numa data não pode ser
        afrouxado pelo contador de dias."""
        os_dois = Identidade(papel=STAFF, dias_a_frente=30,
                             visivel_ate=date(2026, 9, 25))

        _, fim = janela_da_agenda(os_dois, HOJE)

        self.assertEqual(fim, date(2026, 9, 25))

    def test_a_data_tambem_pode_ser_a_mais_larga_e_perder(self):
        os_dois = Identidade(papel=STAFF, dias_a_frente=3,
                             visivel_ate=date(2026, 12, 31))

        _, fim = janela_da_agenda(os_dois, HOJE)

        self.assertEqual(fim, HOJE + timedelta(days=3))

    def test_sem_configuracao_cai_num_padrao_conservador(self):
        """Nem trancar a pessoa fora da agenda, nem liberar o calendário
        inteiro por esquecimento."""
        nova = Identidade(papel=STAFF)

        _, fim = janela_da_agenda(nova, HOJE)

        self.assertEqual(fim, HOJE + timedelta(days=DIAS_PADRAO_A_FRENTE))

    def test_admin_nao_tem_janela(self):
        self.assertTrue(dentro_da_janela(MESTRE, "2020-01-01"))
        self.assertTrue(dentro_da_janela(MESTRE, "2099-01-01"))


class TestOQueCabeNaJanela(unittest.TestCase):
    def setUp(self):
        self.patcher = mock.patch(
            "src.utils.acesso.janela_da_agenda",
            return_value=(HOJE, HOJE + timedelta(days=14)),
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_ontem_fica_de_fora(self):
        self.assertFalse(dentro_da_janela(FUNCIONARIA, "2026-09-20"))

    def test_hoje_entra(self):
        self.assertTrue(dentro_da_janela(FUNCIONARIA, "2026-09-21"))

    def test_depois_do_fim_fica_de_fora(self):
        self.assertFalse(dentro_da_janela(FUNCIONARIA, "2026-10-06"))

    def test_data_ilegivel_e_negada(self):
        """Não conseguir ler o pedido não pode significar liberar."""
        for lixo in ("", None, "amanha", "31/12/2026", "2026-13-45"):
            self.assertFalse(dentro_da_janela(FUNCIONARIA, lixo), repr(lixo))

    def test_o_intervalo_pedido_e_apertado_ate_caber(self):
        de, ate = limita_intervalo(FUNCIONARIA, "2026-01-01", "2026-12-31")

        self.assertEqual(de, "2026-09-21")
        self.assertEqual(ate, "2026-10-05")

    def test_intervalo_inteiramente_no_passado_vira_vazio(self):
        de, ate = limita_intervalo(FUNCIONARIA, "2026-01-01", "2026-02-01")

        self.assertGreater(de, ate, "de > ate devolve lista vazia, que é honesto")

    def test_intervalo_do_admin_nao_e_tocado(self):
        de, ate = limita_intervalo(MESTRE, "2020-01-01", "2099-12-31")

        self.assertEqual((de, ate), ("2020-01-01", "2099-12-31"))


class TestNenhumValorEmReais(unittest.TestCase):
    def test_o_preco_do_agendamento_sai(self):
        limpo = sem_valores({
            "id": "a1", "patient_name": "Ana",
            "original_price_cents": 19500, "final_price_cents": 17550,
            "discount_pct": 10,
        })

        self.assertEqual(set(limpo), {"id", "patient_name"})

    def test_sai_tambem_dentro_de_lista_aninhada(self):
        """A resposta de agendamentos é uma lista dentro de um dicionário.
        Tratar só o primeiro nível deixaria o valor passar no segundo."""
        limpo = sem_valores({
            "appointments": [
                {"id": "a1", "final_price_cents": 100},
                {"id": "a2", "final_price_cents": 200},
            ]
        })

        for item in limpo["appointments"]:
            self.assertNotIn("final_price_cents", item)

    def test_preco_de_servico_e_desconto_do_paciente_saem(self):
        limpo = sem_valores({
            "services": [{"name": "Laser", "price_cents": 19500}],
            "patient": {"name": "Ana", "custom_discount_pct": 15},
        })

        self.assertNotIn("price_cents", limpo["services"][0])
        self.assertNotIn("custom_discount_pct", limpo["patient"])

    def test_o_que_nao_e_dinheiro_fica(self):
        """`discount_reason` pinta a caixa de parceria na agenda e não revela
        valor nenhum. Levar junto quebraria a tela sem ganho."""
        limpo = sem_valores({
            "discount_reason": "partnership",
            "duration_minutes": 15,
            "areas": "Axilas",
        })

        self.assertEqual(set(limpo), {"discount_reason", "duration_minutes", "areas"})

    def test_o_admin_continua_vendo_tudo(self):
        dado = {"final_price_cents": 19500}

        self.assertEqual(para_o_staff(MESTRE, dado), dado)

    def test_a_funcionaria_nao(self):
        self.assertEqual(para_o_staff(FUNCIONARIA, {"final_price_cents": 1}), {})


class TestSegredosDaClinica(unittest.TestCase):
    def test_credencial_do_whatsapp_nao_sai(self):
        limpo = sem_segredos({
            "clinic_id": "essencia", "name": "Essência",
            "zapi_instance_id": "i", "zapi_instance_token": "t",
            "business_hours": {"mon": "9-18"},
        })

        self.assertEqual(set(limpo), {"clinic_id", "name", "business_hours"})


class TestHojeEODaClinicaENaoODaAWS(unittest.TestCase):
    """Bug pego em 20/09/2026, conferindo a janela contra dados reais.

    A Lambda roda em UTC. As 21h de Sao Paulo ja sao o dia seguinte em UTC,
    entao `date.today()` cru empurrava a janela um dia para a frente e tirava da
    funcionaria a agenda DE HOJE bem no fim do expediente - que e exatamente
    quando ela vai registrar a sessao que acabou de fazer.
    """

    def test_as_21h_de_sao_paulo_ainda_e_hoje(self):
        from datetime import datetime
        import pytz

        from src.utils.acesso import hoje_na_clinica

        # 21/09 23:30 em Sao Paulo ja e 22/09 02:30 em UTC.
        sp = pytz.timezone("America/Sao_Paulo")
        momento = sp.localize(datetime(2026, 9, 21, 23, 30))

        self.assertEqual(momento.astimezone(pytz.utc).date(), date(2026, 9, 22))
        self.assertEqual(momento.date(), date(2026, 9, 21),
                         "para quem esta na clinica, ainda e dia 21")

        with mock.patch("src.utils.acesso.datetime") as dt:
            dt.now.return_value = momento
            self.assertEqual(hoje_na_clinica("America/Sao_Paulo"), date(2026, 9, 21))

    def test_a_janela_usa_o_fuso_da_identidade(self):
        from src.utils.acesso import hoje_na_clinica

        com_fuso = Identidade(papel=STAFF, dias_a_frente=3, fuso="America/Sao_Paulo")

        with mock.patch("src.utils.acesso.hoje_na_clinica",
                        return_value=date(2026, 9, 21)) as h:
            inicio, fim = janela_da_agenda(com_fuso)

        h.assert_called_once_with("America/Sao_Paulo")
        self.assertEqual(inicio, date(2026, 9, 21))
        self.assertEqual(fim, date(2026, 9, 24))
        self.assertTrue(callable(hoje_na_clinica))

    def test_fuso_invalido_cai_no_padrao_em_vez_de_explodir(self):
        from src.utils.acesso import hoje_na_clinica

        self.assertIsInstance(hoje_na_clinica("Marte/Olympus"), date)

    def test_o_padrao_e_sao_paulo(self):
        from src.utils.acesso import FUSO_PADRAO

        self.assertEqual(FUSO_PADRAO, "America/Sao_Paulo")
        self.assertEqual(Identidade(papel=STAFF).fuso, "America/Sao_Paulo")


class TestOsDoisInterruptores(unittest.TestCase):
    """Decisao do Andre em 21/09/2026: nem toda recepcao e igual.

    Quem cobra no balcao precisa do valor; quem so agenda nao precisa. E a
    clinica que nao quer a base inteira de pacientes a mao de quem atende
    tambem tem como fechar isso, sem tirar dela o prontuario.
    """

    def setUp(self):
        self.ve_preco = Identidade(papel=STAFF, clinic_id="essencia",
                                   ve_precos=True)
        self.nao_ve = Identidade(papel=STAFF, clinic_id="essencia",
                                 ve_precos=False)

    def test_com_o_interruptor_ligado_o_preco_passa(self):
        dado = {"final_price_cents": 19500}

        self.assertEqual(para_o_staff(self.ve_preco, dado), dado)

    def test_desligado_o_preco_sai(self):
        self.assertEqual(para_o_staff(self.nao_ve, {"final_price_cents": 1}), {})

    def test_o_admin_nao_depende_do_interruptor(self):
        admin_sem = Identidade(papel=ADMIN, chave_mestra=True, ve_precos=False)

        self.assertTrue(admin_sem.mostra_valores)

    def test_o_padrao_e_nao_mostrar_valor(self):
        """Ligar a coluna nao pode revelar preco para quem ja existia."""
        self.assertFalse(Identidade(papel=STAFF).ve_precos)

    def test_sem_a_lista_a_permissao_de_ler_pacientes_cai(self):
        sem_lista = Identidade(papel=STAFF, ve_lista_de_pacientes=False)

        self.assertFalse(sem_lista.pode("pacientes.ler"))

    def test_mas_o_prontuario_e_o_agendamento_ficam(self):
        """Ela chega ao prontuario pelo atalho da agenda, e cadastra paciente
        pelo telefone. Fechar esses junto trancaria a recepcao fora do proprio
        trabalho."""
        sem_lista = Identidade(papel=STAFF, ve_lista_de_pacientes=False)

        for permissao in ("prontuario.ler", "prontuario.escrever",
                          "pacientes.escrever", "agenda.ler", "agenda.escrever"):
            with self.subTest(permissao):
                self.assertTrue(sem_lista.pode(permissao))

    def test_o_padrao_e_ver_a_lista(self):
        """Era o comportamento no ar antes do interruptor existir."""
        self.assertTrue(Identidade(papel=STAFF).ve_lista_de_pacientes)

    def test_o_admin_ve_a_lista_mesmo_com_o_interruptor_desligado(self):
        admin_sem = Identidade(papel=ADMIN, ve_lista_de_pacientes=False)

        self.assertTrue(admin_sem.pode("pacientes.ler"))


if __name__ == "__main__":
    unittest.main()
