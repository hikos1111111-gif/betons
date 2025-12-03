import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from wsgiref.simple_server import make_server

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import server


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.tmp_dir.name, "test.db")
        cls.app = server.create_app(db_path=cls.db_path, auto_seed=True)
        cls.httpd = make_server("127.0.0.1", 0, cls.app)
        cls.port = cls.httpd.server_port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=2)
        cls.httpd.server_close()
        cls.tmp_dir.cleanup()

    def base_url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def http_request(self, method: str, path: str, body: dict | None = None):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url(path), method=method, data=data, headers=headers)
        with urllib.request.urlopen(req) as resp:
            payload = resp.read().decode("utf-8")
            content = json.loads(payload) if payload else {}
            return resp.status, content

    def test_health(self):
        status, content = self.http_request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(content.get("status"), "ok")

    def test_crud_flow(self):
        status, listing = self.http_request("GET", "/api/records")
        self.assertEqual(status, 200)
        initial_count = len(listing.get("items", []))

        status, created = self.http_request(
            "POST",
            "/api/records",
            {
                "date": "2024-12-10",
                "site": "Test Yard",
                "mix": "C32/40",
                "volume": 10.5,
                "status": "Scheduled",
                "notes": "Night shift",
            },
        )
        self.assertEqual(status, 201)
        new_id = created.get("id")
        self.assertTrue(new_id)

        status, listing = self.http_request("GET", "/api/records")
        self.assertEqual(len(listing.get("items", [])), initial_count + 1)

        status, updated = self.http_request(
            "PUT",
            f"/api/records/{new_id}",
            {"status": "Completed", "volume": 11.0},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated.get("message"), "Updated")

        status, _ = self.http_request("DELETE", f"/api/records/{new_id}")
        self.assertEqual(status, 200)

        status, listing = self.http_request("GET", "/api/records")
        self.assertEqual(len(listing.get("items", [])), initial_count)


if __name__ == "__main__":
    unittest.main()
