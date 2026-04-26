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
        google_spreadsheet_id VARCHAR(255),  -- DEPRECATED: will be dropped by migration
        google_sheet_name VARCHAR(100) DEFAULT 'Agenda',  -- DEPRECATED: will be dropped by migration
        owner_email VARCHAR(255),
        max_session_minutes INTEGER DEFAULT 60,
        welcome_intro_message TEXT,
        display_name VARCHAR(255),
        use_agent BOOLEAN DEFAULT FALSE,
        bot_paused BOOLEAN DEFAULT FALSE,
        batch_message_template TEXT,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # Unidades (filhos da clinic — fronteira operacional)
    # 1 clinic pode ter N units; cada unit tem agenda/profissionais/preços próprios
    # zapi_instance_id é opcional: se NULL, herda da clinic (fallback no webhook)
    """
    CREATE TABLE IF NOT EXISTS scheduler.units (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(100) NOT NULL,
        address TEXT,
        timezone VARCHAR(50) NOT NULL DEFAULT 'America/Sao_Paulo',
        business_hours JSONB DEFAULT '{}',
        buffer_minutes INTEGER DEFAULT 0,
        zapi_instance_id VARCHAR(255),
        max_future_dates INTEGER DEFAULT 5,
        active BOOLEAN DEFAULT TRUE,
        metadata JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(clinic_id, slug)
    )
    """,

    # Serviços
    # unit_id NULL = padrão da clinic (vale para todas units); NOT NULL = override desta unit
    """
    CREATE TABLE IF NOT EXISTS scheduler.services (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        unit_id UUID REFERENCES scheduler.units(id),
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

    # Junction profissional <-> unidade (M2M)
    # Profissional pode atuar em N unidades; flag active permite ativar/desativar por unit
    """
    CREATE TABLE IF NOT EXISTS scheduler.professionals_units (
        professional_id UUID NOT NULL REFERENCES scheduler.professionals(id) ON DELETE CASCADE,
        unit_id UUID NOT NULL REFERENCES scheduler.units(id) ON DELETE CASCADE,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (professional_id, unit_id)
    )
    """,

    # Regras de disponibilidade
    # unit_id é a fronteira da agenda — sempre obrigatório operacionalmente (NOT NULL após Fase 3)
    """
    CREATE TABLE IF NOT EXISTS scheduler.availability_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        unit_id UUID REFERENCES scheduler.units(id),
        professional_id UUID REFERENCES scheduler.professionals(id),
        day_of_week INTEGER NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,

    # Exceções de disponibilidade (sempre por unit operacionalmente)
    """
    CREATE TABLE IF NOT EXISTS scheduler.availability_exceptions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        unit_id UUID REFERENCES scheduler.units(id),
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
        last_message_at TIMESTAMPTZ,
        deleted_at TIMESTAMPTZ,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(clinic_id, phone)
    )
    """,

    # Agendamentos (sempre por unit operacionalmente)
    """
    CREATE TABLE IF NOT EXISTS scheduler.appointments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        unit_id UUID REFERENCES scheduler.units(id),
        patient_id UUID REFERENCES scheduler.patients(id),
        professional_id UUID REFERENCES scheduler.professionals(id),
        service_id UUID REFERENCES scheduler.services(id),
        appointment_date DATE NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        status VARCHAR(20) DEFAULT 'CONFIRMED',
        notes TEXT,
        full_name VARCHAR(255),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        version INTEGER DEFAULT 1
    )
    """,

    # Templates de mensagem
    # unit_id NULL = padrão da clinic; NOT NULL = override desta unit
    # Constraint UNIQUE(clinic_id, template_key) será substituída por partial unique indexes na migration 009
    """
    CREATE TABLE IF NOT EXISTS scheduler.message_templates (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        unit_id UUID REFERENCES scheduler.units(id),
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
    # unit_id NULL = padrão da clinic; NOT NULL = override desta unit
    """
    CREATE TABLE IF NOT EXISTS scheduler.faq_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
        unit_id UUID REFERENCES scheduler.units(id),
        question_key VARCHAR(100) NOT NULL,
        question_label VARCHAR(255) NOT NULL,
        answer TEXT NOT NULL,
        display_order INTEGER DEFAULT 0,
        active BOOLEAN DEFAULT TRUE,
        UNIQUE(clinic_id, question_key)
    )
    """,

    # Areas de tratamento (independentes, reutilizaveis entre servicos)
    # unit_id NULL = padrão da clinic; NOT NULL = override desta unit
    """
    CREATE TABLE IF NOT EXISTS scheduler.areas (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
        unit_id UUID REFERENCES scheduler.units(id),
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
    # unit_id NULL = preço padrão da clinic; NOT NULL = override desta unit (preço/duração)
    """
    CREATE TABLE IF NOT EXISTS scheduler.service_areas (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        service_id UUID NOT NULL REFERENCES scheduler.services(id) ON DELETE CASCADE,
        unit_id UUID REFERENCES scheduler.units(id),
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

    # Appointment-service-areas junction table (normalized areas per appointment)
    """
    CREATE TABLE IF NOT EXISTS scheduler.appointment_service_areas (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        appointment_id UUID NOT NULL REFERENCES scheduler.appointments(id) ON DELETE CASCADE,
        service_id UUID NOT NULL REFERENCES scheduler.services(id),
        area_id UUID NOT NULL REFERENCES scheduler.areas(id),
        area_name VARCHAR(255) NOT NULL,
        service_name VARCHAR(255) NOT NULL,
        duration_minutes INTEGER NOT NULL,
        price_cents INTEGER,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(appointment_id, service_id, area_id)
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_appt_svc_areas_appointment ON scheduler.appointment_service_areas(appointment_id)",

    # Drop legacy TEXT areas column from appointments
    "ALTER TABLE scheduler.appointments DROP COLUMN IF EXISTS areas",

    # Add owner_email to clinics
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS owner_email VARCHAR(255)",

    # Discount rules per clinic (configurable progressive discounts)
    """
    CREATE TABLE IF NOT EXISTS scheduler.discount_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
        first_session_discount_pct INTEGER NOT NULL DEFAULT 0,
        tier_2_min_areas INTEGER NOT NULL DEFAULT 2,
        tier_2_max_areas INTEGER NOT NULL DEFAULT 4,
        tier_2_discount_pct INTEGER NOT NULL DEFAULT 0,
        tier_3_min_areas INTEGER NOT NULL DEFAULT 5,
        tier_3_discount_pct INTEGER NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(clinic_id)
    )
    """,

    # Max session minutes and welcome intro message for clinics
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS max_session_minutes INTEGER DEFAULT 60",
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS welcome_intro_message TEXT",

    # Discount fields on appointments
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS discount_pct INTEGER DEFAULT 0",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS discount_reason VARCHAR(50)",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS original_price_cents INTEGER",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS final_price_cents INTEGER",

    # Full name on appointments (collected during WhatsApp flow)
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)",

    # Clinic users (login for frontend panel)
    # unit_id NULL = acesso clinic-wide (default); NOT NULL = role unit-scoped (futuro)
    """
    CREATE TABLE IF NOT EXISTS scheduler.clinic_users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
        unit_id UUID REFERENCES scheduler.units(id),
        email VARCHAR(255) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        name VARCHAR(255),
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(email)
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_clinic_users_email ON scheduler.clinic_users(email)",

    # Normalize existing patient phone numbers to digits-only format (55DDDNNNNNNNNN).
    # Must temporarily drop unique constraint, normalize all phones, merge duplicates,
    # then recreate the constraint.
    """
    DO $$
    DECLARE
        dup RECORD;
        keeper_id UUID;
        keeper_name VARCHAR;
        keeper_gender VARCHAR;
        donor RECORD;
    BEGIN
        -- 1. Drop unique constraint temporarily
        ALTER TABLE scheduler.patients DROP CONSTRAINT IF EXISTS patients_clinic_id_phone_key;

        -- 2. Normalize all phone numbers: strip non-digits, prepend 55 if missing
        UPDATE scheduler.patients
        SET phone = CASE
            WHEN regexp_replace(phone, '[^0-9]', '', 'g') ~ '^55'
            THEN regexp_replace(phone, '[^0-9]', '', 'g')
            ELSE '55' || regexp_replace(phone, '[^0-9]', '', 'g')
        END,
        updated_at = NOW()
        WHERE phone ~ '[^0-9]';

        -- 3. Strip leading 0 after country code (e.g. 5501199... -> 551199...)
        UPDATE scheduler.patients
        SET phone = '55' || substring(phone from 4),
            updated_at = NOW()
        WHERE phone ~ '^550';

        -- 4. Merge duplicates: for each (clinic_id, phone) with >1 row, keep the oldest
        FOR dup IN
            SELECT clinic_id, phone
            FROM scheduler.patients
            GROUP BY clinic_id, phone
            HAVING COUNT(*) > 1
        LOOP
            -- Find keeper (oldest)
            SELECT id, name, gender INTO keeper_id, keeper_name, keeper_gender
            FROM scheduler.patients
            WHERE clinic_id = dup.clinic_id AND phone = dup.phone
            ORDER BY created_at ASC LIMIT 1;

            -- Reassign appointments from duplicates to keeper
            UPDATE scheduler.appointments
            SET patient_id = keeper_id
            WHERE patient_id IN (
                SELECT id FROM scheduler.patients
                WHERE clinic_id = dup.clinic_id AND phone = dup.phone AND id != keeper_id
            );

            -- Fill in keeper's missing name/gender from duplicates
            IF keeper_name IS NULL OR keeper_gender IS NULL THEN
                FOR donor IN
                    SELECT name, gender FROM scheduler.patients
                    WHERE clinic_id = dup.clinic_id AND phone = dup.phone AND id != keeper_id
                    ORDER BY created_at ASC
                LOOP
                    IF keeper_name IS NULL AND donor.name IS NOT NULL THEN
                        keeper_name := donor.name;
                    END IF;
                    IF keeper_gender IS NULL AND donor.gender IS NOT NULL THEN
                        keeper_gender := donor.gender;
                    END IF;
                END LOOP;

                UPDATE scheduler.patients
                SET name = keeper_name, gender = keeper_gender, updated_at = NOW()
                WHERE id = keeper_id;
            END IF;

            -- Delete duplicates
            DELETE FROM scheduler.patients
            WHERE clinic_id = dup.clinic_id AND phone = dup.phone AND id != keeper_id;
        END LOOP;

        -- 5. Recreate unique constraint
        ALTER TABLE scheduler.patients ADD CONSTRAINT patients_clinic_id_phone_key UNIQUE (clinic_id, phone);
    END $$
    """,

    # display_name on clinics
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS display_name VARCHAR(255)",

    # Remove legacy AI flow column
    "ALTER TABLE scheduler.clinics DROP COLUMN IF EXISTS use_ai_flow",

    # Leads table (unified lead tracking with GCLID for Google Ads conversion)
    """
    CREATE TABLE IF NOT EXISTS scheduler.leads (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
        phone VARCHAR(20) NOT NULL,
        name VARCHAR(255),
        email VARCHAR(255),
        gclid VARCHAR(255),
        source VARCHAR(50) NOT NULL DEFAULT 'whatsapp',
        booked BOOLEAN NOT NULL DEFAULT FALSE,
        first_appointment_id UUID REFERENCES scheduler.appointments(id),
        first_appointment_value DECIMAL(10,2),
        raw_message TEXT,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(clinic_id, phone)
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_leads_clinic_id ON scheduler.leads(clinic_id)",
    "CREATE INDEX IF NOT EXISTS idx_leads_phone ON scheduler.leads(phone)",
    "CREATE INDEX IF NOT EXISTS idx_leads_gclid ON scheduler.leads(gclid) WHERE gclid IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON scheduler.leads(clinic_id, created_at)",

    # Agent mode flag per clinic
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS use_agent BOOLEAN DEFAULT FALSE",

    # Remove deprecated Google Sheets columns
    "ALTER TABLE scheduler.clinics DROP COLUMN IF EXISTS google_spreadsheet_id",
    "ALTER TABLE scheduler.clinics DROP COLUMN IF EXISTS google_sheet_name",

    # Bot pause flag per clinic
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS bot_paused BOOLEAN DEFAULT FALSE",

    # Configurable default message template for batch WhatsApp sends
    "ALTER TABLE scheduler.clinics ADD COLUMN IF NOT EXISTS batch_message_template TEXT",

    # Last message timestamp on patients (updated when outbound message is sent)
    "ALTER TABLE scheduler.patients ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS idx_patients_last_message ON scheduler.patients(clinic_id, last_message_at)",

    # Soft-delete column on patients (set when patient is excluded by clinic owner)
    "ALTER TABLE scheduler.patients ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS idx_patients_deleted ON scheduler.patients(clinic_id, deleted_at)",

    # ============================================================
    # Migration 009 — Multi-unit architecture (Fase 0: Schema)
    # PRD: docs/work/prd/009-multi-unit-architecture.md
    # SPEC: docs/work/spec/009-multi-unit-architecture.md
    #
    # Aplica em DBs existentes os mesmos elementos já presentes nos CREATE TABLE acima.
    # Operacionais (appointments/availability_*) ficam nullable nesta fase; passam a NOT NULL
    # apenas na Fase 3 (cutover), após o backfill rodar em prod.
    # ============================================================

    # 1. Indexes em units / professionals_units (criação garantida; tabelas vêm do CREATE acima)
    "CREATE INDEX IF NOT EXISTS idx_units_clinic ON scheduler.units(clinic_id) WHERE active = TRUE",
    "CREATE INDEX IF NOT EXISTS idx_units_zapi ON scheduler.units(zapi_instance_id) WHERE zapi_instance_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_prof_units_unit ON scheduler.professionals_units(unit_id) WHERE active = TRUE",

    # 2. unit_id columns — idempotentes (no-op se CREATE TABLE já incluiu)
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
    "ALTER TABLE scheduler.availability_rules ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
    "ALTER TABLE scheduler.availability_exceptions ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
    "ALTER TABLE scheduler.services ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
    "ALTER TABLE scheduler.areas ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
    "ALTER TABLE scheduler.service_areas ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
    "ALTER TABLE scheduler.faq_items ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
    "ALTER TABLE scheduler.message_templates ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
    "ALTER TABLE scheduler.clinic_users ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",

    # 3. Indexes operacionais por unit (queries de availability/appointment passam a filtrar por unit_id)
    "CREATE INDEX IF NOT EXISTS idx_appointments_unit_date ON scheduler.appointments(unit_id, appointment_date)",
    "CREATE INDEX IF NOT EXISTS idx_availability_rules_unit ON scheduler.availability_rules(unit_id)",
    "CREATE INDEX IF NOT EXISTS idx_availability_exceptions_unit ON scheduler.availability_exceptions(unit_id, exception_date)",

    # 4. Drop dos UNIQUE inline antigos para liberar override pattern (clinic-default + unit-override).
    #    Faz lookup pelo nome auto-gerado do Postgres; se a constraint não existir, NO-OP.
    #    Sem este drop, a constraint atual (sem unit_id) bloquearia overrides com mesmo name.
    """
    DO $$
    DECLARE
        cons TEXT;
    BEGIN
        SELECT conname INTO cons FROM pg_constraint
        WHERE conrelid = 'scheduler.areas'::regclass
          AND contype = 'u'
          AND pg_get_constraintdef(oid) ILIKE '%(clinic_id, name)%';
        IF cons IS NOT NULL THEN
            EXECUTE format('ALTER TABLE scheduler.areas DROP CONSTRAINT %I', cons);
        END IF;

        SELECT conname INTO cons FROM pg_constraint
        WHERE conrelid = 'scheduler.service_areas'::regclass
          AND contype = 'u'
          AND pg_get_constraintdef(oid) ILIKE '%(service_id, area_id)%';
        IF cons IS NOT NULL THEN
            EXECUTE format('ALTER TABLE scheduler.service_areas DROP CONSTRAINT %I', cons);
        END IF;

        SELECT conname INTO cons FROM pg_constraint
        WHERE conrelid = 'scheduler.faq_items'::regclass
          AND contype = 'u'
          AND pg_get_constraintdef(oid) ILIKE '%(clinic_id, question_key)%';
        IF cons IS NOT NULL THEN
            EXECUTE format('ALTER TABLE scheduler.faq_items DROP CONSTRAINT %I', cons);
        END IF;

        SELECT conname INTO cons FROM pg_constraint
        WHERE conrelid = 'scheduler.message_templates'::regclass
          AND contype = 'u'
          AND pg_get_constraintdef(oid) ILIKE '%(clinic_id, template_key)%';
        IF cons IS NOT NULL THEN
            EXECUTE format('ALTER TABLE scheduler.message_templates DROP CONSTRAINT %I', cons);
        END IF;
    END $$
    """,

    # 5. Partial unique indexes (override pattern):
    #    - default da clinic: 1 row por chave funcional com unit_id IS NULL
    #    - override por unit:  1 row por (chave, unit_id) com unit_id IS NOT NULL
    #
    # services — chave funcional (clinic_id, name)
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_services_clinic_default ON scheduler.services(clinic_id, name) WHERE unit_id IS NULL AND active = TRUE",
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_services_clinic_unit ON scheduler.services(clinic_id, unit_id, name) WHERE unit_id IS NOT NULL AND active = TRUE",
    # areas — chave funcional (clinic_id, name)
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_areas_clinic_default ON scheduler.areas(clinic_id, name) WHERE unit_id IS NULL AND active = TRUE",
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_areas_clinic_unit ON scheduler.areas(clinic_id, unit_id, name) WHERE unit_id IS NOT NULL AND active = TRUE",
    # service_areas — chave funcional (service_id, area_id)
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_service_areas_default ON scheduler.service_areas(service_id, area_id) WHERE unit_id IS NULL AND active = TRUE",
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_service_areas_unit ON scheduler.service_areas(service_id, area_id, unit_id) WHERE unit_id IS NOT NULL AND active = TRUE",
    # faq_items — chave funcional (clinic_id, question_key)
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_faq_clinic_default ON scheduler.faq_items(clinic_id, question_key) WHERE unit_id IS NULL AND active = TRUE",
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_faq_clinic_unit ON scheduler.faq_items(clinic_id, unit_id, question_key) WHERE unit_id IS NOT NULL AND active = TRUE",
    # message_templates — chave funcional (clinic_id, template_key)
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_templates_clinic_default ON scheduler.message_templates(clinic_id, template_key) WHERE unit_id IS NULL AND active = TRUE",
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_templates_clinic_unit ON scheduler.message_templates(clinic_id, unit_id, template_key) WHERE unit_id IS NOT NULL AND active = TRUE",
]


def main():
    print("RDS HOST = ", os.environ.get("RDS_HOST"))
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
