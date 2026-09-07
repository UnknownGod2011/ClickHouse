from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .extraction import (
    HERO_PROPERTY_REGISTRY,
    FixtureExtractionTransport,
    GovernedMultimodalExtractor,
    PropertySpec,
    TakeExtractionRequest,
)
from .models import Baseline
from .multimodal_benchmark import BenchmarkEvaluation, BenchmarkTruth, evaluate_benchmark_run

REPORT_SCHEMA_VERSION = "takekeeper-multimodal-benchmark-report-v1"
SUPPORTED_MANIFEST_SCHEMA = "takekeeper-multimodal-eval-v1"


@dataclass(frozen=True, slots=True)
class BenchmarkThresholds:
    exact_value_accuracy: float = 1.0
    mean_evidence_iou: float = 0.80
    evidence_iou_at_50_rate: float = 1.0
    disposition_accuracy: float = 1.0
    projection_accuracy: float = 1.0
    finding_status_accuracy: float = 1.0
    max_unsupported_assertions: int = 0

    def __post_init__(self) -> None:
        for name in (
            "exact_value_accuracy",
            "mean_evidence_iou",
            "evidence_iou_at_50_rate",
            "disposition_accuracy",
            "projection_accuracy",
            "finding_status_accuracy",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_unsupported_assertions < 0:
            raise ValueError("max_unsupported_assertions must be non-negative")


@dataclass(frozen=True, slots=True)
class AggregateEvaluation:
    expected_count: int
    predicted_count: int
    exact_value_correct: int
    evidence_iou_sum: float
    evidence_iou_at_50_correct: int
    disposition_correct: int
    projection_correct: int
    finding_status_correct: int
    unsupported_assertions: int

    @classmethod
    def from_evaluations(cls, evaluations: Sequence[BenchmarkEvaluation]) -> "AggregateEvaluation":
        return cls(
            expected_count=sum(item.expected_count for item in evaluations),
            predicted_count=sum(item.predicted_count for item in evaluations),
            exact_value_correct=sum(item.exact_value_correct for item in evaluations),
            evidence_iou_sum=sum(item.evidence_iou_sum for item in evaluations),
            evidence_iou_at_50_correct=sum(item.evidence_iou_at_50_correct for item in evaluations),
            disposition_correct=sum(item.disposition_correct for item in evaluations),
            projection_correct=sum(item.projection_correct for item in evaluations),
            finding_status_correct=sum(item.finding_status_correct for item in evaluations),
            unsupported_assertions=sum(item.unsupported_assertions for item in evaluations),
        )

    @property
    def exact_value_accuracy(self) -> float:
        return self.exact_value_correct / self.expected_count if self.expected_count else 1.0

    @property
    def mean_evidence_iou(self) -> float:
        return self.evidence_iou_sum / self.expected_count if self.expected_count else 1.0

    @property
    def evidence_iou_at_50_rate(self) -> float:
        return self.evidence_iou_at_50_correct / self.expected_count if self.expected_count else 1.0

    @property
    def disposition_accuracy(self) -> float:
        return self.disposition_correct / self.expected_count if self.expected_count else 1.0

    @property
    def projection_accuracy(self) -> float:
        return self.projection_correct / self.expected_count if self.expected_count else 1.0

    @property
    def finding_status_accuracy(self) -> float:
        return self.finding_status_correct / self.expected_count if self.expected_count else 1.0


def _metric_dict(score: BenchmarkEvaluation | AggregateEvaluation) -> dict[str, int | float]:
    return {
        "expected_count": score.expected_count,
        "predicted_count": score.predicted_count,
        "exact_value_accuracy": round(score.exact_value_accuracy, 6),
        "mean_evidence_iou": round(score.mean_evidence_iou, 6),
        "evidence_iou_at_50_rate": round(score.evidence_iou_at_50_rate, 6),
        "disposition_accuracy": round(score.disposition_accuracy, 6),
        "projection_accuracy": round(score.projection_accuracy, 6),
        "finding_status_accuracy": round(score.finding_status_accuracy, 6),
        "unsupported_assertions": score.unsupported_assertions,
    }


def _validate_manifest(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != SUPPORTED_MANIFEST_SCHEMA:
        raise ValueError(f"unsupported benchmark manifest schema: {payload.get('schema_version')!r}")
    for field in ("production_id", "scene_id", "extractor_model", "extractor_version"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"manifest {field} must be a non-empty string")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must contain at least one benchmark case")
    names = [case.get("name") for case in cases if isinstance(case, Mapping)]
    if len(names) != len(cases) or any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("every benchmark case must have a non-empty name")
    if len(set(names)) != len(names):
        raise ValueError("benchmark case names must be unique")


def _baselines(manifest: Mapping[str, Any]) -> tuple[Baseline, ...]:
    rows = manifest.get("baselines")
    if not isinstance(rows, list):
        raise ValueError("manifest baselines must be an array")
    return tuple(
        Baseline(
            production_id=str(manifest["production_id"]),
            scene_id=str(manifest["scene_id"]),
            entity_id=str(row["entity_id"]),
            property_key=str(row["property_key"]),
            baseline_value=str(row["baseline_value"]),
            source_take_id=str(row["source_take_id"]),
        )
        for row in rows
    )


def _truth(case: Mapping[str, Any]) -> tuple[BenchmarkTruth, ...]:
    rows = case.get("truth")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"benchmark case {case.get('name')!r} must contain truth labels")
    return tuple(BenchmarkTruth(**row) for row in rows)


def _property_specs(truth: Sequence[BenchmarkTruth]) -> tuple[PropertySpec, ...]:
    registry = {(item.entity_id, item.property_key): item for item in HERO_PROPERTY_REGISTRY}
    identities = {(item.entity_id, item.property_key) for item in truth}
    unknown = sorted(identities - registry.keys())
    if unknown:
        raise ValueError(f"benchmark truth references unregistered properties: {unknown!r}")
    return tuple(registry[identity] for identity in sorted(identities))


def _extract_case(manifest: Mapping[str, Any], case: Mapping[str, Any], truth: Sequence[BenchmarkTruth]):
    media_uri = case.get("media_uri")
    response = case.get("response")
    if not isinstance(media_uri, str) or not media_uri.strip():
        raise ValueError(f"benchmark case {case.get('name')!r} media_uri must be non-empty")
    if not isinstance(response, Mapping):
        raise ValueError(f"benchmark case {case.get('name')!r} response must be an object")

    transport = FixtureExtractionTransport({media_uri: response})
    extractor = GovernedMultimodalExtractor(
        transport,
        run_id_factory=lambda: f"benchmark-{case['name']}",
    )
    request = TakeExtractionRequest(
        production_id=str(manifest["production_id"]),
        scene_id=str(manifest["scene_id"]),
        take_id=str(case["take_id"]),
        media_uri=media_uri,
        duration_ms=int(case["duration_ms"]),
        properties=_property_specs(truth),
        extractor_model=str(manifest["extractor_model"]),
        extractor_version=str(manifest["extractor_version"]),
    )
    return extractor.extract(request)


def _threshold_failures(metrics: Mapping[str, int | float], thresholds: BenchmarkThresholds) -> list[str]:
    failures: list[str] = []
    minimums = {
        "exact_value_accuracy": thresholds.exact_value_accuracy,
        "mean_evidence_iou": thresholds.mean_evidence_iou,
        "evidence_iou_at_50_rate": thresholds.evidence_iou_at_50_rate,
        "disposition_accuracy": thresholds.disposition_accuracy,
        "projection_accuracy": thresholds.projection_accuracy,
        "finding_status_accuracy": thresholds.finding_status_accuracy,
    }
    for metric, minimum in minimums.items():
        actual = float(metrics[metric])
        if actual < minimum:
            failures.append(f"{metric}={actual:.6f} below minimum {minimum:.6f}")
    unsupported = int(metrics["unsupported_assertions"])
    if unsupported > thresholds.max_unsupported_assertions:
        failures.append(
            f"unsupported_assertions={unsupported} above maximum {thresholds.max_unsupported_assertions}"
        )
    return failures


def run_manifest(
    manifest_bytes: bytes,
    *,
    thresholds: BenchmarkThresholds | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or BenchmarkThresholds()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("benchmark manifest must be valid UTF-8 JSON") from exc
    if not isinstance(manifest, Mapping):
        raise ValueError("benchmark manifest root must be an object")
    _validate_manifest(manifest)

    baselines = _baselines(manifest)
    case_reports: list[dict[str, Any]] = []
    evaluations: list[BenchmarkEvaluation] = []

    for case in manifest["cases"]:
        truth = _truth(case)
        result = _extract_case(manifest, case, truth)
        evaluation = evaluate_benchmark_run(result=result, truth=truth, baselines=baselines)
        evaluations.append(evaluation)
        metrics = _metric_dict(evaluation)
        failures = _threshold_failures(metrics, thresholds)
        case_reports.append(
            {
                "name": case["name"],
                "take_id": case["take_id"],
                "metrics": metrics,
                "passed": not failures,
                "failures": failures,
            }
        )

    aggregate = AggregateEvaluation.from_evaluations(evaluations)
    aggregate_metrics = _metric_dict(aggregate)
    aggregate_failures = _threshold_failures(aggregate_metrics, thresholds)
    failed_cases = [item["name"] for item in case_reports if not item["passed"]]
    failures = list(aggregate_failures)
    if failed_cases:
        failures.append("case threshold failure: " + ", ".join(failed_cases))

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "manifest_schema_version": manifest["schema_version"],
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "candidate": {
            "extractor_model": manifest["extractor_model"],
            "extractor_version": manifest["extractor_version"],
        },
        "thresholds": asdict(thresholds),
        "aggregate": aggregate_metrics,
        "cases": case_reports,
        "passed": not failures,
        "failures": failures,
    }


def render_report(report: Mapping[str, Any]) -> str:
    """Return stable machine-readable JSON suitable for diffing and archival."""

    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TakeKeeper's governed multimodal benchmark gate.")
    parser.add_argument("manifest", type=Path, help="Path to a takekeeper-multimodal-eval-v1 manifest")
    parser.add_argument("--output", type=Path, help="Optional JSON report path; stdout is always emitted")
    parser.add_argument("--min-exact-value", type=float, default=1.0)
    parser.add_argument("--min-mean-iou", type=float, default=0.80)
    parser.add_argument("--min-iou50-rate", type=float, default=1.0)
    parser.add_argument("--min-disposition", type=float, default=1.0)
    parser.add_argument("--min-projection", type=float, default=1.0)
    parser.add_argument("--min-finding-status", type=float, default=1.0)
    parser.add_argument("--max-unsupported-assertions", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        thresholds = BenchmarkThresholds(
            exact_value_accuracy=args.min_exact_value,
            mean_evidence_iou=args.min_mean_iou,
            evidence_iou_at_50_rate=args.min_iou50_rate,
            disposition_accuracy=args.min_disposition,
            projection_accuracy=args.min_projection,
            finding_status_accuracy=args.min_finding_status,
            max_unsupported_assertions=args.max_unsupported_assertions,
        )
        manifest_bytes = args.manifest.read_bytes()
        report = run_manifest(manifest_bytes, thresholds=thresholds)
        rendered = render_report(report)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        sys.stdout.write(rendered)
        return 0 if report["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        sys.stderr.write(f"takekeeper benchmark error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
