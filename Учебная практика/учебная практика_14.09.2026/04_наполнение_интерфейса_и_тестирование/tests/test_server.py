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


if __name__ == "__main__":
    unittest.main()
