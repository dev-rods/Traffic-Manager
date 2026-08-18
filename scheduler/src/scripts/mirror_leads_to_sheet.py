"""
Mirror leads from the database into the clinic's Google Sheet.

The landing page writes each submission to a Google Sheet through an automation that
lives outside this repository. That automation stopped appending on 2026-08-06 while
`POST /leads` kept persisting every lead, so the sheet silently drifted behind the
database. This script reconciles it: every lead in the database shows up at least
once in the sheet.

Semantics worth knowing before reading the diff logic: the sheet records *submissions*
(someone who submits twice gets two rows), while the database records *people* —
`scheduler.leads` upserts on `UNIQUE(clinic_id, phone, first_name)`. The mirror can
therefore guarantee presence, not reproduce duplicate submissions. A lead counts as
already present when its phone appears anywhere in the sheet, which is what makes
re-running safe.

Dry-run by default: nothing is written without --apply.

Usage:
    cd scheduler
    python -m src.scripts.mirror_leads_to_sheet --clinic <clinic_id> --sheet <spreadsheet_id>
    python -m src.scripts.mirror_leads_to_sheet --clinic <clinic_id> --sheet <spreadsheet_id> --apply

Reads PostgreSQL (leads) and Google Sheets. Writes to the sheet only with --apply.

Both the database and the service account are resolved from SSM by --stage, and the
resolved database host is always printed. That is deliberate: scheduler/.env points at
the dev database while the live leads are in the prod one, so defaulting to the env
vars silently mirrors from the wrong database. Pass --db-from-env to opt back into the
RDS_* environment variables.
"""
import argparse
import json
import os
import re
from datetime import timezone

import pytz
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from src.services.db.postgres import PostgresService
from src.utils.phone import normalize_phone

load_dotenv()

# The sheet records local clinic time. pytz carries its own database, so this works
# on Windows too, where the stdlib zoneinfo has no tzdata to read.
CLINIC_TZ = pytz.timezone("America/Sao_Paulo")

SHEET_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_HEADER = ["Datetime", "origem", "Nome", "Telefone", "Procedimentos", "Observações"]

# `source` in the database is how the lead reached us; `origem` in the sheet is which
# landing page form it came from. For this clinic the generic landing-page source is
# always the depilação form.
ORIGEM_BY_SOURCE = {"landing-page": "depilacao", "harmonizacao": "harmonizacao"}
DEFAULT_SOURCES = ("landing-page", "harmonizacao")

PROCEDIMENTOS_KEYS = ("procedimentos", "procedures", "servicos")
OBSERVACOES_KEYS = ("observacoes", "observações", "observations", "mensagem", "message")


def _ssm_client(aws_profile: str | None):
    import boto3

    session = boto3.Session(profile_name=aws_profile) if aws_profile else boto3.Session()
    return session.client("ssm")


def load_service_account(stage: str, aws_profile: str | None) -> dict:
    """Service account JSON from the env var, falling back to SSM."""
    raw = os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT")
    if raw:
        return json.loads(raw)

    parameter = _ssm_client(aws_profile).get_parameter(
        Name=f"/{stage}/GOOGLE_SHEETS_SERVICE_ACCOUNT", WithDecryption=True
    )
    return json.loads(parameter["Parameter"]["Value"])


def resolve_database(stage: str, aws_profile: str | None, from_env: bool) -> str:
    """Point PostgresService at the right database and return the host for logging.

    PostgresService builds its pool from the RDS_* env vars, so this sets them before
    the first instantiation. Resolving from SSM by stage is the default because the
    checked-in .env points at dev while the leads being mirrored live in prod.
    """
    if from_env:
        return os.environ.get("RDS_HOST") or "(RDS_HOST não definido)"

    ssm = _ssm_client(aws_profile)

    def parameter(name: str) -> str:
        return ssm.get_parameter(Name=f"/{stage}/{name}", WithDecryption=True)["Parameter"]["Value"]

    os.environ["RDS_HOST"] = parameter("SUPABASE_DB_HOST")
    os.environ["RDS_PORT"] = parameter("SUPABASE_DB_PORT")
    os.environ["RDS_DATABASE"] = parameter("SUPABASE_DB_NAME")
    os.environ["RDS_USERNAME"] = parameter("SUPABASE_DB_USER")
    os.environ["RDS_PASSWORD"] = parameter("SUPABASE_DB_PASSWORD")
    return os.environ["RDS_HOST"]


def sheets_service(service_account: dict):
    credentials = Credentials.from_service_account_info(service_account, scopes=SHEET_SCOPES)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def phone_key(raw) -> str:
    """Comparable phone key: DDD + last 8 digits.

    Tolerates the country code being present or not and the mobile 9th digit being
    added or missing, which is exactly how the same number drifts between the sheet
    (typed by hand, stored as a number) and the database (normalized to 55DDDNNNNNNNNN).
    """
    if raw is None:
        return ""
    # A phone column read as a number arrives as 11999961308.0, and stripping
    # non-digits from that string would turn the trailing ".0" into an extra digit.
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)

    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("55") and len(digits) > 11:
        digits = digits[2:]
    if len(digits) < 10:
        return digits
    return digits[:2] + digits[-8:]


