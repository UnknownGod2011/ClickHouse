from __future__ import annotations

import copy
import unittest

from takekeeper.extraction import (
    FixtureExtractionTransport,
    GovernedMultimodalExtractor,
    HERO_PROPERTY_REGISTRY,
    TakeExtractionRequest,
)
from takekeeper.extraction_projection import compare_extraction_to_baselines
from takekeeper.memory import InMemoryProductionMemory
from takekeeper.models import Baseline
from takekeeper.service import TakeAnalysisService


class ExtractionProjectionTests(unittest.TestCase):
    def _request(self):
        return TakeExtractionRequest(
            production_id="glass-house",
            scene_id="28",
            take_id="S28-T47",
            media_uri="fixture://projection",
            duration_ms=10_000,
            properties=HERO_PROPERTY_REGISTRY[:1],
            extractor_model="gemini-fixture",
            extractor_version="fixture-v1",
        )

    def _payload(self):
        return {
            "observations": [{
                "entity_id": "hero_mug",
                "property_key": "hand",
                "normalized_value": "left",
                "raw_model_value": "mug remains in left hand",
                "evidence_start_ms": 2000,
                "evidence_end_ms": 6500,
                "confidence": 0.96,
                "source_type": "vision",
                "evidence_rationale_short": "Mug is clearly visible in the left hand.",
                "visibility_state": "clear",
                "temporal_support": "sustained",
            }]
        }

    def _baseline(self):
        return Baseline(
            production_id="glass-house",
            scene_id="28",
            entity_id="hero_mug",
            property_key="hand",
            baseline_value="right",
            source_take_id="S28-T31",
        )

    def _extract(self, payload, *, run_id="run-projection"):
        return GovernedMultimodalExtractor(
            FixtureExtractionTransport({"fixture://projection": payload}),
            run_id_factory=lambda: run_id,
        ).extract(self._request())

    def _analyze(self, payload):
        return compare_extraction_to_baselines(result=self._extract(payload), baselines=[self._baseline()])

    def test_high_confidence_sustained_evidence_can_become_mismatch(self):
        findings, projection = self._analyze(self._payload())

        self.assertEqual(len(projection.observations), 1)
        self.assertTrue(projection.decisions[0].projected)
        self.assertEqual(projection.decisions[0].reason, "eligible")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].status, "mismatch")
        self.assertEqual(findings[0].observed_value, "left")

    def test_abstention_cannot_become_mismatch(self):
        payload = copy.deepcopy(self._payload())
        payload["observations"][0].update(
            normalized_value="unknown",
            confidence=0.40,
            visibility_state="occluded",
            temporal_support="unknown",
        )
        findings, projection = self._analyze(payload)

        self.assertEqual(projection.decisions[0].reason, "abstention_value")
        self.assertEqual(projection.observations, ())
        self.assertEqual(findings[0].status, "insufficient_evidence")
        self.assertIsNone(findings[0].observed_value)

    def test_occluded_assertion_cannot_become_mismatch(self):
        payload = copy.deepcopy(self._payload())
        payload["observations"][0]["visibility_state"] = "occluded"
        findings, projection = self._analyze(payload)

        self.assertEqual(projection.decisions[0].reason, "visibility_not_clear")
        self.assertFalse(projection.decisions[0].projected)
        self.assertEqual(findings[0].status, "insufficient_evidence")

    def test_weak_confidence_cannot_become_mismatch(self):
        payload = copy.deepcopy(self._payload())
        payload["observations"][0]["confidence"] = 0.60
        findings, projection = self._analyze(payload)

        self.assertEqual(projection.decisions[0].reason, "needs_confirmation")
        self.assertFalse(projection.decisions[0].projected)
        self.assertEqual(findings[0].status, "insufficient_evidence")

    def test_uncertain_temporal_support_cannot_become_mismatch(self):
        payload = copy.deepcopy(self._payload())
        payload["observations"][0]["temporal_support"] = "single_sample"
        findings, projection = self._analyze(payload)

        self.assertEqual(projection.decisions[0].reason, "temporal_support_not_sustained")
        self.assertFalse(projection.decisions[0].projected)
        self.assertEqual(findings[0].status, "insufficient_evidence")

    def test_new_abstaining_run_replaces_stale_machine_projection(self):
        memory = InMemoryProductionMemory()
        memory.upsert_baselines([self._baseline()])
        service = TakeAnalysisService(memory)

        first_findings, _ = service.analyze_extraction(self._extract(self._payload(), run_id="run-1"))
        self.assertEqual(first_findings[0].status, "mismatch")
        self.assertEqual(len(memory.list_observations(production_id="glass-house", scene_id="28", take_id="S28-T47")), 1)

        abstaining = copy.deepcopy(self._payload())
        abstaining["observations"][0].update(
            normalized_value="unknown",
            confidence=0.35,
            visibility_state="occluded",
            temporal_support="unknown",
        )
        second_findings, second_projection = service.analyze_extraction(
            self._extract(abstaining, run_id="run-2")
        )

        self.assertEqual(second_projection.observations, ())
        self.assertEqual(
            memory.list_observations(production_id="glass-house", scene_id="28", take_id="S28-T47"),
            [],
        )
        self.assertEqual(len(second_findings), 1)
        self.assertEqual(second_findings[0].status, "insufficient_evidence")
        self.assertIsNone(second_findings[0].observed_value)


if __name__ == "__main__":
    unittest.main()
