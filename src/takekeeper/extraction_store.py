from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .clickhouse_memory import ClickHouseClientLike
from .extraction import ExtractedObservation, ExtractionRunResult, TakeExtractionRequest


class ExtractionPersistenceError(RuntimeError):
    """Extraction provenance could not be persisted safely."""


@dataclass(frozen=True, slots=True)
class ExtractionRunRecord:
    run_id: str
    production_id: str
    scene_id: str
    take_id: str
    media_uri: str
    media_fingerprint: str
    duration_ms: int
    extractor_model: str
    extractor_version: str
    prompt_schema_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExtractedObservationRecord:
    run_id: str
    observation_id: str
    production_id: str
    scene_id: str
    take_id: str
    entity_id: str
    property_key: str
    normalized_value: str
    raw_model_value: str
    confidence: float
    evidence_start_ms: int
    evidence_end_ms: int
    source_type: str
    visibility_state: str
    temporal_support: str
    disposition: str
    verification_state: str
    evidence_rationale_short: str
    created_at: datetime


class ExtractionProvenanceStore(Protocol):
    def append(self, request: TakeExtractionRequest, result: ExtractionRunResult) -> ExtractionRunRecord: ...
    def list_runs(self, *, production_id: str, scene_id: str, take_id: str) -> list[ExtractionRunRecord]: ...
    def list_observations(self, *, production_id: str, run_id: str) -> list[ExtractedObservationRecord]: ...


def media_fingerprint(request: TakeExtractionRequest) -> str:
    """Stable provenance identity for the trusted media reference and clip duration.

    This is not a content hash: callers should use an immutable/versioned media URI when
    possible. The fingerprint prevents accidental loss of which media reference was used.
    """
    payload = f"v1\0{request.media_uri}\0{request.duration_ms}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def observation_record_id(run_id: str, item: ExtractedObservation) -> str:
    obs = item.observation
    key = f"takekeeper-extraction-observation-v1\0{run_id}\0{obs.entity_id}\0{obs.property_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _validate_scope(request: TakeExtractionRequest, result: ExtractionRunResult) -> None:
    if not result.run_id.strip():
        raise ExtractionPersistenceError("run_id must be non-empty")
    request_scope = (request.production_id, request.scene_id, request.take_id)
    result_scope = (result.production_id, result.scene_id, result.take_id)
    if result_scope != request_scope:
        raise ExtractionPersistenceError("extraction result scope does not match trusted request scope")
    if result.extractor_model != request.extractor_model:
        raise ExtractionPersistenceError("extractor model does not match trusted request")
    if result.extractor_version != request.extractor_version:
        raise ExtractionPersistenceError("extractor version does not match trusted request")
    if result.prompt_schema_version != request.prompt_schema_version:
        raise ExtractionPersistenceError("prompt schema version does not match trusted request")
    for item in result.observations:
        obs = item.observation
        if (obs.production_id, obs.scene_id, obs.take_id) != request_scope:
            raise ExtractionPersistenceError("extracted observation escaped trusted take scope")


def _records(
    request: TakeExtractionRequest,
    result: ExtractionRunResult,
    created_at: datetime,
) -> tuple[ExtractionRunRecord, list[ExtractedObservationRecord]]:
    _validate_scope(request, result)
    run = ExtractionRunRecord(
        run_id=result.run_id,
        production_id=request.production_id,
        scene_id=request.scene_id,
        take_id=request.take_id,
        media_uri=request.media_uri,
        media_fingerprint=media_fingerprint(request),
        duration_ms=request.duration_ms,
        extractor_model=result.extractor_model,
        extractor_version=result.extractor_version,
        prompt_schema_version=result.prompt_schema_version,
        created_at=created_at,
    )
    observations = [
        ExtractedObservationRecord(
            run_id=result.run_id,
            observation_id=observation_record_id(result.run_id, item),
            production_id=request.production_id,
            scene_id=request.scene_id,
            take_id=request.take_id,
            entity_id=item.observation.entity_id,
            property_key=item.observation.property_key,
            normalized_value=item.observation.normalized_value,
            raw_model_value=item.raw_model_value,
            confidence=item.observation.confidence,
            evidence_start_ms=item.observation.evidence_start_ms,
            evidence_end_ms=item.observation.evidence_end_ms,
            source_type=item.source_type,
            visibility_state=item.visibility_state,
            temporal_support=item.temporal_support,
            disposition=item.disposition,
            verification_state=item.observation.verification_state,
            evidence_rationale_short=item.evidence_rationale_short,
            created_at=created_at,
        )
        for item in result.observations
    ]
    return run, observations


class InMemoryExtractionProvenanceStore:
    """Deterministic reference implementation with append-only semantics."""

    def __init__(self) -> None:
        self._runs: dict[str, ExtractionRunRecord] = {}
        self._observations: dict[str, list[ExtractedObservationRecord]] = {}

    def append(self, request: TakeExtractionRequest, result: ExtractionRunResult) -> ExtractionRunRecord:
        if result.run_id in self._runs:
            raise ExtractionPersistenceError("run_id already exists; extraction history is append-only")
        run, observations = _records(request, result, datetime.now(timezone.utc))
        self._runs[run.run_id] = run
        self._observations[run.run_id] = observations
        return run

    def list_runs(self, *, production_id: str, scene_id: str, take_id: str) -> list[ExtractionRunRecord]:
        return sorted(
            [
                run for run in self._runs.values()
                if (run.production_id, run.scene_id, run.take_id) == (production_id, scene_id, take_id)
            ],
            key=lambda run: (run.created_at, run.run_id),
        )

    def list_observations(self, *, production_id: str, run_id: str) -> list[ExtractedObservationRecord]:
        run = self._runs.get(run_id)
        if run is None or run.production_id != production_id:
            return []
        return list(self._observations.get(run_id, ()))


