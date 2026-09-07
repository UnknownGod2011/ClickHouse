from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from takekeeper.schema_preflight import (
    ClickHouseSchemaNotReady,
    check_extraction_schema,
    require_extraction_schema_ready,
)


@dataclass
class _Result:
    result_set: list[list[Any]]


RUN_COLUMNS = [
    ["production_id", "String"],
    ["scene_id", "String"],
    ["take_id", "String"],
    ["run_id", "String"],
    ["media_uri", "String"],
    ["media_fingerprint", "FixedString(64)"],
    ["media_mime_type", "LowCardinality(Nullable(String))"],
    ["media_content_sha256", "Nullable(FixedString(64))"],
    ["media_byte_size", "Nullable(UInt64)"],
    ["duration_ms", "UInt64"],
    ["extractor_model", "String"],
    ["extractor_version", "String"],
    ["prompt_schema_version", "String"],
    ["created_at", "DateTime64(3, 'UTC')"],
]

OBS_COLUMNS = [
    ["production_id", "String"],
    ["scene_id", "String"],
    ["take_id", "String"],
    ["run_id", "String"],
    ["observation_id", "String"],
    ["entity_id", "String"],
    ["property_key", "LowCardinality(String)"],
    ["normalized_value", "String"],
    ["raw_model_value", "String"],
    ["confidence", "Float32"],
    ["evidence_start_ms", "UInt64"],
    ["evidence_end_ms", "UInt64"],
    ["source_type", "LowCardinality(String)"],
    ["visibility_state", "LowCardinality(String)"],
    ["temporal_support", "LowCardinality(String)"],
    ["disposition", "LowCardinality(String)"],
    ["verification_state", "LowCardinality(String)"],
    ["evidence_rationale_short", "String"],
    ["created_at", "DateTime64(3, 'UTC')"],
]


class _FakeClient:
    def __init__(self, *, run_columns=None, observation_columns=None) -> None:
        self.run_columns = RUN_COLUMNS if run_columns is None else run_columns
        self.observation_columns = OBS_COLUMNS if observation_columns is None else observation_columns
        self.queries: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def query(self, query: str, parameters=None, **kwargs):
        parameters = dict(parameters or {})
        self.queries.append((query, parameters, kwargs))
        table = parameters["table"]
        if table == "extraction_runs":
            return _Result([list(row) for row in self.run_columns])
        if table == "extracted_observations":
            return _Result([list(row) for row in self.observation_columns])
        raise AssertionError(f"unexpected table: {table}")

    def command(self, *args, **kwargs):
        raise AssertionError("preflight must not execute commands")

    def insert(self, *args, **kwargs):
        raise AssertionError("preflight must not insert")


class SchemaPreflightTests(unittest.TestCase):
    def test_ready_schema_passes_and_uses_two_bounded_metadata_queries(self) -> None:
        client = _FakeClient()
        report = require_extraction_schema_ready(client)

        self.assertTrue(report.ready)
        self.assertEqual(report.missing_columns, ())
        self.assertEqual(report.incompatible_columns, ())
        self.assertEqual(len(client.queries), 2)
        for query, parameters, kwargs in client.queries:
            self.assertIn("FROM system.columns", query)
            self.assertEqual(parameters["database"], "takekeeper")
            self.assertIn(parameters["table"], {"extraction_runs", "extracted_observations"})
            self.assertEqual(kwargs["settings"]["max_result_rows"], 64)
            self.assertEqual(kwargs["settings"]["result_overflow_mode"], "throw")

    def test_missing_migration_002_columns_fail_closed(self) -> None:
        old_columns = [row for row in RUN_COLUMNS if row[0] not in {
            "media_mime_type", "media_content_sha256", "media_byte_size"
        }]
        report = check_extraction_schema(_FakeClient(run_columns=old_columns))

        self.assertFalse(report.ready)
        self.assertEqual(
            report.missing_columns,
            (
                "extraction_runs.media_byte_size",
                "extraction_runs.media_content_sha256",
                "extraction_runs.media_mime_type",
            ),
        )
        with self.assertRaises(ClickHouseSchemaNotReady) as ctx:
            report.require_ready()
        message = str(ctx.exception)
        self.assertIn("sql/migrations/*.sql", message)
        self.assertNotIn("media_content_sha256", message)
        self.assertNotIn("takekeeper", message)

    def test_wrong_provenance_type_is_reported_without_echoing_type(self) -> None:
        columns = [list(row) for row in RUN_COLUMNS]
        for row in columns:
            if row[0] == "media_content_sha256":
                row[1] = "String"
        report = check_extraction_schema(_FakeClient(run_columns=columns))

        self.assertFalse(report.ready)
        self.assertEqual(report.incompatible_columns, ("extraction_runs.media_content_sha256",))
        with self.assertRaises(ClickHouseSchemaNotReady) as ctx:
            report.require_ready()
        self.assertNotIn("String", str(ctx.exception))
        self.assertNotIn("FixedString", str(ctx.exception))

    def test_missing_observation_table_is_detected_as_missing_required_columns(self) -> None:
        report = check_extraction_schema(_FakeClient(observation_columns=[]))
        self.assertFalse(report.ready)
        self.assertIn("extracted_observations.run_id", report.missing_columns)
        self.assertIn("extracted_observations.created_at", report.missing_columns)

    def test_database_identifier_is_validated_before_query(self) -> None:
        client = _FakeClient()
        with self.assertRaises(ValueError):
            check_extraction_schema(client, database="takekeeper; DROP DATABASE x")
        self.assertEqual(client.queries, [])

    def test_metadata_values_are_parameters_not_interpolated(self) -> None:
        client = _FakeClient()
        check_extraction_schema(client, database="takekeeper_prod")
        for query, parameters, _kwargs in client.queries:
            self.assertNotIn("takekeeper_prod", query)
            self.assertEqual(parameters["database"], "takekeeper_prod")
            self.assertNotIn(parameters["table"], query)


if __name__ == "__main__":
    unittest.main()
