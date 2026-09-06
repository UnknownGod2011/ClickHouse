from __future__ import annotations

import unittest
from dataclasses import replace

from takekeeper.extraction import (
    FixtureExtractionTransport,
    GovernedMultimodalExtractor,
    HERO_PROPERTY_REGISTRY,
    TakeExtractionRequest,
)
from takekeeper.extraction_store import ClickHouseExtractionProvenanceStore, ExtractionPersistenceError


class _Result:
    def __init__(self, rows):
        self.result_set = rows


class _StatefulClickHouseClient:
    """Small failure-injection fake for the provenance store's ClickHouse contract."""

    def __init__(self, *, fail_observation_once: str | None = None):
        self.runs: list[list[object]] = []
        self.observations: list[list[object]] = []
        self.fail_observation_once = fail_observation_once
        self.failed = False
        self.insert_settings: list[dict[str, object]] = []

    def command(self, cmd, parameters=None, **kwargs):
        raise AssertionError("provenance append must not use destructive commands")

    def insert(self, table, data, column_names=None, **kwargs):
        self.insert_settings.append(dict(kwargs.get("settings") or {}))
        if table.endswith(".extraction_runs"):
            self.runs.extend([list(row) for row in data])
            return None
        if not table.endswith(".extracted_observations"):
            raise AssertionError(f"unexpected table {table}")

        if self.fail_observation_once == "before" and not self.failed:
            self.failed = True
            raise TimeoutError("simulated failure before observation persistence")

        self.observations.extend([list(row) for row in data])
        if self.fail_observation_once == "after" and not self.failed:
            self.failed = True
            raise TimeoutError("simulated acknowledgement loss after persistence")
        return None

    def query(self, query, parameters=None, **kwargs):
        parameters = parameters or {}
        production_id = parameters.get("production_id")
        run_id = parameters.get("run_id")

        if "FROM takekeeper.extraction_runs" in query:
            matches = [
                row for row in self.runs
                if row[0] == production_id and row[3] == run_id
            ]
            return _Result([
                [row[1], row[2], row[4], row[5], row[6], row[7], row[8], row[9], row[10]]
                for row in matches
            ])

        if "FROM takekeeper.extracted_observations" in query and "observation_id =" in query:
            observation_id = parameters.get("observation_id")
            matches = [
                row for row in self.observations
                if row[0] == production_id and row[3] == run_id and row[4] == observation_id
            ]
            return _Result([
                [
                    row[1], row[2], row[5], row[6], row[7], row[8], row[9], row[10], row[11],
                    row[12], row[13], row[14], row[15], row[16], row[17], row[18],
                ]
                for row in matches
            ])

        if "SELECT observation_id FROM takekeeper.extracted_observations" in query:
            return _Result([
                [row[4]] for row in self.observations
                if row[0] == production_id and row[3] == run_id
            ])

        raise AssertionError(f"unexpected query: {query}")


class ClickHouseExtractionRetryTests(unittest.TestCase):
    def _request(self):
        return TakeExtractionRequest(
            production_id="glass-house",
            scene_id="28",
            take_id="S28-T47",
            media_uri="fixture://s28-t47",
            duration_ms=10_000,
            properties=tuple(HERO_PROPERTY_REGISTRY[:1]),
            extractor_model="gemini-fixture",
            extractor_version="fixture-v1",
        )

    def _result(self, request, run_id="run-retry", value="left"):
        payload = {"observations": [{
            "entity_id": "hero_mug",
            "property_key": "hand",
            "normalized_value": value,
            "raw_model_value": value,
            "evidence_start_ms": 1000,
            "evidence_end_ms": 5000,
            "confidence": 0.95,
            "source_type": "vision",
            "evidence_rationale_short": "fixture",
            "visibility_state": "clear",
            "temporal_support": "sustained",
        }]}
        return GovernedMultimodalExtractor(
            FixtureExtractionTransport({request.media_uri: payload}),
            run_id_factory=lambda: run_id,
        ).extract(request)

    def test_retry_repairs_run_written_before_observation_failure(self):
        request = self._request()
        result = self._result(request)
        client = _StatefulClickHouseClient(fail_observation_once="before")
        store = ClickHouseExtractionProvenanceStore(client)

        with self.assertRaises(TimeoutError):
            store.append(request, result)
        self.assertEqual(len(client.runs), 1)
        self.assertEqual(len(client.observations), 0)

        recovered = store.append(request, result)
        self.assertEqual(recovered.run_id, result.run_id)
        self.assertEqual(len(client.runs), 1)
        self.assertEqual(len(client.observations), 1)

    def test_retry_after_observation_ack_loss_is_idempotent(self):
        request = self._request()
        result = self._result(request)
        client = _StatefulClickHouseClient(fail_observation_once="after")
        store = ClickHouseExtractionProvenanceStore(client)

        with self.assertRaises(TimeoutError):
            store.append(request, result)
        self.assertEqual(len(client.runs), 1)
        self.assertEqual(len(client.observations), 1)

        store.append(request, result)
        self.assertEqual(len(client.runs), 1)
        self.assertEqual(len(client.observations), 1)

    def test_same_run_id_with_changed_payload_fails_closed(self):
        request = self._request()
        client = _StatefulClickHouseClient()
        store = ClickHouseExtractionProvenanceStore(client)
        store.append(request, self._result(request, value="left"))

        with self.assertRaisesRegex(ExtractionPersistenceError, "different immutable provenance"):
            store.append(request, self._result(request, value="right"))

    def test_unexpected_persisted_observation_fails_closed(self):
        request = self._request()
        result = self._result(request)
        client = _StatefulClickHouseClient()
        store = ClickHouseExtractionProvenanceStore(client)
        store.append(request, result)
        extra = list(client.observations[0])
        extra[4] = "unexpected-observation-id"
        client.observations.append(extra)

        with self.assertRaisesRegex(ExtractionPersistenceError, "unexpected persisted observations"):
            store.append(request, result)

    def test_deterministic_deduplication_tokens_are_used_for_each_table(self):
        request = self._request()
        client = _StatefulClickHouseClient()
        ClickHouseExtractionProvenanceStore(client).append(request, self._result(request))

        self.assertEqual(len(client.insert_settings), 2)
        for settings in client.insert_settings:
            self.assertEqual(settings["insert_deduplicate"], 1)
            token = settings["insert_deduplication_token"]
            self.assertIsInstance(token, str)
            self.assertEqual(len(token), 64)


if __name__ == "__main__":
    unittest.main()
