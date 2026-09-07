from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from .media_provenance import MediaProvenanceError, SUPPORTED_VIDEO_MIME_TYPES
from .models import Observation

SourceType = Literal["vision", "transcript", "metadata"]
VisibilityState = Literal["clear", "partial", "occluded", "absent", "unknown"]
TemporalSupport = Literal["sustained", "transient", "single_sample", "unknown"]
ExtractionDisposition = Literal["machine_high_confidence", "needs_confirmation"]


class ExtractionError(RuntimeError):
    """Base class for bounded extraction failures."""


class ExtractionTransportError(ExtractionError):
    """The model transport failed before a valid response was available."""


class ExtractionSchemaError(ExtractionError):
    """The model response violated the TakeKeeper extraction contract."""


@dataclass(frozen=True, slots=True)
class PropertySpec:
    entity_id: str
    property_key: str
    allowed_values: tuple[str, ...]
    minimum_confidence: float = 0.80
    allowed_sources: tuple[SourceType, ...] = ("vision",)

    def __post_init__(self) -> None:
        if not self.entity_id or not self.property_key:
            raise ValueError("property identity must be non-empty")
        if not self.allowed_values or len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("allowed_values must be a non-empty unique tuple")
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1")


HERO_PROPERTY_REGISTRY: tuple[PropertySpec, ...] = (
    PropertySpec("hero_mug", "hand", ("left", "right", "both", "not_held", "unknown")),
    PropertySpec("maya", "jacket_state", ("open", "zipped", "closed_unzipped", "unknown")),
    PropertySpec("practical_lamp", "power_state", ("on", "off", "unknown"), minimum_confidence=0.90),
    PropertySpec("boom", "visibility", ("visible", "not_visible", "unknown"), minimum_confidence=0.90),
    PropertySpec(
        "dialogue",
        "im_leaving",
        ("present", "absent", "uncertain"),
        minimum_confidence=0.85,
        allowed_sources=("transcript",),
    ),
)


@dataclass(frozen=True, slots=True)
class TakeExtractionRequest:
    production_id: str
    scene_id: str
    take_id: str
    media_uri: str
    duration_ms: int
    properties: tuple[PropertySpec, ...]
    extractor_model: str
    extractor_version: str
    prompt_schema_version: str = "takekeeper-extraction-v1"
    media_mime_type: str | None = None
    media_content_sha256: str | None = None
    media_byte_size: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("production_id", "scene_id", "take_id", "media_uri", "extractor_model", "extractor_version"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must be non-empty")
        if self.duration_ms <= 0:
            raise ValueError("duration_ms must be positive")
        if not self.properties:
            raise ValueError("at least one configured property is required")
        identities = [(item.entity_id, item.property_key) for item in self.properties]
        if len(set(identities)) != len(identities):
            raise ValueError("configured properties must be unique")
        if self.media_mime_type is not None:
            if not isinstance(self.media_mime_type, str) or self.media_mime_type.strip().lower() not in SUPPORTED_VIDEO_MIME_TYPES:
                raise ValueError("media_mime_type must be a supported video MIME type when provided")
        if self.media_content_sha256 is not None:
            value = self.media_content_sha256
            if not isinstance(value, str) or len(value) != 64 or value != value.lower() or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError("media_content_sha256 must be a lowercase SHA-256 hex digest")
        if self.media_byte_size is not None:
            if type(self.media_byte_size) is not int or self.media_byte_size <= 0:
                raise ValueError("media_byte_size must be a positive integer when provided")
            if self.media_content_sha256 is None:
                raise ValueError("media_byte_size requires media_content_sha256")


@dataclass(frozen=True, slots=True)
class ExtractionPrompt:
    text: str
    response_schema: Mapping[str, Any]
    media_uri: str
    media_mime_type: str | None = None
    media_content_sha256: str | None = None
    media_byte_size: int | None = None


@dataclass(frozen=True, slots=True)
class ExtractedObservation:
    observation: Observation
    source_type: SourceType
    extractor_model: str
    extractor_version: str
    raw_model_value: str
    evidence_rationale_short: str
    visibility_state: VisibilityState
    temporal_support: TemporalSupport
    disposition: ExtractionDisposition


@dataclass(frozen=True, slots=True)
class ExtractionRunResult:
    run_id: str
    production_id: str
    scene_id: str
    take_id: str
    extractor_model: str
    extractor_version: str
    prompt_schema_version: str
    observations: tuple[ExtractedObservation, ...]


class ExtractionTransport(Protocol):
    def __call__(self, prompt: ExtractionPrompt) -> str | Mapping[str, Any]: ...


def _response_schema(specs: Sequence[PropertySpec]) -> dict[str, Any]:
    identities = [f"{item.entity_id}.{item.property_key}" for item in specs]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["observations"],
        "properties": {
            "observations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "entity_id", "property_key", "normalized_value", "raw_model_value",
                        "evidence_start_ms", "evidence_end_ms", "confidence", "source_type",
                        "evidence_rationale_short", "visibility_state", "temporal_support",
                    ],
                    "properties": {
                        "entity_id": {"type": "string"},
                        "property_key": {"type": "string"},
                        "normalized_value": {"type": "string"},
                        "raw_model_value": {"type": "string"},
                        "evidence_start_ms": {"type": "integer", "minimum": 0},
                        "evidence_end_ms": {"type": "integer", "minimum": 0},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source_type": {"type": "string", "enum": ["vision", "transcript", "metadata"]},
                        "evidence_rationale_short": {"type": "string", "maxLength": 240},
                        "visibility_state": {"type": "string", "enum": ["clear", "partial", "occluded", "absent", "unknown"]},
                        "temporal_support": {"type": "string", "enum": ["sustained", "transient", "single_sample", "unknown"]},
                    },
                },
            }
        },
        "x-takekeeper-configured-properties": identities,
    }


