from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from takekeeper.extraction import HERO_PROPERTY_REGISTRY, TakeExtractionRequest, build_extraction_prompt
from takekeeper.google_genai_transport import (
    GoogleGenAIExtractionTransport,
    GoogleGenAITransportConfig,
    GoogleGenAITransportError,
)


@dataclass
class FakeResponse:
    text: str = '{"observations": []}'


class FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return FakeResponse()


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


class TrustedMediaExtractionTests(unittest.TestCase):
    def _request(self, **overrides: Any) -> TakeExtractionRequest:
        values = {
            "production_id": "prod-a",
            "scene_id": "S12",
            "take_id": "T47",
            "media_uri": "https://media.example/object/opaque-id?signature=secret",
            "duration_ms": 10_000,
            "properties": (HERO_PROPERTY_REGISTRY[0],),
            "extractor_model": "gemini-test",
            "extractor_version": "candidate-1",
            "media_mime_type": "video/mp4",
            "media_content_sha256": "a" * 64,
            "media_byte_size": 123456,
        }
        values.update(overrides)
        return TakeExtractionRequest(**values)

    def test_prompt_carries_trusted_media_metadata_without_putting_it_in_prompt_text(self) -> None:
        request = self._request()
        prompt = build_extraction_prompt(request)

        self.assertEqual(prompt.media_uri, request.media_uri)
        self.assertEqual(prompt.media_mime_type, "video/mp4")
        self.assertEqual(prompt.media_content_sha256, "a" * 64)
        self.assertEqual(prompt.media_byte_size, 123456)
        self.assertNotIn("signature=secret", prompt.text)
        self.assertNotIn("a" * 64, prompt.text)

    def test_google_transport_accepts_extensionless_signed_media_with_trusted_mime(self) -> None:
        request = self._request()
        prompt = build_extraction_prompt(request)
        parts: list[tuple[str, str]] = []

        def part_factory(uri: str, mime_type: str) -> dict[str, str]:
            parts.append((uri, mime_type))
            return {"uri": uri, "mime_type": mime_type}

        client = FakeClient()
        transport = GoogleGenAIExtractionTransport(
            client,
            GoogleGenAITransportConfig(model="gemini-test"),
            part_factory=part_factory,
        )

        self.assertEqual(transport(prompt), '{"observations": []}')
        self.assertEqual(parts, [(request.media_uri, "video/mp4")])
        self.assertEqual(len(client.models.calls), 1)

    def test_google_transport_rejects_trusted_mime_that_conflicts_with_suffix(self) -> None:
        request = self._request(
            media_uri="https://media.example/take.webm?signature=secret",
            media_mime_type="video/mp4",
        )
        prompt = build_extraction_prompt(request)
        transport = GoogleGenAIExtractionTransport(
            FakeClient(),
            GoogleGenAITransportConfig(model="gemini-test"),
            part_factory=lambda uri, mime: (uri, mime),
        )

        with self.assertRaisesRegex(GoogleGenAITransportError, "conflicts"):
            transport(prompt)

    def test_content_size_requires_content_hash(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires media_content_sha256"):
            self._request(media_content_sha256=None, media_byte_size=123)

    def test_content_hash_must_be_lowercase_sha256(self) -> None:
        for digest in ("A" * 64, "z" * 64, "abc"):
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
                    self._request(media_content_sha256=digest)

    def test_existing_suffix_based_request_remains_backward_compatible(self) -> None:
        request = self._request(
            media_uri="gs://bucket/take.mp4",
            media_mime_type=None,
            media_content_sha256=None,
            media_byte_size=None,
        )
        prompt = build_extraction_prompt(request)
        self.assertIsNone(prompt.media_mime_type)
        self.assertIsNone(prompt.media_content_sha256)
        self.assertIsNone(prompt.media_byte_size)


if __name__ == "__main__":
    unittest.main()
