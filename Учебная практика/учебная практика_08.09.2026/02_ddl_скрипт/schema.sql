-- PostgreSQL schema for the partner shipment history task.
-- Core business tables are kept in 3NF:
-- partners -> shipments <- products.

DROP VIEW IF EXISTS partner_shipment_history;
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS partners CASCADE;
DROP SCHEMA IF EXISTS raw_import CASCADE;

CREATE TABLE partners (
    partner_id INTEGER PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    inn VARCHAR(12) NOT NULL UNIQUE,
    contact_email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    rating DECIMAL(3, 2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT partners_inn_format_chk CHECK (inn ~ '^[0-9]{10}([0-9]{2})?$'),
    CONSTRAINT partners_email_format_chk CHECK (
        contact_email IS NULL
        OR contact_email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'
    ),
    CONSTRAINT partners_rating_range_chk CHECK (rating IS NULL OR rating BETWEEN 0 AND 5)
);

CREATE TABLE products (
    product_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE shipments (
    shipment_id INTEGER PRIMARY KEY,
    partner_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    shipment_date DATE NOT NULL,
    quantity INTEGER NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT shipments_partner_id_fk FOREIGN KEY (partner_id)
        REFERENCES partners(partner_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT shipments_product_id_fk FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT shipments_quantity_positive_chk CHECK (quantity > 0),
    CONSTRAINT shipments_total_amount_non_negative_chk CHECK (total_amount >= 0)
);

CREATE INDEX idx_shipments_partner_date ON shipments(partner_id, shipment_date DESC);
CREATE INDEX idx_shipments_product ON shipments(product_id);

CREATE SCHEMA raw_import;

CREATE TABLE raw_import.partners_src (
    partner_id TEXT,
    company_name TEXT,
    inn TEXT,
    contact_email TEXT,
    phone TEXT,
    rating TEXT
);

CREATE TABLE raw_import.sales_src (
    sale_id TEXT,
    partner_id TEXT,
    product_name TEXT,
    sale_date TEXT,
    quantity TEXT,
    total_amount TEXT
);

CREATE TABLE raw_import.etl_rejected_sales (
    sale_id_raw TEXT,
    partner_id_raw TEXT,
    product_name_raw TEXT,
    sale_date_raw TEXT,
    quantity_raw TEXT,
    total_amount_raw TEXT,
    rejection_reason TEXT NOT NULL,
    rejected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW partner_shipment_history AS
SELECT
    s.shipment_id,
    s.shipment_date,
    p.partner_id,
    p.company_name,
    p.inn,
    pr.product_id,
    pr.product_name,
    s.quantity,
    s.total_amount,
    ROUND(s.total_amount / NULLIF(s.quantity, 0), 2) AS unit_price
FROM shipments AS s
JOIN partners AS p ON p.partner_id = s.partner_id
JOIN products AS pr ON pr.product_id = s.product_id;
