# -*- coding: utf-8 -*-
"""O bot sabe quem está falando, e não pede o que o banco já tem.

Em 05/10/2026 a Yasmin, cadastrada com nome, nascimento, CPF e e-mail, recebeu
"Para finalizar o cadastro, me envia: Nome completo, Data de nascimento, CPF,
E-mail" logo depois de marcar. Nenhuma tool identificava a pessoa, e o contrato
de book_appointment exigia nome sempre.

Três camadas, testadas em ordem:
  1. identificar()           o que o modelo recebe sobre a pessoa
  2. sem_passo_de_cadastro() o prompt sem o roteiro que pede cadastro
  3. o agente                a trava que recusa pedir mesmo assim (test_cadastro_pelo_bot)
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.identificacao_de_paciente import (
    a_partir_das_linhas,
    cadastro_completo,
    identificar,
    sem_passo_de_cadastro,
)

CLINIC = "clinicaessenciaestetica-9668a4"
PHONE = "5511984048030"

# A linha como o banco devolve para a Yasmin (dados reais, menos os sensíveis).
YASMIN = {
    "id": "1ce44d35-47b9-402e-a5e3-aee5f447689d",
    "name": "Yasmin Alves de Souza Lopes",
    "birth_date": "1999-01-01", "cpf": "00000000000", "email": "y@x.com",
    "sessoes_feitas": 0, "ultima_sessao": None,
    "agendamento_futuro": {"id": "ap1", "data": "2026-10-09", "hora": "14:00"},
}


class TestCadastroCompleto(unittest.TestCase):
    def test_os_quatro_preenchidos(self):
        self.assertTrue(cadastro_completo(YASMIN))

    def test_falta_um_e_incompleto(self):
        for campo in ("name", "birth_date", "cpf", "email"):
            with self.subTest(campo=campo):
                self.assertFalse(cadastro_completo({**YASMIN, campo: None}))
                self.assertFalse(cadastro_completo({**YASMIN, campo: "  "}))

    def test_vazio(self):
        self.assertFalse(cadastro_completo({}))
        self.assertFalse(cadastro_completo(None))


class TestOQueOModeloRecebe(unittest.TestCase):
    def test_yasmin_e_cadastrada_mesmo_sem_sessao_feita(self):
        """O gatilho do bug é o cadastro, não o histórico: ela tinha zero
        sessões feitas e mesmo assim não devia ouvir pedido de CPF."""
        r = a_partir_das_linhas([YASMIN], PHONE)
        self.assertTrue(r["encontrado"])
        self.assertTrue(r["cadastro_completo"])
        self.assertEqual(r["nome"], "Yasmin Alves de Souza Lopes")
        self.assertEqual(r["sessoes_feitas"], 0)
        self.assertEqual(r["agendamento_futuro"]["data"], "2026-10-09")

    def test_nao_vaza_os_dados_sensiveis(self):
        """Saber que existe, sim. Ver o valor, não."""
        r = a_partir_das_linhas([YASMIN], PHONE)
        for campo in ("cpf", "email", "birth_date", "areas", "areas_tratadas"):
            self.assertNotIn(campo, r)

    def test_desconhecida(self):
        self.assertEqual(a_partir_das_linhas([], PHONE), {"encontrado": False})

    def test_dois_pacientes_no_mesmo_numero_nao_identifica(self):
        """Mãe e filha num celular: identificar automaticamente agendaria em
        nome da pessoa errada, e a trava de cadastro impediria perguntar."""
        r = a_partir_das_linhas([YASMIN, {**YASMIN, "id": "x", "name": "Ana"}], PHONE)
        self.assertFalse(r["encontrado"])
        self.assertTrue(r["ambiguo"])
        self.assertEqual(r["candidatos"], ["Yasmin Alves de Souza Lopes", "Ana"])
        self.assertIn("nome completo", r["o_que_fazer"])


class TestConsulta(unittest.TestCase):
    def test_casa_pelas_variantes_do_numero(self):
        """WhatsApp com 12 dígitos e cadastro com 13 são a mesma pessoa."""
        db = mock.MagicMock()
        db.execute_query.return_value = [YASMIN]

        r = identificar(db, CLINIC, "554797053940")

        sql, params = db.execute_query.call_args[0]
        self.assertIn("= ANY(%s)", sql)
        self.assertIn("deleted_at IS NULL", sql)
        self.assertEqual(params[0], CLINIC)
        self.assertEqual(set(params[1]), {"554797053940", "5547997053940"})
        self.assertTrue(r["encontrado"])

    def test_falha_no_banco_e_lead_desconhecida(self):
        """Nunca levanta: sem identificação, o fluxo é o de antes."""
        db = mock.MagicMock()
        db.execute_query.side_effect = RuntimeError("down")
        self.assertEqual(identificar(db, CLINIC, PHONE), {"encontrado": False})


# O roteiro como está no template da Essência (AI_SYSTEM_PROMPT, 05/10/2026),
# só a seção que importa e as vizinhas.
H = chr(0x2550) * 3
PROMPT_REAL = (
    f"{H} DE ONDE VÊM OS FATOS {H}\n"
    "Nunca afirme data sem tool.\n\n"
    f"{H} COMO CONDUZIR A CONVERSA {H}\n"
    "1. BOAS-VINDAS\n   Cumprimente.\n\n"
    "5. CONFIRMAÇÃO\n"
    "   Resuma em uma mensagem curta: áreas, data, horário e valor total. Pergunte \"Confirmo?\"\n\n"
    "6. CADASTRO\n"
    "   Depois que a pessoa confirmar o agendamento, peça os dados de cadastro numa única mensagem, em lista:\n\n"
    "   \"Perfeito! Para finalizar o cadastro, me envia:\n"
    "   Nome completo:\n"
    "   Data de nascimento:\n"
    "   CPF:\n"
    "   E-mail:\"\n\n"
    "   O telefone você já tem, é o número da conversa. Não peça de novo.\n"
    "   Se a data de nascimento indicar menor de 18 anos, não conclua o agendamento: transfira para uma especialista imediatamente.\n\n"
    "7. APÓS AGENDAR\n"
    "   Só chame book_appointment depois de ter os dados de cadastro. Passe full_name, birth_date (YYYY-MM-DD), cpf e email para a tool - sem isso o cadastro fica incompleto no sistema da clínica.\n"
    "   Depois chame get_pre_session_instructions e envie as orientações de cuidado.\n\n"
    f"{H} COMO LIDAR COM OBJEÇÃO {H}\n"
    "Acolha o receio numa linha.\n"
)


class TestPromptSemOPassoDeCadastro(unittest.TestCase):
    def setUp(self):
        self.prompt = sem_passo_de_cadastro(PROMPT_REAL, "Yasmin Alves de Souza Lopes")

    def test_o_texto_pronto_sai(self):
        """Retirado, não contradito: o que não está no prompt não é reproduzido."""
        self.assertNotIn("Para finalizar o cadastro", self.prompt)
        self.assertNotIn("Nome completo:", self.prompt)
        self.assertNotIn("dados de cadastro", self.prompt)
        self.assertNotIn("Passe full_name, birth_date", self.prompt)

    def test_o_passo_diz_que_ela_e_cadastrada_e_leva_o_nome(self):
        self.assertIn("6. CADASTRO", self.prompt)
        self.assertIn("JÁ É PACIENTE CADASTRADA (nome: Yasmin Alves de Souza Lopes)", self.prompt)
        self.assertIn("NÃO peça nenhum desses dados", self.prompt)

    def test_o_resto_do_roteiro_fica(self):
        for trecho in ("5. CONFIRMAÇÃO", "7. APÓS AGENDAR", "get_pre_session_instructions",
                       "COMO LIDAR COM OBJEÇÃO", "DE ONDE VÊM OS FATOS", "Nunca afirme data sem tool."):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, self.prompt)

    def test_nao_toca_fora_da_secao(self):
        """A frase "dados de cadastro" em outra seção não é desta regra."""
        prompt = PROMPT_REAL + f"\n{H} OUTRA {H}\nGuarde os dados de cadastro com cuidado.\n"
        saida = sem_passo_de_cadastro(prompt, "X")
        self.assertIn("Guarde os dados de cadastro com cuidado.", saida)

    def test_sem_nome_nao_inventa_parenteses(self):
        saida = sem_passo_de_cadastro(PROMPT_REAL, "")
        self.assertIn("JÁ É PACIENTE CADASTRADA. A clínica", saida)

    def test_template_sem_o_passo_volta_como_veio(self):
        """Clínica que editou o template: a trava de saída continua valendo."""
        prompt = f"{H} COMO CONDUZIR A CONVERSA {H}\n1. BOAS-VINDAS\n   Oi.\n"
        self.assertEqual(sem_passo_de_cadastro(prompt, "X"), prompt)
        self.assertEqual(sem_passo_de_cadastro("", "X"), "")
        self.assertEqual(sem_passo_de_cadastro("sem seção nenhuma", "X"), "sem seção nenhuma")


if __name__ == "__main__":
    unittest.main()
