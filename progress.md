# TakeKeeper Progress

## Current status

TakeKeeper is a personal open-source production-memory system with deterministic continuity comparison, ClickHouse-backed state, bounded read-only ClickHouse MCP access, append-only extraction/review provenance, governed multimodal extraction, fail-closed continuity projection, Gemini/Vertex transport, objective multimodal benchmarks, deterministic synthetic-video generation, live external-media candidate evaluation, and trusted media provenance utilities.

This run wires trusted production-media metadata into the canonical extraction request/prompt and Google transport. Extensionless private/signed `https://` or `gs://` video can now be sent to Gemini when trusted ingest supplies an allow-listed MIME type. Optional content SHA-256 and byte size now travel with the extraction prompt as application-owned provenance metadata, without being copied into model prompt text. Fresh and existing ClickHouse deployments also have schema support for those fields, although the current `ClickHouseExtractionProvenanceStore` still needs to persist them.

## Inspected this run

- Read the previous `progress.md` completely before deciding what to change.
- Confirmed `UnknownGod2011/ClickHouse` on `main` is the intended repository and the connected account has push/admin permission.
- Inspected the recursive repository tree plus the current extraction and provenance path, especially:
  - `src/takekeeper/extraction.py`;
  - `src/takekeeper/google_genai_transport.py`;
  - `src/takekeeper/media_provenance.py`;
  - `src/takekeeper/extraction_store.py`;
  - `sql/schema.sql`;
  - `tests/test_google_genai_transport.py`;
  - `tests/test_extraction_store.py`.
- Confirmed the highest-priority unblocked gap was trusted MIME/content identity propagation rather than more benchmark-only work.
- Preserved tenant scope, configured-property/value registries, local response validation, continuity projection policy, read-only MCP boundaries, append-only extraction history, and existing fixture compatibility.

## Exact changes made this run

### Canonical extraction request and prompt now carry trusted media metadata

Updated `src/takekeeper/extraction.py`:

- `TakeExtractionRequest` now has optional trusted fields:
  - `media_mime_type`;
  - `media_content_sha256`;
  - `media_byte_size`.
- Existing callers remain compatible because all three fields default to `None`.
- MIME metadata is allow-listed against TakeKeeper's supported video MIME set.
- Content SHA-256 must be lowercase 64-character hexadecimal.
- Byte size must be a positive integer and cannot be supplied without a content hash.
- `ExtractionPrompt` now carries the same three fields.
- `build_extraction_prompt()` propagates the fields as structured application metadata but does not include signed locators, content hashes, or byte size inside prompt text.

These values remain trusted ingest/application metadata; Gemini cannot return or override them.

### Google transport now supports extensionless trusted production media

Updated `src/takekeeper/google_genai_transport.py`:

- removed its duplicate MIME/scheme validation implementation;
- routes URI + optional explicit MIME through the shared `media_provenance.resolve_video_mime_type()` boundary;
- supports extensionless signed/object URLs only when trusted application metadata supplies an allow-listed MIME type;
- still rejects plaintext HTTP, malformed GCS locators, embedded URL credentials, unsupported MIME families, and MIME/suffix disagreement;
- still exposes no tools/function calls and still uses TakeKeeper's locally constructed structured-output schema;
- content SHA-256 and byte size are not sent as model text or model-controlled metadata; they remain available to persistence/provenance layers.

### Regression coverage

Added `tests/test_trusted_media_extraction.py` covering:

- request → prompt propagation of MIME/content hash/byte size;
- absence of signed locator/hash leakage into prompt text;
- extensionless signed HTTPS media accepted by Google transport with trusted `video/mp4` metadata;
- MIME/suffix conflict rejection;
- byte-size-without-content-hash rejection;
- malformed/uppercase content digest rejection;
- backward compatibility for ordinary suffix-based GCS media with no explicit metadata.

### ClickHouse schema migration

Added `sql/migrations/002_extraction_media_provenance.sql` for existing deployments. It adds, idempotently:

- `media_mime_type LowCardinality(Nullable(String))`;
- `media_content_sha256 Nullable(FixedString(64))`;
- `media_byte_size Nullable(UInt64)`.

Updated `sql/schema.sql` so fresh deployments create `takekeeper.extraction_runs` with the same columns.

The migration is additive and nullable so historical extraction rows remain valid and older application inserts can still omit the new columns while rolling forward.

### Repository safety

- No GitHub Actions workflow was added, modified, triggered, or rerun.
- No unrelated repository was touched.
- No Gemini/Vertex, ClickHouse, object-storage, or private-media credential was used.
- No production media was uploaded, downloaded, modified, deleted, or transcoded.
- No destructive ClickHouse operation was introduced.

## Validation / results

Files were written directly to `UnknownGod2011/ClickHouse` `main` through the authenticated GitHub connector.

Implementation commits this run:

- `a8287b822328368b4181f401ebba1779951befb6` — shared trusted MIME validation in Google transport;
- `7d4d0812ac78f29fa9473112be042a7b9832226e` — trusted media metadata through extraction requests/prompts;
- `9b10c9fd63084fccda9a361e3170529b310401b5` — trusted-media extraction regression tests;
- `45ea03d292dc5e6470bfb0631d37d858be122e9c` — additive ClickHouse provenance migration;
- `bd7ddeea14240c269bd583cd8a05211fb7c76043` — provenance fields in fresh schema.

