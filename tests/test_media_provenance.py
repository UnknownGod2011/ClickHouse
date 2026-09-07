from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from takekeeper.media_provenance import (
    MediaProvenanceError,
    build_media_provenance,
    hash_local_media,
    resolve_video_mime_type,
)


class MediaProvenanceTests(unittest.TestCase):
    def test_extensionless_signed_https_accepts_trusted_explicit_mime(self) -> None:
        uri = "https://media.example/object/abc123?X-Signature=secret"
        self.assertEqual(resolve_video_mime_type(uri, "video/mp4"), "video/mp4")

    def test_supported_suffix_is_inferred_without_explicit_metadata(self) -> None:
        self.assertEqual(resolve_video_mime_type("gs://bucket/scene/take.webm"), "video/webm")

    def test_ambiguous_uri_requires_explicit_mime(self) -> None:
        with self.assertRaisesRegex(MediaProvenanceError, "explicit video MIME"):
            resolve_video_mime_type("https://media.example/object/abc123")

    def test_explicit_mime_conflict_fails_closed(self) -> None:
        with self.assertRaisesRegex(MediaProvenanceError, "conflicts"):
            resolve_video_mime_type("gs://bucket/take.mp4", "video/webm")

    def test_rejects_non_video_and_unsafe_uris(self) -> None:
        for uri in (
            "http://media.example/take.mp4",
            "file:///tmp/take.mp4",
            "https://user:pass@media.example/take.mp4",
            "gs://bucket",
        ):
            with self.subTest(uri=uri):
                with self.assertRaises(MediaProvenanceError):
                    resolve_video_mime_type(uri, "video/mp4")

    def test_provenance_hashes_complete_locator_without_exposing_it(self) -> None:
        uri = "https://media.example/take?signature=top-secret"
        record = build_media_provenance(media_uri=uri, duration_ms=2500, mime_type="video/mp4")
        self.assertEqual(record.locator_sha256, hashlib.sha256(uri.encode("utf-8")).hexdigest())
        self.assertNotIn("top-secret", repr(record))
        self.assertFalse(record.has_content_identity)

    def test_content_identity_is_validated_and_recorded(self) -> None:
        digest = hashlib.sha256(b"video-bytes").hexdigest()
        record = build_media_provenance(
            media_uri="gs://bucket/object",
            duration_ms=1000,
            mime_type="video/mp4",
            content_sha256=digest,
            byte_size=11,
        )
        self.assertEqual(record.content_sha256, digest)
        self.assertEqual(record.byte_size, 11)
        self.assertTrue(record.has_content_identity)

    def test_byte_size_without_content_hash_is_rejected(self) -> None:
        with self.assertRaisesRegex(MediaProvenanceError, "byte_size requires"):
            build_media_provenance(
                media_uri="gs://bucket/object",
                duration_ms=1000,
                mime_type="video/mp4",
                byte_size=100,
            )

    def test_invalid_digest_is_rejected(self) -> None:
        for digest in ("abc", "A" * 64, "g" * 64):
            with self.subTest(digest=digest):
                with self.assertRaises(MediaProvenanceError):
                    build_media_provenance(
                        media_uri="gs://bucket/object",
                        duration_ms=1000,
                        mime_type="video/mp4",
                        content_sha256=digest,
                    )

    def test_hash_local_media_streams_content_and_records_size(self) -> None:
        payload = (b"takekeeper-media" * 4096) + b"tail"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "take.mp4"
            path.write_bytes(payload)
            result = hash_local_media(path, chunk_size=257)

        self.assertEqual(result.content_sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(result.byte_size, len(payload))
        self.assertEqual(result.mime_type, "video/mp4")

    def test_local_extensionless_media_accepts_explicit_mime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "object-123"
            path.write_bytes(b"self-owned-fixture")
            result = hash_local_media(path, mime_type="video/mp4")
        self.assertEqual(result.mime_type, "video/mp4")

    def test_local_symlink_is_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "take.mp4"
            link = Path(directory) / "link.mp4"
            target.write_bytes(b"video")
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation unavailable")
            with self.assertRaisesRegex(MediaProvenanceError, "symlink"):
                hash_local_media(link)

    def test_local_size_limit_fails_before_reading_large_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "take.mp4"
            path.write_bytes(b"123456")
            with self.assertRaisesRegex(MediaProvenanceError, "hashing limit"):
                hash_local_media(path, max_bytes=5)

    def test_chunk_size_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "take.mp4"
            path.write_bytes(b"x")
            for chunk_size in (0, 16 * 1024 * 1024 + 1):
                with self.subTest(chunk_size=chunk_size):
                    with self.assertRaises(MediaProvenanceError):
                        hash_local_media(path, chunk_size=chunk_size)


if __name__ == "__main__":
    unittest.main()