def build_extraction_prompt(request: TakeExtractionRequest) -> ExtractionPrompt:
    registry_lines = []
    for spec in request.properties:
        registry_lines.append(
            f"- {spec.entity_id}.{spec.property_key}: one of {', '.join(spec.allowed_values)}; sources={','.join(spec.allowed_sources)}"
        )
    text = (
        "Analyze exactly one registered production take. Return only configured observations and cite bounded millisecond evidence windows. "
        "Use unknown/uncertain values when the media does not support a claim. Do not infer absence from failure to observe. "
        "Do not invent production, scene, take, entity, or property identifiers.\nConfigured properties:\n"
        + "\n".join(registry_lines)
    )
    return ExtractionPrompt(
        text=text,
        response_schema=_response_schema(request.properties),
        media_uri=request.media_uri,
        media_mime_type=request.media_mime_type.strip().lower() if request.media_mime_type is not None else None,
        media_content_sha256=request.media_content_sha256,
        media_byte_size=request.media_byte_size,
    )


class GovernedMultimodalExtractor:
    """Fail-closed adapter around a Gemini-compatible structured-output transport.

    Tenant/take scope is supplied by trusted application metadata, never copied from model output.
    The transport is intentionally injectable so deterministic fixtures and Google SDK clients share
    the same validation path.
    """

    def __init__(self, transport: ExtractionTransport, *, run_id_factory: Callable[[], str] | None = None) -> None:
        self._transport = transport
        self._run_id_factory = run_id_factory or (lambda: str(uuid.uuid4()))

    def extract(self, request: TakeExtractionRequest) -> ExtractionRunResult:
        prompt = build_extraction_prompt(request)
        try:
            raw_response = self._transport(prompt)
        except Exception as exc:  # transport implementations are intentionally pluggable
            raise ExtractionTransportError("multimodal extraction transport failed") from exc

        payload = self._decode_payload(raw_response)
        observations = self._validate_observations(request, payload)
        return ExtractionRunResult(
            run_id=self._run_id_factory(),
            production_id=request.production_id,
            scene_id=request.scene_id,
            take_id=request.take_id,
            extractor_model=request.extractor_model,
            extractor_version=request.extractor_version,
            prompt_schema_version=request.prompt_schema_version,
            observations=tuple(observations),
        )

    @staticmethod
    def _decode_payload(raw_response: str | Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(raw_response, str):
            try:
                payload = json.loads(raw_response)
            except json.JSONDecodeError as exc:
                raise ExtractionSchemaError("model response was not valid JSON") from exc
        elif isinstance(raw_response, Mapping):
            payload = raw_response
        else:
            raise ExtractionSchemaError("model response must be JSON text or an object")
        if set(payload) != {"observations"} or not isinstance(payload["observations"], list):
            raise ExtractionSchemaError("model response must contain only an observations array")
        return payload

    @staticmethod
    def _validate_observations(
        request: TakeExtractionRequest, payload: Mapping[str, Any]
    ) -> list[ExtractedObservation]:
        registry = {(item.entity_id, item.property_key): item for item in request.properties}
        seen: set[tuple[str, str]] = set()
        results: list[ExtractedObservation] = []
        required = {
            "entity_id", "property_key", "normalized_value", "raw_model_value",
            "evidence_start_ms", "evidence_end_ms", "confidence", "source_type",
            "evidence_rationale_short", "visibility_state", "temporal_support",
        }
        for index, row in enumerate(payload["observations"]):
            if not isinstance(row, Mapping) or set(row) != required:
                raise ExtractionSchemaError(f"observation {index} has missing or unexpected fields")
            identity = (row["entity_id"], row["property_key"])
            if identity not in registry:
                raise ExtractionSchemaError(f"observation {index} references an unconfigured property")
            if identity in seen:
                raise ExtractionSchemaError(f"observation {index} duplicates a configured property")
            seen.add(identity)
            spec = registry[identity]

            value = row["normalized_value"]
            if not isinstance(value, str) or value not in spec.allowed_values:
                raise ExtractionSchemaError(f"observation {index} has an out-of-registry value")
            raw_value = row["raw_model_value"]
            rationale = row["evidence_rationale_short"]
            if not isinstance(raw_value, str) or len(raw_value) > 240:
                raise ExtractionSchemaError(f"observation {index} has invalid raw_model_value")
            if not isinstance(rationale, str) or len(rationale) > 240:
                raise ExtractionSchemaError(f"observation {index} has invalid evidence rationale")

            start = row["evidence_start_ms"]
            end = row["evidence_end_ms"]
            if type(start) is not int or type(end) is not int or start < 0 or end < start or end > request.duration_ms:
                raise ExtractionSchemaError(f"observation {index} has an invalid evidence window")
            confidence = row["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
                raise ExtractionSchemaError(f"observation {index} has invalid confidence")

            source_type = row["source_type"]
            if source_type not in spec.allowed_sources:
                raise ExtractionSchemaError(f"observation {index} uses a disallowed evidence source")
            visibility = row["visibility_state"]
            temporal = row["temporal_support"]
            if visibility not in ("clear", "partial", "occluded", "absent", "unknown"):
                raise ExtractionSchemaError(f"observation {index} has invalid visibility_state")
            if temporal not in ("sustained", "transient", "single_sample", "unknown"):
                raise ExtractionSchemaError(f"observation {index} has invalid temporal_support")

            high_confidence = (
                value not in ("unknown", "uncertain")
                and float(confidence) >= spec.minimum_confidence
                and visibility == "clear"
                and temporal == "sustained"
            )
            results.append(
                ExtractedObservation(
                    observation=Observation(
                        production_id=request.production_id,
                        scene_id=request.scene_id,
                        take_id=request.take_id,
                        entity_id=spec.entity_id,
                        property_key=spec.property_key,
                        normalized_value=value,
                        confidence=float(confidence),
                        evidence_start_ms=start,
                        evidence_end_ms=end,
                        verification_state="unverified",
                    ),
                    source_type=source_type,
                    extractor_model=request.extractor_model,
                    extractor_version=request.extractor_version,
                    raw_model_value=raw_value,
                    evidence_rationale_short=rationale,
                    visibility_state=visibility,
                    temporal_support=temporal,
                    disposition="machine_high_confidence" if high_confidence else "needs_confirmation",
                )
            )
        return results


class FixtureExtractionTransport:
    """Credential-free deterministic transport for extraction/evaluation tests."""

    def __init__(self, responses_by_media_uri: Mapping[str, str | Mapping[str, Any]]) -> None:
        self._responses = dict(responses_by_media_uri)
        self.calls: list[ExtractionPrompt] = []

    def __call__(self, prompt: ExtractionPrompt) -> str | Mapping[str, Any]:
        self.calls.append(prompt)
        if prompt.media_uri not in self._responses:
            raise KeyError("no fixture response registered for media URI")
        return self._responses[prompt.media_uri]
