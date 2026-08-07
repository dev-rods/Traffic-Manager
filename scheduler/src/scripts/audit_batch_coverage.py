"""
Audit coverage of a batch message send: who was skipped and who got it twice.

The patients list used to paginate with `ORDER BY created_at DESC` over rows sharing an
identical created_at (bulk import), so OFFSET pages overlapped and skipped — some patients
never appeared on any page and never received the campaign, others appeared twice and got
it twice. This script reconciles the clinic's patient base against what was actually sent,
so the clinic can reach the skipped ones by other channels.

Usage:
    cd scheduler
    python -m src.scripts.audit_batch_coverage --clinic <clinic_id> --date 2026-07-22
    python -m src.scripts.audit_batch_coverage --clinic <clinic_id> --date 2026-07-22 \
        --from 13:00 --to 16:00 --csv skipped_2026-07-22.csv

Reads DynamoDB (message events) and PostgreSQL (patient base) — no writes.
Requires the same env vars as the Lambdas: MESSAGE_EVENTS_TABLE, RDS_*, AWS credentials.
"""
import argparse
import csv
import os
from collections import Counter

import boto3
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv

from src.services.db.postgres import PostgresService

load_dotenv()


def fetch_sent(table, clinic_id: str, start_iso: str, end_iso: str) -> list:
    """OUTBOUND sends the provider accepted, within [start_iso, end_iso]."""
    items, last_key = [], None
    while True:
        kwargs = {
            "IndexName": "clinicId-statusTimestamp-index",
            "KeyConditionExpression": Key("clinicId").eq(clinic_id)
            & Key("statusTimestamp").between(f"SENT#{start_iso}", f"SENT#{end_iso}"),
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
    return [i for i in items if i.get("direction") == "OUTBOUND"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit batch send coverage")
    parser.add_argument("--clinic", required=True, help="clinic_id")
    parser.add_argument("--date", required=True, help="send date, YYYY-MM-DD (UTC)")
    parser.add_argument("--from", dest="start", default="00:00", help="start time UTC, HH:MM")
    parser.add_argument("--to", dest="end", default="23:59", help="end time UTC, HH:MM")
    parser.add_argument("--csv", help="write the skipped patients to this CSV path")
    args = parser.parse_args()

    start_iso = f"{args.date}T{args.start}:00Z"
    end_iso = f"{args.date}T{args.end}:59Z"

    table = boto3.resource("dynamodb").Table(os.environ["MESSAGE_EVENTS_TABLE"])
    sends = fetch_sent(table, args.clinic, start_iso, end_iso)
    per_phone = Counter(s["phone"] for s in sends)

    db = PostgresService()
    patients = db.execute_query(
        """SELECT phone, name FROM scheduler.patients
           WHERE clinic_id = %s AND deleted_at IS NULL
           ORDER BY name""",
        (args.clinic,),
    )

    skipped = [p for p in patients if per_phone.get(p["phone"], 0) == 0]
    duplicated = [p for p in patients if per_phone.get(p["phone"], 0) > 1]
    # Sends whose phone has no patient row — usually a cadastro fixed or removed afterwards
    known_phones = {p["phone"] for p in patients}
    orphan_phones = sorted(set(per_phone) - known_phones)

    print(f"Clinic          : {args.clinic}")
    print(f"Window (UTC)    : {start_iso} -> {end_iso}")
    print(f"Active patients : {len(patients)}")
    print(f"Sends recorded  : {len(sends)} ({len(per_phone)} distinct phones)")
    print(f"NOT REACHED     : {len(skipped)}")
    print(f"Sent twice+     : {len(duplicated)}")
    print(f"Sends w/o patient row: {len(orphan_phones)}")

    if skipped:
        print("\n--- Not reached ---")
        for p in skipped:
            print(f"  {p['phone']:<15} {p['name']}")

    if duplicated:
        print("\n--- Received more than once ---")
        for p in duplicated:
            print(f"  {p['phone']:<15} {p['name']} (x{per_phone[p['phone']]})")

    if orphan_phones:
        print("\n--- Sent to phones with no patient row ---")
        for phone in orphan_phones:
            print(f"  {phone:<15} (x{per_phone[phone]})")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["phone", "name", "sends_in_window"])
            for p in skipped:
                writer.writerow([p["phone"], p["name"], 0])
        print(f"\nWrote {len(skipped)} rows to {args.csv}")


if __name__ == "__main__":
    main()
