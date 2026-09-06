from __future__ import annotations

import io
import unittest

from takekeeper.review_console import ReviewConsoleApp


class StubApi:
    def __init__(self):
        self.calls = []

    def __call__(self, environ, start_response):
        self.calls.append((environ.get("REQUEST_METHOD"), environ.get("PATH_INFO")))
        body = b'{"ok":true}'
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]


def call(app, path="/review", method="GET"):
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = int(status.split()[0])
        captured["headers"] = dict(headers)

    body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], body


class ReviewConsoleTests(unittest.TestCase):
    def setUp(self):
        self.api = StubApi()
        self.app = ReviewConsoleApp(self.api)

    def test_console_is_same_origin_no_store_and_framing_denied(self):
        status, headers, body = call(self.app)
        text = body.decode()
        self.assertEqual(200, status)
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertEqual("DENY", headers["X-Frame-Options"])
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("TakeKeeper Review Console", text)
        self.assertEqual([], self.api.calls)

    def test_console_does_not_persist_bearer_token_in_browser_storage(self):
        _, _, body = call(self.app)
        text = body.decode()
        self.assertNotIn("localStorage", text)
        self.assertNotIn("sessionStorage", text)
        self.assertNotIn("document.cookie", text)
        self.assertIn("type=\"password\"", text)
        self.assertIn("'Authorization':'Bearer '+token", text)

    def test_console_uses_only_bounded_review_endpoints(self):
        _, _, body = call(self.app)
        text = body.decode()
        self.assertIn("/v1/review/context", text)
        self.assertIn("/v1/review/decision", text)
        self.assertNotIn("run_query", text)
        self.assertNotIn("sql", text.lower())

    def test_non_get_review_is_rejected_without_api_delegation(self):
        status, _, body = call(self.app, method="POST")
        self.assertEqual(405, status)
        self.assertEqual(b"method not allowed", body)
        self.assertEqual([], self.api.calls)

    def test_other_routes_delegate_unchanged_to_review_api(self):
        status, _, _ = call(self.app, path="/v1/review/context", method="POST")
        self.assertEqual(200, status)
        self.assertEqual([("POST", "/v1/review/context")], self.api.calls)


if __name__ == "__main__":
    unittest.main()
