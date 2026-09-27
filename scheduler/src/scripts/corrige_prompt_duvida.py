# -*- coding: utf-8 -*-
"""Corrige o bloco DUVIDA do AI_SYSTEM_PROMPT das clinicas.

Roda contra o BANCO, nao contra o codigo: Essencia e Nobre Laser tem prompt
proprio em `message_templates`, e o default do codigo nao as alcanca.

Idempotente: reconhece o texto ja corrigido e nao reaplica. Recusa clinica
cujo bloco tenha sido editado a mao, em vez de sobrescrever o que alguem
escreveu.

O bloco manda empurrar toda duvida de volta para o agendamento. Em 23/09/2026
isso gerou "Ja chamei uma especialista... Enquanto isso, ja aproveito: quais
areas voce gostaria de tratar?" para uma paciente que JA TINHA sessao marcada
para o dia seguinte - e que estava esperando resposta de outra pergunta.

    python -m src.scripts.corrige_prompt_duvida             # simula
    python -m src.scripts.corrige_prompt_duvida --aplicar   # grava
"""
import difflib
import sys

from src.services.db.postgres import PostgresService

APLICAR = "--aplicar" in sys.argv

VELHO = """2. DÚVIDA
   Chame get_faq_answer e responda com o que ela devolver, de forma curta e direta.
   Se houver receio (dor, resultado, preço, segurança), acolha, responda com fato e devolva para a ação:
   "Faz sentido? Quais áreas você quer tratar?\""""

NOVO = """2. DÚVIDA
   Chame get_faq_answer e responda com o que ela devolver, de forma curta e direta.

   ANTES de puxar a conversa para agendamento, chame lookup_appointments.
   Quem já tem sessão marcada não está tentando marcar outra. Perguntar "quais
   áreas você quer tratar?" a essa pessoa ignora o que ela já fez e soa como se
   você não soubesse com quem está falando. Havendo agendamento: responda a
   dúvida e PARE. No máximo, ofereça ajuda com a sessão que já existe.

   Se você NÃO conseguiu responder e vai chamar a especialista, não emende
   outra pergunta. Quem está esperando uma resposta não quer receber uma tarefa
   no lugar dela.

   Só quando não houver agendamento, e a dúvida já estiver respondida, você
   pode devolver para a ação:
   "Faz sentido? Quais áreas você quer tratar?\""""


def main():
    d = PostgresService()
    linhas = d.execute_query(
        "SELECT clinic_id, content FROM scheduler.message_templates "
        "WHERE template_key = 'AI_SYSTEM_PROMPT' ORDER BY clinic_id", ())

    if not linhas:
        print("Nenhuma clinica com AI_SYSTEM_PROMPT proprio.")
        return

    mexidas = 0
    for l in linhas:
        clinica, atual = l["clinic_id"], l["content"]
        print("\n=== %s ===" % clinica)

        if NOVO in atual:
            print("  ja corrigido.")
            continue
        if VELHO not in atual:
            print("  !! o bloco esperado NAO esta neste prompt. Pulando.")
            print("     (o texto pode ter sido editado a mao; conferir antes)")
            continue

        novo_conteudo = atual.replace(VELHO, NOVO, 1)
        for linha in difflib.unified_diff(
                VELHO.split("\n"), NOVO.split("\n"),
                fromfile="antes", tofile="depois", lineterm=""):
            print("  " + linha)

        if APLICAR:
            d.execute_write(
                "UPDATE scheduler.message_templates SET content = %s, updated_at = NOW() "
                "WHERE clinic_id = %s AND template_key = 'AI_SYSTEM_PROMPT'",
                (novo_conteudo, clinica))
            print("\n  APLICADO (%d -> %d chars)" % (len(atual), len(novo_conteudo)))
            mexidas += 1
        else:
            print("\n  (simulacao - use --aplicar)")

    if APLICAR:
        print("\n%d prompt(s) atualizado(s)." % mexidas)


if __name__ == "__main__":
    main()
