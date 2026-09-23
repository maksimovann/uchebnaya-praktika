-- 1. Список партнеров
SELECT
    p.partner_id,
    p.company_name,
    p.inn,
    p.contact_email,
    p.phone,
    p.rating,
    COUNT(s.shipment_id) AS deliveries_count
FROM partners AS p
LEFT JOIN shipments AS s ON s.partner_id = p.partner_id
GROUP BY
    p.partner_id,
    p.company_name,
    p.inn,
    p.contact_email,
    p.phone,
    p.rating
ORDER BY p.company_name;

-- 2. Добавление/обновление партнера и его тестовой доставки.
-- Идентификаторы вычисляются из текущих данных, поэтому блок можно запускать повторно.
BEGIN;

WITH saved_partner AS (
INSERT INTO partners (
    partner_id,
    company_name,
    inn,
    contact_email,
    phone,
    rating
)
SELECT
    COALESCE(MAX(partner_id), 0) + 1,
    'ООО "Тест-Партнер"',
    '7700000010',
    'test_partner@example.com',
    '+7 (999) 000-00-10',
    4.5
FROM partners
ON CONFLICT (inn) DO UPDATE
SET
    company_name = EXCLUDED.company_name,
    contact_email = EXCLUDED.contact_email,
    phone = EXCLUDED.phone,
    rating = EXCLUDED.rating,
    updated_at = CURRENT_TIMESTAMP
RETURNING partner_id
),
saved_product AS (
    INSERT INTO products (product_name)
    VALUES ('Тестовый продукт')
    ON CONFLICT (product_name) DO UPDATE
    SET product_name = EXCLUDED.product_name
    RETURNING product_id
)
INSERT INTO shipments (
    shipment_id,
    partner_id,
    product_id,
    shipment_date,
    quantity,
    total_amount
)
SELECT
    COALESCE((SELECT MAX(shipment_id) FROM shipments), 0) + 1,
    saved_partner.partner_id,
    saved_product.product_id,
    CURRENT_DATE,
    1,
    CAST(1000.00 AS DECIMAL(12, 2))
FROM saved_partner
CROSS JOIN saved_product
WHERE NOT EXISTS (
    SELECT 1
    FROM shipments AS existing_shipment
    WHERE existing_shipment.partner_id = saved_partner.partner_id
      AND existing_shipment.product_id = saved_product.product_id
      AND existing_shipment.quantity = 1
      AND existing_shipment.total_amount = CAST(1000.00 AS DECIMAL(12, 2))
);

COMMIT;

-- 3. История отгрузок партнера за период
SELECT
    s.shipment_id,
    p.company_name,
    pr.product_name,
    s.shipment_date,
    s.quantity,
    s.total_amount
FROM shipments AS s
JOIN partners AS p ON p.partner_id = s.partner_id
JOIN products AS pr ON pr.product_id = s.product_id
WHERE s.partner_id = 1
  AND s.shipment_date BETWEEN DATE '2026-03-01' AND DATE '2026-03-31'
ORDER BY s.shipment_date, s.shipment_id;
