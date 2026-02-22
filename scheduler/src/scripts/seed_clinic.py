"""
Seed script: popula dados de exemplo para Laser Beauty.
Executar: python -m src.scripts.seed_clinic
"""
import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main():
    conn = psycopg2.connect(
        host=os.environ.get("RDS_HOST"),
        port=int(os.environ.get("RDS_PORT", "5432")),
        dbname=os.environ.get("RDS_DATABASE"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
    )

    cursor = conn.cursor()
    cursor.execute("SET search_path TO scheduler, public")

    # ── 1. Clinic ──────────────────────────────────────────────────────────
    business_hours = {
        "mon": {"start": "09:00", "end": "18:00"},
        "tue": {"start": "09:00", "end": "18:00"},
        "wed": {"start": "09:00", "end": "18:00"},
        "thu": {"start": "09:00", "end": "18:00"},
        "fri": {"start": "09:00", "end": "18:00"},
    }

    welcome_intro = (
        "✨ Nós trabalhamos com o Soprano Ice Platinum, uma das tecnologias mais avançadas do mundo em depilação a laser.\n\n"
        "💎 Trata-se de um equipamento de ponta, avaliado em cerca de R$ 350 a R$ 400 mil reais, reconhecido pela sua segurança e eficiência.\n\n"
        "📅 As sessões têm intervalo médio de 30 dias, ou seja, você realiza aproximadamente 1 sessão por mês.\n\n"
        "Como o equipamento é de alto valor, ele é locado exclusivamente para alguns dias de atendimento durante o mês, "
        "garantindo que cada paciente seja recebido em estrutura adequada.\n\n"
        "👉 Trabalhamos somente com sessão avulsa, para dar liberdade e flexibilidade a cada pessoa."
    )

    pre_session_instructions = (
        "• Evite exposição solar intensa na região tratada por 7 dias antes e após a sessão.\n"
        "• Não utilize cremes com ácidos na área a ser tratada nas 48h anteriores.\n"
        "• A área deve estar raspada (com lâmina) no dia da sessão. Não use cera ou pinça.\n"
        "• Gestantes não podem realizar o procedimento.\n"
        "• Em caso de uso de medicamentos fotossensibilizantes, informe nossa equipe."
    )

    cursor.execute(
        """
        INSERT INTO clinics (clinic_id, name, phone, business_hours, buffer_minutes, max_session_minutes, welcome_intro_message, pre_session_instructions)
        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s)
        ON CONFLICT (clinic_id) DO UPDATE SET
            max_session_minutes = EXCLUDED.max_session_minutes,
            welcome_intro_message = EXCLUDED.welcome_intro_message,
            pre_session_instructions = EXCLUDED.pre_session_instructions,
            updated_at = NOW()
        RETURNING id, clinic_id
        """,
        ("laser-beauty-sp", "Laser Beauty SP", "5511988880000", json.dumps(business_hours), 10, 60, welcome_intro, pre_session_instructions),
    )
    conn.commit()
    row = cursor.fetchone()
    if row:
        print(f"[1/6] Clinic criada: id={row[0]}, clinic_id={row[1]}")
    else:
        print("[1/6] Clinic ja existe (laser-beauty-sp) - skip")

    clinic_id = "laser-beauty-sp"

    # ── 2. Service ─────────────────────────────────────────────────────────
    cursor.execute(
        """
        INSERT INTO services (id, clinic_id, name, duration_minutes, price_cents)
        VALUES (gen_random_uuid(), %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id, name
        """,
        (clinic_id, "Depilacao a laser", 45, 15000),
    )
    conn.commit()
    row = cursor.fetchone()
    if row:
        print(f"[2/6] Service criado: id={row[0]}, name={row[1]}")
    else:
        print("[2/6] Service ja existe - skip")

    # ── 3. Professional ────────────────────────────────────────────────────
    cursor.execute(
        """
        INSERT INTO professionals (id, clinic_id, name, role)
        VALUES (gen_random_uuid(), %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id, name
        """,
        (clinic_id, "Dra. Ana Souza", "Biomedica esteta"),
    )
    conn.commit()
    row = cursor.fetchone()
    if row:
        professional_id = row[0]
        print(f"[3/6] Professional criado: id={row[0]}, name={row[1]}")
    else:
        print("[3/6] Professional ja existe - skip")
        cursor.execute(
            "SELECT id FROM professionals WHERE clinic_id = %s AND name = %s",
            (clinic_id, "Dra. Ana Souza"),
        )
        result = cursor.fetchone()
        professional_id = result[0] if result else None

    # ── 4. Availability Rules (mon-fri, 09:00-18:00) ──────────────────────
    rules_inserted = 0
    for day_of_week in range(1, 6):  # 1=mon .. 5=fri
        cursor.execute(
            """
            INSERT INTO availability_rules (id, clinic_id, professional_id, day_of_week, start_time, end_time)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (clinic_id, professional_id, day_of_week, "09:00", "18:00"),
        )
        conn.commit()
        row = cursor.fetchone()
        if row:
            rules_inserted += 1

    print(f"[4/6] Availability rules: {rules_inserted} criada(s), {5 - rules_inserted} ja existiam")

    # ── 5. FAQ Items ───────────────────────────────────────────────────────
    faq_items = [
        (
            "EQUIPMENT",
            "Qual equipamento vocês usam?",
            "Trabalhamos com o Soprano Ice Platinum, uma das tecnologias mais avançadas do mundo em depilação a laser. Trata-se de um equipamento de ponta, reconhecido pela sua segurança e eficiência.",
            1,
        ),
        (
            "SESSION_INTERVAL",
            "Qual o intervalo entre sessões?",
            "As sessões têm intervalo médio de 30 dias, ou seja, você realiza aproximadamente 1 sessão por mês.",
            2,
        ),
        (
            "SCHEDULE_DATES",
            "Como funcionam as datas?",
            "Nossa clínica disponibiliza o laser em apenas algumas datas específicas por mês. Consulte os dias disponíveis no agendamento.",
            3,
        ),
        (
            "PAYMENT",
            "Como funciona o pagamento?",
            "Trabalhamos somente com sessão avulsa, para dar liberdade e flexibilidade. O pagamento é feito presencialmente.",
            4,
        ),
        (
            "TEAM",
            "Quem são os profissionais?",
            "Nossa equipe de biomédicas estetas é treinada e especializada em atendimento personalizado com a tecnologia Soprano Ice.",
            5,
        ),
    ]

    faqs_inserted = 0
    for question_key, question_label, answer, display_order in faq_items:
        cursor.execute(
            """
            INSERT INTO faq_items (id, clinic_id, question_key, question_label, answer, display_order)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
            ON CONFLICT (clinic_id, question_key) DO NOTHING
            RETURNING id
            """,
            (clinic_id, question_key, question_label, answer, display_order),
        )
        conn.commit()
        row = cursor.fetchone()
        if row:
            faqs_inserted += 1

    print(f"[5/6] FAQ items: {faqs_inserted} criado(s), {len(faq_items) - faqs_inserted} ja existiam")

    # ── 6. Discount Rules ────────────────────────────────────────────────
    cursor.execute(
        """
        INSERT INTO discount_rules (id, clinic_id, first_session_discount_pct,
            tier_2_min_areas, tier_2_max_areas, tier_2_discount_pct,
            tier_3_min_areas, tier_3_discount_pct, is_active)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (clinic_id) DO NOTHING
        RETURNING id
        """,
        (clinic_id, 20, 2, 4, 10, 5, 15),
    )
    conn.commit()
    row = cursor.fetchone()
    if row:
        print(f"[6/6] Discount rules criada: id={row[0]}")
    else:
        print("[6/6] Discount rules ja existe - skip")

    cursor.close()
    conn.close()
    print("\nSeed concluido com sucesso.")


if __name__ == "__main__":
    main()
