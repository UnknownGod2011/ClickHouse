from __future__ import annotations

import json
import unittest
from dataclasses import dataclass
from typing import Any

from takekeeper.extraction import (
    GovernedMultimodalExtractor,
    HERO_PROPERTY_REGISTRY,
    TakeExtractionRequest,
    build_extraction_prompt,
)
from takekeeper.google_genai_transport import (
    GoogleGenAIExtractionTransport,
    GoogleGenAITransportConfig,
    GoogleGenAITransportError,
    _google_json_schema,
    _supported_video_mime,
)


@dataclass
class FakeResponse:
    text: str | None


class FakeModels:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response or FakeResponse('{"observations": []}')
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, models: FakeModels) -> None:
        self.models = models


class GoogleGenAITransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parts: list[tuple[str, str]] = []

        def part_factory(uri: str, mime_type: str) -> dict[str, str]:
            self.parts.append((uri, mime_type))
            return {"uri": uri, "mime_type": mime_type}

        self.part_factory = part_factory

    def _prompt(self, uri: str = "gs://takekeeper-private/scene-12/take-47.mp4"):
        request = TakeExtractionRequest(
            production_id="prod-a",
            scene_id="S12",
            take_id="T47",
            media_uri=uri,
            duration_ms=10_000,
            properties=(HERO_PROPERTY_REGISTRY[0],),
            extractor_model="gemini-test",
            extractor_version="test",
        )
        return request, build_extraction_prompt(request)

    def test_generate_content_is_bounded_and_schema_constrained(self) -> None:
        models = FakeModels(FakeResponse('{"observations": []}'))
        transport = GoogleGenAIExtractionTransport(
            FakeClient(models),
            GoogleGenAITransportConfig(model="gemini-2.5-flash", max_output_tokens=2048),
            part_factory=self.part_factory,
        )
        _, prompt = self._prompt()

        response = transport(prompt)

        self.assertEqual(response, '{"observations": []}')
        self.assertEqual(self.parts, [(prompt.media_uri, "video/mp4")])
        self.assertEqual(len(models.calls), 1)
        call = models.calls[0]
        self.assertEqual(call["model"], "gemini-2.5-flash")
        self.assertEqual(call["contents"], [{"uri": prompt.media_uri, "mime_type": "video/mp4"}, prompt.text])
        self.assertEqual(call["config"]["response_mime_type"], "application/json")
        self.assertEqual(call["config"]["temperature"], 0.0)
        self.assertEqual(call["config"]["max_output_tokens"], 2048)
        self.assertNotIn("tools", call["config"])
        self.assertNotIn("x-takekeeper-configured-properties", call["config"]["response_json_schema"])
        self.assertEqual(prompt.response_schema["x-takekeeper-configured-properties"], ["hero_mug.hand"])

    def test_governed_extractor_revalidates_provider_json(self) -> None:
        payload = {
            "observations": [
                {
                    "entity_id": "hero_mug",
                    "property_key": "hand",
                    "normalized_value": "left",
                    "raw_model_value": "left hand",
                    "evidence_start_ms": 1000,
                    "evidence_end_ms": 5000,
                    "confidence": 0.97,
                    "source_type": "vision",
                    "evidence_rationale_short": "Mug remains in left hand.",
                    "visibility_state": "clear",
                    "temporal_support": "sustained",
                }
            ]
        }
        models = FakeModels(FakeResponse(json.dumps(payload)))
        transport = GoogleGenAIExtractionTransport(
            FakeClient(models),
            GoogleGenAITransportConfig(model="gemini-2.5-flash"),
            part_factory=self.part_factory,
        )
        request, _ = self._prompt()

        result = GovernedMultimodalExtractor(transport, run_id_factory=lambda: "run-google").extract(request)

        self.assertEqual(result.run_id, "run-google")
        self.assertEqual(result.observations[0].observation.production_id, "prod-a")
        self.assertEqual(result.observations[0].observation.normalized_value, "left")
        self.assertEqual(result.observations[0].disposition, "machine_high_confidence")

    def test_provider_cannot_inject_trusted_scope_fields(self) -> None:
        payload = {
            "observations": [],
            "production_id": "attacker-production",
        }
        models = FakeModels(FakeResponse(json.dumps(payload)))
        transport = GoogleGenAIExtractionTransport(
            FakeClient(models),
            GoogleGenAITransportConfig(model="gemini-2.5-flash"),
            part_factory=self.part_factory,
        )
        request, _ = self._prompt()

        with self.assertRaisesRegex(Exception, "only an observations array"):
            GovernedMultimodalExtractor(transport).extract(request)

    def test_rejects_untrusted_or_ambiguous_media_uri_schemes(self) -> None:
        for uri in (
            "file:///tmp/take.mp4",
            "http://example.test/take.mp4",
            "ftp://example.test/take.mp4",
            "https://user:pass@example.test/take.mp4",
            "gs://bucket",
        ):
            with self.subTest(uri=uri):
                with self.assertRaises(GoogleGenAITransportError):
                    _supported_video_mime(uri)

    def test_accepts_supported_https_and_gcs_video_types(self) -> None:
        self.assertEqual(_supported_video_mime("https://media.example/take.webm?sig=redacted"), "video/webm")
        self.assertEqual(_supported_video_mime("gs://bucket/path/take.mov"), "video/quicktime")

    def test_rejects_unknown_or_nonvideo_media_extensions(self) -> None:
        for uri in ("https://media.example/take", "https://media.example/frame.jpg"):
            with self.subTest(uri=uri):
                with self.assertRaises(GoogleGenAITransportError):
                    _supported_video_mime(uri)

    def test_provider_failure_is_redacted(self) -> None:
        models = FakeModels(error=RuntimeError("secret endpoint detail"))
        transport = GoogleGenAIExtractionTransport(
            FakeClient(models),
            GoogleGenAITransportConfig(model="gemini-2.5-flash"),
            part_factory=self.part_factory,
        )
        _, prompt = self._prompt()

        with self.assertRaisesRegex(GoogleGenAITransportError, "generate_content failed") as raised:
            transport(prompt)
        self.assertNotIn("secret endpoint detail", str(raised.exception))

    def test_missing_or_empty_response_text_fails_closed(self) -> None:
        for text in (None, "", "   "):
            with self.subTest(text=text):
                models = FakeModels(FakeResponse(text))
                transport = GoogleGenAIExtractionTransport(
                    FakeClient(models),
                    GoogleGenAITransportConfig(model="gemini-2.5-flash"),
                    part_factory=self.part_factory,
                )
                _, prompt = self._prompt()
                with self.assertRaises(GoogleGenAITransportError):
                    transport(prompt)

    def test_schema_sanitizer_removes_only_provider_private_annotations(self) -> None:
        schema = {
            "type": "object",
            "x-private": "remove",
            "properties": {"value": {"type": "string", "x-note": "remove"}},
            "required": ["value"],
        }
        sanitized = _google_json_schema(schema)
        self.assertEqual(
            sanitized,
            {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
        )
        self.assertIn("x-private", schema)

    def test_config_validation(self) -> None:
        with self.assertRaises(ValueError):
            GoogleGenAITransportConfig(model="")
        with self.assertRaises(ValueError):
            GoogleGenAITransportConfig(model="gemini", max_output_tokens=0)
        with self.assertRaises(ValueError):
            GoogleGenAITransportConfig(model="gemini", temperature=-0.1)


if __name__ == "__main__":
    unittest.main()
