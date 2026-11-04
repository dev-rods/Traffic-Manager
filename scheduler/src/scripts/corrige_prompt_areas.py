# -*- coding: utf-8 -*-
"""Troca o bloco "3. ÁREAS" do AI_SYSTEM_PROMPT das clínicas (PRD 037).

Roda contra o BANCO, não contra o código: Essência e Nobre Laser têm prompt
próprio em `message_templates`, e o default do código não as alcança.

Idempotente: reconhece o texto já corrigido e não reaplica. Recusa clínica
cujo bloco tenha sido editado à mão, em vez de sobrescrever o que alguém
escreveu.

Em 03/11/2026 (Nobre SJC) a pessoa escreveu "Virilha" e o bot respondeu com
botões - perianal sim/não, depois Simples/Cavada/Completa - sem explicar o
que cada tipo é. O prompt mandava entender áreas em texto livre, mas a
descrição da tool present_options mandava usá-la SEMPRE para áreas; e
explicar as variantes nunca tinha sido regra.

    python -m src.scripts.corrige_prompt_areas             # simula
    python -m src.scripts.corrige_prompt_areas --aplicar   # grava
"""
import difflib
import sys

VELHO = """3. ÁREAS
   Chame list_areas. Se a pessoa citar as áreas em texto livre, entenda direto - não a faça escolher de novo numa lista.
   Confirme as áreas, chame calculate_discount e mostre o valor."""

NOVO = """3. ÁREAS
   Chame list_areas. Se a pessoa citar as áreas em texto livre, entenda direto - não a faça escolher de novo numa lista.
   Áreas, variantes de área e perguntas de sim ou não vão em texto corrido, como numa conversa. Nunca use present_options para isso: botões são só para datas e horários.
   Quando a área citada tiver variantes no catálogo, explique a diferença antes de perguntar qual ela quer:
   - Virilha (simples, cavada, completa): chame get_faq_answer sobre os tipos de virilha. O texto do FAQ já vai para a pessoa como mensagem própria; a sua fala é só a pergunta "qual delas você prefere?".
   - Perna, braço, coxa e glúteo (inteira ou 1/2): a diferença é a extensão. Diga isso em uma linha e pergunte qual.
   Perianal é uma área à parte: depois de a pessoa escolher o tipo de virilha, pergunte em uma linha, em texto, se quer incluir a região perianal.
   Confirme as áreas, chame calculate_discount e mostre o valor."""

APLICADO = "aplicado"
JA_CORRIGIDO = "ja_corrigido"
BLOCO_AUSENTE = "bloco_ausente"


def aplica(conteudo):
    """(novo_conteudo, status). Nunca altera o texto fora dos dois ramos seguros."""
    if NOVO in conteudo:
        return conteudo, JA_CORRIGIDO
    if VELHO not in conteudo:
        return conteudo, BLOCO_AUSENTE
    return conteudo.replace(VELHO, NOVO, 1), APLICADO


def main(argv=None):
    from src.services.db.postgres import PostgresService

    argv = sys.argv[1:] if argv is None else argv
    aplicar = "--aplicar" in argv

    d = PostgresService()
    linhas = d.execute_query(
        "SELECT clinic_id, content FROM scheduler.message_templates "
        "WHERE template_key = 'AI_SYSTEM_PROMPT' ORDER BY clinic_id", ())

    if not linhas:
        print("Nenhuma clínica com AI_SYSTEM_PROMPT próprio.")
        return

    mexidas = 0
    for l in linhas:
        clinica, atual = l["clinic_id"], l["content"]
        print("\n=== %s ===" % clinica)
        novo_conteudo, status = aplica(atual)

        if status == JA_CORRIGIDO:
            print("  já corrigido.")
            continue
        if status == BLOCO_AUSENTE:
            print("  !! o bloco esperado NÃO está neste prompt. Pulando.")
            print("     (o texto pode ter sido editado à mão; conferir antes)")
            continue

        for linha in difflib.unified_diff(
                VELHO.split("\n"), NOVO.split("\n"),
                fromfile="antes", tofile="depois", lineterm=""):
            print("  " + linha)

        if aplicar:
            d.execute_write(
                "UPDATE scheduler.message_templates SET content = %s, updated_at = NOW() "
                "WHERE clinic_id = %s AND template_key = 'AI_SYSTEM_PROMPT'",
                (novo_conteudo, clinica))
            print("\n  APLICADO (%d -> %d chars)" % (len(atual), len(novo_conteudo)))
            mexidas += 1
        else:
            print("\n  (simulação - use --aplicar)")

    if aplicar:
        print("\n%d prompt(s) atualizado(s)." % mexidas)


if __name__ == "__main__":
    main()
