# -*- coding: utf-8 -*-
"""Troca travessao e meia-risca por hifen nos textos que chegam ao paciente.

    python -m src.scripts.troca_travessao             # simula
    python -m src.scripts.troca_travessao --aplicar   # grava

Por que isto existe: o travessao (—) e a meia-risca (–) nao estao no teclado do
celular e nao acrescentam nada que o hifen nao resolva. Em 27/09/2026 uma
varredura achou 12 respostas do FAQ e 3 clinicas com esses caracteres.

O AI_SYSTEM_PROMPT entra na varredura mesmo NAO indo ao paciente: o modelo
imita o estilo do que le. Conferido na conversa de 23/09 - o bot mandou quatro
mensagens com travessao para a paciente, e o prompt dele tem seis. Trocar la
reduz a chance de o modelo reproduzir aqui; a instrucao explicita, que este
script tambem acrescenta, e o que garante.

Idempotente: rodar de novo nao acha nada para trocar.
"""
import sys

from src.services.db.postgres import PostgresService

APLICAR = "--aplicar" in sys.argv

TRAVESSAO = "\u2014"
MEIA_RISCA = "\u2013"

# (tabela, coluna, colunas que identificam a linha)
ALVOS = [
    ("faq_items", "question_label", ["clinic_id", "question_label"]),
    ("faq_items", "answer", ["clinic_id", "question_label"]),
    ("clinics", "welcome_message", ["clinic_id"]),
    ("clinics", "welcome_intro_message", ["clinic_id"]),
    ("clinics", "pre_session_instructions", ["clinic_id"]),
    ("clinics", "batch_message_template", ["clinic_id"]),
    ("message_templates", "content", ["clinic_id", "template_key"]),
]

# A instrucao entra na secao que ja governa o estilo das mensagens.
ANCORA = '• Nunca use "Prezada", "Venho por meio desta" ou linguagem formal de escritório.'
INSTRUCAO = (
    ANCORA
    + "\n• Use hífen (-), nunca travessão (—) nem meia-risca (–): não estão no "
    "teclado do celular e não acrescentam nada."
)


def limpa(texto):
    return (texto or "").replace(TRAVESSAO, "-").replace(MEIA_RISCA, "-")


def main():
    db = PostgresService()
    trocas = 0

    for tabela, coluna, chaves in ALVOS:
        campos = ", ".join(chaves)
        try:
            linhas = db.execute_query(
                "SELECT %s, %s AS texto FROM scheduler.%s "
                "WHERE %s LIKE %%s OR %s LIKE %%s"
                % (campos, coluna, tabela, coluna, coluna),
                ("%" + TRAVESSAO + "%", "%" + MEIA_RISCA + "%"))
        except Exception as e:
            print("  (pulei %s.%s: %s)" % (tabela, coluna, str(e)[:60]))
            continue

        for linha in linhas:
            novo = limpa(linha["texto"])
            quantos = ((linha["texto"] or "").count(TRAVESSAO)
                       + (linha["texto"] or "").count(MEIA_RISCA))
            quem = " / ".join(str(linha[k]) for k in chaves)
            print("  %-22s %-24s %d ocorrencia(s)  %s"
                  % (tabela + "." + coluna, "", quantos, quem))

            if APLICAR:
                onde = " AND ".join("%s = %%s" % k for k in chaves)
                db.execute_write(
                    "UPDATE scheduler.%s SET %s = %%s WHERE %s"
                    % (tabela, coluna, onde),
                    tuple([novo] + [linha[k] for k in chaves]))
            trocas += 1

    # A instrucao explicita: o modelo gera travessao por conta propria, entao
    # limpar o prompt reduz a chance mas nao fecha a porta.
    prompts = db.execute_query(
        "SELECT clinic_id, content FROM scheduler.message_templates "
        "WHERE template_key = 'AI_SYSTEM_PROMPT'", ())
    for p in prompts:
        if "nunca travessão" in p["content"]:
            print("  instrucao ja presente em %s" % p["clinic_id"])
            continue
        if ANCORA not in p["content"]:
            print("  !! ancora de estilo nao achada em %s; instrucao NAO inserida"
                  % p["clinic_id"])
            continue
        print("  + instrucao de hifen em %s" % p["clinic_id"])
        if APLICAR:
            db.execute_write(
                "UPDATE scheduler.message_templates SET content = %s, updated_at = NOW() "
                "WHERE clinic_id = %s AND template_key = 'AI_SYSTEM_PROMPT'",
                (limpa(p["content"]).replace(limpa(ANCORA), limpa(INSTRUCAO), 1),
                 p["clinic_id"]))

    print("\n  %d campo(s) %s." % (trocas, "corrigido(s)" if APLICAR else "a corrigir"))
    if not APLICAR:
        print("  (simulacao - use --aplicar)")


if __name__ == "__main__":
    main()
