"""Seed script for Clínica Essência Estética."""
import psycopg2
import json
import os
import hashlib
from dotenv import load_dotenv

load_dotenv()


def hash_password_for_storage(password: str) -> str:
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2:{salt}:{dk.hex()}"


def main():
    conn = psycopg2.connect(
        host=os.getenv("RDS_HOST"),
        port=os.getenv("RDS_PORT"),
        database=os.getenv("RDS_DATABASE"),
        user=os.getenv("RDS_USERNAME"),
        password=os.getenv("RDS_PASSWORD"),
    )
    cur = conn.cursor()

    # --- Generate clinic_id ---
    clinic_name = "Clínica Essência Estética"
    base = "".join(e for e in clinic_name if e.isalnum()).lower()
    hash_suffix = hashlib.md5(clinic_name.encode()).hexdigest()[:6]
    clinic_id = f"{base}-{hash_suffix}"
    print(f"clinic_id: {clinic_id}")

    # === 1. CREATE CLINIC ===
    business_hours = json.dumps({
        "mon": {"start": "07:15", "end": "21:00"},
        "tue": {"start": "07:15", "end": "21:00"},
        "wed": {"start": "07:15", "end": "21:00"},
        "thu": {"start": "07:15", "end": "21:00"},
        "fri": {"start": "07:15", "end": "21:00"},
    })

    cur.execute(
        """
        INSERT INTO scheduler.clinics
            (clinic_id, name, phone, address, timezone, business_hours,
             buffer_minutes, max_session_minutes, owner_email, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (clinic_id) DO UPDATE SET
            name=EXCLUDED.name, phone=EXCLUDED.phone, address=EXCLUDED.address,
            business_hours=EXCLUDED.business_hours, updated_at=NOW()
        RETURNING clinic_id
        """,
        (
            clinic_id, clinic_name, "+5511963352425",
            "Rua Augusta, 2709, Cerqueira César, São Paulo-SP",
            "America/Sao_Paulo", business_hours, 10, 60,
            "gestao.essenceclinic@gmail.com",
        ),
    )
    print(f"Clinic created: {cur.fetchone()[0]}")

    # === 2. CREATE SERVICE ===
    cur.execute(
        """
        INSERT INTO scheduler.services (clinic_id, name, duration_minutes, price_cents, description, active)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (
            clinic_id, "Depilação a Laser", 20, 15000,
            "Sessão de depilação a laser com tecnologia de última geração",
        ),
    )
    service_row = cur.fetchone()
    if service_row:
        service_id = service_row[0]
    else:
        cur.execute(
            "SELECT id FROM scheduler.services WHERE clinic_id=%s AND name=%s",
            (clinic_id, "Depilação a Laser"),
        )
        service_id = cur.fetchone()[0]
    print(f"Service ID: {service_id}")

    # === 3. CREATE AREAS (same 32 areas as Depilação Premium) ===
    areas_data = [
        ("Abdômen", 1), ("Aréola", 2), ("Axilas", 3),
        ("Barba Comp. + Pescoço", 4), ("Barba contorno", 5),
        ("Braço Completo", 6), ("1/2 Braço", 7), ("Buço", 8),
        ("Costas total + ombros", 9), ("Costeleta", 10), ("Coxas", 11),
        ("Glabela (entre as sobrancelhas)", 12), ("Glúteo", 13),
        ("Linha alba", 14), ("Lombar", 15), ("Mão ou Pé + Dedos", 16),
        ("Mento/Queixo", 17), ("Nariz", 18), ("Nuca", 19), ("Ombros", 20),
        ("Orelhas", 21), ("Peitoral", 22), ("Peitoral + abdômen", 23),
        ("Perianal/ânus", 24), ("Perna Completa", 25), ("1/2 Perna", 26),
        ("Pescoço", 27), ("Rosto Completo", 28), ("Virilha Cavada", 29),
        ("Virilha Completa", 30), ("Virilha Comp. + ânus", 31),
        ("Virilha Simples", 32),
    ]

    area_ids = {}
    for name, order in areas_data:
        cur.execute(
            """
            INSERT INTO scheduler.areas (clinic_id, name, display_order, active)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (clinic_id, name) DO UPDATE SET display_order=EXCLUDED.display_order
            RETURNING id
            """,
            (clinic_id, name, order),
        )
        area_ids[name] = cur.fetchone()[0]
    print(f"Areas created: {len(area_ids)}")

    # === 4. CREATE SERVICE_AREAS (same durations/prices as premium) ===
    service_areas_data = [
        ("Abdômen", 5, 15500), ("Aréola", 2, 6500), ("Axilas", 5, 9500),
        ("Barba Comp. + Pescoço", 15, 15000), ("Barba contorno", 8, 11500),
        ("Braço Completo", 15, 19500), ("1/2 Braço", 8, 11500), ("Buço", 2, 6500),
        ("Costas total + ombros", 10, 23500), ("Costeleta", 2, 7500),
        ("Coxas", 10, 15500), ("Glabela (entre as sobrancelhas)", 2, 9500),
        ("Glúteo", 8, 11500), ("Linha alba", 2, 6500), ("Lombar", 5, 11500),
        ("Mão ou Pé + Dedos", 2, 7000), ("Mento/Queixo", 2, 6500),
        ("Nariz", 2, 9500), ("Nuca", 5, 7500), ("Ombros", 5, 11500),
        ("Orelhas", 2, 9500), ("Peitoral", 5, 15500),
        ("Peitoral + abdômen", 10, 23500), ("Perianal/ânus", 2, 9500),
        ("Perna Completa", 20, 24500), ("1/2 Perna", 10, 15500),
        ("Pescoço", 5, 9000), ("Rosto Completo", 10, 14000),
        ("Virilha Cavada", 10, 15500), ("Virilha Completa", 10, 17500),
        ("Virilha Comp. + ânus", 12, 19500), ("Virilha Simples", 5, 14500),
    ]

    sa_count = 0
    for area_name, duration, price in service_areas_data:
        cur.execute(
            """
            INSERT INTO scheduler.service_areas (service_id, area_id, duration_minutes, price_cents, active)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT (service_id, area_id) DO UPDATE SET
                duration_minutes=EXCLUDED.duration_minutes, price_cents=EXCLUDED.price_cents
            """,
            (service_id, area_ids[area_name], duration, price),
        )
        sa_count += 1
    print(f"Service areas created: {sa_count}")

    # === 5. AVAILABILITY RULES (3 specific dates, 07:15-21:00) ===
    dates = ["2026-04-15", "2026-04-28", "2026-04-29"]
    for d in dates:
        cur.execute(
            """
            INSERT INTO scheduler.availability_rules
                (clinic_id, day_of_week, rule_date, start_time, end_time, active)
            VALUES (%s, NULL, %s, %s, %s, TRUE)
            ON CONFLICT DO NOTHING
            """,
            (clinic_id, d, "07:15", "21:00"),
        )
    print(f"Availability rules created: {len(dates)} dates")

    # === 6. DISCOUNT RULES (same as premium) ===
    cur.execute(
        """
        INSERT INTO scheduler.discount_rules
            (clinic_id, first_session_discount_pct,
             tier_2_min_areas, tier_2_max_areas, tier_2_discount_pct,
             tier_3_min_areas, tier_3_discount_pct, is_active)
        VALUES (%s, 20, 2, 4, 10, 5, 15, TRUE)
        ON CONFLICT (clinic_id) DO UPDATE SET
            first_session_discount_pct=20, tier_2_discount_pct=10, tier_3_discount_pct=15
        """,
        (clinic_id,),
    )
    print("Discount rules created")

    # === 7. FAQ ITEMS (copy from premium) ===
    cur.execute(
        """SELECT question_key, question_label, answer, display_order
           FROM scheduler.faq_items
           WHERE clinic_id=%s ORDER BY display_order""",
        ("clinicadepilacaopremium-3fbce9",),
    )
    faq_rows = cur.fetchall()
    for key, label, answer, order in faq_rows:
        cur.execute(
            """
            INSERT INTO scheduler.faq_items
                (clinic_id, question_key, question_label, answer, display_order, active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (clinic_id, question_key) DO UPDATE SET
                question_label=EXCLUDED.question_label, answer=EXCLUDED.answer,
                display_order=EXCLUDED.display_order
            """,
            (clinic_id, key, label, answer, order),
        )
    print(f"FAQ items created: {len(faq_rows)}")

    # === 8. CLINIC USER (login credentials) ===
    pw_hash = hash_password_for_storage("Gestao-2026")
    cur.execute(
        """
        INSERT INTO scheduler.clinic_users (clinic_id, email, password_hash, name, active)
        VALUES (%s, %s, %s, %s, TRUE)
        ON CONFLICT (email) DO UPDATE SET
            password_hash=EXCLUDED.password_hash, clinic_id=EXCLUDED.clinic_id, name=EXCLUDED.name
        """,
        (clinic_id, "gestao.essenceclinic@gmail.com", pw_hash, "Gestão Essência"),
    )
    print("Clinic user created")

    conn.commit()
    cur.close()
    conn.close()

    print()
    print("=" * 40)
    print("DONE!")
    print(f"Clinic ID: {clinic_id}")
    print(f"Login: gestao.essenceclinic@gmail.com")
    print(f"Password: Gestao-2026")
    print(f"Frontend: https://traffic-manager-eight.vercel.app")
    print("=" * 40)


if __name__ == "__main__":
    main()
