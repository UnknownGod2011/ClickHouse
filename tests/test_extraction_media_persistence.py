from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from takekeeper.extraction import HERO_PROPERTY_REGISTRY, ExtractionRunResult, TakeExtractionRequest
from takekeeper.extraction_store import ClickHouseExtractionProvenanceStore, ExtractionPersistenceError


@dataclass
class _QueryResult:
    result_set: list[list[object]]


class _FakeClickHouse:
    def __init__(self) -> None:
        self.runs: list[dict[str, object]] = []
        self.inserts: list[tuple[str, dict[str, object], dict[str, object]]] = []

    def insert(self, table, data, column_names=None, **kwargs):
        assert column_names is not None
        for values in data:
            row = dict(zip(column_names, values, strict=True))
            self.inserts.append((table, row, kwargs))
            if table.endswith(".extraction_runs"):
                self.runs.append(row)

    def query(self, query, parameters=None, **kwargs):
        parameters = parameters or {}
        if "FROM takekeeper.extracted_observations" in query:
            return _QueryResult([])
        if "FROM takekeeper.extraction_runs" not in query:
            raise AssertionError(f"unexpected query: {query}")

        rows = [row for row in self.runs if row["production_id"] == parameters["production_id"]]
        if "run_id = {run_id:String}" in query:
            rows = [row for row in rows if row["run_id"] == parameters["run_id"]]
            return _QueryResult([
                [
                    row["scene_id"], row["take_id"], row["media_uri"], row["media_fingerprint"],
                    row["media_mime_type"], row["media_content_sha256"], row["media_byte_size"],
                    row["duration_ms"], row["extractor_model"], row["extractor_version"],
                    row["prompt_schema_version"], row["created_at"],
                ]
                for row in rows
            ])

        rows = [
            row for row in rows
            if row["scene_id"] == parameters["scene_id"] and row["take_id"] == parameters["take_id"]
        ]
        rows.sort(key=lambda row: (row["created_at"], row["run_id"]))
        return _QueryResult([
            [
                row["run_id"], row["media_uri"], row["media_fingerprint"], row["media_mime_type"],
                row["media_content_sha256"], row["media_byte_size"], row["duration_ms"],
                row["extractor_model"], row["extractor_version"], row["prompt_schema_version"],
                row["created_at"],
            ]
            for row in rows
        ])


class ExtractionMediaPersistenceTests(unittest.TestCase):
    def _request(self, *, digest="a" * 64, mime="video/mp4", byte_size=1234):
        return TakeExtractionRequest(
            production_id="glass-house",
            scene_id="28",
            take_id="S28-T47",
            media_uri="gs://takekeeper-private/glass-house/28/S28-T47/object",
            duration_ms=10_000,
            properties=tuple(HERO_PROPERTY_REGISTRY[:1]),
            extractor_model="gemini-2.5-flash",
            extractor_version="google-genai-v1",
            media_mime_type=mime,
            media_content_sha256=digest,
            media_byte_size=byte_size,
        )

    @staticmethod
    def _result(request, *, run_id="run-byte-identity"):
        return ExtractionRunResult(
            run_id=run_id,
            production_id=request.production_id,
            scene_id=request.scene_id,
            take_id=request.take_id,
            extractor_model=request.extractor_model,
            extractor_version=request.extractor_version,
            prompt_schema_version=request.prompt_schema_version,
            observations=(),
        )

    def test_clickhouse_insert_persists_trusted_byte_identity(self):
        client = _FakeClickHouse()
        store = ClickHouseExtractionProvenanceStore(client)
        request = self._request()

        record = store.append(request, self._result(request))

        self.assertEqual(record.media_mime_type, "video/mp4")
        self.assertEqual(record.media_content_sha256, "a" * 64)
        self.assertEqual(record.media_byte_size, 1234)
        run_insert = client.inserts[0][1]
        self.assertEqual(run_insert["media_mime_type"], "video/mp4")
        self.assertEqual(run_insert["media_content_sha256"], "a" * 64)
        self.assertEqual(run_insert["media_byte_size"], 1234)

    def test_identical_retry_reconciles_without_second_run_insert(self):
        client = _FakeClickHouse()
        store = ClickHouseExtractionProvenanceStore(client)
        request = self._request()
        result = self._result(request)

        first = store.append(request, result)
        second = store.append(request, result)

        self.assertEqual(first.media_content_sha256, second.media_content_sha256)
        self.assertEqual(len([row for table, row, _ in client.inserts if table.endswith(".extraction_runs")]), 1)

    def test_reused_run_id_with_changed_content_hash_fails_closed(self):
        client = _FakeClickHouse()
        store = ClickHouseExtractionProvenanceStore(client)
        first_request = self._request(digest="a" * 64)
        store.append(first_request, self._result(first_request))
        changed_request = self._request(digest="b" * 64)

        with self.assertRaisesRegex(ExtractionPersistenceError, "different immutable provenance"):
            store.append(changed_request, self._result(changed_request))

    def test_reused_run_id_with_changed_mime_or_byte_size_fails_closed(self):
        for changed in (
            self._request(mime="video/webm"),
            self._request(byte_size=1235),
        ):
            with self.subTest(mime=changed.media_mime_type, byte_size=changed.media_byte_size):
                client = _FakeClickHouse()
                store = ClickHouseExtractionProvenanceStore(client)
                original = self._request()
                store.append(original, self._result(original))
                with self.assertRaisesRegex(ExtractionPersistenceError, "different immutable provenance"):
                    store.append(changed, self._result(changed))

    def test_list_runs_round_trips_nullable_and_present_provenance_with_tenant_scope(self):
        client = _FakeClickHouse()
        store = ClickHouseExtractionProvenanceStore(client)
        request = self._request()
        store.append(request, self._result(request))

        rows = store.list_runs(production_id="glass-house", scene_id="28", take_id="S28-T47")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].media_mime_type, "video/mp4")
        self.assertEqual(rows[0].media_content_sha256, "a" * 64)
        self.assertEqual(rows[0].media_byte_size, 1234)
        self.assertEqual(store.list_runs(production_id="other", scene_id="28", take_id="S28-T47"), [])


if __name__ == "__main__":
    unittest.main()
