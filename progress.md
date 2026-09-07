# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed multimodal extraction, fail-closed continuity projection, Gemini/Vertex transport, objective multimodal benchmarks, deterministic synthetic-video generation, live external-media candidate evaluation, trusted media provenance, immutable trusted media byte identity, and bounded extraction-schema readiness.

This run turns schema readiness from an optional helper into the canonical production ingestion invariant. `SchemaGatedIngestService` starts closed, performs the trusted ClickHouse extraction-schema preflight before opening, invokes extraction/persistence only while ready, and revokes readiness before every recheck so a failed post-deploy validation cannot leave a previously-ready process accepting takes.

## Inspected this run

- Read the previous `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and the connected account has push/admin permission.
- Inspected `src/takekeeper/schema_preflight.py` and confirmed it already performs two bounded, parameterized metadata reads for `extraction_runs` and `extracted_observations`.
- Inspected `src/takekeeper/extraction.py` for the trusted `TakeExtractionRequest`, extractor contract, and model/scope validation boundary.
- Inspected `src/takekeeper/extraction_store.py` for the append-only extraction provenance protocol and ClickHouse writer.
- Inspected `src/takekeeper/__init__.py`, `tests/test_schema_preflight.py`, `SCHEMA_READINESS.md`, and `README.md` to keep the new runtime boundary aligned with existing public APIs and documentation.
- Confirmed there was no existing canonical ingest bootstrap/readiness service enforcing the schema preflight.

## Exact changes made this run

### Canonical schema-gated ingestion runtime

Added `src/takekeeper/ingest_runtime.py` with:

- `SchemaGatedIngestService` as the production extraction entry boundary;
- `IngestReadiness`, exposing only coarse `ready/not_ready` state plus whether schema checking completed;
- `IngestNotReady` for attempts to ingest before readiness;
- `IngestBootstrapError` for bounded provider/preflight failures without copying provider exception text;
- `IngestedTake`, carrying the governed extraction result plus persisted provenance record.

The service starts with ingestion closed. `start()` calls `require_extraction_schema_ready(...)` using the trusted application ClickHouse client and only flips readiness to `ready` after the current schema contract passes. `ingest(...)` refuses to invoke the extractor or persistence store while closed.

### Revalidation fails closed

`start()` deliberately clears readiness before every preflight. This means a process that was previously healthy cannot remain open if a deployment/restart/revalidation later sees an old, partially migrated, or incompatible schema.

`close()` explicitly revokes readiness without querying ClickHouse, touching media, or mutating extraction history.

### Coarse readiness/privacy contract

The runtime readiness surface contains no:

- ClickHouse host or connection string;
- database/schema diff details;
- provider exception text;
- production/scene/take identifiers;
- media URI, MIME, hash, or byte size;
- Gemini output;
- credential or secret material.

`ClickHouseSchemaNotReady` remains the actionable migration failure from the schema gate. Unexpected metadata/provider failures are wrapped in a fixed `IngestBootstrapError` message while retaining the original exception only as the internal cause.

### Regression coverage

Added `tests/test_ingest_runtime.py` covering:

- ingestion denied before startup/preflight;
- a current schema opening ingestion after exactly the underlying bounded metadata checks;
- successful routing through extractor then provenance store;
- migration-002-old schema never opening ingestion;
- failed recheck revoking previously granted readiness;
- provider/preflight exception detail not escaping the bounded bootstrap error;
- explicit `close()` revoking readiness without extra ClickHouse queries or persistence mutations.

The tests use fake ClickHouse metadata, extractor, and store objects and require no credentials, cloud services, media, or writable database.

### Public API and documentation

- Exported `SchemaGatedIngestService`, `IngestReadiness`, `IngestNotReady`, `IngestBootstrapError`, and `IngestedTake` from `takekeeper`.
- Updated `SCHEMA_READINESS.md` to make `SchemaGatedIngestService` the recommended production composition boundary and document startup, revalidation, readiness, migration, and privilege separation semantics.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No Gemini/Vertex, ClickHouse, object-storage, or private-media credential was used.
- No production media was accessed or modified.
- No destructive ClickHouse operation was introduced.
- Schema checks remain metadata-read-only and migrations remain an out-of-band privileged operation.

## Validation / results

Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.

Implementation commits this run before this handoff update:

- `67b27625bd37bb988bda350c0e2bcf42b0781bd4` — enforce schema readiness at ingestion boundary;
- `e68b1abfb896d9823e6cdbf6fdb71926a870c6c2` — test schema-gated production ingestion;
- `40cc2251ee35d15b28b6a459407a9302dab6605b` — export production ingest runtime;
- `b313c7bb6212d7737c45b51d6f8252183e46e7cf` — tighten ingest runtime imports;
- `d5cf8223ebce1b6cf3ca9132106ba289f58509fc` — document enforced ingestion readiness boundary.

Structural review performed:

- verified the new service imports existing protocols/types rather than adding a dependency;
- verified ingestion checks `_ready` before extractor invocation;
- verified `start()` clears readiness before executing the preflight;
- verified old-schema failure leaves extractor/store call counts at zero in regression coverage;
- verified the public readiness object is intentionally coarse;
- verified no CI workflow or external service execution was introduced.

Executable validation is still unavailable in this automation environment because there is no runnable repository checkout exposed to the execution container. I therefore do **not** claim `tests/test_ingest_runtime.py`, `tests/test_schema_preflight.py`, or the full Python suite passes here. No GitHub Actions run was used as a workaround.

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

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists; schema readiness is implemented and now enforced by the canonical ingestion boundary; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review/schema-readiness/ingest-bootstrap paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review, trusted extraction scope, replacement isolation, immutable run retry identity, metadata-only preflight, and closed-by-default ingestion are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME metadata, byte identity, schema support, canonical ClickHouse persistence, rollout-skew detection, and schema-gated ingestion exist; live execution remains pending.

## Blockers / unknowns

1. A runnable local repository checkout is unavailable in this execution environment, so Python tests and ClickHouse DDL validation remain unexecuted here.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` video/schema behavior, latency, token usage, and provider failure modes remain unmeasured.
6. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql` before the updated persistence adapter writes the new fields; startup now detects this rollout skew and refuses ingestion.
7. Local SHA-256 hashing cannot prove immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/staged objects or use object generation/version guarantees.
8. A real ClickHouse validation is still needed to confirm exact driver type strings and nullable `FixedString(64)` round trips under the selected ClickHouse/clickhouse-connect versions.
9. The canonical domain ingestion boundary now exists, but there is not yet a production HTTP/worker entrypoint that exposes its coarse readiness state and accepts trusted requests only after `start()` succeeds.

## Highest-priority backlog

- Add a minimal authenticated production ingest API/worker composition around `SchemaGatedIngestService`, with `/healthz` independent of ClickHouse and `/readyz` returning only coarse readiness; prove POST ingestion cannot reach extraction while unready.
- Run `tests/test_ingest_runtime.py`, `tests/test_schema_preflight.py`, `tests/test_extraction_media_persistence.py`, `tests/test_extraction_store.py`, and the full credential-free suite in a normal checkout; fix any integration/type issues discovered.
- Run schema preflight, migration 002, extraction retry, and projection replacement against a disposable real ClickHouse instance.
- Run the deterministic ffmpeg fixture generator and `takekeeper-live-benchmark` against one authorized Gemini/Vertex candidate using self-owned generated media.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Add a small authenticated production ingest HTTP/worker entrypoint around `SchemaGatedIngestService` with separate liveness/readiness semantics, strict bounded JSON request validation, and regression tests proving an old/unreachable ClickHouse schema returns unready and cannot invoke Gemini or persistence. This makes the enforced domain boundary usable by a real deployment without broadening credentials or agent capabilities.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://clickhouse.com/docs/operations/system-tables/columns
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
