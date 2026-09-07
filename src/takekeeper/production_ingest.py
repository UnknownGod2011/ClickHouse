from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .extraction import HERO_PROPERTY_REGISTRY, GovernedMultimodalExtractor, PropertySpec
from .extraction_store import ClickHouseExtractionProvenanceStore
from .google_genai_transport import (
    GoogleGenAIExtractionTransport,
    GoogleGenAITransportConfig,
    create_google_genai_client,
)
from .google_identity import GoogleOidcIdentityProvider, IapIdentityProvider
from .ingest_api import IngestHttpApp
from .ingest_runtime import SchemaGatedIngestService
from .review_api import ReviewerIdentityProvider, StaticBearerIdentityProvider

ClickHouseClientFactory = Callable[..., Any]
GenAIClientFactory = Callable[..., Any]
IdentityProviderFactory = Callable[["ProductionIngestConfig"], tuple[ReviewerIdentityProvider, str]]


class ProductionIngestConfigurationError(RuntimeError):
    """Production ingest configuration is absent or structurally invalid.

    Messages identify only configuration field names. Secret values are never included.
    """


class ProductionIngestStartupError(RuntimeError):
    """Production ingest could not safely become ready."""


@dataclass(frozen=True, slots=True)
class ProductionIngestConfig:
    clickhouse_host: str
    clickhouse_port: int
    clickhouse_username: str
    clickhouse_password: str = field(repr=False)
    clickhouse_database: str = "takekeeper"
    clickhouse_secure: bool = True
    gemini_mode: str = "vertex"
    gemini_model: str = ""
    gemini_api_key: str | None = field(default=None, repr=False)
    google_cloud_project: str | None = None
    google_cloud_location: str | None = None
    extractor_version: str = ""
    prompt_schema_version: str = "takekeeper-extraction-v1"
    ingest_identity_mode: str = "static"
    ingest_bearer_token: str | None = field(default=None, repr=False)
    ingest_actor_id: str = "ingest-api"
    ingest_expected_audience: str | None = None

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> "ProductionIngestConfig":
        env = os.environ if environ is None else environ
        host = _required(env, "TAKEKEEPER_CLICKHOUSE_HOST", max_length=255)
        username = _optional(env, "TAKEKEEPER_CLICKHOUSE_USERNAME", "default", max_length=128)
        password = _required_secret(env, "TAKEKEEPER_CLICKHOUSE_PASSWORD")
        database = _optional(env, "TAKEKEEPER_CLICKHOUSE_DATABASE", "takekeeper", max_length=128)
        if not database.replace("_", "").isalnum():
            raise ProductionIngestConfigurationError("invalid TAKEKEEPER_CLICKHOUSE_DATABASE")
        port = _positive_int(env, "TAKEKEEPER_CLICKHOUSE_PORT", 8443, maximum=65535)
        secure = _boolean(env, "TAKEKEEPER_CLICKHOUSE_SECURE", True)

        mode = _optional(env, "TAKEKEEPER_GEMINI_MODE", "vertex", max_length=32).lower()
        if mode not in {"vertex", "developer"}:
            raise ProductionIngestConfigurationError("invalid TAKEKEEPER_GEMINI_MODE")
        model = _required(env, "TAKEKEEPER_GEMINI_MODEL", max_length=160)
        extractor_version = _required(env, "TAKEKEEPER_EXTRACTOR_VERSION", max_length=160)
        prompt_schema_version = _optional(
            env,
            "TAKEKEEPER_PROMPT_SCHEMA_VERSION",
            "takekeeper-extraction-v1",
            max_length=160,
        )

        api_key: str | None = None
        project: str | None = None
        location: str | None = None
        if mode == "vertex":
            project = _required(env, "TAKEKEEPER_GOOGLE_CLOUD_PROJECT", max_length=256)
            location = _required(env, "TAKEKEEPER_GOOGLE_CLOUD_LOCATION", max_length=128)
            if env.get("TAKEKEEPER_GEMINI_API_KEY"):
                raise ProductionIngestConfigurationError(
                    "TAKEKEEPER_GEMINI_API_KEY must not be set in vertex mode"
                )
        else:
            api_key = _required_secret(env, "TAKEKEEPER_GEMINI_API_KEY")
            if env.get("TAKEKEEPER_GOOGLE_CLOUD_PROJECT") or env.get("TAKEKEEPER_GOOGLE_CLOUD_LOCATION"):
                raise ProductionIngestConfigurationError(
                    "Vertex project/location must not be set in developer mode"
                )

        identity_mode = _optional(env, "TAKEKEEPER_INGEST_IDENTITY_MODE", "static", max_length=32).lower()
        if identity_mode not in {"static", "google_oidc", "iap"}:
            raise ProductionIngestConfigurationError("invalid TAKEKEEPER_INGEST_IDENTITY_MODE")

        bearer: str | None = None
        actor = _optional(env, "TAKEKEEPER_INGEST_ACTOR_ID", "ingest-api", max_length=128)
        audience: str | None = None
        if identity_mode == "static":
            bearer = _required_secret(env, "TAKEKEEPER_INGEST_BEARER_TOKEN", minimum_length=32)
            if env.get("TAKEKEEPER_INGEST_EXPECTED_AUDIENCE"):
                raise ProductionIngestConfigurationError(
                    "TAKEKEEPER_INGEST_EXPECTED_AUDIENCE must not be set in static identity mode"
                )
        else:
            audience = _required(env, "TAKEKEEPER_INGEST_EXPECTED_AUDIENCE", max_length=2_048)
            if env.get("TAKEKEEPER_INGEST_BEARER_TOKEN"):
                raise ProductionIngestConfigurationError(
                    "TAKEKEEPER_INGEST_BEARER_TOKEN must not be set in Google identity mode"
                )
            if env.get("TAKEKEEPER_INGEST_ACTOR_ID"):
                raise ProductionIngestConfigurationError(
                    "TAKEKEEPER_INGEST_ACTOR_ID must not be set in Google identity mode"
                )

        return cls(
            clickhouse_host=host,
            clickhouse_port=port,
            clickhouse_username=username,
            clickhouse_password=password,
            clickhouse_database=database,
            clickhouse_secure=secure,
            gemini_mode=mode,
            gemini_model=model,
            gemini_api_key=api_key,
            google_cloud_project=project,
            google_cloud_location=location,
            extractor_version=extractor_version,
            prompt_schema_version=prompt_schema_version,
            ingest_identity_mode=identity_mode,
            ingest_bearer_token=bearer,
            ingest_actor_id=actor,
            ingest_expected_audience=audience,
        )


