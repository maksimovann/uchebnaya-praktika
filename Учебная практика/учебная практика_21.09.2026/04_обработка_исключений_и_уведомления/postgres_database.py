from discount import calculate_partner_discount


PARTNER_FIELDS_SQL = r"""
ALTER TABLE partners ADD COLUMN IF NOT EXISTS partner_type VARCHAR(20) NOT NULL DEFAULT 'ООО';
ALTER TABLE partners ADD COLUMN IF NOT EXISTS address VARCHAR(500);
ALTER TABLE partners ADD COLUMN IF NOT EXISTS director_name VARCHAR(255);
UPDATE partners
SET partner_type = (regexp_match(TRIM(company_name), '^(ООО|ИП|ЗАО|АО|ПАО|ТК)\s+'))[1],
    company_name = regexp_replace(TRIM(company_name), '^(ООО|ИП|ЗАО|АО|ПАО|ТК)\s+', '')
WHERE TRIM(company_name) ~ '^(ООО|ИП|ЗАО|АО|ПАО|ТК)\s+';
UPDATE partners SET rating = ROUND(COALESCE(rating, 0));
"""

PARTNER_SUMMARY_SQL = """
WITH sales_history AS (
    SELECT partner_id, quantity FROM shipments
)
SELECT
    p.partner_id AS id,
    p.company_name,
    p.partner_type,
    p.inn,
    p.contact_email AS email,
    p.phone,
    p.rating,
    p.address,
    p.director_name,
    COALESCE(SUM(s.quantity), 0) AS total_quantity
FROM partners AS p
LEFT JOIN sales_history AS s ON s.partner_id = p.partner_id
{where_clause}
GROUP BY p.partner_id, p.company_name, p.partner_type, p.inn, p.contact_email,
    p.phone, p.rating, p.address, p.director_name
{order_clause}
"""


def initialize_postgres(database_url: str) -> None:
    psycopg, _ = _driver()
    try:
        with psycopg.connect(database_url) as connection:
            connection.execute(PARTNER_FIELDS_SQL)
    except psycopg.Error as error:
        raise RuntimeError("Не удалось обновить структуру PostgreSQL") from error


def list_partners_from_postgres(database_url: str) -> list[dict]:
    rows = _fetch_all(
        database_url,
        PARTNER_SUMMARY_SQL.format(where_clause="", order_clause="ORDER BY p.company_name"),
    )
    return [_with_discount(row) for row in rows]


def get_partner_from_postgres(database_url: str, partner_id: int) -> dict | None:
    rows = _fetch_all(
        database_url,
        PARTNER_SUMMARY_SQL.format(
            where_clause="WHERE p.partner_id = %s",
            order_clause="",
        ),
        (partner_id,),
    )
    return _with_discount(rows[0]) if rows else None


def create_partner_in_postgres(database_url: str, data: dict) -> dict:
    psycopg, dict_row = _driver()
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                # The legacy schema has no identity sequence, so the lock prevents duplicate IDs.
                cursor.execute("LOCK TABLE partners IN EXCLUSIVE MODE")
                cursor.execute("SELECT COALESCE(MAX(partner_id), 0) + 1 AS next_id FROM partners")
                partner_id = cursor.fetchone()["next_id"]
                cursor.execute(
                    "INSERT INTO partners "
                    "(partner_id, company_name, partner_type, inn, contact_email, phone, rating, address, director_name) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (partner_id, *_partner_values(data)),
                )
    except psycopg.Error as error:
        raise RuntimeError("Не удалось добавить партнера в PostgreSQL") from error
    return get_partner_from_postgres(database_url, partner_id)


def update_partner_in_postgres(database_url: str, partner_id: int, data: dict) -> dict | None:
    psycopg, _ = _driver()
    try:
        with psycopg.connect(database_url) as connection:
            cursor = connection.execute(
                "UPDATE partners SET company_name = %s, partner_type = %s, inn = %s, "
                "contact_email = %s, phone = %s, rating = %s, address = %s, director_name = %s "
                "WHERE partner_id = %s",
                (*_partner_values(data), partner_id),
            )
            if cursor.rowcount == 0:
                return None
    except psycopg.Error as error:
        raise RuntimeError("Не удалось обновить партнера в PostgreSQL") from error
    return get_partner_from_postgres(database_url, partner_id)


def _driver():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RuntimeError("Установите зависимость: pip install 'psycopg[binary]'") from error
    return psycopg, dict_row


def _fetch_all(database_url: str, query: str, parameters: tuple = ()) -> list[dict]:
    psycopg, dict_row = _driver()
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            return connection.execute(query, parameters).fetchall()
    except psycopg.Error as error:
        raise RuntimeError("Не удалось прочитать базу PostgreSQL") from error


def _partner_values(data: dict) -> tuple:
    return (
        data["company_name"], data["partner_type"], data["inn"], data["email"],
        data["phone"], data["rating"], data["address"], data["director_name"],
    )


def _with_discount(row: dict) -> dict:
    partner = dict(row)
    partner["rating"] = int(partner["rating"] or 0)
    partner["discount_percent"] = calculate_partner_discount(partner["total_quantity"])
    return partner
