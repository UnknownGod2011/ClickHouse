# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed multimodal extraction, fail-closed continuity projection, Gemini/Vertex transport, objective multimodal benchmarks, deterministic synthetic-video generation, live external-media candidate evaluation, trusted media provenance, immutable trusted media byte identity, and a bounded extraction-schema readiness gate.

This run adds a production deployment preflight for the trusted ClickHouse application connection. TakeKeeper can now verify the exact `extraction_runs` and `extracted_observations` column/type contract before enabling ingestion, including the MIME/SHA-256/byte-size fields introduced by migration 002. Schema drift fails closed with a coarse actionable migration message instead of surfacing during the first production extraction.

## Inspected this run

- Read the previous `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and the connected account has push/admin permission.
- Inspected `src/takekeeper/extraction_store.py` and confirmed the trusted media provenance fields are now part of `_RUN_COLUMNS`, reads, writes, and immutable retry reconciliation.
- Inspected the trusted ClickHouse client protocol in `src/takekeeper/clickhouse_memory.py`.
- Inspected `sql/schema.sql` and `sql/migrations/002_extraction_media_provenance.sql` to derive the exact application schema contract.
- Inspected `pyproject.toml`; no new dependency is required for the preflight.
- Searched for an existing schema/readiness implementation and found none.
- Attempted executable validation from a clean clone; the runtime still cannot resolve `github.com`, so Python could not start against the repository checkout.

## Exact changes made this run

### Bounded extraction schema preflight

Added `src/takekeeper/schema_preflight.py`.

It provides:

- `check_extraction_schema(client, database=...)` for a read-only report;
- `require_extraction_schema_ready(client, database=...)` for a fail-closed deployment/worker startup gate;
- `SchemaPreflightReport` with deterministic `ready`, checked tables, missing columns, and incompatible columns;
- `ClickHouseSchemaNotReady` with an intentionally coarse remediation message.

The check performs exactly two parameterized reads against `system.columns`, one for `extraction_runs` and one for `extracted_observations`. Each read is bounded with `max_result_rows=64` and `result_overflow_mode=throw`.

No production rows, media locators, media hashes, Gemini output, tenant identifiers, or credentials are read. Database names and table names are sent as query parameters rather than interpolated into SQL.

### Migration 002 rollout skew is detected before ingestion

The `extraction_runs` readiness contract explicitly verifies:

- `media_mime_type` as nullable low-cardinality string metadata;
- `media_content_sha256` as nullable `FixedString(64)`;
- `media_byte_size` as nullable `UInt64`;
- the existing locator fingerprint, trusted scope, duration, extractor identity, prompt-schema identity, and timestamp columns.

The companion `extracted_observations` table is checked in the same gate so a deployment cannot pass run-table readiness but fail on the first observation insert.

Missing/incompatible columns do not echo observed database types, connection strings, database names, media data, hashes, or credentials in the raised readiness exception. The operator receives only a bounded instruction to apply `sql/schema.sql` for a fresh deployment or pending `sql/migrations/*.sql` for an upgrade and rerun the preflight.

### Regression coverage

Added `tests/test_schema_preflight.py` covering:

- a current schema passing;
- exactly two bounded `system.columns` reads;
- migration-002 provenance columns missing from an older deployment;
- an incompatible content-hash column type;
- a missing `extracted_observations` table surfacing as required columns missing;
- invalid database identifiers rejected before any query;
- database/table values remaining parameterized rather than interpolated;
- no command or insert operation being used by the preflight.

### Operator/deployment documentation

Added `SCHEMA_READINESS.md` with the recommended startup sequence:

1. create the separately permissioned trusted application ClickHouse client;
2. run `require_extraction_schema_ready(...)` before accepting ingestion or starting extraction workers;
3. fail the deployment/readiness transition if the check fails;
4. apply migrations out of band using appropriately privileged credentials;
5. restart/recheck with the normal lower-privilege application connection.

The document reiterates that Gemini, the browser UI, and the official ClickHouse MCP server must not receive migration privileges.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No Gemini/Vertex, ClickHouse, object-storage, or private-media credential was used.
- No production media was accessed or modified.
- No destructive ClickHouse operation was introduced.
- The readiness path is metadata-read-only and does not perform migrations automatically.

## Validation / results

Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.

Implementation commits this run:

- `40a7b6e5a0f8d8438a9426d54119eb694e2f5620` — add bounded ClickHouse extraction schema preflight;
- `cfaeea67af45614b57fb59cab97e1ccd4ec5fb0e` — add credential-free schema-preflight regression coverage;
- `03add05055ef0ecdf367d09742fc1e00371d10d6` — document the production schema readiness gate.

Attempted validation:

```text
git clone --depth 1 https://github.com/UnknownGod2011/ClickHouse.git /tmp/takekeeper-check
PYTHONPATH=src python -m unittest tests.test_schema_preflight -v
```

Result: clone failed before checkout because DNS resolution for `github.com` failed (`Could not resolve host: github.com`). Therefore the new Python test suite is structurally reviewed but is **not claimed as passing** in this environment. No GitHub Actions run was used as a workaround.

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

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists; schema readiness is now implemented structurally; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review/schema-readiness paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review, trusted extraction scope, replacement isolation, immutable run retry identity, and metadata-only preflight are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME metadata, byte identity, schema support, canonical ClickHouse persistence, and rollout-skew detection exist; live execution remains pending.

## Blockers / unknowns

1. A runnable local repository checkout is unavailable in this execution environment because DNS resolution for `github.com` fails, so Python tests and ClickHouse DDL validation remain unexecuted here.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` video/schema behavior, latency, token usage, and provider failure modes remain unmeasured.
6. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql` before the updated persistence adapter writes the new fields; the new preflight now detects this rollout skew before ingestion.
7. Local SHA-256 hashing cannot prove immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/staged objects or use object generation/version guarantees.
8. A real ClickHouse validation is still needed to confirm exact driver type strings and nullable `FixedString(64)` round trips under the selected ClickHouse/clickhouse-connect versions.
9. The new readiness helper is available for deployment/startup wiring, but there is not yet one canonical production service bootstrap that invokes it automatically before opening the ingest surface.

## Highest-priority backlog

- Wire `require_extraction_schema_ready(...)` into the canonical production ingest/bootstrap boundary once that service entry point is identified/standardized, and expose only a coarse ready/not-ready operator status.
- Run `tests/test_schema_preflight.py`, `tests/test_extraction_media_persistence.py`, `tests/test_extraction_store.py`, and the full credential-free suite in a normal checkout; fix any integration/type issues discovered.
- Run schema preflight, migration 002, extraction retry, and projection replacement against a disposable real ClickHouse instance.
- Run the deterministic ffmpeg fixture generator and `takekeeper-live-benchmark` against one authorized Gemini/Vertex candidate using self-owned generated media.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Create/standardize the production ingestion bootstrap so the trusted ClickHouse client must pass `require_extraction_schema_ready(...)` before the ingest worker/API becomes ready, with a coarse readiness surface and fake-client tests proving an old schema cannot accept a take. This turns the new preflight from a callable guard into an enforced deployment invariant.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://clickhouse.com/docs/operations/system-tables/columns
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
