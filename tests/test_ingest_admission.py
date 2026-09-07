from __future__ import annotations

import io
import json
import unittest
from types import SimpleNamespace

from takekeeper.extraction import PropertySpec
from takekeeper.ingest_admission import ActorIngestAdmissionGuard, IngestOverloaded
from takekeeper.ingest_api import IngestHttpApp
from takekeeper.ingest_runtime import IngestReadiness
from takekeeper.review_api import StaticBearerIdentityProvider


class _Service:
    def __init__(self) -> None:
        self.requests = []

    def readiness(self):
        return IngestReadiness(state="ready", schema_checked=True)

    def ingest(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            result=SimpleNamespace(
                run_id="run-1",
                production_id=request.production_id,
                scene_id=request.scene_id,
                take_id=request.take_id,
                observations=(),
            )
        )


class _UnreadableBody:
    def read(self, _length):
        raise AssertionError("overloaded request body must not be read")


class ActorIngestAdmissionGuardTests(unittest.TestCase):
    def test_concurrency_is_isolated_per_authenticated_actor(self):
        guard = ActorIngestAdmissionGuard(max_concurrent_per_actor=1)
        first = guard.acquire("actor-a")
        try:
            with self.assertRaises(IngestOverloaded):
                guard.acquire("actor-a")
            other = guard.acquire("actor-b")
            other.release()
        finally:
            first.release()

        snapshot = guard.snapshot()
        self.assertEqual(snapshot.active_requests, 0)
        self.assertEqual(snapshot.admitted_total, 2)
        self.assertEqual(snapshot.rejected_concurrency_total, 1)

    def test_sliding_window_rate_limit_expires(self):
        now = [100.0]
        guard = ActorIngestAdmissionGuard(
            max_concurrent_per_actor=4,
            max_requests_per_window=2,
            window_seconds=60,
            clock=lambda: now[0],
        )
        guard.acquire("actor-a").release()
        now[0] = 120.0
        guard.acquire("actor-a").release()
        with self.assertRaises(IngestOverloaded):
            guard.acquire("actor-a")

        now[0] = 161.0
        guard.acquire("actor-a").release()
        self.assertEqual(guard.snapshot().rejected_rate_total, 1)

    def test_actor_tracking_is_bounded_and_recovers_after_window(self):
        now = [10.0]
        guard = ActorIngestAdmissionGuard(
            max_tracked_actors=1,
            max_requests_per_window=1,
            window_seconds=10,
            clock=lambda: now[0],
        )
        guard.acquire("actor-a").release()
        with self.assertRaises(IngestOverloaded):
            guard.acquire("actor-b")
        self.assertEqual(guard.snapshot().rejected_capacity_total, 1)

        now[0] = 21.0
        guard.acquire("actor-b").release()


class IngestAdmissionHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _Service()
        self.guard = ActorIngestAdmissionGuard(max_concurrent_per_actor=1, max_requests_per_window=10)
        self.app = IngestHttpApp(
            self.service,
            StaticBearerIdentityProvider({"secret-token": "operator-1"}),
            property_profiles={
                "continuity-v1": (
                    PropertySpec("hero_mug", "hand", ("left", "right", "unknown")),
                )
            },
            extractor_model="gemini-2.5-flash",
            extractor_version="2026-09",
            admission_guard=self.guard,
        )

    def _call(self, environ):
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        body = b"".join(self.app(environ, start_response))
        return int(captured["status"].split()[0]), json.loads(body)

    def test_overload_is_rejected_after_auth_but_before_body_read(self):
        active = self.guard.acquire("operator-1")
        try:
            status, payload = self._call(
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": "/v1/ingest",
                    "HTTP_AUTHORIZATION": "Bearer secret-token",
                    "CONTENT_LENGTH": "100",
                    "wsgi.input": _UnreadableBody(),
                }
            )
        finally:
            active.release()

        self.assertEqual(status, 429)
        self.assertEqual(payload, {"error": "ingestion overloaded"})
        self.assertEqual(self.service.requests, [])

    def test_failed_request_releases_concurrency_lease(self):
        invalid = json.dumps({"unexpected": True}).encode()
        status, payload = self._call(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/v1/ingest",
                "HTTP_AUTHORIZATION": "Bearer secret-token",
                "CONTENT_LENGTH": str(len(invalid)),
                "wsgi.input": io.BytesIO(invalid),
            }
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload, {"error": "invalid request"})
        self.assertEqual(self.guard.snapshot().active_requests, 0)

    def test_metrics_are_aggregate_and_do_not_disclose_actor_ids(self):
        lease = self.guard.acquire("operator-1")
        lease.release()
        status, payload = self._call(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/metrics",
                "CONTENT_LENGTH": "0",
                "wsgi.input": io.BytesIO(),
            }
        )
        self.assertEqual(status, 200)
        rendered = json.dumps(payload)
        self.assertNotIn("operator-1", rendered)
        self.assertNotIn("production", rendered)
        metrics = payload["ingest_admission"]
        self.assertEqual(metrics["active_requests"], 0)
        self.assertEqual(metrics["admitted_total"], 1)


if __name__ == "__main__":
    unittest.main()
