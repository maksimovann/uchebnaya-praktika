from discount import calculate_partner_discount


PARTNER_SUMMARY_SQL = """
WITH sales_history AS (
    SELECT partner_id, quantity FROM shipments
)
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
GROUP BY p.partner_id, p.company_name, p.inn, p.contact_email, p.phone, p.rating
ORDER BY p.company_name
"""


def list_partners_from_postgres(database_url: str) -> list[dict]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RuntimeError("Установите зависимость: pip install 'psycopg[binary]'") from error
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(PARTNER_SUMMARY_SQL)
                rows = cursor.fetchall()
    except psycopg.Error as error:
        raise RuntimeError("Не удалось прочитать базу PostgreSQL") from error
    partners = []
    for row in rows:
        partner = dict(row)
        partner["rating"] = float(partner["rating"]) if partner["rating"] is not None else None
        partner["discount_percent"] = calculate_partner_discount(partner["total_quantity"])
        partners.append(partner)
    return partners
