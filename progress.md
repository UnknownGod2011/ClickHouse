# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed multimodal extraction, fail-closed continuity projection, Gemini/Vertex transport, objective multimodal benchmarks, deterministic synthetic-video generation, live external-media candidate evaluation, and trusted media provenance.

This run completes the persistence half of trusted media provenance. The canonical ClickHouse extraction store now writes, reads, and immutably reconciles trusted media MIME type, SHA-256 byte identity, and byte size in addition to the existing locator fingerprint. A retry may resume an identical partially persisted run, but reusing the same `run_id` with different trusted media bytes, MIME metadata, or byte size now fails closed before any observation reconciliation proceeds.

## Inspected this run

- Read the previous `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and the connected account has push/admin permission.
- Inspected the canonical persistence path in `src/takekeeper/extraction_store.py`.
- Inspected `TakeExtractionRequest` trusted media fields and validation in `src/takekeeper/extraction.py`.
- Inspected the ClickHouse client protocol in `src/takekeeper/clickhouse_memory.py`.
- Inspected `tests/test_extraction_store.py` to preserve existing append-only in-memory semantics and tenant-scoped reads.
- Rechecked `sql/migrations/002_extraction_media_provenance.sql`; the existing additive migration matches the application columns now being written.
- Attempted a clean local clone for executable validation. DNS resolution for `github.com` still failed before checkout, so no local Python process could run against repository files.

## Exact changes made this run

### Extraction run records now retain trusted byte identity

Updated `src/takekeeper/extraction_store.py`:

- `ExtractionRunRecord` now includes:
  - `media_mime_type: str | None`;
  - `media_content_sha256: str | None`;
  - `media_byte_size: int | None`.
- `_records()` copies those fields only from the trusted `TakeExtractionRequest`; Gemini/model output has no path to populate or alter them.
- `media_fingerprint` remains explicitly documented as locator+duration identity and is not conflated with byte identity.

### ClickHouse inserts and reads now include media provenance

`ClickHouseExtractionProvenanceStore` now:

- includes all three trusted fields in `_RUN_COLUMNS`;
- writes them on new `extraction_runs` inserts;
- selects and reconstructs them in `_existing_run()`;
- selects and reconstructs them in tenant/scene/take-scoped `list_runs()`;
- preserves `None` for historical rows whose migration-added fields are null.

The application column order matches the additive migration/fresh schema contract. Existing historical rows remain readable because the columns are nullable.

### Immutable retry reconciliation now protects byte identity

`_run_payload()` now includes MIME type, content SHA-256, and byte size. Therefore the existing retry reconciler now rejects a reused `run_id` if any of these trusted immutable values differ from the persisted row.

This closes an important production ambiguity: two objects could share a locator/duration or a mutable object name while containing different bytes. When a trusted ingest boundary supplies a content digest, the run identity now protects that fact during acknowledgement-loss retries, partial persistence recovery, and duplicate submissions.

The retry error remains intentionally non-sensitive: it states that immutable provenance differs without echoing URIs, hashes, sizes, credentials, or provider payloads.

### Regression coverage

Added `tests/test_extraction_media_persistence.py` with an in-process fake ClickHouse client. It covers:

- trusted MIME/SHA-256/byte size written in the run insert;
- returned `ExtractionRunRecord` carrying the same fields;
- an identical same-`run_id` retry reconciling without a second run insert;
- same `run_id` + changed content SHA-256 failing closed;
- same `run_id` + changed MIME type failing closed;
- same `run_id` + changed byte size failing closed;
- `list_runs()` round-tripping the provenance fields;
- tenant-scoped run reads returning no data for another production.

The test deliberately uses an extraction result with zero observations so the cases isolate run-level retry/provenance behavior rather than observation reconciliation.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No Gemini/Vertex, ClickHouse, object-storage, or private-media credential was used.
- No production media was uploaded, downloaded, modified, deleted, or transcoded.
- No destructive ClickHouse operation was introduced.

## Validation / results

Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.

Implementation commits this run:

- `1a9d8ab516850192fc791fbcdf89c514f872ce41` — persist trusted media byte provenance and include it in immutable retry reconciliation;
- `b5def2f32cc8baaaa677f0e71fb61ca89f651fd8` — add credential-free retry/round-trip regression coverage.

Attempted local validation command path:

```text
git clone --depth 1 https://github.com/UnknownGod2011/ClickHouse.git
```

Result: the environment failed DNS resolution for `github.com` before checkout (`Could not resolve host: github.com`). Therefore the new Python tests and ClickHouse DDL were structurally reviewed but are **not claimed as passing** in this environment. No GitHub Actions run was used as a workaround.

No live Gemini/Vertex request, real ClickHouse request, official MCP session, ffmpeg rendering, or production-media hash was performed.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for application writes or credential handling.
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

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review, trusted extraction scope, replacement isolation, and immutable run retry identity are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME metadata, byte identity, schema support, and canonical ClickHouse persistence wiring exist; live execution remains pending.

## Blockers / unknowns

1. A runnable local repository checkout is unavailable in this execution environment because DNS resolution for `github.com` fails, so Python tests and ClickHouse DDL validation remain unexecuted here.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` video/schema behavior, latency, token usage, and provider failure modes remain unmeasured.
6. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql` before this updated persistence adapter writes the new fields.
7. Local SHA-256 hashing cannot prove immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/staged objects or use object generation/version guarantees.
8. A real ClickHouse validation is still needed to confirm the exact Python driver round-trip representation for nullable `FixedString(64)` under the selected ClickHouse/clickhouse-connect versions, although the adapter follows the existing string conversion pattern.

## Highest-priority backlog

- Run `tests/test_extraction_media_persistence.py`, `tests/test_extraction_store.py`, and the full credential-free suite in a normal checkout; fix any integration/type issues discovered.
- Add a safe migration preflight/readiness check so deployments fail with an actionable non-secret error if application code is newer than the ClickHouse schema, instead of discovering missing provenance columns during the first production extraction.
- Run the migration plus extraction retry/projection replacement against a disposable real ClickHouse instance.
- Run the deterministic ffmpeg fixture generator and `takekeeper-live-benchmark` against one authorized Gemini/Vertex candidate using self-owned generated media.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Add a bounded ClickHouse schema/readiness preflight for the trusted application connection that verifies the required extraction provenance columns (including MIME/SHA-256/byte size) before ingestion starts, with fake-client regression tests and a non-secret actionable migration error. This prevents application/schema rollout skew from turning the first real production extraction into the migration detector.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
