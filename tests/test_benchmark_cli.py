from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from takekeeper.benchmark_cli import (
    REPORT_SCHEMA_VERSION,
    BenchmarkThresholds,
    main,
    render_report,
    run_manifest,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "multimodal_eval" / "manifest.json"


class BenchmarkCliTest(unittest.TestCase):
    def test_default_fixture_manifest_passes_release_gate(self) -> None:
        manifest_bytes = FIXTURE_PATH.read_bytes()
        report = run_manifest(manifest_bytes)

        self.assertEqual(report["schema_version"], REPORT_SCHEMA_VERSION)
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(len(report["cases"]), 3)
        self.assertTrue(all(case["passed"] for case in report["cases"]))
        self.assertEqual(report["aggregate"]["expected_count"], 6)
        self.assertEqual(report["aggregate"]["predicted_count"], 6)
        self.assertEqual(report["aggregate"]["exact_value_accuracy"], 1.0)
        self.assertGreaterEqual(report["aggregate"]["mean_evidence_iou"], 0.80)
        self.assertEqual(report["aggregate"]["evidence_iou_at_50_rate"], 1.0)
        self.assertEqual(report["aggregate"]["disposition_accuracy"], 1.0)
        self.assertEqual(report["aggregate"]["projection_accuracy"], 1.0)
        self.assertEqual(report["aggregate"]["finding_status_accuracy"], 1.0)
        self.assertEqual(report["aggregate"]["unsupported_assertions"], 0)
        self.assertEqual(len(report["manifest_sha256"]), 64)

    def test_regressed_fixture_fails_gate_with_case_diagnostic(self) -> None:
        manifest = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        manifest["cases"][0]["response"]["observations"][0]["normalized_value"] = "right"
        payload = json.dumps(manifest, sort_keys=True).encode("utf-8")

        report = run_manifest(payload)

        self.assertFalse(report["passed"])
        failed_case = next(case for case in report["cases"] if case["name"] == "matching_clear_take")
        self.assertFalse(failed_case["passed"])
        self.assertTrue(any("exact_value_accuracy" in item for item in failed_case["failures"]))
        self.assertTrue(any("case threshold failure" in item for item in report["failures"]))

    def test_report_rendering_is_stable_and_sorted(self) -> None:
        report = run_manifest(FIXTURE_PATH.read_bytes())
        first = render_report(report)
        second = render_report(report)

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        decoded = json.loads(first)
        self.assertEqual(decoded, report)

    def test_thresholds_fail_closed_outside_valid_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            BenchmarkThresholds(mean_evidence_iou=1.01)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            BenchmarkThresholds(max_unsupported_assertions=-1)

    def test_cli_writes_identical_report_and_returns_zero_on_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "reports" / "benchmark.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main([str(FIXTURE_PATH), "--output", str(output_path)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(output_path.read_text(encoding="utf-8"), stdout.getvalue())
            self.assertTrue(json.loads(stdout.getvalue())["passed"])

    def test_cli_returns_one_for_quality_regression_and_two_for_bad_manifest(self) -> None:
        manifest = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        manifest["cases"][0]["response"]["observations"][0]["normalized_value"] = "right"

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            regressed_path = directory_path / "regressed.json"
            regressed_path.write_text(json.dumps(manifest), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([str(regressed_path)])
            self.assertEqual(exit_code, 1)
            self.assertFalse(json.loads(stdout.getvalue())["passed"])

            invalid_path = directory_path / "invalid.json"
            invalid_path.write_text("not-json", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = main([str(invalid_path)])
            self.assertEqual(exit_code, 2)
            self.assertIn("benchmark error", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
