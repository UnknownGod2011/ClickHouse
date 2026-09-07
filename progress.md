# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed Gemini/Vertex multimodal extraction, strict continuity projection, objective multimodal benchmarks, deterministic synthetic media, trusted media MIME/hash/byte provenance, immutable same-run retry identity, bounded schema readiness, schema-gated ingestion, an authenticated WSGI ingest API, and now a secret-safe environment-driven production composition layer.

This run closed the deployment-composition gap around `IngestHttpApp`. A production process can now construct the trusted ClickHouse application client, Gemini/Vertex client, governed extractor, ClickHouse provenance store, schema-gated ingest service, bearer identity adapter, and WSGI app from bounded environment configuration. The factory does not return a ready deployment until the extraction schema preflight succeeds.

## Inspected this run

- Read this `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and the connected GitHub account has push/admin permission.
- Inspected `src/takekeeper/ingest_api.py`, `ingest_runtime.py`, `extraction.py`, `google_genai_transport.py`, `extraction_store.py`, `schema_preflight.py`, `review_api.py`, `__init__.py`, `pyproject.toml`, `tests/test_ingest_api.py`, and `README.md`.
- Confirmed the existing ingest boundary already separates liveness/readiness, authenticates before reading request bytes, keeps model/property policy server-owned, and routes ingestion only through `SchemaGatedIngestService`.
- Confirmed `create_google_genai_client(...)` supports Gemini Developer API and Vertex AI while deferring optional SDK import until runtime.
- Confirmed `ClickHouseExtractionProvenanceStore` and schema preflight use the trusted application client and remain separate from read-only MCP.
- Checked current official ClickHouse Python guidance: `clickhouse_connect.get_client(...)` remains the documented Python path and ClickHouse Cloud examples use secure port 8443.
- Checked current Google Gen AI SDK documentation for the server-side API-key vs Vertex project/location client split.

## Exact changes made this run

### Environment-driven production composition

Added `src/takekeeper/production_ingest.py` with:

- `ProductionIngestConfig.from_environ(...)`;
- `ProductionIngestConfigurationError` for bounded field-name-only configuration failures;
- `ProductionIngestStartupError` for coarse startup failures;
- `ProductionIngestDeployment` containing the app and schema-gated service;
- `build_ingest_deployment_from_env(...)` for injectable/testable composition;
- `create_wsgi_app_from_env(...)` for WSGI server factories.

The composition path constructs, in order:

1. trusted ClickHouse application client;
2. Google Gen AI / Vertex client;
3. `GoogleGenAIExtractionTransport`;
4. `GovernedMultimodalExtractor`;
5. `ClickHouseExtractionProvenanceStore`;
6. `SchemaGatedIngestService`;
7. `StaticBearerIdentityProvider`;
8. `IngestHttpApp`;
9. schema readiness via `service.start()`.

The deployment is returned only after step 9 succeeds.

### Fail-closed configuration

Production composition now requires bounded environment configuration for ClickHouse, provider mode/model, extractor version, and ingest authentication.

- ClickHouse Cloud-oriented defaults are secure transport with port 8443; deployments may explicitly override port/secure for secured self-hosted endpoints.
- Vertex mode requires project/location and rejects a TakeKeeper Gemini API-key variable.
- Developer API mode requires a server-side API key and rejects Vertex project/location variables.
- The production factory requires a non-empty ClickHouse password and an ingest bearer token of at least 32 characters.
- No model ID is silently selected by the factory; `TAKEKEEPER_GEMINI_MODEL` is operator-owned deployment configuration.

### Secret handling hardening

During review, found that a normal dataclass `repr()` would expose parsed passwords/API keys/tokens if deployment config were logged. Fixed this before handoff:

- ClickHouse password, Gemini API key, and ingest bearer token fields are `repr=False`.
- Provider/driver exceptions are converted at the composition trust boundary to a fixed `ProductionIngestStartupError` and exception context is suppressed with `from None`, because SDK/driver errors can contain endpoints or connection details.
- Configuration errors name environment variables only and never echo their values.
- `ProductionIngestDeployment` does not retain/expose the parsed config object; it contains only the app and service.

### Server-owned property profiles

`build_ingest_deployment_from_env(..., property_profiles=...)` accepts trusted deployment-owned `PropertySpec` mappings. HTTP callers still cannot define schemas/values; they can only select registered profile names. The environment-only WSGI factory defaults to the built-in `hero` profile.

### Regression coverage

Added `tests/test_production_ingest.py` covering:

- successful Vertex-mode composition;
- exactly two schema-preflight metadata queries before readiness opens;
- schema drift failing startup closed;
- missing configuration failing before provider factories are called;
- secret values absent from `ProductionIngestConfig.__repr__`;
- provider failure messages not appearing in the public startup error;
- Vertex/Developer configuration separation;
- short bearer-token rejection without value echo.

The schema fake never permits inserts, proving composition/preflight itself is metadata-read-only.

### Public API and documentation

- Exported production composition classes/functions from `takekeeper.__init__`.
- Added `PRODUCTION_INGEST.md` with environment variables, ClickHouse Cloud/Vertex example, WSGI composition, startup ordering, secret behavior, server-owned profile injection, privilege separation, and local/self-hosted notes.
- Updated `README.md` so repository map/current capabilities/production gates include schema-gated HTTP ingestion and production composition instead of the older stale ingest backlog.
- Recorded current official ClickHouse Python and Google Gen AI SDK references in the documentation.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No ClickHouse, Gemini/Vertex, object-storage, MCP, or production-media credential was used.
- No cloud resource or production media was accessed or modified.
- No destructive ClickHouse operation was introduced.
- Official ClickHouse MCP remains read-only and separately permissioned from application writes.

## Validation / results

Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.

Implementation commits before this handoff update:

- `a222a15812fdc8787200ab3bdc4680007652597d` — initial secret-safe production ingest composition;
- `a43e5646bb0acefcbcc99b2de5c7125c447edeb2` — redact production ingest secrets from config repr;
- `b69dee4c3ea2d12b06285e9e599a48f89264d667` — production composition/security regression coverage;
- `a769fdffa0fc9cd34fe80fc905fd00a798a6ed8d` — public production composition exports;
- `ec1a8f742fa0d310f6f0812d23660545b75d149d` — hardened startup exception handling and server-owned profile injection;
- `dd5048c1bf2d3cb1d2d7c55470fb22a935cbcb2f` — production ingest deployment documentation;
- `609b68346b7e32665f58ce075dbd45961b7f7acb` — coherent README production-ingest update.

Structural review performed after writing:

- re-fetched `src/takekeeper/production_ingest.py` from `main` and verified secrets are `repr=False`;
- verified provider exceptions are suppressed at the startup boundary;
- verified `service.start()` is the final operation before a deployment is returned;
- verified ClickHouse schema preflight and persistence receive the same trusted application client;
- verified MCP construction/credentials are absent from this composition path;
- re-fetched `tests/test_production_ingest.py` from `main` and checked the intended fail-closed/secret-redaction cases are committed.

Executable validation attempt:

```text
git clone --depth 1 https://github.com/UnknownGod2011/ClickHouse.git /tmp/takekeeper-check
PYTHONPATH=src python -m unittest \
  tests.test_production_ingest \
  tests.test_ingest_api \
  tests.test_ingest_runtime \
  tests.test_schema_preflight -v
