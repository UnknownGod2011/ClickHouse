from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from takekeeper.extraction import ExtractionRunResult, PropertySpec, TakeExtractionRequest
from takekeeper.ingest_runtime import IngestBootstrapError, IngestNotReady, SchemaGatedIngestService
from takekeeper.schema_preflight import ClickHouseSchemaNotReady


@dataclass
class _Result:
    result_set: list[list[Any]]


RUN_COLUMNS = [
    ["production_id", "String"], ["scene_id", "String"], ["take_id", "String"],
    ["run_id", "String"], ["media_uri", "String"], ["media_fingerprint", "FixedString(64)"],
    ["media_mime_type", "LowCardinality(Nullable(String))"],
    ["media_content_sha256", "Nullable(FixedString(64))"], ["media_byte_size", "Nullable(UInt64)"],
    ["duration_ms", "UInt64"], ["extractor_model", "String"], ["extractor_version", "String"],
    ["prompt_schema_version", "String"], ["created_at", "DateTime64(3, 'UTC')"],
]

OBS_COLUMNS = [
    ["production_id", "String"], ["scene_id", "String"], ["take_id", "String"],
    ["run_id", "String"], ["observation_id", "String"], ["entity_id", "String"],
    ["property_key", "LowCardinality(String)"], ["normalized_value", "String"],
    ["raw_model_value", "String"], ["confidence", "Float32"], ["evidence_start_ms", "UInt64"],
    ["evidence_end_ms", "UInt64"], ["source_type", "LowCardinality(String)"],
    ["visibility_state", "LowCardinality(String)"], ["temporal_support", "LowCardinality(String)"],
    ["disposition", "LowCardinality(String)"], ["verification_state", "LowCardinality(String)"],
    ["evidence_rationale_short", "String"], ["created_at", "DateTime64(3, 'UTC')"],
]


class _SchemaClient:
    def __init__(self, *, old_schema: bool = False, fail: bool = False) -> None:
        self.old_schema = old_schema
        self.fail = fail
        self.queries = 0

    def query(self, _query: str, parameters=None, **_kwargs):
        self.queries += 1
        if self.fail:
            raise RuntimeError("provider detail that must not escape")
        table = dict(parameters or {})["table"]
        if table == "extraction_runs":
            rows = RUN_COLUMNS
            if self.old_schema:
                rows = [row for row in rows if row[0] not in {"media_mime_type", "media_content_sha256", "media_byte_size"}]
            return _Result([list(row) for row in rows])
        if table == "extracted_observations":
            return _Result([list(row) for row in OBS_COLUMNS])
        raise AssertionError("unexpected metadata table")


class _Extractor:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, request: TakeExtractionRequest) -> ExtractionRunResult:
        self.calls += 1
        return ExtractionRunResult(
            run_id="run-1",
            production_id=request.production_id,
            scene_id=request.scene_id,
            take_id=request.take_id,
            extractor_model=request.extractor_model,
            extractor_version=request.extractor_version,
            prompt_schema_version=request.prompt_schema_version,
            observations=(),
        )


class _Store:
    def __init__(self) -> None:
        self.calls = 0
        self.value = object()

    def append(self, request, result):
        self.calls += 1
        self.last = (request, result)
        return self.value


REQUEST = TakeExtractionRequest(
    production_id="prod-a",
    scene_id="scene-1",
    take_id="take-1",
    media_uri="gs://trusted/take-1.mp4",
    duration_ms=1000,
    properties=(PropertySpec("hero_mug", "hand", ("left", "right", "unknown")),),
    extractor_model="gemini-test",
    extractor_version="v1",
)


class IngestRuntimeTests(unittest.TestCase):
    def test_ingest_is_closed_before_preflight(self) -> None:
        extractor = _Extractor()
        store = _Store()
        service = SchemaGatedIngestService(
            clickhouse_client=_SchemaClient(), extractor=extractor, provenance_store=store
        )

        self.assertFalse(service.readiness().ready)
        self.assertFalse(service.readiness().schema_checked)
        with self.assertRaises(IngestNotReady):
            service.ingest(REQUEST)
        self.assertEqual(extractor.calls, 0)
        self.assertEqual(store.calls, 0)

    def test_current_schema_opens_ingestion_and_persists_result(self) -> None:
        client = _SchemaClient()
        extractor = _Extractor()
        store = _Store()
        service = SchemaGatedIngestService(
            clickhouse_client=client, extractor=extractor, provenance_store=store
        )

        report = service.start()
        self.assertTrue(report.ready)
        self.assertTrue(service.readiness().ready)
        self.assertTrue(service.readiness().schema_checked)
        self.assertEqual(client.queries, 2)

        ingested = service.ingest(REQUEST)
        self.assertEqual(ingested.result.run_id, "run-1")
        self.assertIs(ingested.persisted_run, store.value)
        self.assertEqual(extractor.calls, 1)
        self.assertEqual(store.calls, 1)

    def test_old_schema_never_opens_ingestion(self) -> None:
        extractor = _Extractor()
        store = _Store()
        service = SchemaGatedIngestService(
            clickhouse_client=_SchemaClient(old_schema=True), extractor=extractor, provenance_store=store
        )

        with self.assertRaises(ClickHouseSchemaNotReady):
            service.start()
        self.assertFalse(service.readiness().ready)
        self.assertTrue(service.readiness().schema_checked)
        with self.assertRaises(IngestNotReady):
            service.ingest(REQUEST)
        self.assertEqual(extractor.calls, 0)
        self.assertEqual(store.calls, 0)

    def test_failed_recheck_revokes_previous_readiness(self) -> None:
        client = _SchemaClient()
        extractor = _Extractor()
        store = _Store()
        service = SchemaGatedIngestService(
            clickhouse_client=client, extractor=extractor, provenance_store=store
        )
        service.start()
        self.assertTrue(service.readiness().ready)

        client.old_schema = True
        with self.assertRaises(ClickHouseSchemaNotReady):
            service.start()
        self.assertFalse(service.readiness().ready)
        with self.assertRaises(IngestNotReady):
            service.ingest(REQUEST)

    def test_provider_failure_is_coarse_and_keeps_boundary_closed(self) -> None:
        service = SchemaGatedIngestService(
            clickhouse_client=_SchemaClient(fail=True), extractor=_Extractor(), provenance_store=_Store()
        )

        with self.assertRaises(IngestBootstrapError) as ctx:
            service.start()
        self.assertFalse(service.readiness().ready)
        self.assertFalse(service.readiness().schema_checked)
        self.assertNotIn("provider detail", str(ctx.exception))

    def test_close_revokes_readiness_without_querying_or_mutating_store(self) -> None:
        client = _SchemaClient()
        store = _Store()
        service = SchemaGatedIngestService(
            clickhouse_client=client, extractor=_Extractor(), provenance_store=store
        )
        service.start()
        query_count = client.queries

        service.close()
        self.assertFalse(service.readiness().ready)
        self.assertEqual(client.queries, query_count)
        self.assertEqual(store.calls, 0)


if __name__ == "__main__":
    unittest.main()
