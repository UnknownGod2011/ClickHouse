# Production ingestion composition

TakeKeeper's production ingest HTTP boundary is intentionally assembled from environment configuration rather than command-line secrets. `takekeeper.production_ingest` creates the trusted ClickHouse application client, Google Gen AI / Vertex AI client, governed extractor, append-only provenance store, schema-gated ingest service, bearer identity adapter, and `IngestHttpApp`.

The factory calls `SchemaGatedIngestService.start()` before returning the deployment. If the extraction schema is missing, incompatible, or unreachable, construction fails and no WSGI application is returned as ready.

## Install provider extras

```bash
pip install -e '.[clickhouse,gemini]'
```

A WSGI server remains a deployment choice rather than a TakeKeeper core dependency. For example, an operator may install Gunicorn separately and use the application factory:

```bash
gunicorn 'takekeeper.production_ingest:create_wsgi_app_from_env()' \
  --bind "0.0.0.0:${PORT:-8080}"
```

Do not put ClickHouse passwords, Gemini API keys, or ingest bearer tokens in command-line arguments. Supply them through the deployment environment/secret manager.

## Required configuration

Common variables:

| Variable | Purpose |
| --- | --- |
| `TAKEKEEPER_CLICKHOUSE_HOST` | Trusted application-write ClickHouse endpoint. |
| `TAKEKEEPER_CLICKHOUSE_PORT` | Optional; defaults to `8443`. |
| `TAKEKEEPER_CLICKHOUSE_USERNAME` | Optional; defaults to `default`. Use a dedicated application identity. |
| `TAKEKEEPER_CLICKHOUSE_PASSWORD` | Required non-empty application credential. |
| `TAKEKEEPER_CLICKHOUSE_DATABASE` | Optional; defaults to `takekeeper`. |
| `TAKEKEEPER_CLICKHOUSE_SECURE` | Optional strict boolean; defaults to `true`. |
| `TAKEKEEPER_GEMINI_MODE` | `vertex` (default) or `developer`. |
| `TAKEKEEPER_GEMINI_MODEL` | Operator-selected model ID. No model is silently chosen by the factory. |
| `TAKEKEEPER_EXTRACTOR_VERSION` | Operator/deployment provenance label. |
| `TAKEKEEPER_PROMPT_SCHEMA_VERSION` | Optional; defaults to `takekeeper-extraction-v1`. |
| `TAKEKEEPER_INGEST_BEARER_TOKEN` | Required bearer secret, minimum 32 characters. |
| `TAKEKEEPER_INGEST_ACTOR_ID` | Optional stable server-owned actor label; defaults to `ingest-api`. |

Vertex AI mode additionally requires:

```text
TAKEKEEPER_GOOGLE_CLOUD_PROJECT
TAKEKEEPER_GOOGLE_CLOUD_LOCATION
```

Authentication is delegated to Google Application Default Credentials. `TAKEKEEPER_GEMINI_API_KEY` must not be set in Vertex mode.

Gemini Developer API mode instead requires:

```text
TAKEKEEPER_GEMINI_MODE=developer
TAKEKEEPER_GEMINI_API_KEY=<secret>
```

Developer mode rejects Vertex project/location variables so an ambiguous provider configuration cannot silently select a different authority path.

## Example: ClickHouse Cloud + Vertex AI

```text
TAKEKEEPER_CLICKHOUSE_HOST=<service-host>
TAKEKEEPER_CLICKHOUSE_PORT=8443
TAKEKEEPER_CLICKHOUSE_USERNAME=takekeeper_ingest
TAKEKEEPER_CLICKHOUSE_PASSWORD=<secret>
TAKEKEEPER_CLICKHOUSE_DATABASE=takekeeper
TAKEKEEPER_CLICKHOUSE_SECURE=true

TAKEKEEPER_GEMINI_MODE=vertex
TAKEKEEPER_GEMINI_MODEL=<approved-model-id>
TAKEKEEPER_GOOGLE_CLOUD_PROJECT=<project-id>
TAKEKEEPER_GOOGLE_CLOUD_LOCATION=<region>
TAKEKEEPER_EXTRACTOR_VERSION=<deployment-version>

TAKEKEEPER_INGEST_BEARER_TOKEN=<random-secret-at-least-32-characters>
TAKEKEEPER_INGEST_ACTOR_ID=production-ingest
```

