# -*- coding: utf-8 -*-
"""O menor preço por área da clínica, para o prompt não guardar o número.

O `AI_SYSTEM_PROMPT` dizia "a partir de *R$ 65* por área" com o valor escrito no
texto, em dois lugares. O número estava certo em 06/09/2026 - R$ 65,00 é
mesmo o mais barato entre as 32 áreas da Essência - e esse não era o problema.

O problema é o mesmo padrão que já custou caro aqui: dado copiado. Quando a
clínica reajustar a tabela, `service_areas` muda e o prompt continua anunciando
R$ 65, com toda a confiança. E a proveniência não pega: ela extrai valores em
dinheiro, mas só data e horário bloqueiam a resposta - um preço velho sai com um
aviso no log e mais nada.

Agora o número vem do banco a cada montagem do prompt. Ele é estável dentro de
uma conversa, então o prefixo cacheado continua byte-idêntico.
"""
import logging

logger = logging.getLogger(__name__)

# Sem preço nenhum, o texto perde o número em vez de inventar um. "A partir de
# R$ 0" seria mentira e um placeholder cru na cara da paciente seria pior.
#
# O termo entra no meio de "A partir de ___ por área", entao precisa caber ali.
# "sob consulta" nao e a frase mais elegante nessa posicao, mas so aparece se a
# clinica nao tiver nenhuma area com preco - uma configuracao quebrada, em que o
# bot nao conseguiria cotar nada de qualquer forma.
SEM_PRECO = "sob consulta"


def formata_reais(centavos):
    """1_2345 -> 'R$ 123,45'. Mesmo formato que as tools já devolvem."""
    return f"R$ {centavos / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def preco_minimo_por_area(db, clinic_id):
    """Menor preço ativo entre as áreas da clínica, formatado.

    Devolve `SEM_PRECO` quando não há preço ou a consulta falha. Nunca levanta:
    o prompt é montado a cada mensagem, e derrubá-lo por causa de um argumento
    de venda deixaria a paciente sem resposta.
    """
    try:
        linhas = db.execute_query(
            """
            SELECT MIN(sa.price_cents) AS minimo
            FROM scheduler.service_areas sa
            JOIN scheduler.areas a ON a.id = sa.area_id
            WHERE a.clinic_id = %s AND sa.active = TRUE AND a.active = TRUE
              AND sa.price_cents IS NOT NULL AND sa.price_cents > 0
            """,
            (clinic_id,),
        )
    except Exception as e:
        logger.error(f"[PrecoMinimo] Falha ao consultar {clinic_id}: {e}")
        return SEM_PRECO

    if not linhas or linhas[0].get("minimo") is None:
        logger.warning(f"[PrecoMinimo] {clinic_id} sem area com preco")
        return SEM_PRECO

    return formata_reais(int(linhas[0]["minimo"]))
