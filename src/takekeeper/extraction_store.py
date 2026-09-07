from __future__ import annotations

import hashlib
import uuid
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
    media_mime_type: str | None
    media_content_sha256: str | None
    media_byte_size: int | None
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

    This is deliberately distinct from media_content_sha256. Locator identity is useful
    even when a trusted ingest boundary cannot establish byte identity; when a content
    digest is available, both values are persisted and immutable for a run.
    """
    payload = f"v1\0{request.media_uri}\0{request.duration_ms}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def observation_record_id(run_id: str, item: ExtractedObservation) -> str:
    obs = item.observation
    key = f"takekeeper-extraction-observation-v1\0{run_id}\0{obs.entity_id}\0{obs.property_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _dedup_token(kind: str, production_id: str, record_id: str) -> str:
    payload = f"takekeeper-extraction-v1\0{kind}\0{production_id}\0{record_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
        media_mime_type=request.media_mime_type,
        media_content_sha256=request.media_content_sha256,
        media_byte_size=request.media_byte_size,
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
    """Append-only ClickHouse persistence using the trusted application connection.

    The two provenance tables are not transactionally atomic. `append` is therefore a
    reconciler: a retry may resume an identical partially persisted run, but it refuses
    any existing row whose immutable payload differs from the retry payload. Each insert
    also carries a deterministic ClickHouse deduplication token as a second line of
    defense against acknowledgement-loss retries and concurrent identical attempts.
    """

    _RUN_COLUMNS = [
        "production_id", "scene_id", "take_id", "run_id", "media_uri",
        "media_fingerprint", "media_mime_type", "media_content_sha256", "media_byte_size",
        "duration_ms", "extractor_model", "extractor_version", "prompt_schema_version", "created_at",
    ]
    _OBSERVATION_COLUMNS = [
        "production_id", "scene_id", "take_id", "run_id", "observation_id",
        "entity_id", "property_key", "normalized_value", "raw_model_value",
        "confidence", "evidence_start_ms", "evidence_end_ms", "source_type",
        "visibility_state", "temporal_support", "disposition", "verification_state",
        "evidence_rationale_short", "created_at",
    ]

    def __init__(self, client: ClickHouseClientLike, *, database: str = "takekeeper") -> None:
        if not database.replace("_", "").isalnum():
            raise ValueError("database must contain only letters, digits, and underscores")
        self._client = client
        self._database = database

    def _table(self, name: str) -> str:
        return f"{self._database}.{name}"

    @staticmethod
    def _run_payload(run: ExtractionRunRecord) -> tuple[Any, ...]:
        return (
            run.production_id, run.scene_id, run.take_id, run.run_id, run.media_uri,
            run.media_fingerprint, run.media_mime_type, run.media_content_sha256, run.media_byte_size,
            run.duration_ms, run.extractor_model, run.extractor_version, run.prompt_schema_version,
        )

    @staticmethod
    def _observation_payload(row: ExtractedObservationRecord) -> tuple[Any, ...]:
        return (
            row.production_id, row.scene_id, row.take_id, row.run_id, row.observation_id,
            row.entity_id, row.property_key, row.normalized_value, row.raw_model_value,
            row.confidence, row.evidence_start_ms, row.evidence_end_ms, row.source_type,
            row.visibility_state, row.temporal_support, row.disposition, row.verification_state,
            row.evidence_rationale_short,
        )

    def _existing_run(self, *, production_id: str, run_id: str) -> ExtractionRunRecord | None:
        result = self._client.query(
            f"SELECT scene_id, take_id, media_uri, media_fingerprint, media_mime_type, "
            f"media_content_sha256, media_byte_size, duration_ms, extractor_model, extractor_version, "
            f"prompt_schema_version, created_at FROM {self._table('extraction_runs')} "
            "WHERE production_id = {production_id:String} AND run_id = {run_id:String}",
            parameters={"production_id": production_id, "run_id": run_id},
        )
        rows = list(result.result_set)
        if not rows:
            return None
        if len(rows) != 1:
            raise ExtractionPersistenceError("run_id resolves to multiple provenance rows")
        row = rows[0]
        return ExtractionRunRecord(
            run_id=run_id,
            production_id=production_id,
            scene_id=str(row[0]),
            take_id=str(row[1]),
            media_uri=str(row[2]),
            media_fingerprint=str(row[3]),
            media_mime_type=None if row[4] is None else str(row[4]),
            media_content_sha256=None if row[5] is None else str(row[5]),
            media_byte_size=None if row[6] is None else int(row[6]),
            duration_ms=int(row[7]),
            extractor_model=str(row[8]),
            extractor_version=str(row[9]),
            prompt_schema_version=str(row[10]),
            created_at=row[11],
        )

    def _existing_observation(
        self, *, production_id: str, run_id: str, observation_id: str
    ) -> ExtractedObservationRecord | None:
        result = self._client.query(
            f"SELECT scene_id, take_id, entity_id, property_key, normalized_value, raw_model_value, "
            f"confidence, evidence_start_ms, evidence_end_ms, source_type, visibility_state, "
            f"temporal_support, disposition, verification_state, evidence_rationale_short, created_at "
            f"FROM {self._table('extracted_observations')} "
            "WHERE production_id = {production_id:String} AND run_id = {run_id:String} "
            "AND observation_id = {observation_id:String}",
            parameters={
                "production_id": production_id,
                "run_id": run_id,
                "observation_id": observation_id,
            },
        )
        rows = list(result.result_set)
        if not rows:
            return None
        if len(rows) != 1:
            raise ExtractionPersistenceError("observation_id resolves to multiple provenance rows")
        row = rows[0]
        return ExtractedObservationRecord(
            run_id=run_id,
            observation_id=observation_id,
            production_id=production_id,
            scene_id=str(row[0]),
            take_id=str(row[1]),
            entity_id=str(row[2]),
            property_key=str(row[3]),
            normalized_value=str(row[4]),
            raw_model_value=str(row[5]),
            confidence=float(row[6]),
            evidence_start_ms=int(row[7]),
            evidence_end_ms=int(row[8]),
            source_type=str(row[9]),
            visibility_state=str(row[10]),
            temporal_support=str(row[11]),
            disposition=str(row[12]),
            verification_state=str(row[13]),
            evidence_rationale_short=str(row[14]),
            created_at=row[15],
        )

    def append(self, request: TakeExtractionRequest, result: ExtractionRunResult) -> ExtractionRunRecord:
        desired_run, desired_observations = _records(request, result, datetime.now(timezone.utc))

        existing_run = self._existing_run(production_id=request.production_id, run_id=result.run_id)
        if existing_run is None:
            self._client.insert(
                self._table("extraction_runs"),
                [[*self._run_payload(desired_run), desired_run.created_at]],
                column_names=self._RUN_COLUMNS,
                settings={
                    "insert_deduplicate": 1,
                    "insert_deduplication_token": _dedup_token("run", request.production_id, result.run_id),
                },
            )
            persisted_run = desired_run
        else:
            if self._run_payload(existing_run) != self._run_payload(desired_run):
                raise ExtractionPersistenceError(
                    "run_id already exists with different immutable provenance; refusing retry"
                )
            persisted_run = existing_run

        desired_ids = {row.observation_id for row in desired_observations}
        if len(desired_ids) != len(desired_observations):
            raise ExtractionPersistenceError("extraction result produced duplicate observation identities")

        for desired in desired_observations:
            existing = self._existing_observation(
                production_id=request.production_id,
                run_id=result.run_id,
                observation_id=desired.observation_id,
            )
            if existing is not None:
                if self._observation_payload(existing) != self._observation_payload(desired):
                    raise ExtractionPersistenceError(
                        "observation_id already exists with different immutable provenance; refusing retry"
                    )
                continue
            self._client.insert(
                self._table("extracted_observations"),
                [[*self._observation_payload(desired), desired.created_at]],
                column_names=self._OBSERVATION_COLUMNS,
                settings={
                    "insert_deduplicate": 1,
                    "insert_deduplication_token": _dedup_token(
                        "observation", request.production_id, desired.observation_id
                    ),
                },
            )

        existing_ids_result = self._client.query(
            f"SELECT observation_id FROM {self._table('extracted_observations')} "
            "WHERE production_id = {production_id:String} AND run_id = {run_id:String}",
            parameters={"production_id": request.production_id, "run_id": result.run_id},
        )
        existing_ids = [str(row[0]) for row in existing_ids_result.result_set]
        if len(existing_ids) != len(set(existing_ids)):
            raise ExtractionPersistenceError("run contains duplicate persisted observation identities")
        if set(existing_ids) != desired_ids:
            raise ExtractionPersistenceError(
                "run contains incomplete or unexpected persisted observations after reconciliation"
            )
        return persisted_run

    def list_runs(self, *, production_id: str, scene_id: str, take_id: str) -> list[ExtractionRunRecord]:
        result = self._client.query(
            f"SELECT run_id, media_uri, media_fingerprint, media_mime_type, media_content_sha256, "
            f"media_byte_size, duration_ms, extractor_model, extractor_version, prompt_schema_version, created_at "
            f"FROM {self._table('extraction_runs')} "
            "WHERE production_id = {production_id:String} AND scene_id = {scene_id:String} "
            "AND take_id = {take_id:String} ORDER BY created_at, run_id",
            parameters={"production_id": production_id, "scene_id": scene_id, "take_id": take_id},
        )
        return [ExtractionRunRecord(
            run_id=str(row[0]), production_id=production_id, scene_id=scene_id, take_id=take_id,
            media_uri=str(row[1]), media_fingerprint=str(row[2]),
            media_mime_type=None if row[3] is None else str(row[3]),
            media_content_sha256=None if row[4] is None else str(row[4]),
            media_byte_size=None if row[5] is None else int(row[5]), duration_ms=int(row[6]),
            extractor_model=str(row[7]), extractor_version=str(row[8]), prompt_schema_version=str(row[9]),
            created_at=row[10],
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
