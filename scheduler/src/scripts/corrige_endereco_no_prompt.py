# -*- coding: utf-8 -*-
"""Tira o endereço escrito à mão do AI_SYSTEM_PROMPT e põe {{clinic_address}}.

Roda contra o BANCO, não contra o código: Essência e Nobre Laser têm prompt
próprio em `message_templates`, e o default do código não as alcança.

O bloco "AO FECHAR O AGENDAMENTO" trazia o endereço da Essência literal, e o
prompt da Nobre era cópia do dela - uma lead de São José dos Campos recebeu o
endereço de São Paulo em 09/11/2026. As referências de localização (metrô,
estacionamento, ponto de referência) já vivem no FAQ `PARKING` de cada clínica,
que é por clínica e está correto nas duas; o endereço vem de `{{clinic_address}}`,
que é o cadastro.

Idempotente: reconhece o texto já corrigido e não reaplica. Recusa prompt cujo
bloco tenha sido editado à mão, em vez de sobrescrever o que alguém escreveu.

    python -m src.scripts.corrige_endereco_no_prompt             # simula
    python -m src.scripts.corrige_endereco_no_prompt --aplicar   # grava
    python -m src.scripts.corrige_endereco_no_prompt --verifica  # só audita
"""
import sys

CHAVE = "AI_SYSTEM_PROMPT"

VELHO = """Sempre que finalizar um agendamento, passe o endereço completo com as referências de localização:

Rua Augusta, 2709
Conj. 26 - CLÍNICA ESSÊNCIA (2º andar)

Estação mais próxima: Linha 4 - Amarela: Oscar Freire (cerca de 13 minutos a pé)

‼️ Prédio comercial ao lado das pernambucanas, com fachada e recepção em reforma, possui estacionamento pago 24h. 🚨"""

NOVO = """Sempre que finalizar um agendamento, passe o endereço completo da clínica: {{clinic_address}}
Nunca escreva um endereço de memória nem repita o de outra mensagem: o endereço é o que está nesta linha.
Se a pessoa pedir referências de localização - metrô, estacionamento, ponto de referência -, chame get_faq_answer: o FAQ desta clínica tem essas informações."""

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


def audita(linhas, enderecos):
    """[(clinic_id, dona_do_endereco, endereco)] - quem carrega endereço alheio."""
    from src.services.endereco_alheio import endereco_alheio

    achados = []
    for l in linhas:
        alheio = endereco_alheio(l["content"], l["clinic_id"], enderecos)
        if alheio:
            achados.append((l["clinic_id"], alheio[0], alheio[1]))
    return achados


def main(argv=None):
    from src.services.db.postgres import PostgresService
    from src.services.endereco_alheio import enderecos_das_clinicas

    argv = sys.argv[1:] if argv is None else argv
    aplicar = "--aplicar" in argv
    so_verifica = "--verifica" in argv

    d = PostgresService()
    linhas = d.execute_query(
        "SELECT clinic_id, template_key, content FROM scheduler.message_templates "
        "ORDER BY clinic_id, template_key", ())
    enderecos = enderecos_das_clinicas(d)

    print("=== AUDITORIA: template que cita endereço de outra clínica ===")
    achados = audita(linhas, enderecos)
    if not achados:
        print("  nenhum.")
    for clinica, dona, endereco in achados:
        print(f"  !! {clinica} cita o endereço de {dona}: {endereco}")

    if so_verifica:
        return 1 if achados else 0

    prompts = [l for l in linhas if l["template_key"] == CHAVE]
    if not prompts:
        print("\nNenhuma clínica com AI_SYSTEM_PROMPT próprio.")
        return 0

    print("\n=== CORREÇÃO do bloco AO FECHAR O AGENDAMENTO ===")
    mexidas = 0
    for l in prompts:
        clinica, atual = l["clinic_id"], l["content"]
        print(f"\n--- {clinica}")
        novo_conteudo, status = aplica(atual)

        if status == JA_CORRIGIDO:
            print("  já corrigido.")
            continue
        if status == BLOCO_AUSENTE:
            print("  !! o bloco esperado NÃO está neste prompt. Pulando.")
            print("     (o texto pode ter sido editado à mão; conferir antes)")
            continue

        print("  - endereço literal da Essência")
        print("  + {{clinic_address}} + referências pelo FAQ")
        mexidas += 1
        if aplicar:
            d.execute_write(
                "UPDATE scheduler.message_templates SET content = %s, updated_at = NOW() "
                "WHERE clinic_id = %s AND template_key = %s",
                (novo_conteudo, clinica, CHAVE))
            print("  GRAVADO.")

    if not aplicar and mexidas:
        print(f"\n{mexidas} prompt(s) a corrigir. Rode com --aplicar para gravar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
