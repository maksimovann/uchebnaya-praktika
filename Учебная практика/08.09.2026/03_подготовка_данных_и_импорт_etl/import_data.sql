

TRUNCATE TABLE raw_import.partners_src;
TRUNCATE TABLE raw_import.sales_src;
TRUNCATE TABLE raw_import.etl_rejected_sales;

\copy raw_import.partners_src FROM 'C:/Users/mannka/Downloads/import_partners.csv' WITH (FORMAT csv, HEADER true, QUOTE E'\b')
\copy raw_import.sales_src FROM 'C:/Users/mannka/Downloads/import_sales.txt' WITH (FORMAT csv, HEADER true, DELIMITER E'\t', QUOTE E'\b')

BEGIN;

INSERT INTO partners (
    partner_id,
    company_name,
    inn,
    contact_email,
    phone,
    rating
)
SELECT
    btrim(partner_id)::INTEGER,
    btrim(company_name),
    btrim(inn),
    NULLIF(btrim(contact_email), ''),
    NULLIF(btrim(phone), ''),
    NULLIF(btrim(rating), '')::NUMERIC(3, 2)
FROM raw_import.partners_src
WHERE NULLIF(btrim(partner_id), '') IS NOT NULL
ON CONFLICT (partner_id) DO UPDATE
SET
    company_name = EXCLUDED.company_name,
    inn = EXCLUDED.inn,
    contact_email = EXCLUDED.contact_email,
    phone = EXCLUDED.phone,
    rating = EXCLUDED.rating,
    updated_at = CURRENT_TIMESTAMP;

WITH normalized_sales AS (
    SELECT
        btrim(sale_id) AS sale_id,
        btrim(partner_id) AS partner_id,
        btrim(product_name) AS product_name,
        btrim(sale_date) AS sale_date,
        btrim(quantity) AS quantity,
        btrim(total_amount) AS total_amount
    FROM raw_import.sales_src
)
INSERT INTO products (product_name)
SELECT DISTINCT product_name
FROM normalized_sales
WHERE product_name <> ''
ON CONFLICT (product_name) DO NOTHING;

WITH normalized_sales AS (
    SELECT
        btrim(sale_id) AS sale_id,
        btrim(partner_id) AS partner_id,
        btrim(product_name) AS product_name,
        btrim(sale_date) AS sale_date,
        btrim(quantity) AS quantity,
        btrim(total_amount) AS total_amount
    FROM raw_import.sales_src
),
typed_sales AS (
    SELECT
        sale_id,
        partner_id,
        product_name,
        sale_date,
        quantity,
        total_amount,
        CASE
            WHEN sale_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                THEN to_date(sale_date, 'YYYY-MM-DD')
            WHEN sale_date ~ '^[0-9]{2}\.[0-9]{2}\.[0-9]{4}$'
                THEN to_date(sale_date, 'DD.MM.YYYY')
            ELSE NULL
        END AS parsed_sale_date
    FROM normalized_sales
),
invalid_sales AS (
    SELECT
        ts.*,
        concat_ws(
            '; ',
            CASE WHEN ts.sale_id !~ '^[0-9]+$' THEN 'sale_id is not an integer' END,
            CASE WHEN ts.partner_id !~ '^[0-9]+$' THEN 'partner_id is not an integer' END,
            CASE WHEN p.partner_id IS NULL THEN 'partner_id is absent in partners' END,
            CASE WHEN ts.product_name = '' THEN 'product_name is empty' END,
            CASE WHEN ts.parsed_sale_date IS NULL THEN 'sale_date has unsupported format' END,
            CASE
                WHEN ts.quantity !~ '^[0-9]+$' THEN 'quantity is not an integer'
                WHEN ts.quantity::INTEGER <= 0 THEN 'quantity must be positive integer'
            END,
            CASE WHEN ts.total_amount !~ '^[0-9]+(\.[0-9]{1,2})?$' THEN 'total_amount must be non-negative decimal' END
        ) AS rejection_reason
    FROM typed_sales AS ts
    LEFT JOIN partners AS p
        ON p.partner_id = CASE WHEN ts.partner_id ~ '^[0-9]+$' THEN ts.partner_id::INTEGER END
)
INSERT INTO raw_import.etl_rejected_sales (
    sale_id_raw,
    partner_id_raw,
    product_name_raw,
    sale_date_raw,
    quantity_raw,
    total_amount_raw,
    rejection_reason
)
SELECT
    sale_id,
    partner_id,
    product_name,
    sale_date,
    quantity,
    total_amount,
    rejection_reason
FROM invalid_sales
WHERE rejection_reason <> '';

WITH normalized_sales AS (
    SELECT
        btrim(sale_id) AS sale_id,
        btrim(partner_id) AS partner_id,
        btrim(product_name) AS product_name,
        btrim(sale_date) AS sale_date,
        btrim(quantity) AS quantity,
        btrim(total_amount) AS total_amount
    FROM raw_import.sales_src
),
typed_sales AS (
    SELECT
        sale_id,
        partner_id,
        product_name,
        quantity,
        total_amount,
        CASE
            WHEN sale_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                THEN to_date(sale_date, 'YYYY-MM-DD')
            WHEN sale_date ~ '^[0-9]{2}\.[0-9]{2}\.[0-9]{4}$'
                THEN to_date(sale_date, 'DD.MM.YYYY')
            ELSE NULL
        END AS parsed_sale_date
    FROM normalized_sales
),
valid_sales AS (
    SELECT *
    FROM typed_sales
    WHERE sale_id ~ '^[0-9]+$'
      AND partner_id ~ '^[0-9]+$'
      AND product_name <> ''
      AND parsed_sale_date IS NOT NULL
      AND quantity ~ '^[0-9]+$'
      AND quantity::INTEGER > 0
      AND total_amount ~ '^[0-9]+(\.[0-9]{1,2})?$'
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
    vs.sale_id::INTEGER,
    vs.partner_id::INTEGER,
    pr.product_id,
    vs.parsed_sale_date,
    vs.quantity::INTEGER,
    vs.total_amount::NUMERIC(12, 2)
FROM valid_sales AS vs
JOIN partners AS p ON p.partner_id = vs.partner_id::INTEGER
JOIN products AS pr ON pr.product_name = vs.product_name
ON CONFLICT (shipment_id) DO UPDATE
SET
    partner_id = EXCLUDED.partner_id,
    product_id = EXCLUDED.product_id,
    shipment_date = EXCLUDED.shipment_date,
    quantity = EXCLUDED.quantity,
    total_amount = EXCLUDED.total_amount;

COMMIT;

SELECT COUNT(*) AS partners_count FROM partners;
SELECT COUNT(*) AS products_count FROM products;
SELECT COUNT(*) AS shipments_count FROM shipments;
SELECT COUNT(*) AS rejected_sales_count FROM raw_import.etl_rejected_sales;
