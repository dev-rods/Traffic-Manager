# -*- coding: utf-8 -*-
"""Insere o galho "2b. SESSÃO JÁ MARCADA" no AI_SYSTEM_PROMPT do banco (PRD 045).

Roda contra o BANCO: Essência e Nobre têm prompt próprio em `message_templates`,
e o default do código não as alcança. O roteiro de COMO CONDUZIR A CONVERSA
tinha sete etapas, todas de marcação; quem já tinha sessão e pedia uma mudança
caía nele e saía com um "Confirmo?" para uma SEGUNDA sessão (Essência 09/11/2026,
Nobre 05/11/2026 - nas duas a recepção teve de desfazer).

Idempotente: reconhece o galho já inserido e não repete. Recusa prompt sem a
âncora "3. ÁREAS", em vez de adivinhar onde pôr.

    python -m src.scripts.insere_galho_sessao_marcada             # simula
    python -m src.scripts.insere_galho_sessao_marcada --aplicar   # grava
"""
import sys

CHAVE = "AI_SYSTEM_PROMPT"
ANCORA = "3. ÁREAS\n"
TITULO = "2b. SESSÃO JÁ MARCADA"

GALHO = """2b. SESSÃO JÁ MARCADA
   Se o bloco QUEM É mostra um próximo horário, você está falando com alguém
   que já tem sessão. Qualquer pedido de mudança - trocar, tirar ou incluir
   área, mudar o dia ou a hora - é ALTERAÇÃO dessa sessão, nunca marcação de
   outra.
   1. Leia as áreas que ela tem marcadas (QUEM É ou lookup_appointments) e
      confirme em uma frase o que muda: "Então fica só axilas, no mesmo dia
      18/11 às 14:50 - é isso?"
   2. O horário dela é dela. Mantenha data e hora por padrão. Só proponha
      outro horário se ela pedir ou se alterar_agendamento responder que as
      áreas novas não cabem - e aí ofereça primeiro o mais próximo no MESMO
      dia, por get_time_slots.
   3. Confirmada a mudança, chame alterar_agendamento. Nunca book_appointment:
      ele cria uma segunda sessão e deixa a primeira ocupando a agenda.
   4. Só se ela disser, com todas as letras, que quer OUTRA sessão além da que
      tem, siga para 3. ÁREAS - e diga a ela que a primeira continua marcada.

"""

APLICADO = "aplicado"
JA_APLICADO = "ja_aplicado"
ANCORA_AUSENTE = "ancora_ausente"


def aplica(conteudo):
    """(novo_conteudo, status). Só insere; não altera nada do que já está lá."""
    if TITULO in conteudo:
        return conteudo, JA_APLICADO
    if ANCORA not in conteudo:
        return conteudo, ANCORA_AUSENTE
    return conteudo.replace(ANCORA, GALHO + ANCORA, 1), APLICADO


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
        novo, status = aplica(atual)
        print(f"\n--- {clinica}")
        if status == JA_APLICADO:
            print("  já tem o galho.")
            continue
        if status == ANCORA_AUSENTE:
            print("  !! sem a âncora '3. ÁREAS'. Pulando - conferir o prompt à mão.")
            continue
        print(f"  + {TITULO} antes de 3. ÁREAS ({len(atual)} -> {len(novo)} chars)")
        mexidas += 1
        if aplicar:
            d.execute_write(
                "UPDATE scheduler.message_templates SET content = %s, updated_at = NOW() "
                "WHERE clinic_id = %s AND template_key = %s",
                (novo, clinica, CHAVE))
            print("  GRAVADO.")

    if not aplicar and mexidas:
        print(f"\n{mexidas} prompt(s) a alterar. Rode com --aplicar para gravar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
