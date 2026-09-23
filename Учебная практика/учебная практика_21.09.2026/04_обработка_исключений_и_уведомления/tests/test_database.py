import unittest
from pathlib import Path

from database import (
    connect_database,
    create_partner,
    get_partner_with_discount,
    import_practice_data,
    initialize_database,
    list_partners_with_discounts,
    update_partner,
)
from postgres_database import PARTNER_SUMMARY_SQL


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = connect_database(":memory:")
        initialize_database(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_import_from_previous_practice(self) -> None:
        result = import_practice_data(
            self.connection,
            DATA_DIR / "import_partners.csv",
            DATA_DIR / "import_sales.txt",
        )
        self.assertEqual(result, {"partners": 3, "sales": 4, "rejected_sales": 1})
        partners = list_partners_with_discounts(self.connection)
        by_id = {partner["id"]: partner for partner in partners}
        self.assertEqual(by_id[1]["total_quantity"], 80)
        self.assertEqual(by_id[2]["total_quantity"], 200)
        self.assertEqual(by_id[3]["total_quantity"], 150)
        self.assertEqual(by_id[1]["discount_percent"], 0)
        self.assertIsNone(by_id[2]["phone"])
        self.assertEqual(by_id[1]["rating"], 5)
        self.assertEqual(by_id[3]["rating"], 0)

    def test_partner_without_history_and_boundary(self) -> None:
        self.connection.execute(
            "INSERT INTO partners (partner_id, company_name, inn) VALUES (1, 'Тест', '1234567890')"
        )
        partner = get_partner_with_discount(self.connection, 1)
        self.assertEqual(partner["total_quantity"], 0)
        self.assertEqual(partner["discount_percent"], 0)
        self.assertIsNone(get_partner_with_discount(self.connection, 999))
        self.connection.execute("INSERT INTO products (product_id, product_name) VALUES (1, 'Товар')")
        self.connection.execute(
            "INSERT INTO shipments "
            "(shipment_id, partner_id, product_id, shipment_date, quantity, total_amount) "
            "VALUES (1, 1, 1, '2026-09-19', 9999, '100')"
        )
        self.assertEqual(get_partner_with_discount(self.connection, 1)["discount_percent"], 0)
        self.connection.execute(
            "INSERT INTO shipments "
            "(shipment_id, partner_id, product_id, shipment_date, quantity, total_amount) "
            "VALUES (2, 1, 1, '2026-09-19', 1, '1')"
        )
        self.assertEqual(get_partner_with_discount(self.connection, 1)["discount_percent"], 5)

    def test_postgres_summary_query_handles_missing_history(self) -> None:
        self.connection.execute(
            "INSERT INTO partners (partner_id, company_name, inn) VALUES (1, 'Тест', '1234567890')"
        )
        query = PARTNER_SUMMARY_SQL.format(where_clause="", order_clause="")
        row = self.connection.execute(query).fetchone()
        self.assertEqual(row["total_quantity"], 0)

    def test_create_and_update_partner(self) -> None:
        data = {
            "company_name": "Новый партнер",
            "partner_type": "ЗАО",
            "inn": "1234567890",
            "email": "new@example.ru",
            "phone": "+7 999 100-20-30",
            "rating": 3,
            "address": "Москва",
            "director_name": "Иванов Иван Иванович",
        }
        created = create_partner(self.connection, data)
        self.assertEqual(created["partner_type"], "ЗАО")
        self.assertEqual(created["total_quantity"], 0)
        data["company_name"] = "Обновленный партнер"
        updated = update_partner(self.connection, created["id"], data)
        self.assertEqual(updated["company_name"], "Обновленный партнер")
        self.assertIsNone(update_partner(self.connection, 999, data))

    def test_large_partner_list(self) -> None:
        rows = [
            (partner_id, f"Партнер {partner_id}", f"{partner_id:010d}")
            for partner_id in range(1, 1004)
        ]
        self.connection.executemany(
            "INSERT INTO partners (partner_id, company_name, inn) VALUES (?, ?, ?)",
            rows,
        )
        self.connection.execute("INSERT INTO products (product_id, product_name) VALUES (1, 'Товар')")
        self.connection.executemany(
            "INSERT INTO shipments "
            "(shipment_id, partner_id, product_id, shipment_date, quantity, total_amount) "
            "VALUES (?, ?, 1, '2026-09-19', 300000, '1')",
            [(partner_id, partner_id) for partner_id in range(1, 1004, 2)],
        )
        partners = list_partners_with_discounts(self.connection)
        by_id = {partner["id"]: partner for partner in partners}
        self.assertEqual(len(partners), 1003)
        self.assertEqual(by_id[1]["discount_percent"], 15)
        self.assertEqual(by_id[2]["discount_percent"], 0)


if __name__ == "__main__":
    unittest.main()
