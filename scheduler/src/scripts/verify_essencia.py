"""Verify all data for Clínica Essência Estética."""
import os
import hashlib
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main():
    clinic_name = "Clínica Essência Estética"
    base = "".join(e for e in clinic_name if e.isalnum()).lower()
    hash_suffix = hashlib.md5(clinic_name.encode()).hexdigest()[:6]
    clinic_id = f"{base}-{hash_suffix}"
    print(f"Expected clinic_id = {repr(clinic_id)}")
    print(f"Expected clinic_id bytes = {clinic_id.encode('utf-8').hex()}")

    conn = psycopg2.connect(
        host=os.getenv("RDS_HOST"),
        port=os.getenv("RDS_PORT"),
        database=os.getenv("RDS_DATABASE"),
        user=os.getenv("RDS_USERNAME"),
        password=os.getenv("RDS_PASSWORD"),
    )
    cur = conn.cursor()

    # What's in the DB
    cur.execute("SELECT clinic_id FROM scheduler.clinics WHERE name LIKE '%%Ess%%'")
    row = cur.fetchone()
    db_clinic_id = row[0]
    print(f"DB clinic_id = {repr(db_clinic_id)}")
    print(f"DB clinic_id bytes = {db_clinic_id.encode('utf-8').hex()}")
    print(f"Match: {clinic_id == db_clinic_id}")

    # Login user
    cur.execute(
        "SELECT clinic_id FROM scheduler.clinic_users WHERE email='gestao.essenceclinic@gmail.com'"
    )
    print(f"User clinic_id = {repr(cur.fetchone()[0])}")

    # Counts
    for table in ["patients", "services", "areas", "availability_rules", "service_areas", "faq_items", "discount_rules"]:
        if table == "service_areas":
            cur.execute(
                f"SELECT count(*) FROM scheduler.{table} sa JOIN scheduler.services s ON sa.service_id=s.id WHERE s.clinic_id=%s",
                (db_clinic_id,),
            )
        else:
            cur.execute(
                f"SELECT count(*) FROM scheduler.{table} WHERE clinic_id=%s",
                (db_clinic_id,),
            )
        print(f"  {table}: {cur.fetchone()[0]}")

    # Availability rules details
    cur.execute(
        "SELECT rule_date, day_of_week, start_time, end_time FROM scheduler.availability_rules WHERE clinic_id=%s",
        (db_clinic_id,),
    )
    print("\nAvailability rules:")
    for r in cur.fetchall():
        print(f"  date={r[0]} dow={r[1]} {r[2]}-{r[3]}")

    conn.close()


if __name__ == "__main__":
    main()
