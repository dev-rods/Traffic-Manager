# -*- coding: utf-8 -*-
"""Guarda: ninguém chama as portas do bot sem considerar o silêncio (PRD 039).

Uma regra nova só vale se TODO ponto que decide a mesma coisa a aplicar - e a
divergência entre eles é silenciosa. Este teste varre `src/` e exige que cada
chamada a `pode_responder`, `pode_iniciar` ou `motivo_da_pausa` passe
`silenciado=`, ou repasse um `silenciado` que ela própria recebeu.

Por AST, não por texto: busca textual casa com docstring e com comentário, e
foi assim que um guarda anterior passou a vida inteira sem verificar nada.
"""
import ast
import io
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2] / "src"

PORTAS = {"pode_responder", "pode_iniciar", "motivo_da_pausa"}

# Onde as funções moram (quem define, não quem chama) e os repassadores puros,
# que recebem `silenciado` de quem os chama e entregam adiante.
DONOS = {"services/atendimento.py"}
REPASSADORES = {
    "services/retomada.py",            # pode_retomar(..., silenciado=...)
    "services/elegibilidade_do_bot.py",  # por_que_nao_pode(..., silenciado=...)
}

# `bot_policy.should_bot_reply` é o nome antigo, mantido vivo só para quem não
# migrou; ele não decide nada por si e não tem como consultar o banco.
ISENTOS = {"services/bot_policy.py"}


def _arquivos():
    for caminho in RAIZ.rglob("*.py"):
        if "__pycache__" in caminho.parts:
            continue
        yield caminho, caminho.relative_to(RAIZ).as_posix()


def _nome_chamado(no):
    f = no.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


class TestTodaChamadaConsideraOSilencio(unittest.TestCase):
    def test_nenhuma_porta_e_chamada_sem_silenciado(self):
        faltando = []
        for caminho, rel in _arquivos():
            if rel in DONOS or rel in ISENTOS:
                continue
            arvore = ast.parse(io.open(caminho, encoding="utf-8").read())
            for no in ast.walk(arvore):
                if not isinstance(no, ast.Call):
                    continue
                if _nome_chamado(no) not in PORTAS:
                    continue
                if any(kw.arg == "silenciado" for kw in no.keywords):
                    continue
                faltando.append(f"{rel}:{no.lineno} {_nome_chamado(no)}()")

        self.assertEqual(faltando, [], (
            "estas chamadas decidem se o bot fala e ignoram o silêncio por "
            "contato (PRD 039). Passe `silenciado=` - de `silencio.esta_silenciado` "
            "quando houver banco à mão, ou repassado por quem chamou:\n  "
            + "\n  ".join(faltando)))

    def test_os_repassadores_recebem_o_argumento(self):
        """Quem repassa precisa aceitar o valor, senão o repasse é uma
        constante disfarçada."""
        for rel in REPASSADORES:
            arvore = ast.parse(io.open(RAIZ / rel, encoding="utf-8").read())
            aceita = {
                f.name for f in ast.walk(arvore)
                if isinstance(f, ast.FunctionDef)
                and any(a.arg == "silenciado" for a in f.args.kwonlyargs)
            }
            with self.subTest(arquivo=rel):
                self.assertTrue(aceita, f"{rel} repassa `silenciado` sem recebê-lo")


class TestLembreteNaoPassaPelaPorta(unittest.TestCase):
    """Decisão §4.1: o lembrete de sessão é a clínica falando, não o bot, e
    continua saindo para número silenciado. Se um refactor o fizer consultar a
    porta, que seja uma decisão consciente - não um acidente."""

    def test_o_processador_do_lembrete_nao_chama_as_portas(self):
        arvore = ast.parse(io.open(RAIZ / "functions/reminder/processor.py",
                                   encoding="utf-8").read())
        chamadas = {_nome_chamado(n) for n in ast.walk(arvore)
                    if isinstance(n, ast.Call)} & PORTAS
        self.assertEqual(chamadas, set(), (
            "o processador do lembrete passou a consultar a porta do bot: isso "
            "muda a decisão §4.1 do PRD 039 (o lembrete sai mesmo para número "
            "silenciado) e precisa ser deliberado"))


if __name__ == "__main__":
    unittest.main()
