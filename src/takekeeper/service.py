from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .continuity import compare_observations
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
        findings = compare_observations(
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
        self.memory.replace_findings(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
            findings=findings,
        )
        return findings
