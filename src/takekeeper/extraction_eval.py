from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .extraction import ExtractedObservation


@dataclass(frozen=True, slots=True)
class TruthObservation:
    entity_id: str
    property_key: str
    normalized_value: str
    evidence_start_ms: int
    evidence_end_ms: int
    observable: bool = True

    def __post_init__(self) -> None:
        if not self.entity_id or not self.property_key or not self.normalized_value:
            raise ValueError("truth identity/value must be non-empty")
        if self.evidence_start_ms < 0 or self.evidence_end_ms < self.evidence_start_ms:
            raise ValueError("invalid truth evidence window")


@dataclass(frozen=True, slots=True)
class ExtractionEvaluation:
    expected_count: int
    predicted_count: int
    exact_value_correct: int
    evidence_overlap_correct: int
    unsupported_assertions: int
    abstention_correct: int

    @property
    def exact_value_accuracy(self) -> float:
        return self.exact_value_correct / self.expected_count if self.expected_count else 1.0

    @property
    def evidence_overlap_rate(self) -> float:
        return self.evidence_overlap_correct / self.expected_count if self.expected_count else 1.0


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return max(a_start, b_start) <= min(a_end, b_end)


def evaluate_extraction(
    predicted: Iterable[ExtractedObservation], truth: Iterable[TruthObservation]
) -> ExtractionEvaluation:
    predicted_map = {
        (item.observation.entity_id, item.observation.property_key): item for item in predicted
    }
    truth_list = list(truth)
    truth_map = {(item.entity_id, item.property_key): item for item in truth_list}
    if len(truth_map) != len(truth_list):
        raise ValueError("truth observations must have unique entity/property identities")

    exact = 0
    overlap = 0
    unsupported = 0
    abstention_correct = 0

    for identity, expected in truth_map.items():
        actual = predicted_map.get(identity)
        if actual is None:
            continue
        value = actual.observation.normalized_value
        if value == expected.normalized_value:
            exact += 1
        if _overlaps(
            actual.observation.evidence_start_ms,
            actual.observation.evidence_end_ms,
            expected.evidence_start_ms,
            expected.evidence_end_ms,
        ):
            overlap += 1
        is_abstention = value in ("unknown", "uncertain")
        if not expected.observable:
            if is_abstention:
                abstention_correct += 1
            else:
                unsupported += 1

    for identity, actual in predicted_map.items():
        if identity not in truth_map and actual.observation.normalized_value not in ("unknown", "uncertain"):
            unsupported += 1

    return ExtractionEvaluation(
        expected_count=len(truth_map),
        predicted_count=len(predicted_map),
        exact_value_correct=exact,
        evidence_overlap_correct=overlap,
        unsupported_assertions=unsupported,
        abstention_correct=abstention_correct,
    )
