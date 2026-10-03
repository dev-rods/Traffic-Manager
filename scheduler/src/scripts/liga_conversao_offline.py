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

A conversao da Essencia, criada a mao em 27/09/2026, e a 7699541177.
"""
import sys

from src.services.db.postgres import PostgresService

APLICAR = "--aplicar" in sys.argv


def listar(d):
    """Mostra o estado de cada clinica. E daqui que sai o clinic_id correto."""
    linhas = d.execute_query(
        "SELECT clinic_id, name, google_ads_customer_id, offline_conversion_action_id "
        "FROM scheduler.clinics ORDER BY clinic_id", ())
    print("%-28s %-22s %-14s %s" % ("clinic_id", "nome", "conta ads", "conversao"))
    for c in linhas:
        print("%-28s %-22s %-14s %s" % (
            c["clinic_id"], (c["name"] or "")[:22],
            c["google_ads_customer_id"] or "-",
            c["offline_conversion_action_id"] or "(vazio)"))
    print("\nPara ligar:  python -m src.scripts.liga_conversao_offline "
          "<clinic_id> <action_id> --aplicar")


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
        "SELECT clinic_id, name, google_ads_customer_id, offline_conversion_action_id "
        "FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,))

    print("=== %s ===" % clinic_id)
    if not linhas:
        print("  !! clinica NAO existe neste banco.")
        print("     (dev e prod sao bancos diferentes - conferir em qual voce esta)")
        raise SystemExit(1)

    c = linhas[0]
    atual = c["offline_conversion_action_id"]
    print("  nome:             %s" % c["name"])

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

    print("  conta Google Ads: %s" % c["google_ads_customer_id"])
    print("  conversao:        (vazio) -> %s" % action_id)

    if APLICAR:
        d.execute_write(
            "UPDATE scheduler.clinics SET offline_conversion_action_id = %s, "
            "updated_at = NOW() WHERE clinic_id = %s", (action_id, clinic_id))
        print("\n  APLICADO. O uploader passa a enxergar a clinica no proximo ciclo.")
    else:
        print("\n  (simulacao - use --aplicar)")


if __name__ == "__main__":
    main()