def read_sheet_rows(service, spreadsheet_id: str, tab: str) -> list:
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{tab}!A:F")
        .execute()
    )
    return response.get("values", [])


def existing_phone_keys(rows: list) -> set:
    """Phone keys already in the sheet. Column D (index 3) holds the phone."""
    keys = set()
    for row in rows[1:]:  # skip header
        if len(row) > 3 and row[3]:
            key = phone_key(row[3])
            if key:
                keys.add(key)
    return keys


def fetch_leads(db: PostgresService, clinic_id: str, sources: tuple) -> list:
    return db.execute_query(
        """
        SELECT name, phone, source, created_at, metadata, raw_message
        FROM scheduler.leads
        WHERE clinic_id = %s AND source = ANY(%s)
        ORDER BY created_at
        """,
        (clinic_id, list(sources)),
    )


def _from_metadata(metadata, keys: tuple) -> str:
    if not isinstance(metadata, dict):
        return ""
    for key in keys:
        value = metadata.get(key)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)
        return str(value)
    return ""


def to_sheet_row(lead: dict) -> list:
    """One database lead as a sheet row, matching the columns the sheet already uses."""
    created_at = lead["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    local = created_at.astimezone(CLINIC_TZ)

    phone = normalize_phone(lead["phone"] or "")
    if phone.startswith("55") and len(phone) > 11:
        phone = phone[2:]

    return [
        local.strftime("%Y/%m/%d %H:%M:%S"),
        ORIGEM_BY_SOURCE.get(lead["source"], lead["source"] or ""),
        lead["name"] or "",
        phone,
        _from_metadata(lead.get("metadata"), PROCEDIMENTOS_KEYS),
        _from_metadata(lead.get("metadata"), OBSERVACOES_KEYS) or (lead.get("raw_message") or ""),
    ]


def append_rows(service, spreadsheet_id: str, tab: str, rows: list) -> int:
    response = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=f"{tab}!A:F",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        )
        .execute()
    )
    return response.get("updates", {}).get("updatedRows", 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror database leads into the clinic's Google Sheet")
    parser.add_argument("--clinic", required=True, help="clinic_id")
    parser.add_argument("--sheet", required=True, help="spreadsheet id")
    parser.add_argument("--tab", default="Folha1", help="sheet tab name (default: Folha1)")
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help=f"comma-separated lead sources to mirror (default: {','.join(DEFAULT_SOURCES)})",
    )
    parser.add_argument("--stage", default="dev", help="SSM stage for the database (default: dev)")
    parser.add_argument(
        "--sheets-stage",
        default="dev",
        help=(
            "SSM stage holding GOOGLE_SHEETS_SERVICE_ACCOUNT. Separate from --stage because "
            "the service account is one Google identity shared by every environment, and it "
            "currently only exists under /dev (default: dev)"
        ),
    )
    parser.add_argument("--aws-profile", default=None, help="AWS profile for the SSM lookup")
    parser.add_argument(
        "--db-from-env",
        action="store_true",
        help="use the RDS_* env vars instead of resolving the database from SSM",
    )
    parser.add_argument("--apply", action="store_true", help="actually append; without it, dry-run")
    args = parser.parse_args()

    sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())

    service = sheets_service(load_service_account(args.sheets_stage, args.aws_profile))
    rows = read_sheet_rows(service, args.sheet, args.tab)
    present = existing_phone_keys(rows)

    db_host = resolve_database(args.stage, args.aws_profile, args.db_from_env)
    db = PostgresService()
    leads = fetch_leads(db, args.clinic, sources)

    missing = [lead for lead in leads if phone_key(lead["phone"]) not in present]

    print(f"Clinic          : {args.clinic}")
    print(f"Stage           : {args.stage}")
    print(f"Database        : {db_host}")
    print(f"Spreadsheet     : {args.sheet} (tab {args.tab})")
    print(f"Sources         : {', '.join(sources)}")
    print(f"Rows in sheet   : {max(len(rows) - 1, 0)} ({len(present)} distinct phones)")
    print(f"Leads in DB     : {len(leads)}")
    print(f"Missing in sheet: {len(missing)}")

    if not missing:
        print("\nSheet is already in sync. Nothing to do.")
        return

    print("\n--- Rows to append ---")
    for lead in missing:
        row = to_sheet_row(lead)
        print(f"  {row[0]}  {row[1]:<13} {row[2][:26]:<26} {row[3]}")

    if not args.apply:
        print(f"\nDry-run: nothing written. Re-run with --apply to append these {len(missing)} row(s).")
        return

    appended = append_rows(service, args.sheet, args.tab, [to_sheet_row(lead) for lead in missing])
    print(f"\nAppended {appended} row(s) to the sheet.")


if __name__ == "__main__":
    main()
