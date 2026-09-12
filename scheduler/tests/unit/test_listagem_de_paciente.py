# -*- coding: utf-8 -*-
"""A listagem de pacientes devolve todo campo que a tela le.

Mesmo defeito que ja custou o `is_first_visit` em 09/09/2026, e aqui era pior:
a listagem nao trazia cpf, birth_date nem email, e o modal de edicao le
exatamente esses tres. Ele abria com os campos em branco e, ao salvar, mandava
o branco de volta - toda edicao de paciente APAGAVA o cadastro dele.

Passou despercebido porque so 6 dos 271 pacientes tinham esses dados: o dano
era invisivel ate alguem procurar.

Coluna nova entra em tres lugares - banco, escritor e leitor. Esquecer o leitor
nao quebra nada: so faz a tela mentir, e neste caso destruir dado junto.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LISTAGEM = RAIZ / "src" / "functions" / "patient" / "list.py"
TIPOS = RAIZ.parent / "frontend" / "src" / "types" / "index.ts"

# Campos do tipo `Patient` do frontend que a listagem NAO precisa trazer.
DERIVADOS = {"deleted_at"}


def campos_que_a_tela_espera():
    texto = TIPOS.read_text(encoding="utf-8")
    inicio = texto.index("export interface Patient {")
    corpo = texto[inicio:texto.index("}", inicio)]
    return {m.group(1) for m in re.finditer(r"^\s{2}(\w+)\??:", corpo, re.M)} - DERIVADOS


class TestContratoDaListagem(unittest.TestCase):
    def test_a_query_traz_todo_campo_que_a_tela_le(self):
        sql = LISTAGEM.read_text(encoding="utf-8")
        esperados = campos_que_a_tela_espera()

        self.assertGreater(len(esperados), 6, "o leitor do tipo parou de achar campo")
        for campo in sorted(esperados):
            with self.subTest(campo=campo):
                self.assertIn(
                    f"p.{campo}", sql,
                    f"a tela le `{campo}` mas a listagem nao traz. O modal abre "
                    f"vazio e sobrescreve o que havia ao salvar.")

    def test_o_cadastro_esta_na_query(self):
        """Por nome, porque foram estes tres que sumiam."""
        sql = LISTAGEM.read_text(encoding="utf-8")

        for campo in ("p.cpf", "p.birth_date", "p.email"):
            self.assertIn(campo, sql)

    def test_o_desconto_personalizado_esta_na_query(self):
        self.assertIn("p.custom_discount_pct", LISTAGEM.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
