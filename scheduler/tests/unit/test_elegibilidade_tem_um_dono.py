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
import os
import re
import unittest

SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Marcas da decisão de elegibilidade. Não são strings quaisquer: cada uma é um
# pedaço da query que escolhe o que vai para o Google.
MARCAS = (
    "appointment_date < CURRENT_DATE",   # a sessão já aconteceu
    "INTERVAL '90 days'",                # a janela do clique
)

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


class TestUmDonoSo(unittest.TestCase):
    def test_o_scheduler_nao_decide_elegibilidade(self):
        achados = []
        for caminho in _arquivos_py():
            if os.path.basename(caminho) == "setup_database.py":
                continue  # o DDL cria o índice; não decide nada
            with open(caminho, encoding="utf-8") as f:
                texto = _sem_comentarios(f.read())
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
