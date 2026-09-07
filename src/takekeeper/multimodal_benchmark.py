from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .extraction import ExtractedObservation, ExtractionDisposition, ExtractionRunResult
from .extraction_projection import compare_extraction_to_baselines
from .models import Baseline, FindingStatus

ExpectedFindingStatus = FindingStatus | Literal["none"]


@dataclass(frozen=True, slots=True)
class BenchmarkTruth:
    """Ground truth for one configured property in a labeled take fixture."""

    entity_id: str
    property_key: str
    normalized_value: str
    evidence_start_ms: int
    evidence_end_ms: int
    expected_disposition: ExtractionDisposition
    expected_projected: bool
    expected_finding_status: ExpectedFindingStatus

    def __post_init__(self) -> None:
        if not self.entity_id or not self.property_key or not self.normalized_value:
            raise ValueError("benchmark truth identity/value must be non-empty")
        if self.evidence_start_ms < 0 or self.evidence_end_ms < self.evidence_start_ms:
            raise ValueError("benchmark truth evidence window is invalid")


@dataclass(frozen=True, slots=True)
class BenchmarkEvaluation:
    expected_count: int
    predicted_count: int
    exact_value_correct: int
    evidence_iou_sum: float
    evidence_iou_at_50_correct: int
    disposition_correct: int
    projection_correct: int
    finding_status_correct: int
    unsupported_assertions: int

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


def evidence_window_iou(
    predicted_start_ms: int,
    predicted_end_ms: int,
    truth_start_ms: int,
    truth_end_ms: int,
) -> float:
    """Inclusive temporal IoU for bounded millisecond evidence windows."""

    intersection_start = max(predicted_start_ms, truth_start_ms)
    intersection_end = min(predicted_end_ms, truth_end_ms)
    if intersection_end < intersection_start:
        return 0.0

    intersection = intersection_end - intersection_start + 1
    union_start = min(predicted_start_ms, truth_start_ms)
    union_end = max(predicted_end_ms, truth_end_ms)
    union = union_end - union_start + 1
    return intersection / union


def _unique_prediction_map(
    predicted: Iterable[ExtractedObservation],
) -> dict[tuple[str, str], ExtractedObservation]:
    prediction_map: dict[tuple[str, str], ExtractedObservation] = {}
    for item in predicted:
        identity = (item.observation.entity_id, item.observation.property_key)
        if identity in prediction_map:
            raise ValueError("predicted observations must have unique entity/property identities")
        prediction_map[identity] = item
    return prediction_map


def evaluate_benchmark_run(
    *,
    result: ExtractionRunResult,
    truth: Iterable[BenchmarkTruth],
    baselines: Iterable[Baseline],
) -> BenchmarkEvaluation:
    """Score extraction quality and the downstream continuity safety boundary separately.

    The evaluator intentionally scores four independent concerns: normalized values,
    temporal evidence localization, confidence/disposition policy, and whether the
    extraction is permitted to become a current continuity fact. It also validates the
    final continuity finding status so a model can score well on JSON shape while still
    failing the production-memory safety contract.
    """

    truth_list = list(truth)
    truth_map = {(item.entity_id, item.property_key): item for item in truth_list}
    if len(truth_map) != len(truth_list):
        raise ValueError("benchmark truth must have unique entity/property identities")

    prediction_map = _unique_prediction_map(result.observations)
    findings, projection = compare_extraction_to_baselines(
        result=result,
        baselines=tuple(baselines),
    )
    projection_map = {
        (decision.entity_id, decision.property_key): decision for decision in projection.decisions
    }
    finding_map = {(finding.entity_id, finding.property_key): finding.status for finding in findings}

    exact_value_correct = 0
    evidence_iou_sum = 0.0
    evidence_iou_at_50_correct = 0
    disposition_correct = 0
    projection_correct = 0
    finding_status_correct = 0

    for identity, expected in truth_map.items():
        actual = prediction_map.get(identity)
        if actual is None:
            continue

        if actual.observation.normalized_value == expected.normalized_value:
            exact_value_correct += 1

        iou = evidence_window_iou(
            actual.observation.evidence_start_ms,
            actual.observation.evidence_end_ms,
            expected.evidence_start_ms,
            expected.evidence_end_ms,
        )
        evidence_iou_sum += iou
        if iou >= 0.50:
            evidence_iou_at_50_correct += 1

        if actual.disposition == expected.expected_disposition:
            disposition_correct += 1

        decision = projection_map.get(identity)
        if decision is not None and decision.projected == expected.expected_projected:
            projection_correct += 1

        actual_status: ExpectedFindingStatus = finding_map.get(identity, "none")
        if actual_status == expected.expected_finding_status:
            finding_status_correct += 1

    unsupported_assertions = 0
    for identity, actual in prediction_map.items():
        if identity not in truth_map and actual.observation.normalized_value not in ("unknown", "uncertain"):
            unsupported_assertions += 1

    return BenchmarkEvaluation(
        expected_count=len(truth_map),
        predicted_count=len(prediction_map),
        exact_value_correct=exact_value_correct,
        evidence_iou_sum=evidence_iou_sum,
        evidence_iou_at_50_correct=evidence_iou_at_50_correct,
        disposition_correct=disposition_correct,
        projection_correct=projection_correct,
        finding_status_correct=finding_status_correct,
        unsupported_assertions=unsupported_assertions,
    )
