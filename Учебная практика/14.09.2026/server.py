import argparse
import json
import os
import sqlite3
from contextlib import closing
from getpass import getpass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from database import connect_database, import_practice_data, initialize_database, list_partners_with_discounts
from postgres_database import list_partners_from_postgres


PROJECT_DIR = Path(__file__).resolve().parent
STATIC_FILES = {
    "/": (PROJECT_DIR / "web" / "index.html", "text/html; charset=utf-8"),
    "/app.css": (PROJECT_DIR / "web" / "app.css", "text/css; charset=utf-8"),
    "/app.js": (PROJECT_DIR / "web" / "app.js", "text/javascript; charset=utf-8"),
    "/resources/logo.svg": (PROJECT_DIR / "resources" / "logo.svg", "image/svg+xml"),
    "/resources/favicon.svg": (PROJECT_DIR / "resources" / "favicon.svg", "image/svg+xml"),
}


class CRMHandler(BaseHTTPRequestHandler):
    database_path = PROJECT_DIR / "practice.sqlite3"
    postgres_url = None

    def _send_json(self, status: HTTPStatus, payload: object) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/partners":
            try:
                if self.postgres_url:
                    partners = list_partners_from_postgres(self.postgres_url)
                else:
                    with closing(connect_database(self.database_path)) as connection:
                        partners = list_partners_with_discounts(connection)
                self._send_json(HTTPStatus.OK, {"partners": partners})
            except (sqlite3.Error, RuntimeError):
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Ошибка базы данных"})
            return
        if path in STATIC_FILES:
            file_path, content_type = STATIC_FILES[path]
            content = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        self.send_error(HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser(description="Локальная CRM партнеров")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path, default=PROJECT_DIR / "practice.sqlite3")
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument("--pg-database")
    parser.add_argument("--pg-user", default="postgres")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    args = parser.parse_args()
    postgres_url = os.environ.get("PARTNER_CRM_DATABASE_URL")
    if args.postgres:
        try:
            from psycopg.conninfo import make_conninfo
        except ImportError as error:
            parser.error("Установите зависимость: python -m pip install -r requirements-postgres.txt")
        database_name = args.pg_database or input("Название базы PostgreSQL: ").strip()
        if not database_name:
            parser.error("Название базы не может быть пустым")
        postgres_url = make_conninfo(
            host=args.pg_host,
            port=args.pg_port,
            dbname=database_name,
            user=args.pg_user,
            password=getpass("Пароль PostgreSQL: "),
        )
    if postgres_url:
        try:
            partners = list_partners_from_postgres(postgres_url)
        except RuntimeError as error:
            parser.error(str(error))
        print(f"Подключено к PostgreSQL. Партнеров: {len(partners)}", flush=True)
    if not postgres_url:
        with closing(connect_database(args.db)) as connection:
            initialize_database(connection)
            partner_count = connection.execute("SELECT COUNT(*) FROM partners").fetchone()[0]
            if partner_count == 0:
                import_practice_data(
                    connection,
                    PROJECT_DIR / "data" / "import_partners.csv",
                    PROJECT_DIR / "data" / "import_sales.txt",
                )
    CRMHandler.database_path = args.db
    CRMHandler.postgres_url = postgres_url
    server = ThreadingHTTPServer((args.host, args.port), CRMHandler)
    print(f"CRM доступна по адресу http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
