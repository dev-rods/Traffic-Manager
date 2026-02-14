"""
Migration script: Extract areas from service_areas into new areas table.
Run ONCE before deploying the new schema.

Usage: cd scheduler && python -m src.scripts.migrate_areas
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

MIGRATION_STEPS = [
    # 1. Create the new areas table
    """
    CREATE TABLE IF NOT EXISTS scheduler.areas (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
        name VARCHAR(255) NOT NULL,
        display_order INTEGER DEFAULT 0,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(clinic_id, name)
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_areas_clinic ON scheduler.areas(clinic_id)",

    # 2. Migrate distinct area names from service_areas into areas
    """
    INSERT INTO scheduler.areas (clinic_id, name, display_order, active)
    SELECT DISTINCT s.clinic_id, sa.name, sa.display_order, sa.active
    FROM scheduler.service_areas sa
    JOIN scheduler.services s ON sa.service_id = s.id
    ON CONFLICT (clinic_id, name) DO NOTHING
    """,

    # 3. Add area_id column to service_areas
    "ALTER TABLE scheduler.service_areas ADD COLUMN IF NOT EXISTS area_id UUID",

    # 4. Populate area_id based on name match
    """
    UPDATE scheduler.service_areas sa
    SET area_id = a.id
    FROM scheduler.areas a
    JOIN scheduler.services s ON s.clinic_id = a.clinic_id
    WHERE sa.service_id = s.id AND sa.name = a.name
    """,

    # 5. Drop old columns and add FK + unique constraint
    "ALTER TABLE scheduler.service_areas DROP COLUMN IF EXISTS name",
    "ALTER TABLE scheduler.service_areas DROP COLUMN IF EXISTS display_order",

    # 6. Add FK constraint (only if not exists)
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'fk_service_areas_area'
        ) THEN
            ALTER TABLE scheduler.service_areas
            ADD CONSTRAINT fk_service_areas_area
            FOREIGN KEY (area_id) REFERENCES scheduler.areas(id) ON DELETE CASCADE;
        END IF;
    END $$
    """,

    # 7. Add unique constraint on (service_id, area_id)
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_service_areas_service_area'
        ) THEN
            ALTER TABLE scheduler.service_areas
            ADD CONSTRAINT uq_service_areas_service_area UNIQUE (service_id, area_id);
        END IF;
    END $$
    """,

    # 8. Drop old unique constraint on (service_id, name) if exists
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'service_areas_service_id_name_key'
        ) THEN
            ALTER TABLE scheduler.service_areas DROP CONSTRAINT service_areas_service_id_name_key;
        END IF;
    END $$
    """,

    "CREATE INDEX IF NOT EXISTS idx_service_areas_area ON scheduler.service_areas(area_id)",
]


def main():
    conn = psycopg2.connect(
        host=os.environ.get("RDS_HOST"),
        port=int(os.environ.get("RDS_PORT", "5432")),
        dbname=os.environ.get("RDS_DATABASE"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
    )

    cursor = conn.cursor()

    for i, sql in enumerate(MIGRATION_STEPS):
        try:
            cursor.execute(sql)
            conn.commit()
            label = sql.strip().split('\n')[0][:80]
            print(f"[{i+1}/{len(MIGRATION_STEPS)}] OK: {label}")
        except Exception as e:
            conn.rollback()
            label = sql.strip().split('\n')[0][:80]
            print(f"[{i+1}/{len(MIGRATION_STEPS)}] ERRO: {label} -> {e}")

    cursor.close()
    conn.close()
    print("\nMigration concluida.")


if __name__ == "__main__":
    main()
