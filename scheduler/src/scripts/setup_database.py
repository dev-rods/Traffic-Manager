"""
Script para criar o schema e tabelas do scheduler no PostgreSQL.
Executar localmente: python -m src.scripts.setup_database
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SQL_STATEMENTS = [
    # Schema
    "CREATE SCHEMA IF NOT EXISTS scheduler",

    # Clínicas (tenants)
    """
    CREATE TABLE IF NOT EXISTS scheduler.clinics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        phone VARCHAR(20),
        address TEXT,
        timezone VARCHAR(50) DEFAULT 'America/Sao_Paulo',
        business_hours JSONB NOT NULL,
        buffer_minutes INTEGER DEFAULT 10,
        welcome_message TEXT,
        pre_session_instructions TEXT,
        zapi_instance_id VARCHAR(255),
        zapi_instance_token VARCHAR(255),
        google_spreadsheet_id VARCHAR(255),
        google_sheet_name VARCHAR(100) DEFAULT 'Agenda',
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # Serviços
    """
    CREATE TABLE IF NOT EXISTS scheduler.services (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        name VARCHAR(255) NOT NULL,
        duration_minutes INTEGER NOT NULL,
        price_cents INTEGER,
        description TEXT,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # Profissionais
    """
    CREATE TABLE IF NOT EXISTS scheduler.professionals (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        name VARCHAR(255) NOT NULL,
        role VARCHAR(100),
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # Regras de disponibilidade
    """
    CREATE TABLE IF NOT EXISTS scheduler.availability_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        professional_id UUID REFERENCES scheduler.professionals(id),
        day_of_week INTEGER NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # Exceções de disponibilidade
    """
    CREATE TABLE IF NOT EXISTS scheduler.availability_exceptions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        exception_date DATE NOT NULL,
        exception_type VARCHAR(20) NOT NULL,
        start_time TIME,
        end_time TIME,
        reason VARCHAR(255),
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # Pacientes
    """
    CREATE TABLE IF NOT EXISTS scheduler.patients (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        phone VARCHAR(20) NOT NULL,
        name VARCHAR(255),
        gender VARCHAR(1) CHECK (gender IN ('M', 'F')),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(clinic_id, phone)
    )
    """,

    # Agendamentos
    """
    CREATE TABLE IF NOT EXISTS scheduler.appointments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        patient_id UUID REFERENCES scheduler.patients(id),
        professional_id UUID REFERENCES scheduler.professionals(id),
        service_id UUID REFERENCES scheduler.services(id),
        appointment_date DATE NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        areas TEXT,
        status VARCHAR(20) DEFAULT 'CONFIRMED',
        notes TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        version INTEGER DEFAULT 1
    )
    """,

    # Templates de mensagem
    """
    CREATE TABLE IF NOT EXISTS scheduler.message_templates (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        template_key VARCHAR(100) NOT NULL,
        content TEXT NOT NULL,
        buttons JSONB,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(clinic_id, template_key)
    )
    """,

    # FAQ
    """
    CREATE TABLE IF NOT EXISTS scheduler.faq_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        question_key VARCHAR(100) NOT NULL,
        question_label VARCHAR(255) NOT NULL,
        answer TEXT NOT NULL,
        display_order INTEGER DEFAULT 0,
        active BOOLEAN DEFAULT TRUE,
        UNIQUE(clinic_id, question_key)
    )
    """,

    # Areas de tratamento (independentes, reutilizaveis entre servicos)
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

    # Junction: servico <-> area
    """
    CREATE TABLE IF NOT EXISTS scheduler.service_areas (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        service_id UUID NOT NULL REFERENCES scheduler.services(id) ON DELETE CASCADE,
        area_id UUID NOT NULL REFERENCES scheduler.areas(id) ON DELETE CASCADE,
        duration_minutes INTEGER,
        price_cents INTEGER,
        pre_session_instructions TEXT,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(service_id, area_id)
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_service_areas_service ON scheduler.service_areas(service_id)",
    "CREATE INDEX IF NOT EXISTS idx_service_areas_area ON scheduler.service_areas(area_id)",

    # Appointment-services junction table (multi-service per appointment)
    """
    CREATE TABLE IF NOT EXISTS scheduler.appointment_services (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        appointment_id UUID NOT NULL REFERENCES scheduler.appointments(id) ON DELETE CASCADE,
        service_id UUID NOT NULL REFERENCES scheduler.services(id),
        service_name VARCHAR(255) NOT NULL,
        duration_minutes INTEGER NOT NULL,
        price_cents INTEGER,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(appointment_id, service_id)
    )
    """,

    # Add total_duration_minutes to appointments
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS total_duration_minutes INTEGER",

    # Add rule_date column to availability_rules (fixed-date rules)
    "ALTER TABLE scheduler.availability_rules ALTER COLUMN day_of_week DROP NOT NULL",
    "ALTER TABLE scheduler.availability_rules ADD COLUMN IF NOT EXISTS rule_date DATE",

    # Check constraint: either day_of_week or rule_date, never both
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'chk_rule_type'
        ) THEN
            ALTER TABLE scheduler.availability_rules
            ADD CONSTRAINT chk_rule_type CHECK (
                (day_of_week IS NOT NULL AND rule_date IS NULL)
                OR (day_of_week IS NULL AND rule_date IS NOT NULL)
            );
        END IF;
    END $$
    """,

    "CREATE INDEX IF NOT EXISTS idx_availability_rules_date ON scheduler.availability_rules(clinic_id, rule_date)",

    # Add max_future_dates to clinics
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS max_future_dates INTEGER DEFAULT 5",

    # Add gender to patients
    "ALTER TABLE scheduler.patients ADD COLUMN IF NOT EXISTS gender VARCHAR(1) CHECK (gender IN ('M', 'F'))",

    # Unique constraints
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_availability_rules_clinic_day'
        ) THEN
            ALTER TABLE scheduler.availability_rules
            ADD CONSTRAINT uq_availability_rules_clinic_day UNIQUE (clinic_id, day_of_week);
        END IF;
    END $$
    """,

    # Índices
    "CREATE INDEX IF NOT EXISTS idx_appointments_clinic_date ON scheduler.appointments(clinic_id, appointment_date)",
    "CREATE INDEX IF NOT EXISTS idx_appointments_patient ON scheduler.appointments(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_appointments_status ON scheduler.appointments(clinic_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_patients_phone ON scheduler.patients(clinic_id, phone)",
    "CREATE INDEX IF NOT EXISTS idx_availability_rules_clinic ON scheduler.availability_rules(clinic_id, day_of_week)",
    "CREATE INDEX IF NOT EXISTS idx_availability_exceptions_clinic ON scheduler.availability_exceptions(clinic_id, exception_date)",
    "CREATE INDEX IF NOT EXISTS idx_appointment_services_appointment ON scheduler.appointment_services(appointment_id)",

    # Add duration_minutes override to service_areas (nullable, falls back to services.duration_minutes)
    "ALTER TABLE scheduler.service_areas ADD COLUMN IF NOT EXISTS duration_minutes INTEGER",

    # Add price_cents override to service_areas (nullable, falls back to services.price_cents)
    "ALTER TABLE scheduler.service_areas ADD COLUMN IF NOT EXISTS price_cents INTEGER",

    # Add pre_session_instructions to service_areas (hierarchical: service_area > clinic)
    "ALTER TABLE scheduler.service_areas ADD COLUMN IF NOT EXISTS pre_session_instructions TEXT",
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

    for i, sql in enumerate(SQL_STATEMENTS):
        try:
            cursor.execute(sql)
            conn.commit()
            label = sql.strip().split('\n')[0][:80]
            print(f"[{i+1}/{len(SQL_STATEMENTS)}] OK: {label}")
        except Exception as e:
            conn.rollback()
            label = sql.strip().split('\n')[0][:80]
            print(f"[{i+1}/{len(SQL_STATEMENTS)}] ERRO: {label} -> {e}")

    cursor.close()
    conn.close()
    print("\nSetup concluído.")


if __name__ == "__main__":
    main()