class ClickHouseExtractionProvenanceStore:
    """Append-only ClickHouse persistence using the trusted application connection."""

    def __init__(self, client: ClickHouseClientLike, *, database: str = "takekeeper") -> None:
        if not database.replace("_", "").isalnum():
            raise ValueError("database must contain only letters, digits, and underscores")
        self._client = client
        self._database = database

    def _table(self, name: str) -> str:
        return f"{self._database}.{name}"

    def append(self, request: TakeExtractionRequest, result: ExtractionRunResult) -> ExtractionRunRecord:
        existing = self._client.query(
            f"SELECT count() FROM {self._table('extraction_runs')} "
            "WHERE production_id = {production_id:String} AND run_id = {run_id:String}",
            parameters={"production_id": request.production_id, "run_id": result.run_id},
        )
        if existing.result_set and int(existing.result_set[0][0]) != 0:
            raise ExtractionPersistenceError("run_id already exists; extraction history is append-only")

        run, observations = _records(request, result, datetime.now(timezone.utc))
        self._client.insert(
            self._table("extraction_runs"),
            [[
                run.production_id, run.scene_id, run.take_id, run.run_id, run.media_uri,
                run.media_fingerprint, run.duration_ms, run.extractor_model, run.extractor_version,
                run.prompt_schema_version, run.created_at,
            ]],
            column_names=[
                "production_id", "scene_id", "take_id", "run_id", "media_uri",
                "media_fingerprint", "duration_ms", "extractor_model", "extractor_version",
                "prompt_schema_version", "created_at",
            ],
        )
        if observations:
            self._client.insert(
                self._table("extracted_observations"),
                [[
                    row.production_id, row.scene_id, row.take_id, row.run_id, row.observation_id,
                    row.entity_id, row.property_key, row.normalized_value, row.raw_model_value,
                    row.confidence, row.evidence_start_ms, row.evidence_end_ms, row.source_type,
                    row.visibility_state, row.temporal_support, row.disposition,
                    row.verification_state, row.evidence_rationale_short, row.created_at,
                ] for row in observations],
                column_names=[
                    "production_id", "scene_id", "take_id", "run_id", "observation_id",
                    "entity_id", "property_key", "normalized_value", "raw_model_value",
                    "confidence", "evidence_start_ms", "evidence_end_ms", "source_type",
                    "visibility_state", "temporal_support", "disposition", "verification_state",
                    "evidence_rationale_short", "created_at",
                ],
            )
        return run

    def list_runs(self, *, production_id: str, scene_id: str, take_id: str) -> list[ExtractionRunRecord]:
        result = self._client.query(
            f"SELECT run_id, media_uri, media_fingerprint, duration_ms, extractor_model, "
            f"extractor_version, prompt_schema_version, created_at FROM {self._table('extraction_runs')} "
            "WHERE production_id = {production_id:String} AND scene_id = {scene_id:String} "
            "AND take_id = {take_id:String} ORDER BY created_at, run_id",
            parameters={"production_id": production_id, "scene_id": scene_id, "take_id": take_id},
        )
        return [ExtractionRunRecord(
            run_id=str(row[0]), production_id=production_id, scene_id=scene_id, take_id=take_id,
            media_uri=str(row[1]), media_fingerprint=str(row[2]), duration_ms=int(row[3]),
            extractor_model=str(row[4]), extractor_version=str(row[5]), prompt_schema_version=str(row[6]),
            created_at=row[7],
        ) for row in result.result_set]

    def list_observations(self, *, production_id: str, run_id: str) -> list[ExtractedObservationRecord]:
        result = self._client.query(
            f"SELECT scene_id, take_id, observation_id, entity_id, property_key, normalized_value, "
            f"raw_model_value, confidence, evidence_start_ms, evidence_end_ms, source_type, "
            f"visibility_state, temporal_support, disposition, verification_state, "
            f"evidence_rationale_short, created_at FROM {self._table('extracted_observations')} "
            "WHERE production_id = {production_id:String} AND run_id = {run_id:String} "
            "ORDER BY entity_id, property_key, observation_id",
            parameters={"production_id": production_id, "run_id": run_id},
        )
        return [ExtractedObservationRecord(
            run_id=run_id, observation_id=str(row[2]), production_id=production_id,
            scene_id=str(row[0]), take_id=str(row[1]), entity_id=str(row[3]), property_key=str(row[4]),
            normalized_value=str(row[5]), raw_model_value=str(row[6]), confidence=float(row[7]),
            evidence_start_ms=int(row[8]), evidence_end_ms=int(row[9]), source_type=str(row[10]),
            visibility_state=str(row[11]), temporal_support=str(row[12]), disposition=str(row[13]),
            verification_state=str(row[14]), evidence_rationale_short=str(row[15]), created_at=row[16],
        ) for row in result.result_set]
