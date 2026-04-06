"""Fix clinic_id for Essência Estética: create new ASCII clinic_id, migrate data, delete old."""
import os
import hashlib
import unicodedata
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def normalize_clinic_id(clinic_name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", clinic_name)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    base = "".join(e for e in ascii_only if e.isalnum()).lower()
    hash_suffix = hashlib.md5(clinic_name.encode()).hexdigest()[:6]
    return f"{base}-{hash_suffix}"


def main():
    clinic_name = "Clínica Essência Estética"

    old_base = "".join(e for e in clinic_name if e.isalnum()).lower()
    old_hash = hashlib.md5(clinic_name.encode()).hexdigest()[:6]
    old_id = f"{old_base}-{old_hash}"
    new_id = normalize_clinic_id(clinic_name)

    print(f"Old: {repr(old_id)}")
    print(f"New: {repr(new_id)}")

    conn = psycopg2.connect(
        host=os.getenv("RDS_HOST"),
        port=os.getenv("RDS_PORT"),
        database=os.getenv("RDS_DATABASE"),
        user=os.getenv("RDS_USERNAME"),
        password=os.getenv("RDS_PASSWORD"),
    )
    cur = conn.cursor()

    # 1. Clone clinic row with new clinic_id
    cur.execute(
        """INSERT INTO scheduler.clinics
           (clinic_id, name, phone, address, timezone, business_hours,
            buffer_minutes, max_session_minutes, owner_email, welcome_message,
            pre_session_instructions, welcome_intro_message, display_name,
            use_agent, bot_paused, active, max_future_dates,
            zapi_instance_id, zapi_instance_token)
           SELECT %s, name, phone, address, timezone, business_hours,
            buffer_minutes, max_session_minutes, owner_email, welcome_message,
            pre_session_instructions, welcome_intro_message, display_name,
            use_agent, bot_paused, active, max_future_dates,
            zapi_instance_id, zapi_instance_token
           FROM scheduler.clinics WHERE clinic_id = %s
           ON CONFLICT (clinic_id) DO NOTHING""",
        (new_id, old_id),
    )
    print(f"  clinics cloned: {cur.rowcount}")

    # 2. Clone services
    cur.execute(
        """INSERT INTO scheduler.services (clinic_id, name, duration_minutes, price_cents, description, active)
           SELECT %s, name, duration_minutes, price_cents, description, active
           FROM scheduler.services WHERE clinic_id = %s""",
        (new_id, old_id),
    )
    print(f"  services cloned: {cur.rowcount}")

    # 3. Clone areas
    cur.execute(
        """INSERT INTO scheduler.areas (clinic_id, name, display_order, active)
           SELECT %s, name, display_order, active
           FROM scheduler.areas WHERE clinic_id = %s
           ON CONFLICT (clinic_id, name) DO NOTHING""",
        (new_id, old_id),
    )
    print(f"  areas cloned: {cur.rowcount}")

    # 4. Clone service_areas (need to map old service/area IDs to new ones)
    cur.execute(
        """INSERT INTO scheduler.service_areas (service_id, area_id, duration_minutes, price_cents, pre_session_instructions, active)
           SELECT ns.id, na.id, sa.duration_minutes, sa.price_cents, sa.pre_session_instructions, sa.active
           FROM scheduler.service_areas sa
           JOIN scheduler.services os ON sa.service_id = os.id AND os.clinic_id = %s
           JOIN scheduler.areas oa ON sa.area_id = oa.id AND oa.clinic_id = %s
           JOIN scheduler.services ns ON ns.clinic_id = %s AND ns.name = os.name
           JOIN scheduler.areas na ON na.clinic_id = %s AND na.name = oa.name
           ON CONFLICT (service_id, area_id) DO NOTHING""",
        (old_id, old_id, new_id, new_id),
    )
    print(f"  service_areas cloned: {cur.rowcount}")

    # 5. Clone availability_rules
    cur.execute(
        """INSERT INTO scheduler.availability_rules
           (clinic_id, professional_id, day_of_week, rule_date, start_time, end_time, active)
           SELECT %s, professional_id, day_of_week, rule_date, start_time, end_time, active
           FROM scheduler.availability_rules WHERE clinic_id = %s""",
        (new_id, old_id),
    )
    print(f"  availability_rules cloned: {cur.rowcount}")

    # 6. Clone patients
    cur.execute(
        """INSERT INTO scheduler.patients (clinic_id, phone, name, gender)
           SELECT %s, phone, name, gender
           FROM scheduler.patients WHERE clinic_id = %s
           ON CONFLICT (clinic_id, phone) DO NOTHING""",
        (new_id, old_id),
    )
    print(f"  patients cloned: {cur.rowcount}")

    # 7. Clone clinic_users
    cur.execute(
        """INSERT INTO scheduler.clinic_users (clinic_id, email, password_hash, name, active)
           SELECT %s, email, password_hash, name, active
           FROM scheduler.clinic_users WHERE clinic_id = %s
           ON CONFLICT (email) DO UPDATE SET clinic_id = EXCLUDED.clinic_id""",
        (new_id, old_id),
    )
    print(f"  clinic_users cloned: {cur.rowcount}")

    # 8. Clone discount_rules
    cur.execute(
        """INSERT INTO scheduler.discount_rules
           (clinic_id, first_session_discount_pct,
            tier_2_min_areas, tier_2_max_areas, tier_2_discount_pct,
            tier_3_min_areas, tier_3_discount_pct, is_active)
           SELECT %s, first_session_discount_pct,
            tier_2_min_areas, tier_2_max_areas, tier_2_discount_pct,
            tier_3_min_areas, tier_3_discount_pct, is_active
           FROM scheduler.discount_rules WHERE clinic_id = %s
           ON CONFLICT (clinic_id) DO NOTHING""",
        (new_id, old_id),
    )
    print(f"  discount_rules cloned: {cur.rowcount}")

    # 9. Clone faq_items
    cur.execute(
        """INSERT INTO scheduler.faq_items
           (clinic_id, question_key, question_label, answer, display_order, active)
           SELECT %s, question_key, question_label, answer, display_order, active
           FROM scheduler.faq_items WHERE clinic_id = %s
           ON CONFLICT (clinic_id, question_key) DO NOTHING""",
        (new_id, old_id),
    )
    print(f"  faq_items cloned: {cur.rowcount}")

    # 10. Delete old data (children first, then parent)
    print("\nDeleting old data...")
    for table in [
        "faq_items", "discount_rules", "clinic_users", "patients",
        "availability_rules", "service_areas", "areas", "services", "clinics",
    ]:
        if table == "service_areas":
            cur.execute(
                """DELETE FROM scheduler.service_areas
                   WHERE service_id IN (SELECT id FROM scheduler.services WHERE clinic_id = %s)""",
                (old_id,),
            )
        else:
            cur.execute(
                f"DELETE FROM scheduler.{table} WHERE clinic_id = %s",
                (old_id,),
            )
        if cur.rowcount > 0:
            print(f"  {table}: {cur.rowcount} row(s) deleted")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone! New clinic_id: {new_id}")


if __name__ == "__main__":
    main()
