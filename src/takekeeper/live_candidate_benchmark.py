from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .benchmark_cli import (
    AggregateEvaluation,
    BenchmarkThresholds,
    REPORT_SCHEMA_VERSION,
    _baselines,
    _metric_dict,
    _property_specs,
    _threshold_failures,
    _truth,
    _validate_manifest,
    render_report,
)
from .extraction import ExtractionTransport, GovernedMultimodalExtractor, TakeExtractionRequest
from .google_genai_transport import (
    GoogleGenAIExtractionTransport,
    GoogleGenAITransportConfig,
    create_google_genai_client,
)
from .multimodal_benchmark import BenchmarkEvaluation, evaluate_benchmark_run

MEDIA_MAP_SCHEMA_VERSION = "takekeeper-live-media-map-v1"
RUN_MODE = "external_media_candidate"


def _decode_json_object(payload_bytes: bytes, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} root must be an object")
    return payload


def _validate_candidate_identity(model: str, version: str) -> None:
    if not model.strip():
        raise ValueError("candidate model must be non-empty")
    if not version.strip():
        raise ValueError("candidate extractor version must be non-empty")
    if len(model) > 200 or len(version) > 200:
        raise ValueError("candidate identity fields must be at most 200 characters")


def _validated_media_map(
    payload: Mapping[str, Any],
    *,
    manifest_sha256: str,
    case_names: set[str],
) -> dict[str, str]:
    if payload.get("schema_version") != MEDIA_MAP_SCHEMA_VERSION:
        raise ValueError(f"unsupported live media map schema: {payload.get('schema_version')!r}")
    if payload.get("manifest_sha256") != manifest_sha256:
        raise ValueError("live media map manifest_sha256 does not match the benchmark manifest")

    cases = payload.get("cases")
    if not isinstance(cases, Mapping):
        raise ValueError("live media map cases must be an object")
    if set(cases) != case_names:
        missing = sorted(case_names - set(cases))
        unexpected = sorted(set(cases) - case_names)
        raise ValueError(f"live media map case set mismatch; missing={missing!r} unexpected={unexpected!r}")

    result: dict[str, str] = {}
    for case_name, media_uri in cases.items():
        if not isinstance(media_uri, str) or not media_uri.strip():
            raise ValueError(f"live media URI for {case_name!r} must be a non-empty string")
        if len(media_uri) > 4096:
            raise ValueError(f"live media URI for {case_name!r} is too long")
        result[str(case_name)] = media_uri
    return result


def run_live_candidate(
    manifest_bytes: bytes,
    media_map_bytes: bytes,
    *,
    transport: ExtractionTransport,
    extractor_model: str,
    extractor_version: str,
    thresholds: BenchmarkThresholds | None = None,
) -> dict[str, Any]:
    """Evaluate external media with a candidate transport against immutable benchmark truth.

    The URI map is deliberately separate from the truth manifest. Its bytes are fingerprinted in
    the report, while URI values themselves are never emitted because HTTPS entries may be signed.
    """

    thresholds = thresholds or BenchmarkThresholds()
    _validate_candidate_identity(extractor_model, extractor_version)

    manifest = _decode_json_object(manifest_bytes, label="benchmark manifest")
    _validate_manifest(manifest)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    case_names = {str(case["name"]) for case in manifest["cases"]}

    media_map_payload = _decode_json_object(media_map_bytes, label="live media map")
    media_by_case = _validated_media_map(
        media_map_payload,
        manifest_sha256=manifest_sha256,
        case_names=case_names,
    )

    baselines = _baselines(manifest)
    case_reports: list[dict[str, Any]] = []
    evaluations: list[BenchmarkEvaluation] = []

    for case in manifest["cases"]:
        case_name = str(case["name"])
        truth = _truth(case)
        extractor = GovernedMultimodalExtractor(
            transport,
            run_id_factory=lambda name=case_name: f"live-benchmark-{name}",
        )
        request = TakeExtractionRequest(
            production_id=str(manifest["production_id"]),
            scene_id=str(manifest["scene_id"]),
            take_id=str(case["take_id"]),
            media_uri=media_by_case[case_name],
            duration_ms=int(case["duration_ms"]),
            properties=_property_specs(truth),
            extractor_model=extractor_model,
            extractor_version=extractor_version,
        )
        result = extractor.extract(request)
        evaluation = evaluate_benchmark_run(result=result, truth=truth, baselines=baselines)
        evaluations.append(evaluation)
        metrics = _metric_dict(evaluation)
        failures = _threshold_failures(metrics, thresholds)
        case_reports.append(
            {
                "name": case_name,
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
        "manifest_sha256": manifest_sha256,
        "media_map_sha256": hashlib.sha256(media_map_bytes).hexdigest(),
        "run_mode": RUN_MODE,
        "candidate": {
            "extractor_model": extractor_model,
            "extractor_version": extractor_version,
        },
        "thresholds": {
            "exact_value_accuracy": thresholds.exact_value_accuracy,
            "mean_evidence_iou": thresholds.mean_evidence_iou,
            "evidence_iou_at_50_rate": thresholds.evidence_iou_at_50_rate,
            "disposition_accuracy": thresholds.disposition_accuracy,
            "projection_accuracy": thresholds.projection_accuracy,
            "finding_status_accuracy": thresholds.finding_status_accuracy,
            "max_unsupported_assertions": thresholds.max_unsupported_assertions,
        },
        "aggregate": aggregate_metrics,
        "cases": case_reports,
        "passed": not failures,
        "failures": failures,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate trusted external video URIs with Gemini against TakeKeeper benchmark truth."
    )
    parser.add_argument("manifest", type=Path, help="Path to immutable takekeeper-multimodal-eval-v1 manifest")
    parser.add_argument("media_map", type=Path, help="Path to takekeeper-live-media-map-v1 JSON")
    parser.add_argument("--model", required=True, help="Gemini/Vertex model identifier")
    parser.add_argument("--extractor-version", required=True, help="Operator-defined candidate/version label")
    parser.add_argument("--vertex-ai", action="store_true", help="Use Vertex AI with Application Default Credentials")
    parser.add_argument("--project", help="Vertex AI project; defaults to GOOGLE_CLOUD_PROJECT")
    parser.add_argument("--location", help="Vertex AI location; defaults to GOOGLE_CLOUD_LOCATION")
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
        client = create_google_genai_client(
            vertex_ai=args.vertex_ai,
            project=args.project or os.environ.get("GOOGLE_CLOUD_PROJECT"),
            location=args.location or os.environ.get("GOOGLE_CLOUD_LOCATION"),
        )
        transport = GoogleGenAIExtractionTransport(
            client,
            GoogleGenAITransportConfig(model=args.model),
        )
        report = run_live_candidate(
            args.manifest.read_bytes(),
            args.media_map.read_bytes(),
            transport=transport,
            extractor_model=args.model,
            extractor_version=args.extractor_version,
            thresholds=thresholds,
        )
        rendered = render_report(report)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        sys.stdout.write(rendered)
        return 0 if report["passed"] else 1
    except Exception as exc:
        # Provider/credential failures are intentionally reduced to the exception class: SDK errors
        # can contain request metadata or URLs. Detailed debugging remains available via local tooling.
        if isinstance(exc, (OSError, ValueError, KeyError, TypeError)):
            message = str(exc)
        else:
            message = exc.__class__.__name__
        sys.stderr.write(f"takekeeper live benchmark error: {message}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
