from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .continuity import compare_observations
from .extraction import ExtractedObservation, ExtractionRunResult
from .models import Baseline, Finding, Observation

ProjectionReason = Literal[
    "eligible",
    "needs_confirmation",
    "abstention_value",
    "visibility_not_clear",
    "temporal_support_not_sustained",
    "scope_mismatch",
]


@dataclass(frozen=True, slots=True)
class ProjectionDecision:
    """Audit-friendly decision for one extracted property at the continuity boundary."""

    entity_id: str
    property_key: str
    projected: bool
    reason: ProjectionReason
    observation: Observation | None


@dataclass(frozen=True, slots=True)
class ContinuityProjection:
    """Policy-qualified observations plus the reasons excluded evidence stayed out."""

    production_id: str
    scene_id: str
    take_id: str
    observations: tuple[Observation, ...]
    decisions: tuple[ProjectionDecision, ...]


class ExtractionProjectionError(RuntimeError):
    """Validated extraction state was internally inconsistent with trusted scope."""


def _projection_reason(
    extracted: ExtractedObservation,
    *,
    production_id: str,
    scene_id: str,
    take_id: str,
) -> ProjectionReason:
    observation = extracted.observation
    if (
        observation.production_id != production_id
        or observation.scene_id != scene_id
        or observation.take_id != take_id
    ):
        return "scope_mismatch"
    if observation.normalized_value in ("unknown", "uncertain"):
        return "abstention_value"
    if extracted.visibility_state != "clear":
        return "visibility_not_clear"
    if extracted.temporal_support != "sustained":
        return "temporal_support_not_sustained"
    if extracted.disposition != "machine_high_confidence":
        return "needs_confirmation"
    return "eligible"


def project_extraction_for_continuity(result: ExtractionRunResult) -> ContinuityProjection:
    """Promote only policy-eligible machine evidence into continuity analysis.

    The extractor is deliberately allowed to preserve uncertain evidence for review and
    provenance. This boundary is stricter: continuity comparison receives only clear,
    sustained, non-abstaining observations already classified machine-high-confidence.
    Every exclusion is retained as an explicit decision so a missing projected observation
    becomes ``insufficient_evidence`` rather than a false mismatch.
    """

    projected: list[Observation] = []
    decisions: list[ProjectionDecision] = []
    seen: set[tuple[str, str]] = set()

    for extracted in result.observations:
        observation = extracted.observation
        identity = (observation.entity_id, observation.property_key)
        if identity in seen:
            raise ExtractionProjectionError("extraction result contains duplicate property identity")
        seen.add(identity)

        reason = _projection_reason(
            extracted,
            production_id=result.production_id,
            scene_id=result.scene_id,
            take_id=result.take_id,
        )
        if reason == "scope_mismatch":
            raise ExtractionProjectionError("extracted observation drifted from trusted run scope")

        is_projected = reason == "eligible"
        if is_projected:
            projected.append(observation)
        decisions.append(
            ProjectionDecision(
                entity_id=observation.entity_id,
                property_key=observation.property_key,
                projected=is_projected,
                reason=reason,
                observation=observation,
            )
        )

    return ContinuityProjection(
        production_id=result.production_id,
        scene_id=result.scene_id,
        take_id=result.take_id,
        observations=tuple(projected),
        decisions=tuple(decisions),
    )


def compare_extraction_to_baselines(
    *,
    result: ExtractionRunResult,
    baselines: tuple[Baseline, ...] | list[Baseline],
    confirmation_threshold: float = 0.80,
) -> tuple[list[Finding], ContinuityProjection]:
    """Run continuity comparison only after governed extraction projection."""

    projection = project_extraction_for_continuity(result)
    findings = compare_observations(
        production_id=projection.production_id,
        scene_id=projection.scene_id,
        take_id=projection.take_id,
        observations=projection.observations,
        baselines=baselines,
        confirmation_threshold=confirmation_threshold,
    )
    return findings, projection
