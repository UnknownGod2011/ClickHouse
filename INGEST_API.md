# TakeKeeper production ingest API

TakeKeeper's production extraction ingress is a narrow WSGI application around `SchemaGatedIngestService`. It is intentionally separate from ClickHouse MCP: MCP remains a bounded read-only agent surface, while ingest uses the trusted application ClickHouse client and governed Gemini extraction path.

## Lifecycle

1. Construct the trusted ClickHouse client, governed extractor, and extraction provenance store.
2. Construct `SchemaGatedIngestService` with those dependencies.
3. Call `service.start()` before declaring the deployment ready. This performs the bounded extraction-schema preflight and fails closed when migrations are missing or ClickHouse cannot be safely checked.
4. Construct `IngestHttpApp` with an identity provider, server-owned property profiles, and server-owned extractor model/version.
5. Serve the WSGI app with a production WSGI server or framework adapter.
6. On deployment shutdown or a failed revalidation, call `service.close()` so ingestion is explicitly closed.

The HTTP app never performs migrations and should not be given schema-migration privileges.

## Endpoints

### `GET /healthz`

Process liveness only. It does not query ClickHouse and returns:

```json
{"status":"ok"}
```

Use this for container/process liveness probes. A healthy process may still be intentionally unable to ingest.

### `GET /readyz`

Coarse ingestion readiness only. It returns HTTP 200 when schema-gated ingestion is open and HTTP 503 otherwise. The payload contains only:

```json
{"status":"ready|not_ready","schema_checked":true}
```

No ClickHouse host, database, schema diff, provider error, media identity, tenant identity, or credential detail is exposed.

### `POST /v1/ingest`

Authenticated trusted-take ingestion. The bearer identity adapter is invoked before request bytes are read. The default helper used elsewhere in TakeKeeper is `StaticBearerIdentityProvider`, but deployments can supply another implementation of the same identity protocol.

Example bounded request shape:

```json
{
  "production_id": "prod-1",
  "scene_id": "scene-7",
  "take_id": "take-3",
  "media_uri": "gs://private-bucket/prod-1/scene-7/take-3.mp4",
  "duration_ms": 12500,
  "property_profile": "continuity-v1",
  "media_mime_type": "video/mp4",
  "media_content_sha256": "<64 lowercase hex characters>",
  "media_byte_size": 1024
}
```

Successful ingestion returns only the run and trusted scope identifiers plus observation count. It does not echo the media URI, content hash, byte size, model response, provider details, or credentials.

## Server-owned policy

Clients cannot choose:

- Gemini/Vertex model identity;
- extractor implementation version;
- prompt schema version;
- arbitrary `PropertySpec` definitions;
- arbitrary allowed values for continuity properties.

Instead, the deployment registers named property profiles when constructing `IngestHttpApp`. A request may select only one configured profile name. This keeps configurable production mappings possible without allowing an HTTP caller to redefine the extraction trust boundary.

## Request bounds and failure behavior

- JSON bodies are capped at 32 KiB.
- production/scene/take/profile identifiers are length bounded and reject control characters.
- media locators are capped at 4096 characters.
- duration is a positive integer capped at 24 hours.
- unknown JSON fields fail closed.
- media MIME/hash/byte-size validation is delegated to the canonical `TakeExtractionRequest` domain boundary.
- requests received while ingestion is closed return HTTP 503 before the extractor or provenance store can run.
- authentication failures return a fixed bounded response; supplied tokens are never echoed.
- unexpected provider/runtime exceptions return a fixed `internal server error` response without copying exception text.

## Deployment guidance

Keep the ingress private where possible (for example behind an authenticated internal service boundary). TLS termination, request-rate limits, network policy, workload identity, and secret injection belong to the deployment platform rather than this dependency-free WSGI core.

For ClickHouse Cloud or self-hosted ClickHouse, the application connection should receive only the tables/system metadata permissions needed for normal TakeKeeper operation. Apply migrations out of band using a separately privileged administrative identity. Do not reuse ClickHouse MCP credentials for writes.

For private media, prefer immutable/versioned objects and trusted byte hashing. Signed media locators and content hashes should not be logged by reverse proxies or application middleware.

## Credential-free tests

`tests/test_ingest_api.py` exercises liveness/readiness separation, authentication-before-body-read, server-owned model/property policy, body bounds, unready HTTP 503 behavior, canonical media provenance validation, and fixed error redaction without calling ClickHouse, Gemini, object storage, or GitHub Actions.
