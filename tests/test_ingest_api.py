from __future__ import annotations

import io
import json
import unittest
from types import SimpleNamespace

from takekeeper.extraction import PropertySpec
from takekeeper.ingest_api import IngestHttpApp, MAX_BODY_BYTES
from takekeeper.ingest_runtime import IngestNotReady, IngestReadiness
from takekeeper.review_api import StaticBearerIdentityProvider


class _Service:
    def __init__(self, *, ready: bool = False, schema_checked: bool = False) -> None:
        self.ready = ready
        self.schema_checked = schema_checked
        self.requests = []

    def readiness(self) -> IngestReadiness:
        return IngestReadiness(
            state="ready" if self.ready else "not_ready",
            schema_checked=self.schema_checked,
        )

    def ingest(self, request):
        if not self.ready:
            raise IngestNotReady("closed")
        self.requests.append(request)
        result = SimpleNamespace(
            run_id="run-1",
            production_id=request.production_id,
            scene_id=request.scene_id,
            take_id=request.take_id,
            observations=(object(), object()),
        )
        return SimpleNamespace(result=result)


class _UnreadableBody:
    def read(self, _length):
        raise AssertionError("unauthenticated request body must not be read")


class IngestHttpAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _Service()
        self.identity = StaticBearerIdentityProvider({"secret-token": "operator-1"})
        self.profile = (
            PropertySpec("hero_mug", "hand", ("left", "right", "unknown")),
        )
        self.app = IngestHttpApp(
            self.service,
            self.identity,
            property_profiles={"continuity-v1": self.profile},
            extractor_model="gemini-2.5-flash",
            extractor_version="2026-09",
        )

    def request(self, method: str, path: str, payload=None, *, token="secret-token"):
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
        }
        if token is not None:
            environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        response = b"".join(self.app(environ, start_response))
        return int(captured["status"].split()[0]), json.loads(response), captured["headers"]

    def valid_payload(self):
        return {
            "production_id": "prod-1",
            "scene_id": "scene-7",
            "take_id": "take-3",
            "media_uri": "gs://private-bucket/prod-1/scene-7/take-3.mp4",
            "duration_ms": 12_500,
            "property_profile": "continuity-v1",
            "media_mime_type": "video/mp4",
            "media_content_sha256": "a" * 64,
            "media_byte_size": 1_024,
        }

    def test_health_is_independent_of_clickhouse_readiness(self):
        status, payload, headers = self.request("GET", "/healthz", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok"})
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_readyz_is_coarse_and_fails_closed(self):
        status, payload, _ = self.request("GET", "/readyz", token=None)
        self.assertEqual(status, 503)
        self.assertEqual(payload, {"status": "not_ready", "schema_checked": False})

        self.service.schema_checked = True
        status, payload, _ = self.request("GET", "/readyz", token=None)
        self.assertEqual(status, 503)
        self.assertEqual(payload, {"status": "not_ready", "schema_checked": True})

        self.service.ready = True
        status, payload, _ = self.request("GET", "/readyz", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ready", "schema_checked": True})

    def test_unready_ingest_returns_503_and_persists_nothing(self):
        status, payload, _ = self.request("POST", "/v1/ingest", self.valid_payload())
        self.assertEqual(status, 503)
        self.assertEqual(payload, {"error": "ingestion not ready"})
        self.assertEqual(self.service.requests, [])

    def test_authenticated_ready_ingest_uses_server_owned_policy(self):
        self.service.ready = True
        self.service.schema_checked = True
        status, payload, _ = self.request("POST", "/v1/ingest", self.valid_payload())
        self.assertEqual(status, 201)
        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(payload["observation_count"], 2)
        self.assertEqual(len(self.service.requests), 1)
        request = self.service.requests[0]
        self.assertEqual(request.extractor_model, "gemini-2.5-flash")
        self.assertEqual(request.extractor_version, "2026-09")
        self.assertEqual(request.properties, self.profile)
        self.assertEqual(request.media_content_sha256, "a" * 64)

    def test_caller_cannot_override_model_or_property_registry(self):
        payload = self.valid_payload()
        payload["extractor_model"] = "attacker-model"
        status, response, _ = self.request("POST", "/v1/ingest", payload)
        self.assertEqual(status, 400)
        self.assertEqual(response, {"error": "invalid request"})

    def test_unknown_property_profile_is_rejected(self):
        payload = self.valid_payload()
        payload["property_profile"] = "unconfigured"
        status, response, _ = self.request("POST", "/v1/ingest", payload)
        self.assertEqual(status, 400)
        self.assertEqual(response, {"error": "invalid request"})

    def test_authentication_happens_before_body_read(self):
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/v1/ingest",
            "CONTENT_LENGTH": "10",
            "wsgi.input": _UnreadableBody(),
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = status

        response = json.loads(b"".join(self.app(environ, start_response)))
        self.assertTrue(captured["status"].startswith("401 "))
        self.assertEqual(response, {"error": "authentication required"})

    def test_invalid_token_is_redacted(self):
        status, payload, _ = self.request("POST", "/v1/ingest", self.valid_payload(), token="wrong-secret")
        self.assertEqual(status, 401)
        self.assertEqual(payload, {"error": "authentication required"})
        self.assertNotIn("wrong-secret", json.dumps(payload))

    def test_oversized_body_is_rejected_before_service(self):
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/v1/ingest",
            "HTTP_AUTHORIZATION": "Bearer secret-token",
            "CONTENT_LENGTH": str(MAX_BODY_BYTES + 1),
            "wsgi.input": io.BytesIO(b"{}"),
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = status

        response = json.loads(b"".join(self.app(environ, start_response)))
        self.assertTrue(captured["status"].startswith("400 "))
        self.assertEqual(response, {"error": "invalid request"})
        self.assertEqual(self.service.requests, [])

    def test_media_provenance_validation_remains_domain_owned(self):
        payload = self.valid_payload()
        payload["media_content_sha256"] = "NOT-A-HASH"
        status, response, _ = self.request("POST", "/v1/ingest", payload)
        self.assertEqual(status, 400)
        self.assertEqual(response, {"error": "invalid request"})

    def test_provider_or_service_errors_do_not_escape(self):
        class BrokenService(_Service):
            def ingest(self, request):
                raise RuntimeError("clickhouse://user:secret@private-host/internal")

        app = IngestHttpApp(
            BrokenService(ready=True, schema_checked=True),
            self.identity,
            property_profiles={"continuity-v1": self.profile},
            extractor_model="gemini-2.5-flash",
            extractor_version="2026-09",
        )
        self.app = app
        status, payload, _ = self.request("POST", "/v1/ingest", self.valid_payload())
        self.assertEqual(status, 500)
        self.assertEqual(payload, {"error": "internal server error"})
        self.assertNotIn("private-host", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
