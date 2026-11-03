# -*- coding: utf-8 -*-
"""Une os cadastros duplicados que o PRD 033 explicou (Essência, out/2026).

Dois casos, ambos criados pelo site porque o telefone não casava:

- Paula Schimmelpfeng: original `553591328559` (bot, com CPF e e-mail);
  duplicado `5535991328559` (site, com o 9). Os agendamentos do duplicado vão
  para o original, o duplicado é apagado (soft-delete).
- Isadora Pires: original `5531617223202` (bot, com o 55 indevido); duplicado
  `5511971694536` (site, número da mãe). O telefone do original passa a ser
  `31617223202`, como o WhatsApp entrega. O agendamento feito no número da mãe
  vai para o original; o duplicado é apagado.

Idempotente: cada passo confere o estado antes de escrever. Uso:

    RDS_* no ambiente (ver memória de acesso), depois
    python -m src.scripts.une_cadastros_duplicados_033 [--aplica]

Sem `--aplica` só mostra o que faria.
"""
import sys

from src.services.db.postgres import PostgresService

CLINIC = "clinicaessenciaestetica-9668a4"

CASOS = [
    {"quem": "Paula Schimmelpfeng", "original": "553591328559",
     "duplicado": "5535991328559", "telefone_final": "553591328559"},
    {"quem": "Isadora Pires", "original": "5531617223202",
     "duplicado": "5511971694536", "telefone_final": "31617223202"},
]


def _paciente(db, phone):
    linhas = db.execute_query(
        "SELECT id, name, phone, deleted_at FROM scheduler.patients "
        "WHERE clinic_id = %s AND phone = %s",
        (CLINIC, phone),
    )
    return linhas[0] if linhas else None


def _agendamentos(db, patient_id):
    return db.execute_query(
        "SELECT id, appointment_date, start_time, status FROM scheduler.appointments "
        "WHERE patient_id = %s::uuid ORDER BY appointment_date, start_time",
        (str(patient_id),),
    )


def main(aplica: bool) -> int:
    db = PostgresService()
    for caso in CASOS:
        print(f"\n== {caso['quem']}")
        original = _paciente(db, caso["original"]) or _paciente(db, caso["telefone_final"])
        duplicado = _paciente(db, caso["duplicado"])
        if not original:
            print("  original não encontrado; nada a fazer")
            continue
        print(f"  original  {original['phone']} id={original['id']}")
        if duplicado and duplicado.get("deleted_at") is None:
            ags = _agendamentos(db, duplicado["id"])
            print(f"  duplicado {duplicado['phone']} id={duplicado['id']} "
                  f"com {len(ags)} agendamento(s): "
                  + ", ".join(f"{a['appointment_date']} {str(a['start_time'])[:5]} {a['status']}" for a in ags))
            if aplica:
                db.execute_write(
                    "UPDATE scheduler.appointments SET patient_id = %s::uuid, updated_at = NOW() "
                    "WHERE patient_id = %s::uuid",
                    (str(original["id"]), str(duplicado["id"])),
                )
                db.execute_write(
                    "UPDATE scheduler.patients SET deleted_at = NOW(), updated_at = NOW() "
                    "WHERE id = %s::uuid",
                    (str(duplicado["id"]),),
                )
                print("  -> agendamentos movidos e duplicado apagado")
        else:
            print("  duplicado já ausente ou apagado")

        if original["phone"] != caso["telefone_final"]:
            print(f"  telefone {original['phone']} -> {caso['telefone_final']}")
            if aplica:
                db.execute_write(
                    "UPDATE scheduler.patients SET phone = %s, updated_at = NOW() WHERE id = %s::uuid",
                    (caso["telefone_final"], str(original["id"])),
                )
                print("  -> telefone corrigido")

    print("\n" + ("APLICADO" if aplica else "SIMULAÇÃO: rode com --aplica para gravar"))
    return 0


if __name__ == "__main__":
    sys.exit(main("--aplica" in sys.argv))
