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

-- 2. Добавление нового партнера и первой тестовой доставки
BEGIN;

INSERT INTO partners (
    partner_id,
    company_name,
    inn,
    contact_email,
    phone,
    rating
)
VALUES (
    10,
    'ООО "Тест-Партнер"',
    '7700000010',
    'test_partner@example.com',
    '+7 (999) 000-00-10',
    4.5
);

INSERT INTO products (product_name)
VALUES ('Тестовый продукт')
ON CONFLICT (product_name) DO NOTHING;

INSERT INTO shipments (
    shipment_id,
    partner_id,
    product_id,
    shipment_date,
    quantity,
    total_amount
)
SELECT
    1001,
    10,
    product_id,
    CURRENT_DATE,
    1,
    1000.00
FROM products
WHERE product_name = 'Тестовый продукт';

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