```

The execution container failed at clone with `Could not resolve host: github.com`, so Python never started. This is an environment/network blocker, not a test result. I therefore do **not** claim the new or existing suites pass here. GitHub Actions were deliberately not used as a workaround.

No live Gemini/Vertex request, real ClickHouse request, official MCP session, ffmpeg rendering, or production-media operation was performed.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for application writes, migrations, or credential handling.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Agent-facing MCP access remains bounded; arbitrary agent SQL is not exposed.
4. Production/scene/take scope is trusted application metadata and never model output.
5. Only configured entity/property pairs and registry values can enter governed extraction.
6. Machine confidence is not human confirmation.
7. Extraction provenance is append-only; reprocessing creates a new run. ClickHouse may reconcile only an identical retry of the same run.
8. Continuity projection is stricter than extraction persistence; uncertain evidence cannot become current continuity state.
9. Missing/abstaining projected evidence becomes `insufficient_evidence`, never a mismatch.
10. Google structured output is a formatting aid, not a trust boundary; responses are locally validated.
11. Locator fingerprints and content hashes are distinct provenance concepts; locator hashing is never represented as byte identity.
12. Explicit MIME type, content SHA-256, byte size, production scope, model identity, and media identity are trusted application metadata and cannot be supplied by Gemini.
13. MIME/suffix disagreement fails closed.
14. Signed/private media URI values and content hashes must not be copied into prompts, logs, benchmark reports, or operator-visible error strings unless explicitly required by a trusted administrative surface.
15. A persisted same-`run_id` retry must match locator fingerprint, trusted MIME metadata, content SHA-256, byte size, duration, scope, extractor identity, and prompt schema before reconciliation can continue.
16. Application/schema compatibility must be checked before enabling extraction ingestion; the first production take must never serve as the migration detector.
17. Schema readiness is metadata-read-only and must not implicitly grant migration privileges to the normal application connection.
18. Production extraction ingress starts closed and must route through `SchemaGatedIngestService`.
19. Revalidation revokes readiness before checking, so a failed schema recheck always leaves ingestion closed.
20. Network callers may select only server-configured property profiles; they cannot define model identity, prompt schema, property registries, SQL, or migrations.
21. Liveness and ingestion readiness are separate contracts.
22. Production ingest HTTP errors are bounded and must not copy provider exception detail, media provenance, or credentials into responses.
23. Production composition must obtain secrets from environment/secret injection rather than argv.
24. Production composition must not expose secret fields through dataclass reprs or chained provider errors.
25. Vertex and Developer API authority configuration must be mutually exclusive in the production factory.
26. A production deployment object is returned only after the trusted ClickHouse extraction-schema preflight succeeds.

## Gates

- **Gate A — live ClickHouse:** schema readiness is implemented/enforced through production composition; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review/schema-readiness/ingest-bootstrap/HTTP/composition paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review/ingest, immutable retry identity, metadata-only preflight, server-owned extraction policy, secret-safe composition, and startup gating are implemented structurally; live RBAC/workload-identity/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME/byte identity, schema support, persistence, rollout-skew detection, HTTP ingress, and production composition exist; live execution remains pending.

## Blockers / unknowns

1. The execution container cannot currently resolve `github.com`, so a normal checkout and Python test execution remain unavailable from this run.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` video/schema behavior, latency, token usage, and provider failure modes remain unmeasured.
6. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql` before updated persistence writes; startup preflight detects the skew and refuses ingestion.
7. Local SHA-256 hashing cannot prove immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/staged objects or use object generation/version guarantees.
8. A real ClickHouse validation is still needed to confirm exact driver type strings and nullable `FixedString(64)` round trips under selected ClickHouse/clickhouse-connect versions.
9. Static bearer authentication is appropriate for local/self-hosted trusted deployments but Cloud Run production should gain a workload-identity/IAP/OIDC adapter rather than depending only on a long-lived shared token.
10. Rate limiting, TLS termination/network policy, and WSGI server process behavior remain deployment responsibilities and have not been empirically exercised.

## Highest-priority backlog

- Run `tests/test_production_ingest.py`, `tests/test_ingest_api.py`, `tests/test_ingest_runtime.py`, `tests/test_schema_preflight.py`, extraction persistence tests, and the full credential-free suite in a runnable checkout; fix any concrete integration/type issues.
- Add a workload-identity/IAP/OIDC `ReviewerIdentityProvider` implementation for production Cloud Run while retaining `StaticBearerIdentityProvider` for local/self-hosted setups.
- Run production composition plus migration 002/schema preflight against a disposable authorized ClickHouse instance and verify readiness transitions empirically.
- Run the deterministic ffmpeg fixture generator and `takekeeper-live-benchmark` against one authorized Gemini/Vertex candidate using self-owned generated media.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Add a production Google Cloud identity adapter for `IngestHttpApp` (IAP/OIDC/workload identity): verify signed Google identity tokens server-side, map only trusted claims to an actor, preserve the existing narrow `ReviewerIdentityProvider` protocol, keep static bearer auth for local/self-hosted use, and add credential-free token-verifier tests proving invalid audience/issuer/expiry fails closed without leaking token contents.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://clickhouse.com/docs/operations/system-tables/columns
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
