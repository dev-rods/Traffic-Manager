# -*- coding: utf-8 -*-
"""A regra de quais conversões sobem ao Google mora em UM lugar.

Em 27/09/2026 ela morava em dois: o uploader do `infra/`, que fala com o
Google de verdade, e `LeadService.get_pending_conversions`, que ninguém
chamava. Quando a regra mudou - a conversão passou a contar no agendamento,
não na sessão - só o uploader mudou.

A cópia morta não ficou só desatualizada. Ela levou junto seis testes que
continuaram verdes afirmando a regra derrubada, entre eles um chamado
`test_future_appointment_not_eligible` provando o oposto da decisão que
acabara de ser tomada. Uma suíte verde dizendo que a mudança não aconteceu é
pior do que nenhuma suíte.

Este teste falha se a elegibilidade voltar a ser decidida dentro do scheduler.
"""
import ast
import os
import unittest

SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Marcas da decisão de elegibilidade. Não são strings quaisquer: cada uma é um
# pedaço da query que escolhe o que vai para o Google.
MARCAS = (
    # A sessão já aconteceu. A expressão mudou em 04/10/2026, de `CURRENT_DATE`
    # para a data de São Paulo: o banco roda em UTC, que está à frente do
    # Brasil, e entre 21h e meia-noite BRT o `CURRENT_DATE` já era o dia
    # seguinte - a sessão de hoje passava por realizada. O marcador acompanha a
    # regra de verdade, porque marcador defasado deixa de guardar.
    "appointment_date < (NOW() AT TIME ZONE 'America/Sao_Paulo')::date",
    "INTERVAL '90 days'",                # a janela do clique
)

# A ÚNICA exceção, e ela é nomeada: `marca_no_show` usa o mesmo predicado de
# "a sessão já aconteceu" como PRÉ-CONDIÇÃO para registrar ausência - não para
# decidir o que sobe ao Google. Os dois nem precisam concordar: o uploader
# exclui NO_SHOW pelo `status = CONFIRMED`, antes de olhar data.
#
# A exceção é por FUNÇÃO, não por arquivo: `appointment_service.py` inteiro
# liberado deixaria uma cópia da elegibilidade entrar ali sem alarme.
EXCECAO = "marca_no_show"

# `uploaded_at IS NULL` ficou DE FORA de propósito, mesmo sendo parte da query
# de elegibilidade. Ela aparece legitimamente em `update_conversion_date`, que
# não decide nada sobre o Google: só recusa mexer no que já subiu. Uma marca que
# acusa esse caso viraria ruído, e teste que dá alarme falso é teste que alguém
# desliga. As duas que sobraram só existem para decidir o que sobe.


def _arquivos_py():
    for pasta, _, nomes in os.walk(SRC):
        if "__pycache__" in pasta:
            continue
        for nome in nomes:
            if nome.endswith(".py"):
                yield os.path.join(pasta, nome)


def _sem_comentarios(texto):
    """Tira linhas de comentário: a nota que explica a remoção cita as marcas,
    e é exatamente o tipo de documentação que deve poder continuar existindo."""
    return "\n".join(
        l for l in texto.split("\n") if not l.lstrip().startswith("#")
    )


def _sem_a_excecao(texto):
    """Remove o corpo de `marca_no_show`, pelo AST e não por regex.

    Pelo AST porque o limite da função é o que importa: cortar por texto (do
    `def` até a próxima linha em branco, digamos) erraria assim que alguém
    formatasse diferente, e o erro seria silencioso nos dois sentidos -
    liberando demais, ou acusando o inocente.
    """
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return texto

    linhas = texto.split("\n")
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == EXCECAO:
            for i in range(no.lineno - 1, min(no.end_lineno, len(linhas))):
                linhas[i] = ""
    return "\n".join(linhas)


class TestUmDonoSo(unittest.TestCase):
    def test_o_scheduler_nao_decide_elegibilidade(self):
        achados = []
        for caminho in _arquivos_py():
            if os.path.basename(caminho) == "setup_database.py":
                continue  # o DDL cria o índice; não decide nada
            with open(caminho, encoding="utf-8") as f:
                texto = _sem_a_excecao(_sem_comentarios(f.read()))
            for marca in MARCAS:
                if marca in texto:
                    achados.append("%s: %s" % (os.path.relpath(caminho, SRC), marca))

        self.assertEqual(
            achados, [],
            "elegibilidade de conversão decidida fora do uploader:\n  "
            + "\n  ".join(achados)
            + "\n\nA regra pertence a infra/src/functions/conversions/uploader.py.",
        )

    def test_a_nota_que_explica_a_remocao_continua(self):
        """Sem ela, o próximo a precisar da query reescreve a cópia."""
        caminho = os.path.join(SRC, "services", "lead_service.py")
        with open(caminho, encoding="utf-8") as f:
            texto = f.read()

        self.assertIn("get_pending_conversions", texto)
        self.assertIn("uploader.py", texto)


if __name__ == "__main__":
    unittest.main()
