-- Backfill original_price_cents and final_price_cents for appointments
-- that have NULL prices but have service_area records.
--
-- Run: psql -h <host> -U <user> -d trafficmanager -f src/scripts/backfill_prices.sql

-- 1. Appointments with service_areas (most common case)
UPDATE scheduler.appointments a
SET
    original_price_cents = sub.total_price,
    final_price_cents = CASE
        WHEN a.discount_pct > 0 THEN sub.total_price * (100 - a.discount_pct) / 100
        ELSE sub.total_price
    END,
    updated_at = NOW()
FROM (
    SELECT
        asa.appointment_id,
        SUM(COALESCE(asa.price_cents, 0)) as total_price
    FROM scheduler.appointment_service_areas asa
    GROUP BY asa.appointment_id
) sub
WHERE a.id = sub.appointment_id
  AND a.original_price_cents IS NULL
  AND sub.total_price > 0;

-- 2. Appointments without areas — use base service price
UPDATE scheduler.appointments a
SET
    original_price_cents = s.price_cents,
    final_price_cents = CASE
        WHEN a.discount_pct > 0 THEN s.price_cents * (100 - a.discount_pct) / 100
        ELSE s.price_cents
    END,
    updated_at = NOW()
FROM scheduler.services s
WHERE a.service_id = s.id
  AND a.original_price_cents IS NULL
  AND s.price_cents > 0
  AND NOT EXISTS (
      SELECT 1 FROM scheduler.appointment_service_areas asa WHERE asa.appointment_id = a.id
  );

-- Verify results
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE original_price_cents IS NOT NULL) as with_price,
    COUNT(*) FILTER (WHERE original_price_cents IS NULL) as without_price
FROM scheduler.appointments
WHERE status = 'CONFIRMED';
