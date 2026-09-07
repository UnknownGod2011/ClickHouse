from __future__ import annotations

import json
from dataclasses import asdict
from typing import Mapping, Sequence

from .extraction import HERO_PROPERTY_REGISTRY, PropertySpec, TakeExtractionRequest
from .ingest_runtime import IngestNotReady, SchemaGatedIngestService
from .review_api import ReviewerIdentityProvider

MAX_BODY_BYTES = 32_768
MAX_TEXT_FIELD_LENGTH = 256
MAX_MEDIA_URI_LENGTH = 4_096
MAX_DURATION_MS = 24 * 60 * 60 * 1_000
_ALLOWED_FIELDS = {
    "production_id",
    "scene_id",
    "take_id",
    "media_uri",
    "duration_ms",
    "property_profile",
    "media_mime_type",
    "media_content_sha256",
    "media_byte_size",
}


class IngestHttpApp:
    """Narrow WSGI ingress for trusted TakeKeeper extraction.

    Liveness is process-local and intentionally independent of ClickHouse. Readiness is the
    coarse state exported by :class:`SchemaGatedIngestService`. Ingestion is authenticated,
    accepts only bounded trusted take metadata, and never lets callers choose model identity,
    prompt schema, or arbitrary property/value registries.
    """

    def __init__(
        self,
        service: SchemaGatedIngestService,
        identity: ReviewerIdentityProvider,
        *,
        property_profiles: Mapping[str, Sequence[PropertySpec]] | None = None,
        extractor_model: str,
        extractor_version: str,
        prompt_schema_version: str = "takekeeper-extraction-v1",
        credential_environ_key: str = "HTTP_AUTHORIZATION",
    ) -> None:
        self._service = service
        self._identity = identity
        configured = property_profiles or {"hero": HERO_PROPERTY_REGISTRY}
        if not configured:
            raise ValueError("at least one property profile is required")
        self._profiles: dict[str, tuple[PropertySpec, ...]] = {}
        for name, specs in configured.items():
            profile = name.strip() if isinstance(name, str) else ""
            values = tuple(specs)
            if not profile or len(profile) > 128 or not values:
                raise ValueError("invalid property profile")
            self._profiles[profile] = values
        if not extractor_model.strip() or not extractor_version.strip() or not prompt_schema_version.strip():
            raise ValueError("extractor identity must be configured")
        if (
            not isinstance(credential_environ_key, str)
            or not credential_environ_key.startswith("HTTP_")
            or len(credential_environ_key) > 128
            or not all(ch.isupper() or ch.isdigit() or ch == "_" for ch in credential_environ_key)
        ):
            raise ValueError("invalid credential environ key")
        self._extractor_model = extractor_model.strip()
        self._extractor_version = extractor_version.strip()
        self._prompt_schema_version = prompt_schema_version.strip()
        self._credential_environ_key = credential_environ_key

    def __call__(self, environ, start_response):
        try:
            status, payload = self._dispatch(environ)
        except PermissionError:
            status, payload = 401, {"error": "authentication required"}
        except IngestNotReady:
            status, payload = 503, {"error": "ingestion not ready"}
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            status, payload = 400, {"error": "invalid request"}
        except Exception:
            status, payload = 500, {"error": "internal server error"}

        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        start_response(
            f"{status} {_status_text(status)}",
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]

    def _dispatch(self, environ) -> tuple[int, dict]:
        method = str(environ.get("REQUEST_METHOD", "")).upper()
        path = str(environ.get("PATH_INFO", ""))

        if path == "/healthz":
            if method != "GET":
                return 405, {"error": "method not allowed"}
            return 200, {"status": "ok"}

        if path == "/readyz":
            if method != "GET":
                return 405, {"error": "method not allowed"}
            readiness = self._service.readiness()
            return (200 if readiness.ready else 503), {
                "status": readiness.state,
                "schema_checked": readiness.schema_checked,
            }

        if path != "/v1/ingest":
            return 404, {"error": "not found"}
        if method != "POST":
            return 405, {"error": "method not allowed"}

        # Authenticate before reading attacker-controlled request bytes. Deployments may source
        # credentials from Authorization or a verified reverse-proxy assertion header such as IAP.
        self._identity.authenticate(environ.get(self._credential_environ_key))
        payload = _read_json_body(environ)
        request = self._request_from_payload(payload)
        ingested = self._service.ingest(request)
        return 201, {
            "run_id": ingested.result.run_id,
            "production_id": ingested.result.production_id,
            "scene_id": ingested.result.scene_id,
            "take_id": ingested.result.take_id,
            "observation_count": len(ingested.result.observations),
        }

    def _request_from_payload(self, payload: dict) -> TakeExtractionRequest:
        if set(payload) - _ALLOWED_FIELDS:
            raise ValueError("unexpected fields")

        production_id = _bounded_text(payload, "production_id")
        scene_id = _bounded_text(payload, "scene_id")
        take_id = _bounded_text(payload, "take_id")
        media_uri = _bounded_text(payload, "media_uri", max_length=MAX_MEDIA_URI_LENGTH)
        profile_name = _bounded_text(payload, "property_profile", max_length=128)
        try:
            properties = self._profiles[profile_name]
        except KeyError as exc:
            raise ValueError("unknown property profile") from exc

        duration_ms = payload.get("duration_ms")
        if type(duration_ms) is not int or not 0 < duration_ms <= MAX_DURATION_MS:
            raise ValueError("invalid duration")

        media_mime_type = payload.get("media_mime_type")
        media_content_sha256 = payload.get("media_content_sha256")
        media_byte_size = payload.get("media_byte_size")
        for optional_text in (media_mime_type, media_content_sha256):
            if optional_text is not None and not isinstance(optional_text, str):
                raise ValueError("invalid media provenance")
        if media_byte_size is not None and type(media_byte_size) is not int:
            raise ValueError("invalid media provenance")

        return TakeExtractionRequest(
            production_id=production_id,
            scene_id=scene_id,
            take_id=take_id,
            media_uri=media_uri,
            duration_ms=duration_ms,
            properties=properties,
            extractor_model=self._extractor_model,
            extractor_version=self._extractor_version,
            prompt_schema_version=self._prompt_schema_version,
            media_mime_type=media_mime_type,
            media_content_sha256=media_content_sha256,
            media_byte_size=media_byte_size,
        )


def _read_json_body(environ) -> dict:
    raw_length = environ.get("CONTENT_LENGTH") or "0"
    try:
        length = int(raw_length)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid content length") from exc
    if length <= 0 or length > MAX_BODY_BYTES:
        raise ValueError("invalid body size")
    body = environ["wsgi.input"].read(length)
    if len(body) != length:
        raise ValueError("incomplete body")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload


def _bounded_text(payload: dict, field: str, *, max_length: int = MAX_TEXT_FIELD_LENGTH) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise ValueError("invalid text field")
    value = value.strip()
    if not value or len(value) > max_length or any(ord(ch) < 32 for ch in value):
        raise ValueError("invalid text field")
    return value


def _status_text(status: int) -> str:
    return {
        200: "OK",
        201: "Created",
        400: "Bad Request",
        401: "Unauthorized",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
        503: "Service Unavailable",
    }[status]
