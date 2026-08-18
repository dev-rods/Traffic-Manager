## How to run a script

# Setup database
python -m src.scripts.setup_database

# Create spreadsheets
python -m src.scripts.create_spreadsheets

# Audit a batch send: who was skipped, who got it twice (read-only)
python -m src.scripts.audit_batch_coverage --clinic <clinic_id> --date 2026-07-22 \
    --from 13:30 --to 15:30 --csv ../../nao_receberam.csv

# Mirror leads from the database into the clinic's Google Sheet.
# Dry-run by default; --apply is what actually appends. Safe to re-run.
python -m src.scripts.mirror_leads_to_sheet --clinic <clinic_id> --sheet <spreadsheet_id> \
    --stage prod --aws-profile <profile>
python -m src.scripts.mirror_leads_to_sheet --clinic <clinic_id> --sheet <spreadsheet_id> \
    --stage prod --aws-profile <profile> --apply