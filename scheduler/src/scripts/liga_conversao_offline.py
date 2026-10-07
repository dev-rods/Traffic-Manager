# -*- coding: utf-8 -*-
"""Aponta uma clinica para a conversao offline dela no Google Ads.

Sem `clinics.offline_conversion_action_id` preenchido, o uploader mensal nao
tem para onde mandar nada: a query de clinicas elegiveis exige a coluna, e o
resumo sai com `clinics: 0`. Silencioso - nenhum erro, nenhuma conversao.

A conversao offline e criada a mao no Google Ads (Ferramentas > Conversoes >
Importar > Uploads manuais). O numero abaixo e o ID dela, nao o da campanha
nem o da conta.

Sem argumentos, LISTA as clinicas e o estado de cada uma. O clinic_id nao esta
escrito neste arquivo de proposito: ele so existe no banco, e um mapa chutado
no codigo mandaria conversao para a conta errada sem erro nenhum.

    python -m src.scripts.liga_conversao_offline                          # lista
    python -m src.scripts.liga_conversao_offline <clinic_id> <action_id>  # simula
    python -m src.scripts.liga_conversao_offline <clinic_id> <action_id> --aplicar

## Sao DUAS actions desde o PRD 017

    --compra        (default) so confirmado, sessao passada. PRD 016.
    --agendamento   todo agendamento, inclusive cancelado e falta. PRD 017.

Um evento otimiza, o outro mede. `--compra` e o default por compatibilidade
com quem ja usou este script, nao por ser o mais importante.

A conversao de COMPRA da Essencia, criada a mao em 27/09/2026, e a 7699541177.
"""
import sys

from src.services.db.postgres import PostgresService

APLICAR = "--aplicar" in sys.argv

# Qual das duas actions o comando esta ligando. `--compra` e o default porque
# este script existia antes de haver duas, e quem ja o usa nao deve descobrir a
# mudanca por ter ligado a action errada.
AGENDAMENTO = "--agendamento" in sys.argv
COLUNA = ("booking_conversion_action_id" if AGENDAMENTO
          else "offline_conversion_action_id")
ROTULO = "AGENDAMENTO" if AGENDAMENTO else "COMPRA"


def listar(d):
    """Mostra o estado de cada clinica. E daqui que sai o clinic_id correto."""
    linhas = d.execute_query(
        "SELECT clinic_id, name, google_ads_customer_id, "
        "       offline_conversion_action_id, booking_conversion_action_id "
        "FROM scheduler.clinics ORDER BY clinic_id", ())
    print("%-28s %-20s %-12s %-14s %s" % (
        "clinic_id", "nome", "conta ads", "compra", "agendamento"))
    for c in linhas:
        print("%-28s %-20s %-12s %-14s %s" % (
            c["clinic_id"], (c["name"] or "")[:20],
            c["google_ads_customer_id"] or "-",
            c["offline_conversion_action_id"] or "(vazio)",
            c["booking_conversion_action_id"] or "(vazio)"))
    print("\nPara ligar a de COMPRA:")
    print("  python -m src.scripts.liga_conversao_offline "
          "<clinic_id> <action_id> --aplicar")
    print("Para ligar a de AGENDAMENTO:")
    print("  python -m src.scripts.liga_conversao_offline "
          "<clinic_id> <action_id> --agendamento --aplicar")


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]

    d = PostgresService()
    if len(argumentos) != 2:
        listar(d)
        return

    clinic_id, action_id = argumentos
    if not action_id.isdigit():
        print("!! o action_id e so numeros (ex: 7699541177). Recebi: %r" % action_id)
        raise SystemExit(2)

    linhas = d.execute_query(
        "SELECT clinic_id, name, google_ads_customer_id, "
        "       offline_conversion_action_id, booking_conversion_action_id "
        "FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,))

    print("=== %s ===" % clinic_id)
    if not linhas:
        print("  !! clinica NAO existe neste banco.")
        print("     (dev e prod sao bancos diferentes - conferir em qual voce esta)")
        raise SystemExit(1)

    c = linhas[0]
    atual = c[COLUNA]
    print("  nome:             %s" % c["name"])
    print("  ligando a de:     %s" % ROTULO)

    if not c["google_ads_customer_id"]:
        print("  !! sem google_ads_customer_id. O uploader ignora a clinica de todo")
        print("     jeito; ligar so a conversao nao resolve.")
        raise SystemExit(1)

    if atual == action_id:
        print("  ja ligada (%s). Nada a fazer." % action_id)
        return
    if atual:
        print("  !! ja aponta para OUTRA conversao: %s" % atual)
        print("     Nao vou sobrescrever. Se a troca e intencional, limpe a mao.")
        raise SystemExit(1)

    # As duas actions sao DISTINTAS no Google Ads: uma e PURCHASE, a outra de
    # lead/agendamento. Apontar as duas colunas para o mesmo ID mandaria o
    # mesmo evento duas vezes para o mesmo destino, e o Google trataria o
    # segundo como ajuste do primeiro (mesmo transactionId) - contagem errada,
    # em silencio.
    outra = ("offline_conversion_action_id" if AGENDAMENTO
             else "booking_conversion_action_id")
    if c[outra] == action_id:
        print("  !! este ID ja esta ligado na OUTRA coluna (%s)." % outra)
        print("     As duas actions tem de ser distintas - uma e PURCHASE, a")
        print("     outra de agendamento. Crie a segunda no painel do Google.")
        raise SystemExit(1)

    print("  conta Google Ads: %s" % c["google_ads_customer_id"])
    print("  conversao:        (vazio) -> %s" % action_id)

    if APLICAR:
        # Nome de coluna nao e parametrizavel em SQL, e COLUNA vem de uma flag
        # fechada (`--agendamento`), nao de entrada livre - as duas unicas
        # possibilidades estao escritas acima.
        d.execute_write(
            "UPDATE scheduler.clinics SET %s = %%s, "
            "updated_at = NOW() WHERE clinic_id = %%s" % COLUNA,
            (action_id, clinic_id))
        print("\n  APLICADO. O uploader passa a enxergar a clinica no proximo ciclo.")
    else:
        print("\n  (simulacao - use --aplicar)")


if __name__ == "__main__":
    main()
