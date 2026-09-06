from __future__ import annotations

import unittest

from takekeeper.extraction import (
    ExtractionSchemaError,
    FixtureExtractionTransport,
    GovernedMultimodalExtractor,
    HERO_PROPERTY_REGISTRY,
    PropertySpec,
    TakeExtractionRequest,
)
from takekeeper.extraction_eval import TruthObservation, evaluate_extraction


class GovernedExtractionTests(unittest.TestCase):
    def _request(self, *, properties=None, duration_ms=10_000):
        return TakeExtractionRequest(
            production_id="glass-house",
            scene_id="28",
            take_id="S28-T47",
            media_uri="fixture://s28-t47",
            duration_ms=duration_ms,
            properties=tuple(properties or HERO_PROPERTY_REGISTRY[:2]),
            extractor_model="gemini-fixture",
            extractor_version="fixture-v1",
        )

    def _payload(self):
        return {
            "observations": [
                {
                    "entity_id": "hero_mug",
                    "property_key": "hand",
                    "normalized_value": "left",
                    "raw_model_value": "mug is in her left hand",
                    "evidence_start_ms": 2000,
                    "evidence_end_ms": 6000,
                    "confidence": 0.96,
                    "source_type": "vision",
                    "evidence_rationale_short": "Mug remains visibly held in the left hand.",
                    "visibility_state": "clear",
                    "temporal_support": "sustained",
                },
                {
                    "entity_id": "maya",
                    "property_key": "jacket_state",
                    "normalized_value": "open",
                    "raw_model_value": "jacket front is open",
                    "evidence_start_ms": 1000,
                    "evidence_end_ms": 7000,
                    "confidence": 0.91,
                    "source_type": "vision",
                    "evidence_rationale_short": "Open jacket front is visible across the window.",
                    "visibility_state": "clear",
                    "temporal_support": "sustained",
                },
            ]
        }

    def test_fixture_transport_uses_same_validation_path_and_trusted_scope(self):
        transport = FixtureExtractionTransport({"fixture://s28-t47": self._payload()})
        result = GovernedMultimodalExtractor(transport, run_id_factory=lambda: "run-1").extract(self._request())

        self.assertEqual(result.run_id, "run-1")
        self.assertEqual(len(result.observations), 2)
        self.assertEqual(result.observations[0].observation.production_id, "glass-house")
        self.assertEqual(result.observations[0].observation.take_id, "S28-T47")
        self.assertEqual(result.observations[0].disposition, "machine_high_confidence")
        self.assertEqual(len(transport.calls), 1)
        self.assertIn("unknown/uncertain", transport.calls[0].text)

    def test_rejects_unconfigured_property(self):
        payload = self._payload()
        payload["observations"][0]["property_key"] = "color"
        extractor = GovernedMultimodalExtractor(FixtureExtractionTransport({"fixture://s28-t47": payload}))
        with self.assertRaisesRegex(ExtractionSchemaError, "unconfigured property"):
            extractor.extract(self._request())

    def test_rejects_out_of_registry_value(self):
        payload = self._payload()
        payload["observations"][0]["normalized_value"] = "over_shoulder"
        extractor = GovernedMultimodalExtractor(FixtureExtractionTransport({"fixture://s28-t47": payload}))
        with self.assertRaisesRegex(ExtractionSchemaError, "out-of-registry value"):
            extractor.extract(self._request())

    def test_rejects_impossible_evidence_window(self):
        payload = self._payload()
        payload["observations"][0]["evidence_end_ms"] = 10001
        extractor = GovernedMultimodalExtractor(FixtureExtractionTransport({"fixture://s28-t47": payload}))
        with self.assertRaisesRegex(ExtractionSchemaError, "invalid evidence window"):
            extractor.extract(self._request(duration_ms=10_000))

    def test_low_confidence_or_weak_temporal_support_requires_confirmation(self):
        payload = self._payload()
        payload["observations"][0]["confidence"] = 0.61
        payload["observations"][1]["temporal_support"] = "single_sample"
        result = GovernedMultimodalExtractor(FixtureExtractionTransport({"fixture://s28-t47": payload})).extract(self._request())
        self.assertEqual([item.disposition for item in result.observations], ["needs_confirmation", "needs_confirmation"])

    def test_source_policy_is_property_specific(self):
        dialogue = PropertySpec(
            "dialogue",
            "im_leaving",
            ("present", "absent", "uncertain"),
            allowed_sources=("transcript",),
        )
        payload = {
            "observations": [{
                "entity_id": "dialogue",
                "property_key": "im_leaving",
                "normalized_value": "present",
                "raw_model_value": "I'm leaving",
                "evidence_start_ms": 1000,
                "evidence_end_ms": 2000,
                "confidence": 0.95,
                "source_type": "vision",
                "evidence_rationale_short": "Lip movement appears consistent.",
                "visibility_state": "clear",
                "temporal_support": "sustained",
            }]
        }
        extractor = GovernedMultimodalExtractor(FixtureExtractionTransport({"fixture://s28-t47": payload}))
        with self.assertRaisesRegex(ExtractionSchemaError, "disallowed evidence source"):
            extractor.extract(self._request(properties=(dialogue,)))

    def test_evaluator_measures_value_evidence_and_unsupported_assertions(self):
        result = GovernedMultimodalExtractor(
            FixtureExtractionTransport({"fixture://s28-t47": self._payload()})
        ).extract(self._request())
        metrics = evaluate_extraction(
            result.observations,
            [
                TruthObservation("hero_mug", "hand", "left", 1500, 6500),
                TruthObservation("maya", "jacket_state", "open", 900, 7100),
            ],
        )
        self.assertEqual(metrics.exact_value_accuracy, 1.0)
        self.assertEqual(metrics.evidence_overlap_rate, 1.0)
        self.assertEqual(metrics.unsupported_assertions, 0)

    def test_unobservable_truth_requires_abstention(self):
        payload = self._payload()
        payload["observations"] = [payload["observations"][0]]
        payload["observations"][0]["normalized_value"] = "unknown"
        payload["observations"][0]["confidence"] = 0.45
        payload["observations"][0]["visibility_state"] = "occluded"
        payload["observations"][0]["temporal_support"] = "unknown"
        result = GovernedMultimodalExtractor(
            FixtureExtractionTransport({"fixture://s28-t47": payload})
        ).extract(self._request(properties=HERO_PROPERTY_REGISTRY[:1]))
        metrics = evaluate_extraction(
            result.observations,
            [TruthObservation("hero_mug", "hand", "unknown", 0, 10_000, observable=False)],
        )
        self.assertEqual(metrics.abstention_correct, 1)
        self.assertEqual(metrics.unsupported_assertions, 0)


if __name__ == "__main__":
    unittest.main()