ClickHouse's current Python integration uses `clickhouse_connect.get_client(...)`; its ClickHouse Cloud example uses the secure HTTPS interface on port `8443`. TakeKeeper defaults to that secure port but lets self-hosted deployments override port/secure explicitly.

## Readiness contract

The composition sequence is:

1. parse and structurally validate environment configuration;
2. construct the trusted ClickHouse application client;
3. construct the Google Gen AI / Vertex client;
4. construct the governed Gemini extraction transport and extractor;
5. construct `ClickHouseExtractionProvenanceStore` using the same ClickHouse application client;
6. construct `SchemaGatedIngestService` and authenticated `IngestHttpApp`;
7. execute the bounded `system.columns` extraction-schema preflight;
8. return the deployment only after the service becomes ready.

There is no alternate startup path that marks ingestion ready before schema validation. `/healthz` may still be healthy while `/readyz` is unavailable, which is intentional.

## Secret behavior

`ProductionIngestConfig` marks ClickHouse passwords, Gemini API keys, and ingest bearer tokens as `repr=False`. Composition exceptions are coarse and provider exception context is suppressed at the trust boundary because SDK/driver messages can contain endpoints or connection details.

Configuration errors name only the affected environment variable; they do not echo its value. HTTP error behavior remains the bounded contract in `INGEST_API.md`.

## Property profiles

HTTP callers can select only server-owned property profiles. The environment-only WSGI factory currently exposes the built-in `hero` profile. Embedders that need production-specific mappings can call `build_ingest_deployment_from_env(..., property_profiles=...)` and inject validated `PropertySpec` sequences from trusted deployment code/configuration.

Do not accept a property registry directly from an ingest request. Entity/property/value policy is part of the trusted extraction boundary.

## Privilege separation

Use three distinct authorities:

- **trusted ClickHouse application credential** — schema metadata reads plus the narrowly required TakeKeeper writes;
- **read-only ClickHouse MCP credential** — analytical agent queries only, with write access disabled;
- **Google model credential** — Gemini/Vertex extraction only.

The production composition module does not construct or reuse the MCP credential.

## Local/self-hosted notes

A production factory intentionally requires a non-empty ClickHouse password. A passwordless local ClickHouse instance is suitable for isolated development, but should be composed directly in development code/tests rather than weakening the production factory's credential requirement.

For an explicitly secured self-hosted HTTP endpoint, override `TAKEKEEPER_CLICKHOUSE_PORT` and `TAKEKEEPER_CLICKHOUSE_SECURE` to match that deployment.

## Validation

Credential-free regression coverage is in `tests/test_production_ingest.py`. It verifies:

- schema preflight runs during composition and readiness opens only afterward;
- an old extraction schema fails startup closed;
- missing configuration fails before any provider factory is called;
- secret values do not appear in config `repr()`;
- provider failure messages do not become the public startup error;
- Vertex and Developer API configuration cannot be mixed;
- short ingest bearer secrets are rejected without echoing the value.

Live provider behavior still requires an authorized ClickHouse/GCP environment and must not be inferred from these fakes.

## References

- ClickHouse Python integration: https://clickhouse.com/integrations/python
- ClickHouse Connect: https://github.com/ClickHouse/clickhouse-connect
- Google Gen AI Python SDK: https://googleapis.github.io/python-genai/
- Gemini video understanding: https://ai.google.dev/gemini-api/docs/video-understanding
