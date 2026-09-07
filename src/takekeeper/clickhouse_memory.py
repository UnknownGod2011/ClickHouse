from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from .models import Baseline, Finding, Observation
from .review import stable_finding_id


class QueryResultLike(Protocol):
    @property
    def result_set(self) -> Sequence[Sequence[Any]]: ...


class ClickHouseClientLike(Protocol):
    def query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> QueryResultLike: ...

    def command(
        self,
        cmd: str,
        parameters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any: ...

    def insert(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> Any: ...


class ClickHouseProductionMemory:
    """ClickHouse-backed ProductionMemory using a separately permissioned app connection.

    The agent-facing MCP connection should remain read-only; this adapter is for the
    trusted application ingest/persistence path.
    """

    def __init__(self, client: ClickHouseClientLike, *, database: str = "takekeeper") -> None:
        if not database.replace("_", "").isalnum():
            raise ValueError("database must contain only letters, digits, and underscores")
        self._client = client
        self._database = database

    def _table(self, name: str) -> str:
        return f"{self._database}.{name}"

    def _insert_observations(self, rows: list[Observation]) -> None:
        if not rows:
            return
        now = datetime.now(timezone.utc)
        self._client.insert(
            self._table("observations"),
            [
                [
                    row.production_id,
                    row.scene_id,
                    row.take_id,
                    str(uuid4()),
                    row.entity_id,
                    "unknown",
                    row.property_key,
                    row.normalized_value,
                    row.normalized_value,
                    row.evidence_start_ms,
                    row.evidence_end_ms,
                    row.confidence,
                    "application",
                    row.verification_state,
                    "",
                    now,
                ]
                for row in rows
            ],
            column_names=[
                "production_id", "scene_id", "take_id", "observation_id",
                "entity_id", "entity_type", "property_key", "normalized_value",
                "raw_value", "evidence_start_ms", "evidence_end_ms", "confidence",
                "source_type", "verification_state", "model_version", "created_at",
            ],
        )

    def upsert_observations(self, observations: Iterable[Observation]) -> None:
        rows = list(observations)
        if not rows:
            return
        for observation in rows:
            self._delete_observation_key(observation)
        self._insert_observations(rows)

    def replace_observations(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        observations: Iterable[Observation],
    ) -> None:
        rows = list(observations)
        scope = (production_id, scene_id, take_id)
        for observation in rows:
            if (observation.production_id, observation.scene_id, observation.take_id) != scope:
                raise ValueError("observation scope does not match replacement scope")
        self._client.command(
            f"DELETE FROM {self._table('observations')} WHERE "
            "production_id = {production_id:String} AND scene_id = {scene_id:String} "
            "AND take_id = {take_id:String}",
            parameters={"production_id": production_id, "scene_id": scene_id, "take_id": take_id},
            settings={"mutations_sync": 1},
        )
        self._insert_observations(rows)

    def _delete_observation_key(self, observation: Observation) -> None:
        self._client.command(
            f"DELETE FROM {self._table('observations')} WHERE "
            "production_id = {production_id:String} AND scene_id = {scene_id:String} "
            "AND take_id = {take_id:String} AND entity_id = {entity_id:String} "
            "AND property_key = {property_key:String}",
            parameters={
                "production_id": observation.production_id,
                "scene_id": observation.scene_id,
                "take_id": observation.take_id,
                "entity_id": observation.entity_id,
                "property_key": observation.property_key,
            },
            settings={"mutations_sync": 1},
        )

    def list_observations(self, *, production_id: str, scene_id: str, take_id: str) -> list[Observation]:
        result = self._client.query(
            f"SELECT entity_id, property_key, normalized_value, confidence, "
            f"evidence_start_ms, evidence_end_ms, verification_state "
            f"FROM {self._table('observations')} "
            "WHERE production_id = {production_id:String} AND scene_id = {scene_id:String} "
            "AND take_id = {take_id:String} "
            "ORDER BY entity_id, property_key",
            parameters={"production_id": production_id, "scene_id": scene_id, "take_id": take_id},
        )
        return [
            Observation(
                production_id=production_id,
                scene_id=scene_id,
                take_id=take_id,
                entity_id=str(row[0]),
                property_key=str(row[1]),
                normalized_value=str(row[2]),
                confidence=float(row[3]),
                evidence_start_ms=int(row[4]),
                evidence_end_ms=int(row[5]),
                verification_state=str(row[6]),
            )
            for row in result.result_set
        ]

    def upsert_baselines(self, baselines: Iterable[Baseline]) -> None:
        rows = list(baselines)
        if not rows:
            return
        now = datetime.now(timezone.utc)
        for baseline in rows:
            self._client.command(
                f"DELETE FROM {self._table('continuity_baselines')} WHERE "
                "production_id = {production_id:String} AND scene_id = {scene_id:String} "
                "AND entity_id = {entity_id:String} AND property_key = {property_key:String}",
                parameters={
                    "production_id": baseline.production_id,
                    "scene_id": baseline.scene_id,
                    "entity_id": baseline.entity_id,
                    "property_key": baseline.property_key,
                },
                settings={"mutations_sync": 1},
            )
        self._client.insert(
            self._table("continuity_baselines"),
            [
                [
                    row.production_id, row.scene_id, row.entity_id, row.property_key,
                    row.baseline_value, row.source_take_id, "takekeeper", now, True,
                ]
                for row in rows
            ],
            column_names=[
                "production_id", "scene_id", "entity_id", "property_key",
                "baseline_value", "source_take_id", "approved_by", "approved_at", "active",
            ],
        )

    def list_baselines(self, *, production_id: str, scene_id: str) -> list[Baseline]:
        result = self._client.query(
            f"SELECT entity_id, property_key, baseline_value, source_take_id "
            f"FROM {self._table('continuity_baselines')} "
            "WHERE production_id = {production_id:String} AND scene_id = {scene_id:String} AND active = true "
            "ORDER BY entity_id, property_key",
            parameters={"production_id": production_id, "scene_id": scene_id},
        )
        return [
            Baseline(
                production_id=production_id,
                scene_id=scene_id,
                entity_id=str(row[0]),
                property_key=str(row[1]),
                baseline_value=str(row[2]),
                source_take_id=str(row[3]),
            )
            for row in result.result_set
        ]

    def replace_findings(
        self,
        *,
        production_id: str,
        scene_id: str,
        take_id: str,
        findings: Iterable[Finding],
    ) -> None:
        rows = list(findings)
        scope = (production_id, scene_id, take_id)
        for finding in rows:
            if (finding.production_id, finding.scene_id, finding.take_id) != scope:
                raise ValueError("finding scope does not match replacement scope")

        self._client.command(
            f"DELETE FROM {self._table('continuity_findings')} WHERE "
            "production_id = {production_id:String} AND scene_id = {scene_id:String} "
            "AND current_take_id = {take_id:String}",
            parameters={"production_id": production_id, "scene_id": scene_id, "take_id": take_id},
            settings={"mutations_sync": 1},
        )
        if not rows:
            return

        now = datetime.now(timezone.utc)
        self._client.insert(
            self._table("continuity_findings"),
            [
                [
                    row.production_id, row.scene_id, row.take_id, stable_finding_id(row),
                    row.entity_id, row.property_key, row.baseline_value, row.observed_value,
                    self._severity(row), row.confidence, row.status, row.evidence_start_ms,
                    row.evidence_end_ms, row.baseline_source_take_id, now,
                ]
                for row in rows
            ],
            column_names=[
                "production_id", "scene_id", "current_take_id", "finding_id",
                "entity_id", "property_key", "baseline_value", "observed_value",
                "severity", "confidence", "status", "evidence_start_ms", "evidence_end_ms",
                "baseline_source_take_id", "created_at",
            ],
        )

    @staticmethod
    def _severity(finding: Finding) -> str:
        if finding.status == "mismatch":
            return "high" if (finding.confidence or 0.0) >= 0.85 else "medium"
        if finding.status == "needs_confirmation":
            return "low"
        return "info"

    def list_findings(self, *, production_id: str, scene_id: str, take_id: str) -> list[Finding]:
        result = self._client.query(
            f"SELECT entity_id, property_key, baseline_value, observed_value, confidence, status, "
            f"evidence_start_ms, evidence_end_ms, baseline_source_take_id "
            f"FROM {self._table('continuity_findings')} "
            "WHERE production_id = {production_id:String} AND scene_id = {scene_id:String} "
            "AND current_take_id = {take_id:String} "
            "ORDER BY property_key, entity_id",
            parameters={"production_id": production_id, "scene_id": scene_id, "take_id": take_id},
        )
        return [
            Finding(
                production_id=production_id,
                scene_id=scene_id,
                take_id=take_id,
                entity_id=str(row[0]),
                property_key=str(row[1]),
                baseline_value=None if row[2] is None else str(row[2]),
                observed_value=None if row[3] is None else str(row[3]),
                confidence=None if row[4] is None else float(row[4]),
                status=str(row[5]),
                evidence_start_ms=None if row[6] is None else int(row[6]),
                evidence_end_ms=None if row[7] is None else int(row[7]),
                baseline_source_take_id=None if row[8] is None else str(row[8]),
            )
            for row in result.result_set
        ]
