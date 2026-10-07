# -*- coding: utf-8 -*-
"""A listagem devolve todo campo que a tela lê.

Em 09/09/2026 a atendente marcava "Primeira vez", salvava, reabria e via
desmarcado. O PUT gravava certo - o banco tinha `is_first_visit = true`. O
SELECT da listagem é que não trazia a coluna, então o campo chegava ausente ao
frontend e a caixinha nascia vazia toda vez.

Coluna nova entra em três lugares: banco, escritor e leitor. Esquecer o leitor
não quebra nada - só faz a tela mentir.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LISTAGEM = RAIZ / "src" / "functions" / "appointment" / "list.py"
TIPOS = RAIZ.parent / "frontend" / "src" / "types" / "index.ts"

# Campos do tipo `Appointment` do frontend que a listagem NÃO precisa trazer,
# porque a tela os deriva ou eles vêm de outro endpoint.
DERIVADOS = {"areas", "area_ids", "duration_minutes", "patient_name"}


def campos_que_a_tela_espera():
    texto = TIPOS.read_text(encoding="utf-8")
    inicio = texto.index("export interface Appointment {")
    corpo = texto[inicio:texto.index("}", inicio)]
    # `nome: tipo` no começo da linha, ignorando comentários.
    return {
        m.group(1) for m in re.finditer(r"^\s{2}(\w+)\??:", corpo, re.M)
    } - DERIVADOS


class TestContratoDaListagem(unittest.TestCase):
    def test_a_query_traz_todo_campo_que_a_tela_le(self):
        sql = LISTAGEM.read_text(encoding="utf-8")
        esperados = campos_que_a_tela_espera()

        self.assertGreater(len(esperados), 8, "o leitor do tipo parou de achar campo")

        for campo in sorted(esperados):
            with self.subTest(campo=campo):
                self.assertIn(
                    campo, sql,
                    f"o frontend lê `{campo}` e a listagem não devolve. "
                    f"Em producao isso e a tela mostrando vazio sem erro nenhum.",
                )

    def test_primeira_visita_esta_na_query(self):
        """Prende o caso que originou este teste, por nome."""
        self.assertIn("is_first_visit", LISTAGEM.read_text(encoding="utf-8"))

    def test_o_leitor_do_tipo_acha_o_bloco_certo(self):
        """Se o parser parasse de achar a interface, o teste acima passaria
        vazio - o modo de falha que ja apareceu varias vezes aqui."""
        campos = campos_que_a_tela_espera()

        self.assertIn("is_first_visit", campos)
        self.assertIn("start_time", campos)
        self.assertNotIn("areas", campos)


if __name__ == "__main__":
    unittest.main()