@dataclass(frozen=True, slots=True)
class ProductionIngestDeployment:
    app: IngestHttpApp
    service: SchemaGatedIngestService


def _default_clickhouse_client_factory(**kwargs: Any) -> Any:
    try:
        import clickhouse_connect
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise ProductionIngestStartupError(
            "clickhouse-connect is required for production ingestion; install the 'clickhouse' extra"
        ) from exc
    return clickhouse_connect.get_client(**kwargs)


def _default_identity_provider_factory(
    config: ProductionIngestConfig,
) -> tuple[ReviewerIdentityProvider, str]:
    if config.ingest_identity_mode == "static":
        if config.ingest_bearer_token is None:
            raise ProductionIngestConfigurationError("missing TAKEKEEPER_INGEST_BEARER_TOKEN")
        return (
            StaticBearerIdentityProvider({config.ingest_bearer_token: config.ingest_actor_id}),
            "HTTP_AUTHORIZATION",
        )
    if config.ingest_expected_audience is None:
        raise ProductionIngestConfigurationError("missing TAKEKEEPER_INGEST_EXPECTED_AUDIENCE")
    if config.ingest_identity_mode == "google_oidc":
        return GoogleOidcIdentityProvider(config.ingest_expected_audience), "HTTP_AUTHORIZATION"
    if config.ingest_identity_mode == "iap":
        return IapIdentityProvider(config.ingest_expected_audience), "HTTP_X_GOOG_IAP_JWT_ASSERTION"
    raise ProductionIngestConfigurationError("invalid TAKEKEEPER_INGEST_IDENTITY_MODE")


