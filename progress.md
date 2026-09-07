# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed multimodal extraction, fail-closed continuity projection, Gemini/Vertex transport, objective multimodal benchmarks, deterministic synthetic-video generation, trusted media provenance, immutable trusted media byte identity, bounded extraction-schema readiness, and schema-gated production ingestion.

This run makes the schema-gated domain boundary usable by a real service layer. TakeKeeper now has a dependency-free authenticated WSGI ingest API with separate liveness/readiness semantics, bounded trusted request parsing, server-owned extractor/property policy, and fail-closed HTTP behavior when ClickHouse schema readiness is absent.

## Inspected this run

- Read the previous `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and the connected account has push/admin permission.
- Inspected `src/takekeeper/ingest_runtime.py` and confirmed `SchemaGatedIngestService` starts closed, rechecks ClickHouse schema before opening, and refuses extraction/persistence while unready.
- Inspected `src/takekeeper/extraction.py` to preserve `TakeExtractionRequest`, trusted media provenance validation, configured `PropertySpec` policy, and server-trusted model/scope metadata.
- Inspected `src/takekeeper/review_api.py` to reuse the existing bearer identity protocol and constant-time `StaticBearerIdentityProvider` rather than creating a second authentication abstraction.
- Inspected `src/takekeeper/__init__.py` and `pyproject.toml`; the core package intentionally has no mandatory runtime dependencies, so the ingress was implemented as WSGI rather than introducing a web framework dependency.
- Searched the repository for an existing health/readiness/ingest HTTP entrypoint and found none.

## Exact changes made this run

### Authenticated production ingest HTTP boundary

Added `src/takekeeper/ingest_api.py` with `IngestHttpApp`.

Endpoints:

- `GET /healthz` — process liveness only; independent of ClickHouse and unauthenticated for platform probes.
- `GET /readyz` — coarse `SchemaGatedIngestService` readiness; HTTP 200 only while ingestion is open, otherwise HTTP 503.
- `POST /v1/ingest` — authenticated trusted-take ingestion routed exclusively through `SchemaGatedIngestService.ingest(...)`.

The POST path authenticates before reading attacker-controlled request bytes.

### Server-owned extraction policy

The HTTP caller cannot supply or override:

- extractor/Gemini model identity;
- extractor implementation version;
- prompt schema version;
- arbitrary `PropertySpec` definitions;
- arbitrary allowed values for continuity properties.

Instead, deployments register named property profiles when constructing `IngestHttpApp`; requests can select only a configured profile name. This keeps mappings configurable for real productions without letting a network caller redefine the extraction trust boundary.

### Bounded request contract

The ingress enforces:

- 32 KiB maximum JSON body;
- JSON object only;
- exact allow-listed fields with unknown fields rejected;
- bounded production/scene/take/profile identifiers;
- 4096-character media locator ceiling;
- positive integer duration capped at 24 hours;
- optional MIME/hash/byte-size primitive-type checks followed by canonical `TakeExtractionRequest` domain validation;
- exact body-length reads so truncated bodies fail closed.

The API never accepts SQL, ClickHouse table names, MCP operations, model prompts, arbitrary schemas, or migration instructions.

### Failure/privacy behavior

- unready ingestion returns HTTP 503 and cannot reach the extractor/provenance store through the gated service;
- invalid/absent credentials return a fixed authentication response without echoing tokens;
- malformed payloads return a fixed `invalid request` response;
- unexpected provider/runtime failures return fixed `internal server error` without copying ClickHouse/Gemini exception text;
- all responses set `Cache-Control: no-store`;
- successful responses expose only run ID, trusted production/scene/take IDs, and observation count; media URI/hash/size and model output are not echoed;
- readiness exposes only `ready|not_ready` plus `schema_checked`, with no ClickHouse host/database/schema diff/provider detail.

### Regression coverage

Added `tests/test_ingest_api.py` covering:

- liveness independent of ClickHouse readiness;
- coarse readiness transitions and HTTP 503 fail-closed behavior;
- unready ingestion admitting no service request;
- successful authenticated ingress;
- server-owned model/version/property profile enforcement;
- unknown property-profile rejection;
- authentication before body read;
- invalid-token redaction;
- oversized body rejection;
- media provenance validation through the canonical domain contract;
- unexpected provider/service detail redaction.

Tests use fakes and require no ClickHouse, Gemini, object storage, production media, or credentials.

### Public API and documentation

- Exported `IngestHttpApp` from `takekeeper`.
- Added `INGEST_API.md` documenting lifecycle composition, endpoint semantics, server-owned policy, request bounds, failure behavior, privilege separation, private-media guidance, and credential-free test coverage.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No Gemini/Vertex, ClickHouse, object-storage, or private-media credential was used.
- No production media was accessed or modified.
- No destructive ClickHouse operation was introduced.
- ClickHouse MCP remains read-only and separate from trusted application writes.

## Validation / results

Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.

Implementation commits before this handoff update:

- `d1c8ced28d891450205db639e48247356ec96f70` — authenticated schema-gated ingest HTTP boundary;
- `4efb303421d5acb124abbd60e8623762560169a7` — ingest HTTP readiness/security regression tests;
- `fcc3bac80c61c5595989bace97a319654288c37e` — public `IngestHttpApp` export;
- `e911d00727b3fcc9bdfdfe08fae3700ae8439de8` — production ingest API documentation.

Structural review performed:

- verified authentication runs before `_read_json_body` on POST ingestion;
- verified `/healthz` does not call ClickHouse/readiness and `/readyz` exposes only the coarse domain state;
- verified POST ingestion has no alternate path around `SchemaGatedIngestService.ingest`;
- verified caller JSON cannot set extractor model/version/prompt schema or inline property registries;
- verified response/error payloads do not echo media provenance, credentials, or provider exception text;
- verified no new mandatory package dependency or CI workflow was introduced;
- re-fetched `tests/test_ingest_api.py` from `main` after writing it to confirm the committed content.

Executable validation is still unavailable in this automation environment because a runnable repository checkout is not exposed to the execution container. I therefore do **not** claim `tests/test_ingest_api.py`, `tests/test_ingest_runtime.py`, or the full Python suite passes here. No GitHub Actions run was used as a workaround.

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
16. Benchmark thresholds remain immutable after observing a candidate.
17. Live-service quality/security claims require real authorized execution and are not inferred from mocks.
18. Application/schema compatibility must be checked before enabling extraction ingestion; the first production take must never serve as the migration detector.
19. Schema readiness is metadata-read-only and must not implicitly grant migration privileges to the normal application connection.
20. Production extraction ingress starts closed and must route through `SchemaGatedIngestService`; successful schema preflight is required before Gemini/extraction or provenance persistence can run.
21. Revalidation revokes readiness before checking, so a failed schema recheck always leaves ingestion closed.
22. Network callers may select only server-configured property profiles; they cannot define model identity, prompt schema, or property/value registries.
23. Liveness and ingestion readiness are separate contracts: a healthy process may intentionally return unready while ClickHouse/schema safety is unresolved.
24. Production ingest HTTP errors are bounded and must not copy provider exception detail, media provenance, or credentials into responses.

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists; schema readiness is implemented, enforced, and surfaced through coarse HTTP readiness; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review/schema-readiness/ingest-bootstrap/HTTP-ingress paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review/ingest, trusted extraction scope, replacement isolation, immutable run retry identity, metadata-only preflight, closed-by-default ingestion, and server-owned extraction policy are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME metadata, byte identity, schema support, canonical ClickHouse persistence, rollout-skew detection, schema-gated ingestion, and bounded HTTP ingress exist; live execution remains pending.

## Blockers / unknowns

1. A runnable local repository checkout is unavailable in this execution environment, so Python tests and ClickHouse DDL validation remain unexecuted here.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` video/schema behavior, latency, token usage, and provider failure modes remain unmeasured.
6. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql` before the updated persistence adapter writes the new fields; startup detects this rollout skew and refuses ingestion.
7. Local SHA-256 hashing cannot prove immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/staged objects or use object generation/version guarantees.
8. A real ClickHouse validation is still needed to confirm exact driver type strings and nullable `FixedString(64)` round trips under selected ClickHouse/clickhouse-connect versions.
9. `IngestHttpApp` is a production-safe WSGI application boundary, but the repository does not yet have an environment-driven composition factory/serve command that constructs the actual ClickHouse client, provenance store, Gemini transport, identity provider, profiles, and schema-gated service for Cloud Run/self-hosted deployment.
10. Rate limiting/TLS/network policy remain deployment responsibilities and have not been empirically exercised.

## Highest-priority backlog

- Add an environment-driven production composition module/CLI that constructs the trusted ClickHouse client, Gemini transport, provenance store, schema-gated ingest service, bearer/workload identity adapter, and `IngestHttpApp` without exposing secrets in argv/logs; keep serving mechanism pluggable for Cloud Run/self-hosted WSGI.
- Run `tests/test_ingest_api.py`, `tests/test_ingest_runtime.py`, `tests/test_schema_preflight.py`, `tests/test_extraction_media_persistence.py`, `tests/test_extraction_store.py`, and the full credential-free suite in a normal checkout; fix integration/type issues discovered.
- Run schema preflight, migration 002, extraction retry, and projection replacement against a disposable real ClickHouse instance.
- Run the deterministic ffmpeg fixture generator and `takekeeper-live-benchmark` against one authorized Gemini/Vertex candidate using self-owned generated media.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Add the environment-driven production composition factory around `IngestHttpApp`: construct ClickHouse/Gemini/provenance dependencies from secret-safe environment configuration, call `SchemaGatedIngestService.start()` before readiness can become 200, define server-owned property profiles, and add credential-free composition tests proving missing/invalid configuration fails closed without leaking secret values.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://clickhouse.com/docs/operations/system-tables/columns
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
