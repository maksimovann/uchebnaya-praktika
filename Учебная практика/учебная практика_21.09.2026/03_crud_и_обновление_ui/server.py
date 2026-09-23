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

from database import (
    connect_database,
    create_partner,
    get_partner_with_discount,
    import_practice_data,
    initialize_database,
    list_partners_with_discounts,
    update_partner,
)
from partner_validation import PartnerValidationError, validate_partner
from postgres_database import (
    create_partner_in_postgres,
    get_partner_from_postgres,
    initialize_postgres,
    list_partners_from_postgres,
    update_partner_in_postgres,
)


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

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise PartnerValidationError("Заполните форму и повторите сохранение.")
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise PartnerValidationError("Данные формы повреждены. Обновите страницу и повторите ввод.") from error
        if not isinstance(payload, dict):
            raise PartnerValidationError("Данные формы имеют неверный формат.")
        return payload

    @staticmethod
    def _partner_id(path: str) -> int | None:
        prefix = "/api/partners/"
        if not path.startswith(prefix):
            return None
        try:
            return int(path.removeprefix(prefix))
        except ValueError:
            return None

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
        partner_id = self._partner_id(path)
        if partner_id is not None:
            try:
                if self.postgres_url:
                    partner = get_partner_from_postgres(self.postgres_url, partner_id)
                else:
                    with closing(connect_database(self.database_path)) as connection:
                        partner = get_partner_with_discount(connection, partner_id)
                if partner is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Партнер не найден"})
                else:
                    self._send_json(HTTPStatus.OK, {"partner": partner})
            except (sqlite3.Error, RuntimeError):
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "База данных недоступна. Проверьте подключение и повторите попытку."})
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

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/partners":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._save_partner(None)

    def do_PUT(self) -> None:
        partner_id = self._partner_id(urlsplit(self.path).path)
        if partner_id is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._save_partner(partner_id)

    def _save_partner(self, partner_id: int | None) -> None:
        try:
            data = validate_partner(self._read_json())
            if self.postgres_url:
                partner = (
                    create_partner_in_postgres(self.postgres_url, data)
                    if partner_id is None
                    else update_partner_in_postgres(self.postgres_url, partner_id, data)
                )
            else:
                with closing(connect_database(self.database_path)) as connection:
                    partner = (
                        create_partner(connection, data)
                        if partner_id is None
                        else update_partner(connection, partner_id, data)
                    )
            if partner is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Партнер не найден"})
                return
            status = HTTPStatus.CREATED if partner_id is None else HTTPStatus.OK
            self._send_json(status, {"partner": partner})
        except PartnerValidationError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except sqlite3.IntegrityError:
            self._send_json(HTTPStatus.CONFLICT, {"error": "ИНН или email уже используются. Проверьте данные и повторите сохранение."})
        except (sqlite3.Error, RuntimeError):
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "База данных недоступна. Проверьте подключение и повторите попытку."})


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
            initialize_postgres(postgres_url)
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
