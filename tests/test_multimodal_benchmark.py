from __future__ import annotations

import json
import unittest
from pathlib import Path

from takekeeper.extraction import (
    HERO_PROPERTY_REGISTRY,
    FixtureExtractionTransport,
    GovernedMultimodalExtractor,
    TakeExtractionRequest,
)
from takekeeper.models import Baseline
from takekeeper.multimodal_benchmark import (
    BenchmarkTruth,
    evaluate_benchmark_run,
    evidence_window_iou,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "multimodal_eval" / "manifest.json"


def _load_manifest() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _property_specs() -> tuple:
    wanted = {("hero_mug", "hand"), ("maya", "jacket_state")}
    return tuple(
        spec
        for spec in HERO_PROPERTY_REGISTRY
        if (spec.entity_id, spec.property_key) in wanted
    )


def _baselines(manifest: dict) -> tuple[Baseline, ...]:
    return tuple(
        Baseline(
            production_id=manifest["production_id"],
            scene_id=manifest["scene_id"],
            entity_id=row["entity_id"],
            property_key=row["property_key"],
            baseline_value=row["baseline_value"],
            source_take_id=row["source_take_id"],
        )
        for row in manifest["baselines"]
    )


def _truth(case: dict) -> tuple[BenchmarkTruth, ...]:
    return tuple(BenchmarkTruth(**row) for row in case["truth"])


def _extract_case(manifest: dict, case: dict):
    transport = FixtureExtractionTransport({case["media_uri"]: case["response"]})
    extractor = GovernedMultimodalExtractor(
        transport,
        run_id_factory=lambda: f"run-{case['take_id']}",
    )
    request = TakeExtractionRequest(
        production_id=manifest["production_id"],
        scene_id=manifest["scene_id"],
        take_id=case["take_id"],
        media_uri=case["media_uri"],
        duration_ms=case["duration_ms"],
        properties=_property_specs(),
        extractor_model=manifest["extractor_model"],
        extractor_version=manifest["extractor_version"],
    )
    return extractor.extract(request)


class MultimodalBenchmarkTest(unittest.TestCase):
    def test_labeled_fixture_suite_scores_each_pipeline_boundary(self) -> None:
        manifest = _load_manifest()
        self.assertEqual(manifest["schema_version"], "takekeeper-multimodal-eval-v1")
        self.assertEqual(len(manifest["cases"]), 3)

        for case in manifest["cases"]:
            with self.subTest(case=case["name"]):
                result = _extract_case(manifest, case)
                score = evaluate_benchmark_run(
                    result=result,
                    truth=_truth(case),
                    baselines=_baselines(manifest),
                )

                self.assertEqual(score.expected_count, 2)
                self.assertEqual(score.predicted_count, 2)
                self.assertEqual(score.exact_value_accuracy, 1.0)
                self.assertGreaterEqual(score.mean_evidence_iou, 0.80)
                self.assertEqual(score.evidence_iou_at_50_rate, 1.0)
                self.assertEqual(score.disposition_accuracy, 1.0)
                self.assertEqual(score.projection_accuracy, 1.0)
                self.assertEqual(score.finding_status_accuracy, 1.0)
                self.assertEqual(score.unsupported_assertions, 0)

    def test_occluded_fixture_cannot_become_continuity_fact(self) -> None:
        manifest = _load_manifest()
        case = next(item for item in manifest["cases"] if item["name"] == "occluded_abstention")
        result = _extract_case(manifest, case)
        score = evaluate_benchmark_run(
            result=result,
            truth=_truth(case),
            baselines=_baselines(manifest),
        )

        self.assertEqual(score.disposition_accuracy, 1.0)
        self.assertEqual(score.projection_accuracy, 1.0)
        self.assertEqual(score.finding_status_accuracy, 1.0)

    def test_temporal_iou_penalizes_weak_localization_not_just_any_overlap(self) -> None:
        self.assertEqual(evidence_window_iou(0, 100, 200, 300), 0.0)
        self.assertAlmostEqual(evidence_window_iou(100, 200, 100, 200), 1.0)
        self.assertLess(evidence_window_iou(0, 1000, 450, 550), 0.11)

    def test_duplicate_truth_identity_fails_closed(self) -> None:
        manifest = _load_manifest()
        case = manifest["cases"][0]
        result = _extract_case(manifest, case)
        truth = _truth(case)

        with self.assertRaisesRegex(ValueError, "unique"):
            evaluate_benchmark_run(
                result=result,
                truth=(truth[0], truth[0]),
                baselines=_baselines(manifest),
            )


if __name__ == "__main__":
    unittest.main()
