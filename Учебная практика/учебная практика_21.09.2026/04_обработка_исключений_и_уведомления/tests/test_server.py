import http.client
import json
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

from database import connect_database, import_practice_data, initialize_database
from server import CRMHandler


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "test.sqlite3"
        with closing(connect_database(database_path)) as connection:
            initialize_database(connection)
            import_practice_data(
                connection,
                DATA_DIR / "import_partners.csv",
                DATA_DIR / "import_sales.txt",
            )
        handler = type(
            "TestCRMHandler",
            (CRMHandler,),
            {"database_path": database_path, "postgres_url": None},
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary_directory.cleanup()

    def test_api_lists_previous_practice_partners(self) -> None:
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port)) as client:
            client.request("GET", "/api/partners")
            response = client.getresponse()
            data = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(len(data["partners"]), 3)
        self.assertEqual(data["partners"][0]["discount_percent"], 0)

    def test_unknown_path_is_not_found(self) -> None:
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port)) as client:
            client.request("GET", "/missing")
            response = client.getresponse()
            response.read()
        self.assertEqual(response.status, 404)

    def request_json(self, method: str, path: str, payload: dict | None = None):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if body else {}
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port)) as client:
            client.request(method, path, body=body, headers=headers)
            response = client.getresponse()
            return response.status, json.loads(response.read())

    def test_create_read_and_update_partner(self) -> None:
        payload = {
            "company_name": "ООО Новый",
            "partner_type": "ООО",
            "inn": "1234567890",
            "rating": "2",
            "address": "Москва",
            "director_name": "Иванов И.И.",
            "phone": "+7 999 000-00-00",
            "email": "new@example.ru",
        }
        status, created = self.request_json("POST", "/api/partners", payload)
        self.assertEqual(status, 201)
        partner_id = created["partner"]["id"]
        status, loaded = self.request_json("GET", f"/api/partners/{partner_id}")
        self.assertEqual(status, 200)
        self.assertEqual(loaded["partner"]["company_name"], "ООО Новый")
        payload["company_name"] = "ООО Обновленный"
        status, updated = self.request_json("PUT", f"/api/partners/{partner_id}", payload)
        self.assertEqual(status, 200)
        self.assertEqual(updated["partner"]["company_name"], "ООО Обновленный")

    def test_invalid_partner_returns_actionable_error(self) -> None:
        status, data = self.request_json("POST", "/api/partners", {"rating": "-1"})
        self.assertEqual(status, 400)
        self.assertIn("Укажите", data["error"])


if __name__ == "__main__":
    unittest.main()