A normal runnable checkout is still unavailable in this automation environment, so the Python tests and ClickHouse DDL were not executed here. They are structurally reviewed but **not claimed as passing**. No GitHub Actions run was used as a workaround.

No live Gemini/Vertex request, real ClickHouse request, official MCP session, ffmpeg rendering, or production-media hash was performed.

## Decisions locked

1. Official ClickHouse MCP remains read-only and is never reused for application writes or credential handling.
2. Trusted application writes use separately permissioned ClickHouse clients.
3. Agent-facing MCP access remains bounded; arbitrary agent SQL is not exposed.
4. Production/scene/take scope is trusted application metadata and never model output.
5. Only configured entity/property pairs and registry values can enter governed extraction.
6. Machine confidence is not human confirmation.
7. Extraction provenance is append-only; reprocessing creates a new run.
8. Continuity projection is stricter than extraction persistence; uncertain evidence cannot become current continuity state.
9. Missing/abstaining projected evidence becomes `insufficient_evidence`, never a mismatch.
10. Google structured output is a formatting aid, not a trust boundary; responses are locally validated.
11. Locator fingerprints and content hashes are distinct provenance concepts; locator hashing is never represented as byte identity.
12. Explicit MIME type, content SHA-256, byte size, production scope, model identity, and media identity are trusted application metadata and cannot be supplied by Gemini.
13. MIME/suffix disagreement fails closed.
14. Signed/private media URI values and content hashes must not be copied into prompts, logs, benchmark reports, or operator-visible error strings unless explicitly required by a trusted administrative surface.
15. Benchmark thresholds remain immutable after observing a candidate.
16. Live-service quality/security claims require real authorized execution and are not inferred from mocks.

## Gates

- **Gate A — live ClickHouse:** implementation/harness coverage exists; real-endpoint execution remains pending.
- **Gate B — continuity correctness:** deterministic comparison, persistence, governed projection, and stale-state convergence are implemented.
- **Gate C — evidence/review:** durable evidence, stable finding identity, append-only review, authenticated API, and operator console are implemented.
- **Gate D — editorial retrieval:** typed/bounded retrieval and SQL coverage exist; live official MCP execution remains pending.
- **Gate E — failure honesty:** extraction/persistence/MCP/review paths fail closed structurally; abstentions cannot become false mismatches.
- **Gate F — security:** tenant scope, parameter binding, read/write separation, authenticated review, trusted extraction scope, and replacement isolation are implemented structurally; live RBAC/write-denial proof remains pending.
- **Gate G — multimodal evidence:** governed extraction, Gemini transport, objective benchmark metrics, synthetic media, live candidate runner, trusted MIME metadata, content-identity fields, and ClickHouse schema support exist; full persistence wiring and live execution remain pending.

## Blockers / unknowns

1. A runnable local repository checkout is unavailable in this execution environment, so Python tests and ClickHouse DDL validation remain unexecuted here.
2. No reachable authorized disposable ClickHouse endpoint is available.
3. No Gemini/Vertex credentials or trusted uploaded benchmark media are available.
4. Official MCP runtime/auth/version behavior and explicit write denial remain unmeasured against a live server.
5. Live `google-genai` video/schema behavior, latency, token usage, and provider failure modes remain unmeasured.
6. `ClickHouseExtractionProvenanceStore` still omits `media_mime_type`, `media_content_sha256`, and `media_byte_size` from `ExtractionRunRecord`, insert columns, retry comparison payloads, and reads; therefore the new schema can store these fields but the canonical persistence adapter does not yet write them.
7. Existing deployments must apply `sql/migrations/002_extraction_media_provenance.sql` before an updated persistence adapter starts writing the new fields.
8. Local SHA-256 hashing cannot prove immutability if another writer replaces same-length bytes during the read; production ingest should hash immutable/staged objects or use object generation/version guarantees.

## Highest-priority backlog

- Wire `media_mime_type`, `media_content_sha256`, and `media_byte_size` through `ExtractionRunRecord` and `ClickHouseExtractionProvenanceStore`, including retry/reconciliation equality and tenant-scoped reads.
- Add persistence tests proving a retry cannot reuse a `run_id` with different content hash/MIME/byte size.
- Run the complete credential-free suite plus actual ffmpeg fixture generation in a normal checkout.
- Run `takekeeper-live-benchmark` against one authorized Gemini/Vertex candidate using generated self-owned media.
- Execute extraction retry/projection replacement against disposable real ClickHouse.
- Start official `ClickHouse/mcp-clickhouse` read-only, exercise continuity/editorial operations, and record explicit write denial.

## Single best next step

**Complete the persistence half of this provenance contract: extend `ExtractionRunRecord` and `ClickHouseExtractionProvenanceStore` so trusted MIME/content SHA-256/byte size are written, read, and included in immutable retry comparisons. Add regression coverage proving identical retries reconcile but a reused `run_id` with changed media byte identity fails closed.**

## Relevant implementation references

- https://clickhouse.com/integrations/python
- https://github.com/ClickHouse/clickhouse-connect
- https://github.com/ClickHouse/mcp-clickhouse
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/video-understanding
- https://ai.google.dev/gemini-api/docs/structured-output
