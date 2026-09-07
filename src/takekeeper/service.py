from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .continuity import compare_observations
from .extraction import ExtractionRunResult
from .extraction_projection import ContinuityProjection, project_extraction_for_continuity
from .memory import ProductionMemory
from .models import Finding, Observation


@dataclass(slots=True)
class TakeAnalysisService:
    memory: ProductionMemory
    confirmation_threshold: float = 0.80

    def analyze(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        observations: Iterable[Observation],
    ) -> list[Finding]:
        rows = list(observations)
        requested_scope = (production_id, scene_id, take_id)
        for row in rows:
            if (row.production_id, row.scene_id, row.take_id) != requested_scope:
                raise ValueError("observation scope does not match requested take")

        self.memory.upsert_observations(rows)
        findings = self._compare_persisted_scope(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
        )
        self.memory.replace_findings(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
            findings=findings,
        )
        return findings

    def analyze_extraction(self, result: ExtractionRunResult) -> tuple[list[Finding], ContinuityProjection]:
        """Analyze one extraction run without allowing uncertain model evidence to become active facts.

        Governed extraction is a full re-analysis of the take's machine-derived current
        observation projection. The previous projected set is therefore replaced, not
        incrementally upserted: if a newer run abstains or loses evidence for a property,
        stale evidence from an older run cannot survive and create a false mismatch.
        Historical raw/model evidence remains the responsibility of the append-only
        extraction provenance store.
        """

        projection = project_extraction_for_continuity(result)
        self.memory.replace_observations(
            production_id=projection.production_id,
            scene_id=projection.scene_id,
            take_id=projection.take_id,
            observations=projection.observations,
        )
        findings = self._compare_persisted_scope(
            production_id=projection.production_id,
            scene_id=projection.scene_id,
            take_id=projection.take_id,
        )
        self.memory.replace_findings(
            production_id=projection.production_id,
            scene_id=projection.scene_id,
            take_id=projection.take_id,
            findings=findings,
        )
        return findings, projection

    def _compare_persisted_scope(self, *, production_id: str, scene_id: str, take_id: str) -> list[Finding]:
        return compare_observations(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
            observations=self.memory.list_observations(
                production_id=production_id,
                scene_id=scene_id,
                take_id=take_id,
            ),
            baselines=self.memory.list_baselines(
                production_id=production_id,
                scene_id=scene_id,
            ),
            confirmation_threshold=self.confirmation_threshold,
        )
