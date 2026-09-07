from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .extraction import ExtractionPrompt
from .media_provenance import MediaProvenanceError, resolve_video_mime_type


class GoogleGenAITransportError(RuntimeError):
    """Raised when the Google Gen AI transport cannot safely produce JSON text."""


class GenerateContentModels(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: list[Any],
        config: Mapping[str, Any],
    ) -> Any: ...


class GoogleGenAIClient(Protocol):
    models: GenerateContentModels


PartFactory = Callable[[str, str], Any]


@dataclass(frozen=True, slots=True)
class GoogleGenAITransportConfig:
    model: str
    temperature: float = 0.0
    max_output_tokens: int = 4096

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model must be non-empty")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")


def _default_part_factory(uri: str, mime_type: str) -> Any:
    try:
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - exercised only with optional dependency absent
        raise GoogleGenAITransportError(
            "google-genai is not installed; install TakeKeeper with the 'gemini' extra"
        ) from exc
    return types.Part.from_uri(file_uri=uri, mime_type=mime_type)


def _supported_video_mime(uri: str, explicit_mime_type: str | None = None) -> str:
    """Resolve trusted video MIME metadata through the shared provenance boundary.

    Keeping URI validation and MIME allow-listing in one module prevents the Gemini path
    from drifting away from ingest provenance rules. Explicit MIME metadata is trusted
    application input and enables extensionless signed/object URLs. Suffix conflicts fail
    closed.
    """

    try:
        return resolve_video_mime_type(uri, explicit_mime_type)
    except MediaProvenanceError as exc:
        raise GoogleGenAITransportError(str(exc)) from exc


def _google_json_schema(value: Any) -> Any:
    """Remove TakeKeeper-only annotations before sending JSON Schema to Google.

    Validation still happens again inside GovernedMultimodalExtractor. This sanitizer only
    prevents provider-side schema parsers from seeing private x-* annotations.
    """

    if isinstance(value, Mapping):
        return {
            key: _google_json_schema(item)
            for key, item in value.items()
            if not str(key).startswith("x-")
        }
    if isinstance(value, list):
        return [_google_json_schema(item) for item in value]
    if isinstance(value, tuple):
        return [_google_json_schema(item) for item in value]
    return value


class GoogleGenAIExtractionTransport:
    """Concrete Google Gen AI / Vertex AI transport for TakeKeeper extraction.

    The transport has intentionally narrow authority: one trusted media URI plus one
    TakeKeeper-built prompt go to one configured model. It does not accept tools,
    function calls, arbitrary provider configuration, or model-selected media.
    """

    def __init__(
        self,
        client: GoogleGenAIClient,
        config: GoogleGenAITransportConfig,
        *,
        part_factory: PartFactory = _default_part_factory,
    ) -> None:
        self._client = client
        self._config = config
        self._part_factory = part_factory

    @property
    def model(self) -> str:
        return self._config.model

    def __call__(self, prompt: ExtractionPrompt) -> str:
        mime_type = _supported_video_mime(prompt.media_uri, prompt.media_mime_type)
        media_part = self._part_factory(prompt.media_uri, mime_type)
        provider_schema = _google_json_schema(prompt.response_schema)
        config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_json_schema": provider_schema,
            "temperature": self._config.temperature,
            "max_output_tokens": self._config.max_output_tokens,
        }
        try:
            response = self._client.models.generate_content(
                model=self._config.model,
                contents=[media_part, prompt.text],
                config=config,
            )
        except Exception as exc:
            raise GoogleGenAITransportError("Google Gen AI generate_content failed") from exc

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise GoogleGenAITransportError("Google Gen AI response did not contain JSON text")
        return text


def create_google_genai_client(
    *,
    api_key: str | None = None,
    vertex_ai: bool = False,
    project: str | None = None,
    location: str | None = None,
) -> GoogleGenAIClient:
    """Create the optional Google SDK client without making credentials mandatory at import time.

    Gemini Developer API mode may use an explicit API key or the SDK's normal environment
    discovery. Vertex AI mode requires a project and location and delegates authentication to
    Google Application Default Credentials.
    """

    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise GoogleGenAITransportError(
            "google-genai is not installed; install TakeKeeper with the 'gemini' extra"
        ) from exc

    if vertex_ai:
        if not project or not project.strip():
            raise ValueError("project is required for Vertex AI mode")
        if not location or not location.strip():
            raise ValueError("location is required for Vertex AI mode")
        return genai.Client(vertexai=True, project=project, location=location)

    if api_key is not None and not api_key.strip():
        raise ValueError("api_key must be non-empty when provided")
    return genai.Client(api_key=api_key) if api_key is not None else genai.Client()
