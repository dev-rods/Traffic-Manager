# -*- coding: utf-8 -*-
"""Reescreve no AI_SYSTEM_PROMPT das clínicas duas etapas do roteiro (PRD 064).

Roda contra o BANCO (Essência e Nobre têm prompt próprio em
`message_templates`); o default do código é alinhado à parte.

O que muda:
- 2. DÚVIDA: o FAQ virou fonte (frente 4). "Responda com o que ela devolver"
  passa a "responda só o que foi perguntado, curto, com as palavras do item;
  não cole o texto inteiro".
- 3. ÁREAS, virilha: decisão P6 do André (25/11). Em vez de "chame o FAQ, o
  texto já vai como mensagem própria", o bot lista os três tipos COM O VALOR
  (list_areas), em uma linha cada, e pergunta qual; o FAQ dos tipos só se a
  pessoa pedir a explicação completa.

Idempotente, recusa bloco editado à mão, simula por padrão:

    python -m src.scripts.corrige_prompt_064 --stage dev             # simula
    python -m src.scripts.corrige_prompt_064 --stage dev --aplicar   # grava
    python -m src.scripts.corrige_prompt_064 --stage prod --aplicar

`--stage` carrega as variáveis RDS_* do SSM (perfil dev-andre), como o eval.
Medir antes de gravar em prod: `eval_064.py --prompt-arquivo` com o texto
simulado (`--salvar-em arquivo`).
"""
import argparse
import difflib
import os
import sys

DUVIDA_VELHO = """2. DÚVIDA
   Chame get_faq_answer e responda com o que ela devolver, de forma curta e direta."""

DUVIDA_NOVO = """2. DÚVIDA
   Chame get_faq_answer e responda só o que foi perguntado, curto, com as palavras e os fatos do item. Não cole o texto inteiro: explicação completa só se a pessoa pedir."""

VIRILHA_VELHO = """   - Virilha (simples, cavada, completa): chame get_faq_answer sobre os tipos de virilha. O texto do FAQ já vai para a pessoa como mensagem própria; a sua fala é só a pergunta "qual delas você prefere?"."""

VIRILHA_NOVO = """   - Virilha (simples, cavada, completa): chame list_areas e responda com as três opções e o valor de cada uma, uma linha por tipo (simples: só o que fica para fora do biquíni; cavada: quase toda, deixando uma faixa central; completa: toda a região), e pergunte qual ela quer. Se a pergunta era de preço, essa É a resposta. Use get_faq_answer sobre os tipos de virilha só se ela pedir a explicação completa."""

TROCAS = (("DÚVIDA", DUVIDA_VELHO, DUVIDA_NOVO), ("VIRILHA", VIRILHA_VELHO, VIRILHA_NOVO))

APLICADO = "aplicado"
JA_CORRIGIDO = "ja_corrigido"
BLOCO_AUSENTE = "bloco_ausente"


def aplica(conteudo):
    """(novo_conteudo, {nome: status}). Nunca altera texto fora dos ramos seguros."""
    status = {}
    for nome, velho, novo in TROCAS:
        if novo in conteudo:
            status[nome] = JA_CORRIGIDO
        elif velho not in conteudo:
            status[nome] = BLOCO_AUSENTE
        else:
            conteudo = conteudo.replace(velho, novo, 1)
            status[nome] = APLICADO
    return conteudo, status


def _carrega_env_do_ssm(stage):
    import boto3
    ssm = boto3.Session(profile_name="dev-andre", region_name="us-east-1").client("ssm")
    for env, param in [("RDS_HOST", "SUPABASE_DB_HOST"), ("RDS_PORT", "SUPABASE_DB_PORT"),
                       ("RDS_DATABASE", "SUPABASE_DB_NAME"), ("RDS_USERNAME", "SUPABASE_DB_USER"),
                       ("RDS_PASSWORD", "SUPABASE_DB_PASSWORD")]:
        os.environ[env] = ssm.get_parameter(Name=f"/{stage}/{param}", WithDecryption=True)["Parameter"]["Value"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("dev", "prod"))
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--salvar-em", help="grava o texto simulado da primeira clínica neste arquivo (para o eval)")
    args = ap.parse_args(argv)
    if args.stage:
        _carrega_env_do_ssm(args.stage)

    from src.services.db.postgres import PostgresService
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
        for nome, st in status.items():
            print(f"  {nome}: {st}")
        if all(st != APLICADO for st in status.values()):
            continue
        for linha in difflib.unified_diff(atual.split("\n"), novo_conteudo.split("\n"),
                                          fromfile="antes", tofile="depois", lineterm="", n=1):
            print("  " + linha)
        if args.salvar_em and mexidas == 0:
            with open(args.salvar_em, "w", encoding="utf-8", newline="\n") as f:
                f.write(novo_conteudo)
            print(f"  texto simulado salvo em {args.salvar_em}")
        if args.aplicar:
            d.execute_write(
                "UPDATE scheduler.message_templates SET content = %s, updated_at = NOW() "
                "WHERE clinic_id = %s AND template_key = 'AI_SYSTEM_PROMPT'",
                (novo_conteudo, clinica))
            print("\n  APLICADO (%d -> %d chars)" % (len(atual), len(novo_conteudo)))
        mexidas += 1
    print("\n%d prompt(s) %s." % (mexidas, "atualizado(s)" if args.aplicar else "simulado(s) - use --aplicar"))


if __name__ == "__main__":
    main()
