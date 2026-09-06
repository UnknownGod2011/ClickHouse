from __future__ import annotations

import unittest

from takekeeper.extraction import FixtureExtractionTransport, GovernedMultimodalExtractor, HERO_PROPERTY_REGISTRY, TakeExtractionRequest
from takekeeper.extraction_store import ExtractionPersistenceError, InMemoryExtractionProvenanceStore, media_fingerprint


class ExtractionStoreTests(unittest.TestCase):
    def _request(self, *, take_id="S28-T47", media_uri="fixture://s28-t47"):
        return TakeExtractionRequest(
            production_id="glass-house", scene_id="28", take_id=take_id,
            media_uri=media_uri, duration_ms=10_000,
            properties=tuple(HERO_PROPERTY_REGISTRY[:1]),
            extractor_model="gemini-fixture", extractor_version="fixture-v1",
        )

    def _result(self, request, run_id, value="left"):
        payload = {"observations": [{
            "entity_id": "hero_mug", "property_key": "hand", "normalized_value": value,
            "raw_model_value": value, "evidence_start_ms": 1000, "evidence_end_ms": 5000,
            "confidence": 0.95, "source_type": "vision", "evidence_rationale_short": "fixture",
            "visibility_state": "clear", "temporal_support": "sustained",
        }]}
        return GovernedMultimodalExtractor(
            FixtureExtractionTransport({request.media_uri: payload}), run_id_factory=lambda: run_id
        ).extract(request)

    def test_reprocessing_appends_history_instead_of_overwriting(self):
        request = self._request()
        store = InMemoryExtractionProvenanceStore()
        first = self._result(request, "run-1", "left")
        second = self._result(request, "run-2", "right")

        store.append(request, first)
        store.append(request, second)

        self.assertEqual([r.run_id for r in store.list_runs(production_id="glass-house", scene_id="28", take_id="S28-T47")], ["run-1", "run-2"])
        self.assertEqual(store.list_observations(production_id="glass-house", run_id="run-1")[0].normalized_value, "left")
        self.assertEqual(store.list_observations(production_id="glass-house", run_id="run-2")[0].normalized_value, "right")

    def test_duplicate_run_id_is_rejected(self):
        request = self._request()
        result = self._result(request, "run-1")
        store = InMemoryExtractionProvenanceStore()
        store.append(request, result)
        with self.assertRaisesRegex(ExtractionPersistenceError, "append-only"):
            store.append(request, result)

    def test_scope_mismatch_fails_closed(self):
        request = self._request()
        other_request = self._request(take_id="S28-T99", media_uri="fixture://s28-t99")
        result = self._result(other_request, "run-1")
        with self.assertRaisesRegex(ExtractionPersistenceError, "scope"):
            InMemoryExtractionProvenanceStore().append(request, result)

    def test_media_fingerprint_changes_with_versioned_reference_or_duration(self):
        one = self._request()
        two = self._request(media_uri="fixture://s28-t47?v=2")
        three = TakeExtractionRequest(
            production_id=one.production_id, scene_id=one.scene_id, take_id=one.take_id,
            media_uri=one.media_uri, duration_ms=11_000, properties=one.properties,
            extractor_model=one.extractor_model, extractor_version=one.extractor_version,
        )
        self.assertNotEqual(media_fingerprint(one), media_fingerprint(two))
        self.assertNotEqual(media_fingerprint(one), media_fingerprint(three))

    def test_observation_reads_are_tenant_scoped(self):
        request = self._request()
        store = InMemoryExtractionProvenanceStore()
        store.append(request, self._result(request, "run-1"))
        self.assertEqual(store.list_observations(production_id="other-production", run_id="run-1"), [])
        self.assertEqual(len(store.list_observations(production_id="glass-house", run_id="run-1")), 1)


if __name__ == "__main__":
    unittest.main()
