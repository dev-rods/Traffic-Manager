# -*- coding: utf-8 -*-
"""O prontuário não escreve no comercial (PRD 052).

Desmembrar áreas, renomear partes e trazer Grandes lábios acontece SÓ no
registro técnico. `appointments` e `appointment_service_areas` são do
agendamento: áreas vendidas, preço, desconto. Se um módulo do prontuário
passasse a escrever ali, o relatório financeiro mudaria por causa de uma
conduta clínica.
"""
import os
import re
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")

PRONTUARIO = [
    os.path.join("services", "historico_de_sessao.py"),
    os.path.join("services", "protocolo_laser.py"),
] + [
    os.path.join("functions", "patient_record", nome)
    for nome in sorted(os.listdir(os.path.join(SRC, "functions", "patient_record")))
    if nome.endswith(".py")
]

ESCRITA_NO_COMERCIAL = re.compile(
    r"\b(UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+scheduler\.(appointments|appointment_service_areas)\b",
    re.IGNORECASE,
)


def _fonte(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
        return f.read()


class TestGuarda(unittest.TestCase):
    def test_nenhum_modulo_do_prontuario_escreve_no_comercial(self):
        culpados = [rel for rel in PRONTUARIO if ESCRITA_NO_COMERCIAL.search(_fonte(rel))]
        self.assertEqual(culpados, [])

    def test_a_guarda_enxerga_escrita_de_verdade(self):
        """Prova positiva: o serviço de agendamento escreve nessas tabelas, e o
        regex tem de achar. Sem isto a guarda poderia ser um check que nunca
        falha."""
        self.assertTrue(ESCRITA_NO_COMERCIAL.search(
            _fonte(os.path.join("services", "appointment_service.py"))))

    def test_os_modulos_listados_existem(self):
        self.assertGreaterEqual(len(PRONTUARIO), 8)
        for rel in PRONTUARIO:
            self.assertTrue(os.path.exists(os.path.join(SRC, rel)), rel)


if __name__ == "__main__":
    unittest.main()
