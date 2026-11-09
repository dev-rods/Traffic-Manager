# -*- coding: utf-8 -*-
"""O endereço de uma clínica não entra no texto de outra.

Em 09/11/2026 uma lead da Nobre Laser (São José dos Campos) recebeu o endereço
da Essência (Rua Augusta, São Paulo) na mensagem que fechou o agendamento,
porque o prompt da Nobre era cópia do da Essência com o endereço escrito à mão.
"""
import unittest

from src.services.endereco_alheio import (
    endereco_alheio,
    menciona,
    nucleo,
    recusa_endereco_alheio,
)
from src.scripts.corrige_endereco_no_prompt import (
    APLICADO,
    BLOCO_AUSENTE,
    JA_CORRIGIDO,
    NOVO,
    VELHO,
    aplica,
)

ESSENCIA = "clinicaessenciaestetica-9668a4"
NOBRE = "nobrelaser-sjc"
ENDERECOS = {
    ESSENCIA: "Rua Augusta, 2709, Conj. 26 (2º andar), Cerqueira César, São Paulo-SP",
    NOBRE: "Rua Armando de Oliveira Cobra, 50, sala 416 - Ed. New Worker Tower",
    "clinicadorods-da7b62": "",
}

# O texto que foi realmente para a paciente em 09/11/2026.
BLOCO_REAL = """Sempre que finalizar um agendamento, passe o endereço completo:

Rua Augusta, 2709
Conj. 26 - CLÍNICA ESSÊNCIA (2º andar)"""


class TestNucleo(unittest.TestCase):
    def test_logradouro_e_numero(self):
        self.assertEqual(nucleo("Rua Augusta, 2709, Conj. 26"), ("augusta", "2709"))

    def test_aceita_avenida_abreviada(self):
        self.assertEqual(nucleo("Av. Paulista, 1000 - Bela Vista"), ("paulista", "1000"))

    def test_endereco_sem_numero_nao_tem_nucleo(self):
        """Sem o par logradouro+número não há como afirmar que é o mesmo lugar -
        e acusar por nome de rua pararia cadastro legítimo."""
        self.assertIsNone(nucleo("Rua Augusta"))
        self.assertIsNone(nucleo(""))


class TestMenciona(unittest.TestCase):
    def test_pega_o_endereco_reescrito_em_outra_ordem(self):
        """O bloco copiado não repetia o cadastro: quebrava em linhas e trocava
        a pontuação. É esse formato que tem de ser reconhecido."""
        self.assertTrue(menciona(BLOCO_REAL, ENDERECOS[ESSENCIA]))

    def test_pega_mesmo_sem_acento_e_em_caixa_alta(self):
        self.assertTrue(menciona("RUA AUGUSTA 2709", ENDERECOS[ESSENCIA]))

    def test_nao_confunde_rua_igual_com_numero_diferente(self):
        self.assertFalse(menciona("Rua Augusta, 101", ENDERECOS[ESSENCIA]))

    def test_texto_sem_endereco_nenhum(self):
        self.assertFalse(menciona("Passe o endereço: {{clinic_address}}",
                                  ENDERECOS[ESSENCIA]))


class TestEnderecoAlheio(unittest.TestCase):
    def test_o_caso_real_da_nobre(self):
        self.assertEqual(endereco_alheio(BLOCO_REAL, NOBRE, ENDERECOS),
                         (ESSENCIA, ENDERECOS[ESSENCIA]))

    def test_a_propria_clinica_pode_citar_o_proprio_endereco(self):
        """Senão a Essência não conseguiria mais salvar o texto dela."""
        self.assertIsNone(endereco_alheio(BLOCO_REAL, ESSENCIA, ENDERECOS))

    def test_variavel_nao_acusa(self):
        self.assertIsNone(endereco_alheio(
            "passe o endereço: {{clinic_address}}", NOBRE, ENDERECOS))

    def test_clinica_sem_endereco_cadastrado_nao_acusa(self):
        self.assertIsNone(endereco_alheio("qualquer texto", NOBRE, ENDERECOS))

    def test_sem_lista_de_enderecos_nao_inventa_suspeita(self):
        self.assertIsNone(endereco_alheio(BLOCO_REAL, NOBRE, None))


class DbFalso:
    def __init__(self, enderecos=None, erro=False):
        self.enderecos = enderecos if enderecos is not None else ENDERECOS
        self.erro = erro

    def execute_query(self, sql, params=None):
        if self.erro:
            raise RuntimeError("banco indisponivel")
        return [{"clinic_id": c, "address": e} for c, e in self.enderecos.items() if e]


class TestRecusa(unittest.TestCase):
    def test_recusa_nomeia_a_dona_do_endereco(self):
        msg = recusa_endereco_alheio(DbFalso(), NOBRE, BLOCO_REAL)
        self.assertIn(ESSENCIA, msg)
        # Com as chaves que a pessoa precisa digitar. Conferir só por
        # "clinic_address" deixou passar um "{clinic_address}" de uma chave,
        # que é nome de variável que o template não reconhece.
        self.assertIn("{{clinic_address}}", msg)

    def test_texto_limpo_passa(self):
        self.assertIsNone(recusa_endereco_alheio(
            DbFalso(), NOBRE, "endereço: {{clinic_address}}"))

    def test_banco_fora_nao_bloqueia_a_escrita(self):
        """Falha aberta: barrar todo cadastro de template porque o banco piscou
        é pior do que a cópia, que a auditoria pega depois."""
        self.assertIsNone(recusa_endereco_alheio(DbFalso(erro=True), NOBRE, BLOCO_REAL))


class TestCorrecaoDoPrompt(unittest.TestCase):
    def test_troca_o_bloco_literal_pela_variavel(self):
        novo, status = aplica("cabeçalho\n\n" + VELHO + "\n\nrodapé")
        self.assertEqual(status, APLICADO)
        self.assertIn("{{clinic_address}}", novo)
        self.assertNotIn("Rua Augusta", novo)
        self.assertIn("cabeçalho", novo)
        self.assertIn("rodapé", novo)

    def test_idempotente(self):
        uma_vez, _ = aplica(VELHO)
        duas_vezes, status = aplica(uma_vez)
        self.assertEqual(status, JA_CORRIGIDO)
        self.assertEqual(uma_vez, duas_vezes)

    def test_prompt_editado_a_mao_e_recusado_em_vez_de_sobrescrito(self):
        texto = "Sempre que finalizar, passe o endereço: Rua Outra, 12"
        novo, status = aplica(texto)
        self.assertEqual(status, BLOCO_AUSENTE)
        self.assertEqual(novo, texto)

    def test_o_texto_novo_nao_carrega_endereco_de_ninguem(self):
        """A guarda tem de aprovar a própria correção - senão o script
        gravaria algo que a escrita recusaria depois."""
        self.assertIsNone(endereco_alheio(NOVO, NOBRE, ENDERECOS))
        self.assertIsNone(nucleo(NOVO))


if __name__ == "__main__":
    unittest.main()
