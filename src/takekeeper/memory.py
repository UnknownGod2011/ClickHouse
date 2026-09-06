from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .models import Baseline, Finding, Observation


class ProductionMemory(Protocol):
    def upsert_observations(self, observations: Iterable[Observation]) -> None: ...
    def list_observations(self, *, production_id: str, scene_id: str, take_id: str) -> list[Observation]: ...
    def upsert_baselines(self, baselines: Iterable[Baseline]) -> None: ...
    def list_baselines(self, *, production_id: str, scene_id: str) -> list[Baseline]: ...
    def replace_findings(self, *, production_id: str, scene_id: str, take_id: str, findings: Iterable[Finding]) -> None: ...
    def list_findings(self, *, production_id: str, scene_id: str, take_id: str) -> list[Finding]: ...


class InMemoryProductionMemory:
    """Deterministic reference store with the same tenant/scope boundaries as ClickHouse."""

    def __init__(self) -> None:
        self._observations: dict[tuple[str, str, str, str, str], Observation] = {}
        self._baselines: dict[tuple[str, str, str, str], Baseline] = {}
        self._findings: dict[tuple[str, str, str, str, str], Finding] = {}

    def upsert_observations(self, observations: Iterable[Observation]) -> None:
        for observation in observations:
            key = (observation.production_id, observation.scene_id, observation.take_id, observation.entity_id, observation.property_key)
            self._observations[key] = observation

    def list_observations(self, *, production_id: str, scene_id: str, take_id: str) -> list[Observation]:
        scope = (production_id, scene_id, take_id)
        rows = [row for key, row in self._observations.items() if key[:3] == scope]
        return sorted(rows, key=lambda row: (row.entity_id, row.property_key))

    def upsert_baselines(self, baselines: Iterable[Baseline]) -> None:
        for baseline in baselines:
            key = (baseline.production_id, baseline.scene_id, baseline.entity_id, baseline.property_key)
            self._baselines[key] = baseline

    def list_baselines(self, *, production_id: str, scene_id: str) -> list[Baseline]:
        scope = (production_id, scene_id)
        rows = [row for key, row in self._baselines.items() if key[:2] == scope]
        return sorted(rows, key=lambda row: (row.entity_id, row.property_key))

    def replace_findings(self, *, production_id: str, scene_id: str, take_id: str, findings: Iterable[Finding]) -> None:
        scope = (production_id, scene_id, take_id)
        self._findings = {key: value for key, value in self._findings.items() if key[:3] != scope}
        for finding in findings:
            if (finding.production_id, finding.scene_id, finding.take_id) != scope:
                raise ValueError("finding scope does not match replacement scope")
            key = (finding.production_id, finding.scene_id, finding.take_id, finding.entity_id, finding.property_key)
            self._findings[key] = finding

    def list_findings(self, *, production_id: str, scene_id: str, take_id: str) -> list[Finding]:
        scope = (production_id, scene_id, take_id)
        rows = [row for key, row in self._findings.items() if key[:3] == scope]
        return sorted(rows, key=lambda row: (row.property_key, row.entity_id))
