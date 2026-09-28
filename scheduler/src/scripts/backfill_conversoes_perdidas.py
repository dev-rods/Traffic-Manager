# -*- coding: utf-8 -*-
"""Recupera as conversoes que nunca foram gravadas por causa do lead_service=None.

`AppointmentService` recebia `lead_service` opcional, e varios caminhos de
criacao de agendamento o construiam sem ele. Esses caminhos entravam no
`if self.lead_service:` e saiam: o agendamento acontecia, o lead ficava como
nao-convertido e a linha em `lead_conversions` nunca existia. Medido na
Essencia: 57% dos agendamentos vindos de anuncio ficaram invisiveis para o
Google.

O buraco foi fechado com `AppointmentService.completo()`, mas o passado nao se
conserta sozinho - este script refaz o que aquele `if` pulou.

NAO reimplementa a regra. Chama `record_conversion` e `mark_as_booked`, os
mesmos metodos que o fluxo normal chamaria, para que a resolucao de lead
(telefone normalizado, primeiro nome, preferencia por gclid) seja exatamente a
mesma. Idempotente: `record_conversion` tem ON CONFLICT (appointment_id) e
`mark_as_booked` so mexe em lead com booked = FALSE.

Agendamento cancelado tambem e gravado, de proposito: o uploader e quem decide
o que sobe, e ele ja filtra por CONFIRMED.

    python -m src.scripts.backfill_conversoes_perdidas <clinic_id>
    python -m src.scripts.backfill_conversoes_perdidas <clinic_id> --aplicar
"""
import sys

from src.services.db.postgres import PostgresService
from src.services.lead_service import LeadService

APLICAR = "--aplicar" in sys.argv


# Agendamentos de uma pessoa que tem lead com gclid, e que nunca viraram linha
# em lead_conversions. O LEFT JOIN ... IS NULL e o coracao: e a diferenca entre
# o que aconteceu e o que foi contado.
ORFAOS = """
    SELECT a.id, a.appointment_date, a.start_time, a.status,
           a.final_price_cents, a.full_name,
           p.phone, p.name AS patient_name
    FROM scheduler.appointments a
    JOIN scheduler.patients p ON p.id = a.patient_id
    LEFT JOIN scheduler.lead_conversions lc ON lc.appointment_id = a.id
    WHERE a.clinic_id = %s
      AND lc.id IS NULL
      AND EXISTS (
          SELECT 1 FROM scheduler.leads l
          WHERE l.clinic_id = a.clinic_id
            AND l.phone = p.phone
            AND l.gclid IS NOT NULL AND l.gclid <> ''
      )
    ORDER BY a.appointment_date, a.start_time
"""


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argumentos:
        print("uso: python -m src.scripts.backfill_conversoes_perdidas <clinic_id> [--aplicar]")
        raise SystemExit(2)
    clinic_id = argumentos[0]

    d = PostgresService()
    leads = LeadService(d)

    orfaos = d.execute_query(ORFAOS, (clinic_id,))
    if not orfaos:
        print("Nada a recuperar em %s." % clinic_id)
        return

    print("%d agendamento(s) sem conversao gravada em %s:\n" % (len(orfaos), clinic_id))

    gravadas = 0
    valor = 0
    for a in orfaos:
        nome = a["full_name"] or a["patient_name"]
        cents = a["final_price_cents"] or 0
        print("  %s %s  %-28s %-9s R$ %8.2f" % (
            a["appointment_date"], str(a["start_time"])[:5], (nome or "?")[:28],
            a["status"], cents / 100.0))

        if not APLICAR:
            continue

        conv = leads.record_conversion(
            clinic_id=clinic_id,
            phone=a["phone"],
            name=nome,
            appointment_id=str(a["id"]),
            value_cents=cents,
            # mesmo formato do fluxo normal: hora da sessao no fuso da clinica
            conversion_date="%s %s-03:00" % (a["appointment_date"], a["start_time"]),
        )
        if conv:
            gravadas += 1
            valor += cents
            # o mesmo `if` pulava os dois; o lead tambem ficou por marcar
            leads.mark_as_booked(
                clinic_id=clinic_id, phone=a["phone"], appointment_id=str(a["id"]),
                appointment_value=cents / 100.0 if cents else None, name=nome,
            )
        else:
            print("      (sem lead com gclid resolvivel - nao gravado)")

    if APLICAR:
        print("\n%d conversao(oes) gravada(s), R$ %.2f." % (gravadas, valor / 100.0))
        print("Sobem no proximo ciclo do uploader (segunda, 7h BRT).")
    else:
        print("\n(simulacao - use --aplicar)")


if __name__ == "__main__":
    main()
