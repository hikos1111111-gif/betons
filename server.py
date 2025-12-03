import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Callable, Iterable, List, Tuple
from wsgiref.simple_server import make_server
from wsgiref.util import FileWrapper

DEFAULT_DB_PATH = Path(os.environ.get("DB_PATH", "data.db"))
STATIC_DIR = Path(__file__).parent / "static"

ResponseBody = Iterable[bytes]
StartResponse = Callable[[str, List[Tuple[str, str]]], None]


def init_db(db_path: Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                site TEXT NOT NULL,
                mix TEXT NOT NULL,
                volume REAL NOT NULL,
                status TEXT NOT NULL,
                notes TEXT DEFAULT ''
            )
            """
        )
        conn.commit()


def seed_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT COUNT(1) FROM records")
        count = cur.fetchone()[0]
        if count:
            return
        sample_rows = [
            ("2024-11-28", "Site A", "C25/30", 18.5, "Scheduled", "Morning delivery"),
            ("2024-11-29", "Site B", "C30/37", 22.0, "Completed", "Slab pour finished"),
            ("2024-12-02", "Site C", "Shotcrete", 12.0, "Delayed", "Awaiting pump"),
        ]
        conn.executemany(
            "INSERT INTO records (date, site, mix, volume, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
            sample_rows,
        )
        conn.commit()


def json_response(start_response: StartResponse, status: str, payload: dict) -> ResponseBody:
    body = json.dumps(payload).encode("utf-8")
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ]
    start_response(status, headers)
    return [body]


def read_request_body(environ) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH", "0"))
    except (TypeError, ValueError):
        length = 0
    if length <= 0:
        return b""
    return environ["wsgi.input"].read(length)


def parse_json_body(environ) -> dict:
    raw_body = read_request_body(environ)
    if not raw_body:
        return {}
    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def serve_static(path: Path, start_response: StartResponse) -> ResponseBody:
    if not path.exists() or not path.is_file():
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]

    mime = "text/plain"
    if path.suffix == ".html":
        mime = "text/html; charset=utf-8"
    elif path.suffix == ".css":
        mime = "text/css"
    elif path.suffix == ".js":
        mime = "application/javascript"
    elif path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
        mime = f"image/{path.suffix.lstrip('.')}"

    file_size = path.stat().st_size
    headers = [("Content-Type", mime), ("Content-Length", str(file_size))]
    start_response("200 OK", headers)
    return FileWrapper(open(path, "rb"))  # type: ignore[return-value]


def get_records(db_path: Path) -> List[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, date, site, mix, volume, status, notes FROM records ORDER BY date"
        ).fetchall()
        return [dict(row) for row in rows]


def create_record(db_path: Path, payload: dict) -> Tuple[bool, str, int]:
    required = ["date", "site", "mix", "volume", "status"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return False, f"Missing fields: {', '.join(missing)}", 0
    try:
        volume = float(payload.get("volume"))
    except (TypeError, ValueError):
        return False, "Volume must be a number", 0

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO records (date, site, mix, volume, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (
                payload.get("date"),
                payload.get("site"),
                payload.get("mix"),
                volume,
                payload.get("status"),
                payload.get("notes", ""),
            ),
        )
        conn.commit()
        return True, "Created", cur.lastrowid


def update_record(db_path: Path, record_id: int, payload: dict) -> Tuple[bool, str]:
    fields = {k: payload.get(k) for k in ["date", "site", "mix", "volume", "status", "notes"]}
    if not any(v is not None for v in fields.values()):
        return False, "No fields to update"

    if fields.get("volume") is not None:
        try:
            fields["volume"] = float(fields["volume"])
        except (TypeError, ValueError):
            return False, "Volume must be a number"

    assignments = ", ".join([f"{key} = ?" for key, value in fields.items() if value is not None])
    values = [value for value in fields.values() if value is not None]
    values.append(record_id)

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            f"UPDATE records SET {assignments} WHERE id = ?",
            values,
        )
        conn.commit()
        if cur.rowcount == 0:
            return False, "Record not found"
    return True, "Updated"


def delete_record(db_path: Path, record_id: int) -> Tuple[bool, str]:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        if cur.rowcount == 0:
            return False, "Record not found"
    return True, "Deleted"


def create_app(db_path: Path = DEFAULT_DB_PATH, auto_seed: bool = True):
    db_path = Path(db_path)
    init_db(db_path)
    if auto_seed:
        seed_db(db_path)

    def application(environ, start_response):
        path = environ.get("PATH_INFO", "") or "/"
        method = environ.get("REQUEST_METHOD", "GET").upper()

        if path == "/" and method == "GET":
            return serve_static(STATIC_DIR / "index.html", start_response)

        if path.startswith("/static/") and method == "GET":
            relative = path.replace("/static/", "")
            return serve_static(STATIC_DIR / relative, start_response)

        if path == "/api/health":
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.execute("SELECT 1")
                return json_response(start_response, "200 OK", {"status": "ok"})
            except sqlite3.Error as exc:  # pragma: no cover - defensive
                return json_response(start_response, "500 Internal Server Error", {"error": str(exc)})

        if path == "/api/records":
            if method == "GET":
                records = get_records(db_path)
                return json_response(start_response, "200 OK", {"items": records})
            if method == "POST":
                payload = parse_json_body(environ)
                success, message, record_id = create_record(db_path, payload)
                status = "201 Created" if success else "400 Bad Request"
                body = {"message": message}
                if success:
                    body["id"] = record_id
                return json_response(start_response, status, body)

        match = re.match(r"^/api/records/(\d+)$", path)
        if match:
            record_id = int(match.group(1))
            if method == "PUT":
                payload = parse_json_body(environ)
                success, message = update_record(db_path, record_id, payload)
                status = "200 OK" if success else "400 Bad Request"
                return json_response(start_response, status, {"message": message})
            if method == "DELETE":
                success, message = delete_record(db_path, record_id)
                status = "200 OK" if success else "404 Not Found"
                return json_response(start_response, status, {"message": message})

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]

    return application


def main():
    parser = argparse.ArgumentParser(description="Lightweight CRUD server using stdlib only")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)), help="Port to bind")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--no-seed", action="store_true", help="Disable inserting sample data on boot")
    args = parser.parse_args()

    app = create_app(db_path=args.db, auto_seed=not args.no_seed)
    with make_server("0.0.0.0", args.port, app) as httpd:
        print(f"Serving on port {args.port}, database at {args.db}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
