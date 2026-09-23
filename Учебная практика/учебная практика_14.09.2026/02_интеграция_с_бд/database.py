import csv
import sqlite3
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from discount import calculate_partner_discount


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS partners (
    partner_id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    inn TEXT NOT NULL UNIQUE,
    contact_email TEXT,
    phone TEXT,
    rating REAL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id INTEGER PRIMARY KEY,
    partner_id INTEGER NOT NULL REFERENCES partners(partner_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    shipment_date TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    total_amount TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shipments_partner_id ON shipments(partner_id);

CREATE VIEW IF NOT EXISTS sales_history AS
SELECT partner_id, quantity FROM shipments;
"""

SUMMARY_SELECT_SQL = """
SELECT
    p.partner_id AS id,
    p.company_name,
    p.inn,
    p.contact_email AS email,
    p.phone,
    p.rating,
    COALESCE(SUM(s.quantity), 0) AS total_quantity
FROM partners AS p
LEFT JOIN sales_history AS s ON s.partner_id = p.partner_id
"""

SUMMARY_GROUP_SQL = """
GROUP BY p.partner_id, p.company_name, p.inn, p.contact_email, p.phone, p.rating
"""


def connect_database(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.commit()


def _read_rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=delimiter, quoting=csv.QUOTE_NONE)
        return list(reader)


def _parse_date(value: str) -> str:
    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value.strip(), date_format).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Неверный формат даты")


def import_practice_data(
    connection: sqlite3.Connection,
    partners_path: Path,
    sales_path: Path,
) -> dict[str, int]:
    partners = _read_rows(partners_path, ",")
    sales = _read_rows(sales_path, "\t")
    imported_sales = 0
    rejected_sales = 0
    with connection:
        for row in partners:
            rating = row["rating"].strip()
            connection.execute(
                "INSERT INTO partners (partner_id, company_name, inn, contact_email, phone, rating) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(partner_id) DO UPDATE SET "
                "company_name = excluded.company_name, inn = excluded.inn, "
                "contact_email = excluded.contact_email, phone = excluded.phone, rating = excluded.rating",
                (
                    int(row["partner_id"].strip()),
                    row["company_name"].strip(),
                    row["inn"].strip(),
                    row["contact_email"].strip() or None,
                    row["phone"].strip() or None,
                    float(rating) if rating else None,
                ),
            )
        for row in sales:
            try:
                shipment_id = int(row["sale_id"].strip())
                partner_id = int(row["partner_id"].strip())
                product_name = row["product_name"].strip()
                shipment_date = _parse_date(row["sale_date"])
                quantity = int(row["quantity"].strip())
                total_amount = Decimal(row["total_amount"].strip())
                if quantity <= 0 or total_amount < 0 or not product_name:
                    raise ValueError("Некорректная продажа")
                partner_exists = connection.execute(
                    "SELECT 1 FROM partners WHERE partner_id = ?",
                    (partner_id,),
                ).fetchone()
                if partner_exists is None:
                    raise ValueError("Партнер не найден")
            except (ValueError, InvalidOperation, TypeError):
                rejected_sales += 1
                continue
            connection.execute(
                "INSERT OR IGNORE INTO products (product_name) VALUES (?)",
                (product_name,),
            )
            product_id = connection.execute(
                "SELECT product_id FROM products WHERE product_name = ?",
                (product_name,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO shipments "
                "(shipment_id, partner_id, product_id, shipment_date, quantity, total_amount) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(shipment_id) DO UPDATE SET "
                "partner_id = excluded.partner_id, product_id = excluded.product_id, "
                "shipment_date = excluded.shipment_date, quantity = excluded.quantity, "
                "total_amount = excluded.total_amount",
                (shipment_id, partner_id, product_id, shipment_date, quantity, str(total_amount)),
            )
            imported_sales += 1
    return {"partners": len(partners), "sales": imported_sales, "rejected_sales": rejected_sales}


def _partner_from_row(row: sqlite3.Row) -> dict:
    partner = dict(row)
    partner["discount_percent"] = calculate_partner_discount(partner["total_quantity"])
    return partner


def get_partner_with_discount(connection: sqlite3.Connection, partner_id: int) -> dict | None:
    query = SUMMARY_SELECT_SQL + "WHERE p.partner_id = ?\n" + SUMMARY_GROUP_SQL
    row = connection.execute(query, (partner_id,)).fetchone()
    if row is None:
        return None
    return _partner_from_row(row)


def list_partners_with_discounts(connection: sqlite3.Connection) -> list[dict]:
    query = SUMMARY_SELECT_SQL + SUMMARY_GROUP_SQL + "ORDER BY p.company_name COLLATE NOCASE"
    rows = connection.execute(query).fetchall()
    return [_partner_from_row(row) for row in rows]
