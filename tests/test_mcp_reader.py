import json
import unittest

from takekeeper.mcp_reader import McpEvidenceReader, McpReadError
from takekeeper.queries import EditorialConstraints


CONTINUITY_ROW = {
    "production_id": "glass-house",
    "scene_id": "28",
    "take_id": "S28-T47",
    "entity_id": "maya",
    "property_key": "prop.mug.hand",
    "observed_value": "left",
    "confidence": 0.97,
    "evidence_start_ms": 4200,
    "evidence_end_ms": 8200,
    "baseline_value": "right",
    "baseline_source_take_id": "S28-T31",
}

EDITORIAL_ROW = {
    "take_id": "S28-T31",
    "take_number": 31,
    "director_rating": 5,
    "production_id": "glass-house",
    "scene_id": "28",
    "dialogue_evidence_ms": 3100,
    "eyeline_evidence_ms": 4300,
}


class FakeCaller:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class McpEvidenceReaderTests(unittest.TestCase):
    def test_continuity_parses_official_json_string_shape(self):
        caller = FakeCaller(json.dumps([CONTINUITY_ROW]))
        reader = McpEvidenceReader(caller)
        rows = reader.continuity_evidence(
            production_id="glass-house",
            scene_id="28",
            take_id="S28-T47",
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("left", rows[0].observed_value)
        self.assertEqual("right", rows[0].baseline_value)
        self.assertEqual("run_query", caller.calls[0][0])
        self.assertIn("o.production_id=p", caller.calls[0][1]["query"])
        self.assertEqual(1, reader.traces[0].row_count)

    def test_editorial_parses_mcp_text_content_envelope(self):
        caller = FakeCaller({
            "content": [{"type": "text", "text": json.dumps([EDITORIAL_ROW])}],
            "isError": False,
        })
        rows = McpEvidenceReader(caller).editorial_search(
            EditorialConstraints("glass-house", "28", min_rating=4)
        )
        self.assertEqual(("S28-T31",), tuple(row.take_id for row in rows))

    def test_accepts_future_structured_data_wrapper(self):
        caller = FakeCaller({"structuredContent": {"data": [CONTINUITY_ROW]}})
        rows = McpEvidenceReader(caller).continuity_evidence(
            production_id="glass-house",
            scene_id="28",
            take_id="S28-T47",
        )
        self.assertEqual(1, len(rows))

    def test_empty_result_is_truthful_empty_evidence(self):
        rows = McpEvidenceReader(FakeCaller("[]")).continuity_evidence(
            production_id="glass-house",
            scene_id="28",
            take_id="S28-T47",
        )
        self.assertEqual((), rows)

    def test_transport_outage_fails_closed(self):
        with self.assertRaisesRegex(McpReadError, "transport failed"):
            McpEvidenceReader(FakeCaller(ConnectionError("down"))).continuity_evidence(
                production_id="glass-house",
                scene_id="28",
                take_id="S28-T47",
            )

    def test_wrong_production_row_is_rejected(self):
        bad = dict(CONTINUITY_ROW, production_id="other-production")
        with self.assertRaisesRegex(McpReadError, "wrong production"):
            McpEvidenceReader(FakeCaller(json.dumps([bad]))).continuity_evidence(
                production_id="glass-house",
                scene_id="28",
                take_id="S28-T47",
            )

    def test_malformed_or_tool_error_payloads_fail_closed(self):
        for payload in [
            "not-json",
            {"content": [{"type": "image", "data": "..."}]},
            {"isError": True, "content": [{"type": "text", "text": "boom"}]},
            json.dumps([{"production_id": "glass-house"}]),
        ]:
            with self.subTest(payload=payload):
                with self.assertRaises(McpReadError):
                    McpEvidenceReader(FakeCaller(payload)).continuity_evidence(
                        production_id="glass-house",
                        scene_id="28",
                        take_id="S28-T47",
                    )

    def test_invalid_confidence_and_evidence_window_fail_closed(self):
        invalid_confidence = dict(CONTINUITY_ROW, confidence=1.2)
        invalid_window = dict(CONTINUITY_ROW, evidence_start_ms=9000, evidence_end_ms=100)
        for row in [invalid_confidence, invalid_window]:
            with self.subTest(row=row):
                with self.assertRaises(McpReadError):
                    McpEvidenceReader(FakeCaller(json.dumps([row]))).continuity_evidence(
                        production_id="glass-house",
                        scene_id="28",
                        take_id="S28-T47",
                    )


if __name__ == "__main__":
    unittest.main()
