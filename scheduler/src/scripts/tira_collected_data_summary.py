# -*- coding: utf-8 -*-
"""Tira a linha {{collected_data_summary}} do AI_SYSTEM_PROMPT no banco.

A variável era, no desenho original do agente (docs/plans/2026-02-28-ai-
conversation-engine-design.md §4), o resumo do estado confirmado da conversa -
áreas, valor, nome - reinjetado no prompt a cada turno para sobreviver à janela
deslizante de 20 mensagens. O `collected_data` estruturado da sessão nunca
existiu: `conversation_agent` sempre passou string vazia. A linha ocupa o lugar
de uma informação que o modelo não recebe.

Decisão do André em 09/11/2026: a linha sai. O papel dela ficou com o histórico
e com o `respaldo_das_tools`.

Idempotente: se a linha não está mais lá, não faz nada.

    python -m src.scripts.tira_collected_data_summary             # simula
    python -m src.scripts.tira_collected_data_summary --aplicar   # grava
"""
import sys

CHAVE = "AI_SYSTEM_PROMPT"
LINHA = "{{collected_data_summary}}\n"

APLICADO = "aplicado"
JA_LIMPO = "ja_limpo"


def aplica(conteudo):
    """(novo_conteudo, status). Remove a linha; não toca em nada mais."""
    if LINHA not in conteudo:
        return conteudo, JA_LIMPO
    return conteudo.replace(LINHA, "", 1), APLICADO


def main(argv=None):
    from src.services.db.postgres import PostgresService

    argv = sys.argv[1:] if argv is None else argv
    aplicar = "--aplicar" in argv

    d = PostgresService()
    prompts = d.execute_query(
        "SELECT clinic_id, content FROM scheduler.message_templates "
        "WHERE template_key = %s ORDER BY clinic_id", (CHAVE,))

    if not prompts:
        print("Nenhuma clínica com AI_SYSTEM_PROMPT próprio neste banco.")
        return 0

    mexidas = 0
    for l in prompts:
        clinica, atual = l["clinic_id"], l["content"]
        novo_conteudo, status = aplica(atual)
        print(f"\n--- {clinica}")

        if status == JA_LIMPO:
            print("  a linha não está no prompt.")
            continue

        print(f"  - {{{{collected_data_summary}}}} ({len(atual)} -> {len(novo_conteudo)} chars)")
        mexidas += 1
        if aplicar:
            d.execute_write(
                "UPDATE scheduler.message_templates SET content = %s, updated_at = NOW() "
                "WHERE clinic_id = %s AND template_key = %s",
                (novo_conteudo, clinica, CHAVE))
            print("  GRAVADO.")

    if not aplicar and mexidas:
        print(f"\n{mexidas} prompt(s) a limpar. Rode com --aplicar para gravar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
