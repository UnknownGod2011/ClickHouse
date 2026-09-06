from __future__ import annotations

import io
import json
import unittest

from takekeeper.memory import InMemoryProductionMemory
from takekeeper.models import Finding
from takekeeper.review import FindingReviewService, InMemoryReviewDecisionStore
from takekeeper.review_api import ReviewHttpApp, StaticBearerIdentityProvider


SCOPE = {
    "production_id": "glass-house",
    "scene_id": "S28",
    "take_id": "S28-T47",
    "entity_id": "maya",
    "property_key": "prop.mug_hand",
}


def seed_service():
    memory = InMemoryProductionMemory()
    memory.replace_findings(
        production_id="glass-house",
        scene_id="S28",
        take_id="S28-T47",
        findings=[Finding(
            **SCOPE,
            baseline_value="left",
            observed_value="right",
            confidence=0.98,
            status="mismatch",
            evidence_start_ms=100,
            evidence_end_ms=900,
            baseline_source_take_id="S28-T31",
        )],
    )
    return FindingReviewService(memory, InMemoryReviewDecisionStore())


def call(app, path, payload, *, token="secret-token", method="POST"):
    raw = json.dumps(payload).encode()
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(raw)),
        "CONTENT_TYPE": "application/json",
        "HTTP_AUTHORIZATION": f"Bearer {token}" if token is not None else "",
        "wsgi.input": io.BytesIO(raw),
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = int(status.split()[0])
        captured["headers"] = dict(headers)

    body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], json.loads(body)


class ReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.app = ReviewHttpApp(
            seed_service(),
            StaticBearerIdentityProvider({"secret-token": "script-supervisor@example.test"}),
        )

    def test_context_returns_evidence_and_empty_history(self):
        status, headers, body = call(self.app, "/v1/review/context", SCOPE)
        self.assertEqual(200, status)
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertEqual("mismatch", body["finding"]["status"])
        self.assertEqual(100, body["finding"]["evidence_start_ms"])
        self.assertTrue(body["finding"]["finding_id"])
        self.assertEqual([], body["history"])

    def test_decision_actor_comes_from_bearer_identity(self):
        payload = {**SCOPE, "decision": "confirmed", "note": "Checked against slate reference."}
        status, _, body = call(self.app, "/v1/review/decision", payload)
        self.assertEqual(201, status)
        self.assertEqual("script-supervisor@example.test", body["decision"]["actor_id"])

        status, _, context = call(self.app, "/v1/review/context", SCOPE)
        self.assertEqual(200, status)
        self.assertEqual(1, len(context["history"]))
        self.assertEqual("confirmed", context["history"][0]["decision"])

    def test_rejects_caller_supplied_actor_or_finding_id(self):
        for forbidden in ("actor_id", "finding_id"):
            payload = {**SCOPE, "decision": "confirmed", forbidden: "attacker-controlled"}
            status, _, body = call(self.app, "/v1/review/decision", payload)
            self.assertEqual(400, status)
            self.assertEqual("invalid request", body["error"])

    def test_authentication_is_required_and_invalid_token_rejected(self):
        status, _, _ = call(self.app, "/v1/review/context", SCOPE, token=None)
        self.assertEqual(401, status)
        status, _, _ = call(self.app, "/v1/review/context", SCOPE, token="wrong")
        self.assertEqual(401, status)

    def test_cross_production_scope_does_not_leak_finding(self):
        status, _, body = call(self.app, "/v1/review/context", {**SCOPE, "production_id": "other"})
        self.assertEqual(404, status)
        self.assertEqual("finding not found in requested scope", body["error"])

    def test_decision_and_note_are_bounded(self):
        status, _, _ = call(self.app, "/v1/review/decision", {**SCOPE, "decision": "delete"})
        self.assertEqual(400, status)
        status, _, _ = call(
            self.app,
            "/v1/review/decision",
            {**SCOPE, "decision": "confirmed", "note": "x" * 2001},
        )
        self.assertEqual(400, status)

    def test_method_is_restricted(self):
        status, _, _ = call(self.app, "/v1/review/context", SCOPE, method="GET")
        self.assertEqual(405, status)


if __name__ == "__main__":
    unittest.main()
