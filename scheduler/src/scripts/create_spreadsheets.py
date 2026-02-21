"""
Script para criar planilhas Google Sheets para clinicas existentes
que possuem owner_email mas ainda nao tem google_spreadsheet_id.

Executar: cd scheduler && python -m src.scripts.create_spreadsheets
"""
import os
import sys
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# Reutiliza SheetsSync para criacao
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.services.sheets_sync import SheetsSync


class SimpleDB:
    """Minimal DB wrapper matching PostgresService interface for SheetsSync."""

    def __init__(self, conn):
        self.conn = conn

    def execute_query(self, query, params=None):
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return [dict(r) for r in rows]

    def execute_write_returning(self, query, params=None):
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, params)
        row = cursor.fetchone()
        self.conn.commit()
        cursor.close()
        return dict(row) if row else None


def main():
    conn = psycopg2.connect(
        host=os.environ.get("RDS_HOST"),
        port=int(os.environ.get("RDS_PORT", "5432")),
        dbname=os.environ.get("RDS_DATABASE"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
    )

    db = SimpleDB(conn)

    # Buscar clinicas com owner_email mas sem spreadsheet
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT clinic_id, name, owner_email
        FROM scheduler.clinics
        WHERE owner_email IS NOT NULL
          AND owner_email != ''
          AND (google_spreadsheet_id IS NULL OR google_spreadsheet_id = '')
          AND active = TRUE
        ORDER BY created_at
        """
    )
    clinics = [dict(r) for r in cursor.fetchall()]
    cursor.close()

    if not clinics:
        print("Nenhuma clinica encontrada sem planilha (com owner_email).")
        return

    print(f"Encontradas {len(clinics)} clinica(s) para criar planilha:\n")
    for c in clinics:
        print(f"  - {c['clinic_id']} | {c['name']} | {c['owner_email']}")

    print()
    confirm = input("Criar planilhas? (s/N): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    sheets = SheetsSync(db)

    created = 0
    for c in clinics:
        clinic_id = c["clinic_id"]
        name = c["name"]
        email = c["owner_email"]

        print(f"\n[{clinic_id}] Criando planilha para '{name}'...")

        spreadsheet_id = sheets.create_spreadsheet(name, email)
        if not spreadsheet_id:
            print(f"  ERRO: Falha ao criar planilha")
            continue

        # Atualizar no banco
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE scheduler.clinics SET google_spreadsheet_id = %s, updated_at = NOW() WHERE clinic_id = %s",
            (spreadsheet_id, clinic_id),
        )
        conn.commit()
        cursor.close()

        print(f"  OK: spreadsheet_id={spreadsheet_id}")
        created += 1

    conn.close()
    print(f"\nConcluido: {created}/{len(clinics)} planilhas criadas.")


if __name__ == "__main__":
    main()
