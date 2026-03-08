"""
Seed a clinic user for dev/testing.
Run: cd scheduler && python -m src.scripts.seed_user
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

# Add project root to path so we can import the auth module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.functions.auth.login import hash_password_for_storage

load_dotenv()

EMAIL = "rodrigocardosodevrods@gmail.com"
PASSWORD = "admin123"
CLINIC_ID = "clinicadorods-da7b62"
NAME = "Rodrigo"


def main():
    conn = psycopg2.connect(
        host=os.environ.get("RDS_HOST"),
        port=int(os.environ.get("RDS_PORT", "5432")),
        dbname=os.environ.get("RDS_DATABASE"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
    )
    cursor = conn.cursor()

    password_hash = hash_password_for_storage(PASSWORD)

    cursor.execute("""
        INSERT INTO scheduler.clinic_users (clinic_id, email, password_hash, name, active)
        VALUES (%s, %s, %s, %s, TRUE)
        ON CONFLICT (email) DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            updated_at = NOW()
    """, (CLINIC_ID, EMAIL, password_hash, NAME))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"User seeded: {EMAIL} / {PASSWORD} -> clinic {CLINIC_ID}")


if __name__ == "__main__":
    main()
