from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from takekeeper.benchmark_cli import BenchmarkThresholds
from takekeeper.extraction import FixtureExtractionTransport
from takekeeper.live_candidate_benchmark import MEDIA_MAP_SCHEMA_VERSION, run_live_candidate

FIXTURE = Path(__file__).parent / "fixtures" / "multimodal_eval" / "manifest.json"


def _fixture_inputs():
    manifest_bytes = FIXTURE.read_bytes()
    manifest = json.loads(manifest_bytes)
    uri_by_case = {case["name"]: f"https://media.example/{case['take_id']}.mp4?sig=super-secret" for case in manifest["cases"]}
    responses = {
        uri_by_case[case["name"]]: case["response"]
        for case in manifest["cases"]
    }
    media_map = {
        "schema_version": MEDIA_MAP_SCHEMA_VERSION,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "cases": uri_by_case,
    }
    media_map_bytes = json.dumps(media_map, sort_keys=True).encode("utf-8")
    return manifest_bytes, media_map_bytes, responses, uri_by_case


class LiveCandidateBenchmarkTests(unittest.TestCase):
    def test_runs_same_governed_scoring_path_with_external_media(self):
        manifest_bytes, media_map_bytes, responses, _ = _fixture_inputs()
        report = run_live_candidate(
            manifest_bytes,
            media_map_bytes,
            transport=FixtureExtractionTransport(responses),
            extractor_model="gemini-candidate",
            extractor_version="candidate-2026-09-07",
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["run_mode"], "external_media_candidate")
        self.assertEqual(report["candidate"]["extractor_model"], "gemini-candidate")
        self.assertEqual(report["candidate"]["extractor_version"], "candidate-2026-09-07")
        self.assertEqual(report["manifest_sha256"], hashlib.sha256(manifest_bytes).hexdigest())
        self.assertEqual(report["media_map_sha256"], hashlib.sha256(media_map_bytes).hexdigest())
        self.assertEqual(report["aggregate"]["exact_value_accuracy"], 1.0)
        self.assertEqual(report["aggregate"]["finding_status_accuracy"], 1.0)

    def test_report_never_contains_signed_media_uris(self):
        manifest_bytes, media_map_bytes, responses, uri_by_case = _fixture_inputs()
        report = run_live_candidate(
            manifest_bytes,
            media_map_bytes,
            transport=FixtureExtractionTransport(responses),
            extractor_model="gemini-candidate",
            extractor_version="candidate-v1",
        )
        rendered = json.dumps(report, sort_keys=True)
        for uri in uri_by_case.values():
            self.assertNotIn(uri, rendered)
        self.assertNotIn("super-secret", rendered)

    def test_manifest_digest_mismatch_fails_before_transport(self):
        manifest_bytes, media_map_bytes, responses, _ = _fixture_inputs()
        payload = json.loads(media_map_bytes)
        payload["manifest_sha256"] = "0" * 64
        transport = FixtureExtractionTransport(responses)

        with self.assertRaisesRegex(ValueError, "manifest_sha256"):
            run_live_candidate(
                manifest_bytes,
                json.dumps(payload).encode("utf-8"),
                transport=transport,
                extractor_model="gemini-candidate",
                extractor_version="candidate-v1",
            )
        self.assertEqual(transport.calls, [])

    def test_missing_or_extra_case_fails_before_transport(self):
        manifest_bytes, media_map_bytes, responses, _ = _fixture_inputs()
        payload = json.loads(media_map_bytes)
        payload["cases"].pop("matching_clear_take")
        payload["cases"]["unexpected"] = "https://media.example/extra.mp4"
        transport = FixtureExtractionTransport(responses)

        with self.assertRaisesRegex(ValueError, "case set mismatch"):
            run_live_candidate(
                manifest_bytes,
                json.dumps(payload).encode("utf-8"),
                transport=transport,
                extractor_model="gemini-candidate",
                extractor_version="candidate-v1",
            )
        self.assertEqual(transport.calls, [])

    def test_candidate_identity_overrides_fixture_identity(self):
        manifest_bytes, media_map_bytes, responses, _ = _fixture_inputs()
        report = run_live_candidate(
            manifest_bytes,
            media_map_bytes,
            transport=FixtureExtractionTransport(responses),
            extractor_model="models/gemini-2.5-pro",
            extractor_version="live-eval-17",
        )
        self.assertNotEqual(report["candidate"]["extractor_model"], "fixture-model")
        self.assertEqual(report["candidate"]["extractor_model"], "models/gemini-2.5-pro")

    def test_threshold_failure_remains_release_gate_failure(self):
        manifest_bytes, media_map_bytes, responses, _ = _fixture_inputs()
        first_uri = next(iter(responses))
        mutated = dict(responses)
        response = json.loads(json.dumps(mutated[first_uri]))
        response["observations"][0]["normalized_value"] = "right"
        mutated[first_uri] = response

        report = run_live_candidate(
            manifest_bytes,
            media_map_bytes,
            transport=FixtureExtractionTransport(mutated),
            extractor_model="gemini-candidate",
            extractor_version="candidate-v1",
            thresholds=BenchmarkThresholds(),
        )
        self.assertFalse(report["passed"])
        self.assertLess(report["aggregate"]["exact_value_accuracy"], 1.0)

    def test_media_map_uri_length_is_bounded(self):
        manifest_bytes, media_map_bytes, responses, _ = _fixture_inputs()
        payload = json.loads(media_map_bytes)
        payload["cases"]["matching_clear_take"] = "https://media.example/" + ("x" * 5000) + ".mp4"
        transport = FixtureExtractionTransport(responses)
        with self.assertRaisesRegex(ValueError, "too long"):
            run_live_candidate(
                manifest_bytes,
                json.dumps(payload).encode("utf-8"),
                transport=transport,
                extractor_model="gemini-candidate",
                extractor_version="candidate-v1",
            )
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
