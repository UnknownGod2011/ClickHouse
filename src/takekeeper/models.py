from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VerificationState = Literal["unverified", "human_confirmed", "human_rejected"]
FindingStatus = Literal["mismatch", "needs_confirmation", "insufficient_evidence", "missing_baseline"]


@dataclass(frozen=True, slots=True)
class Observation:
    production_id: str
    scene_id: str
    take_id: str
    entity_id: str
    property_key: str
    normalized_value: str
    confidence: float
    evidence_start_ms: int
    evidence_end_ms: int
    verification_state: VerificationState = "unverified"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.evidence_start_ms < 0 or self.evidence_end_ms < self.evidence_start_ms:
            raise ValueError("invalid evidence window")


@dataclass(frozen=True, slots=True)
class Baseline:
    production_id: str
    scene_id: str
    entity_id: str
    property_key: str
    baseline_value: str
    source_take_id: str


@dataclass(frozen=True, slots=True)
class Finding:
    production_id: str
    scene_id: str
    take_id: str
    entity_id: str
    property_key: str
    baseline_value: str | None
    observed_value: str | None
    confidence: float | None
    status: FindingStatus
    evidence_start_ms: int | None
    evidence_end_ms: int | None
    baseline_source_take_id: str | None