def build_ingest_deployment_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    clickhouse_client_factory: ClickHouseClientFactory | None = None,
    genai_client_factory: GenAIClientFactory | None = None,
    identity_provider_factory: IdentityProviderFactory | None = None,
    property_profiles: Mapping[str, Sequence[PropertySpec]] | None = None,
) -> ProductionIngestDeployment:
    """Compose and open the trusted production ingestion stack from environment config.

    No secret is accepted through argv. The returned app cannot report ready until the same
    trusted ClickHouse client used for provenance persistence has passed schema preflight.
    Factories and server-owned profiles are injectable so composition can be tested or
    customized without giving HTTP callers authority to define extraction policy.
    """

    config = ProductionIngestConfig.from_environ(environ)
    clickhouse_factory = clickhouse_client_factory or _default_clickhouse_client_factory
    google_factory = genai_client_factory or create_google_genai_client
    identity_factory = identity_provider_factory or _default_identity_provider_factory
    profiles = {"hero": HERO_PROPERTY_REGISTRY} if property_profiles is None else property_profiles

    try:
        clickhouse_client = clickhouse_factory(
            host=config.clickhouse_host,
            port=config.clickhouse_port,
            username=config.clickhouse_username,
            password=config.clickhouse_password,
            database=config.clickhouse_database,
            secure=config.clickhouse_secure,
        )
        genai_client = google_factory(
            api_key=config.gemini_api_key,
            vertex_ai=config.gemini_mode == "vertex",
            project=config.google_cloud_project,
            location=config.google_cloud_location,
        )
        transport = GoogleGenAIExtractionTransport(
            genai_client,
            GoogleGenAITransportConfig(model=config.gemini_model),
        )
        extractor = GovernedMultimodalExtractor(transport)
        provenance_store = ClickHouseExtractionProvenanceStore(
            clickhouse_client,
            database=config.clickhouse_database,
        )
        service = SchemaGatedIngestService(
            clickhouse_client=clickhouse_client,
            extractor=extractor,
            provenance_store=provenance_store,
            database=config.clickhouse_database,
        )
        identity, credential_environ_key = identity_factory(config)
        app = IngestHttpApp(
            service,
            identity,
            property_profiles=profiles,
            extractor_model=config.gemini_model,
            extractor_version=config.extractor_version,
            prompt_schema_version=config.prompt_schema_version,
            credential_environ_key=credential_environ_key,
        )
        # This is deliberately last. Construction alone can never make /readyz return 200.
        service.start()
        return ProductionIngestDeployment(app=app, service=service)
    except ProductionIngestConfigurationError:
        raise
    except Exception:
        # Suppress provider exception context because SDK/driver/auth errors can contain tokens,
        # endpoints, connection strings, or other details that must not enter startup logs.
        raise ProductionIngestStartupError(
            "TakeKeeper production ingestion could not start safely."
        ) from None


def create_wsgi_app_from_env(environ: Mapping[str, str] | None = None) -> IngestHttpApp:
    """WSGI-server factory for Cloud Run or self-hosted deployment."""

    return build_ingest_deployment_from_env(environ).app


def _required(
    env: Mapping[str, str],
    name: str,
    *,
    max_length: int,
) -> str:
    value = env.get(name)
    if value is None or not isinstance(value, str) or not value.strip():
        raise ProductionIngestConfigurationError(f"missing {name}")
    cleaned = value.strip()
    if len(cleaned) > max_length or any(ord(ch) < 32 for ch in cleaned):
        raise ProductionIngestConfigurationError(f"invalid {name}")
    return cleaned


def _optional(
    env: Mapping[str, str],
    name: str,
    default: str,
    *,
    max_length: int,
) -> str:
    value = env.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise ProductionIngestConfigurationError(f"invalid {name}")
    cleaned = value.strip()
    if len(cleaned) > max_length or any(ord(ch) < 32 for ch in cleaned):
        raise ProductionIngestConfigurationError(f"invalid {name}")
    return cleaned


def _required_secret(
    env: Mapping[str, str],
    name: str,
    *,
    minimum_length: int = 1,
) -> str:
    value = env.get(name)
    if not isinstance(value, str) or len(value) < minimum_length:
        raise ProductionIngestConfigurationError(f"missing or invalid {name}")
    if any(ord(ch) < 32 for ch in value):
        raise ProductionIngestConfigurationError(f"missing or invalid {name}")
    return value


def _positive_int(
    env: Mapping[str, str],
    name: str,
    default: int,
    *,
    maximum: int,
) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ProductionIngestConfigurationError(f"invalid {name}") from exc
    if not 0 < value <= maximum:
        raise ProductionIngestConfigurationError(f"invalid {name}")
    return value


def _boolean(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ProductionIngestConfigurationError(f"invalid {name}")
