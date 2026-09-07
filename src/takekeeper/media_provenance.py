from __future__ import annotations

import hashlib
import mimetypes
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

SUPPORTED_VIDEO_MIME_TYPES: frozenset[str] = frozenset(
    {
        "video/mp4",
        "video/mpeg",
        "video/quicktime",
        "video/x-msvideo",
        "video/x-flv",
        "video/webm",
        "video/x-ms-wmv",
        "video/3gpp",
    }
)

_MAX_URI_LENGTH = 8192
_DEFAULT_MAX_LOCAL_BYTES = 100 * 1024 * 1024 * 1024


class MediaProvenanceError(ValueError):
    """Trusted media metadata or local bytes violated the ingest contract."""


@dataclass(frozen=True, slots=True)
class TrustedMediaProvenance:
    """Bounded provenance metadata for one production-media object.

    `locator_sha256` fingerprints the complete trusted URI, including a signed query if
    present, without exposing the URI in downstream reports. `content_sha256`, when
    available, identifies actual bytes and therefore supersedes locator identity for
    duplicate/change detection.
    """

    locator_sha256: str
    duration_ms: int
    mime_type: str
    content_sha256: str | None = None
    byte_size: int | None = None

    @property
    def has_content_identity(self) -> bool:
        return self.content_sha256 is not None


@dataclass(frozen=True, slots=True)
class LocalMediaDigest:
    path: Path
    content_sha256: str
    byte_size: int
    mime_type: str


def _validate_media_uri(uri: str) -> None:
    if not isinstance(uri, str) or not uri.strip():
        raise MediaProvenanceError("media URI must be non-empty")
    if len(uri) > _MAX_URI_LENGTH:
        raise MediaProvenanceError("media URI is too long")
    parsed = urlparse(uri)
    if parsed.scheme not in {"https", "gs"}:
        raise MediaProvenanceError("media URI must use https:// or gs://")
    if parsed.username or parsed.password:
        raise MediaProvenanceError("media URI must not contain embedded credentials")
    if parsed.scheme == "https" and not parsed.netloc:
        raise MediaProvenanceError("https media URI must include a host")
    if parsed.scheme == "gs" and (not parsed.netloc or not parsed.path.strip("/")):
        raise MediaProvenanceError("gs media URI must include a bucket and object")


def _validate_sha256(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise MediaProvenanceError(f"{field_name} must be a lowercase SHA-256 hex digest")
    if value != value.lower() or any(ch not in "0123456789abcdef" for ch in value):
        raise MediaProvenanceError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


def resolve_video_mime_type(uri: str, explicit_mime_type: str | None = None) -> str:
    """Resolve a supported video MIME type from trusted metadata and/or URI suffix.

    Explicit metadata enables extensionless signed/object URLs. When both explicit MIME
    metadata and an inferable suffix are present, disagreement fails closed instead of
    silently trusting either source.
    """

    _validate_media_uri(uri)
    parsed = urlparse(uri)
    inferred, _ = mimetypes.guess_type(parsed.path)
    if inferred not in SUPPORTED_VIDEO_MIME_TYPES:
        inferred = None

    if explicit_mime_type is not None:
        if not isinstance(explicit_mime_type, str):
            raise MediaProvenanceError("explicit MIME type must be a string")
        explicit = explicit_mime_type.strip().lower()
        if explicit not in SUPPORTED_VIDEO_MIME_TYPES:
            raise MediaProvenanceError("explicit MIME type is not a supported video type")
        if inferred is not None and inferred != explicit:
            raise MediaProvenanceError("explicit MIME type conflicts with the media URI suffix")
        return explicit

    if inferred is None:
        raise MediaProvenanceError("media URI is ambiguous; trusted explicit video MIME metadata is required")
    return inferred


def build_media_provenance(
    *,
    media_uri: str,
    duration_ms: int,
    mime_type: str | None = None,
    content_sha256: str | None = None,
    byte_size: int | None = None,
) -> TrustedMediaProvenance:
    """Build a redaction-safe provenance record from trusted ingest metadata."""

    if type(duration_ms) is not int or duration_ms <= 0:
        raise MediaProvenanceError("duration_ms must be a positive integer")
    resolved_mime = resolve_video_mime_type(media_uri, mime_type)

    if content_sha256 is not None:
        content_sha256 = _validate_sha256(content_sha256, field_name="content_sha256")
    if byte_size is not None and (type(byte_size) is not int or byte_size <= 0):
        raise MediaProvenanceError("byte_size must be a positive integer when provided")
    if content_sha256 is None and byte_size is not None:
        raise MediaProvenanceError("byte_size requires content_sha256 so byte identity is not implied")

    locator_sha256 = hashlib.sha256(media_uri.encode("utf-8")).hexdigest()
    return TrustedMediaProvenance(
        locator_sha256=locator_sha256,
        duration_ms=duration_ms,
        mime_type=resolved_mime,
        content_sha256=content_sha256,
        byte_size=byte_size,
    )


def hash_local_media(
    path: str | os.PathLike[str],
    *,
    mime_type: str | None = None,
    max_bytes: int = _DEFAULT_MAX_LOCAL_BYTES,
    chunk_size: int = 1024 * 1024,
) -> LocalMediaDigest:
    """Stream-hash an operator-owned local media file without following symlinks.

    This helper intentionally does not upload, mutate, delete, transcode, or open remote
    URLs. It is suitable for ingest-time hashing before an operator uploads immutable
    production media to object storage.
    """

    if type(max_bytes) is not int or max_bytes <= 0:
        raise MediaProvenanceError("max_bytes must be a positive integer")
    if type(chunk_size) is not int or chunk_size <= 0 or chunk_size > 16 * 1024 * 1024:
        raise MediaProvenanceError("chunk_size must be between 1 byte and 16 MiB")

    media_path = Path(path)
    try:
        metadata = media_path.lstat()
    except OSError as exc:
        raise MediaProvenanceError("local media file is not accessible") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise MediaProvenanceError("local media path must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise MediaProvenanceError("local media path must be a regular file")
    if metadata.st_size <= 0:
        raise MediaProvenanceError("local media file must be non-empty")
    if metadata.st_size > max_bytes:
        raise MediaProvenanceError("local media file exceeds configured hashing limit")

    inferred, _ = mimetypes.guess_type(media_path.name)
    if mime_type is None:
        resolved_mime = inferred if inferred in SUPPORTED_VIDEO_MIME_TYPES else None
        if resolved_mime is None:
            raise MediaProvenanceError("local media type is ambiguous; explicit video MIME metadata is required")
    else:
        explicit = mime_type.strip().lower() if isinstance(mime_type, str) else ""
        if explicit not in SUPPORTED_VIDEO_MIME_TYPES:
            raise MediaProvenanceError("explicit MIME type is not a supported video type")
        if inferred in SUPPORTED_VIDEO_MIME_TYPES and inferred != explicit:
            raise MediaProvenanceError("explicit MIME type conflicts with the local file suffix")
        resolved_mime = explicit

    digest = hashlib.sha256()
    bytes_read = 0
    try:
        with media_path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > max_bytes:
                    raise MediaProvenanceError("local media file exceeded configured hashing limit while reading")
                digest.update(chunk)
    except MediaProvenanceError:
        raise
    except OSError as exc:
        raise MediaProvenanceError("local media file could not be hashed") from exc

    if bytes_read != metadata.st_size:
        raise MediaProvenanceError("local media file changed while it was being hashed")

    return LocalMediaDigest(
        path=media_path,
        content_sha256=digest.hexdigest(),
        byte_size=bytes_read,
        mime_type=resolved_mime,
    )
