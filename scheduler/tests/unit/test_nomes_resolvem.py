# -*- coding: utf-8 -*-
"""Todo nome usado nos módulos de produção existe.

Esta classe de erro já apareceu duas vezes nesta base:

  02/09/2026  `conversation_agent` usava `intencoes`, `tools_obrigatorias` e
              `fatos_sem_origem` sem importar. A suíte estava verde porque nada
              exercitava `process_message`; quebrou em produção.
  06/09/2026  `attendant/handler` usava `CAMPO_DE_PAUSA`, `PAUSA_ATENDENTE` e
              `esta_pausado` sem importar. Mesma coisa: nenhum teste toca o
              handler, e o `NameError` só apareceria com uma atendente clicando.

Testar cada handler daria mais, mas custa dublê de AWS e banco para cada um.
Isto aqui é barato e pega o modo de falha específico: usar sem importar.
"""
import ast
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2] / "src"

# Só nomes que a análise estática reconhece com segurança: CONSTANTES e funções
# do projeto. Variável local com nome comum daria falso positivo e o teste
# viraria ruído - que é como um teste morre.
def _interessa(nome):
    return nome.isupper() or nome.startswith(("esta_", "pode_", "por_que_", "deve_"))


def nomes_nao_resolvidos(caminho):
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    definidos = set(dir(__builtins__)) | {"__name__", "__file__", "__doc__"}
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            for alias in no.names:
                definidos.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definidos.add(no.name)
        elif isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name):
                    definidos.add(alvo.id)
        elif isinstance(no, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(no.target, ast.Name):
                definidos.add(no.target.id)
        elif isinstance(no, ast.arg):
            definidos.add(no.arg)
        elif isinstance(no, (ast.Global, ast.Nonlocal)):
            definidos.update(no.names)
        elif isinstance(no, ast.ExceptHandler) and no.name:
            definidos.add(no.name)
        elif isinstance(no, (ast.For, ast.comprehension)):
            alvo = no.target
            if isinstance(alvo, ast.Name):
                definidos.add(alvo.id)
            elif isinstance(alvo, (ast.Tuple, ast.List)):
                definidos.update(e.id for e in alvo.elts if isinstance(e, ast.Name))
        elif isinstance(no, ast.withitem) and isinstance(no.optional_vars, ast.Name):
            definidos.add(no.optional_vars.id)

    usados = {
        no.id for no in ast.walk(arvore)
        if isinstance(no, ast.Name) and isinstance(no.ctx, ast.Load) and _interessa(no.id)
    }
    return usados - definidos


class TestNomesResolvem(unittest.TestCase):
    def test_nenhum_modulo_usa_nome_que_nao_existe(self):
        arquivos = sorted(RAIZ.rglob("*.py"))
        self.assertGreater(len(arquivos), 40, "o varredor parou de achar modulo")

        for caminho in arquivos:
            if "__pycache__" in str(caminho):
                continue
            with self.subTest(modulo=caminho.relative_to(RAIZ).as_posix()):
                faltando = nomes_nao_resolvidos(caminho)
                self.assertEqual(
                    faltando, set(),
                    f"{caminho.name} usa {sorted(faltando)} sem importar nem definir. "
                    f"Em producao isso e NameError na primeira chamada.",
                )

    def test_o_varredor_acha_o_erro_de_verdade(self):
        """Se a analise parasse de funcionar, o teste acima passaria vazio."""
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                         encoding="utf-8") as f:
            f.write("def usa():\n    return CONSTANTE_QUE_NINGUEM_IMPORTOU\n")
            temporario = Path(f.name)

        try:
            self.assertEqual(nomes_nao_resolvidos(temporario),
                             {"CONSTANTE_QUE_NINGUEM_IMPORTOU"})
        finally:
            temporario.unlink()


if __name__ == "__main__":
    unittest.main()
