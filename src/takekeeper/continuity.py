from __future__ import annotations

from collections.abc import Iterable

from .models import Baseline, Finding, Observation


def compare_observations(
    *, production_id: str, scene_id: str, take_id: str,
    observations: Iterable[Observation], baselines: Iterable[Baseline],
    confirmation_threshold: float = 0.80,
) -> list[Finding]:
    """Compare a take against approved baselines without inventing missing evidence."""
    if not 0.0 <= confirmation_threshold <= 1.0:
        raise ValueError("confirmation_threshold must be between 0 and 1")
    obs_by_key = {(o.entity_id, o.property_key): o for o in observations if o.production_id == production_id and o.scene_id == scene_id and o.take_id == take_id}
    baseline_by_key = {(b.entity_id, b.property_key): b for b in baselines if b.production_id == production_id and b.scene_id == scene_id}
    findings: list[Finding] = []
    for key, baseline in baseline_by_key.items():
        obs = obs_by_key.get(key)
        if obs is None:
            findings.append(Finding(production_id, scene_id, take_id, baseline.entity_id, baseline.property_key, baseline.baseline_value, None, None, "insufficient_evidence", None, None, baseline.source_take_id))
            continue
        if obs.normalized_value == baseline.baseline_value:
            continue
        status = "mismatch" if obs.confidence >= confirmation_threshold else "needs_confirmation"
        findings.append(Finding(production_id, scene_id, take_id, obs.entity_id, obs.property_key, baseline.baseline_value, obs.normalized_value, obs.confidence, status, obs.evidence_start_ms, obs.evidence_end_ms, baseline.source_take_id))
    for key, obs in obs_by_key.items():
        if key not in baseline_by_key:
            findings.append(Finding(production_id, scene_id, take_id, obs.entity_id, obs.property_key, None, obs.normalized_value, obs.confidence, "missing_baseline", obs.evidence_start_ms, obs.evidence_end_ms, None))
    return sorted(findings, key=lambda f: (f.property_key, f.entity_id))
