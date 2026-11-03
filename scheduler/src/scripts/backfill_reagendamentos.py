# -*- coding: utf-8 -*-
"""Liga, no passado, os cancelamentos que eram remarcações (PRD 035).

Medido em prod em 01/11/2026: 37 dos 117 CANCELLED dos últimos 60 dias tinham
outro agendamento do mesmo paciente criado logo depois. O site só tinha
"cancelar", e a recepção cancela e recria. Para a frente, `create_appointment`
já faz o vínculo. Este script faz para trás.

NÃO reimplementa a regra: para cada agendamento criado desde `--desde`, chama
`vincula_antecessor`, a mesma função do create, com o `created_at` do
registro como referência. Idempotente: o UPDATE exige
`rescheduled_to_id IS NULL`, e a segunda execução não liga nada.

Fora de propósito: agendamentos de importação (antecessor com data anterior
a 01/09/2026) e conversões do Google Ads. As conversões dos pares antigos já
subiram ou não, e mexer nelas agora é assunto do PRD 016/017.

    python -m src.scripts.backfill_reagendamentos <clinic_id>              # dry-run
    python -m src.scripts.backfill_reagendamentos <clinic_id> --aplicar
    python -m src.scripts.backfill_reagendamentos <clinic_id> --desde 2026-09-01
"""
import sys
from datetime import date

from src.services.db.postgres import PostgresService
from src.services.reagendamento import candidato_a_antecessor, vincula_antecessor

DESDE_PADRAO = "2026-09-01"
# Antes disto é histórico importado em 08 e 09/09/2026, não remarcação.
DATA_MINIMA_DO_ANTECESSOR = date(2026, 9, 1)

NOVOS = """
    SELECT id, clinic_id, patient_id, appointment_date, status, created_at
    FROM scheduler.appointments
    WHERE clinic_id = %s AND created_at >= %s::date AND patient_id IS NOT NULL
    ORDER BY created_at
"""


def _argumentos(argv):
    argv = list(argv)
    desde = DESDE_PADRAO
    if "--desde" in argv:
        i = argv.index("--desde")
        desde = argv[i + 1]
        del argv[i:i + 2]
    posicionais = [a for a in argv if not a.startswith("--")]
    return posicionais, "--aplicar" in argv, desde


def roda(db, clinic_id, aplicar, desde=DESDE_PADRAO, saida=print):
    """Devolve a lista de pares (antecessor, novo) encontrados ou ligados."""
    pares = []
    ligados = {}  # antecessor -> novo, nesta execução
    for novo in db.execute_query(NOVOS, (clinic_id, desde)):
        candidato = candidato_a_antecessor(db, novo)
        if not candidato:
            continue
        if candidato["appointment_date"] < DATA_MINIMA_DO_ANTECESSOR:
            continue
        # Um antecessor só liga a um novo. No apply o UPDATE já garante isso
        # (`rescheduled_to_id IS NULL`); no dry-run precisa ser dito aqui, senão
        # o mesmo cancelado aparece para cada novo criado na janela.
        if str(candidato["id"]) in ligados:
            continue
        # Dois cancelados criados perto um do outro apontariam um para o outro.
        if ligados.get(str(novo["id"])) == str(candidato["id"]):
            continue
        if aplicar:
            ligado = vincula_antecessor(db, novo)
            if not ligado:
                continue
        delta = (novo["created_at"] - candidato["updated_at"]).total_seconds() / 60
        ligados[str(candidato["id"])] = str(novo["id"])
        pares.append((str(candidato["id"]), str(novo["id"])))
        saida(f"{'LIGADO ' if aplicar else 'LIGARIA'} {candidato['appointment_date']} -> "
              f"{novo['appointment_date']} ({novo['status']}, {delta:+.0f} min) "
              f"antecessor={candidato['id']} novo={novo['id']}")
    saida(f"{'ligados' if aplicar else 'a ligar'}: {len(pares)}"
          + ("" if aplicar else "  (dry-run; use --aplicar para gravar)"))
    return pares


def main():
    posicionais, aplicar, desde = _argumentos(sys.argv[1:])
    if not posicionais:
        print("uso: python -m src.scripts.backfill_reagendamentos <clinic_id> [--aplicar] [--desde YYYY-MM-DD]")
        raise SystemExit(2)
    roda(PostgresService(), posicionais[0], aplicar, desde)


if __name__ == "__main__":
    main()
